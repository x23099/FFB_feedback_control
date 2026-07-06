import socket
import sys
import threading
import time
from collections import deque

from PySide6.QtCore import Signal, QObject
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout


LATENCY_PORT = 5001


class LatencySignal(QObject):
    updated = Signal(float, float, str)


class LatencyWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Stream Latency Monitor")
        self.resize(460, 230)

        self.label_title = QLabel("STREAM STATUS")
        self.label_title.setFont(QFont("Arial", 18, QFont.Bold))

        self.label_latency = QLabel("Latency: --- ms")
        self.label_latency.setFont(QFont("Arial", 32, QFont.Bold))

        self.label_fps = QLabel("FPS: ---")
        self.label_fps.setFont(QFont("Arial", 32, QFont.Bold))

        self.label_from = QLabel("Waiting for sender...")
        self.label_from.setFont(QFont("Arial", 14))

        layout = QVBoxLayout()
        layout.addWidget(self.label_title)
        layout.addWidget(self.label_latency)
        layout.addWidget(self.label_fps)
        layout.addWidget(self.label_from)
        self.setLayout(layout)

    def update_status(self, latency_ms, fps, sender_ip):
        self.label_latency.setText(f"Latency: {latency_ms:.1f} ms")
        self.label_fps.setText(f"FPS: {fps:.1f}")
        self.label_from.setText(f"from {sender_ip}")

        if latency_ms < 50 and fps >= 25:
            self.setStyleSheet("background-color: #d8ffd8; color: black;")
        elif latency_ms < 150 and fps >= 15:
            self.setStyleSheet("background-color: #fff3b0; color: black;")
        else:
            self.setStyleSheet("background-color: #ffd0d0; color: black;")


def latency_receiver(signal_obj):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", LATENCY_PORT))

    recv_times = deque()

    while True:
        data, addr = sock.recvfrom(1024)

        try:
            sent_ns = int(data.decode())
            now_ns = time.time_ns()
            now_sec = time.time()

            latency_ms = (now_ns - sent_ns) / 1_000_000

            recv_times.append(now_sec)

            while recv_times and now_sec - recv_times[0] > 1.0:
                recv_times.popleft()

            fps = len(recv_times)

            signal_obj.updated.emit(latency_ms, float(fps), addr[0])

        except Exception:
            pass


def main():
    app = QApplication(sys.argv)

    signal_obj = LatencySignal()
    window = LatencyWindow()
    signal_obj.updated.connect(window.update_status)

    thread = threading.Thread(target=latency_receiver, args=(signal_obj,), daemon=True)
    thread.start()

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()