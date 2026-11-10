# TÀI LIỆU KIẾN TRÚC HỆ THỐNG (SYSTEM ARCHITECTURE)
## Nền tảng Khảo thí Trực tuyến An toàn & Giám sát AI (Smart AI Proctoring & Secure Examination Platform)

---

### 1. TỔNG QUAN HỆ THỐNG
Hệ thống là nền tảng khảo thí phân tán chuẩn Client-Server dành cho môi trường mạng nội bộ (LAN/Enterprise), tích hợp giám sát sinh trắc học thời gian thực bằng AI, kiểm soát an ninh tầng hệ điều hành (Kiosk OS-level), đồng bộ hóa lệnh thi đồng loạt qua UDP Multicast, và bảo đảm tính toàn vẹn, chống chối bỏ (Non-repudiation) thông qua Chữ ký số RSA-2048 PSS kết hợp hàm băm an toàn SHA-256.

---

### 2. SƠ ĐỒ THÀNH PHẦN KIẾN TRÚC (SYSTEM COMPONENT DIAGRAM)

```mermaid
flowchart TB
    subgraph ClientDesktop["🖥️ CLIENT DESKTOP APPLICATION (PyQt6 / Kiosk Mode)"]
        direction TB
        subgraph UI_Layer["Giao diện Người dùng (QStackedWidget)"]
            S1["Screen 1: Pre-flight Diagnostic"]
            S2["Screen 2: Biometric Onboarding"]
            S3["Screen 3: Exam View & Palette"]
            S4["Screen 4: Cryptographic Receipt"]
        end

        subgraph Client_Security["An ninh Tầng Hệ điều hành (OS Security)"]
            MB["Multi-Monitor Blocker (QGuiApplication)"]
            PW["Anti-Cheat Watchdog (psutil 3s scan)"]
            CS["Clipboard & Focus Sanitizer"]
        end

        subgraph Client_Proctor["Giám sát Thị giác Máy tính (AI Engine)"]
            CV_Worker["AIProctorThread (OpenCV + MediaPipe)"]
            Face_Mesh["FaceMesh & Head Pose (Yaw/Pitch)"]
        end

        subgraph Client_Core["Tầng Xử lý Mạng & Lưu trữ Cục bộ"]
            Net_Client["NetworkClient (TCP Socket + RSA Signer)"]
            Local_DB[("Local SQLite Draft Storage")]
            MC_Listen["MulticastListener (UDP 224.1.1.1:5005)"]
        end

        S3 <--> Local_DB
        CV_Worker --> Face_Mesh
        Face_Mesh --> UI_Layer
        Client_Security --> Net_Client
        CV_Worker --> Net_Client
        MC_Listen --> S3
    end

    subgraph Network_Boundary["🌐 TẦNG GIAO VẬN MẠNG (TCP / UDP)"]
        TCP_Stream["Kênh TCP Tin cậy (Frame: 23-byte Binary Header + JSON Payload)"]
        UDP_Stream["Kênh UDP Multicast (224.1.1.1:5005 - Đồng bộ Lệnh thi)"]
    end

    subgraph ServerBackend["🏢 BACKEND SERVER CORE (Layered Multi-Threaded Architecture)"]
        direction TB
        subgraph Net_Inbound["Tầng Nhập liệu Mạng & Giao vận"]
            TCP_Listener["Multi-Thread TCP Listener (Port 8888)"]
            MC_Sender["Multicast Command Broadcaster (TTL=2)"]
            Socket_Handler["Socket Request Handler (Packet Framing)"]
        end

        subgraph Core_Services["Tầng Dịch vụ Nghiệp vụ (Business Services)"]
            Session_Mgr["SessionManager (Heartbeat & Concurrency)"]
            Auth_Svc["AuthService (Biometric & Key Registration)"]
            Exam_Svc["ExamService (Paper Delivery & RSA Verify)"]
            Audit_Svc["AuditService (Telemetry & Evidence Storage)"]
        end

        subgraph DB_Layer["Tầng Dữ liệu Bền vững (Persistent Data Access)"]
            DB_Conn["Thread-Safe Database Connection Pool (WAL Mode)"]
            Student_Repo["StudentRepository"]
            Exam_Repo["ExamRepository"]
            Sub_Repo["SubmissionRepository"]
            Viol_Repo["ViolationRepository"]
            Disk_DB[("SQLite/Postgres Database: exam_system.db")]
        end

        TCP_Listener --> Socket_Handler
        Socket_Handler --> Core_Services
        Core_Services --> DB_Layer
        DB_Conn --> Disk_DB
    end

    Net_Client <==> TCP_Stream <==> TCP_Listener
    MC_Sender -.-> UDP_Stream -.-> MC_Listen
```

