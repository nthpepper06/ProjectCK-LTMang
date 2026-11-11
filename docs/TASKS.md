# TỔNG HỢP TIẾN ĐỘ & CHECKLIST CÔNG VIỆC DỰ ÁN
# (PROJECT TASK LIST & EXECUTION CHECKLIST)

> **Dự án:** Smart AI Proctoring & Secure Examination Platform  
> **Trạng thái:** ✅ ĐÃ HOÀN THÀNH 100% CẢ 4 GIAI ĐOẠN (SPEC-DRIVEN LEVEL 6)  
> **Bản cập nhật:** 2026-11-11

---

## GIAI ĐOẠN 1: PHÂN TÍCH & THIẾT KẾ HỆ THỐNG
- [x] Tạo tài liệu kiến trúc tổng thể [`docs/ARCHITECTURE.md`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/docs/ARCHITECTURE.md):
  - [x] Sơ đồ khối kiến trúc hệ thống tổng thể (System Component Diagram) bằng cú pháp Mermaid.
  - [x] Sơ đồ tuần tự đầy đủ (End-to-End Sequence Diagram) từ Pre-flight, Biometric Auth, Nhận đề, Vi phạm AI, đến Nộp bài Ký số.
  - [x] Bảng và biểu đồ trạng thái phiên (Session State Machine: `DISCONNECTED` $\to$ `CONNECTED` $\to$ `AUTHENTICATED` $\to$ `IN_EXAM` $\to$ `SUBMITTED`).
- [x] Tạo tài liệu thiết kế cơ sở dữ liệu [`docs/DATABASE_DESIGN.md`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/docs/DATABASE_DESIGN.md):
  - [x] Thiết kế ERD (Entity Relationship Diagram) trực quan bằng Mermaid.
  - [x] Từ điển dữ liệu chuẩn hóa 5 bảng: `students`, `exams`, `questions`, `submissions`, `violation_logs`.
  - [x] Chiến lược đánh chỉ mục Indexing tăng tốc truy vấn và đảm bảo tính toàn vẹn khóa ngoại (Foreign Keys).
  - [x] Phân tích xử lý tương tranh đa luồng (WAL Mode + Python Mutex Serialization).

---

## GIAI ĐOẠN 2: THIẾT KẾ & TRIỂN KHAI TẦNG DATABASE THỰC TẾ
- [x] Khởi tạo tệp DDL [`server/database/schema.sql`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/server/database/schema.sql):
  - [x] Tạo bảng `students` (id, student_id UNIQUE, full_name, rsa_public_key, face_embedding BLOB, created_at).
  - [x] Tạo bảng `exams` (id, exam_code UNIQUE, title, start_time, duration_minutes, is_active).
  - [x] Tạo bảng `questions` (id, exam_id FK, question_index, content, options JSON, correct_answer).
  - [x] Tạo bảng `submissions` (id, exam_id FK, student_id FK, answers_payload, sha256_hash, digital_signature, server_receipt_signature, submitted_at, status).
  - [x] Tạo bảng `violation_logs` (id, student_id FK, exam_id FK, violation_type, suspicion_score, details, evidence_path, timestamp).
  - [x] Cài đặt chỉ mục Index tối ưu hóa tìm kiếm theo `student_id`, `exam_code`, `timestamp`.
- [x] Triển khai [`server/database/connection.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/server/database/connection.py):
  - [x] Quản lý kết nối Thread-safe với Thread-Local Storage (`threading.local`).
  - [x] Bật chế độ ghi nhật ký trước `PRAGMA journal_mode = WAL`.
  - [x] Kích hoạt bắt buộc ràng buộc khóa ngoại `PRAGMA foreign_keys = ON`.
  - [x] Context Manager `read_cursor()` và `write_transaction()` tuần tự hóa ghi qua `_write_lock`.
- [x] Triển khai Repository Pattern [`server/database/repositories.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/server/database/repositories.py):
  - [x] `StudentRepository`: CRUD thí sinh, tìm kiếm theo MSSV, lưu và lấy Public Key, xác thực vector sinh trắc học.
  - [x] `ExamRepository`: Quản lý kỳ thi, lấy đề thi kích hoạt, lấy danh sách câu hỏi.
  - [x] `SubmissionRepository`: Lưu bài nộp với chữ ký số, đối soát chống chối bỏ.
  - [x] `ViolationRepository`: Ghi nhật ký cảnh báo AI, đếm số lần vi phạm của từng thí sinh.
