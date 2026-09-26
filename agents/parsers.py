"""Conservative English-text demo parsers; replace these with an LLM adapter later."""
import re

# Canonical skills and conservative aliases used by the offline extractor.  Aliases
# are evidence hints; the original resume sentence is always retained as evidence.
SKILL_ALIASES = {
    'Excel': ('Excel', 'Microsoft Excel', 'spreadsheets', 'spreadsheet reporting'),
    'Xero': ('Xero',),
    'GST': ('GST', 'goods and services tax'),
    'bookkeeping': ('bookkeeping', 'book keeping', 'book-keeping', 'maintained books'),
    'invoicing': ('invoicing', 'invoices', 'billing', 'accounts receivable'),
    'SQL': ('SQL', 'structured query language'),
    'Python': ('Python',),
    'SAP': ('SAP',),
    'accounting': ('accounting', 'accountancy', 'financial accounting'),
}
SKILLS = tuple(SKILL_ALIASES)
EXPERIENCE_RE = re.compile(r'(?P<low>\d+(?:\.\d+)?)\s*(?:[–—-]\s*(?P<high>\d+(?:\.\d+)?))?\s*\+?\s*years?\b', re.I)
MONTHS_RE = re.compile(r'(?P<months>\d+(?:\.\d+)?)\s*months?\b', re.I)
ACCOUNTING_CONTEXT_RE = re.compile(r'\b(account|accounting|accounts|finance|financial|bookkeep|invoic|gst|tax|audit|ledger|payroll)\w*\b', re.I)


def lines(text):
    if not isinstance(text, str) or not text.strip() or len(text) > 50000:
        raise ValueError('Provide between 1 and 50,000 characters of text.')
    return [s.strip(' •-\t') for s in re.split(r'[\n;]+|(?<=[.!?])\s+', text) if s.strip()]


