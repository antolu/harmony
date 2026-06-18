# SSO Browser container with VNC for interactive authentication
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    x11vnc \
    xvfb \
    fluxbox \
    chromium-browser \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /app

# Setup VNC
ENV DISPLAY=:0
ENV VNC_PORT=5900
ENV SCREEN_WIDTH=1280
ENV SCREEN_HEIGHT=800
ENV SCREEN_DEPTH=24

# Startup script
COPY start-vnc.sh /app/
RUN chmod +x /app/start-vnc.sh && mkdir -p /sessions

EXPOSE 5900

CMD ["/app/start-vnc.sh"]
