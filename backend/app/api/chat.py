import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from app.api.auth import current_user
from app.core.db import transaction
from app.core.config import RERANK_THRESHOLD
from app.retrieval.search import search, IndexNotReady
from app.retrieval.rerank import rerank
from app.generation.prompt import make_prompt
from app.generation.llm import generate
from app.generation.settings import LLMError
from app.generation.citations import build_response, abstain

router = APIRouter()

class Question(BaseModel):
    question: str = Field(min_length=1, max_length=2000, pattern=r'.*\S.*')

def answer_question(db, user, question, mode='rerank', threshold=RERANK_THRESHOLD):
    candidates = search(db, user, question, mode='dense' if mode == 'dense' else 'hybrid')
    passages = rerank(question,candidates) if mode == 'rerank' else candidates[:5]
    if not passages or (mode == 'rerank' and passages[0]['score'] < threshold):
        return abstain(), passages
    return build_response(generate(make_prompt(question,passages)), passages), passages

@router.post('/chat')
def chat(body: Question, user=Depends(current_user)):
    try:
        with transaction(user['id']) as db:
            response, _ = answer_question(db, user, body.question)
            return response
    except LLMError as exc:
        raise HTTPException(503, str(exc)) from None
    except IndexNotReady as exc:
        raise HTTPException(409, str(exc)) from None
    except (httpx.HTTPError, ValueError, KeyError):
        raise HTTPException(503, 'Recherche documentaire indisponible : vérifier le service d’embeddings et de classement des passages. Le LLM externe chargé de rédiger les réponses est un service distinct.') from None
