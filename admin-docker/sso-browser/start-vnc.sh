#!/bin/bash

# Start Xvfb
Xvfb $DISPLAY -screen 0 ${SCREEN_WIDTH}x${SCREEN_HEIGHT}x${SCREEN_DEPTH} &
sleep 2

# Start window manager
fluxbox &
sleep 2

# Start VNC server (no password for internal use)
x11vnc -display $DISPLAY -nopw -forever -shared -rfbport $VNC_PORT &

# Wait for VNC to start
sleep 2

echo "VNC server started on port $VNC_PORT"

# Keep container running
tail -f /dev/null
