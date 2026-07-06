#!/bin/bash

PORT="5000"

echo "[INFO] Starting latency display UI..."
python3 latency_display.py &
LATENCY_UI_PID=$!

echo "[INFO] Waiting for THETA UI stream on udp://@:$PORT"
echo "[INFO] Press q in ffplay window to quit."

ffplay \
-loglevel warning \
-fflags nobuffer \
-flags low_delay \
-framedrop \
-probesize 32 \
-analyzeduration 0 \
-window_title "THETA UI Receiver" \
srt://@:$PORT?mode=listener&latency=50

kill "$LATENCY_UI_PID" 2>/dev/null

echo "[INFO] Receiver stopped."