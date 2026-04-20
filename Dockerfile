FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    apt install gcc -y && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY ./pyproject.toml ./uv.lock ./README.md /app/

RUN uv sync --frozen --no-dev --no-install-project

COPY src/ /app/src

RUN uv sync --frozen --no-dev

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import webrtcvad; import websockets; import pydantic; print('OK')" || exit 1


CMD ["uv", "run", "./receive_server.py"]