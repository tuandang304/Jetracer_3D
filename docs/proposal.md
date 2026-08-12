# ĐỀ CƯƠNG NGHIÊN CỨU: GIẢI PHÁP TỰ HÀNH TỐI ƯU HÓA TRÊN THIẾT BỊ NHÚNG CHO XE JETRACER TRONG BÀI THI TỐC ĐỘ VÀ ĐÔ THỊ THÔNG MINH

**Tên dự án:** Hệ thống tự hành thời gian thực tích hợp học sâu và điều khiển thích ứng trên nền tảng NVIDIA Jetson Nano
**Đối tượng áp dụng:** Cuộc thi Jetson AI Racer Challenge 2026
**Tên đội đề xuất:** AlphaRacer

---

## Tóm tắt đề tài (Abstract)
Đề tài nghiên cứu này đề xuất một giải pháp phần mềm tự hành toàn diện cho xe mô hình JetRacer trong khuôn khổ cuộc thi *Jetson AI Racer Challenge 2026*. Với giới hạn phần cứng nghiêm ngặt của bộ vi xử lý NVIDIA Jetson Nano (4GB LPDDR4, GPU 128-core Maxwell), việc cân bằng giữa độ chính xác nhận diện và tốc độ xử lý thời gian thực là thách thức cốt lõi. Giải pháp đề xuất xây dựng một kiến trúc mô-đun hóa tối ưu: Mô-đun Nhận thức (Perception) sử dụng mạng CNN rút gọn (ResNet-18 cải tiến) cho nhiệm vụ bám làn đường (behavioral cloning) kết hợp thuật toán nhận diện vật thể YOLOv8-nano cho các biển báo giao thông và đèn tín hiệu; cả hai mô hình học sâu này đều được tối ưu hóa thông qua thư viện NVIDIA TensorRT ở định dạng FP16. Mô-đun Quyết định (Decision) sử dụng máy trạng thái hữu hạn (Finite State Machine - FSM) tích hợp bộ lọc thời gian để đưa ra các quyết định điều hướng ổn định tại các giao lộ. Mô-đun Điều khiển (Control) áp dụng bộ điều khiển PID thích ứng nhằm tinh chỉnh góc lái và tốc độ hành trình. Kết quả thực nghiệm mô phỏng và trên sa bàn thực tế kỳ vọng hệ thống đạt tần suất xử lý tối thiểu $25\text{ FPS}$ (trễ điều khiển dưới $40\text{ ms}$), độ chính xác nhận diện biển báo mAP@0.5 đạt trên $93\%$, đảm bảo xe hoàn thành xuất sắc cả hai bài thi Speed Track và Smart City.

---

## 1. Giới thiệu bài toán & Lý do chọn đề tài (Introduction & Motivation)

Hệ thống xe tự hành (Autonomous Vehicles - AV) đã và đang phát triển mạnh mẽ từ quy mô nghiên cứu đến ứng dụng thực tiễn công nghiệp. Trong môi trường học thuật và các cuộc thi công nghệ như *Jetson AI Racer Challenge 2026*, việc triển khai thuật toán tự hành trên các xe đua mô hình tỷ lệ thu nhỏ (như NVIDIA JetRacer AI Kit) mang lại một sân chơi thực tế đầy thách thức, yêu cầu các kỹ sư phải giải quyết các bài toán kỹ thuật từ thu thập dữ liệu, huấn luyện mô hình học sâu, đến tối ưu hóa mã nguồn trên các thiết bị nhúng giới hạn tài nguyên.

Nội dung chuyên môn của cuộc thi đặt ra hai bài toán riêng biệt nhưng có mối liên kết chặt chẽ:
1. **Bài thi Tốc độ (Speed Track):** Yêu cầu xe bám làn (lane keeping) ổn định ở dải tốc độ cao, vượt qua các điểm kiểm tra (checkpoint) theo đúng thứ tự và tránh các chướng ngại vật tĩnh hoặc động trên đường đua.
2. **Bài thi Đô thị Thông minh (Smart City):** Yêu cầu xe nhận diện chính xác các loại biển báo lệnh (rẽ trái, rẽ phải, đi thẳng), biển báo cấm (cấm rẽ), và trạng thái đèn tín hiệu giao thông (xanh, đỏ) tại các giao lộ, từ đó ra quyết định điều hướng hành trình thông minh để về đích an toàn với độ trễ xử lý $\le 300\text{ ms}$.

