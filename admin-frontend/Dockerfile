# syntax=docker/dockerfile:1.4
ARG BUILD_TYPE=production

FROM node:20-alpine AS base

WORKDIR /app

COPY package*.json ./
RUN npm install

FROM base AS development

RUN printf '#!/bin/sh\nexec npm run dev -- --host 0.0.0.0 --port 3001\n' > /start.sh && \
    chmod +x /start.sh

EXPOSE 3001

FROM base AS production-build

COPY . .
RUN npm run build

FROM nginx:alpine AS production

COPY --from=production-build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

FROM ${BUILD_TYPE} AS final

ARG BUILD_TYPE=production

CMD ["/bin/sh", "-c", "if [ -f /start.sh ]; then /start.sh; else nginx -g 'daemon off;'; fi"]
