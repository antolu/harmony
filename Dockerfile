FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY harmony/ ./harmony/

# Install Python dependencies
RUN pip install --no-cache-dir -e ".[elasticsearch]"

# Expose API port
EXPOSE 8000

# Run the API
CMD ["harmony-api"]
