import math
import os
import httpx
from app.core.config import INFERENCE_URL

def embed(texts):
    with httpx.Client(timeout=float(os.getenv('EMBEDDING_TIMEOUT', '180')), trust_env=False) as client:
        response = client.post(f'{INFERENCE_URL}/embed', json={'texts': texts})
        response.raise_for_status()
        vectors = response.json()['vectors']
    if len(vectors) != len(texts) or any(len(v) != 1024 or not all(math.isfinite(x) for x in v) for v in vectors):
        raise ValueError('Invalid embedding response')
    return vectors

def vector_literal(vector):
    if len(vector) != 1024 or not all(math.isfinite(x) for x in vector):
        raise ValueError('Invalid vector')
    return '[' + ','.join(str(float(x)) for x in vector) + ']'
