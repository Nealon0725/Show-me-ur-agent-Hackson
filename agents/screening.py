from agents.parsers import parse_resume


def evaluate(text, criteria, answers=None, resume_parser=None):
    profile = (resume_parser or parse_resume)(text, criteria)
    answers = answers or {}
    details = []
    for c in criteria:
        fact = profile['facts'][c['id']]
        if c['id'] in answers:
            answer = answers[c['id']]
            fact = {'status': answer['status'], 'evidence': ['Follow-up: ' + answer['evidence']],
                    'evidence_refs': [{'source': 'followup', 'text': answer['evidence'], 'line': None}],
                    'resume_evidence_refs': fact['evidence_refs'],
                    'reason': 'Evidence status confirmed by the recruiter from a follow-up answer.'}
        details.append(dict(c, **fact))
    weight = sum(c['weight'] for c in details if c.get('scored', True))
    earned = sum(c['weight'] for c in details if c.get('scored', True) and c['status'] == 'evidenced')
    unresolved = [c for c in details if c['status'] in ('unknown', 'needs_review')]
    return {'score': round(100 * earned / weight) if weight else None,
            'score_label': 'Documented skill coverage (not hiring probability)',
            'details': details, 'missing_information': [c['label'] for c in unresolved],
            'questions': [{'criterion_id': c['id'], 'question':
                           ('Please clarify the conflicting statements about ' if c['status'] == 'needs_review' else 'Please describe your experience with ')
                           + c.get('description', c['label']) + ', with a concrete task and dates.'} for c in unresolved],
            'unmet_requirements': [c['label'] for c in details if c['status'] == 'not_met'],
            'parser': profile['parser'], 'model_usage': profile.get('usage', {}),
            'model_request_id': profile.get('request_id')}
