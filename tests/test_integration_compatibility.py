import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from agents.parsers import parse_resume
from agents.workflow import Workflow


class IntegrationCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parser = Mock(side_effect=parse_resume)
        self.workflow = Workflow(Path(self.temp.name) / 'test.db', self.parser)

    def test_followup_reuses_original_evidence_and_completed_rank(self):
        run = self.workflow.create('Required: Excel, Xero', [
            'Used Excel for reporting.', 'Used Excel and Xero for invoicing.'])
        run = self.workflow.update(run['id'], 'confirm', {})
        self.assertEqual(self.parser.call_count, 2)
        run = self.workflow.update(run['id'], 'followup', {
            'candidate_id': 'C001', 'answers': {
                'xero': {'status': 'evidenced', 'evidence': 'Used Xero for invoices.'}}})
        self.assertEqual(self.parser.call_count, 2)
        rank = run['candidates'][0]['evaluation']['rank']
        run = self.workflow.update(run['id'], 'review', {
            'candidate_id': 'C001', 'decision': 'shortlist', 'reason': 'Demo review.'})
        self.assertEqual(run['candidates'][0]['evaluation']['rank'], rank)
        self.assertTrue(all('detail' in e and 'reason' in e for e in run['events']))
        with self.assertRaises(ValueError):
            self.workflow.update(run['id'], 'review', {
                'candidate_id': 'C001', 'decision': 'decline', 'reason': 'Overwrite.'})

    def test_legacy_run_restores_and_accepts_followup_without_model_call(self):
        run = self.workflow.create('Required: Xero', ['Xero experience not specified.'])
        run = self.workflow.update(run['id'], 'confirm', {})
        run.pop('workflow_state')
        run['job'].pop('criteria_version')
        candidate = run['candidates'][0]
        candidate.pop('state')
        candidate['action'] = 'REQUEST_INFORMATION'
        for key in ('action', 'documented_score', 'possible_score', 'evidence_completeness', 'rank', 'rank_status'):
            candidate['evaluation'].pop(key)
        self.workflow.store.save(run['id'], run)
        restored = self.workflow.get(run['id'])
        self.assertEqual(restored['candidates'][0]['action'], 'REQUEST_INFO')
        self.assertEqual(self.parser.call_count, 1)
        restored = self.workflow.update(run['id'], 'followup', {
            'candidate_id': 'C001', 'answers': {
                'xero': {'status': 'evidenced', 'evidence': 'Used Xero for invoices.'}}})
        self.assertEqual(restored['candidates'][0]['action'], 'SHORTLIST')
        self.assertEqual(self.parser.call_count, 1)
        self.assertEqual(self.workflow.store.get(run['id']), restored)

    def test_pending_followup_cannot_be_reviewed_or_answer_unrelated_criterion(self):
        run = self.workflow.create('Required: Xero', ['Xero experience not specified.'])
        run = self.workflow.update(run['id'], 'confirm', {})
        for operation, payload in [
            ('review', {'decision': 'shortlist', 'reason': 'Too early.'}),
            ('followup', {'answers': {'excel': {'status': 'evidenced', 'evidence': 'Used Excel.'}}}),
            ('followup', {'answers': {'xero': {'status': 'evidenced', 'evidence': ''}}}),
        ]:
            with self.subTest(operation=operation, payload=payload), self.assertRaises(ValueError):
                self.workflow.update(run['id'], operation, dict(candidate_id='C001', **payload))
        self.assertEqual(self.workflow.store.get(run['id']), run)

    def test_ranking_does_not_reorder_candidate_identity_in_api(self):
        run = self.workflow.create('Required: Xero', ['No Xero experience.', 'Used Xero for invoicing.'])
        run = self.workflow.update(run['id'], 'confirm', {})
        self.assertEqual([c['id'] for c in run['candidates']], ['C001', 'C002'])
        self.assertEqual([c['evaluation']['rank'] for c in run['candidates']], [2, 1])
