#!/usr/bin/env python3
"""
Lái xe THỦ CÔNG bằng bàn phím WASD trong Donkey Simulator.

    python src/sim/manual_drive.py
    python src/sim/manual_drive.py --scene waveshare --throttle 0.6 --record lap.avi

Phím bấm (cửa sổ "JetRacer Manual Drive" phải đang được chọn):

    W / S      ga tiến / lùi (giữ phím)
    A / D      đánh lái trái / phải (thả ra là tự trả lái về giữa)
    SHIFT      giữ cùng W để chạy nhanh hơn (boost)
    SPACE      phanh — cắt ga ngay lập tức
    R          reset xe về vạch xuất phát
    Q / ESC    thoát

Trên Windows script đọc trạng thái phím thật (GetAsyncKeyState) nên giữ phím là
xe chạy liên tục, không bị khựng do độ trễ auto-repeat của bàn phím. Hệ điều
hành khác sẽ tự chuyển sang chế độ đọc phím qua cửa sổ OpenCV.
"""

import argparse
import os
import sys
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import cv2                                                      # noqa: E402
import numpy as np                                              # noqa: E402

from src.sim.donkey_client import DonkeySimClient, SCENES       # noqa: E402


WINDOW = "JetRacer Manual Drive (WASD)"      # tên ASCII để tìm được cửa sổ Win32


# ----------------------------------------------------------------------
# Đọc bàn phím
# ----------------------------------------------------------------------
class KeyReader(object):
    """
    Trả về tập các phím ĐANG được giữ.

    Windows: hỏi thẳng hệ điều hành trạng thái phím, nên biết được cả lúc nhả
    phím — điều khiển mượt như chơi game.
    Nền tảng khác: dùng cv2.waitKey, mỗi lần nhận được phím thì coi như phím đó
    còn được giữ trong HOLD giây (vì OpenCV không báo sự kiện nhả phím).
    """

    HOLD = 0.20     # giây, chỉ dùng cho chế độ dự phòng

    #: phím -> mã ảo của Windows
    VK = {
        "w": 0x57, "a": 0x41, "s": 0x53, "d": 0x44,
        "r": 0x52, "q": 0x51,
        "shift": 0x10, "space": 0x20, "esc": 0x1B,
    }

    def __init__(self, require_focus=True):
        self.native = False
        self._user32 = None
        self._hwnd = 0
        self._require_focus = require_focus
        self._fallback = {}

        if sys.platform == "win32":
            try:
                import ctypes
                self._user32 = ctypes.windll.user32
                self._user32.GetAsyncKeyState.restype = ctypes.c_short
                self.native = True
            except Exception:
                self.native = False

    # -- chế độ Windows -------------------------------------------------
    def _window_focused(self):
        if not self._require_focus:
            return True
        if not self._hwnd:
            # Cửa sổ HighGUI là cửa sổ Win32 thật, tìm theo đúng tiêu đề
            self._hwnd = self._user32.FindWindowW(None, WINDOW)
            if not self._hwnd:
                return True      # chưa tìm thấy thì đừng chặn người dùng
        return self._user32.GetForegroundWindow() == self._hwnd

    # -- API chính ------------------------------------------------------
    def pressed(self):
        if self.native:
            if not self._window_focused():
                return set()
            return {
                name for name, vk in self.VK.items()
                if self._user32.GetAsyncKeyState(vk) & 0x8000
            }

        now = time.time()
        return {k for k, t in self._fallback.items() if now - t < self.HOLD}

    def feed(self, key_code):
        """Nạp mã phím từ cv2.waitKey (chỉ có tác dụng ở chế độ dự phòng)."""
        if self.native or key_code < 0:
            return
        code = key_code & 0xFF
        name = {32: "space", 27: "esc"}.get(code)
        if name is None:
            ch = chr(code).lower() if 32 < code < 127 else ""
            name = ch if ch in self.VK else None
        if name is not None:
            self._fallback[name] = time.time()


