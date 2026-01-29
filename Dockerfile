# SIP Relay Server v2 - Docker Image
# Multi-stage build for optimized image size

# =============================================================================
# Stage 1: Builder - Install dependencies and download models
# =============================================================================
FROM python:3.12-slim AS builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install UV package manager
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Install Python dependencies
RUN uv sync --frozen --no-dev

# =============================================================================
# Stage 2: Runtime - Final lightweight image
# =============================================================================
FROM python:3.12-slim AS runtime

# Labels
LABEL org.opencontainers.image.title="SIP Relay Server v2"
LABEL org.opencontainers.image.description="AI-powered SIP relay server with STT/LLM/TTS pipeline"
LABEL org.opencontainers.image.version="0.2.0"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 sipserver

# Set working directory
WORKDIR /app

# Copy UV from builder
COPY --from=builder /root/.local/bin/uv /usr/local/bin/uv

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Set PATH to use virtual environment
ENV PATH="/app/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/.venv"

# Copy application code
COPY --chown=sipserver:sipserver . .

# Create required directories
RUN mkdir -p /app/output/transcode /app/output/response /app/output/converted /app/recording \
    && chown -R sipserver:sipserver /app/output /app/recording

# Ensure voices directory exists (should be volume-mounted or copied)
RUN mkdir -p /app/voices && chown -R sipserver:sipserver /app/voices

# Switch to non-root user
USER sipserver

# Health check - verify Python and key modules are importable
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import websockets; import pydantic; print('OK')" || exit 1

# Default environment variables (can be overridden)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV LOG_LEVEL=INFO

# Expose ports
# SIP UDP ports
EXPOSE 5060/udp
EXPOSE 5062/udp
# WebSocket TCP port
EXPOSE 8080/tcp
# RTP UDP port range (31000-31010)
EXPOSE 31000-31010/udp

# Default command - run the SIP receive server
CMD ["python", "receive_server.py"]
