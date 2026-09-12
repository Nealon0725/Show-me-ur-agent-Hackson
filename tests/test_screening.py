import json
from pathlib import Path
import unittest

from agents.parsers import parse_jd
from agents.screening import evaluate


class EvidenceTests(unittest.TestCase):
    def test_three_accounting_examples(self):
        demo = json.loads((Path(__file__).resolve().parents[1] / 'data/demo.json').read_text(encoding='utf-8'))
        criteria = parse_jd(demo['jd'])['criteria']
        expected = [
            {'excel': 'evidenced', 'xero': 'evidenced', 'gst': 'evidenced', 'bookkeeping': 'evidenced', 'invoicing': 'evidenced', 'relevant_experience': 'evidenced'},
            {'excel': 'evidenced', 'xero': 'unknown', 'gst': 'evidenced', 'bookkeeping': 'evidenced', 'invoicing': 'evidenced', 'relevant_experience': 'evidenced'},
            {'excel': 'unknown', 'xero': 'not_met', 'gst': 'unknown', 'bookkeeping': 'unknown', 'invoicing': 'unknown', 'relevant_experience': 'unknown'},
        ]
        for text, statuses in zip(demo['resumes'], expected):
            result = evaluate(text, criteria)
            self.assertEqual({d['id']: d['status'] for d in result['details']}, statuses)
            for detail in result['details']:
                self.assertTrue(detail['reason'])
                for ref in detail['evidence_refs']:
                    self.assertIn(ref['text'], text.splitlines()[ref['line'] - 1])
        self.assertEqual(result['unmet_requirements'], ['Xero'])
        self.assertNotIn('xero', [q['criterion_id'] for q in result['questions']])

    def test_denial_ambiguity_and_conflict(self):
        criteria = parse_jd('Required: Xero')['criteria']
        cases = {
            'No Xero experience.': 'not_met',
            'Never used Xero.': 'not_met',
            'Xero experience not specified.': 'unknown',
            'Familiar with Xero.': 'unknown',
            'Xero': 'unknown',
            'Used Xero.\nNo Xero experience.': 'needs_review',
            'Used Xero but no SAP experience.': 'evidenced',
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(evaluate(text, criteria)['details'][0]['status'], expected)

    def test_financial_context_requires_explicit_jd(self):
        text = 'Excel for office reports.'
        self.assertEqual(evaluate(text, parse_jd('Required: Excel')['criteria'])['details'][0]['status'], 'evidenced')
        self.assertEqual(evaluate(text, parse_jd('Required: Excel for financial tasks')['criteria'])['details'][0]['status'], 'unknown')

    def test_followup_preserves_resume_source(self):
        criteria = parse_jd('Required: Xero')['criteria']
        result = evaluate('Familiar with Xero.', criteria, {'xero': {'status': 'evidenced', 'evidence': 'Used Xero for invoices.'}})
        detail = result['details'][0]
        self.assertEqual(detail['status'], 'evidenced')
        self.assertEqual(detail['evidence_refs'][0]['source'], 'followup')
        self.assertEqual(detail['resume_evidence_refs'][0]['line'], 1)
        self.assertFalse(result['questions'])

    def test_relevant_experience_is_separate_from_skill_score(self):
        criteria = parse_jd('Accounts Executive\nRequired: Excel\n1–2 years of relevant experience')['criteria']
        cases = {
            'Accounts Assistant, 2 years\nUsed Excel for bookkeeping.': ('evidenced', 100),
            'Accounts Assistant, 6 months\nUsed Excel for bookkeeping.': ('not_met', 100),
            'Sales assistant, 2 years\nUsed Excel for reports.': ('unknown', 100),
            'No accounting experience\nUsed Excel for reports.': ('not_met', 100),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                result = evaluate(text, criteria)
                details = {item['id']: item for item in result['details']}
                self.assertEqual((details['relevant_experience']['status'], result['score']), expected)
                self.assertFalse(details['relevant_experience']['scored'])

    def test_job_marks_operational_items_for_human_review(self):
        job = parse_jd('Accounts Executive\n1 year relevant experience\nBudget SGD 4,000 per month')
        self.assertEqual(job['criteria'][-1]['minimum_years'], 1)
        items = {item['id']: item for item in job['human_review_items']}
        self.assertIn('Budget SGD', items['compensation']['source'])
        self.assertIsNone(items['work_eligibility']['source'])
