from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.api.auth import current_user
from app.core.db import transaction

router = APIRouter()

class CollectionInput(BaseModel):
    name: str = Field(min_length=1, max_length=160, pattern=r'.*\S.*')

@router.get('/collections')
def list_collections(user=Depends(current_user)):
    with transaction(user['id']) as db:
        return db.execute('''SELECT c.id, c.name, cp.can_write FROM collections c
            JOIN collection_permissions cp ON cp.collection_id=c.id
            JOIN users u ON u.role_id=cp.role_id WHERE u.id=%s ORDER BY c.name''', (user['id'],)).fetchall()

@router.post('/collections', status_code=201)
def create_collection(body: CollectionInput, user=Depends(current_user)):
    if user['role'] not in ('manager', 'admin'):
        raise HTTPException(403, 'Création réservée aux managers et administrateurs')
    with transaction(user['id']) as db:
        row = db.execute('INSERT INTO collections(name) VALUES (%s) ON CONFLICT DO NOTHING RETURNING *', (body.name.strip(),)).fetchone()
        if not row:
            raise HTTPException(409, 'Nom indisponible')
        db.execute('''INSERT INTO collection_permissions(collection_id, role_id, can_write)
            SELECT %s, id, true FROM roles WHERE name='admin' OR id=%s''', (row['id'], user['role_id']))
        return row
