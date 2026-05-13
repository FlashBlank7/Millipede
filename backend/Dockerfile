FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (cached layer)
COPY pyproject.toml .
RUN pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir -e ".[dev]" || \
    pip install --no-cache-dir \
        fastapi uvicorn[standard] python-multipart \
        sqlalchemy[asyncio] alembic asyncpg psycopg2-binary \
        authlib python-jose[cryptography] passlib[bcrypt] \
        redis celery[redis] \
        boto3 minio \
        transitions \
        litellm anthropic openai \
        langgraph langchain-core \
        docker \
        "pydantic[email]" pydantic-settings python-dotenv httpx tenacity structlog anyio \
        pandas numpy openpyxl xlrd

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