Thách thức kỹ thuật lớn nhất nằm ở thiết bị phần cứng xử lý nhúng được trang bị trên xe: **NVIDIA Jetson Nano**. Với GPU kiến trúc Maxwell 128 nhân và CPU ARM A57 4 nhân, việc chạy đồng thời mô hình bám làn và mô hình phát hiện vật thể học sâu rất dễ dẫn đến tình trạng quá tải tài nguyên (out of memory), giảm tốc độ khung hình dưới mức an toàn ($< 10\text{ FPS}$), gây trễ điều khiển lớn và trực tiếp dẫn đến các lỗi nghiêm trọng như lệch làn hoặc va chạm chướng ngại vật. Do đó, việc xây dựng và tối ưu hóa hệ thống phần mềm nhúng thời gian thực để đạt hiệu suất cao là cực kỳ cần thiết. Nghiên cứu này tập trung đề xuất và hiện thực hóa kiến trúc phần mềm tích hợp TensorRT cùng các thuật toán điều khiển thích ứng để giải quyết triệt để các hạn chế trên.

---

## 2. Phát biểu vấn đề & Câu hỏi nghiên cứu (Problem Statement & Research Questions)

### 2.1. Phát biểu vấn đề
Thiết kế một hệ thống điều khiển tự động hoàn toàn (Autonomous Control System) cho xe JetRacer, sử dụng dữ liệu đầu vào duy nhất từ camera góc rộng phía trước nhằm:
* Thực hiện bám làn ổn định với tốc độ tối đa, không để xảy ra trường hợp hai bánh xe cùng một bên vượt ra ngoài mép làn (lỗi lệch làn bị phạt $-10$ điểm/lần và cộng $+15$ giây vào tổng thời gian hoàn thành).
* Tránh các vật cản trên đường mà không va chạm (lỗi va chạm bị phạt $-5$ điểm/lần và cộng $+10$ giây).
* Nhận diện và thực thi đúng hiệu lệnh từ các loại biển báo và đèn tín hiệu tại giao lộ với thời gian trễ xử lý tổng thể $\le 300\text{ ms}$. Chạy quá đèn đỏ sẽ bị hủy lượt chạy ngay lập tức.
* Đạt tần suất xử lý điều khiển toàn chu kỳ $\ge 20\text{ FPS}$ để nhận điểm cộng hiệu năng tối đa ($+10$ điểm).

### 2.2. Câu hỏi nghiên cứu
Để hiện thực hóa mục tiêu trên, đề cương tập trung trả lời ba câu hỏi nghiên cứu (Research Questions - RQ) sau:
* **RQ1:** Làm thế nào để cấu trúc và tối ưu hóa đồng thời mô hình bám làn và mô hình nhận diện vật thể trên GPU Jetson Nano để đảm bảo tốc độ suy luận dưới $30\text{ ms}$ (đạt trên $25\text{ FPS}$) mà không làm giảm đáng kể độ chính xác?
* **RQ2:** Chiến lược tăng cường dữ liệu (data augmentation) và tiền xử lý hình ảnh nào giúp mô hình bám làn đường dạng hồi quy (behavioral cloning) thích ứng tốt với sự thay đổi của điều kiện ánh sáng và hiện tượng phản xạ/bóng đổ trên sa bàn thực tế?
* **RQ3:** Làm thế nào để thiết kế bộ logic quyết định (Decision Logic) bền vững với nhiễu phát hiện (noise/false negatives) tức thời của cảm biến (ví dụ: biển báo bị che khuất hoặc mất dấu trong 1-2 khung hình do rung lắc camera)?

---

## 3. Nghiên Cứu Liên Quan (Related Work)

