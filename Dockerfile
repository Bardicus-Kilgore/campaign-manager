FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies first (layer cache)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --python 3.12

# Copy application code
COPY app/        ./app/
COPY static/     ./static/
COPY templates/  ./templates/
COPY server.py   ./
COPY pf2e.db     ./pf2e.db.seed

# Data directory for uploads, references, and the live DB
RUN mkdir -p /data/uploads /data/references

COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5000
ENTRYPOINT ["/entrypoint.sh"]