# ----------------------------------------------------------------------
# Mô hình điều khiển
# ----------------------------------------------------------------------
class DriveState(object):
    """Biến phím bấm rời rạc thành lệnh ga/lái mượt theo thời gian."""

    def __init__(self, args):
        self.max_throttle = args.throttle
        self.boost_throttle = args.boost
        self.reverse_throttle = args.reverse
        self.accel_rate = args.accel          # đơn vị ga / giây
        self.coast_rate = args.coast          # tốc độ nhả ga khi buông W/S
        self.steer_rate = args.steer_rate     # tốc độ đánh lái
        self.center_rate = args.center_rate   # tốc độ trả lái về giữa

        self.steering = 0.0
        self.throttle = 0.0
        self.braking = False

    @staticmethod
    def _approach(value, target, rate, dt):
        step = rate * dt
        if value < target:
            return min(value + step, target)
        return max(value - step, target)

    def update(self, keys, dt):
        # --- lái ---
        target = 0.0
        if "a" in keys:
            target -= 1.0
        if "d" in keys:
            target += 1.0

        rate = self.steer_rate if target != 0.0 else self.center_rate
        self.steering = self._approach(self.steering, target, rate, dt)

        # --- ga ---
        self.braking = "space" in keys
        if self.braking:
            self.throttle = 0.0
            return self.steering, self.throttle

        forward = "w" in keys
        reverse = "s" in keys
        if forward and not reverse:
            target = self.boost_throttle if "shift" in keys else self.max_throttle
        elif reverse and not forward:
            target = -self.reverse_throttle
        else:
            target = 0.0

        rate = self.accel_rate if target != 0.0 else self.coast_rate
        self.throttle = self._approach(self.throttle, target, rate, dt)
        return self.steering, self.throttle


# ----------------------------------------------------------------------
# Giao diện
# ----------------------------------------------------------------------
def draw_bar(canvas, x, y, w, h, value, span=(-1.0, 1.0), color=(0, 220, 0)):
    """Vẽ thanh giá trị có vạch 0 ở giữa."""
    cv2.rectangle(canvas, (x, y), (x + w, y + h), (70, 70, 70), 1)
    lo, hi = span
    zero = int(x + w * (0.0 - lo) / (hi - lo))
    cv2.line(canvas, (zero, y), (zero, y + h), (110, 110, 110), 1)

    end = int(x + w * (float(np.clip(value, lo, hi)) - lo) / (hi - lo))
    if end != zero:
        x0, x1 = (zero, end) if end > zero else (end, zero)
        cv2.rectangle(canvas, (x0, y + 2), (x1, y + h - 2), color, -1)


def render(frame, state, client, fps, scale):
    """Ghép khung hình từ sim với bảng thông số."""
    view = cv2.resize(frame, None, fx=scale, fy=scale,
                      interpolation=cv2.INTER_NEAREST)
    h, w = view.shape[:2]
    panel = np.zeros((150, w, 3), dtype=np.uint8)
    panel[:] = (28, 28, 28)

    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(panel, "STEER", (10, 20), font, 0.45, (200, 200, 200), 1)
    draw_bar(panel, 80, 8, w - 100, 16, state.steering, color=(0, 200, 255))
    cv2.putText(panel, f"{state.steering:+.2f}", (w - 60, 20), font, 0.45,
                (0, 200, 255), 1)

    cv2.putText(panel, "THROT", (10, 48), font, 0.45, (200, 200, 200), 1)
    thr_color = (0, 0, 220) if state.throttle < 0 else (0, 220, 0)
    draw_bar(panel, 80, 36, w - 100, 16, state.throttle, color=thr_color)
    cv2.putText(panel, f"{state.throttle:+.2f}", (w - 60, 48), font, 0.45,
                thr_color, 1)

    hit = client.hit if client.hit not in ("none", "", None) else "-"
    line1 = (f"speed {client.speed:5.2f}   cte {client.cte:+6.2f}   "
             f"hit {hit}   fps {fps:4.1f}")
    cv2.putText(panel, line1, (10, 78), font, 0.45, (230, 230, 230), 1)

    if state.braking:
        cv2.putText(panel, "PHANH", (w - 90, 78), font, 0.5, (0, 80, 255), 2)

    cv2.putText(panel, "W/S ga lui   A/D lai   SHIFT boost", (10, 106),
                font, 0.42, (150, 150, 150), 1)
    cv2.putText(panel, "SPACE phanh   R reset   Q/ESC thoat", (10, 128),
                font, 0.42, (150, 150, 150), 1)

    return np.vstack([view, panel])


