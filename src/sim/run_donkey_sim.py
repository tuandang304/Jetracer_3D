
#!/usr/bin/env python3
"""
Chạy thuật toán Speed Track bên trong Donkey Simulator — trên Windows, KHÔNG cần
ROS, KHÔNG cần Ubuntu/WSL.

    python src/sim/run_donkey_sim.py
    python src/sim/run_donkey_sim.py --scene waveshare --line white --show

Xem hướng dẫn đầy đủ ở docs/donkey_sim_windows.md
"""

import argparse
import os
import sys
import threading
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# QUAN TRỌNG: phải cài rospy giả TRƯỚC khi import bất cứ thứ gì trong src/
from src.sim import rospy_stub          # noqa: E402
rospy_stub.install()

import cv2                              # noqa: E402
import numpy as np                      # noqa: E402
import rospy                            # noqa: E402  (đã là bản giả lập)

from src.sim.donkey_client import DonkeySimClient, SCENES   # noqa: E402


# Ngưỡng HSV cho từng loại vạch kẻ. Xe thật bám vạch ĐEN, còn trong sim thì
# tùy scene — đây là lý do phổ biến nhất khiến xe không chạy.
LINE_PRESETS = {
    "yellow": ((15, 50, 50), (40, 255, 255)),      # vạch vàng (mở rộng cho sim)
    "white":  ((0, 0, 200), (180, 45, 255)),        # vạch trắng
    "black":  ((0, 0, 0), (180, 255, 75)),          # như xe thật
}


class SimCar(object):
    """
    Lớp thay thế NvidiaRacecar: nhận .steering/.throttle rồi đẩy sang Donkey Sim.

    RacerController._set_throttle/_set_steering chỉ kiểm tra sự tồn tại của hai
    thuộc tính này, nên không cần sửa gì trong racer_controller.py.
    """

    def __init__(self, client):
        self._client = client
        self._steering = 0.0
        self._throttle = 0.0

    @property
    def steering(self):
        return self._steering

    @steering.setter
    def steering(self, value):
        self._steering = float(value)
        self._client.set_control(self._steering, self._throttle)

    @property
    def throttle(self):
        return self._throttle

    @throttle.setter
    def throttle(self, value):
        self._throttle = float(value)
        self._client.set_control(self._steering, self._throttle)


def patch_controller(client):
    """Ép RacerController dùng SimCar thay cho phần cứng thật."""
    from src.core.control import racer_controller as rc

    def _initialize_sim_hardware(self):
        self.car = SimCar(client)
        self._mock = False
        self._log("Khởi tạo chế độ Donkey Sim (điều khiển qua TCP).")

    rc.RacerController._initialize_hardware = _initialize_sim_hardware
    return rc


def patch_follow_only(module):
    """
    Tắt logic phát hiện giao lộ.

    Sa bàn Donkey Sim là đường đua vòng kín, không có ngã tư và không khớp
    map.json, nên ROI dự báo mất vạch ở khúc cua gấp sẽ bị hiểu nhầm là giao lộ
    và xe dừng lại. Ở đây ta luôn trả về "vẫn thấy vạch ở xa".
    """
    original = module.JetRacerController._get_line_center

    def _patched(self, image, roi_y, roi_h):
        value = original(self, image, roi_y, roi_h)
        if value is None and roi_y == self.LOOKAHEAD_ROI_Y:
            return self.WIDTH // 2
        return value

    module.JetRacerController._get_line_center = _patched


