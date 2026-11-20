# Backend – Python 3.12 + Tesseract OCR (tiếng Việt + tiếng Anh)
# Multi-stage: builder cài uv và deps; runtime copy .venv + app
# Chạy với non-root user "app" (uid 1000).

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Tesseract và gói ngôn ngữ cần thiết ở build stage để kiểm tra import
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-vie \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cài uv
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv

WORKDIR /app/src/backend

# Cài dependency đã khóa cùng package AI nội bộ.
COPY backend/pyproject.toml backend/uv.lock ./
COPY ai/pyproject.toml ../ai/
COPY ai/hr_ats_ai ../ai/hr_ats_ai

RUN uv sync --frozen --no-dev

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Chỉ cài Tesseract runtime (không cần build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-vie \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd -r app && useradd -r -g app -u 1000 app

WORKDIR /app/src/backend

# Giữ nguyên đường dẫn venv và package editable như ở builder.
COPY --from=builder /app/src/backend/.venv ./.venv
COPY --from=builder /app/src/ai/hr_ats_ai ../ai/hr_ats_ai

COPY backend/app ./app
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations

RUN mkdir -p var/storage ../ai/var && chown -R app:app var ../ai/var

ENV PATH="/app/src/backend/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

USER app

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000

# Default: API server; override CMD để chạy worker/beat
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
