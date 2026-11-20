from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.api.auth import admin, hasher
from app.core.db import transaction
from app.retrieval.permissions import require_collection

router = APIRouter(prefix='/admin')
Role = Literal['admin', 'manager', 'developer']

class NewUser(BaseModel):
    email: str = Field(min_length=3, max_length=254, pattern=r'^[^\s@]+@[^\s@]+$')
    password: str = Field(min_length=12, max_length=1024)
    role: Role

class Permission(BaseModel):
    can_write: bool = False

@router.post('/users', status_code=201)
def create_user(body: NewUser, user=Depends(admin)):
    encoded = hasher.hash(body.password)
    with transaction(user['id']) as db:
        row = db.execute('''INSERT INTO users(email,password_hash,role_id)
            SELECT %s,%s,id FROM roles WHERE name=%s ON CONFLICT DO NOTHING RETURNING id,email''',
            (body.email.strip().lower(), encoded, body.role)).fetchone()
        if not row:
            raise HTTPException(409, 'Utilisateur déjà existant')
        return row

@router.get('/permissions')
def permissions(user=Depends(admin)):
    with transaction(user['id']) as db:
        return db.execute('''SELECT cp.collection_id, r.name AS role, cp.can_write
            FROM collection_permissions cp JOIN roles r ON r.id=cp.role_id ORDER BY r.name''').fetchall()

@router.put('/roles/{role}/collections/{collection_id}')
def set_permission(role: Role, collection_id: UUID, body: Permission, user=Depends(admin)):
    if role == 'admin' and not body.can_write:
        raise HTTPException(400, 'Le rôle admin conserve les droits de gestion')
    with transaction(user['id']) as db:
        require_collection(db, user, collection_id, write=True)
        db.execute('''INSERT INTO collection_permissions(collection_id,role_id,can_write)
            SELECT %s,id,%s FROM roles WHERE name=%s ON CONFLICT(collection_id,role_id)
            DO UPDATE SET can_write=EXCLUDED.can_write''', (collection_id, body.can_write, role))
    return {'ok': True}

@router.delete('/roles/{role}/collections/{collection_id}')
def revoke_permission(role: Role, collection_id: UUID, user=Depends(admin)):
    if role == 'admin':
        raise HTTPException(400, 'Le rôle admin conserve les droits de gestion')
    with transaction(user['id']) as db:
        require_collection(db, user, collection_id, write=True)
        db.execute('DELETE FROM collection_permissions WHERE collection_id=%s AND role_id=(SELECT id FROM roles WHERE name=%s)', (collection_id, role))
    return {'ok': True}