# ----------------------------------------------------------------------
def build_parser():
    p = argparse.ArgumentParser(
        description="Lái xe thủ công bằng WASD trong Donkey Simulator."
    )
    p.add_argument("--host", default="127.0.0.1", help="IP của sim")
    p.add_argument("--port", type=int, default=9091, help="Cổng TCP của sim")
    p.add_argument("--scene", default="generated_track", choices=SCENES,
                   help="Sa bàn muốn nạp")
    p.add_argument("--throttle", type=float, default=0.45,
                   help="Ga tối đa khi giữ W")
    p.add_argument("--boost", type=float, default=0.85,
                   help="Ga tối đa khi giữ SHIFT + W")
    p.add_argument("--reverse", type=float, default=0.35,
                   help="Ga tối đa khi lùi (S)")
    p.add_argument("--accel", type=float, default=1.8,
                   help="Tốc độ lên ga (đơn vị ga / giây)")
    p.add_argument("--coast", type=float, default=1.2,
                   help="Tốc độ nhả ga khi buông W/S")
    p.add_argument("--steer-rate", type=float, default=4.0,
                   help="Tốc độ đánh lái khi giữ A/D")
    p.add_argument("--center-rate", type=float, default=6.0,
                   help="Tốc độ tự trả lái về giữa khi thả A/D")
    p.add_argument("--scale", type=float, default=3.0,
                   help="Phóng to khung hình sim (ảnh gốc chỉ 160x120)")
    p.add_argument("--record", default=None, metavar="FILE",
                   help="Ghi lại màn hình ra file .avi")
    p.add_argument("--auto-reset", action="store_true",
                   help="Tự reset xe khi va chạm (mặc định: tự bấm R)")
    p.add_argument("--no-focus-check", action="store_true",
                   help="Nhận phím cả khi cửa sổ không được chọn (Windows)")
    p.add_argument("--verbose", action="store_true",
                   help="In các bản tin nhận được từ sim")
    return p


def main():
    args = build_parser().parse_args()

    client = DonkeySimClient(host=args.host, port=args.port,
                             scene=args.scene, verbose=args.verbose)
    client.connect()

    keys = KeyReader(require_focus=not args.no_focus_check)
    state = DriveState(args)
    writer = None

    cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
    print("[LÁI  ] W/S ga-lùi, A/D lái, SHIFT boost, SPACE phanh, "
          "R reset, Q/ESC thoát.")
    if keys.native:
        print("[LÁI  ] Đọc phím trực tiếp từ Windows — giữ phím là xe chạy liên tục.")
    else:
        print("[LÁI  ] Chế độ dự phòng qua OpenCV — hãy giữ phím, đừng gõ nhấp nhả.")

    last = time.perf_counter()
    fps = 0.0
    last_reset = 0.0
    r_was_down = False

    try:
        while True:
            now = time.perf_counter()
            dt = min(now - last, 0.1)       # chặn bước nhảy khi cửa sổ bị treo
            last = now
            if dt > 0:
                fps = 0.9 * fps + 0.1 * (1.0 / dt)

            held = keys.pressed()
            steering, throttle = state.update(held, dt)
            client.set_control(steering, throttle)

            # R: reset — chỉ ăn một lần cho mỗi lần bấm
            r_down = "r" in held
            if r_down and not r_was_down and now - last_reset > 0.5:
                client.reset_car()
                state.throttle = 0.0
                state.steering = 0.0
                last_reset = now
            r_was_down = r_down

            if args.auto_reset and client.hit not in ("none", "", None):
                if now - last_reset > 3.0:
                    print(f"[LÁI  ] Va chạm ({client.hit}) — reset.")
                    client.reset_car()
                    last_reset = now

            frame = client.latest_frame
            if frame is not None:
                canvas = render(frame, state, client, fps, args.scale)
                cv2.imshow(WINDOW, canvas)

                if args.record:
                    if writer is None:
                        h, w = canvas.shape[:2]
                        writer = cv2.VideoWriter(
                            args.record, cv2.VideoWriter_fourcc(*"XVID"),
                            30.0, (w, h)
                        )
                        print(f"[LÁI  ] Đang ghi vào {args.record}")
                    writer.write(canvas)

            key = cv2.waitKey(1)
            keys.feed(key)
            if (key & 0xFF) in (27, ord("q"), ord("Q")):
                break
            if "esc" in held or "q" in held:
                break
            # Người dùng bấm nút X đóng cửa sổ
            if cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break
    except KeyboardInterrupt:
        pass
    finally:
        client.set_control(0.0, 0.0)
        if writer is not None:
            writer.release()
            print(f"[LÁI  ] Đã lưu video {args.record}")
        client.close()
        cv2.destroyAllWindows()
        print("[LÁI  ] Đã đóng kết nối sim.")


if __name__ == "__main__":
    main()
