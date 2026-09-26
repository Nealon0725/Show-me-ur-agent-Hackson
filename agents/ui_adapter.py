"""Adapt uploaded resume evidence to the Clearhire candidate UI contract."""
import re
import uuid
from pathlib import Path


NEGATION = re.compile(r"\b(?:no|not|never|without|did not|don't|do not|haven't|hasn't)\b", re.I)
ACTION = re.compile(
    r"\b(?:built|developed|implemented|maintained|managed|prepared|performed|handled|used|using|"
    r"created|designed|wrote|updated|supported|coordinated|reconciled|investigated|delivered|submitted)\b",
    re.I,
)
DATE_RANGE = re.compile(r"(?P<sy>20\d{2})[-/](?P<sm>1[0-2]|0?[1-9])\s*(?:to|[-–—])\s*"
                        r"(?P<ey>20\d{2})[-/](?P<em>1[0-2]|0?[1-9])", re.I)
DURATION = re.compile(r"(?P<n>\d+(?:\.\d+)?)\s*(?P<unit>years?|months?)\b", re.I)
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)


JOBS = {
    'JD-001': {
        'minimum_months': 24,
        'criteria': [
            ('C1', 'Commercial experience', 'At least 24 months of commercial software development.',
             'duration', [r'software', r'develop', r'backend', r'frontend', r'full.?stack', r'web application']),
            ('C2', 'Backend development', 'Backend business logic and HTTP APIs in Python or JavaScript/TypeScript.',
             'groups', [[r'python', r'javascript', r'typescript', r'node\.js'],
                        [r'backend', r'http', r'\bapi\b', r'endpoint', r'route', r'business logic']]),
            ('C3', 'SQL & data modelling', 'SQL, relational data modelling or database migrations.',
             'groups', [[r'\bsql\b', r'postgres', r'mysql', r'sqlite', r'relational', r'database', r'migration', r'data model']]),
            ('C4', 'Git & automated tests', 'Both Git collaboration and automated tests.',
             'groups', [[r'\bgit\b', r'pull request', r'code review'],
                        [r'automated test', r'unit test', r'integration test', r'pytest', r'jest', r'mocha']]),
        ],
    },
    'JD-002': {
        'minimum_months': 12,
        'criteria': [
            ('C1', 'B2B sales experience', 'At least 12 months supporting B2B sales operations.',
             'duration', [r'\bb2b\b', r'sales operation', r'sales admin', r'commercial assistant']),
            ('C2', 'CRM operations', 'Maintaining CRM customer, opportunity or pipeline records.',
             'groups', [[r'\bcrm\b', r'hubspot', r'salesforce', r'zoho', r'dynamics']]),
            ('C3', 'Spreadsheet reporting', 'Spreadsheet reporting using pivot tables or lookup functions.',
             'groups', [[r'excel', r'spreadsheet'], [r'pivot', r'xlookup', r'vlookup', r'lookup']]),
            ('C4', 'Quotes & handovers', 'B2B quotations plus customer follow-up or order handover.',
             'groups', [[r'quotation', r'quote'], [r'follow.?up', r'handover', r'purchase order', r'order']]),
        ],
    },
    'JD-003': {
        'minimum_months': 12,
        'criteria': [
            ('C1', 'Accounts experience', 'At least 12 months of bookkeeping or accounts support.',
             'duration', [r'bookkeep', r'account', r'finance', r'billing', r'ledger']),
            ('C2', 'Payables & receivables', 'Both accounts payable and accounts receivable tasks.',
             'groups', [[r'accounts payable', r'\bap\b', r'supplier invoice', r'supplier payment'],
                        [r'accounts receivable', r'\bar\b', r'customer bill', r'customer invoice', r'collection', r'receipt']]),
            ('C3', 'Bank reconciliation', 'Bank reconciliations and investigation of differences.',
             'groups', [[r'bank'], [r'reconcil', r'investigat.*difference']]),
            ('C4', 'Finance tools', 'Both spreadsheets and accounting software for finance tasks.',
             'groups', [[r'excel', r'spreadsheet'], [r'xero', r'quickbooks', r'\bsap\b', r'accounting software']]),
        ],
    },
}


def _rows(text):
    if not isinstance(text, str) or not text.strip() or len(text) > 50000:
        raise ValueError('Provide between 1 and 50,000 characters of resume text.')
    return [{'line': i, 'text': row.strip()} for i, row in enumerate(text.splitlines(), 1) if row.strip()]


def _matches(row, patterns):
    return any(re.search(pattern, row, re.I) for pattern in patterns)


def _months(rows):
    values = []
    for row in rows:
        for match in DATE_RANGE.finditer(row['text']):
            start = int(match['sy']) * 12 + int(match['sm'])
            end = int(match['ey']) * 12 + int(match['em'])
            if end >= start:
                values.append(end - start + 1)
        for match in DURATION.finditer(row['text']):
            number = float(match['n'])
            values.append(round(number * 12 if match['unit'].lower().startswith('year') else number))
    return max(values, default=None)


