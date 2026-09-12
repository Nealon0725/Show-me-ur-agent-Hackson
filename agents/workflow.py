"""Bounded observe -> act -> follow-up -> re-evaluate -> human review loop."""
from agents.parsers import parse_jd, lines
from agents.screening import evaluate
from tools.store import Store


class Workflow:
    def __init__(self, path, resume_parser=None):
        self.store = Store(path)
        self.resume_parser = resume_parser

    def create(self, jd, resumes):
        job = parse_jd(jd)
        if not isinstance(resumes, list) or not 1 <= len(resumes) <= 30:
            raise ValueError('Provide 1–30 resumes.')
        for resume in resumes:
            lines(resume)
        state = {'job': job, 'criteria_confirmed': False, 'events': [], 'candidates': [
            {'id': 'C%03d' % (i+1), 'text': text, 'answers': {}, 'round': 0,
             'action': 'CONFIRM_CRITERIA', 'decision': None} for i, text in enumerate(resumes)]}
        self.event(state, 'JD_PARSED', 'Human confirmation required before screening.')
        return self.store.create(state)

    @staticmethod
    def event(state, action, detail):
        state['events'].append({'step': len(state['events']) + 1, 'action': action, 'detail': detail})

    def screen(self, state, candidate):
        result = evaluate(candidate['text'], state['job']['criteria'], candidate['answers'], self.resume_parser)
        candidate['evaluation'] = result
        candidate['decision'] = None
        if result['missing_information'] and candidate['round'] < 2:
            candidate['action'] = 'REQUEST_INFORMATION'
        else:
            candidate['action'] = 'HUMAN_REVIEW'
        self.event(state, 'RE_EVALUATE' if candidate['round'] else 'SCREEN', candidate['id'])
        self.event(state, candidate['action'], candidate['id'] + ': draft questions only; no messages sent.')

    def update(self, run_id, operation, payload):
        state = self.store.get(run_id)
        if operation == 'confirm':
            if state['criteria_confirmed']:
                raise ValueError('Criteria already confirmed. Create a new run to change the JD.')
            if not state['job']['criteria']:
                raise ValueError('No supported skills found. Add explicit skills to the JD.')
            state['criteria_confirmed'] = True
            self.event(state, 'CRITERIA_CONFIRMED', 'Recruiter confirmed extracted criteria.')
            for candidate in state['candidates']:
                self.screen(state, candidate)
        else:
            if not state['criteria_confirmed']:
                raise ValueError('Confirm criteria first.')
            candidate = next((c for c in state['candidates'] if c['id'] == payload.get('candidate_id')), None)
            if candidate is None:
                raise ValueError('Unknown candidate.')
            if operation == 'followup':
                if candidate['action'] != 'REQUEST_INFORMATION':
                    raise ValueError('This candidate is not awaiting clarification.')
                answers = payload.get('answers')
                if not isinstance(answers, dict) or not answers:
                    raise ValueError('Provide at least one answer.')
                allowed = {q['criterion_id'] for q in candidate['evaluation']['questions']}
                for key, answer in answers.items():
                    if key not in allowed or not isinstance(answer, dict):
                        raise ValueError('Invalid answer criterion.')
                    if answer.get('status') not in ('evidenced', 'not_met', 'unknown'):
                        raise ValueError('Answer status must be evidenced, not_met or unknown.')
                    lines(answer.get('evidence'))
                candidate['answers'].update(answers)
                candidate['round'] += 1
                self.event(state, 'FOLLOWUP_RECORDED', candidate['id'] + ': recruiter-recorded evidence')
                self.screen(state, candidate)
            elif operation == 'review':
                if candidate['decision'] is not None:
                    raise ValueError('Decision already recorded.')
                decision = payload.get('decision')
                if decision not in ('shortlist', 'hold', 'decline'):
                    raise ValueError('Choose shortlist, hold or decline.')
                lines(payload.get('reason'))
                candidate['decision'] = {'decision': decision, 'reason': payload['reason']}
                candidate['action'] = 'COMPLETE'
                self.event(state, 'HUMAN_DECISION', candidate['id'] + ': ' + decision)
            else:
                raise ValueError('Unknown operation.')
        self.store.save(run_id, state)
        return state
