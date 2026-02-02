# Stage 1: Build frontend
FROM node:20-alpine AS frontend
WORKDIR /app

COPY admin-frontend/package*.json ./
RUN npm install

COPY admin-frontend/ ./
RUN npm run build

# Stage 2: Production
FROM python:3.13-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends nginx supervisor && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python package
COPY harmony/ /app/harmony/
COPY pyproject.toml /app/
COPY README.md /app/

# Install Python dependencies
ENV SETUPTOOLS_SCM_PRETEND_VERSION=0.1.0
RUN pip install --no-cache-dir -e ".[admin,elasticsearch]"

# Copy frontend build
COPY --from=frontend /app/dist /app/frontend/dist

# Copy nginx config
COPY admin-docker/nginx.conf /etc/nginx/sites-available/default

# Copy supervisor config
COPY admin-docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Create data directories
RUN mkdir -p /data/configs /data/logs /data/jobs

# Expose port
EXPOSE 80

# Start services
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
