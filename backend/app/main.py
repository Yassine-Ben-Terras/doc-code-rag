from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.api import auth, collections, documents, chat, admin, llm_settings
from app.core.config import jwt_secret
from app.core.db import transaction

@asynccontextmanager
async def lifespan(app):
    jwt_secret()
    yield

app = FastAPI(title='Assistant documentation interne', version='1.0.0', lifespan=lifespan)
for module in (auth, collections, documents, chat, admin, llm_settings):
    app.include_router(module.router)

@app.exception_handler(RequestValidationError)
async def hide_invalid_input(request, exc):
    # Validation responses must not echo submitted passwords or provider keys.
    return JSONResponse(status_code=422, content={'detail': [
        {'loc': error['loc'], 'type': error['type'], 'msg': error['msg']}
        for error in exc.errors()]})

@app.middleware('http')
async def hide_internal_errors(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        # Catch before ASGI's error logger: driver tracebacks can include row data.
        return JSONResponse(status_code=500, content={'detail': 'Erreur interne du service'})

@app.get('/health')
def health():
    with transaction() as db:
        db.execute('SELECT 1')
    return {'status': 'ok'}
