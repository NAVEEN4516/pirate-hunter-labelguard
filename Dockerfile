FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 LANGSMITH_TRACING=false
WORKDIR /app
RUN groupadd --gid 10001 labelguard && useradd --uid 10001 --gid 10001 --create-home labelguard
COPY requirements.lock pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.lock
COPY labelguard ./labelguard
COPY data ./data
COPY prompts ./prompts
COPY web ./web
COPY examples ./examples
COPY eval ./eval
COPY tests ./tests
COPY scripts ./scripts
COPY loadtests ./loadtests
COPY docs ./docs
RUN pip install --no-cache-dir --no-deps . && mkdir -p /app/runtime /app/data/index /app/output && chown -R labelguard:labelguard /app
USER labelguard
EXPOSE 8000 8010 9101
CMD ["uvicorn", "labelguard.api:app", "--host", "0.0.0.0", "--port", "8000"]
