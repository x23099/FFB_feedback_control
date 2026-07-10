import argparse
import asyncio
import json
import logging
import socket
import sys
import threading
import time
from collections import deque
import numpy as np
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
from PySide6.QtCore import Qt, Signal, QObject, Slot
from PySide6.QtGui import QFont, QImage, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout, QHBoxLayout

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webrtc_receive")

LATENCY_PORT = 5001
HTTP_PORT = 5002

class ReceiveSignals(QObject):
    frame_received = Signal(np.ndarray)
    latency_updated = Signal(float, float, str)

class WebRTCReceiveWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("THETA UI WebRTC Receiver")
        self.resize(1280, 800)

        # Video Display Label.
        self.label_video = QLabel("Waiting for WebRTC stream...")
        self.label_video.setAlignment(Qt.AlignCenter)
        self.label_video.setStyleSheet("background-color: black; color: white;")
        self.label_video.setFont(QFont("Arial", 24))

        # Latency Display Labels.
        self.label_latency = QLabel("Latency: --- ms")
        self.label_latency.setFont(QFont("Arial", 20, QFont.Bold))
        
        self.label_fps = QLabel("FPS: ---")
        self.label_fps.setFont(QFont("Arial", 20, QFont.Bold))
        
        self.label_sender = QLabel("Sender: Waiting...")
        self.label_sender.setFont(QFont("Arial", 12))

        # Info Bar.
        info_layout = QHBoxLayout()
        info_layout.addWidget(self.label_latency)
        info_layout.addWidget(self.label_fps)
        info_layout.addWidget(self.label_sender)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.label_video, stretch=1)
        main_layout.addLayout(info_layout)
        self.setLayout(main_layout)

    @Slot(np.ndarray)
    def update_frame(self, frame):
        t0 = time.perf_counter()
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        
        # PyAV/aiortc outputs RGB24 format.
        q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        
        scaled_pixmap = pixmap.scaled(
            self.label_video.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.label_video.setPixmap(scaled_pixmap)
        t1 = time.perf_counter()

        if not hasattr(self, 'draw_count'):
            self.draw_count = 0
            self.draw_total_time = 0.0
        self.draw_count += 1
        self.draw_total_time += (t1 - t0)
        
        if self.draw_count >= 30:
            avg_draw = (self.draw_total_time / 30) * 1000
            print(f"[RCV-LATENCY] Qt Draw & Scale (30 frames avg): {avg_draw:.1f}ms")
            self.draw_count = 0
            self.draw_total_time = 0.0

    @Slot(float, float, str)
    def update_latency(self, latency_ms, fps, sender_ip):
        self.label_latency.setText(f"Latency: {latency_ms:.1f} ms")
        self.label_fps.setText(f"FPS: {fps:.1f}")
        self.label_sender.setText(f"from {sender_ip}")

        if latency_ms < 50 and fps >= 25:
            self.setStyleSheet("background-color: #d8ffd8; color: black;")
        elif latency_ms < 150 and fps >= 15:
            self.setStyleSheet("background-color: #fff3b0; color: black;")
        else:
            self.setStyleSheet("background-color: #ffd0d0; color: black;")

# Asyncio thread hosting the HTTP signaling server and WebRTC engine.
class WebRTCServerThread(threading.Thread):
    def __init__(self, signals):
        super().__init__(daemon=True)
        self.signals = signals
        self.loop = None
        self.pc = None

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.start_server())

    async def start_server(self):
        app = web.Application()
        app.router.add_post("/offer", self.handle_offer)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", HTTP_PORT)
        
        logger.info(f"Starting HTTP signaling server on port {HTTP_PORT}...")
        await site.start()
        
        while True:
            await asyncio.sleep(3600)

    async def handle_offer(self, request):
        params = await request.json()
        offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

        self.pc = RTCPeerConnection()
        
        @self.pc.on("track")
        def on_track(track):
            logger.info(f"Track received: {track.kind}")
            if track.kind == "video":
                asyncio.ensure_future(self.process_video(track))

        @self.pc.on("connectionstatechange")
        def on_state_change():
            logger.info(f"Connection state changed: {self.pc.connectionState}")

        await self.pc.setRemoteDescription(offer)
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)

        return web.Response(
            content_type="application/json",
            text=json.dumps({
                "sdp": self.pc.localDescription.sdp,
                "type": self.pc.localDescription.type
            })
        )

    async def process_video(self, track):
        recv_count = 0
        recv_stats = {'recv': 0.0, 'conv': 0.0}
        
        while True:
            try:
                t_recv_start = time.perf_counter()
                frame = await track.recv()
                t_recv_end = time.perf_counter()
                
                t_conv_start = time.perf_counter()
                img = frame.to_ndarray(format="rgb24")
                t_conv_end = time.perf_counter()
                
                self.signals.frame_received.emit(img)
                
                recv_count += 1
                recv_stats['recv'] += (t_recv_end - t_recv_start)
                recv_stats['conv'] += (t_conv_end - t_conv_start)
                
                if recv_count >= 30:
                    avg_recv = (recv_stats['recv'] / 30) * 1000
                    avg_conv = (recv_stats['conv'] / 30) * 1000
                    print(f"[RCV-LATENCY] Track.recv() wait: {avg_recv:.1f}ms | RGB conversion: {avg_conv:.1f}ms")
                    recv_count = 0
                    recv_stats = {'recv': 0.0, 'conv': 0.0}
            except Exception as e:
                logger.error(f"Error processing video frame: {e}")
                break

def latency_receiver(signals):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", LATENCY_PORT))
    
    recv_times = deque()
    
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            sent_ns = int(data.decode())
            now_ns = time.time_ns()
            now_sec = time.time()

            latency_ms = (now_ns - sent_ns) / 1_000_000
            recv_times.append(now_sec)

            while recv_times and now_sec - recv_times[0] > 1.0:
                recv_times.popleft()

            fps = len(recv_times)
            signals.latency_updated.emit(latency_ms, float(fps), addr[0])
        except Exception:
            pass

def main():
    app = QApplication(sys.argv)
    
    signals = ReceiveSignals()
    window = WebRTCReceiveWindow()
    
    signals.frame_received.connect(window.update_frame)
    signals.latency_updated.connect(window.update_latency)
    
    server_thread = WebRTCServerThread(signals)
    server_thread.start()
    
    latency_thread = threading.Thread(target=latency_receiver, args=(signals,), daemon=True)
    latency_thread.start()
    
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
