"""Persist one shared external chat-completions configuration."""
import os
from urllib.parse import urlsplit
from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, Field, SecretStr, field_validator

class LLMError(Exception):
    pass

class SettingsInput(BaseModel):
    provider: str = Field(min_length=1, max_length=80)
    base_url: str = Field(max_length=500)
    model: str = Field(min_length=1, max_length=200)
    api_key: SecretStr | None = Field(default=None, max_length=4096)

    @field_validator('provider', 'model')
    @classmethod
    def nonempty(cls, value):
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError('Valeur invalide')
        return value

    @field_validator('base_url')
    @classmethod
    def external_url(cls, value):
        value = value.strip().rstrip('/')
        url = urlsplit(value)
        if (url.scheme != 'https' or not url.hostname or url.username or url.password
                or url.query or url.fragment or any(c.isspace() for c in value)):
            raise ValueError('Utiliser une URL HTTPS sans identifiants ni paramètres')
        return value

def cipher():
    try:
        return Fernet(os.environ['LLM_ENCRYPTION_KEY'].encode('ascii'))
    except (KeyError, ValueError, UnicodeError):
        raise LLMError('Clé de chiffrement manquante ou invalide : exécuter scripts/configure.py puis recréer l’API.') from None

def public_settings(row):
    if not row:
        return {'configured': False}
    return {**{key: row[key] for key in ('provider', 'base_url', 'model', 'updated_at')},
            'configured': True, 'has_api_key': True}

def read_settings(db):
    return db.execute('SELECT * FROM llm_settings WHERE id=1').fetchone()

def save_settings(db, body):
    db.execute('SELECT pg_advisory_xact_lock(7182041)')
    old = read_settings(db)
    key = body.api_key.get_secret_value().strip() if body.api_key else ''
    if key:
        if any(c.isspace() for c in key):
            raise LLMError('La clé API ne doit pas contenir d’espaces.')
        encrypted = cipher().encrypt(key.encode()).decode()
    elif old and old['provider'] == body.provider and old['base_url'] == body.base_url:
        encrypted = old['api_key_encrypted']
    else:
        raise LLMError('Saisir une clé API pour ce fournisseur et cette URL.')
    return db.execute('''INSERT INTO llm_settings(id,provider,base_url,model,api_key_encrypted)
        VALUES (1,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET
        provider=EXCLUDED.provider,base_url=EXCLUDED.base_url,model=EXCLUDED.model,
        api_key_encrypted=EXCLUDED.api_key_encrypted,updated_at=now()
        RETURNING provider,base_url,model,updated_at''',
        (body.provider, body.base_url, body.model, encrypted)).fetchone()

def decrypt_key(row):
    try:
        return cipher().decrypt(row['api_key_encrypted'].encode()).decode()
    except (InvalidToken, UnicodeError):
        raise LLMError('Impossible de déchiffrer la clé API. Rétablir LLM_ENCRYPTION_KEY ou enregistrer une nouvelle clé API.') from None
