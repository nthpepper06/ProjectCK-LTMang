# Hệ thống Khảo thí Trực tuyến An toàn & Giám sát Chống Gian lận Thông minh
## (Smart AI Proctoring & Secure Examination Platform)

> **Môn học:** Lập trình Mạng & An toàn Hệ thống  
> **Ngôn ngữ & Nền tảng:** Python 3.10+, PyQt6, OpenCV, MediaPipe, Cryptography, psutil, qrcode, WebSockets, Sockets (TCP & UDP Multicast).

---

## 📌 1. Tổng quan Kiến trúc Hệ thống

Dự án triển khai mô hình lai **Client-Server & Multicast P2P** kết hợp giám sát trí tuệ nhân tạo và mật mã học nâng cao, đảm bảo kỳ thi trực tuyến diễn ra an toàn, minh bạch và chống chối bỏ (*Non-repudiation*).

```
                      +------------------------------------+
                      |   GIÁM THỊ (PROCTOR CONTROLLER)    |
                      |   UDP Multicast (224.1.1.1:5005)   |
                      +-----------------+------------------+
                                        |
                 [Phát lệnh đồng bộ: START, PAUSE, FINISH]
                                        |
                                        v
+------------------------+   TCP / SSL   +-------------------------+
|     DESKTOP CLIENT     |<=============>|   EXAM TCP SERVER CORE  |
|  - Kiosk Mode Fullscreen|               |  - Multi-Thread Sockets |
|  - AI Camera Head Pose |  Telemetry &  |  - Session / Auth Guard |
|  - Question Palette    |  Violations   |  - RSA Countersignature |
|  - SQLite Auto-Save    |-------------->|  - Evidence File Vault  |
|  - Anti-Cheat Watchdog |               +------------+------------+
+------------------------+                            |
                                                WebSocket Event
                                                      |
                                                      v
                                         +-------------------------+
                                         |  PROCTOR WEB DASHBOARD  |
                                         |  (Live Stream & Alerts) |
                                         +-------------------------+
```

---

## 🚀 2. Các Phân hệ Cốt lõi

### A. Client Desktop Kiosk Mode (`client_desktop/`)
Được quản lý thông qua `QStackedWidget` theo đúng 4 giai đoạn vòng đời thi cử:
1. **Screen 1 (Pre-flight System Check):**
   - Quét camera HD, kiểm tra microphone.
   - Đo độ trễ mạng tới Server (yêu cầu Ping < 100ms).
   - Kiểm tra nguồn điện/pin máy tính (cảnh báo nếu < 40% chưa cắm sạc).
   - Kiểm tra màn hình duy nhất (ngăn chặn xuất cổng HDMI / màn hình phụ).
2. **Screen 2 (Biometric Onboarding & Login):**
   - Nhập thông tin thí sinh (MSSV, Họ tên).
   - Căn khung khuôn mặt trong camera, trích xuất Face Embedding và gửi xác thực sinh trắc học tới Server để nhận Session Token.
3. **Screen 3 (Exam View - Tối ưu UX/UI):**
   - **Question Palette (Lưới câu hỏi):** Đánh dấu trạng thái 3 màu (*Đã làm - Xanh lá, Chưa làm - Xám, Cần xem lại - Cam*). Bấm nút số câu sẽ tự động cuộn đến câu hỏi tương ứng.
   - **Local Auto-Save:** Tự động lưu nháp mã hóa vào SQLite cục bộ (`exam_local_drafts.db`) mỗi 15 giây hoặc sau khi gõ phím, đảm bảo không mất bài thi khi rớt mạng hoặc mất điện đột ngột.
   - **Network Auto-Reconnect:** Widget hiển thị ping thời gian thực, tự động thử kết nối lại TCP ngầm mà không làm đơ giao diện làm bài.
   - **Submission Confirmation Modal:** Hộp thoại thống kê chi tiết số câu đã làm / chưa làm trước khi xác nhận nộp.
4. **Screen 4 (Submission Receipt & Audit):**
   - Hiển thị biên lai điện tử với Timestamp mili-giây chuẩn xác.
   - Mã băm SHA-256 của toàn bộ bài làm.
   - Chữ ký số RSA 2048-bit PSS của sinh viên và chữ ký số xác thực của Server.
   - **Mã QR đối chiếu:** Chứa bản ghi chứng thực nộp bài giúp quét tra cứu nhanh.

### B. An ninh tầng Hệ điều hành (`client_desktop/security/`)
- **Multi-Monitor Blocker:** Phát hiện màn hình phụ qua `QGuiApplication.screens()` và phủ rèm đen khóa màn hình phụ.
- **Process Anti-Cheat Watchdog:** Luồng ngầm định kỳ 3 giây quét tiến trình qua `psutil` để phát hiện và cảnh báo các phần mềm gian lận (*TeamViewer, AnyDesk, UltraViewer, OBS Virtual Cam, Discord, Chrome, v.v.*).
- **Clipboard & Key Hook:** Định kỳ xóa bộ nhớ tạm Clipboard (mỗi 2 giây), chặn phím tắt nguy hiểm (`Alt`, `Esc`, `Windows`, `F11`) và bắt sự kiện `Focus Lost` (Alt-Tab/click ra ngoài).

