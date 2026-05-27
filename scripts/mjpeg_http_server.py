#!/usr/bin/env python3
from __future__ import annotations

import argparse
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import rclpy
from rclpy.node import Node
from rclpy.qos import (
    QoSDurabilityPolicy,
    QoSHistoryPolicy,
    QoSProfile,
    QoSReliabilityPolicy,
)
from sensor_msgs.msg import CompressedImage

latest_frame: bytes | None = None
frame_lock = threading.Lock()


class CameraRelay(Node):
    def __init__(self, topic: str):
        super().__init__("camera_mjpeg_server")
        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            durability=QoSDurabilityPolicy.VOLATILE,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=5,
        )
        self.sub = self.create_subscription(
            CompressedImage,
            topic,
            self.on_image,
            qos,
        )
        self.get_logger().info(f"[mjpeg] subscribe: {topic}")

    def on_image(self, msg: CompressedImage):
        global latest_frame
        fmt = (msg.format or "").lower()
        if fmt and "jpeg" not in fmt and "jpg" not in fmt:
            # 严格只转发 JPEG 帧，避免 H.264 无法直接拼接
            return
        with frame_lock:
            latest_frame = bytes(msg.data)


class MjpegHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        if self.path not in ("/", "/stream.mjpg"):
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        # 允许前端用 Canvas/MediaRecorder 做截图与录屏（跨域时依赖 CORS）
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()

        try:
            while True:
                with frame_lock:
                    frame = latest_frame
                if not frame:
                    time.sleep(0.05)
                    continue
                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode())
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
                time.sleep(0.03)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="/aima/hal/sensor/stereo_head_front_right/rgb_image/compressed")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    rclpy.init()
    node = CameraRelay(topic=args.topic)

    ros_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    ros_thread.start()

    server = ThreadingHTTPServer((args.host, args.port), MjpegHandler)
    print(f"[mjpeg] url: http://{args.host}:{args.port}/stream.mjpg  (topic={args.topic})")
    try:
        server.serve_forever()
    finally:
        server.server_close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
