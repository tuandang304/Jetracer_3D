# -*- coding: utf-8 -*-
from __future__ import print_function
try:
    from IPython.display import display
except ImportError:
    pass

import traitlets
import ipywidgets.widgets as widgets
from jetracer.nvidia_racecar import NvidiaRacecar

car = NvidiaRacecar()

try:
    car.steering_motor.set_pulse_width_range(500, 2500)
    print("✅ Đã mở khóa giới hạn góc cua vật lý (PWM: 500 - 2500) thành công!")
except Exception as e:
    print("⚠️ Không thể can thiệp xung PWM:", e)

car.steering_gain = -1.0
car.throttle_gain = 0.3  # Giảm tốc độ tối đa xuống 30% (tùy chỉnh từ 0.1 đến 1.0)

controller = widgets.Controller(index=0)
display(controller)
print("👉 CHÚ Ý: Hãy bấm một nút bất kỳ hoặc xoay nhẹ 2 cần gạt để kích hoạt tay cầm.")


btn_connect = widgets.Button(description="KÍCH HOẠT ĐIỀU KHIỂN XE", button_style='success', layout=widgets.Layout(width='300px', height='40px'))
output = widgets.Output()

def thuc_hien_ket_noi(b):
    with output:
        output.clear_output()
        num_axes = len(controller.axes)
        print("📊 Số trục (Axes) trình duyệt đang nhận diện: {}".format(num_axes))
        
        if num_axes >= 3:
            try:
                # Dùng AXES[2] cho bẻ lái (Cần PHẢI) và AXES[1] cho ga (Cần TRÁI)
                traitlets.dlink((controller.axes[2], 'value'), (car, 'steering'), transform=lambda x: x)
                traitlets.dlink((controller.axes[1], 'value'), (car, 'throttle'), transform=lambda x: -x)
                
                print("🚀 [THÀNH CÔNG] Đã tách cần gạt thành công!")
                print("🕹️ Cần TRÁI (Axis 1): Tiến / Lùi")
                print("🕹️ Cần PHẢI (Axis 2): Bẻ lái Trái / Phải")
                print("⚡ Tốc độ tối đa: {}% (car.throttle_gain = {})".format(int(car.throttle_gain * 100), car.throttle_gain))
            except Exception as errors:
                print("❌ Lỗi khi thiết lập liên kết: {}".format(errors))
        elif num_axes >= 2:
            try:
                # Nếu chỉ nhận 2 trục (tay cầm đơn giản): Dùng AXES[0] cho bẻ lái và AXES[1] cho ga
                traitlets.dlink((controller.axes[0], 'value'), (car, 'steering'), transform=lambda x: x)
                traitlets.dlink((controller.axes[1], 'value'), (car, 'throttle'), transform=lambda x: -x)
                
                print("🚀 [THÀNH CÔNG] Đã kết nối tay cầm chế độ 2 trục!")
                print("🕹️ Axis 0: Bẻ lái Trái / Phải")
                print("🕹️ Axis 1: Tiến / Lùi")
                print("⚡ Tốc độ tối đa: {}% (car.throttle_gain = {})".format(int(car.throttle_gain * 100), car.throttle_gain))
            except Exception as errors:
                print("❌ Lỗi khi thiết lập liên kết: {}".format(errors))
        else:
            print("❌ [THẤT BẠI] Trình duyệt chưa nhận diện đủ cần gạt (Hiện có: {} trục).".format(num_axes))
            print("👉 HƯỚNG DẪN SỬA LỖI:")
            print("  1. Tay cầm PHẢI cắm vào MÁY TÍNH/LAPTOP (nơi mở trình duyệt web), KHÔNG cắm vào Jetson.")
            print("  2. Bấm một vài nút (A, B, X, Y) và xoay tròn 2 cần gạt vài vòng để trình duyệt nhận diện.")
            print("  3. Nhìn ô Controller() phía trên xem các thanh trượt có nhúc nhích khi bạn gạt cần không.")
            print("  4. Bấm lại nút này để kích hoạt.")

btn_connect.on_click(thuc_hien_ket_noi)

print("-" * 60)
display(btn_connect, output)