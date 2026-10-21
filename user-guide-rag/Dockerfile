FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.21 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/models/huggingface \
    PATH="/app/.venv/bin:$PATH" \
    UV_LINK_MODE=copy

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,id=etch-user-guide-rag-uv,target=/root/.cache/uv \
    uv sync --locked --no-dev

COPY main.py init_models.py ./
COPY rag ./rag
COPY content ./content

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--workers", "1"]
