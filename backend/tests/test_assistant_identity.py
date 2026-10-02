"""Identity contracts through the existing gateway, council and SSE paths."""
import json
from unittest.mock import MagicMock
import httpx
import pytest
from pydantic import BaseModel
from app.core import config
from app.core.models_config import ModelRole, get_role_config
from app.services.gateway import assistant_identity as identity
from app.services.gateway.model_gateway import ModelGateway
from app.services.copilot.union_war_room import COUNCIL_DELEGATES, UnionWarRoomEngine
from app.services import ai_copilot

pytestmark = pytest.mark.unit
MODELS = ['deepseek-r1:7b', 'qwen3.5:9b', 'gemma4:latest', 'phi4-mini:latest', 'granite4:latest', 'llama3.1:8b']

@pytest.fixture(autouse=True)
def policy(monkeypatch):
    for key, value in {'ASSISTANT_NAME': 'HRIDAY', 'ASSISTANT_PRODUCT_NAME': 'HighView', 'ASSISTANT_IDENTITY_ENABLED': True, 'ASSISTANT_HIDE_MODEL_IDENTITY': True, 'ASSISTANT_ALLOW_MODEL_DISCLOSURE': True, 'ASSISTANT_MAX_IDENTITY_RETRIES': 1}.items():
        monkeypatch.setattr(config, key, value)
    monkeypatch.setattr('app.services.gateway.model_gateway.time.sleep', lambda *a: None)

@pytest.mark.parametrize('model', MODELS)
def test_greeting_corrective_retry(model):
    systems = []
    def generate(system):
        systems.append(system)
        return f"Hello! I'm {model}." if len(systems) == 1 else "Hello! I'm HRIDAY. How can I help?"
    result = identity.guarded_completion(generate, query='hi', runtime_model=model, task_system='Use verified facts.')
    assert result.text == "Hello! I'm HRIDAY. How can I help?"
    assert result.runtime_model == model and result.identity_guard_triggered and result.identity_retry_count == 1
    assert all('You are HRIDAY' in s and 'Use verified facts.' in s and model in s for s in systems)
    assert 'CORRECTIVE IDENTITY INSTRUCTION' in systems[1]

@pytest.mark.parametrize('query', ['Who are you?', 'what is your name', 'are you DeepSeek?', 'introduce yourself'])
def test_identity_question(query):
    result = identity.guarded_completion(lambda _: "I'm DeepSeek-R1.", query=query, runtime_model='qwen3.5:9b')
    assert result.text == "I'm HRIDAY, the AI assistant in HighView."
    assert result.identity_retry_count == 0

@pytest.mark.parametrize('query', ['Which model are you using right now?', 'which underlying model is answering me?', 'Which model is powering this response?', 'What model powers you?', 'what powers you?'])
def test_explicit_runtime_disclosure(query):
    result = identity.guarded_completion(lambda _: "I'm DeepSeek-R1.", query=query, runtime_model='qwen3.5:9b')
    assert result.text == "I'm HRIDAY, and this response is powered by qwen3.5:9b."
    assert 'unavailable' in identity.identity_answer(query)

@pytest.mark.parametrize('text', ['DeepSeek-R1 is a reasoning model. Qwen supports coding.', 'Compare DeepSeek and Qwen.', 'The problematic example is "I am DeepSeek-R1. How can I help?"', '> I am Qwen, your assistant.\nThis is a quote.', '```python\nprint("I am Gemma.")\n```\nThis is code.', '`I am Phi` is an example.', "I'm HRIDAY, and this response is powered by deepseek-r1:7b."])
def test_discussion_quotes_code_preserved(text):
    assert not identity.identity_leak(text, 'deepseek-r1:7b')
    guard = identity.IdentityStreamGuard('deepseek-r1:7b')
    emitted = ''.join(guard.feed(c) for c in text) + guard.finish()
    assert not guard.blocked and emitted == text

@pytest.mark.parametrize('text', ["I'm DeepSeek-R1.", 'I am Qwen3.5.', 'As Gemma, I can help.', 'My name is Phi-4.', 'I’m Granite4.', 'I am Llama3.1.', 'As an AI model developed by OpenAI, I can help.', "I'm HRIDAY, an AI assistant developed by Google.", 'I was trained by Microsoft.'])
def test_stream_leaks_never_emit_at_any_boundary(text):
    for split in range(len(text) + 1):
        guard = identity.IdentityStreamGuard('deepseek-r1:7b')
        emitted = guard.feed(text[:split]) + guard.feed(text[split:]) + guard.finish()
        assert guard.blocked and emitted == ''

