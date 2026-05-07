# Multi-stage Dockerfile for both development and production builds
# syntax=docker/dockerfile:1.4
ARG BUILD_TYPE=production

# Base stage with common dependencies
FROM node:20-alpine AS base

ARG USER_ID=1000
ARG GROUP_ID=1000

WORKDIR /app

# Create a non-root user if it doesn't exist
# node:alpine already has a 'node' user with UID 1000,
# but we might need a different UID/GID.
SHELL ["/bin/ash", "-o", "pipefail", "-c"]
RUN if ! getent group harmony > /dev/null; then \
        addgroup -g "${GROUP_ID}" harmony || true; \
    fi && \
    if ! getent passwd harmony > /dev/null; then \
        adduser -u "${USER_ID}" -G "$(getent group "${GROUP_ID}" | cut -d: -f1 || echo harmony)" -D -h /home/harmony -s /bin/sh harmony || true; \
    fi && \
    chown -R ${USER_ID}:${GROUP_ID} /app

# Copy package files
COPY --chown=${USER_ID}:${GROUP_ID} package*.json ./

# Install dependencies
USER harmony
RUN npm install

# Development stage
FROM base AS development

# Source code will be mounted as volume for live reload
USER root
RUN printf '#!/bin/sh\nexec npm run dev -- --host 0.0.0.0 --port 3001\n' > /start.sh && \
    chmod +x /start.sh
USER harmony

EXPOSE 3001

# Production stage - Build the app
FROM base AS production-build

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Production stage - Serve with nginx
FROM nginx:alpine AS production

# Copy built assets from build stage
COPY --from=production-build /app/dist /usr/share/nginx/html

# Copy nginx configuration (will be in context root when building)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

# Final stage selection based on build type
FROM ${BUILD_TYPE} AS final

# Set up entrypoint based on build type
# Set up entrypoint based on build type
ARG BUILD_TYPE=production

# Use conditional entrypoint (production uses default nginx)
CMD ["/bin/sh", "-c", "if [ -f /start.sh ]; then /start.sh; else nginx -g 'daemon off;'; fi"]