def _fact(rows, spec, minimum_months):
    criterion_id, label, description, kind, config = spec
    if kind == 'duration':
        duration_rows = [row for row in rows if DATE_RANGE.search(row['text']) or DURATION.search(row['text'])]
        context_rows = [row for row in rows if _matches(row['text'], config)]
        refs = list({row['line']: row for row in duration_rows + context_rows}.values())
        months = _months(duration_rows)
        if months is not None and context_rows:
            status = 'evidenced' if months >= minimum_months else 'not_met'
        else:
            status = 'unknown'
    else:
        group_rows = [[row for row in rows if _matches(row['text'], group)] for group in config]
        positive = [[row for row in matches if not NEGATION.search(row['text'])] for matches in group_rows]
        negative = [row for matches in group_rows for row in matches if NEGATION.search(row['text'])]
        refs = list({row['line']: row for matches in group_rows for row in matches}.values())
        all_positive = all(matches for matches in positive)
        concrete = any(ACTION.search(row['text']) for matches in positive for row in matches)
        if all_positive and negative:
            status = 'needs_review'
        elif all_positive and concrete:
            status = 'evidenced'
        elif negative:
            status = 'not_met'
        else:
            status = 'unknown'
    reason = {
        'evidenced': 'The resume contains concrete, relevant work evidence; the recruiter should still verify the claim.',
        'not_met': 'The resume explicitly limits this experience or states less than the required duration.',
        'needs_review': 'The resume contains positive and negative statements that need human clarification.',
        'unknown': 'The resume does not provide enough specific evidence; missing information is not proof of inability.',
    }[status]
    return {
        'criterion_id': criterion_id,
        'label': label,
        'description': description,
        'status': status,
        'reason': reason,
        'evidence_refs': [{'source': 'resume', **row} for row in refs],
    }


def _profile(name, text, job_id, facts):
    rows = _rows(text)
    plain = [row['text'] for row in rows]
    first = next((row for row in plain if not re.fullmatch(r'(?:resume|curriculum vitae|cv)', row, re.I)), '')
    candidate_name = first[:80] if first and len(first) <= 80 else Path(name).stem
    role = next((row[:100] for row in plain[1:5] if not EMAIL.search(row)), 'Imported résumé')
    email = next((match.group(0) for row in plain for match in [EMAIL.search(row)] if match), '')
    vocabulary = ('Python', 'JavaScript', 'TypeScript', 'Node.js', 'SQL', 'PostgreSQL', 'MySQL', 'SQLite',
                  'Git', 'pytest', 'Jest', 'Mocha', 'CRM', 'HubSpot', 'Salesforce', 'Zoho', 'Excel',
                  'Xero', 'QuickBooks', 'SAP', 'bookkeeping', 'invoicing', 'GST')
    skills = [skill for skill in vocabulary if re.search(r'\b' + re.escape(skill) + r'\b', text, re.I)]
    ui_status = {'evidenced': 'demonstrated', 'not_met': 'explicitly_not_met',
                 'unknown': 'not_evidenced', 'needs_review': 'unclear'}
    criteria = []
    for fact in facts:
        refs = fact['evidence_refs']
        criteria.append({
            'criterion_id': fact['criterion_id'],
            'status': ui_status[fact['status']],
            'source_section': 'RESUME',
            'evidence_quote': '\n'.join(ref['text'] for ref in refs) or 'No specific resume evidence was found.',
            'interpretation': fact['reason'],
            'analysis_status': fact['status'],
        })
    evidenced = sum(item['status'] == 'demonstrated' for item in criteria)
    if evidenced == len(criteria):
        label = 'evidence_complete'
    elif any(item['status'] == 'unclear' for item in criteria):
        label = 'needs_clarification'
    elif evidenced >= max(1, len(criteria) // 2):
        label = 'evidence_partial'
    else:
        label = 'evidence_limited'
    return {
        'id': 'UP-' + uuid.uuid4().hex[:8],
        'jobId': job_id,
        'name': candidate_name,
        'role': role,
        'employer': '',
        'email': email,
        'skills': skills,
        'months': _months(rows),
        'education': '',
        'certifications': '',
        'experience': [],
        'project': '',
        'criteria': criteria,
        'label': label,
        'text': text,
        'pdf': None,
        'synthetic': False,
    }


def evaluate_ui_resumes(job_id, resumes, resume_parser=None):
    job = JOBS.get(job_id)
    if job is None:
        raise ValueError('Unknown Clearhire job.')
    if not isinstance(resumes, list) or not 1 <= len(resumes) <= 50:
        raise ValueError('Provide 1–50 resumes.')
    candidates = []
    for resume in resumes:
        if not isinstance(resume, dict) or not isinstance(resume.get('name'), str):
            raise ValueError('Each resume needs a file name and extracted text.')
        text = resume.get('text')
        rows = _rows(text)
        criteria = [{'id': spec[0], 'label': spec[1], 'description': spec[2], 'type': 'skill',
                     'required': True, 'scored': True, 'weight': 1, 'source': spec[2]}
                    for spec in job['criteria']]
        if resume_parser is None:
            facts = [_fact(rows, spec, job['minimum_months']) for spec in job['criteria']]
        else:
            parsed = resume_parser(text, criteria)
            facts = [dict(criterion_id=c['id'], label=c['label'], description=c['description'],
                          **parsed['facts'][c['id']]) for c in criteria]
        candidates.append(_profile(resume['name'], text, job_id, facts))
    return {'job_id': job_id, 'candidates': candidates,
            'analysis_note': 'Evidence coverage supports recruiter review; it is not a hiring probability.'}