### C. Giao thức Mạng & Máy chủ (`server/` & `common/`)
- **Giao thức Header 23-byte:** Định dạng nhị phân `!4sBHIQI` gồm Magic bytes (`b"EXAM"`), Version, Command Type, Nonce (chống replay attack), Timestamp và Payload Length.
- **Multi-Thread TCP Server (`server/tcp_server.py`):** Mỗi thí sinh được xử lý bởi một Worker Thread độc lập, theo dõi nhịp tim (Heartbeat Watchdog), tiếp nhận ảnh bằng chứng vi phạm và lưu trữ bài nộp.
- **UDP Multicast Broadcaster (`server/multicast_sender.py`):** Giám thị phát lệnh đồng bộ (`START_EXAM`, `PAUSE`, `RESUME`, `FINISH`, `ANNOUNCEMENT`) tới địa chỉ `224.1.1.1:5005` giúp hàng trăm client cùng phản hồi tức thì.
- **Mật mã học (`common/crypto_utils.py`):** Cặp khóa RSA 2048-bit, băm SHA-256, ký số PSS và mã hóa đối xứng AES-256-GCM.

---

## 🛠️ 3. Cài đặt Môi trường

Yêu cầu máy tính cài đặt **Python 3.10+**.

Cài đặt tất cả các thư viện phụ thuộc:
```powershell
pip install -r requirements.txt
```

---

## 🎮 4. Hướng dẫn Khởi chạy Hệ thống Đồng thời 3 Thành phần

Hệ thống được thiết kế theo kiến trúc phân tán hiện đại, giám thị và thí sinh có thể vận hành đồng thời trên 3 thành phần chính:

### Bước 1: Khởi động Máy chủ Tích hợp (TCP Core + Web Bridge + WebSocket)
Mở Terminal thứ nhất và chạy:
```powershell
python server\tcp_server.py
```
*Các cổng dịch vụ tự động kích hoạt:*
* **Cổng TCP `8888`:** Lắng nghe kết nối an toàn từ Desktop Kiosk Client của thí sinh.
* **Cổng HTTP `8080`:** Cung cấp Proctor Web Dashboard & REST APIs cho Giám thị.
* **Cổng WebSocket `8081`:** Đẩy thông báo vi phạm AI, nhịp tim và trạng thái thi theo thời gian thực.

---