### 3.1. Thuật toán bám làn đường (Lane Following)
Trong các nghiên cứu về xe tự hành, bám làn đường thường được tiếp cận theo hai hướng chính:
* **Phương pháp thị giác truyền thống:** Sử dụng các bộ lọc màu (HSV), phát hiện cạnh Canny, phép biến đổi Perspective Transform (Bird's Eye View) và khớp đường cong đa thức (Polynomial Fitting) [3]. Phương pháp này tính toán nhanh nhưng cực kỳ nhạy cảm với điều kiện ánh sáng thay đổi và không thể áp dụng khi vạch làn đường bị mờ hoặc bị chướng ngại vật che khuất.
* **Học máy đầu cuối (End-to-End Deep Learning):** Được tiên phong bởi mô hình PilotNet của NVIDIA [1], bản chất là huấn luyện một mạng nơ-ron tích chập (CNN) ánh xạ trực tiếp từ hình ảnh camera đến góc lái (steering angle) thông qua phương pháp Behavioral Cloning (Học bắt chước). Mặc dù hoạt động rất tốt trong các môi trường phức tạp và không cần trích xuất tính năng thủ công, phương pháp này đòi hỏi tập dữ liệu đa dạng để tránh hiện tượng quá khớp (overfitting). Nghiên cứu của chúng tôi kế thừa kiến trúc ResNet-18 [2] làm mạng xương sống (backbone) cho mô hình bám làn nhờ khả năng trích xuất đặc trưng không gian vượt trội của các khối dư (residual blocks).

### 3.2. Nhận diện biển báo và đèn tín hiệu (Traffic Sign & Light Detection)
Đối với bài toán phát hiện vật thể nhỏ trong thời gian thực trên thiết bị biên, các kiến trúc thuộc họ YOLO (You Only Look Once) và SSD (Single Shot MultiBox Detector) thường được cân nhắc. 
* SSD-MobileNet có tốc độ nhanh nhưng độ chính xác suy giảm mạnh khi đối tượng nằm ở khoảng cách xa (khi xe chuẩn bị tiến vào giao lộ).
* **YOLOv8-nano (YOLOv8n)** [4] là phiên bản mới nhất của dòng YOLO được tối ưu hóa cho thiết bị di động/nhúng, loại bỏ cơ chế anchor-based cũ (chuyển sang anchor-free) giúp giảm đáng kể số lượng tham số huấn luyện, đồng thời cải thiện đáng kể độ chính xác phân loại và định vị vật thể nhỏ.

### 3.3. Tối ưu hóa phần cứng trên thiết bị nhúng (Hardware Optimization)
Đoạn mã PyTorch gốc khi chạy trực tiếp trên GPU Maxwell của Jetson Nano thông qua CUDA thường chỉ đạt hiệu năng thấp ($5$ - $10\text{ FPS}$) do kiến trúc nhân Maxwell cũ và băng thông bộ nhớ hạn chế. Sử dụng thư viện **NVIDIA TensorRT** [5] cho phép tối ưu hóa đồ thị tính toán của mô hình bằng cách gộp các lớp (layer fusion), tối ưu hóa bộ nhớ đệm, và chuyển đổi kiểu dữ liệu từ FP32 sang FP16 (FP16 quantization). Điều này giúp tăng tốc độ xử lý từ $3$ đến $5$ lần mà độ suy giảm độ chính xác là không đáng kể, đáp ứng hoàn toàn điều kiện thời gian thực.

---

## 4. Phương Pháp Đề Xuất (Proposed Method)

### 4.1. Kiến trúc hệ thống tổng quát (System Architecture)
Chúng tôi đề xuất một kiến trúc hệ thống dạng mô-đun phân tầng để đảm bảo tính độc lập và dễ dàng tối ưu hóa từng thành phần. Sơ đồ khối hoạt động của hệ thống được mô tả như dưới đây:

```
                  ┌──────────────────────────────┐
                  │      CSI/USB Camera          │
                  └──────────────┬───────────────┘
                                 │ Frame (640x480)
                                 ▼
Perception        ┌──────────────────────────────┐
Layer             │       Image Preprocessing    │
                  └──────┬────────────────┬──────┘
                         │                │
                         ▼ (Resized)      ▼ (Resized)
                  ┌──────────────┐ ┌──────────────┐
                  │   LaneNet    │ │   SignNet    │
                  │ (ResNet-18)  │ │  (YOLOv8n)  │
                  └──────┬───────┘ └──────┬───────┘
                         │ Target (x,y)   │ Class, BBox, Conf
                         ▼            ┌───▼───────────┐
                         │            │ Filter &      │
                         │            │ Hysteresis    │
                         │            └───┬───────────┘
                         │                │ Tracked Objects
                         ▼                ▼
Decision          ┌──────────────────────────────┐
Layer             │    Finite State Machine      │
                  │     (FSM Decision Core)      │
                  └──────────────┬───────────────┘
                                 │ Control States & Modifiers
                                 ▼
Control           ┌──────────────────────────────┐
Layer             │ Adaptive PID Controllers     │
                  └──────────────┬───────────────┘
                                 │ Steering Angle & Throttle
                                 ▼
                  ┌──────────────────────────────┐
                  │      JetRacer Actuators      │
                  └──────────────────────────────┘
```

### 4.2. Mô-đun Nhận thức (Perception Module)

#### 4.2.1. Nhận diện làn đường (LaneNet)
Chúng tôi sử dụng một mạng tích chập dựa trên kiến trúc ResNet-18 cải tiến làm nền tảng. Đầu ra của mô hình không phải là góc lái trực tiếp (để tránh sự phụ thuộc quá lớn vào tốc độ xe tại thời điểm thu thập dữ liệu), mà là **tọa độ điểm đích tiếp theo $(x, y)$** nằm trên đường tâm của làn đường phía trước xe.
* **Đầu vào:** Hình ảnh từ camera góc rộng được cắt lấy Vùng quan tâm (Region of Interest - ROI) loại bỏ phần hậu cảnh nhiễu phía trên đường chân trời, sau đó giảm độ phân giải xuống kích thước $224 \times 224$ pixel.
* **Hàm mất mát (Loss Function):** Sử dụng sai số bình phương trung bình (Mean Squared Error - MSE) để tối ưu hóa tọa độ dự báo:
$$\mathcal{L}_{lane} = \frac{1}{N} \sum_{i=1}^{N} \left[ (x_i - \hat{x}_i)^2 + (y_i - \hat{y}_i)^2 \right]$$
Trong đó $(x_i, y_i)$ là tọa độ nhãn thực tế của tâm làn đường và $(\hat{x}_i, \hat{y}_i)$ là tọa độ dự báo từ mô hình.
* **Tối ưu hóa:** Mô hình được xuất sang định dạng ONNX, sau đó biên dịch bằng TensorRT sang tệp Engine chạy ở độ chính xác FP16 trực tiếp trên GPU.

#### 4.2.2. Nhận diện biển báo và đèn tín hiệu (SignNet)
Sử dụng mô hình YOLOv8-nano được huấn luyện trên tập dữ liệu gồm 6 lớp đối tượng cụ thể:
1. `TurnLeft` (Biển chỉ dẫn bắt buộc rẽ trái).
2. `TurnRight` (Biển chỉ dẫn bắt buộc rẽ phải).
3. `GoStraight` (Biển chỉ dẫn bắt buộc đi thẳng).
4. `Prohibited` (Biển cấm).
5. `RedLight` (Đèn giao thông đỏ).
6. `GreenLight` (Đèn giao thông xanh).

Hình ảnh đầu vào có kích thước $320 \times 320$ pixel để đảm bảo nhận diện tốt các biển báo kích thước nhỏ ở xa. Mô hình YOLOv8n cũng được biên dịch thông qua TensorRT FP16 nhằm tối giản hóa thời gian trễ suy luận xuống mức $\le 20\text{ ms}$.

### 4.3. Mô-đun Quyết định (Decision Module)
Để hệ thống hoạt động ổn định trước các lỗi nhận diện tức thời (ví dụ: YOLOv8 bị mất dấu đèn đỏ trong 1 khung hình do xe đi qua gờ giảm chấn gây rung camera), Mô-đun Quyết định triển khai một **Bộ lọc Hysteresis thời gian** kết hợp **Máy trạng thái hữu hạn (FSM)**.

#### 4.3.1. Bộ lọc nhiễu tín hiệu nhận diện
Một biển báo hoặc đèn tín hiệu chỉ được xác nhận thay đổi trạng thái khi và chỉ khi kết quả nhận diện của nó đồng nhất trong ít nhất $k$ khung hình liên tiếp ($k = 3$ đối với điều kiện hoạt động ở mức $25\text{ FPS}$).
$$S_{filtered}(t) = \begin{cases} S(t) & \text{nếu } S(t) = S(t-1) = \dots = S(t-k+1) \\ S_{filtered}(t-1) & \text{ngược lại} \end{cases}$$

#### 4.3.2. Thiết kế các trạng thái trong FSM
FSM bao gồm các trạng thái chính và điều kiện chuyển trạng thái được mô tả chi tiết trong Bảng 1:

**Bảng 1: Các trạng thái hoạt động của FSM điều khiển**

| Tên trạng thái | Mô tả hành vi | Điều kiện chuyển trạng thái |
| :--- | :--- | :--- |
| `LANE_FOLLOW` | Xe bám làn tự động dựa trên đầu ra của LaneNet với tốc độ cơ sở cao. Đây là trạng thái mặc định của xe. | Phát hiện biển báo/vật cản gần hoặc đèn đỏ tại giao lộ. |
| `OBSTACLE_AVOID` | Xe lệch làn tạm thời theo quỹ đạo vòng tránh chướng ngại vật định sẵn, sau đó nhanh chóng quay lại tâm làn. | Phát hiện vật cản có khoảng cách $< D_{safe}$; Trở lại `LANE_FOLLOW` khi xe đã vượt qua vật cản. |
| `TRAFFIC_LIGHT_STOP`| Xe giảm tốc độ và dừng hẳn trước vạch dừng giao lộ khi phát hiện tín hiệu đèn đỏ. | Phát hiện `RedLight` ổn định; Chuyển sang `LANE_FOLLOW` khi xuất hiện tín hiệu `GreenLight`. |
| `INTERSECTION_TURN` | Xe áp dụng góc lái cưỡng bức (steering override bias) tương ứng với biển báo lệnh nhận được để đi qua giao lộ. | Phát hiện biển báo lệnh tại giao lộ; Trở lại `LANE_FOLLOW` khi xe đã vượt qua giao lộ thành công. |

### 4.4. Mô-đun Điều khiển (Control Module)

#### 4.4.1. Điều khiển góc lái (Steering Control)
Góc lái của xe được tính toán thông qua một bộ điều khiển PID (Proportional-Integral-Derivative) dựa trên sai số lệch ngang $e_x(t)$ giữa tọa độ điểm đích $x_{pred}$ và vị trí trung tâm camera $x_{center}$:
$$e_x(t) = x_{pred}(t) - x_{center}$$
Tín hiệu điều khiển góc lái $u_{steer}(t)$ được xác định bởi:
$$u_{steer}(t) = K_p e_x(t) + K_i \int_{0}^{t} e_x(\tau) d\tau + K_d \frac{de_x(t)}{dt}$$
Trong đó các tham số $K_p$, $K_i$, $K_d$ sẽ được tinh chỉnh thực nghiệm trên sa bàn để triệt tiêu hiện tượng dao động (overshoot) khi xe đi vào cua gấp.

#### 4.4.2. Điều khiển tốc độ (Adaptive Throttle)
Để hạn chế việc mất kiểm soát lái ở các đoạn cua hoặc va chạm mạnh khi phanh gấp, tốc độ xe được điều chỉnh thích ứng theo góc lái hiện tại và khoảng cách tới chướng ngại vật $D_{obstacle}$:
$$u_{throttle}(t) = v_{base} \cdot \left(1 - \alpha \cdot |u_{steer}(t)|\right) - \beta \cdot \frac{1}{D_{obstacle}(t)}$$
Trong đó:
* $v_{base}$ là tốc độ cơ sở thiết lập cho đoạn đường thẳng.
* $\alpha$ là hệ số giảm tốc khi ôm cua ($\alpha \approx 0.4$).
* $\beta$ là hệ số phanh khi tiếp cận chướng ngại vật hoặc vạch dừng giao lộ.

---

## 5. Kế Hoạch Thực Nghiệm & Phân Tích Dữ Liệu (Experimental Plan)

### 5.1. Thu thập dữ liệu và Tăng cường dữ liệu (Data Augmentation)
Tập dữ liệu huấn luyện sẽ được thu thập trực tiếp bằng cách điều khiển xe chạy thủ công qua nhiều vòng sa bàn dưới các điều kiện chiếu sáng khác nhau (bật/tắt đèn phòng, chiếu sáng cục bộ để tạo bóng đổ giả lập).
* **Tập dữ liệu bám làn:** Khoảng $5,000$ ảnh camera tương ứng với nhãn là tọa độ trung tâm làn đường. Áp dụng các kỹ thuật tăng cường ảnh: thay đổi ngẫu nhiên độ sáng (random brightness), độ tương phản (random contrast), nhiễu Gauss, và tạo mặt nạ bóng đổ giả lập (synthetic shadow masking) để tăng khả năng chống nhiễu của LaneNet.
* **Tập dữ liệu nhận diện biển báo/đèn:** Khoảng $3,000$ ảnh sa bàn đô thị được gán nhãn khung bao (bounding box) bằng công cụ LabelImg hoặc Roboflow. Sử dụng phương pháp Mosaic và Mixup để tăng cường nhận diện các biển báo kích thước nhỏ.

### 5.2. Chỉ số đánh giá hiệu năng (Evaluation Metrics)
Chúng tôi đánh giá hiệu năng của hệ thống dựa trên ba nhóm chỉ số chính:
1. **Độ chính xác mô hình học sâu (Model Accuracy):**
   * Đối với LaneNet: Sai số bình phương trung bình (MSE) giữa tọa độ dự báo và thực tế trên tập kiểm thử (validation set).
   * Đối với SignNet: Chỉ số mAP@0.5 (mean Average Precision tại ngưỡng IoU = 0.5) đạt tối thiểu $93\%$.
2. **Hiệu suất tính toán của phần cứng (Hardware Benchmarks):**
   * Tần số khung hình trung bình (Average FPS) chạy trên Jetson Nano.
   * Thời gian trễ suy luận trung bình (Inference Latency) của từng mô hình và tổng thời gian chu kỳ điều khiển (Control Loop Latency). Mục tiêu tổng thời gian xử lý toàn chu kỳ $< 40\text{ ms}$ (tương đương $> 25\text{ FPS}$).
3. **Hiệu quả vận hành sa bàn thực tế (Race Performance):**
   * Số lần lệch làn đường trung bình trên mỗi lượt chạy (yêu cầu = 0).
   * Số lần va chạm chướng ngại vật (yêu cầu = 0).
   * Thời gian hoàn thành 1 vòng đua (lap time) tối ưu nhất.

### 5.3. Thiết kế ghi nhận nhật ký vận hành (Logging Strategy)
Hệ thống phần mềm tự hành sẽ tích hợp mô-đun ghi log tự động ghi lại dữ liệu vận hành thời gian thực ra tệp cấu trúc `.csv`/`.txt` phục vụ cho việc gỡ lỗi (debug) và hậu phân tích dữ liệu thực nghiệm theo khuyến nghị từ đề bài của Ban tổ chức. Cấu trúc một dòng log mẫu được quy định cụ thể như sau:

**Bảng 2: Cấu trúc tệp nhật ký vận hành (System Log)**

| Thuộc tính (Attribute) | Kiểu dữ liệu | Ý nghĩa và Ví dụ |
| :--- | :--- | :--- |
| `timestamp` | Float | Thời gian hệ thống ghi nhận sự kiện (đơn vị: giây epoch). Ví dụ: `17856345.123` |
| `fps` | Float | Tốc độ xử lý khung hình hiện tại của chu kỳ điều khiển. Ví dụ: `26.4` |
| `detected_object` | String | Nhãn vật thể/biển báo/đèn tín hiệu nhận diện được. Ví dụ: `TurnLeft` hoặc `None` |
| `confidence` | Float | Độ tin cậy của mô hình nhận diện vật thể (0.0 - 1.0). Ví dụ: `0.92` |
| `decision` | String | Trạng thái quyết định của FSM. Ví dụ: `INTERSECTION_TURN` |
| `latency_ms` | Float | Thời gian xử lý trọn vẹn 1 khung hình (đơn vị: ms). Ví dụ: `34.5` |
| `control_output` | List | Lệnh điều khiển gửi đến động cơ dạng `[steering, throttle]`. Ví dụ: `[-0.35, 0.5]` |
| `event` | String | Sự kiện đặc biệt được kích hoạt. Ví dụ: `PASS_CHECKPOINT_1`, `COLLISION`, `LAP_COMPLETED` |

---

## 6. Kế Hoạch Triển Khai & Quản Trị Rủi Ro (Implementation & Risks)

### 6.1. Kế hoạch triển khai (Implementation Roadmap)
Tiến độ thực hiện dự án dự kiến diễn ra trong vòng 8 tuần trước ngày thi đấu chính thức, được phân chia cụ thể như sau:
* **Tuần 1 - 2 (Thiết kế & Thu thập dữ liệu):** Thiết lập môi trường phát triển trên máy tính trạm và Jetson Nano. Thiết kế sa bàn giả lập và tiến hành thu thập hình ảnh làn đường, biển báo. Gán nhãn dữ liệu thủ công.
* **Tuần 3 - 4 (Huấn luyện & Tối ưu hóa mô hình):** Huấn luyện mô hình LaneNet (ResNet-18) và SignNet (YOLOv8n) trên máy tính trạm có GPU mạnh. Chuyển đổi mô hình sang định dạng TensorRT FP16 và thực hiện đo đạc kiểm thử tốc độ suy luận trực tiếp trên Jetson Nano.
* **Tuần 5 - 6 (Phát triển FSM & Điều khiển):** Lập trình logic FSM, thiết lập bộ lọc Hysteresis và bộ điều khiển góc lái/tốc độ PID. Kiểm thử chạy giả lập trên mô hình ảo để đảm bảo tính đúng đắn của logic quyết định.
* **Tuần 7 (Tích hợp hệ thống & Tinh chỉnh thực tế):** Lắp đặt phần mềm lên xe chạy thực tế trên sa bàn mẫu của Ban tổ chức. Tinh chỉnh các hệ số PID lái và ga thích ứng để xe chạy mượt mà, ôm cua tối ưu mà không lệch làn.
* **Tuần 8 (Đánh giá & Hoàn thiện tài liệu):** Chạy thực nghiệm liên tục để đo đạc chỉ số FPS, trễ hệ thống, ghi nhận logs và hoàn thiện Technical Paper nộp cho Ban tổ chức.

### 6.2. Đánh giá rủi ro và Phương án dự phòng (Risk Management)

Trong quá trình triển khai thực tế trên phần cứng thiết bị nhúng Jetson Nano, chúng tôi dự báo một số rủi ro kỹ thuật chính và đề xuất các giải pháp khắc phục tương ứng:

1. **Rủi ro 1: Hiện tượng giảm hiệu năng do quá nhiệt (Thermal Throttling) của Jetson Nano.**
   * *Ảnh hưởng:* Khi chạy tải cao liên tục trong lượt thi 5 phút, nhiệt độ chip vượt quá $75^\circ\text{C}$ sẽ kích hoạt cơ chế tự bảo vệ của phần cứng, giảm xung nhịp CPU/GPU dẫn đến tốc độ khung hình tụt dốc ($< 10\text{ FPS}$).
   * *Phương án giải quyết:* Cấu hình quạt tản nhiệt của xe chạy ở công suất tối đa bằng lệnh hệ thống `sudo jetson_clocks --fan 255` ngay trước khi xuất phát. Tối giản hóa mô hình học sâu thông qua TensorRT để giảm thiểu số lượng phép tính toán của GPU.
2. **Rủi ro 2: Nhận diện sai lệch biển báo do thay đổi ánh sáng đột ngột trên sa bàn thực tế.**
   * *Ảnh hưởng:* Ánh sáng phòng thi có cường độ khác biệt hoặc có bóng đổ của người điều khiển/khán giả che khuất biển báo làm giảm độ tin cậy nhận diện của YOLOv8n xuống dưới ngưỡng kích hoạt FSM.
   * *Phương án giải quyết:* Sử dụng phương pháp tăng cường dữ liệu domain randomization (biến đổi mạnh màu sắc HSV, độ sáng, tương phản giả lập) trong quá trình huấn luyện mô hình. Đồng thời áp dụng bộ lọc Hysteresis thời gian để duy trì trạng thái nhận diện trước đó khi đối tượng bị mất dấu tạm thời trong 1-2 khung hình.
3. **Rủi ro 3: Trễ suy luận của YOLOv8n làm chậm nhịp phản hồi điều khiển bám làn.**
   * *Ảnh hưởng:* Do YOLOv8n chạy nặng hơn mô hình bám làn, nếu lập trình tuần tự (single-thread), xe sẽ phải đợi YOLO chạy xong mới điều khiển góc lái, gây ra trễ chu kỳ điều khiển lớn dẫn đến lệch làn ở tốc độ cao.
   * *Phương án giải quyết:* Triển khai lập trình đa luồng (Multi-threading). Luồng điều khiển bám làn và đọc camera chạy ở tần số cao độc lập ($30\text{ Hz}$), luồng chạy YOLOv8n nhận diện biển báo chạy ở tần số thấp hơn ($15\text{ - }20\text{ Hz}$) gửi tín hiệu trạng thái gián tiếp qua biến dùng chung (shared variable) được bảo vệ bằng cơ chế khóa (Mutex/Lock).

---

## 7. Kết Quả Kỳ Vọng & Giới Hạn Đề Tài (Expected Outcomes & Limitations)

### 7.1. Kết quả kỳ vọng
* **Tần số hoạt động hệ thống:** Chu kỳ điều khiển toàn hệ thống chạy ổn định ở tần số $\ge 25\text{ FPS}$ trên Jetson Nano.
* **Thời gian xử lý trễ:** Thời gian từ lúc camera ghi nhận hình ảnh đến khi gửi xung điều khiển bánh lái (PWM) xuống bộ điều khiển động cơ đạt $\le 40\text{ ms}$, đáp ứng hoàn hảo yêu cầu an toàn thời gian thực.
* **Tỷ lệ hoàn thành lượt chạy:** Đạt tỷ lệ $100\%$ hoàn thành hợp lệ các vòng thi Speed Track và đi đúng lộ trình bài thi Smart City trong quá trình chạy thử nghiệm 10 lượt liên tục.
* **Độ chính xác nhận diện:** Chỉ số mAP@0.5 đối với nhận diện biển báo đạt tối thiểu $93\%$, thời gian đưa ra quyết định tại giao lộ $\le 50\text{ ms}$ từ khi phát hiện biển báo rõ ràng.

### 7.2. Giới hạn đề tài
* Hệ thống phụ thuộc lớn vào chất lượng camera và sự ổn định của vạch làn đường trên sa bàn. Nếu vạch làn bị mờ nặng hoặc bị rách lớn trên khoảng cách dài vượt quá tầm dự báo của LaneNet ($> 30\text{ cm}$), hệ thống bám làn có thể hoạt động không chính xác.
* Mô hình nhận diện biển báo được huấn luyện dựa trên cấu trúc hình học và màu sắc đặc trưng của bộ biển báo chuẩn của Ban tổ chức. Nếu Ban tổ chức thay đổi thiết kế biển báo nằm ngoài tập dữ liệu huấn luyện mà không thông báo trước, độ chính xác nhận diện sẽ bị ảnh hưởng nghiêm trọng.

---

## 8. Tài Liệu Tham Khảo (References)

[1] Bojarski, M., Del Testa, D., Dworakowski, D., Firner, B., Flepp, B., Goyal, P., Jackel, L. D., Monfort, M., Muller, U., Zhang, J., & others. (2016). End to end learning for self-driving cars. *arXiv preprint arXiv:1604.07316*.

[2] He, K., Zhang, X., Ren, S., & Sun, J. (2016). Deep residual learning for image recognition. In *Proceedings of the IEEE conference on computer vision and pattern recognition* (pp. 770-778).

[3] Åström, K. J., & Hägglund, T. (2006). *Advanced PID Control*. Research Triangle Park, NC: ISA - The Instrumentation, Systems, and Automation Society. ISBN: 978-1-55617-942-6.

[4] Jocher, G., Chaurasia, A., & Qiu, J. (2023). *Ultralytics YOLOv8* (Version 8.0.0). [Software]. Available from: https://github.com/ultralytics/ultralytics.

[5] NVIDIA Corporation. (2025). *NVIDIA TensorRT Developer Guide: High-Performance Deep Learning Inference*. Available from: https://developer.nvidia.com/tensorrt.