def start_camera_feed(controller, client, show=False, auto_reset=True):
    """
    Thay cho camera_callback của ROS: bơm khung hình từ sim vào controller.

    Chạy ở thread riêng đúng như callback ROS chạy bất đồng bộ với vòng lặp
    điều khiển 20 Hz.
    """
    stop = threading.Event()

    def _draw_debug_preprocessing(img):
        """Vẽ toàn bộ pipeline tiền xử lý lên các cửa sổ debug."""
        if img is None:
            return

        h, w = img.shape[:2]
        display = img.copy()

        # --- 1. Vẽ ROI lên frame gốc ---
        roi_y = controller.ROI_Y
        roi_h = controller.ROI_H
        la_y = controller.LOOKAHEAD_ROI_Y
        la_h = controller.LOOKAHEAD_ROI_H

        # ROI chính (xanh lá)
        cv2.rectangle(display, (0, roi_y), (w - 1, roi_y + roi_h), (0, 255, 0), 2)
        cv2.putText(display, f"ROI Main y={roi_y}", (5, roi_y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
        # ROI Lookahead (vàng)
        cv2.rectangle(display, (0, la_y), (w - 1, la_y + la_h), (0, 255, 255), 2)
        cv2.putText(display, f"Lookahead y={la_y}", (5, la_y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)

        # Vẽ vùng focus mask (đỏ nhạt)
        center_w = int(w * controller.ROI_CENTER_WIDTH_PERCENT)
        start_x = (w - center_w) // 2
        end_x = start_x + center_w
        cv2.line(display, (start_x, 0), (start_x, h), (0, 0, 255), 1)
        cv2.line(display, (end_x, 0), (end_x, h), (0, 0, 255), 1)

        # Trạng thái + HSV range
        state_name = getattr(controller.current_state, 'name', 'N/A')
        cv2.putText(display, f"State: {state_name}", (5, 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        hsv_lo = tuple(controller.LINE_COLOR_LOWER.tolist())
        hsv_hi = tuple(controller.LINE_COLOR_UPPER.tolist())
        cv2.putText(display, f"HSV: {hsv_lo}->{hsv_hi}", (5, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (200, 200, 200), 1)

        # --- 2. Color Mask (toàn ảnh) ---
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        color_mask = cv2.inRange(hsv, controller.LINE_COLOR_LOWER,
                                 controller.LINE_COLOR_UPPER)

        # --- 3. Focus Mask ---
        focus_mask = np.zeros_like(color_mask)
        cv2.rectangle(focus_mask, (start_x, 0), (end_x, h), 255, -1)

        # --- 4. Final Mask ---
        final_mask = cv2.bitwise_and(color_mask, focus_mask)

        # --- 5. Tìm contours trong ROI chính và vẽ lên display ---
        for roi_name, ry, rh, color in [("Main", roi_y, roi_h, (0, 255, 0)),
                                          ("LA", la_y, la_h, (0, 255, 255))]:
            roi_final = final_mask[ry:ry + rh, :]
            result = cv2.findContours(roi_final, cv2.RETR_EXTERNAL,
                                      cv2.CHAIN_APPROX_SIMPLE)
            # Tương thích cả OpenCV 3 và 4/5
            contours = result[0] if len(result) == 2 else result[1]
            px_count = cv2.countNonZero(roi_final)

            if contours:
                c = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(c)
                # Dịch contour về tọa độ gốc ảnh
                c_shifted = c.copy()
                c_shifted[:, :, 1] += ry
                cv2.drawContours(display, [c_shifted], -1, color, 2)

                M = cv2.moments(c)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"]) + ry
                    cv2.circle(display, (cx, cy), 5, (0, 0, 255), -1)
                    cv2.putText(display, f"{roi_name}: cx={cx} a={area} px={px_count}",
                                (5, ry + rh + 12),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)
            else:
                cv2.putText(display, f"{roi_name}: NO LINE (px={px_count})",
                            (5, ry + rh + 12),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

        # --- Hiển thị các cửa sổ ---
        sz = (400, 400)
        cv2.imshow("1. Camera + ROI", cv2.resize(display, sz))
        # Color mask dạng màu để dễ nhìn
        color_mask_bgr = cv2.cvtColor(color_mask, cv2.COLOR_GRAY2BGR)
        color_mask_bgr[:, :, 0] = 0   # tô xanh lá cho pixel detect
        cv2.imshow("2. Color Mask (HSV)", cv2.resize(color_mask_bgr, sz))
        final_mask_bgr = cv2.cvtColor(final_mask, cv2.COLOR_GRAY2BGR)
        cv2.imshow("3. Final Mask (Color+Focus)", cv2.resize(final_mask_bgr, sz))
        cv2.waitKey(1)

    def loop():
        last_reset = 0.0
        while not stop.is_set():
            frame = client.latest_frame
            if frame is not None:
                controller.latest_image = cv2.resize(
                    frame, (controller.WIDTH, controller.HEIGHT)
                )
                if show:
                    try:
                        _draw_debug_preprocessing(controller.latest_image)
                    except Exception as e:
                        rospy.logwarn_throttle(5, f"Debug draw error: {e}")

            if auto_reset and client.hit not in ("none", "", None):
                if time.time() - last_reset > 3.0:
                    rospy.logwarn(f"Xe va chạm ({client.hit}) — reset về vạch xuất phát.")
                    client.reset_car()
                    last_reset = time.time()

            time.sleep(1.0 / 30.0)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    return stop


def build_parser():
    parser = argparse.ArgumentParser(
        description="Chạy Speed Track trong Donkey Sim (không cần ROS)."
    )
    parser.add_argument("--host", default="127.0.0.1", help="IP của sim")
    parser.add_argument("--port", type=int, default=9091, help="Cổng TCP của sim")
    parser.add_argument("--scene", default="generated_track", choices=SCENES,
                        help="Sa bàn muốn nạp")
    parser.add_argument("--line", default="yellow", choices=sorted(LINE_PRESETS),
                        help="Màu vạch kẻ cần bám (generated_track: vạch vàng ở tim đường)")
    parser.add_argument("--throttle", type=float, default=0.35,
                        help="BASE_THROTTLE trong sim (xe thật: 0.20)")
    parser.add_argument("--turn-throttle", type=float, default=0.28,
                        help="TURN_THROTTLE trong sim")
    parser.add_argument("--gain", type=float, default=1.0,
                        help="STEERING_GAIN — tăng nếu xe cua chậm, giảm nếu xe lắc")
    parser.add_argument("--kp", type=float, default=0.6, help="PID_KP")
    parser.add_argument("--kd", type=float, default=0.15, help="PID_KD")
    parser.add_argument("--safe-zone", type=float, default=0.15,
                        help="SAFE_ZONE_PERCENT — vùng chết ở giữa ảnh")
    parser.add_argument("--intersection", action="store_true",
                        help="Bật lại logic giao lộ (mặc định tắt trong sim)")
    parser.add_argument("--video", default="sim_run.avi",
                        help="File video ghi lại (mặc định KHÔNG đụng jetracer_run.avi)")
    parser.add_argument("--show", action="store_true",
                        help="Mở cửa sổ xem ROI/line theo thời gian thực")
    parser.add_argument("--verbose", action="store_true",
                        help="In các bản tin nhận được từ sim")
    return parser


def main():
    args = build_parser().parse_args()

    client = DonkeySimClient(host=args.host, port=args.port,
                             scene=args.scene, verbose=args.verbose)
    client.connect()

    patch_controller(client)

    from src.speed_track import main_speed_track as mst
    if not args.intersection:
        patch_follow_only(mst)

    # Ghi đè tham số ngay trong setup_parameters để có hiệu lực từ lúc khởi tạo
    lower, upper = LINE_PRESETS[args.line]
    original_setup = mst.JetRacerController.setup_parameters

    def setup_for_sim(self):
        original_setup(self)
        self.LINE_COLOR_LOWER = np.array(lower)
        self.LINE_COLOR_UPPER = np.array(upper)
        self.VIDEO_OUTPUT_FILENAME = args.video

        # Camera sim nhìn xa hơn xe thật — vạch kẻ nằm ở giữa ảnh chứ
        # không phải ở sát đáy. Dịch ROI lên trên để quét đúng chỗ.
        self.ROI_Y = int(self.HEIGHT * 0.55)          # was 0.85
        self.ROI_H = int(self.HEIGHT * 0.20)          # was 0.15
        self.LOOKAHEAD_ROI_Y = int(self.HEIGHT * 0.30)  # was 0.60
        self.LOOKAHEAD_ROI_H = int(self.HEIGHT * 0.20)  # was 0.15

        # Mở rộng vùng quét ngang và giảm ngưỡng pixel cho ảnh sim nhỏ
        self.ROI_CENTER_WIDTH_PERCENT = 0.8            # was 0.5
        self.SCAN_PIXEL_THRESHOLD = 30                 # was 100

    mst.JetRacerController.setup_parameters = setup_for_sim

    rospy.init_node("jetracer_donkey_sim")

    os.chdir(REPO_ROOT)     # để models/ và file video nằm đúng chỗ
    controller = mst.JetRacerController()

    controller.controller.config.update({
        "BASE_THROTTLE": args.throttle,
        "TURN_THROTTLE": args.turn_throttle,
        "STEERING_GAIN": args.gain,
        "PID_KP": args.kp,
        "PID_KD": args.kd,
        "SAFE_ZONE_PERCENT": args.safe_zone,
    })
    rospy.loginfo(f"Bám vạch màu '{args.line}' HSV {lower} → {upper}; "
                  f"throttle={args.throttle}, gain={args.gain}")
    if not args.intersection:
        rospy.loginfo("Logic giao lộ ĐÃ TẮT (chế độ chỉ bám line).")

    stop_feed = start_camera_feed(controller, client, show=args.show)

    try:
        controller.run()
    except KeyboardInterrupt:
        rospy.loginfo("Người dùng dừng chương trình.")
    finally:
        rospy.signal_shutdown("done")
        stop_feed.set()
        time.sleep(0.3)
        try:
            controller.cleanup()
        except Exception:
            pass
        client.close()
        if args.show:
            cv2.destroyAllWindows()
        rospy.loginfo("Đã đóng kết nối sim.")


if __name__ == "__main__":
    main()