def test_later_intro_and_bounded_retry():
    guard = identity.IdentityStreamGuard('qwen3.5:9b')
    assert guard.feed('Hello! ') == 'Hello!'
    assert guard.feed("I'm Qwen. Here is your answer.") == ''
    assert guard.finish() == '' and guard.feed('More text.') == ''
    calls = []
    result = identity.guarded_completion(lambda system: calls.append(system) or "I'm Gemma.", query='hi', runtime_model='gemma4')
    assert len(calls) == 2 and result.response_blocked and result.identity_retry_count == 1
    assert not identity.identity_leak(result.text)

def test_retry_transport_failure_is_safe():
    def generate(system):
        if 'CORRECTIVE' in system: raise httpx.HTTPError('offline')
        return "I'm Gemma."
    result = identity.guarded_completion(generate, query='hi', runtime_model='gemma4')
    assert result.response_blocked and result.identity_retry_count == 1

def test_configuration(monkeypatch):
    monkeypatch.setattr(config, 'ASSISTANT_NAME', 'Configured Assistant')
    assert 'Configured Assistant' in identity.identity_system_prompt('phi4')
    assert 'Configured Assistant' in identity.identity_answer('who are you')
    monkeypatch.setattr(config, 'ASSISTANT_ALLOW_MODEL_DISCLOSURE', False)
    assert 'phi4' not in identity.identity_answer('Which model powers you?', 'phi4')
    monkeypatch.setattr(config, 'ASSISTANT_IDENTITY_ENABLED', False)
    assert identity.identity_system_prompt('phi4', 'Existing system') == 'Existing system'
    assert not identity.identity_leak("I'm Qwen.")

class Schema(BaseModel):
    answer: str

def fake_chat(monkeypatch, callback):
    payloads = []
    def post(self, url, **kwargs):
        payload = kwargs['json']; payloads.append(payload)
        return MagicMock(json=lambda: {'message': {'content': callback(payload, len(payloads))}})
    monkeypatch.setattr(httpx.Client, 'post', post)
    return payloads

@pytest.mark.parametrize('task', ['reporting', 'data analysis', 'copilot', 'presentation', 'coding/debugging'])
def test_task_system_schema_compatibility(monkeypatch, task):
    task_system = f'Perform {task}; output JSON and preserve evidence.'
    payloads = fake_chat(monkeypatch, lambda p, n: '{"answer":"Verified [FACT-001]"}')
    result = ModelGateway.generate(ModelRole.ANALYST, 'Existing task', task_system, response_schema=Schema)
    assert result.success and result.parsed.answer == 'Verified [FACT-001]'
    p = payloads[0]
    assert p['messages'][0]['role'] == 'system' and p['messages'][0]['content'].startswith('You are HRIDAY')
    assert task_system in p['messages'][0]['content']
    assert p['messages'][1] == {'role': 'user', 'content': 'Existing task'} and p['format'] == 'json'
    assert result.runtime_model == p['model']

def test_schema_retry_keeps_identity(monkeypatch):
    payloads = fake_chat(monkeypatch, lambda p, n: 'invalid json' if n == 1 else '{"answer":"Success"}')
    result = ModelGateway.generate(ModelRole.ANALYST, 'Analyze', 'Preserve schema', response_schema=Schema, max_retries=1)
    assert result.success and len(payloads) == 2
    assert all('You are HRIDAY' in p['messages'][0]['content'] and 'Preserve schema' in p['messages'][0]['content'] for p in payloads)

def test_identity_retry_budget_across_fallback(monkeypatch):
    cfg = get_role_config(ModelRole.ANALYST)
    payloads = fake_chat(monkeypatch, lambda p, n: '{"answer":"I am Qwen."}' if p['model'] == cfg.primary else '{"answer":"Verified fallback"}')
    result = ModelGateway.generate(ModelRole.ANALYST, 'Analyze', response_schema=Schema)
    assert result.success and result.model_used == cfg.fallback
    assert result.identity_guard_triggered and result.identity_retry_count == 1
    assert [p['model'] for p in payloads] == [cfg.primary, cfg.primary, cfg.fallback]
    assert 'CORRECTIVE' in payloads[-1]['messages'][0]['content']

