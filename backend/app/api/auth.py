from datetime import datetime, timedelta, timezone
from uuid import UUID
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from app.core.config import jwt_secret
from app.core.db import transaction

router = APIRouter()
hasher = PasswordHasher()
DUMMY_HASH = hasher.hash('dummy-password-for-constant-work')
bearer = HTTPBearer(auto_error=False)

class Login(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)

@router.post('/auth/login')
def login(body: Login):
    with transaction() as db:
        user = db.execute('SELECT u.*, r.name AS role FROM users u JOIN roles r ON r.id=u.role_id WHERE email=%s',
                          (body.email.strip().lower(),)).fetchone()
    try:
        valid = hasher.verify(user['password_hash'] if user else DUMMY_HASH, body.password)
    except (VerificationError, InvalidHashError):
        valid = False
    if not user or not valid:
        raise HTTPException(401, 'Identifiants incorrects')
    now = datetime.now(timezone.utc)
    token = jwt.encode({'sub': str(user['id']), 'iat': now, 'exp': now + timedelta(hours=8),
                        'iss': 'internal-rag', 'aud': 'internal-rag'}, jwt_secret(), algorithm='HS256')
    return {'access_token': token, 'token_type': 'bearer', 'role': user['role']}

def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    try:
        if not credentials:
            raise ValueError()
        claims = jwt.decode(credentials.credentials, jwt_secret(), algorithms=['HS256'],
                            issuer='internal-rag', audience='internal-rag', options={'require': ['sub', 'exp', 'iat']})
        uid = UUID(claims['sub'])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, 'Authentification requise') from None
    with transaction(uid) as db:
        user = db.execute('SELECT u.id, u.role_id, r.name AS role FROM users u JOIN roles r ON u.role_id=r.id WHERE u.id=%s', (uid,)).fetchone()
    if not user:
        raise HTTPException(401, 'Authentification requise')
    return user

def admin(user=Depends(current_user)):
    if user['role'] != 'admin':
        raise HTTPException(403, 'Accès administrateur requis')
    return user
