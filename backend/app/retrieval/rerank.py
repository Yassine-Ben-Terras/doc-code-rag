import math
import os
import httpx
from app.core.config import INFERENCE_URL

def rerank(question, candidates):
    if not candidates:
        return []
    with httpx.Client(timeout=float(os.getenv('RERANK_TIMEOUT', '180')), trust_env=False) as client:
        response = client.post(f'{INFERENCE_URL}/rerank', json={
            'question': question, 'passages': [c['section_path']+'\n'+c['content'] for c in candidates]})
        response.raise_for_status()
        scores = response.json()['scores']
    if len(scores) != len(candidates) or any(not math.isfinite(s) or not 0 <= s <= 1 for s in scores):
        raise ValueError('Invalid reranker response')
    return sorted([dict(c, score=s) for c,s in zip(candidates,scores,strict=True)], key=lambda c: c['score'], reverse=True)[:5]