def test_council_actual_fallback_metadata_and_election(monkeypatch):
    calls = []
    def call(model, prompt, **kwargs):
        calls.append((model, kwargs.get('system_prompt')))
        if 'STRICT DEMOCRATIC VOTING RULE' in prompt: return 'VOTE_FOR: deepseek_reasoner\nRATIONALE: Evidence.'
        if model == COUNCIL_DELEGATES[1].primary_model: return ''
        return "I'm a fabricated model."
    monkeypatch.setattr('app.services.copilot.union_war_room._call_ollama_completion', call)
    result = UnionWarRoomEngine.execute_deliberation('Which model is powering this response?', timeout_seconds=5)
    assert result['runtime_model'] == COUNCIL_DELEGATES[1].fallback_model
    assert result['runtime_model'] in result['answer'] and result['answer'].startswith("I'm HRIDAY")
    assert result['elected_replier']['runtime_model'] == result['runtime_model']
    assert len(result['ballots']) == len(COUNCIL_DELEGATES)
    assert all('You are HRIDAY' in system for _, system in calls if system)
    assert 'Elected Council' not in result['answer'] and 'Elected Council' in result['raw_council_answer']

def prepare_legacy(monkeypatch, responses):
    monkeypatch.setattr(ai_copilot, 'infer_tool', lambda *a, **k: None)
    monkeypatch.setattr(ai_copilot, 'hybrid_search', lambda *a, **k: [])
    monkeypatch.setattr(ai_copilot, 'get_aggregate_context', lambda *a, **k: 'Verified domain context')
    monkeypatch.setattr('app.services.sheet_catalog.linked_evidence', lambda *a, **k: [])
    payloads = []
    class Response:
        def __init__(self, text): self.text = text
        def raise_for_status(self): pass
        def iter_lines(self):
            for c in self.text: yield json.dumps({'response': c})
        def json(self): return {'response': self.text}
        def __enter__(self): return self
        def __exit__(self, *a): pass
    class Client:
        def __init__(self, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def stream(self, method, url, **k): return self.post(url, **k)
        def post(self, url, **k):
            payloads.append(k['json']); value = responses[min(len(payloads) - 1, len(responses) - 1)]
            if isinstance(value, Exception): raise value
            return Response(value)
    monkeypatch.setattr(ai_copilot.httpx, 'Client', Client)
    return payloads

def parse_sse(events):
    return [(e.split('\n')[0][7:], json.loads(e.split('data: ', 1)[1])) for e in events]

def test_legacy_sync_identity_and_retry(monkeypatch):
    payloads = prepare_legacy(monkeypatch, ["I'm DeepSeek.", "Hi! I'm HRIDAY."])
    result = ai_copilot.query_copilot('hi', selected_model='deepseek-r1:7b')
    assert result['answer'] == "Hi! I'm HRIDAY." and result['runtime_model'] == 'deepseek-r1:7b'
    assert len(payloads) == 2 and 'CORRECTIVE' in payloads[1]['system']
    assert payloads[0]['think'] is False
    assert 'Verified domain context' in payloads[0]['prompt'] and 'Pulse Analytics Copilot' not in payloads[0]['prompt']

def test_legacy_stream_safe_corrective_reset(monkeypatch):
    payloads = prepare_legacy(monkeypatch, ["Hello! I'm DeepSeek-R1. More.", "Hi! I'm HRIDAY. How can I help?"])
    events = parse_sse(ai_copilot.stream_copilot_generator('hi', selected_model='deepseek-r1:7b'))
    shown = ''
    for kind, data in events:
        if kind == 'token':
            shown += data['token']; assert not identity.identity_leak(shown)
        if kind == 'answer_reset': shown = ''
    done = next(data for kind, data in events if kind == 'done')
    assert shown == done['answer'] == "Hi! I'm HRIDAY. How can I help?"
    assert len(payloads) == 2 and payloads[0]['model'] == payloads[1]['model']
    assert 'CORRECTIVE' in payloads[1]['system'] and done['identity_diagnostics']['identity_retry_count'] == 1

def test_split_reasoning_and_incremental_model_discussion(monkeypatch):
    text = '<think>I am DeepSeek and reason internally.</think>DeepSeek is a reasoning model. Qwen supports coding.'
    prepare_legacy(monkeypatch, [text])
    events = parse_sse(ai_copilot.stream_copilot_generator('Compare DeepSeek and Qwen', selected_model='qwen3.5:9b'))
    tokens = [d['token'] for k, d in events if k == 'token']
    assert len(tokens) >= 2 and ''.join(tokens) == text.split('</think>')[1]
    assert not next(d for k, d in events if k == 'done')['identity_diagnostics']['identity_guard_triggered']

@pytest.mark.parametrize('response, expected', [("I'm DeepSeek.", 'qwen3.5:9b'), (httpx.HTTPError('offline'), 'unavailable')])
def test_stream_runtime_truthful(monkeypatch, response, expected):
    prepare_legacy(monkeypatch, [response])
    events = parse_sse(ai_copilot.stream_copilot_generator('Which model are you using right now?', selected_model='qwen3.5:9b'))
    answer = ''.join(d['token'] for k, d in events if k == 'token')
    assert expected in answer and 'DeepSeek' not in answer

def test_no_fabricated_deterministic_runtime():
    result = identity.finalize_identity_response({'answer': 'Generic result', 'model_used': 'generic_copilot_engine'}, 'Which model powers you?')
    assert result['runtime_model'] is None and 'unavailable' in result['answer']
    assert result['model_used'] == 'generic_copilot_engine'

@pytest.mark.parametrize('model', MODELS)
def test_gateway_transport_injection_all_model_families(monkeypatch, model):
    payloads = fake_chat(monkeypatch, lambda p, n: "I'm HRIDAY. How can I help?")
    result = ModelGateway.generate(ModelRole.FAST, 'hi', model_override=model)
    assert result.success and result.runtime_model == model
    assert payloads[0]['model'] == model
    assert json.dumps({'assistant_name': 'HRIDAY', 'product_name': 'HighView', 'runtime_model': model}) in payloads[0]['messages'][0]['content']


def test_all_council_models_unavailable_do_not_guess(monkeypatch):
    monkeypatch.setattr('app.services.copilot.union_war_room._call_ollama_completion', lambda *a, **k: '')
    result = UnionWarRoomEngine.execute_deliberation('Which model is powering this response?', timeout_seconds=5)
    assert result['runtime_model'] is None
    assert 'unavailable' in result['answer']
    assert len(result['candidate_answers']) == 5


def test_public_identity_endpoint_and_generic_boundary(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.routers import copilot
    import pandas as pd
    client = TestClient(app)
    response = client.get('/api/copilot/identity')
    assert response.status_code == 200 and response.json()['name'] == 'HRIDAY'
    assert 'runtime_model' not in response.json()
    monkeypatch.setattr(copilot, '_load_active_sheet_dataframe', lambda *a: (pd.DataFrame({'value': [1]}), 'Test', None, None))
    monkeypatch.setattr(copilot, '_execute_generic_copilot', lambda *a, **k: {'answer': 'Data summary', 'model_used': 'generic_copilot_engine'})
    result = client.post('/api/copilot/query', json={'query': 'who are you?', 'engine': 'generic'}).json()
    assert result['answer'] == "I'm HRIDAY, the AI assistant in HighView."
    result = client.post('/api/copilot/query/stream', json={'query': 'Which model powers you?', 'engine': 'generic'})
    events = parse_sse(e for e in result.text.split('\n\n') if e)
    assert 'unavailable' in ''.join(d['token'] for k, d in events if k == 'token')
    assert next(d for k, d in events if k == 'done')['runtime_model'] is None


def test_unfinished_reasoning_never_becomes_a_public_response(monkeypatch):
    from app.services.gateway.model_gateway import clean_cot_reasoning
    assert clean_cot_reasoning('<think>I am DeepSeek. Internal reasoning without a final answer') == ''
    assert ai_copilot.clean_cot_reasoning('<think>I am DeepSeek.') == ''
    prepare_legacy(monkeypatch, ['<think>I am DeepSeek.'])
    events = parse_sse(ai_copilot.stream_copilot_generator('hi', selected_model='deepseek-r1:7b'))
    answer = ''.join(d['token'] for k, d in events if k == 'token')
    assert '<think>' not in answer and 'DeepSeek' not in answer
    assert next(d for k, d in events if k == 'done')['runtime_model'] is None


def test_unasked_runtime_intro_retries_but_explicit_disclosure_is_preserved():
    text = "I'm HRIDAY, and this response is powered by qwen3.5:9b."
    assert identity.identity_leak(text, 'qwen3.5:9b', query='hi')
    assert not identity.identity_leak(text, 'qwen3.5:9b', query='Which model powers you?')
    calls = []
    result = identity.guarded_completion(lambda system: calls.append(system) or (text if len(calls) == 1 else 'Hello! How can I help?'), query='hi', runtime_model='qwen3.5:9b')
    assert result.text == 'Hello! How can I help?' and result.identity_retry_count == 1