---

### 3. SƠ ĐỒ TUẦN TỰ ĐẦY ĐỦ VÒNG ĐỜI THI (SEQUENCE DIAGRAM)

```mermaid
sequenceDiagram
    autonumber
    actor Candidate as Thí sinh (Client UI)
    participant ClientCore as Client Engine
    participant AIWorker as AI Proctor Thread
    participant TCPServer as TCP Server Handler
    participant DB as Persistent Database
    actor Proctor as Giám thị (Multicast Console)

    Note over Candidate, ClientCore: GIAI ĐOẠN 1: PRE-FLIGHT SYSTEM DIAGNOSTIC
    Candidate->>ClientCore: Khởi chạy ứng dụng
    ClientCore->>ClientCore: Quét Camera, Micro, Màn hình phụ, Nguồn điện
    ClientCore->>TCPServer: Đo RTT Ping (< 100ms)
    TCPServer-->>ClientCore: PONG phản hồi độ trễ
    ClientCore-->>Candidate: Tất cả chỉ số ĐẠT -> Mở khóa nút Tiếp tục

    Note over Candidate, DB: GIAI ĐOẠN 2: BIOMETRIC LOGIN & RSA HANDSHAKE
    Candidate->>ClientCore: Nhập MSSV & chụp khuôn mặt
    AIWorker->>ClientCore: Trích xuất Face Embedding (128-d vector)
    ClientCore->>ClientCore: Sinh cặp khóa RSA 2048-bit thí sinh
    ClientCore->>TCPServer: REQ_CONNECT (MSSV, Public Key PEM)
    TCPServer->>DB: Kiểm tra sinh viên & lưu Public Key tạm thời
    TCPServer-->>ClientCore: RES_CONNECT_OK (Server Public Key PEM)
    ClientCore->>TCPServer: REQ_AUTH_BIOMETRIC (MSSV, Face Embedding)
    TCPServer->>DB: Đối soát vector khuôn mặt đăng ký sẵn trong DB
    DB-->>TCPServer: So khớp cosine similarity >= 0.70
    TCPServer-->>ClientCore: RES_AUTH_SUCCESS (Session Token)

    Note over Candidate, DB: GIAI ĐOẠN 3: NHẬN ĐỀ & THI TRỰC TUYẾN
    ClientCore->>TCPServer: REQ_EXAM_PAPER (exam_id, session_token)
    TCPServer->>DB: Lấy đề thi & danh sách câu hỏi
    DB-->>TCPServer: Exam Paper (JSON)
    TCPServer-->>ClientCore: RES_EXAM_PAPER (Title, Questions)
    Proctor->>ClientCore: UDP Multicast (224.1.1.1:5005) -> CMD_EXAM_START
    ClientCore->>Candidate: Mở phòng thi, bắt đầu đếm ngược thời gian

    loop Chu kỳ 3-5 giây trong khi làm bài
        Candidate->>ClientCore: Nhập câu trả lời
        ClientCore->>ClientCore: Auto-save nháp vào SQLite cục bộ (15s)
        ClientCore->>TCPServer: PING (Heartbeat)
        TCPServer-->>ClientCore: PONG
        AIWorker->>ClientCore: Phát hiện nghi vấn (Quay đầu Yaw > 25° / Chrome mở)
        ClientCore->>TCPServer: REPORT_VIOLATION (Vi phạm, Snapshot JPEG)
        TCPServer->>DB: Ghi log vi phạm & lưu file ảnh vào ổ cứng
        TCPServer-->>ClientCore: VIOLATION_ACK
    end

    Note over Candidate, DB: GIAI ĐOẠN 4: NỘP BÀI THI & CHỮ KÝ SỐ CHỐNG CHỐI BỎ
    Candidate->>ClientCore: Nhấn Xác nhận Nộp bài
    ClientCore->>ClientCore: Sắp xếp Canonical JSON câu trả lời
    ClientCore->>ClientCore: Băm SHA-256 nội dung bài thi
    ClientCore->>ClientCore: Ký số hash bằng Private Key RSA-2048 (PSS Padding)
    ClientCore->>TCPServer: SUBMIT_EXAM (exam_id, answers, sha256_hash, signature)
    TCPServer->>DB: Lấy Public Key của thí sinh trong DB
    TCPServer->>TCPServer: Verify chữ ký số Thí sinh (Khẳng định tính xác thực)
    TCPServer->>TCPServer: Ký đối ứng bằng Server RSA Private Key (Countersignature)
    TCPServer->>DB: TRANSACTION: Lưu submission + audit receipt
    TCPServer-->>ClientCore: SUBMIT_ACK (Receipt Data + Server Signature)
    ClientCore->>Candidate: Hiển thị Màn hình 4: Biên nhận điện tử + Mã QR đối soát
```