- [x] Xây dựng Script Seeder [`server/database/seed_data.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/server/database/seed_data.py):
  - [x] Khởi tạo dữ liệu mẫu cho kỳ thi `LTM_2026_FINAL` và 3 câu hỏi trắc nghiệm mạng máy tính.
  - [x] Khởi tạo 2 tài khoản thí sinh (`SV2026_01`, `SV2026_02`) kèm cặp khóa RSA-2048 và vector khuôn mặt mẫu.
  - [x] Đã chạy seeder thành công, tạo cơ sở dữ liệu `server_storage/exam_system.db`.

---

## GIAI ĐOẠN 3: TÁI CẤU TRÚC BACKEND (LAYERED ARCHITECTURE)
- [x] Triển khai Quản lý Phiên [`server/core/session_manager.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/server/core/session_manager.py):
  - [x] Class `ClientSession`: Quản lý socket, IP, MSSV, trạng thái và dấu thời gian heartbeat cuối.
  - [x] Singleton `SessionManager`: Quản lý đồng bộ tập kết nối, thread-safe qua mutex lock.
  - [x] Luồng ngầm **Heartbeat Watchdog Thread**: Quét chu kỳ 3s, tự động ngắt kết nối (kick) client mất tín hiệu quá 15s.
- [x] Triển khai Tầng Dịch Vụ Nghiệp Vụ (`server/services/`):
  - [x] [`auth_service.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/server/services/auth_service.py): Xác thực sinh trắc học Cosine Similarity ($\ge 0.70$) và cấp Token HMAC an toàn.
  - [x] [`exam_service.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/server/services/exam_service.py): Phát đề thi; Đối soát SHA-256; Xác thực chữ ký số RSA-2048 PSS của thí sinh; Ký biên lai Server Countersignature; Ghi DB qua write transaction.
  - [x] [`audit_service.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/server/services/audit_service.py): Giải mã ảnh chụp snapshot webcam từ Base64, lưu file JPEG vào `server_storage/evidence/`, ghi nhật ký vào database.
- [x] Triển khai Bộ Định Tuyến Gói Tin [`server/handlers/socket_handler.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/server/handlers/socket_handler.py):
  - [x] Tách rời logic socket khỏi Server Core, tiếp nhận và phân giải gói tin theo chuẩn giao thức 23-byte Header.
  - [x] Định tuyến Switch-case toàn bộ mã lệnh: `REQ_CONNECT`, `REQ_AUTH_BIOMETRIC`, `PING`, `REQ_EXAM_PAPER`, `REPORT_VIOLATION`, `SUBMIT_EXAM_PAPER`, `DISCONNECT`.
  - [x] Trả về mã phản hồi chuẩn hóa kèm dữ liệu trạng thái.
