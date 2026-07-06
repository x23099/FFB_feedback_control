#!/bin/bash

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1

echo "[INFO] Starting WebRTC Receiver UI..."
python3 webrtc_receive.py
