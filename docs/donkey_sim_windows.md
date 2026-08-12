# Chạy JetRacer trong Donkey Simulator trên Windows

Hướng dẫn chạy thuật toán Speed Track (`src/speed_track/main_speed_track.py`) trong
Donkey Simulator **ngay trên Windows** — không cần Ubuntu, không cần WSL, không cần
cài ROS, không cần Docker.

Cách làm: thay ROS bằng một lớp giả lập `rospy` chạy trong cùng một tiến trình, và
nói chuyện thẳng với simulator qua giao thức TCP JSON có sẵn của nó.

```
┌──────────────────┐   TCP 9091    ┌──────────────────────────────────┐
│  donkey_sim.exe  │◄─────────────►│  run_donkey_sim.py               │
│  (Unity)         │  ảnh + lệnh   │   ├─ rospy_stub  (giả lập ROS)   │
└──────────────────┘               │   ├─ donkey_client (TCP)         │
                                   │   └─ main_speed_track.py (code   │
                                   │        thi đấu, KHÔNG sửa gì)    │
                                   └──────────────────────────────────┘
```

Điểm quan trọng: **code thi đấu không bị sửa một dòng nào**. Mọi thứ dành riêng cho
sim đều nằm trong `src/sim/` và được vá lúc chạy.

---

## 1. Chuẩn bị (chỉ làm 1 lần)

### 1.1. Tải simulator

Tải bản Windows từ trang release của Donkey Sim:

