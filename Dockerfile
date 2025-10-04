FROM python:3.13-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY uv.lock ./
COPY entsoe_influx ./entsoe_influx

# Install dependencies
RUN uv sync --frozen --no-dev

# Set entrypoint
ENTRYPOINT ["uv", "run", "python", "-m", "entsoe_influx.main"]