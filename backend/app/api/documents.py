from pathlib import Path
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from app.api.auth import current_user
from app.core.config import UPLOAD_DIR, MAX_UPLOAD
from app.core.db import transaction
from app.retrieval.permissions import require_collection
from app.ingestion.github import validate_url, DOC_EXTENSIONS

router = APIRouter()

class GithubInput(BaseModel):
    url: str = Field(max_length=300)

@router.get('/collections/{collection_id}/documents')
def list_documents(collection_id: UUID, user=Depends(current_user)):
    with transaction(user['id']) as db:
        require_collection(db, user, collection_id, lock=True)
        return db.execute('SELECT id,name,status,error,created_at FROM documents WHERE collection_id=%s ORDER BY created_at DESC', (collection_id,)).fetchall()

@router.post('/collections/{collection_id}/documents', status_code=202)
def upload_document(collection_id: UUID, file: UploadFile = File(...), user=Depends(current_user)):
    name = (file.filename or '').replace('\\', '/').split('/')[-1]
    suffix = Path(name).suffix.lower()
    if suffix not in DOC_EXTENSIONS | {'.png', '.jpg', '.jpeg'} or len(name) > 255:
        raise HTTPException(400, 'Formats autorisés : PDF, DOCX, MD, TXT, PNG, JPG, JPEG')
    doc_id = uuid4()
    path = UPLOAD_DIR / (str(doc_id) + suffix)
    try:
        with transaction(user['id']) as db:
            require_collection(db, user, collection_id, write=True, lock=True)
            db.execute('SELECT id FROM collections WHERE id=%s FOR UPDATE', (collection_id,))
            if db.execute('SELECT 1 FROM documents WHERE collection_id=%s AND source_url IS NOT NULL', (collection_id,)).fetchone():
                raise HTTPException(409, 'Cette collection est dédiée à un dépôt GitHub')
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            size = 0
            with path.open('xb') as output:
                while chunk := file.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD:
                        raise HTTPException(413, 'Taille maximale : 20 Mo')
                    output.write(chunk)
            if not size:
                raise HTTPException(400, 'Fichier vide')
            return db.execute('''INSERT INTO documents(id,collection_id,name,storage_path)
                VALUES (%s,%s,%s,%s) RETURNING id,name,status''', (doc_id,collection_id,name,path.name)).fetchone()
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()

@router.post('/collections/{collection_id}/github', status_code=202)
def connect_github(collection_id: UUID, body: GithubInput, user=Depends(current_user)):
    try:
        url = validate_url(body.url)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    with transaction(user['id']) as db:
        require_collection(db, user, collection_id, write=True, lock=True)
        db.execute('SELECT id FROM collections WHERE id=%s FOR UPDATE', (collection_id,))
        if db.execute('SELECT 1 FROM documents WHERE collection_id=%s', (collection_id,)).fetchone():
            raise HTTPException(409, 'Un dépôt nécessite une collection vide et dédiée')
        return db.execute('INSERT INTO documents(collection_id,name,source_url) VALUES (%s,%s,%s) RETURNING id,name,status', (collection_id,url,url)).fetchone()

@router.delete('/documents/{document_id}')
def delete_document(document_id: UUID, user=Depends(current_user)):
    with transaction(user['id']) as db:
        doc = db.execute('SELECT * FROM documents WHERE id=%s FOR UPDATE', (document_id,)).fetchone()
        if not doc:
            raise HTTPException(404, 'Collection ou document inaccessible')
        require_collection(db, user, doc['collection_id'], write=True, lock=True)
        db.execute('DELETE FROM documents WHERE id=%s', (document_id,))
    if doc['storage_path']:
        (UPLOAD_DIR / Path(doc['storage_path']).name).unlink(missing_ok=True)
    return {'ok': True}
