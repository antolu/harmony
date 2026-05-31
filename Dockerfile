FROM python:3.13-slim

WORKDIR /app

# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY harmony/ ./harmony/
COPY alembic/ ./alembic/
COPY alembic.ini ./

ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.1.0
RUN pip install --no-cache-dir -e "."

EXPOSE 8000

CMD ["harmony-api"]