- [x] Tái cấu trúc Điểm Vào Máy Chủ [`server/tcp_server.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/server/tcp_server.py):
  - [x] Quản lý luồng bằng `ThreadPoolExecutor(max_workers=50)`.
  - [x] Tiếp nhận kết nối và chuyển giao trực tiếp cho `SocketHandler`.
  - [x] Dọn dẹp tài nguyên (Resource cleanup) và đóng các kết nối sạch khi dừng server.

---

## GIAI ĐOẠN 4: PROCTOR WEB DASHBOARD & ĐỒNG BỘ REAL-TIME
- [x] Xây dựng Cầu Nối Web & WebSocket [`server/web_bridge.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/server/web_bridge.py):
  - [x] Tích hợp HTTP Server (`http://localhost:8080`) phục vụ dashboard và REST APIs (`/api/overview`, `/api/sessions`, `/api/violations`, `/api/submissions`).
  - [x] Phục vụ ảnh bằng chứng snapshot vi phạm tại endpoint `/evidence/<filename>`.
  - [x] Tích hợp WebSocket Server (`ws://localhost:8081`) phát sóng thời gian thực cho các sự kiện: `INITIAL_STATE`, `SESSION_UPDATE`, `NEW_VIOLATION`, `NEW_SUBMISSION`, `MULTICAST_DISPATCHED`.
  - [x] Điều khiển phát sóng UDP Multicast vào nhóm `224.1.1.1:5005` trực tiếp từ Web Dashboard qua `MulticastSender`.
- [x] Xây dựng Giao diện Web Giám Thị Hiện Đại [`proctor_web/index.html`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/proctor_web/index.html):
  - [x] Thiết kế Modern Dark Mode thuần CSS (Zero CDN, độc lập 100% khi chạy trong mạng LAN không có Internet).
  - [x] 4 thẻ chỉ số KPI thời gian thực: Thí sinh trực tuyến, Đang làm bài, Đã nộp bài, Cảnh báo vi phạm.
  - [x] Cụm nút bấm điều khiển phòng thi qua UDP Multicast: `BẮT ĐẦU THI`, `TẠM DỪNG`, `TIẾP TỤC`, `THU BÀI ĐỒNG LOẠT`, `PHÁT THÔNG BÁO`.
  - [x] Bảng danh sách thí sinh kết nối trực tuyến kèm chỉ báo nhịp tim cuối (Heartbeat ago).
  - [x] Bảng đối soát chứng thực chữ ký số RSA-2048 và mã băm SHA-256 các bài đã nộp.
  - [x] Luồng cảnh báo vi phạm AI thời gian thực (Live AI Violation Feed) kèm ảnh snapshot thu nhỏ và Lightbox Modal phóng to ảnh bằng chứng.
- [x] Kiểm thử tích hợp toàn diện [`tests/test_stage4_integration.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/tests/test_stage4_integration.py):
  - [x] Kiểm thử thành công 7/7 bước tích hợp: HTTP serving $\to$ WebSocket connect $\to$ TCP Connect & Auth $\to$ Fetch Exam $\to$ AI Violation & Snapshot $\to$ RSA Submission $\to$ UDP Multicast control.
  - [x] 100% các bài test đều đạt `PASSED`.

---

## BƯỚC KHÓA SỔ DỰ ÁN & RÀ SOÁT TRƯỚC KHI COMMIT (PRE-PUSH AUDIT)
- [x] Tạo tài liệu Single Source of Truth [`docs/SPEC.md`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/docs/SPEC.md).
- [x] Tạo tài liệu tổng kết checklist công việc [`docs/TASKS.md`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/docs/TASKS.md).
- [x] Cập nhật hướng dẫn chạy 3 thành phần hệ thống trong [`README.md`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/README.md).
- [x] Rà soát và cập nhật [`.gitignore`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/.gitignore) chặn rò rỉ cơ sở dữ liệu (`*.db`), ảnh snapshot (`server_storage/`), khóa mật mã (`*.pem`, `*.key`), và cache (`__pycache__/`, `.venv/`).
- [x] Kiểm tra danh sách file sạch bằng `git status`.
- [x] Dừng lại ở báo cáo, tuân thủ không chạy `git push` cho đến khi có lệnh phê duyệt.

---

## GIAI ĐOẠN 5: COMMERCIAL-GRADE ENTERPRISE HARDENING & MULTI-MODAL AI (SEB / LOCKDOWN LEVEL)
- [x] **Phần 1: Mạng LAN Tự Động & Điều Khiển Phòng Thi (Zero-Config LAN & Exam Lifecycle):**
  - [x] Xây dựng module khám phá mạng [`common/discovery.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/common/discovery.py) với `ServerDiscoveryResponder` (UDP 5006) và `ClientLANScanner` (quét 3s).
  - [x] Tích hợp `ServerDiscoveryResponder` vào [`server/tcp_server.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/server/tcp_server.py).
  - [x] Tích hợp quét tự động và cấu hình thủ công fallback kèm lưu `client_config.json` vào [`client_desktop/ui/screen_preflight.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/client_desktop/ui/screen_preflight.py).
  - [x] Triển khai cơ chế Đồng hồ cưỡng chế nộp bài (Time-out Auto-Submission) khi đếm ngược về 00:00:00 hoặc nhận `CMD_EXAM_FINISH` tại [`client_desktop/ui/screen_exam.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/client_desktop/ui/screen_exam.py).
- [x] **Phần 2: Phòng Thủ Tầng Sâu Hệ Điều Hành (Deep OS Hardening via Win32 API):**
  - [x] Xây dựng module [`client_desktop/security/windows_guard.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/client_desktop/security/windows_guard.py) giao tiếp nhân Windows qua `ctypes`.
  - [x] Triển khai Anti-VM & Hypervisor Detection (quét BIOS/System Model Registry và OUI Prefix MAC address ảo).
  - [x] Triển khai Low-Level Keyboard Hook (`WH_KEYBOARD_LL = 13`): Chặn triệt để Windows key, Alt+Tab, Alt+Esc, Ctrl+Esc, F1-F12 (cho phép F11 cho Kiosk switch) và đảm bảo unhook an toàn khi thoát/nộp bài.
  - [x] Triển khai Chống quay màn hình & chụp lén (`SetWindowDisplayAffinity` với `WDA_MONITOR`/`WDA_EXCLUDEFROMCAPTURE`) biến cửa sổ thành màu đen trên OBS/Discord/Zoom/Snipping Tool.
