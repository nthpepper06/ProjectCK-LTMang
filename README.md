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

## 🎮 4. Hướng dẫn Chạy & Demo Hệ thống

### Bước 1: Chạy kiểm thử tự động toàn diện (Automated Integration Tests)
```powershell
python tests\test_integration.py
```
*Kết quả mong đợi: Toàn bộ 4 test suites (Mật mã & Framing, SQLite Auto-save & Watchdog, TCP Lifecycle, UDP Multicast) đều đạt `PASSED`.*

### Bước 2: Khởi động TCP Examination Server
Mở terminal thứ nhất:
```powershell
python server\tcp_server.py
```

### Bước 3: Khởi động Ứng dụng thi Kiosk Client
Mở terminal thứ hai:
```powershell
python client_desktop\main_window.py
```
*Trình tự trải nghiệm:*
1. Màn hình 1: Bấm kiểm tra phần cứng & ping server. Đạt chuẩn -> Bấm **Tiếp tục**.
2. Màn hình 2: Nhập MSSV, căn mặt trước webcam và bấm **So khớp khuôn mặt**.
3. Màn hình 3: Làm bài thi, thử click câu hỏi trên bảng Question Palette, quan sát trạng thái lưu nháp SQLite và camera AI tracking góc đầu.
4. Bấm **Nộp bài thi** -> Xem bảng thống kê -> Xác nhận nộp bài kèm chữ ký số RSA.
5. Màn hình 4: Nhận biên nhận điện tử và mã QR tra cứu.

### Bước 4: Giám thị phát lệnh đồng loạt qua UDP Multicast
Mở terminal thứ ba:
```powershell
python server\multicast_sender.py
```
*Chọn các phím số từ `1` đến `5` để phát lệnh Bắt đầu thi, Tạm dừng hoặc Thu bài đồng loạt cho tất cả các máy thí sinh đang chạy.*

---

## 📂 5. Cấu trúc Mã nguồn Chi tiết

```text
LapTrinhMang_Project/
├── common/
│   ├── protocol.py            # Giao thức truyền tin nhị phân và đóng gói gói tin
│   └── crypto_utils.py        # Thư viện mã hóa RSA-2048, SHA-256 PSS, AES-GCM
├── server/
│   ├── tcp_server.py          # Máy chủ TCP đa luồng chấm thi & xác thực chữ ký số
│   └── multicast_sender.py    # Bộ phát lệnh UDP Multicast phòng thi
├── client_desktop/
│   ├── main_window.py         # Kiosk Host Window điều phối 4 màn hình
│   ├── ai_proctor_thread.py   # QThread xử lý thị giác máy tính & phát hiện vi phạm
│   ├── network_client.py      # TCP Client quản lý phiên, nhịp tim & nộp bài
│   ├── multicast_listener.py  # Luồng lắng nghe UDP Multicast phòng thi
│   ├── security/
│   │   ├── monitor_blocker.py # Khóa màn hình phụ / HDMI
│   │   ├── process_watchdog.py# Quét phần mềm gian lận nền (psutil)
│   │   └── clipboard_hook.py  # Xóa clipboard chống sao chép đề
│   ├── storage/
│   │   └── local_db.py        # SQLite tự động lưu nháp bài thi
│   └── ui/
│       ├── screen_preflight.py# Màn hình 1: Chẩn đoán thiết bị
│       ├── screen_login.py    # Màn hình 2: Xác thực sinh trắc học
│       ├── screen_exam.py     # Màn hình 3: Giao diện thi chính & Question Palette
│       └── screen_receipt.py  # Màn hình 4: Biên nhận chữ ký số & QR Code
├── proctor_web/
│   ├── index.html             # Dashboard Web thời gian thực cho giám thị
│   └── dashboard_server.py    # WebSocket Server thông báo cảnh báo
├── tests/
│   └── test_integration.py   # Test suite tích hợp tự động
├── docs/plans/
│   └── 2026-11-10-production-exam-platform.md
├── .gitignore
├── requirements.txt
└── README.md
```
