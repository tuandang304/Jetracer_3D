#!/usr/bin/env python3
"""
Client nói chuyện trực tiếp với Donkey Simulator qua giao thức TCP JSON.

Không phụ thuộc gym / gym-donkeycar — chỉ cần numpy + opencv, nên chạy được
trên Windows với Python nào cũng được.

Giao thức: mỗi bản tin là một dòng JSON kết thúc bằng '\\n'.
  Gửi đi:  load_scene, car_config, cam_config, control, reset_car, exit_scene
  Nhận về: scene_selection_ready, car_loaded, telemetry, aborted
"""

import base64
import json
import socket
import threading
import time

import cv2
import numpy as np


# Tên scene hợp lệ của Donkey Sim
SCENES = [
    "generated_track",      # đường đua có vạch vàng ở tim đường (mặc định)
    "generated_road",       # đường quê ngoằn ngoèo
    "warehouse",            # nhà kho, vạch kẻ trên nền bê tông
    "sparkfun_avc",
    "roboracingleague_1",
    "waveshare",            # mô phỏng sa bàn Waveshare (giống JetRacer nhất)
    "mini_monaco",
    "warren",
    "circuit_launch",
]


class DonkeySimClient(object):
    """Giữ kết nối tới sim, cung cấp khung hình mới nhất và nhận lệnh lái."""

    def __init__(self, host="127.0.0.1", port=9091, scene="generated_track",
                 cam_config=None, verbose=False):
        self.host = host
        self.port = port
        self.scene = scene
        self.verbose = verbose

        # Ý định: đặt camera thấp và chúc xuống cho giống CSI cam trên JetRacer.
        # LƯU Ý: bản sim đang dùng BỎ QUA cam_config — ảnh trả về vẫn là 160x120
        # mặc định. Không sao vì code tự resize về 300x300, nhưng đừng trông đợi
        # chỉnh được góc/FOV camera qua đây.
        self.cam_config = cam_config or {
            "img_w": "320", "img_h": "240", "img_d": "3",
            "fov": "80", "fish_eye_x": "0.0", "fish_eye_y": "0.0",
            "offset_x": "0.0", "offset_y": "0.9", "offset_z": "0.4",
            "rot_x": "15.0", "img_enc": "JPG",
        }

        self.sock = None
        self._send_lock = threading.Lock()
        self._reader = None
        self._running = False
        self._buffer = b""
        self._seen_types = set()

        self._car_loaded = threading.Event()
        self._first_frame = threading.Event()

        # Trạng thái mới nhất từ sim
        self.latest_frame = None      # ảnh BGR (numpy uint8)
        self.frame_count = 0
        self.speed = 0.0
        self.cte = 0.0
        self.hit = "none"
        self.pos = (0.0, 0.0, 0.0)

        self._steering = 0.0
        self._throttle = 0.0

    # ------------------------------------------------------------
    # Kết nối
    # ------------------------------------------------------------
    def connect(self, timeout=30.0):
        """Kết nối, nạp scene và chờ tới khi có khung hình đầu tiên."""
        print(f"[SIM  ] Đang kết nối tới Donkey Sim {self.host}:{self.port} ...")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5.0)
        try:
            self.sock.connect((self.host, self.port))
        except socket.error as e:
            raise RuntimeError(
                f"Không kết nối được tới sim ({e}). Hãy chắc chắn đã mở "
                f"donkey_sim.exe và đang ở màn hình menu."
            )
        self.sock.settimeout(1.0)

        self._running = True
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

        # Gửi lại load_scene định kỳ tới khi sim báo đã nạp xong
        deadline = time.time() + timeout
        while time.time() < deadline and not self._car_loaded.is_set():
            self.send({"msg_type": "load_scene", "scene_name": self.scene})
            self._car_loaded.wait(2.0)

        if not self._car_loaded.is_set():
            print("[SIM  ] Chưa nhận được 'car_loaded' — vẫn thử chạy tiếp.")
        else:
            print(f"[SIM  ] Đã nạp scene '{self.scene}'.")

        time.sleep(0.5)
        self.send({
            "msg_type": "car_config",
            "body_style": "donkey", "body_r": "255", "body_g": "72", "body_b": "0",
            "car_name": "JetRacer", "font_size": "50",
        })
        time.sleep(0.2)
        config = {"msg_type": "cam_config"}
        config.update(self.cam_config)
        self.send(config)

        # Đá vòng lặp: sim chỉ gửi telemetry sau khi nhận control đầu tiên
        self.set_control(0.0, 0.0)
        if not self._first_frame.wait(10.0):
            raise RuntimeError(
                "Sim không gửi khung hình nào. Kiểm tra lại tên scene "
                f"('{self.scene}') hoặc chạy lại với --verbose."
            )
        print("[SIM  ] Đã nhận khung hình đầu tiên. Sẵn sàng.")

    def close(self):
        self._running = False
        try:
            self.set_control(0.0, 0.0)
            self.send({"msg_type": "exit_scene"})
        except Exception:
            pass
        time.sleep(0.2)
        if self.sock is not None:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    # ------------------------------------------------------------
    # Gửi lệnh
    # ------------------------------------------------------------
    def send(self, message):
        if self.sock is None:
            return
        payload = (json.dumps(message) + "\n").encode("utf-8")
        with self._send_lock:
            try:
                self.sock.sendall(payload)
            except socket.error as e:
                if self._running:
                    print(f"[SIM  ] Lỗi gửi dữ liệu: {e}")

    def set_control(self, steering, throttle):
        """steering: -1.0 (trái) → +1.0 (phải); throttle: -1.0 → +1.0."""
        self._steering = float(np.clip(steering, -1.0, 1.0))
        self._throttle = float(np.clip(throttle, -1.0, 1.0))
        self._send_control()

    def _send_control(self):
        # Sim yêu cầu các giá trị dạng chuỗi
        self.send({
            "msg_type": "control",
            "steering": str(self._steering),
            "throttle": str(self._throttle),
            "brake": "0.0",
        })

    def reset_car(self):
        print("[SIM  ] Reset xe về vạch xuất phát.")
        self.send({"msg_type": "reset_car"})

    # ------------------------------------------------------------
    # Nhận dữ liệu
    # ------------------------------------------------------------
    def _read_loop(self):
        while self._running:
            try:
                chunk = self.sock.recv(16384)
            except socket.timeout:
                continue
            except socket.error:
                break
            if not chunk:
                break
            self._buffer += chunk
            while b"\n" in self._buffer:
                line, self._buffer = self._buffer.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    self._handle(json.loads(line.decode("utf-8")))
                except ValueError:
                    continue

    def _handle(self, message):
        msg_type = message.get("msg_type", "")

        if self.verbose and msg_type not in self._seen_types:
            self._seen_types.add(msg_type)
            print(f"[SIM  ] Nhận bản tin loại '{msg_type}'.")

        if msg_type == "telemetry":
            self._handle_telemetry(message)
        elif msg_type == "car_loaded":
            self._car_loaded.set()
        elif msg_type == "scene_selection_ready":
            self.send({"msg_type": "load_scene", "scene_name": self.scene})
        elif msg_type == "aborted":
            print("[SIM  ] Sim báo 'aborted' — scene bị hủy.")

    def _handle_telemetry(self, message):
        encoded = message.get("image")
        if encoded:
            try:
                raw = np.frombuffer(base64.b64decode(encoded), dtype=np.uint8)
                frame = cv2.imdecode(raw, cv2.IMREAD_COLOR)  # trả về BGR
                if frame is not None:
                    self.latest_frame = frame
                    self.frame_count += 1
                    self._first_frame.set()
            except Exception as e:
                print(f"[SIM  ] Lỗi giải mã ảnh: {e}")

        self.speed = float(message.get("speed", 0.0) or 0.0)
        self.cte = float(message.get("cte", 0.0) or 0.0)
        self.hit = message.get("hit", "none")
        self.pos = (
            float(message.get("pos_x", 0.0) or 0.0),
            float(message.get("pos_y", 0.0) or 0.0),
            float(message.get("pos_z", 0.0) or 0.0),
        )

        # Trả lời mỗi telemetry bằng lệnh điều khiển hiện tại để sim chạy đều nhịp
        self._send_control()
