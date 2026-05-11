# --- Stage 1: build the React frontend ---
FROM node:20-alpine AS frontend
WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./
RUN npm run build


# --- Stage 2: runtime — Python + Playwright + bundled frontend ---
FROM mcr.microsoft.com/playwright/python:v1.59.0-noble

WORKDIR /app

# Python deps
COPY pyproject.toml README.md ./
COPY app/ ./app/
COPY scraper/ ./scraper/
RUN pip install --no-cache-dir -e .

# Built frontend
COPY --from=frontend /app/frontend/dist ./frontend/dist

# Persistent state lives under /data (mounted as a volume).
ENV BB_DB_PATH=/data/betterblackboard.db \
    BB_STORAGE_STATE=/data/storage_state.json \
    BB_HEADLESS=true

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
