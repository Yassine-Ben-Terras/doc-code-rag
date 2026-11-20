from pathlib import Path
import pytest

st = pytest.importorskip('streamlit')
from streamlit.testing.v1 import AppTest

FRONTEND = Path(__file__).resolve().parents[2]/'frontend'/'app.py'

class Response:
    ok = True
    status_code = 200
    def __init__(self,body):
        self.body=body
    def json(self):
        return self.body

def test_login_screen_renders():
    app=AppTest.from_file(str(FRONTEND)).run(timeout=20)
    assert not app.exception
    assert len(app.text_input)==2
    assert app.button[0].label=='Se connecter'

@pytest.mark.parametrize('page',['Questions','Documents','Administration','Configuration LLM'])
def test_authenticated_pages_render(page,monkeypatch):
    def request(method,url,**kwargs):
        if url.endswith('/admin/llm'):
            return Response({'configured': False})
        if url.endswith('/collections'):
            return Response([{'id':'collection-1','name':'Documentation','can_write':True}])
        if url.endswith('/documents'):
            return Response([{'id':'doc-1','name':'runbook.md','status':'ready','error':None}])
        if url.endswith('/permissions'):
            return Response([{'collection_id':'collection-1','role':'admin','can_write':True}])
        raise AssertionError(url)
    monkeypatch.setattr('requests.request',request)
    app=AppTest.from_file(str(FRONTEND))
    app.session_state['token']='test-token'
    app.session_state['role']='admin'
    app.run(timeout=20)
    app.radio[0].set_value(page).run(timeout=20)
    assert not app.exception