def contains(text, skill):
    aliases = SKILL_ALIASES.get(skill, (skill,))
    return any(re.search(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', text, re.I)
               for alias in aliases)


def parse_jd(text):
    rows = lines(text)
    criteria = []
    for skill in SKILLS:
        evidence = [row for row in rows if contains(row, skill)]
        if evidence:
            preferred = all(re.search(r'preferred|nice.to.have|optional|a plus', row, re.I) for row in evidence)
            financial = skill == 'Excel' and any(re.search(r'financial|finance|reconciliation', row, re.I) for row in evidence)
            criteria.append({'id': skill.lower(), 'label': skill, 'aliases': list(SKILL_ALIASES[skill]), 'required': not preferred,
                             'weight': 1 if preferred else 2, 'source': evidence[0],
                             'type': 'skill', 'scored': True,
                             'context': 'financial' if financial else None,
                             'description': 'Excel for financial tasks' if financial else skill + ' experience'})
    for row in rows:
        match = EXPERIENCE_RE.search(row)
        if match and re.search(r'\b(experience|relevant|account|finance)\w*\b', row, re.I):
            minimum = float(match.group('low'))
            target = float(match.group('high')) if match.group('high') else minimum
            preferred = bool(re.search(r'preferred|nice.to.have|optional|a plus', row, re.I))
            criteria.append({'id': 'relevant_experience', 'label': 'Relevant accounting/finance experience',
                             'description': 'At least %s year%s of relevant accounting or finance experience' %
                                            (('%g' % minimum), '' if minimum == 1 else 's'),
                             'type': 'experience', 'required': not preferred, 'scored': False, 'weight': 0,
                             'minimum_years': minimum, 'target_years': target,
                             'context': 'accounting_finance', 'source': row})
            break
    review_specs = (
        ('education', 'Education and professional qualifications', r'\b(degree|diploma|education|qualification|acca|ca|cpa)\b'),
        ('compensation', 'Salary expectations and compensation fit', r'\b(salary|budget|compensation|sgd|\$)\b'),
        ('work_eligibility', 'Work eligibility', r'\b(work (?:permit|eligibility|authorization)|visa|citizen|permanent resident)\b'),
        ('availability', 'Availability and notice period', r'\b(availability|available|notice period|start date)\b'),
    )
    human_review_items = []
    for item_id, label, pattern in review_specs:
        source = next((row for row in rows if re.search(pattern, row, re.I)), None)
        human_review_items.append({'id': item_id, 'label': label, 'source': source,
                                   'reason': 'Recruiter verification required; excluded from automated scoring.'})
    return {'role': rows[0], 'criteria': criteria, 'raw_text': text,
            'human_review_items': human_review_items,
            'review_note': 'Confirm all extracted criteria before screening. Salary, education, availability and work eligibility require recruiter verification.'}


def evidence_rows(text):
    lines(text)  # Validate before preserving original line locations.
    return [{'text': part.strip(), 'line': number, 'source': 'resume'}
            for number, row in enumerate(text.splitlines(), 1)
            for part in re.split(r';|(?<=[.!?])\s+|\s+but\s+', row, flags=re.I)
            if part.strip()]


def classify(row, skill, context):
    token = re.escape(skill)
    # Only narrow, skill-specific denials count as explicit non-fulfilment.
    denial = (r'\b(?:no|without)\s+(?:\w+\s+){0,2}' + token + r'\s+experience\b|'
              r'\bnever\s+(?:used|worked with)\s+' + token + r'\b|'
              r'\b(?:do not|don\x27t)\s+have\s+(?:any\s+)?' + token + r'\s+experience\b')
    if re.search(denial, row, re.I):
        return 'not_met'
    if re.search(r'\b(no|not|never|without|lack|lacking|limited|familiar|learning|basic)\b', row, re.I):
        return 'unknown'
    if context == 'financial' and not re.search(r'\b(financial|finance|reconciliation|bookkeeping|invoicing|accounting)\b', row, re.I):
        return 'unknown'
    if not re.search(r'\b(used|using|prepared|managed|developed|built|performed|handled|for)\b', row, re.I):
        return 'unknown'
    return 'evidenced'


def duration_years(row):
    match = EXPERIENCE_RE.search(row)
    if match:
        return float(match.group('high') or match.group('low'))
    match = MONTHS_RE.search(row)
    return float(match.group('months')) / 12 if match else None


def experience_fact(rows, criterion):
    duration_refs = [row for row in rows if duration_years(row['text']) is not None]
    relevant_refs = [row for row in duration_refs if ACCOUNTING_CONTEXT_RE.search(row['text'])]
    explicit_denial = [row for row in rows if re.search(r'\b(?:no|without)\s+(?:relevant\s+)?(?:accounting|finance|financial)\s+experience\b', row['text'], re.I)]
    minimum = criterion['minimum_years']
    if explicit_denial and any(duration_years(row['text']) >= minimum for row in relevant_refs):
        status, refs = 'needs_review', explicit_denial + relevant_refs
        reason = 'The resume contains conflicting statements about relevant experience.'
    elif explicit_denial:
        status, refs = 'not_met', explicit_denial
        reason = 'The resume explicitly states no relevant accounting or finance experience.'
    elif any(duration_years(row['text']) >= minimum for row in relevant_refs):
        status, refs = 'evidenced', relevant_refs
        reason = 'The resume states relevant accounting or finance experience meeting the minimum duration; this self-report is unverified.'
    elif relevant_refs:
        status, refs = 'not_met', relevant_refs
        reason = 'The stated relevant experience duration is below the confirmed minimum.'
    else:
        status, refs = 'unknown', duration_refs
        reason = ('A duration is stated but its accounting or finance relevance is unclear.' if duration_refs
                  else 'No supported duration for relevant accounting or finance experience was found.')
    refs = list({(row['line'], row['text']): row for row in refs}.values())
    return {'status': status, 'evidence': [row['text'] for row in refs],
            'evidence_refs': refs, 'reason': reason}


def parse_resume(text, criteria):
    rows = evidence_rows(text)
    facts = {}
    for criterion in criteria:
        if criterion.get('type') == 'role_requirement':
            from agents.role_rules import role_fact
            facts[criterion['id']] = role_fact(rows, criterion)
            continue
        if criterion.get('type') == 'experience':
            facts[criterion['id']] = experience_fact(rows, criterion)
            continue
        skill = criterion['label']
        refs = [row for row in rows if contains(row['text'], skill)]
        statuses = {classify(row['text'], skill, criterion.get('context')) for row in refs}
        if 'not_met' in statuses and 'evidenced' in statuses:
            status, reason = 'needs_review', 'Positive and negative statements conflict; human clarification is required.'
        elif 'not_met' in statuses:
            status, reason = 'not_met', 'The resume explicitly states a lack of this experience.'
        elif 'evidenced' in statuses:
            status, reason = 'evidenced', 'The resume describes relevant use or work; this self-report has not been verified.'
        else:
            status = 'unknown'
            reason = ('The mention does not establish the required task context or concrete experience.'
                      if refs else 'No related evidence was found; absence is not evidence of inability.')
        facts[criterion['id']] = {'status': status, 'evidence': [r['text'] for r in refs],
                                  'evidence_refs': refs, 'reason': reason}
    return {'facts': facts, 'parser': 'deterministic_evidence_v2',
            'note': 'Evidence is self-reported text, not verified proficiency. Unknown does not mean unqualified.'}
