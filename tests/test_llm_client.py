import unittest

from agents.llm_client import LLMClient, LLMClientError


SCHEMA = {'type': 'object', 'properties': {'ok': {'type': 'boolean'}},
          'required': ['ok'], 'additionalProperties': False}


class LLMClientTests(unittest.TestCase):
    def test_responses_protocol(self):
        captured = {}

        def request(payload):
            captured.update(payload)
            return {'id': 'resp_1', 'model': 'returned-model', 'output_text': '{"ok": true}',
                    'usage': {'input_tokens': 10, 'output_tokens': 4}}

        client = LLMClient('https://example.test/v1/responses', 'secret', 'requested-model',
                           style='responses', request_json=request)
        result = client.generate_json('Follow instructions.', {'value': 1}, SCHEMA, 'result')
        self.assertEqual(result.data, {'ok': True})
        self.assertEqual(result.request_id, 'resp_1')
        self.assertEqual(result.model, 'returned-model')
        self.assertFalse(captured['store'])
        self.assertEqual(captured['text']['format']['schema'], SCHEMA)

    def test_chat_completions_protocol(self):
        captured = {}

        def request(payload):
            captured.update(payload)
            return {'id': 'chat_1', 'choices': [{'message': {'content': '{"ok": true}'}}]}

        client = LLMClient('https://gateway.test/chat/completions', 'secret', 'gateway-model',
                           style='chat_completions', request_json=request)
        result = client.generate_json('Follow instructions.', {'value': 1}, SCHEMA, 'result')
        self.assertTrue(result.data['ok'])
        self.assertEqual(captured['response_format']['json_schema']['schema'], SCHEMA)
        self.assertEqual(captured['messages'][0]['role'], 'system')

    def test_json_object_and_prompt_compatibility_modes(self):
        payloads = []
        response = lambda payload: payloads.append(payload) or {'choices': [{'message': {'content': '{"ok": true}'}}]}
        for mode in ('json_object', 'prompt'):
            client = LLMClient('https://gateway.test', 'secret', 'model', structured_mode=mode,
                               request_json=response)
            client.generate_json('Instructions.', {}, SCHEMA, 'result')
        self.assertEqual(payloads[0]['response_format'], {'type': 'json_object'})
        self.assertIn('JSON object', payloads[0]['messages'][0]['content'])
        self.assertNotIn('response_format', payloads[1])
        self.assertIn('schema', payloads[1]['messages'][0]['content'])

    def test_rejects_invalid_configuration_and_output(self):
        with self.assertRaises(LLMClientError):
            LLMClient('', 'secret', 'model')
        client = LLMClient('https://gateway.test', 'secret', 'model',
                           request_json=lambda _: {'choices': [{'message': {'content': 'not json'}}]})
        with self.assertRaisesRegex(LLMClientError, 'invalid JSON'):
            client.generate_json('Instructions.', {}, SCHEMA, 'result')


if __name__ == '__main__':
    unittest.main()
