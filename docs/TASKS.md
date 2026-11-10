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
