# JetRacer 2026

Dự án này phục vụ cho thử thách Jetson AI Racer 2026, tập trung vào việc xây dựng hệ thống điều khiển xe tự lái trên nền tảng Jetson với các module nhận diện, lập kế hoạch đường đi và điều khiển xe.

## Tổng quan

Repo hiện có hai hướng tiếp cận chính:
- Speed Track: tập trung vào việc bám làn, đi nhanh và xử lý các tình huống trên đường đua.
- Smart City: tập trung vào điều hướng trong môi trường đô thị, nhận diện biển báo và xử lý các điểm giao nhau.

## Cây thư mục

```text
JetsonAIRacer/
├── README.md
├── docs/
│   ├── DocumentJetracer.md
│   ├── proposal_en.md
│   └── proposal.md
├── JetRacer/
│   └── torchvision/
│       ├── packaging/
│       ├── references/
│       └── torchvision/
├── speed_track/
│   └── main_speed_track.py
└── src/
    ├── __init__.py
    ├── test.py
    ├── core/
    │   ├── __init__.py
    │   ├── control/
    │   │   └── racer_controller.py
    │   ├── perception/
    │   ├── planning/
    │   │   ├── callmap.py
    │   │   └── map_navigator.py
    │   └── utils/
    │       ├── map.json
    │       └── opposite_detector.py
    ├── smart_city/
    │   └── main_smart_city.py
    └── speed_track/
        └── main_speed_track.py
```

## Mô tả chức năng từng phần

- README.md: tài liệu tổng quan của dự án, nơi ghi lại mục tiêu, cấu trúc thư mục và ý tưởng triển khai.
- docs/: chứa các tài liệu nghiên cứu, đề xuất và hướng dẫn liên quan đến giải pháp JetRacer.
  - DocumentJetracer.md: tài liệu tổng quan về hệ thống xe Jetracer.
  - proposal_en.md: đề cương nghiên cứu bằng tiếng Anh.
  - proposal.md: bản đề cương nội bộ bằng tiếng Việt.
- JetRacer/torchvision/: thư viện/khung hỗ trợ liên quan đến xử lý ảnh, huấn luyện mô hình và các ví dụ nhận diện hình ảnh dùng cho AI trên xe.
- speed_track/: file khởi chạy cho chế độ Speed Track.
- src/: mã nguồn chính của hệ thống.
  - src/test.py: file kiểm tra nhanh hoặc ví dụ chạy thử.
  - src/core/control/racer_controller.py: lớp điều khiển phần cứng xe, bao gồm điều khiển steering, throttle, PID và các thao tác cơ bản như đi thẳng, rẽ, dừng.
  - src/core/perception/: nơi dự kiến xử lý dữ liệu cảm biến và hình ảnh từ camera, phục vụ nhận diện làn đường, biển báo và vật cản.
  - src/core/planning/callmap.py: script lấy bản đồ/map từ nguồn bên ngoài và lưu về file JSON để dùng cho điều hướng.
  - src/core/planning/map_navigator.py: module tìm đường ngắn nhất và điều hướng qua các node/bản đồ.
  - src/core/utils/map.json: dữ liệu bản đồ dùng cho planning và navigation.
  - src/core/utils/opposite_detector.py: module phát hiện vật cản hoặc tình huống đối diện để hỗ trợ điều khiển an toàn.
  - src/smart_city/main_smart_city.py: chương trình điều khiển chính cho thử thách Smart City, tích hợp nhận dạng, lập lộ trình và điều khiển xe.
  - src/speed_track/main_speed_track.py: chương trình điều khiển chính cho thử thách Speed Track.

## Ý nghĩa kiến trúc hiện tại

Cấu trúc này chia hệ thống thành ba tầng chính:
1. Perception: thu thập và xử lý dữ liệu từ camera/cảm biến.
2. Planning: lập lộ trình và quyết định hướng đi.
3. Control: chuyển quyết định thành tín hiệu điều khiển cho xe.

Nhờ cách tổ chức này, mỗi phần có thể phát triển độc lập và dễ dàng kiểm thử hơn.

