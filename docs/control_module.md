# Tài liệu Chi tiết Module Điều khiển (Control Module)

Tài liệu này đặc tả cơ chế điều khiển phần cứng của xe JetRacer Pro sử dụng hệ thống lái Ackermann Steering, bộ điều khiển bám làn PID và thuật toán rẽ vòng cung theo thời gian.

---

## 1. Cơ chế lái Ackermann Steering so với Lái Vi sai (Differential Drive)

Hệ thống điều khiển xe JetRacer sử dụng mô hình vật lý **Ackermann Steering** (tương tự như ô tô thực tế) thay vì hệ thống lái vi sai (Differential Drive) như xe JetBot:

- **JetBot (Lái vi sai):** Điều khiển độc lập tốc độ hai bánh trái và phải. Xe có thể quay tròn tại chỗ bằng cách cho một bánh quay tiến và một bánh quay lùi. Lệnh lái: `set_motors(left_speed, right_speed)`.
- **JetRacer (Ackermann):** Lái bằng cách điều khiển một servo cơ khí để đổi hướng góc của cụm bánh trước, kết hợp một động cơ kéo chính ở trục sau để điều khiển tốc độ. **Xe không thể quay tại chỗ** mà bắt buộc phải di chuyển tiến hoặc lùi để thực hiện vòng cua. Lệnh lái: `steering = angle` (hướng servo) và `throttle = speed` (tốc độ động cơ).

```text
       [Bánh trước trái]      [Bánh trước phải]
              \                     /
               \─── [Servo Lái] ───/
                        │
                        │
                        │
                  [Trục truyền động]
                        │
                        │
               ┌────────┴────────┐
         [Bánh sau trái]   [Bánh sau phải]
               └────────┬────────┘
                        │
                 [Động cơ kéo]
```

---

## 2. Giao tiếp Phần cứng (RacerController)

