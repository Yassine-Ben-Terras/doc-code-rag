FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENV PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=10 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip==26.2.1
RUN --mount=type=cache,target=/root/.cache/pip \
    for attempt in 1 2 3; do \
        python -m pip install --prefer-binary --resume-retries 10 -r requirements.txt && exit 0; \
        if [ "$attempt" -lt 3 ]; then sleep 5; fi; \
    done; exit 1
RUN python -c "import numpy, pandas, pyarrow; pyarrow.Table.from_pandas(pandas.DataFrame({'role': ['admin']}))"
COPY app.py .
RUN useradd --uid 10001 --create-home frontend
USER frontend
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--browser.gatherUsageStats=false"]
