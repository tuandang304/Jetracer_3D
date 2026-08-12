# Tài liệu Quy trình Hoạt động & Vòng lặp chính (Pipeline & Execution Loop)

Tài liệu này đặc tả chi tiết luồng xử lý thời gian thực, bảng phân tích trạng thái FSM của xe và sự khác biệt về logic hoạt động giữa hai chế độ Speed Track và Smart City.

---

## 1. Vòng lặp Điều khiển chính (20Hz Control Loop)

Vòng lặp chạy chính nằm trong hàm `run()` của cả hai chương trình điều khiển:
- **Tần số hoạt động:** Khởi tạo thông qua `rospy.Rate(20)` tương đương thời gian chu kỳ điều khiển là $50\text{ ms}$ ($20\text{ FPS}$), đảm bảo khả năng phản hồi thời gian thực trước các sự thay đổi trên sa bàn.
- **Luồng dữ liệu:** 
  1. Camera CSI liên tục cập nhật khung hình mới vào biến `self.latest_image` thông qua callback topic `/csi_cam_0/image_raw`.
  2. Cảm biến Lidar liên tục cập nhật chùm quét vào đối tượng `SimpleOppositeDetector` thông qua topic `/scan`.
  3. Tại mỗi chu kỳ vòng lặp, hệ thống kiểm tra trạng thái hiện tại (`self.current_state`) của Máy trạng thái FSM để quyết định nhánh logic điều khiển tương ứng.
  4. Mỗi khung hình xử lý kèm thông tin debug vẽ trên ảnh sẽ được đối tượng `VideoWriter` ghi lại thành tệp video định dạng AVI phục vụ cho việc kiểm thử và hậu phân tích.

---

## 2. Đặc tả Chi tiết các Trạng thái FSM (RobotState)

FSM điều phối mọi hoạt động của xe thông qua 8 trạng thái đặc trưng với các điều kiện chuyển dịch như sau:

| Mã Trạng Thái | Tên Trạng Thái | Hành Vi Chi Tiết | Điều Kiện Chuyển Sang Trạng Thái Khác |
| :---: | :--- | :--- | :--- |
| **0** | `WAITING_FOR_LINE` | Xe đứng yên (`controller.stop()`). Liên tục quét camera để kiểm tra xem vạch kẻ đường màu đen đã xuất hiện ổn định ở cả hai vùng ROI gần và ROI xa chưa. | Chuyển sang `DRIVING_STRAIGHT` khi phát hiện thấy vạch làn đường hợp lệ ở cả hai ROI. |
| **1** | `DRIVING_STRAIGHT` | Xe chạy tiến bám làn đường bằng bộ điều khiển PID dựa trên dữ liệu ROI Chính. Trạng thái này liên tục thực hiện 3 bước kiểm tra sự kiện theo thứ tự ưu tiên giảm dần: <br>1. *Ưu tiên cao (LiDAR):* Gọi `detector.process_detection()` quét cổng chào. <br>2. *Ưu tiên trung bình (Lookahead ROI):* Kiểm tra xem làn đường ở phía xa có bị mất hay không. <br>3. *Bình thường:* Tính toán PID bám làn. | - Chuyển sang `HANDLING_EVENT` (hoặc `GOAL_REACHED` nếu là đích) nếu LiDAR phát hiện cổng giao lộ. <br>- Chuyển sang `APPROACHING_INTERSECTION` nếu làn đường ở phía xa bị mất (ROI dự báo trống). <br>- Chuyển sang `DEAD_END` nếu mất làn ở ROI chính quá lâu. |
| **2** | `APPROACHING_INTERSECTION` | Xe đi thẳng một đoạn ngắn với tốc độ cơ sở (`controller.forward()`) mà không bám làn nhằm đưa xe tiến sâu vào chính giữa ngã tư giao lộ. | Chuyển sang `HANDLING_EVENT` (hoặc `GOAL_REACHED`) sau khi hết thời gian thiết lập tiếp cận giao lộ `INTERSECTION_APPROACH_DURATION` ($0.5$ giây). |
| **3** | `HANDLING_EVENT` | Xe dừng lại hẳn tại giao lộ. Thực hiện các bước nhận diện biển báo/đèn tín hiệu, đưa ra quyết định rẽ đi tiếp, quay đầu hoặc đi thẳng, sau đó ra lệnh rẽ vòng cung cơ học. | Chuyển sang `LEAVING_INTERSECTION` sau khi hoàn thành hành động bẻ lái rẽ xe hoặc đi thẳng qua ngã tư. <br>- Chuyển sang `DEAD_END` nếu gặp lỗi kế hoạch hoặc sa bàn mâu thuẫn. |
| **4** | `LEAVING_INTERSECTION` | Xe chạy thẳng tiến ra khỏi ngã tư giao lộ để thoát khỏi khu vực nhiễu làn cũ. | Chuyển sang `REACQUIRING_LINE` sau khi chạy thẳng hết thời gian dọn đường `INTERSECTION_CLEARANCE_DURATION` ($1.5$ giây). |
| **5** | `REACQUIRING_LINE` | Xe tiếp tục chạy thẳng và liên tục kiểm tra xem camera đã bắt lại được vạch làn đường mới ở ROI Chính chưa. | - Chuyển sang `DRIVING_STRAIGHT` ngay khi bắt lại được vạch làn đường. <br>- Chuyển sang `DEAD_END` nếu quá thời gian timeout `LINE_REACQUIRE_TIMEOUT` ($3.0$ giây) vẫn không tìm thấy làn. |
| **6** | `DEAD_END` | Xe phanh dừng khẩn cấp và giải phóng toàn bộ tài nguyên hệ thống (ngắt kết nối MQTT, đóng file video ghi hình, dừng động cơ). | Kết thúc chương trình điều khiển. |
| **7** | `GOAL_REACHED` | Xe phanh dừng hoàn thành tại nút đích cuối cùng, giải phóng tài nguyên. | Kết thúc chương trình điều khiển. |

