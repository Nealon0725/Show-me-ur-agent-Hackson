import json
import tempfile
import unittest
from pathlib import Path
from agents.workflow import Workflow


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'test.sqlite3'
        self.workflow = Workflow(self.path)
        self.run = self.workflow.create('Accounts Executive\nRequired: Excel, Xero\nGST preferred', ['Excel for reporting'])

    def tearDown(self):
        self.temp.cleanup()

    def test_full_loop_and_persistence(self):
        run = self.workflow.update(self.run['id'], 'confirm', {})
        c = run['candidates'][0]
        self.assertEqual(c['evaluation']['score'], 40)
        self.assertEqual(c['action'], 'REQUEST_INFO')
        run = self.workflow.update(run['id'], 'followup', {'candidate_id': 'C001', 'answers': {
            'xero': {'status': 'evidenced', 'evidence': 'Used Xero for invoicing for one year.'},
            'gst': {'status': 'not_met', 'evidence': 'I have no GST experience.'}}})
        self.assertEqual(run['candidates'][0]['evaluation']['score'], 80)
        self.assertEqual(run['candidates'][0]['action'], 'SHORTLIST')
        self.assertIsNone(run['candidates'][0]['decision'])
        run = self.workflow.update(run['id'], 'review', {'candidate_id': 'C001', 'decision': 'shortlist', 'reason': 'Reviewed skill evidence and other job requirements.'})
        self.assertEqual(Workflow(self.path).store.get(run['id']), run)
        with self.assertRaises(ValueError):
            self.workflow.update(run['id'], 'followup', {'candidate_id': 'C001', 'answers': {}})

    def test_confirmation_and_validation(self):
        with self.assertRaises(ValueError):
            self.workflow.update(self.run['id'], 'review', {'candidate_id': 'C001'})
        for jd, resumes in [('', ['Excel']), ('Excel', []), ('Excel', [''])]:
            with self.assertRaises(ValueError):
                self.workflow.create(jd, resumes)
        run = self.workflow.create('Unrecognized role', ['Text'])
        with self.assertRaises(ValueError):
            self.workflow.update(run['id'], 'confirm', {})

    def test_round_limit_and_unknown_not_negative(self):
        run = self.workflow.update(self.run['id'], 'confirm', {})
        self.assertEqual(run['candidates'][0]['evaluation']['details'][1]['status'], 'unknown')
        for _ in range(2):
            run = self.workflow.update(run['id'], 'followup', {'candidate_id': 'C001', 'answers': {'xero': {'status': 'unknown', 'evidence': 'Awaiting more details.'}}})
        self.assertEqual(run['candidates'][0]['action'], 'HUMAN_REVIEW')

    def test_negation_and_demographics(self):
        from agents.parsers import parse_jd
        from agents.screening import evaluate
        criteria = parse_jd('Required: Xero')['criteria']
        self.assertEqual(evaluate('No Xero experience', criteria)['details'][0]['status'], 'not_met')
        first = evaluate('Used Xero\nAge: 25\nNationality: Singaporean', criteria)
        second = evaluate('Used Xero\nAge: 55\nNationality: Malaysian', criteria)
        self.assertEqual(first, second)


if __name__ == '__main__':
    unittest.main()