- https://github.com/tawnkramer/gym-donkeycar/releases
- Chọn file **`DonkeySimWin.zip`** (bản mới nhất), giải nén ra đâu cũng được,
  ví dụ `C:\DonkeySim\`.

Đây là **thứ duy nhất** bạn cần tải thêm.

### 1.2. Thư viện Python

Máy bạn đang có Python 3.12 và đã cài đủ. Nếu chạy trên máy khác thì cần:

```powershell
pip install numpy opencv-python networkx
```

Không cần `gym`, không cần `gym-donkeycar`, không cần `rospy`. Các thư viện chỉ dùng
trên xe thật (`onnxruntime`, `pyzbar`, `paho-mqtt`, `requests`) nếu thiếu sẽ được
thay bằng bản rỗng — chương trình vẫn chạy, chỉ là không có YOLO và MQTT.

---

## 2. Chạy

### Bước 1 — Mở simulator

Chạy `donkey_sim.exe`. Để nguyên ở **màn hình menu**, không cần bấm chọn gì cả —
script sẽ tự gửi lệnh nạp sa bàn.

### Bước 2 — Chạy code

Mở PowerShell tại thư mục `C:\Users\trums\Jetracer`:

```powershell
python src/sim/run_donkey_sim.py
```

Xe sẽ tự nạp sa bàn `generated_track`, tìm vạch vàng ở tim đường và bắt đầu bám line.

Dừng bằng `Ctrl+C`.

### Xem trực tiếp ROI và tâm vạch kẻ

```powershell
python src/sim/run_donkey_sim.py --show
```

Cửa sổ hiện lên vẽ đúng những gì `draw_debug_info()` vẽ: ROI chính (xanh lá), ROI dự
báo (vàng), tâm vạch (đỏ). Nếu cửa sổ bị đơ thì bỏ `--show` và xem lại file
`sim_run.avi` sau khi chạy xong.

### Lái tay bằng WASD

Muốn tự lái để đi dạo sa bàn, xem camera nhìn thấy gì, hoặc quay video làm mẫu:

```powershell
python src/sim/manual_drive.py
```

Script này **không** dùng tới `main_speed_track.py` hay `rospy_stub` — chỉ mở kết nối
TCP tới sim và gửi lệnh lái từ bàn phím.

| Phím | Tác dụng |
|---|---|
| `W` / `S` | ga tiến / lùi (giữ phím) |
| `A` / `D` | đánh lái trái / phải, thả ra là tự trả lái về giữa |
| `SHIFT` | giữ cùng `W` để chạy nhanh hơn |
| `SPACE` | phanh, cắt ga ngay |
| `R` | reset xe về vạch xuất phát |
| `Q` / `ESC` | thoát |

Cửa sổ `JetRacer Manual Drive (WASD)` phải đang được chọn thì phím mới ăn. Trên
Windows script đọc trạng thái phím thật qua `GetAsyncKeyState`, nên **giữ** phím là xe
chạy liên tục — không bị khựng nửa giây do auto-repeat của bàn phím.

Tham số hay dùng:

```powershell
python src/sim/manual_drive.py --scene waveshare --throttle 0.6 --record lap.avi
```

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `--scene` | `generated_track` | Sa bàn muốn nạp |
| `--throttle` / `--boost` / `--reverse` | `0.45` / `0.85` / `0.35` | Ga tối đa khi giữ `W`, `SHIFT+W`, `S` |
| `--accel` / `--coast` | `1.8` / `1.2` | Tốc độ lên ga và nhả ga (đơn vị ga mỗi giây) |
| `--steer-rate` / `--center-rate` | `4.0` / `6.0` | Tốc độ đánh lái và tự trả lái |
| `--scale` | `3.0` | Phóng to khung hình (ảnh gốc từ sim chỉ 160×120) |
| `--record FILE` | tắt | Ghi cả màn hình (camera + bảng thông số) ra file `.avi` |
| `--auto-reset` | tắt | Tự reset khi va chạm, thay vì phải bấm `R` |

Bảng thông số dưới khung hình hiện `speed`, `cte` (độ lệch so với tim đường) và `hit`
lấy thẳng từ telemetry của sim — tiện để so xem xe tự lái bám line tốt tới đâu so với
lái tay.

---

## 3. Bảng tham số

| Tham số | Mặc định | Ý nghĩa |
|---|---|---|
| `--scene` | `generated_track` | Sa bàn: `generated_track`, `generated_road`, `warehouse`, `waveshare`, `roboracingleague_1`, `mini_monaco`, `warren`, `sparkfun_avc`, `circuit_launch` |
| `--line` | `white` | Màu vạch cần bám: `white`, `yellow`, `black` |
| `--throttle` | `0.35` | `BASE_THROTTLE`. Xe thật là `0.20`, nhưng sim không có ma sát nên phải cao hơn |
| `--turn-throttle` | `0.28` | `TURN_THROTTLE` |
| `--gain` | `1.0` | `STEERING_GAIN`. Xe cua chậm → tăng; xe lắc zic-zac → giảm |
| `--kp` / `--kd` | `0.6` / `0.15` | Hệ số PID |
| `--safe-zone` | `0.15` | Vùng chết giữa ảnh, xe không bẻ lái khi vạch nằm trong vùng này |
| `--intersection` | tắt | Bật lại logic giao lộ (xem mục 5) |
| `--video` | `sim_run.avi` | File video ghi lại. Mặc định **không** đụng tới `jetracer_run.avi` |
| `--verbose` | tắt | In các loại bản tin nhận từ sim, dùng khi debug kết nối |

Ví dụ tune cho xe chạy nhanh và cua gắt hơn:

```powershell
python src/sim/run_donkey_sim.py --throttle 0.45 --gain 1.3 --kd 0.2 --show
```

---

## 4. Chọn đúng màu vạch — lỗi hay gặp nhất

Xe thật bám **vạch đen** (`LINE_COLOR_UPPER = [180, 255, 75]`, tức V < 75). Mặt đường
trong sim sáng màu và không hề có vạch đen, nên `--line black` luôn cho 0 pixel.

Sa bàn `generated_track` (mặc định) có bố cục như sau, đã đo thực tế trên sim:

- **hai vạch vàng/cam ở MÉP đường** — không phải ở tim đường
- **một vạch trắng đứt quãng ở giữa**

`_get_line_center()` chỉ xét **50% chiều rộng ở giữa ảnh** (`ROI_CENTER_WIDTH_PERCENT = 0.5`)
nên hai vạch vàng nằm ở mép bị lọc sạch. Số liệu đo được ở ROI chính:

| Ngưỡng | Vùng focus 50% (mặc định) | Vùng focus 100% |
|---|---|---|
| `yellow` | **0 px — không thấy gì** | x=252 (bắt vào mép phải) |
| `white` | **x=136, area 529 — đúng vạch giữa** | x=136 |
| `black` | 0 px | 0 px |

Vì vậy sa bàn này phải dùng `--line white`. Nếu dùng `--line yellow`, log sẽ lặp vô hạn
`Đang ở trạng thái chờ... Tìm kiếm vạch kẻ đường` — xe đứng im vì không thấy vạch nào.

| Sa bàn | Nên dùng |
|---|---|
| `generated_track` | `--line white` (vạch trắng đứt quãng ở giữa) |
| `generated_road` | `--line white` |
| `warehouse` | `--line white` |
| `waveshare` | `--line white` |

Nếu xe đứng im và log lặp lại `Đang ở trạng thái chờ... Tìm kiếm vạch kẻ đường`, tức
là ngưỡng HSV chưa khớp. Chạy `--show` để nhìn xem tâm vạch (vạch đỏ) có bám đúng
không, rồi đổi `--line` sang màu khác. Muốn tự đặt ngưỡng riêng thì sửa `LINE_PRESETS`
ở đầu `src/sim/run_donkey_sim.py`.

---

## 5. Logic giao lộ bị tắt mặc định — vì sao

Sa bàn Donkey Sim là **đường đua vòng kín, không có ngã tư**, và tất nhiên không khớp
với `src/core/utils/map.json`. Trong khi đó code phát hiện giao lộ bằng hai cách:

1. **LiDAR** — tìm hai vật thể đối xứng 180°, cách xe 0.25–0.35 m
   (`src/core/utils/opposite_detector.py`). Sim không có LiDAR nên nhánh này luôn im.
2. **ROI dự báo** — nếu vạch kẻ biến mất ở phía xa thì coi là sắp tới giao lộ
   (`main_speed_track.py:384`). Trong sim, khúc cua gấp cũng làm vạch biến mất khỏi ROI
   dự báo → bị hiểu nhầm là giao lộ → xe dừng lại giữa đường đua.

Nên mặc định script vá `_get_line_center` để ROI dự báo luôn báo "vẫn thấy vạch", biến
chương trình thành **chế độ chỉ bám line**. Đây là chế độ đúng để tune PID, `STEERING_GAIN`
và ngưỡng HSV.

Muốn xem lại toàn bộ máy trạng thái (kể cả rẽ ở giao lộ) thì thêm `--intersection`,
nhưng phải hiểu là xe sẽ dừng ở khúc cua đầu tiên và đi theo `map.json` vốn không ứng
với sa bàn.

---

## 6. Những gì KHÔNG mô phỏng được

Sim chỉ dùng để tune phần **thị giác + bám line**. Các phần sau bắt buộc phải thử trên
xe thật:

- **LiDAR và phát hiện giao lộ** — không có trong sim.
- **Điều hướng theo `map.json`** — sa bàn sim không có ngã tư tương ứng.
- **Biển báo YOLO** (`models/best.onnx`) — file model không có trong repo, và sim cũng
  không dựng biển báo.
- **QR code và bài toán** — cần `pyzbar` + vật thể thật.
- **MQTT** — không có broker khi chạy sim, log sẽ báo lỗi kết nối và bỏ qua.
- **Thời gian rẽ 90°** (`TURN_DURATION_90_DEG = 1.5`) — sim không có quán tính và độ trễ
  servo như xe thật, giá trị tune trong sim **không** mang sang xe thật được.

---

## 7. Các file được thêm

| File | Vai trò |
|---|---|
| `src/sim/run_donkey_sim.py` | Script chính, chạy file này |
| `src/sim/manual_drive.py` | Lái tay bằng WASD, không đụng tới code thi đấu |
| `src/sim/donkey_client.py` | Client TCP nói chuyện với simulator |
| `src/sim/rospy_stub.py` | Giả lập `rospy`, `sensor_msgs`, `std_msgs`, `std_srvs` |

Các file này **chỉ dành cho laptop**. Trên xe thật vẫn chạy `main_speed_track.py` với
ROS Melodic thật như cũ, không đụng gì tới `src/sim/`.

`rospy_stub.py` còn xử lý hai điểm vênh giữa Windows và Jetson:

- **`cv2.findContours`**: code viết cho OpenCV 3 (trả 3 giá trị), Windows của bạn đang
  chạy OpenCV 5 (trả 2 giá trị). Stub bọc lại hàm này thay vì sửa code chính, để code
  trên xe thật giữ nguyên.
- **Console cp1252**: mọi log tiếng Việt sẽ ném `UnicodeEncodeError` và làm chết chương
  trình. Stub ép `stdout`/`stderr` sang UTF-8.

---

## 8. Lỗi thường gặp

**`Không kết nối được tới sim`**
Chưa mở `donkey_sim.exe`, hoặc sim đang mở một sa bàn khác thay vì ở menu. Đóng sim, mở
lại, để nguyên màn hình menu rồi chạy script.

**`Sim không gửi khung hình nào`**
Sai tên sa bàn. Chạy lại với `--verbose` để xem sim trả về những bản tin gì, và thử
`--scene generated_road`.

**Cổng 9091 bị chiếm**
Chỉ được mở một `donkey_sim.exe` tại một thời điểm. Kiểm tra:
```powershell
Get-NetTCPConnection -LocalPort 9091 -ErrorAction SilentlyContinue
```

**Kết nối được, thấy ảnh, tìm được vạch, nhưng xe KHÔNG di chuyển** ⚠️
Đây là lỗi đang gặp với bản sim hiện tại trên máy. Triệu chứng: log chạy bình thường,
trạng thái vào `DRIVING_STRAIGHT`, nhưng telemetry luôn trả về `"throttle": 0` và
`"speed": ~2e-07`, vị trí `pos_x/pos_z` không đổi. Đã thử và đều KHÔNG ăn thua:

- gửi `control` dạng chuỗi (đúng như `gym-donkeycar`), dạng số thực, có/không `brake`
- gửi thêm `car_config`, `cam_config`, `racer_info`, `reset_car` trước khi điều khiển
- thử ga 0.35 / 0.6 / 0.7 / 0.8 / 1.0
- thử 5 sa bàn: `generated_track`, `generated_road`, `warehouse`, `roboracingleague_1`, `waveshare`

Sim vẫn chạy đúng nhịp thời gian thực (4.95 s thời gian sim / 4.92 s thời gian thực) và
gửi ảnh đều 20 Hz, tức là nó không hề bị treo — nó chỉ bỏ qua bản tin `control`.
Nguyên nhân gần như chắc chắn nằm ở **phiên bản/chế độ của bản sim đã tải**, không phải
ở code. Xem mục cuối tài liệu.

**Xe chạy được vài giây rồi lao ra khỏi đường**
Giảm `--throttle`, tăng `--gain`. Script tự phát hiện va chạm và reset xe về vạch xuất
phát, nên cứ để chạy và quan sát.

**Xe lắc zic-zac liên tục**
Giảm `--gain` và `--kp`, tăng `--kd`, hoặc tăng `--safe-zone` lên `0.25`.

---

## 9. Vấn đề còn tồn đọng: sim không nhận lệnh điều khiển

**Trạng thái hiện tại:** toàn bộ phần ghép nối đã chạy đúng và được kiểm chứng trên sim
thật, nhưng xe không nhúc nhích vì sim bỏ qua bản tin `control`.

Những phần đã xác nhận CHẠY ĐÚNG với sim thật:

| Hạng mục | Kết quả đo |
|---|---|
| Kết nối TCP + `load_scene` | OK, nhận `car_loaded` |
| Nhận ảnh | OK, 20 khung/giây, ảnh 160×120 |
| Đồng hồ sim | OK, 4.95 s sim / 4.92 s thực |
| Phát hiện vạch kẻ (`--line white`) | OK, tâm vạch x=136 và x=142 (tâm ảnh là 150) |
| Máy trạng thái | OK, vào `DRIVING_STRAIGHT`, chạy 47 s không mất line |
| Ghi video debug | OK, 835 khung vào `sim_run.avi` |
| **Điều khiển xe** | **THẤT BẠI — echo `throttle: 0`, xe đứng im** |

Phần cần bạn kiểm tra trên màn hình sim (mình không nhìn được):

1. **Bản sim đã tải là bản nào?** Cần bản `DonkeySimWin.zip` từ
   https://github.com/tawnkramer/gym-donkeycar/releases. Một số bản build khác
   (sdsandbox tự build, bản dành cho cuộc thi) dùng giao thức khác.
2. **Trên màn hình sim đang hiện gì?** Nếu bạn đã tự bấm chọn sa bàn và chọn chế độ
   lái tay trước đó, sim sẽ ở chế độ manual và bỏ qua điều khiển qua mạng. Thử tắt hẳn
   `donkey_sim.exe`, mở lại, **để nguyên ở màn hình menu, không bấm gì**, rồi chạy script.
3. **Trong menu sim có mục nào kiểu "NN Control over Network" / "Log in" không?**
   Nếu có, cho biết tên chính xác các nút trên màn hình.

## 10. Ghi chú: bản mô phỏng cũ trong repo

Ở thư mục gốc còn sót lại một bản thử nghiệm cũ dùng `gymnasium` + `gym-donkeycar` +
shared memory, gồm: `rospy.py`, `gym-donkeycar.py`, `sensor_msgs/`, `std_msgs/`,
`std_srvs/`, `pyzbar/`.

Bản đó cần cài thêm `gymnasium` và `gym-donkeycar`, phải chạy **hai** tiến trình song
song, và `rospy.py` ở thư mục gốc sẽ **ghi đè** mọi lệnh `import rospy` khi bạn chạy
code từ thư mục gốc. `src/sim/rospy_stub.py` đã nhận biết và thay thế nó tự động, nên
hai bản không xung đột.

Nếu không dùng bản cũ nữa thì xoá các file trên cho gọn — nhưng nhớ rằng
`racer_controller.py:277` và `:300` có gọi `rospy.publish_control()`, là hàm chỉ tồn tại
trong `rospy.py` cũ (chỉ chạy khi ở chế độ mock, nên xoá vẫn an toàn).
