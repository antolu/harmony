# Multi-stage Dockerfile for both development and production builds
# syntax=docker/dockerfile:1.4
ARG BUILD_TYPE=production

# Base stage with common dependencies
FROM python:3.13-slim AS base

ARG USER_ID=1000
ARG GROUP_ID=1000

WORKDIR /app

# Install base system dependencies
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN groupadd -g ${GROUP_ID} harmony || groupmod -n harmony "$(getent group ${GROUP_ID} | cut -d: -f1)" || true && \
    useradd -l -u ${USER_ID} -g ${GROUP_ID} -m -s /bin/bash harmony || \
    useradd -l -u ${USER_ID} -g "$(getent group ${GROUP_ID} | cut -d: -f1)" -m -s /bin/bash harmony || true

# Development stage
FROM base AS development

# Copy package files first to leverage Docker layer cache
COPY pyproject.toml README.md ./
COPY harmony/__init__.py harmony/__init__.py

# Set version for setuptools-scm
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.1.0

# Install dependencies and create data directories
RUN pip install --no-cache-dir -e ".[admin,elasticsearch]" \
    && mkdir -p /data/configs /data/logs /data/jobs /crawl-output \
    && chown -R "${USER_ID}:${GROUP_ID}" /data /app /crawl-output

# Source code will be mounted as volume for live reload

EXPOSE 8000

# Production stage
FROM base AS production

# Copy package files
COPY pyproject.toml README.md ./
COPY harmony/__init__.py harmony/__init__.py

# Set version for setuptools-scm
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.1.0

# Install dependencies
RUN pip install --no-cache-dir -e ".[admin,elasticsearch]"

# Copy application code and create data directories
COPY harmony/ /app/harmony/
RUN mkdir -p /data/configs /data/logs /data/jobs /crawl-output \
    && chown -R "${USER_ID}:${GROUP_ID}" /data /app /crawl-output

EXPOSE 8000

# Final stage selection based on build type
FROM ${BUILD_TYPE} AS final

# Set up entrypoint based on build type
ARG BUILD_TYPE=production
RUN if [ "$BUILD_TYPE" = "development" ]; then \
        printf '#!/bin/bash\nset -e\nalembic upgrade head\nexec uvicorn harmony.api.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /app/harmony\n' > /start.sh && \
        chmod +x /start.sh; \
    else \
        printf '#!/bin/bash\nset -e\nalembic upgrade head\nexec uvicorn harmony.api.main:app --host 0.0.0.0 --port 8000\n' > /start.sh && \
        chmod +x /start.sh; \
    fi

USER harmony

ENTRYPOINT ["/start.sh"]
