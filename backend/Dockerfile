FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENV PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=10 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip==26.2.1
RUN --mount=type=cache,target=/root/.cache/pip \
    for attempt in 1 2 3; do \
        python -m pip install --prefer-binary --resume-retries 10 -r requirements.txt && exit 0; \
        if [ "$attempt" -lt 3 ]; then sleep 5; fi; \
    done; exit 1
COPY backend/ .
COPY eval/ /eval/
RUN useradd --uid 10001 --create-home rag && mkdir /data && chown rag /data && chown -R rag /eval
USER rag
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
