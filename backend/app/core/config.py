import os
from pathlib import Path

UPLOAD_DIR = Path(os.getenv('UPLOAD_DIR', '/data'))
INFERENCE_URL = os.getenv('INFERENCE_URL', 'http://inference:8001')
RERANK_THRESHOLD = float(os.getenv('RERANK_THRESHOLD', '0.5'))
MAX_UPLOAD = 20 * 1024 * 1024

def jwt_secret():
    secret = os.environ.get('JWT_SECRET', '')
    if len(secret) < 32 or secret.startswith('replace-'):
        raise RuntimeError('JWT_SECRET must contain at least 32 random characters')
    return secret