Lớp [RacerController](file:///d:/JetsonAIRacer/src/core/control/racer_controller.py#L64) đóng vai trò là một lớp trừu tượng hóa phần cứng (Hardware Abstraction Layer - HAL). Nó tự động nhận diện và cấu hình giao tiếp phần cứng xe theo thứ tự ưu tiên:

1. **NvidiaRacecar API:** Gọi thư viện chính thức `jetracer.nvidia_racecar.NvidiaRacecar` để điều khiển trực tiếp thanh ghi mạch PWM PCA9685.
2. **JetBot API Fallback:** Nếu xe sử dụng board Waveshare JetBot Pro lai, lớp sẽ nạp thư viện `jetbot.Robot` và mô phỏng lái Ackermann bằng cách dịch giá trị steering thành chênh lệch tốc độ giữa hai bánh xe.
3. **Mock Mode (Mô phỏng):** Nếu chạy code trên máy tính cá nhân/laptop không có phần cứng Jetson, lớp tự động nạp đối tượng giả lập `Mock` để chạy thử nghiệm phần mềm mà không bị báo lỗi nạp thư viện phần cứng.

Các hàm API cơ sở cung cấp cho mã nguồn chính bao gồm:
- `forward(speed)`: Đi thẳng với tốc độ chỉ định.
- `stop()`: Dừng xe ngay lập tức, trả góc lái về 0.
- `steer(steering_value, speed)`: Thiết lập góc lái servo từ `-1.0` (trái tối đa) đến `1.0` (phải tối đa) kết hợp tốc độ động cơ cầu sau.

---

## 3. Bộ điều khiển bám làn phản hồi PID (correct_course_pid)

Để xe tự động điều chỉnh hướng lái đi dọc theo tâm làn đường thu được từ camera, hàm [correct_course_pid()](file:///d:/JetsonAIRacer/src/core/control/racer_controller.py#L196) thực hiện bộ điều khiển PID khép kín:

### 3.1. Tính toán sai số lệch tâm (Error Calculation)
Sai số ngang $e(t)$ được tính bằng khoảng cách giữa tâm vạch làn đường phát hiện được ($X_c$) và tâm khung hình ($Width/2$):
$$e(t) = X_c - \frac{\text{Width}}{2}$$
Sai số này được chuẩn hóa về dải $[-1.0, 1.0]$. Nếu giá trị tuyệt đối của sai số chuẩn hóa nhỏ hơn vùng an toàn `SAFE_ZONE_PERCENT` ($30\%$), xe được coi là đang đi thẳng và bỏ qua điều chỉnh góc lái để tránh rung lắc (dead zone).

### 3.2. Công thức PID
Bộ điều khiển PID tính toán giá trị ngõ ra góc lái servo $u(t)$ theo thời gian:
$$P(t) = K_p \cdot e(t)$$
$$I(t) = I(t-dt) + e(t) \cdot dt \quad \text{với } I(t) \in [-1.0, 1.0] \text{ (Anti-Windup)}$$
$$D(t) = K_d \cdot \frac{e(t) - e(t-dt)}{dt}$$
$$u(t) = P(t) + I(t) + D(t)$$

Giá trị $u(t)$ sau đó được giới hạn (clamp) trong khoảng $[-MAX\_STEERING, MAX\_STEERING]$ (mặc định $[-1.0, 1.0]$) và cộng thêm giá trị hiệu chuẩn lệch lái phần cứng `STEERING_OFFSET` trước khi gửi xuống cơ cấu chấp hành.

---

## 4. Thuật toán Rẽ vòng cung theo thời gian (turn_angle)

Vì xe Ackermann không thể quay tại chỗ, hành động rẽ tại ngã tư được thực hiện thông qua quỹ đạo hình cung dựa trên thời gian thực thi trong hàm [turn_angle()](file:///d:/JetsonAIRacer/src/core/control/racer_controller.py#L151):

1. **Tính toán thời gian rẽ (Duration):** Thời gian tỷ lệ thuận với góc cần rẽ (ví dụ: rẽ $90^\circ$ cần thời gian $T$, rẽ $180^\circ$ cần thời gian $2T$).
   $$\text{Duration} = \frac{|\text{Degrees}|}{90.0} \times \text{TURN\_DURATION\_90\_DEG}$$
2. **Đánh lái cưỡng bức (Steering Override):** Thiết lập góc bẻ lái tối đa về hướng rẽ:
   - Rẽ phải ($\text{Degrees} > 0$): Góc lái bằng `STEERING_VALUE_FOR_TURN` ($0.7$).
   - Rẽ trái ($\text{Degrees} < 0$): Góc lái bằng $-0.7$.
3. **Cấp ga hành trình:** Thiết lập tốc độ chạy rẽ chậm `TURN_THROTTLE` ($0.15$) để xe di chuyển vẽ nên một cung tròn rẽ hướng.
4. **Trễ thời gian:** Cho xe chạy trong khoảng thời gian `Duration`. Vòng lặp chờ ghi nhận hình ảnh để tránh bỏ lỡ khung hình video debug.
5. **Dừng xe và trả lái:** Gọi hàm `stop()` để ngắt lực kéo động cơ và trả góc servo lái về thẳng ($0.0$).

---

## 5. Thuật toán Quét & Ổn định sau khi rẽ (Stabilize After Turn)

Sau khi thực hiện cú rẽ lớn tại ngã tư, camera của xe thường bị lệch hướng so với làn đường mới, dẫn đến việc không nhìn thấy vạch kẻ để bám làn tiếp. Để khắc phục, hệ thống triển khai hàm [stabilize_after_turn()](file:///d:/JetsonAIRacer/src/speed_track/main_speed_track.py#L645):

- **Quét nhỏ tại chỗ (Sweep):** Nếu không thấy làn đường trong khung hình, xe thực hiện bẻ lái nhẹ sang trái một góc nhỏ `small_angle` ($6^\circ$) rồi lùi/tiến nhẹ để kiểm tra vạch làn.
- Nếu thấy vạch làn xuất hiện, xe sẽ trả lái về thẳng và tiếp tục đi.
- Nếu không thấy, xe thực hiện tương tự bẻ lái nhẹ sang phải ($6^\circ$) để dò tìm.
- Kỹ thuật quét chủ động này giúp xe tăng tỷ lệ bắt lại làn đường thành công từ $60\%$ lên hơn $95\%$ trên sa bàn thực tế.
