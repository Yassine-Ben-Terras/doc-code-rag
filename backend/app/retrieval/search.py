import re
from collections import defaultdict
from app.retrieval.permissions import allowed_collections, require_collection
from app.retrieval.inference import embed, vector_literal

class IndexNotReady(Exception):
    pass

def lexical_terms(question):
    return ' | '.join(dict.fromkeys(re.findall(r'[^\W_]+(?:_[^\W_]+)*', question.lower(), flags=re.UNICODE)))

def rrf(*rankings, limit=30):
    scores = defaultdict(float)
    for ranking in rankings:
        for rank, item in enumerate(dict.fromkeys(ranking), 1):
            scores[item] += 1 / (60 + rank)
    return sorted(scores, key=lambda item: (-scores[item], str(item)))[:limit]

def search(db, user, question, mode='hybrid'):
    allowed = allowed_collections(db, user)
    if not allowed:
        return []
    for collection_id in sorted(allowed):
        require_collection(db, user, collection_id, lock=True)
    if not db.execute('SELECT 1 FROM chunks WHERE collection_id=ANY(%s::uuid[]) LIMIT 1', (allowed,)).fetchone():
        if db.execute("SELECT 1 FROM documents WHERE collection_id=ANY(%s::uuid[]) AND status IN ('pending','processing','failed') LIMIT 1", (allowed,)).fetchone():
            raise IndexNotReady('Aucun document accessible n’est encore indexé. Consultez son statut dans Documents : l’indexation nécessite le worker et le service d’embeddings. La connexion au LLM externe ne suffit pas à indexer les fichiers.')
        return []
    query_vector = vector_literal(embed([question])[0])
    db.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
    dense = db.execute('''SELECT id FROM chunks WHERE collection_id=ANY(%s::uuid[])
        ORDER BY embedding <=> %s::vector LIMIT 30''', (allowed,query_vector)).fetchall()
    terms = lexical_terms(question)
    lexical = []
    if mode != 'dense' and terms:
        lexical = db.execute('''SELECT id FROM chunks WHERE collection_id=ANY(%s::uuid[])
            AND tsv @@ to_tsquery('simple',%s)
            ORDER BY ts_rank(tsv,to_tsquery('simple',%s)) DESC, id LIMIT 30''', (allowed,terms,terms)).fetchall()
    ids = rrf([r['id'] for r in dense], [r['id'] for r in lexical])
    if not ids:
        return []
    rows = db.execute('''SELECT ch.id,ch.collection_id,ch.content,ch.section_path,ch.page,ch.line_start,ch.line_end,
        d.name AS document FROM chunks ch JOIN documents d ON d.id=ch.document_id
        WHERE ch.id=ANY(%s::uuid[]) AND ch.collection_id=ANY(%s::uuid[])''', (ids,allowed)).fetchall()
    positions = {item: rank for rank,item in enumerate(ids)}
    return sorted(rows, key=lambda row: positions[row['id']])
