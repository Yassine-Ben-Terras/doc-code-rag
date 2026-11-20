FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HUB_DISABLE_TELEMETRY=1
ENV PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=10 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip==26.2.1
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --resume-retries 10 torch==2.6.0 --index-url "$TORCH_INDEX_URL"
RUN --mount=type=cache,target=/root/.cache/pip \
    for attempt in 1 2 3; do \
        python -m pip install --prefer-binary --resume-retries 10 -r requirements.txt && exit 0; \
        if [ "$attempt" -lt 3 ]; then sleep 5; fi; \
    done; exit 1
COPY main.py .
RUN useradd --uid 10001 --create-home inference && mkdir /models && chown inference /models
USER inference
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--no-access-log"]
