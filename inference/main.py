import os
import threading
import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer, CrossEncoder

lock = threading.Lock()
log = logging.getLogger('uvicorn.error')

@asynccontextmanager
async def lifespan(app):
    import torch
    torch.set_num_threads(max(1, int(os.getenv('INFERENCE_CPU_THREADS', '2'))))
    torch.set_num_interop_threads(1)
    log.info('Loading embedding model from local files')
    app.state.embedding = SentenceTransformer(os.getenv('EMBEDDING_MODEL','/models/bge-m3'), local_files_only=True)
    log.info('Loading reranker from local files')
    app.state.reranker = CrossEncoder(os.getenv('RERANKER_MODEL','/models/bge-reranker-v2-m3'), local_files_only=True, max_length=2048)
    log.info('Local retrieval models ready')
    yield

app = FastAPI(lifespan=lifespan)

class EmbedInput(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=32)

class RerankInput(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    passages: list[str] = Field(min_length=1, max_length=30)

@app.get('/health')
def health():
    return {'status':'ok'}

@app.post('/embed')
def embed(body: EmbedInput):
    with lock:
        vectors = []
        size = max(1, min(8, int(os.getenv('INFERENCE_BATCH_SIZE', '2'))))
        for offset in range(0, len(body.texts), size):
            start = time.monotonic()
            vectors.extend(app.state.embedding.encode(body.texts[offset:offset+size], normalize_embeddings=True, batch_size=size).tolist())
            log.info('embed completed=%s/%s seconds=%.1f', min(offset+size,len(body.texts)),len(body.texts),time.monotonic()-start)
    return {'vectors': vectors}

@app.post('/rerank')
def rerank(body: RerankInput):
    import torch
    with lock:
        scores = []
        size = max(1, min(8, int(os.getenv('INFERENCE_BATCH_SIZE', '2'))))
        for offset in range(0, len(body.passages), size):
            start = time.monotonic()
            scores.extend(app.state.reranker.predict([(body.question,p) for p in body.passages[offset:offset+size]],
                activation_fct=torch.nn.Sigmoid(), batch_size=size).reshape(-1).tolist())
            log.info('rerank completed=%s/%s seconds=%.1f', min(offset+size,len(body.passages)),len(body.passages),time.monotonic()-start)
    return {'scores': scores}
