# CDK16 Analysis Workbench — single-container deployment.
# Builds the React frontend, then serves it statically from FastAPI on $PORT.
FROM python:3.12-slim

WORKDIR /app

# --- Python deps first (better layer caching) ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Frontend build ---
COPY frontend/package.json frontend/package-lock.json* ./frontend/
RUN cd frontend && npm install --no-audit --no-fund

COPY frontend ./frontend
RUN cd frontend && npm run build

# --- Backend + pipeline + processed data ---
COPY api ./api
COPY src ./src
COPY data/processed ./data/processed
COPY data/structures ./data/structures

# Writable dirs for runtime analysis DB + generated reports (works on read-only-ish FS too)
RUN mkdir -p /app/data/processed /app/results/reports/figures

# Non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn api.server:app --host 0.0.0.0 --port ${PORT}"]