---

## 3. So sánh Logic Hoạt động: Speed Track vs. Smart City

Mặc dù hai chế độ chạy chia sẻ chung khung máy trạng thái FSM và cấu trúc phần cứng, logic chi tiết tại trạng thái xử lý sự kiện ngã tư `HANDLING_EVENT` có sự khác biệt rất lớn để đáp ứng mục tiêu riêng biệt của từng bài thi:

| Đặc tính So Sánh | Chế độ Tốc độ (Speed Track) | Chế độ Đô thị Thông minh (Smart City) |
| :--- | :--- | :--- |
| **Mục tiêu cốt lõi** | Di chuyển bám làn tốc độ cao, hoàn thành quãng đường đua trong thời gian ngắn nhất. | Tuân thủ tuyệt đối các luật giao thông (biển báo bắt buộc, biển cấm, đèn tín hiệu) và gửi nhận dữ liệu đô thị. |
| **Phương pháp Nhận diện** | Sử dụng mô hình YOLOv8n ONNX chạy cục bộ trên TensorRT GPU để phát hiện nhanh chướng ngại vật trên đường. | Gửi ảnh thời gian thực qua Roboflow Cloud Inference API để nhận diện chính xác các biển báo và đèn tín hiệu tại giao lộ. |
| **Quá trình tại Ngã tư** | - Không dừng lâu, không xoay tìm biển báo. <br>- Xe lấy trực tiếp hướng đi tiếp theo từ kế hoạch tìm đường tối ưu của bản đồ số để rẽ hướng. | - Dừng xe hẳn. Xoay xe một góc xác định ($45^\circ$, $-45^\circ$, $135^\circ$ hoặc $-135^\circ$) để camera hướng thẳng về phía biển báo. <br>- Gửi ảnh nhận diện biển báo, đèn giao thông và các sự kiện đô thị. <br>- Xoay xe trở lại hướng ban đầu. |
| **Truyền thông & Đánh giá** | Không yêu cầu tương tác hoặc chấm điểm trực tuyến. | - Gửi kết quả biển báo phát hiện được lên Server chấm điểm qua module [submit_sign copy.py](file:///d:/JetsonAIRacer/src/smart_city/submit_sign%20copy.py) hoặc HTTP POST. <br>- Trích xuất dữ liệu mã QR hoặc giải bài toán toán học (`math_problem`) rồi Publish dữ liệu lên Broker MQTT qua topic `jetbot/corrected_event_data`. |
| **Quyết định Điều hướng** | Đi theo đường đi ngắn nhất tính toán từ file `map.json` một cách trực tiếp. | - So khớp kế hoạch bản đồ với biển hiệu lệnh bắt buộc (Rẽ trái/phải/thẳng). <br>- Kiểm tra xem hướng đi có bị cấm bởi biển cấm hay không. <br>- Lập lại lộ trình mới tránh hướng bị cấm (Dynamic Replanning) bằng cách đưa cung đường cấm vào danh sách cấm `banned_edges`. |
| **Ổn định xe sau khi rẽ** | Sử dụng cơ chế bám làn tự động khôi phục bình thường. | Tích hợp thuật toán quét nhỏ chủ động `stabilize_after_turn()` (lắc nhẹ đầu xe trái/phải $6^\circ$) để giúp camera bắt lại vạch đen nhanh hơn sau khi rẽ ngã tư lớn. |
