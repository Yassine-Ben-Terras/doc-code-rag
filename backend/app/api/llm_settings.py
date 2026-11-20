from fastapi import APIRouter, Depends, HTTPException
from app.api.auth import admin
from app.core.db import transaction
from app.generation.settings import SettingsInput, LLMError, read_settings, save_settings, public_settings
from app.generation.llm import complete

router = APIRouter(prefix='/admin/llm')

@router.get('')
def get_settings(user=Depends(admin)):
    with transaction(user['id']) as db:
        return public_settings(read_settings(db))

@router.put('')
def put_settings(body: SettingsInput, user=Depends(admin)):
    try:
        with transaction(user['id']) as db:
            return public_settings(save_settings(db, body))
    except LLMError as exc:
        raise HTTPException(400, str(exc)) from None

@router.delete('')
def delete_settings(user=Depends(admin)):
    with transaction(user['id']) as db:
        db.execute('DELETE FROM llm_settings WHERE id=1')
    return {'ok': True}

@router.post('/test')
def test_settings(user=Depends(admin)):
    with transaction(user['id']) as db:
        settings = read_settings(db)
    if not settings:
        raise HTTPException(400, 'Enregistrer une configuration avant de la tester.')
    try:
        complete(settings, 'Reply with OK.', probe=True)
    except LLMError as exc:
        raise HTTPException(502, str(exc)) from None
    return {'ok': True}
