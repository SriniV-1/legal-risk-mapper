FROM python:3.12-slim

WORKDIR /app

# System deps for numpy/scipy wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m spacy download en_core_web_sm

# Copy application code
COPY backend/ backend/
COPY frontend/ frontend/
COPY data/ data/
COPY migrations/ migrations/

# HF Spaces expects port 7860. Local/Railway can override with PORT env var.
ENV PORT=7860

EXPOSE 7860

# Production server: gunicorn with uvicorn workers
CMD gunicorn backend.main:app \
    --bind 0.0.0.0:${PORT} \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 2 \
    --timeout 120 \
    --access-logfile -