---

### 4. MÔ HÌNH MÁY TRẠNG THÁI PHIÊN (SESSION STATE MACHINE)

```mermaid
stateDiagram-v2
    [*] --> DISCONNECTED: Khởi động Client

    DISCONNECTED --> CONNECTED: TCP Connect + REQ_CONNECT (Trao đổi RSA Public Key)
    CONNECTED --> DISCONNECTED: Socket error / Timeout 15s

    CONNECTED --> AUTHENTICATED: REQ_AUTH_BIOMETRIC (Face Embedding khớp DB >= 70%)
    AUTHENTICATED --> DISCONNECTED: Auth thất bại / Mất kết nối

    AUTHENTICATED --> EXAM_IN_PROGRESS: Nhận đề thi + Lệnh Multicast START_EXAM
    EXAM_IN_PROGRESS --> EXAM_PAUSED: Lệnh Multicast PAUSE_EXAM
    EXAM_PAUSED --> EXAM_IN_PROGRESS: Lệnh Multicast RESUME_EXAM

    EXAM_IN_PROGRESS --> SUBMITTING: Nhấn Nộp bài / Hết giờ thi (CMD_EXAM_FINISH)
    SUBMITTING --> SUBMITTED: Ký số RSA hợp lệ + Server xác nhận cấp Biên lai
    SUBMITTING --> EXAM_IN_PROGRESS: Lỗi đường truyền / Ký số thất bại (Thử lại)

    SUBMITTED --> DISCONNECTED: Thí sinh đóng ứng dụng / Hoàn tất
    DISCONNECTED --> [*]
```

#### Bảng Phân tích Chi tiết Trạng thái Phiên (Session State Transitions)

| Trạng thái | Điều kiện kích hoạt (Trigger) | Hành động Hệ thống (Actions) | Quyền hạn Thí sinh | Rủi ro & Cơ chế phục hồi (Fail-safe) |
|---|---|---|---|---|
| **DISCONNECTED** | Mở ứng dụng hoặc mất kết nối vật lý | Client thử kết nối lại TCP mỗi 4 giây | Chỉ chạy Pre-flight Diagnostics | Không cho phép vào thi nếu chưa nối mạng |
| **CONNECTED** | Hoàn tất bắt tay TCP và gửi `REQ_CONNECT` | Lưu tạm Session, trao đổi khóa công khai RSA-2048 giữa 2 bên | Điền form MSSV, căn chỉnh camera | Timeout 15s tự hủy kết nối để chống nghẽn |
| **AUTHENTICATED** | So khớp Face Embedding đạt độ tin cậy >= 70% | Sinh Session Token, lưu trạng thái định danh vào DB | Được yêu cầu tải đề thi | Nếu sai khuôn mặt quá 3 lần -> Báo động |
| **EXAM_IN_PROGRESS** | Tải đề xong và nhận lệnh bắt đầu | Khởi động luồng giám sát AI, nhận heartbeat định kỳ, bắt đầu đếm giờ | Trả lời câu hỏi, chuyển câu trên Palette | Nếu đứt kết nối mạng: Auto-save SQLite cục bộ không đóng băng màn hình, tự kết nối lại |
| **EXAM_PAUSED** | Nhận lệnh `CMD_EXAM_PAUSE` qua UDP Multicast | Dừng bộ đếm ngược, vô hiệu hóa ô nhập liệu tạm thời | Chỉ xem câu hỏi, không sửa được bài | Phục hồi ngay khi nhận `CMD_EXAM_RESUME` |
| **SUBMITTING** | Thí sinh xác nhận nộp hoặc hết giờ | Canonical hóa đáp án, băm SHA-256, ký RSA-2048 PSS | Khóa mọi ô nhập liệu | Có cơ chế retry nếu gói tin gửi đi bị thất lạc |
| **SUBMITTED** | Server verify chữ ký số và ghi DB thành công | Xóa bản nháp SQLite cục bộ, tạo mã QR biên lai | Xem chứng chỉ biên lai, quét QR | Biên lai lưu bất biến trên Server DB chống chối bỏ |
