import json
import os
import unittest
from unittest.mock import patch

from agents.model_provider import ModelProviderError, OpenAIResumeParser, parser_from_environment
from agents.parsers import parse_jd
from agents.screening import evaluate


class OpenAIProviderTests(unittest.TestCase):
    def setUp(self):
        self.criteria = parse_jd('Required: Excel for financial tasks\nRequired: Xero')['criteria']

    @staticmethod
    def response(evaluations):
        return {'output_text': json.dumps({'evaluations': evaluations})}

    def test_maps_validated_model_output_to_existing_contract(self):
        captured = {}

        def fake_request(payload):
            captured.update(payload)
            return self.response([
                {'criterion_id': 'excel', 'status': 'unknown',
                 'reason': 'Only general office reporting is stated.', 'evidence_lines': [2]},
                {'criterion_id': 'xero', 'status': 'not_met',
                 'reason': 'The resume explicitly denies Xero experience.', 'evidence_lines': [3]},
            ])

        parser = OpenAIResumeParser('test-key', model='test-model', request_json=fake_request)
        result = evaluate('Candidate\nExcel for office reports.\nNo Xero experience.', self.criteria,
                          resume_parser=parser)
        details = {item['id']: item for item in result['details']}
        self.assertEqual(details['excel']['status'], 'unknown')
        self.assertEqual(details['excel']['evidence_refs'][0]['line'], 2)
        self.assertEqual(details['xero']['status'], 'not_met')
        self.assertEqual(result['parser'], 'openai:test-model')
        self.assertEqual(result['model_usage'], {})
        self.assertFalse(captured['store'])
        self.assertEqual(captured['text']['format']['type'], 'json_schema')

    def test_rejects_missing_duplicate_and_invalid_evidence(self):
        invalid = [
            [{'criterion_id': 'excel', 'status': 'unknown', 'reason': 'Missing Xero.', 'evidence_lines': []}],
            [{'criterion_id': 'excel', 'status': 'unknown', 'reason': 'One.', 'evidence_lines': []},
             {'criterion_id': 'excel', 'status': 'unknown', 'reason': 'Two.', 'evidence_lines': []}],
            [{'criterion_id': 'excel', 'status': 'evidenced', 'reason': 'Claim.', 'evidence_lines': [99]},
             {'criterion_id': 'xero', 'status': 'unknown', 'reason': 'Absent.', 'evidence_lines': []}],
        ]
        for evaluations in invalid:
            with self.subTest(evaluations=evaluations):
                parser = OpenAIResumeParser('test-key', request_json=lambda _, e=evaluations: self.response(e))
                with self.assertRaises(ModelProviderError):
                    parser('Excel', self.criteria)

    def test_environment_selection(self):
        with patch.dict(os.environ, {'RECRUITMENT_AGENT_PROVIDER': 'rules'}, clear=True):
            self.assertIsNone(parser_from_environment())
        with patch.dict(os.environ, {'RECRUITMENT_AGENT_PROVIDER': 'openai'}, clear=True):
            with self.assertRaisesRegex(ModelProviderError, 'OPENAI_API_KEY'):
                parser_from_environment()
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test', 'OPENAI_MODEL': 'chosen'}, clear=True):
            self.assertEqual(parser_from_environment().model, 'chosen')
        with patch.dict(os.environ, {'LLM_API_URL': 'https://gateway.test', 'LLM_API_KEY': 'test',
                                     'LLM_MODEL': 'school-model', 'LLM_AUTH_SCHEME': 'none'}, clear=True):
            selected = parser_from_environment()
            self.assertEqual(selected.model, 'school-model')
            self.assertEqual(selected.client.style, 'chat_completions')
            self.assertEqual(selected.client.auth_scheme, '')


if __name__ == '__main__':
    unittest.main()
