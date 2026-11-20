import importlib
import pytest

search_module = importlib.import_module('app.retrieval.search')

@pytest.mark.parametrize('pending', [True, False])
def test_empty_index_never_calls_embeddings(monkeypatch, pending):
    monkeypatch.setattr(search_module, 'allowed_collections', lambda db, user: ['allowed'])
    monkeypatch.setattr(search_module, 'require_collection', lambda *a, **kw: None)
    monkeypatch.setattr(search_module, 'embed', lambda *a: pytest.fail('No embedding call for an empty index'))
    class DB:
        def execute(self, query, params):
            assert params == (['allowed'],)
            self.result = {'exists': 1} if 'FROM documents' in query and pending else None
            return self
        def fetchone(self):
            return self.result
    if pending:
        with pytest.raises(search_module.IndexNotReady, match='encore indexé'):
            search_module.search(DB(), {}, 'question')
    else:
        assert search_module.search(DB(), {}, 'question') == []
