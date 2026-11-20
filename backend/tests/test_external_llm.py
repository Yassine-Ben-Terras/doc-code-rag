import json
from contextlib import contextmanager
import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from app.main import app
from app.api.auth import current_user
from app.api import llm_settings as routes
from app.generation import llm
from app.generation.settings import SettingsInput, LLMError, cipher, save_settings, decrypt_key, public_settings

@pytest.fixture
def encrypted(monkeypatch):
    monkeypatch.setenv('LLM_ENCRYPTION_KEY', Fernet.generate_key().decode())
    return {'provider': 'Example', 'base_url': 'https://provider.example/v1', 'model': 'model-a',
            'api_key_encrypted': cipher().encrypt(b'secret-provider-key').decode(), 'updated_at': 'now'}

class Database:
    def __init__(self, row=None):
        self.row = row
    def execute(self, sql, params=None):
        if sql.startswith('INSERT'):
            self.row = dict(zip(('provider','base_url','model','api_key_encrypted'), params), updated_at='now')
        elif sql.startswith('DELETE'):
            self.row = None
        return self
    def fetchone(self):
        return self.row

def test_key_encrypted_and_preserved_on_model_change(encrypted):
    db = Database()
    body = SettingsInput(provider='Example', base_url=encrypted['base_url'], model='one', api_key='secret-provider-key')
    save_settings(db, body)
    assert 'secret-provider-key' not in db.row['api_key_encrypted']
    assert decrypt_key(db.row) == 'secret-provider-key'
    before = db.row['api_key_encrypted']
    save_settings(db, body.model_copy(update={'model':'two','api_key':None}))
    assert db.row['model'] == 'two' and db.row['api_key_encrypted'] == before
    assert 'api_key_encrypted' not in public_settings(db.row)
    with pytest.raises(LLMError):
        save_settings(db, body.model_copy(update={'base_url':'https://other.example/v1','api_key':None}))

def test_wrong_encryption_key_fails_safely(encrypted, monkeypatch):
    monkeypatch.setenv('LLM_ENCRYPTION_KEY', Fernet.generate_key().decode())
    with pytest.raises(LLMError):
        decrypt_key(encrypted)

@pytest.mark.parametrize('url', ['http://provider.example', 'https://key@provider.example', 'https://provider.example?key=secret'])
def test_unsafe_configuration_url_rejected(url):
    with pytest.raises(ValueError):
        SettingsInput(provider='Example', base_url=url, model='one', api_key='key')

def test_external_request_and_response(encrypted, monkeypatch):
    client_class = httpx.Client
    def handler(request):
        assert str(request.url) == 'https://provider.example/v1/chat/completions'
        assert request.headers['Authorization'] == 'Bearer secret-provider-key'
        payload = json.loads(request.content)
        assert payload['model'] == 'model-a'
        assert payload['messages'][1]['content'] == 'Question with allowed excerpts'
        return httpx.Response(200, json={'choices':[{'message':{'content':'Answer [1]'}}]})
    monkeypatch.setattr(llm.httpx, 'Client', lambda **kw: client_class(transport=httpx.MockTransport(handler), **kw))
    assert llm.complete(encrypted, 'Question with allowed excerpts') == 'Answer [1]'

@pytest.mark.parametrize('status', [401, 429, 500, 302])
def test_provider_errors_never_echo_secrets(encrypted, monkeypatch, status):
    client_class = httpx.Client
    def handler(request):
        return httpx.Response(status, text='secret-provider-key and internal excerpts', headers={'Location':'https://other.example'})
    monkeypatch.setattr(llm.httpx, 'Client', lambda **kw: client_class(transport=httpx.MockTransport(handler), **kw))
    with pytest.raises(LLMError) as exc:
        llm.complete(encrypted, 'private')
    assert 'secret-provider-key' not in str(exc.value) and 'internal excerpts' not in str(exc.value)

@pytest.mark.parametrize('role', ['developer', 'manager'])
def test_non_admin_cannot_manage_provider(role):
    app.dependency_overrides[current_user] = lambda: {'id':'user','role':role}
    try:
        with TestClient(app) as client:
            for method, path in [('GET','/admin/llm'),('PUT','/admin/llm'),('DELETE','/admin/llm'),('POST','/admin/llm/test')]:
                assert client.request(method, path, json={}).status_code == 403
    finally:
        app.dependency_overrides.clear()

