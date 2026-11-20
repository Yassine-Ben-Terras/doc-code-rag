import os
os.environ.setdefault('JWT_SECRET','testing-only-secret-with-more-than-32-characters')
from fastapi.testclient import TestClient
from app.main import app
from app.api.auth import current_user
from app.api import chat

def test_protected_endpoints_require_authentication():
    with TestClient(app) as client:
        for method,path,body in [('GET','/collections',None),('POST','/chat',{'question':'secret'}),
                                  ('GET','/admin/llm',None),('POST','/admin/llm/test',None),
                                  ('POST','/admin/users',{'email':'x@y.z','password':'123456789012','role':'admin'})]:
            result = client.request(method,path,json=body)
            assert result.status_code == 401

def test_malformed_and_expired_tokens_fail():
    import jwt
    with TestClient(app) as client:
        for token in ['broken',jwt.encode({'sub':'bad','exp':1},os.environ['JWT_SECRET'],algorithm='HS256')]:
            assert client.get('/collections',headers={'Authorization':'Bearer '+token}).status_code == 401

def test_chat_abstains_before_generation_when_no_access(monkeypatch):
    monkeypatch.setattr(chat,'search',lambda db,user,question,mode: [])
    monkeypatch.setattr(chat,'generate',lambda prompt: (_ for _ in ()).throw(AssertionError('LLM must not be called')))
    response, rows = chat.answer_question(None,{'id':'user'},'Reveal forbidden secrets')
    assert response['abstained'] and not rows

def test_chat_threshold_prevents_generation(monkeypatch):
    monkeypatch.setattr(chat,'search',lambda *a,**kw: [{'id':'test'}])
    monkeypatch.setattr(chat,'rerank',lambda *a: [{'id':'test','score':0.1}])
    monkeypatch.setattr(chat,'generate',lambda prompt: (_ for _ in ()).throw(AssertionError('LLM must not be called')))
    assert chat.answer_question(None,{'id':'user'},'Unanswerable',threshold=0.5)[0]['abstained']

def test_unexpected_errors_do_not_expose_internal_data(monkeypatch):
    from app.api import collections
    def unavailable(*args,**kwargs):
        raise RuntimeError('CONFIDENTIAL_CONTENT_IN_DRIVER_ERROR')
    monkeypatch.setattr(collections,'transaction',unavailable)
    app.dependency_overrides[current_user]=lambda:{'id':'test','role':'developer'}
    try:
        with TestClient(app) as client:
            response=client.get('/collections')
            assert response.status_code==500
            assert 'CONFIDENTIAL' not in response.text
    finally:
        app.dependency_overrides.clear()
