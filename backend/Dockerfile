FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1

WORKDIR /backend

RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project
COPY . .
RUN uv sync --locked

EXPOSE 8000

CMD ["uv", "run", "--frozen", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]