- [x] **Phần 3: AI Giám Sát Đa Phương Thức (Multi-Modal Vision & Audio AI):**
  - [x] Nâng cấp [`client_desktop/ai_proctor_thread.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/client_desktop/ai_proctor_thread.py) với Eye Aspect Ratio (EAR) và theo dõi chớp mắt phát hiện ảnh tĩnh lặp lại / spoofing.
  - [x] Tích hợp mô hình ONNX Runtime / fallback detector phát hiện vật thể cấm (`cell phone`) và phát hiện có trên 1 người (`person` count > 1) định kỳ mỗi 2 giây.
  - [x] Xây dựng luồng thu âm ngầm giám sát âm thanh môi trường [`client_desktop/security/audio_monitor.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/client_desktop/security/audio_monitor.py) tính toán RMS năng lượng âm thanh, kích hoạt cảnh báo đàm thoại liên tục > 3 giây.
- [x] **Phần 4: Đa Dạng Hóa Loại Câu Hỏi & Trải Nghiệm Khảo Thí (Exam UX & Cyber HUD):**
  - [x] Tích hợp [`client_desktop/ui/cyber_camera_hud.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/client_desktop/ui/cyber_camera_hud.py) với `QPainter` vẽ 4 góc Reticle chữ L, tia quét Laser Face ID, vector nhìn 3D Gaze Ray và các badge Glassmorphism hiển thị góc đầu Yaw/Pitch, EAR, số khuôn mặt.
  - [x] Tích hợp Cyber Camera HUD vào Màn hình Đăng nhập sinh trắc học ([`screen_login.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/client_desktop/ui/screen_login.py)) và Màn hình Thi chính ([`screen_exam.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/client_desktop/ui/screen_exam.py)).
  - [x] Nâng cấp [`client_desktop/ui/screen_exam.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/client_desktop/ui/screen_exam.py) hỗ trợ cả Trắc nghiệm (`multiple_choice` với `QRadioButton` / `QButtonGroup`) và Tự luận (`essay` với `QTextEdit`).
  - [x] Giải quyết triệt để lỗi scroll: Cài đặt `eventFilter` lên `ans_input.viewport()` chống bẫy con lăn chuột (Mouse Wheel Trap) khi di chuyển qua ô nhập văn bản; áp dụng `SetMinAndMaxSize` lên `questions_layout`.
  - [x] Bổ sung Thẻ hành động nộp bài cuối cùng (`ExamEndActionCard`) ngay dưới câu hỏi cuối cùng của danh sách cuộn, cho phép thí sinh nộp bài tiện lợi từ cả thanh Sticky Bottom Bar lẫn cuối trang đề thi.
  - [x] Hoàn thiện chuyển đổi Kiosk/Cửa sổ/Thu nhỏ: Tự động tháo gỡ `LowLevelKeyboardGuard` khi Thu nhỏ hoặc chuyển sang chế độ Cửa sổ để thuận tiện cho Giám thị/Thí sinh thao tác, và tự động tái cài đặt bảo mật khi quay lại Chế độ Toàn màn hình Kiosk.
  - [x] Cập nhật [`server/database/seed_data.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/server/database/seed_data.py) bổ sung câu hỏi tự luận mẫu và tái tạo seed data.
  - [x] Chuẩn hóa lưu nháp tự động vào SQLite cục bộ (`exam_local_drafts.db`).
- [x] **Kiểm thử tự động & Báo cáo:**
  - [x] Viết test suite chuyên sâu [`tests/test_enterprise_security.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/tests/test_enterprise_security.py) kiểm tra UDP LAN Discovery, Anti-VM check, Auto-submit, và Win32 guard logic (7/7 tests passed).
  - [x] Viết test suite tích hợp luồng hoàn chỉnh [`tests/test_full_system_integration.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/tests/test_full_system_integration.py) kiểm tra toàn trình từ TCP Handshake $\to$ Face Auth $\to$ Đề thi $\to$ Báo cáo vi phạm $\to$ Ký số RSA $\to$ Lưu DB (1/1 test passed).
  - [x] Toàn bộ 8/8 tests đạt 100% PASS.
  - [x] Xuất báo cáo nghiệm thu chi tiết, TUYỆT ĐỐI KHÔNG tự ý chạy `git push`.

---

## SPRINT 1: THIẾT KẾ KIẾN TRÚC DỮ LIỆU ĐA VAI TRÒ (RBAC) & AUTH ENGINE DOANH NGHIỆP (TASK-01 & TASK-02)
- [x] **Bước 1: Cập nhật Tài liệu Nguồn sự thật (SSOT Docs):**
  - [x] Cập nhật [`docs/DATABASE_DESIGN.md`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/docs/DATABASE_DESIGN.md): Vẽ lại sơ đồ ERD Mermaid chuẩn hóa quan hệ giữa các bảng `roles`, `users`, `exams`, `questions`, `submissions`, `violation_logs`. Từ điển dữ liệu cho `roles`, `users` (thay thế/bổ trợ bảng `students` cũ) và các chỉ mục (`idx_users_username`, `idx_users_role_id`, `idx_exams_created_by`).
  - [x] Cập nhật [`docs/SPEC.md`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/docs/SPEC.md): Bổ sung định dạng bản tin xác thực tài khoản qua giao thức TCP (Packet Header 23-byte): Opcode `REQ_AUTH_LOGIN` (`0x0007`) và `REQ_AUTH_REGISTER` (`0x0008`) kèm payload JSON và cấu trúc phản hồi.
- [x] **Bước 2: Tầng Dữ liệu & Repositories (`server/database/`):**
  - [x] Cập nhật [`server/database/schema.sql`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/server/database/schema.sql): DDL tạo mới bảng `roles` và tái cấu trúc bảng `users` với `password_hash` bcrypt/PBKDF2, `role_id` (FK), `email`, `rsa_public_key`, `face_embedding`, `status`. Tạo view `students` tương thích ngược.
  - [x] Cập nhật [`server/database/connection.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/server/database/connection.py): Bổ sung cơ chế auto-migration thêm cột `exams.created_by` và quản lý khóa ngoại an toàn khi thiết lập schema.
  - [x] Cập nhật [`server/database/repositories.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/server/database/repositories.py):
    - [x] `RoleRepository`: `get_or_create_role()`, `get_by_name()`, `get_by_id()`, `list_roles()`.
    - [x] `UserRepository`: `create_user()`, `get_by_username()`, `get_by_id()`, `verify_credentials()` (so khớp bcrypt/PBKDF2), `update_face_embedding()`, `update_public_key()`, `list_users()`.
    - [x] `StudentRepository`: Lớp bọc tương thích ngược (wrapper) ánh xạ sang `UserRepository`.
    - [x] `ExamRepository`: Bổ sung `created_by`.
    - [x] `SubmissionRepository` & `ViolationRepository`: Tự động phân giải `student_id` (MSSV) sang `user_id` qua `_resolve_user_id()`.
- [x] **Bước 3: Dịch vụ Xác thực & Hạt giống Dữ liệu (`server/services/auth_service.py` & `seed_data.py`):**
  - [x] Cập nhật [`server/services/auth_service.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/server/services/auth_service.py):
    - [x] Tích hợp băm mật khẩu `bcrypt` (kèm dự phòng chuẩn SHA256 PBKDF2-HMAC).
    - [x] Hàm `authenticate_user(username, password)`: Xác thực thông tin, sinh session token định dạng `f"{username}:{role}:{timestamp}:{hmac_sig}"`.
    - [x] Hàm `register_user(...)`: Kiểm tra username trùng lặp, băm mật khẩu an toàn và lưu vào DB.
    - [x] Hàm `verify_session_token(...)`: Xác thực tính toàn vẹn chữ ký HMAC và độ tươi mới của token.
    - [x] Hàm `authenticate_student(...)`: Duy trì tương thích ngược 100% cho luồng sinh trắc học Face ID.
  - [x] Cập nhật [`server/handlers/socket_handler.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/server/handlers/socket_handler.py): Tiếp nhận và xử lý `REQ_AUTH_LOGIN` và `REQ_AUTH_REGISTER`.
  - [x] Cập nhật [`server/database/seed_data.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/server/database/seed_data.py):
    - [x] Khởi tạo 3 vai trò hệ thống: `ADMIN`, `PROCTOR`, `STUDENT`.
    - [x] Khởi tạo 3 tài khoản mặc định băm mật khẩu bằng bcrypt:
      * `admin_gv` / `Admin@2026` (Vai trò: `ADMIN`)
      * `giamthi_01` / `Proctor@2026` (Vai trò: `PROCTOR`)
      * `SV2026_01` / `Student@2026` (Vai trò: `STUDENT`, nạp sẵn vector khuôn mặt 128-d)
    - [x] Khởi tạo kỳ thi `LTM_2026_FINAL` liên kết với `admin_gv` (`created_by=admin_id`).
- [x] **Bước 4: Kiểm thử Tự động (Unit Tests) & Nghiệm thu:**
  - [x] Tạo file kiểm thử mới [`tests/test_rbac_auth.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/tests/test_rbac_auth.py):
    1. Test khởi tạo DB và chèn đủ 3 vai trò (`ADMIN`, `PROCTOR`, `STUDENT`).
    2. Test đăng ký tài khoản mới và kiểm tra mật khẩu đã được băm an toàn trong DB (tuyệt đối không lưu plaintext).
    3. Test đăng nhập thành công với đúng vai trò và cấp token HMAC hợp lệ.
    4. Test từ chối truy cập khi nhập sai mật khẩu, tài khoản không tồn tại, hoặc đăng ký trùng lặp.
    5. Test bảo mật chống giả mạo session token (tampered token rejection).
  - [x] Chạy toàn bộ test suite (`discover tests`): 13/13 tests PASSED (100%).
  - [x] Tuân thủ kỷ luật: Dừng lại tại báo cáo nghiệm thu, **TUYỆT ĐỐI KHÔNG chạy lệnh `git push`**.
