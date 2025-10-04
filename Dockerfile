# Build stage
FROM python:3.13-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock ./

# Install dependencies into .venv
RUN uv sync --frozen --no-dev

# Runtime stage
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Copy venv from builder
COPY --from=builder /app/.venv /app/.venv

# Copy source code
COPY entsoe_influx ./entsoe_influx

# Set entrypoint using venv directly
ENTRYPOINT ["/app/.venv/bin/python", "-m", "entsoe_influx.main"]