def test_admin_settings_roundtrip_and_test(encrypted, monkeypatch):
    db = Database()
    @contextmanager
    def transaction(*args):
        yield db
    monkeypatch.setattr(routes, 'transaction', transaction)
    calls = []
    monkeypatch.setattr(routes, 'complete', lambda row, prompt, **kw: calls.append((row, prompt, kw)) or 'OK')
    app.dependency_overrides[current_user] = lambda: {'id':'admin','role':'admin'}
    try:
        with TestClient(app) as client:
            assert client.get('/admin/llm').json() == {'configured':False}
            payload = {'provider':'Example','base_url':encrypted['base_url'],'model':'one','api_key':'secret-provider-key'}
            response = client.put('/admin/llm', json=payload)
            assert response.status_code == 200 and response.json()['has_api_key']
            assert 'secret-provider-key' not in response.text
            assert 'api_key_encrypted' not in client.get('/admin/llm').text
            assert client.post('/admin/llm/test').status_code == 200
            assert calls[0][1] == 'Reply with OK.' and calls[0][2]['probe']
            assert client.delete('/admin/llm').status_code == 200
            assert client.get('/admin/llm').json() == {'configured':False}
    finally:
        app.dependency_overrides.clear()

def test_generation_loads_current_database_configuration(encrypted, monkeypatch):
    db = Database(encrypted)
    @contextmanager
    def transaction():
        yield db
    monkeypatch.setattr(llm, 'transaction', transaction)
    monkeypatch.setattr(llm, 'complete', lambda settings, prompt: settings['model'])
    assert llm.generate('question') == 'model-a'
    db.row['model'] = 'model-b'
    assert llm.generate('question') == 'model-b'
    db.row = None
    with pytest.raises(LLMError, match='Aucun LLM'):
        llm.generate('question')

def test_validation_does_not_echo_submitted_key():
    app.dependency_overrides[current_user] = lambda: {'id':'admin','role':'admin'}
    try:
        with TestClient(app) as client:
            response = client.put('/admin/llm', json={'provider':'Example',
                'base_url':'https://provider.example/v1','model':'one','api_key':'secret-canary-'*400})
            assert response.status_code == 422
            assert 'secret-canary' not in response.text
    finally:
        app.dependency_overrides.clear()

@pytest.mark.parametrize('probe', [True, False])
def test_reasoning_model_budget_and_final_answer(encrypted, monkeypatch, probe):
    client_class = httpx.Client
    def handler(request):
        assert json.loads(request.content)['max_tokens'] == 4096
        return httpx.Response(200, json={'choices':[{'finish_reason':'stop',
            'message':{'content':'OK', 'reasoning_content':'PRIVATE_REASONING'}}]})
    monkeypatch.setattr(llm.httpx, 'Client', lambda **kw: client_class(transport=httpx.MockTransport(handler), **kw))
    assert llm.complete(encrypted, 'Reply with OK.', probe=probe) == 'OK'

@pytest.mark.parametrize('content,finish', [(None,'length'), ('Incomplete [1]', 'length'), (None,'stop')])
def test_reasoning_only_or_truncated_is_not_an_answer(encrypted, monkeypatch, content, finish):
    client_class = httpx.Client
    def handler(request):
        return httpx.Response(200, json={'choices':[{'finish_reason':finish,
            'message':{'content':content, 'reasoning_content':'PRIVATE_REASONING'}}]})
    monkeypatch.setattr(llm.httpx, 'Client', lambda **kw: client_class(transport=httpx.MockTransport(handler), **kw))
    with pytest.raises(LLMError) as exc:
        llm.complete(encrypted, 'test')
    assert 'PRIVATE_REASONING' not in str(exc.value)
    assert ('limite de génération' if finish == 'length' else 'sans réponse finale') in str(exc.value)

@pytest.mark.parametrize('exception,expected', [(httpx.ReadTimeout,'trop de temps'), (httpx.ConnectError,'Connexion')])
def test_network_errors_are_distinct_and_redacted(encrypted, monkeypatch, exception, expected):
    client_class = httpx.Client
    def handler(request):
        raise exception('secret-provider-key', request=request)
    monkeypatch.setattr(llm.httpx, 'Client', lambda **kw: client_class(transport=httpx.MockTransport(handler), **kw))
    with pytest.raises(LLMError) as exc:
        llm.complete(encrypted, 'test')
    assert expected in str(exc.value) and 'secret-provider-key' not in str(exc.value)
