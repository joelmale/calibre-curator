FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libmagic1 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip setuptools>=70 && \
    pip install --no-cache-dir -e .

COPY sidecar/ ./sidecar/

EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=5s --retries=5 \
  CMD curl -fsS http://localhost:8090/healthz || exit 1

CMD ["gunicorn", \
     "--bind", "0.0.0.0:8090", \
     "--workers", "2", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "sidecar.app:create_app()"]
