"""Run inside the frontend image, mounting this script and frontend/app.py read-only."""
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

root = Path(__file__).resolve().parents[1]
path = str(root/'frontend'/'app.py')

class Response:
    ok = True
    status_code = 200
    def __init__(self, body):
        self.body = body
    def json(self):
        return self.body

saved = {'configured':False}
calls = []
def request(method, url, **kwargs):
    global saved
    calls.append((method, url, kwargs))
    if url.endswith('/collections'):
        return Response([{'id': 'collection-test', 'name': 'Documentation', 'can_write': True}])
    if url.endswith('/admin/permissions'):
        return Response([{'collection_id': 'collection-test', 'role': 'admin', 'can_write': True}])
    if url.endswith('/admin/llm'):
        if method == 'PUT':
            values = kwargs['json']
            saved = {k:values[k] for k in ('provider','base_url','model')}
            saved.update(configured=True,has_api_key=True)
        elif method == 'DELETE':
            saved = {'configured':False}
        return Response(saved)
    if url.endswith('/admin/llm/test'):
        return Response({'ok':True})
    raise AssertionError(url)

with patch('requests.request', request):
    app = AppTest.from_file(path).run(timeout=30)
    assert not app.exception
    app.session_state['token'] = 'test'
    app.session_state['role'] = 'admin'
    app.run(timeout=30)
    app.radio[0].set_value('Administration').run(timeout=30)
    assert not app.exception
    assert len(app.dataframe) == 1
    assert app.dataframe[0].value.iloc[0]['Rôle'] == 'admin'
    app.radio[0].set_value('Configuration LLM').run(timeout=30)
    assert not app.exception
    for widget, value in zip(app.text_input, ['Mistral','https://api.mistral.ai/v1','test-model','test-key']):
        widget.set_value(value)
    app.button[0].click().run(timeout=30)
    assert not app.exception and saved['configured']
    assert all(widget.value != 'test-key' for widget in app.text_input)
    assert any('Configuration enregistrée' in message.value for message in app.success)
    next(b for b in app.button if b.label == 'Tester la connexion enregistrée').click().run(timeout=30)
    assert not app.exception
    assert any('répondent correctement' in message.value for message in app.success)
    next(b for b in app.button if b.label == 'Confirmer la suppression de la connexion').click().run(timeout=30)
    assert not app.exception and not saved['configured']
    app.session_state['role'] = 'developer'
    app.run(timeout=30)
    assert 'Configuration LLM' not in app.radio[0].options
print('Interface checks passed: login, permissions dataframe, admin settings save/test/delete, key cleared, developer restrictions.')
