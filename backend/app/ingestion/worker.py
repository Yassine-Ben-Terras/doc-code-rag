import logging
import os
import time
import psycopg
from psycopg.rows import dict_row
from pathlib import Path
from tempfile import TemporaryDirectory
from app.core.config import UPLOAD_DIR
from app.core.db import transaction
from app.ingestion.parsers import parse_file, parse_code
from app.ingestion.chunkers import chunk_passage
from app.ingestion.github import clone_repository, repository_files, CODE_EXTENSIONS
from app.retrieval.inference import embed, vector_literal

log = logging.getLogger('worker')

def parse_document(doc):
    if doc['source_url']:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)/'repo'
            clone_repository(doc['source_url'], root)
            for path in repository_files(root):
                name = path.relative_to(root).as_posix()
                try:
                    if path.suffix.lower() in CODE_EXTENSIONS:
                        yield from parse_code(path, name)
                    else:
                        for passage in parse_file(path, name):
                            yield from chunk_passage(passage)
                except UnicodeError:
                    continue
    else:
        path = UPLOAD_DIR / Path(doc['storage_path']).name
        for passage in parse_file(path, doc['name']):
            yield from chunk_passage(passage)

def run_once():
    # Session advisory lock survives the commit of processing status. It also
    # allows a later worker to recover processing jobs after a crashed session.
    with psycopg.connect('', row_factory=dict_row, autocommit=True) as db:
        with db.transaction():
            doc = None
            for candidate in db.execute('''SELECT * FROM documents WHERE status IN ('pending','processing')
                    ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 100''').fetchall():
                acquired = db.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,0)) AS ok', (str(candidate['id']),)).fetchone()['ok']
                if acquired:
                    doc = candidate
                    break
            if not doc:
                return False
            db.execute("UPDATE documents SET status='processing', started_at=now(), error=NULL WHERE id=%s", (doc['id'],))
        try:
            chunks = list(parse_document(doc))
            if not chunks:
                raise ValueError('Aucun texte exploitable (PDF scanné ou document vide)')
            if len(chunks) > 10000:
                raise ValueError('Document trop volumineux')
            vectors = []
            prefix = os.getenv('CONTEXT_PREFIX', 'true').lower() == 'true'
            batch_size = max(1, min(32, int(os.getenv('EMBEDDING_BATCH_SIZE', '4'))))
            for offset in range(0, len(chunks), batch_size):
                vectors.extend(embed([(c.section_path+'\n' if prefix else '') + c.content for c in chunks[offset:offset+batch_size]]))
                log.info('document=%s embedded=%s/%s', doc['id'], min(offset+batch_size,len(chunks)), len(chunks))
            with transaction() as store:
                current = store.execute('SELECT id FROM documents WHERE id=%s FOR UPDATE', (doc['id'],)).fetchone()
                if current:  # A deleted job must never be resurrected.
                    store.execute('DELETE FROM chunks WHERE document_id=%s', (doc['id'],))
                    with store.cursor() as cursor:
                        cursor.executemany('''INSERT INTO chunks(document_id,collection_id,content,section_path,page,line_start,line_end,embedding)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s::vector)''',
                            [(doc['id'],doc['collection_id'],c.content,c.section_path,c.page,c.line_start,c.line_end,vector_literal(v))
                             for c,v in zip(chunks,vectors,strict=True)])
                    store.execute("UPDATE documents SET status='ready', error=NULL WHERE id=%s", (doc['id'],))
            log.info('document=%s status=ready chunks=%s', doc['id'], len(chunks))
        except Exception as exc:
            # Never expose model responses, file contents, tokens or DB errors.
            error = 'Indexation impossible : vérifier le fichier, le dépôt et les services locaux.'
            with transaction() as store:
                store.execute("UPDATE documents SET status='failed', error=%s WHERE id=%s", (error,doc['id']))
            log.warning('document=%s status=failed type=%s', doc['id'], type(exc).__name__)
        finally:
            db.execute('SELECT pg_advisory_unlock_all()')
    return True

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(message)s')
    while True:
        try:
            if not run_once():
                time.sleep(2)
        except Exception as exc:
            log.warning('Worker unavailable: %s', type(exc).__name__)
            time.sleep(5)

if __name__ == '__main__':
    main()
