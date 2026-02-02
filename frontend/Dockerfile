# Multi-stage Dockerfile for both development and production builds
# syntax=docker/dockerfile:1.4
ARG BUILD_TYPE=production

# Base stage with common dependencies
FROM node:20-alpine AS base

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Development stage
FROM base AS development

# Source code will be mounted as volume for live reload

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
ARG BUILD_TYPE=production
RUN if [ "$BUILD_TYPE" = "development" ]; then \
        printf '#!/bin/sh\nexec npm run dev -- --host 0.0.0.0 --port 3001\n' > /start.sh && \
        chmod +x /start.sh; \
    fi

# Use conditional entrypoint (production uses default nginx)
CMD ["/bin/sh", "-c", "if [ -f /start.sh ]; then /start.sh; else nginx -g 'daemon off;'; fi"]
