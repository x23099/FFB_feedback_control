#!/bin/bash

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1

echo "[INFO] Starting WebRTC Receiver UI..."
/home/robo25/theta_ws/RICHO-theta/src/theta-env/bin/python webrtc_receive.py
