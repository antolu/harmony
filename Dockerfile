FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY harmony/ ./harmony/

# Install Python dependencies
# Set pretend version to avoid needing .git folder
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.1.0
RUN pip install --no-cache-dir -e ".[elasticsearch]"

# Expose API port
EXPOSE 8000

# Run the API
CMD ["harmony-api"]