### Bước 2: Mở Giao diện Giám thị Trung tâm (Proctor Web Dashboard)
Mở trình duyệt Web (Chrome, Edge, Firefox, Cốc Cốc) và truy cập:
👉 **[http://localhost:8080](http://localhost:8080)**

*Các tính năng giám thị trực tiếp:*
1. **Theo dõi thời gian thực (Live AI Violation Feed):** Xem ảnh webcam snapshot của thí sinh vi phạm, góc quay đầu Yaw/Pitch, và phóng to ảnh bằng chứng (Lightbox Modal).
2. **Quản lý danh sách phiên thi:** Xem tình trạng thí sinh kết nối, trạng thái làm bài, độ trễ nhịp tim (Heartbeat).
3. **Đối soát Chữ ký số RSA:** Kiểm tra mã băm SHA-256 bài thi và biên lai countersignature có chữ ký số của Server.
4. **Điều khiển phòng thi (UDP Multicast `224.1.1.1:5005`):** Bấm các nút **[Bắt Đầu Thi]**, **[Tạm Dừng Khẩn Cấp]**, **[Tiếp Tục]**, **[Thu Bài Đồng Loạt]**, hoặc phát thanh thông báo tức thì tới toàn bộ máy thi.

---

### Bước 3: Khởi động Ứng dụng Thi Kiosk Client của Thí sinh
Mở Terminal thứ hai và chạy:
```powershell
python client_desktop\main_window.py
```
*Trình tự 4 màn hình Kiosk:*
1. **Màn hình 1 (Pre-flight):** Kiểm tra camera HD, microphone, đo ping tới Server, kiểm tra pin và phát hiện màn hình phụ. Đạt chuẩn $\to$ Bấm **Tiếp tục**.
2. **Màn hình 2 (Sinh trắc học):** Nhập MSSV (`SV2026_01` hoặc `SV2026_02`), căn khung khuôn mặt trước webcam và bấm **So khớp khuôn mặt** để nhận Session Token.
3. **Màn hình 3 (Làm bài thi Kiosk):**
   - Làm bài với bộ câu hỏi tải từ Database máy chủ.
   - Bảng **Question Palette** chuyển đổi màu trạng thái thông minh và tự động cuộn.
   - Cơ chế tự động lưu nháp mã hóa cục bộ mỗi 15 giây chống mất dữ liệu khi mất điện.
   - Camera AI chạy ngầm tính toán góc đầu và phát hiện gian lận.
4. **Màn hình 4 (Biên nhận điện tử & QR Code):** Sau khi nộp bài, hệ thống ký số RSA-2048 PSS, gửi lên Server nhận biên lai và hiển thị mã QR chống chối bỏ.

---

## 🧪 5. Kiểm thử Tích hợp Tự động (Automated Test Suites)

Chạy kịch bản kiểm thử tích hợp toàn diện 4 giai đoạn:
```powershell
# Kiểm thử tích hợp TCP, SQLite, Watchdog, và Multicast
python tests\test_integration.py

# Kiểm thử tích hợp Giai đoạn 4: Client <-> Server <-> Web Bridge WebSocket <-> Multicast
python tests\test_stage4_integration.py
```
*Tất cả bài kiểm thử đều đạt kết quả `PASSED 100%`.*

---

## 📂 6. Cấu trúc Mã nguồn Chi tiết

```text
LapTrinhMang_Project/
├── common/
│   ├── protocol.py            # Giao thức nhị phân 23-byte Header & phân loại mã lệnh
│   └── crypto_utils.py        # Thư viện mã hóa RSA-2048, SHA-256 PSS, AES-256-GCM
├── server/
│   ├── tcp_server.py          # Điểm vào Multi-Threaded TCP Server & điều phối dịch vụ
│   ├── web_bridge.py          # Cầu nối HTTP Dashboard (8080) & WebSocket Broadcaster (8081)
│   ├── multicast_sender.py    # Bộ phát lệnh đồng loạt UDP Multicast (224.1.1.1:5005)
│   ├── core/
│   │   └── session_manager.py # Quản lý phiên kết nối & Heartbeat Watchdog luồng ngầm
│   ├── database/
│   │   ├── schema.sql         # Lược đồ CSDL bền vững (students, exams, questions, submissions, violations)
│   │   ├── connection.py      # Thread-local Database Manager, WAL mode, Mutex lock
│   │   ├── repositories.py    # Repository Pattern cho CRUD và truy vấn an toàn
│   │   └── seed_data.py       # Khởi tạo dữ liệu mẫu đề thi và tài khoản sinh viên
│   ├── services/
│   │   ├── auth_service.py    # Xác thực sinh trắc học Face ID & Token HMAC
│   │   ├── exam_service.py    # Phát đề thi, kiểm tra mã băm & xác thực chữ ký số RSA
│   │   └── audit_service.py   # Lưu trữ ảnh snapshot webcam & ghi log vi phạm
│   └── handlers/
│       └── socket_handler.py  # Router định tuyến byte-stream và điều phối dịch vụ
├── client_desktop/
│   ├── main_window.py         # Kiosk Host Window điều phối 4 màn hình
│   ├── ai_proctor_thread.py   # QThread xử lý thị giác MediaPipe & đo góc Pose Yaw/Pitch
│   ├── network_client.py      # TCP Client quản lý kết nối, heartbeat & nộp bài
│   ├── multicast_listener.py  # Luồng ngầm bắt gói tin UDP Multicast phòng thi
│   ├── security/
│   │   ├── monitor_blocker.py # Khóa màn hình phụ / HDMI
│   │   ├── process_watchdog.py# Quét phần mềm gian lận nền (psutil)
│   │   └── clipboard_hook.py  # Xóa clipboard chống sao chép đề
│   ├── storage/
│   │   └── local_db.py        # SQLite tự động lưu nháp mã hóa cục bộ
│   └── ui/
│       ├── screen_preflight.py# Màn hình 1: Chẩn đoán thiết bị
│       ├── screen_login.py    # Màn hình 2: Xác thực sinh trắc học
│       ├── screen_exam.py     # Màn hình 3: Giao diện thi chính & Question Palette
│       └── screen_receipt.py  # Màn hình 4: Biên nhận chữ ký số & QR Code
├── proctor_web/
│   ├── index.html             # Dashboard Web thời gian thực cho giám thị (Zero-CDN)
│   └── dashboard_server.py    # Điểm chạy độc lập phụ trợ cho Web Bridge
├── tests/
│   ├── test_integration.py    # Test suite tích hợp tổng thể
│   └── test_stage4_integration.py # Test suite tích hợp Web Bridge & WebSocket
├── docs/
│   ├── ARCHITECTURE.md        # Kiến trúc hệ thống, sơ đồ tuần tự & FSM
│   ├── DATABASE_DESIGN.md     # Thiết kế ERD & lược đồ CSDL chuẩn hóa
│   ├── SPEC.md                # Đặc tả kỹ thuật giao thức nhị phân 23-byte & chữ ký số
│   └── TASKS.md               # Bảng tổng hợp toàn bộ checklist hoàn thành
├── server_storage/            # Thư mục lưu trữ database SQLite & ảnh bằng chứng (Ignored in Git)
├── .gitignore
├── requirements.txt
└── README.md
```
