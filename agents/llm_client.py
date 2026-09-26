"""Small replaceable HTTP client for JSON-producing LLM gateways."""
import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class LLMClientError(ValueError):
    """Safe configuration, transport, or response error for API callers."""


@dataclass
class LLMResult:
    data: dict
    model: str
    usage: dict
    request_id: str | None = None


class LLMClient:
    STYLES = ('responses', 'chat_completions')
    STRUCTURED_MODES = ('json_schema', 'json_object', 'prompt')

    def __init__(self, endpoint, api_key, model, style='chat_completions',
                 structured_mode='json_schema', timeout=45, auth_header='Authorization',
                 auth_scheme='Bearer', request_json=None, provider='gateway'):
        if not endpoint or not api_key or not model:
            raise LLMClientError('LLM endpoint, API key and model are required.')
        if style not in self.STYLES:
            raise LLMClientError('LLM_API_STYLE must be responses or chat_completions.')
        if structured_mode not in self.STRUCTURED_MODES:
            raise LLMClientError('LLM_STRUCTURED_MODE must be json_schema, json_object or prompt.')
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model
        self.style = style
        self.structured_mode = structured_mode
        self.timeout = timeout
        self.auth_header = auth_header
        self.auth_scheme = auth_scheme
        self.request_json = request_json or self._request_json
        self.provider = provider

    def _request_json(self, payload):
        authorization = ((self.auth_scheme + ' ') if self.auth_scheme else '') + self.api_key
        request = Request(self.endpoint, data=json.dumps(payload).encode('utf-8'), method='POST', headers={
            self.auth_header: authorization,
            'Content-Type': 'application/json',
        })
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.load(response)
        except HTTPError as exc:
            try:
                body = json.loads(exc.read().decode('utf-8'))
                error = body.get('error')
                detail = error.get('message') if isinstance(error, dict) else str(error or '')
            except (UnicodeDecodeError, json.JSONDecodeError):
                detail = ''
            raise LLMClientError('LLM request failed (%s)%s.' %
                                 (exc.code, ': ' + detail if detail else '')) from exc
        except (URLError, TimeoutError) as exc:
            raise LLMClientError('LLM request could not be completed: ' + str(exc)) from exc

    def _payload(self, instructions, input_data, schema, schema_name):
        user_text = json.dumps(input_data, ensure_ascii=False)
        if self.structured_mode == 'prompt':
            instructions += '\nReturn JSON matching this schema exactly:\n' + json.dumps(schema)
        elif self.structured_mode == 'json_object':
            instructions += '\nReturn a JSON object only.'
        if self.style == 'responses':
            payload = {'model': self.model, 'store': False, 'instructions': instructions,
                       'input': user_text}
            if self.structured_mode == 'json_schema':
                payload['text'] = {'format': {'type': 'json_schema', 'name': schema_name,
                                              'strict': True, 'schema': schema}}
            elif self.structured_mode == 'json_object':
                payload['text'] = {'format': {'type': 'json_object'}}
            return payload

        payload = {'model': self.model, 'messages': [
            {'role': 'system', 'content': instructions},
            {'role': 'user', 'content': user_text},
        ]}
        if self.structured_mode == 'json_schema':
            payload['response_format'] = {'type': 'json_schema', 'json_schema': {
                'name': schema_name, 'strict': True, 'schema': schema}}
        elif self.structured_mode == 'json_object':
            payload['response_format'] = {'type': 'json_object'}
        return payload

    def _text(self, response):
        if self.style == 'responses':
            if isinstance(response.get('output_text'), str):
                return response['output_text']
            for item in response.get('output', []):
                for content in item.get('content', []):
                    if content.get('type') == 'output_text' and isinstance(content.get('text'), str):
                        return content['text']
        else:
            try:
                content = response['choices'][0]['message']['content']
            except (KeyError, IndexError, TypeError):
                content = None
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = [item.get('text', '') for item in content if isinstance(item, dict)]
                if any(parts):
                    return ''.join(parts)
        raise LLMClientError('LLM gateway returned no text output.')

    def generate_json(self, instructions, input_data, schema, schema_name):
        response = self.request_json(self._payload(instructions, input_data, schema, schema_name))
        try:
            data = json.loads(self._text(response))
        except json.JSONDecodeError as exc:
            raise LLMClientError('LLM gateway returned invalid JSON.') from exc
        if not isinstance(data, dict):
            raise LLMClientError('LLM gateway JSON output must be an object.')
        usage = response.get('usage') if isinstance(response.get('usage'), dict) else {}
        return LLMResult(data=data, model=response.get('model') or self.model, usage=usage,
                         request_id=response.get('id') or response.get('request_id'))
