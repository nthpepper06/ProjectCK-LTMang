# THIẾT KẾ CƠ SỞ DỮ LIỆU BỀN VỮNG (DATABASE DESIGN SPECIFICATION)
## Nền tảng Khảo thí Trực tuyến An toàn & Giám sát AI (Persistent Storage Engine)

---

### 1. TỔNG QUAN & MỤC TIÊU
Tầng cơ sở dữ liệu (Database Layer) chịu trách nhiệm lưu trữ bền vững toàn bộ dữ liệu nghiệp vụ của kỳ thi, bao gồm:
- Hồ sơ sinh viên, vector sinh trắc học khuôn mặt (Face Embedding 128 chiều) và Khóa công khai RSA-2048 để đối soát chữ ký số.
- Ngân hàng đề thi và danh sách câu hỏi tự luận/trắc nghiệm có mã hóa.
- Nhật ký vi phạm thời gian thực kèm đường dẫn chứng cứ ảnh chụp từ AI Proctoring.
- Bản ghi nộp bài thi bảo đảm tính bất biến, toàn vẹn dữ liệu (SHA-256) và tính pháp lý chống chối bỏ (Non-repudiation) qua Chữ ký số kép (Candidate Digital Signature + Server Countersignature).

Hệ thống hỗ trợ chuẩn SQLite đa luồng (WAL mode) cho môi trường thi gọn nhẹ, độc lập và tương thích cấu trúc với PostgreSQL khi mở rộng quy mô lớn.

---

### 2. SƠ ĐỒ THỰC THỂ QUAN HỆ (ERD - ENTITY RELATIONSHIP DIAGRAM)

```mermaid
erDiagram
    students ||--o{ submissions : "submits"
    students ||--o{ violation_logs : "commits"
    exams ||--o{ questions : "contains"
    exams ||--o{ submissions : "receives"
    exams ||--o{ violation_logs : "monitored_in"

    students {
        INTEGER id PK "Tự tăng"
        VARCHAR student_id UK "Mã sinh viên duy nhất (MSSV)"
        VARCHAR full_name "Họ và tên thí sinh"
        TEXT rsa_public_key "Khóa công khai RSA 2048-bit định dạng PEM"
        BLOB face_embedding "Vector đặc trưng khuôn mặt (128 floats dạng nhị phân)"
        DATETIME created_at "Thời điểm đăng ký hồ sơ"
    }

    exams {
        INTEGER id PK "Tự tăng"
        VARCHAR exam_code UK "Mã kỳ thi (VD: LTM_2026_FINAL)"
        VARCHAR title "Tên kỳ thi"
        DATETIME start_time "Thời điểm mở ca thi"
        INTEGER duration_minutes "Thời lượng làm bài (phút)"
        BOOLEAN is_active "Trạng thái ca thi đang mở (1: Active, 0: Closed)"
        DATETIME created_at "Thời điểm tạo ca thi"
    }

    questions {
        INTEGER id PK "Tự tăng"
        INTEGER exam_id FK "Liên kết bảng exams(id)"
        INTEGER question_index "Thứ tự câu hỏi trong đề"
        TEXT content "Nội dung câu hỏi đề thi"
        TEXT question_type "Loại câu: essay / multiple_choice"
        TEXT options_json "Các lựa chọn trắc nghiệm (JSON String)"
        TEXT correct_answer_hash "Mã băm/mã hóa đáp án chính xác"
    }

    submissions {
        INTEGER id PK "Tự tăng"
        INTEGER exam_id FK "Liên kết bảng exams(id)"
        VARCHAR student_id FK "Liên kết bảng students(student_id)"
        TEXT answers_payload "Toàn bộ bài làm thí sinh (Canonical JSON)"
        VARCHAR sha256_hash "Mã băm toàn vẹn SHA-256 của bài làm"
        TEXT digital_signature "Chữ ký số RSA-2048 PSS của Thí sinh (Base64)"
        TEXT server_receipt_signature "Chữ ký số xác nhận của Máy chủ (Base64)"
        INTEGER submitted_at_ms "Dấu thời gian chuẩn mili-giây"
        VARCHAR status "Trạng thái: VERIFIED / REJECTED"
        DATETIME created_at "Thời điểm ghi nhận vào CSDL"
    }

    violation_logs {
        INTEGER id PK "Tự tăng"
        VARCHAR student_id FK "Liên kết bảng students(student_id)"
        INTEGER exam_id FK "Liên kết bảng exams(id)"
        VARCHAR violation_type "Loại vi phạm: NO_FACE, MULTIPLE_FACES, LOOKING_AWAY, PROHIBITED_PROCESS"
        REAL suspicion_score "Điểm nghi vấn từ AI (0.0 đến 1.0)"
        VARCHAR details "Mô tả chi tiết hành vi vi phạm"
        VARCHAR evidence_path "Đường dẫn file ảnh snapshot chứng cứ"
        INTEGER timestamp_ms "Thời điểm vi phạm (mili-giây)"
        DATETIME created_at "Thời điểm máy chủ ghi nhận"
    }
```

---

### 3. ĐẶC TẢ CHI TIẾT CÁC BẢNG DỮ LIỆU (DATA DICTIONARY)

#### 3.1. Bảng `students` (Hồ sơ Thí sinh & Sinh trắc học)
Lưu trữ thông tin nhận dạng thí sinh, vector khuôn mặt đăng ký trước và khóa công khai RSA.

| Cột | Kiểu dữ liệu | Ràng buộc (Constraints) | Mô tả |
|---|---|---|---|
| `id` | `INTEGER` | PRIMARY KEY AUTOINCREMENT | Khóa chính tự tăng |
| `student_id` | `VARCHAR(32)` | NOT NULL, UNIQUE | Mã số sinh viên (MSSV) |
| `full_name` | `VARCHAR(128)` | NOT NULL | Họ và tên sinh viên |
| `rsa_public_key`| `TEXT` | NULLABLE | Khóa công khai RSA-2048 (PEM format) trao đổi khi kết nối |
| `face_embedding`| `BLOB` | NULLABLE | Vector 128 số thực biểu diễn đặc trưng khuôn mặt đã đăng ký |
| `created_at` | `DATETIME` | DEFAULT CURRENT_TIMESTAMP | Thời điểm thêm vào hệ thống |

#### 3.2. Bảng `exams` (Ca thi & Đề thi)
Quản lý các ca thi, thời lượng và trạng thái kích hoạt đề thi.

| Cột | Kiểu dữ liệu | Ràng buộc (Constraints) | Mô tả |
|---|---|---|---|
| `id` | `INTEGER` | PRIMARY KEY AUTOINCREMENT | Khóa chính ca thi |
| `exam_code` | `VARCHAR(64)` | NOT NULL, UNIQUE | Mã định danh đề thi (VD: `LTM_2026_FINAL`) |
| `title` | `VARCHAR(255)` | NOT NULL | Tiêu đề kỳ thi |
| `start_time` | `DATETIME` | NULLABLE | Giờ mở phòng thi |
| `duration_minutes` | `INTEGER` | NOT NULL DEFAULT 60 | Thời lượng làm bài tính bằng phút |
| `is_active` | `BOOLEAN` | NOT NULL DEFAULT 1 | 1 nếu đang cho phép thi, 0 nếu đã đóng |
| `created_at` | `DATETIME` | DEFAULT CURRENT_TIMESTAMP | Thời điểm tạo ca thi |

#### 3.3. Bảng `questions` (Chi tiết Câu hỏi trong Đề)
Lưu danh sách câu hỏi thuộc từng đề thi, hỗ trợ cả tự luận (essay) và trắc nghiệm.

| Cột | Kiểu dữ liệu | Ràng buộc (Constraints) | Mô tả |
|---|---|---|---|
| `id` | `INTEGER` | PRIMARY KEY AUTOINCREMENT | Khóa chính câu hỏi |
| `exam_id` | `INTEGER` | NOT NULL, FK `exams(id)` ON DELETE CASCADE | Ca thi sở hữu câu hỏi |
| `question_index` | `INTEGER` | NOT NULL | Số thứ tự câu hỏi (Câu 1, Câu 2,...) |
| `content` | `TEXT` | NOT NULL | Nội dung câu hỏi đề thi |
| `question_type` | `VARCHAR(32)` | DEFAULT 'essay' | Kiểu câu hỏi: `essay` hoặc `multiple_choice` |
| `options_json` | `TEXT` | NULLABLE | Danh sách đáp án A, B, C, D (JSON format) |
| `correct_answer_hash` | `TEXT` | NULLABLE | Hash SHA-256 của đáp án đúng để chấm tự động |

#### 3.4. Bảng `submissions` (Bài nộp & Chữ ký số Chống chối bỏ)
Bảng quan trọng nhất ghi nhận bài làm cuối cùng. Đảm bảo tính pháp lý thông qua mã băm và chữ ký kép.

| Cột | Kiểu dữ liệu | Ràng buộc (Constraints) | Mô tả |
|---|---|---|---|
| `id` | `INTEGER` | PRIMARY KEY AUTOINCREMENT | Khóa chính bài nộp |
| `exam_id` | `INTEGER` | NOT NULL, FK `exams(id)` | Khóa ngoại tới đề thi |
| `student_id` | `VARCHAR(32)` | NOT NULL, FK `students(student_id)` | Mã sinh viên nộp bài |
| `answers_payload`| `TEXT` | NOT NULL | Toàn bộ câu trả lời (JSON định dạng chuẩn hóa) |
| `sha256_hash` | `VARCHAR(64)` | NOT NULL | Giá trị băm SHA-256 của `answers_payload` |
| `digital_signature` | `TEXT` | NOT NULL | Chữ ký số RSA-2048 PSS của thí sinh |
| `server_receipt_signature` | `TEXT` | NOT NULL | Chữ ký số đối ứng của Máy chủ xác nhận biên lai |
| `submitted_at_ms` | `INTEGER` | NOT NULL | Thời gian nộp chuẩn mili-giây |
| `status` | `VARCHAR(32)` | DEFAULT 'VERIFIED' | Trạng thái kiểm tra: `VERIFIED` hoặc `REJECTED` |
| `created_at` | `DATETIME` | DEFAULT CURRENT_TIMESTAMP | Thời điểm ghi DB |

#### 3.5. Bảng `violation_logs` (Nhật ký Giám sát An ninh AI)
Ghi nhận mọi sự kiện vi phạm hoặc hành vi đáng ngờ được phát hiện từ phía Client.

| Cột | Kiểu dữ liệu | Ràng buộc (Constraints) | Mô tả |
|---|---|---|---|
| `id` | `INTEGER` | PRIMARY KEY AUTOINCREMENT | Khóa chính vi phạm |
| `student_id` | `VARCHAR(32)` | NOT NULL, FK `students(student_id)` | Thí sinh có hành vi nghi vấn |
| `exam_id` | `INTEGER` | NOT NULL, FK `exams(id)` | Ca thi xảy ra vi phạm |
| `violation_type` | `VARCHAR(64)` | NOT NULL | Mã vi phạm (`LOOKING_AWAY`, `PROHIBITED_PROCESS`,...) |
| `suspicion_score` | `REAL` | DEFAULT 1.0 | Điểm nghi vấn từ 0.0 đến 1.0 |
| `details` | `TEXT` | NULLABLE | Mô tả chi tiết tiến trình vi phạm hoặc góc quay đầu |
| `evidence_path` | `VARCHAR(255)` | NULLABLE | Đường dẫn lưu ảnh bằng chứng JPEG trên máy chủ |
| `timestamp_ms` | `INTEGER` | NOT NULL | Thời điểm xảy ra vi phạm (mili-giây) |
| `created_at` | `DATETIME` | DEFAULT CURRENT_TIMESTAMP | Thời điểm máy chủ ghi nhận |

---

### 4. CHIẾN LƯỢC ĐÁNH CHỈ MỤC & TỐI ƯU HIỆU NĂNG (INDEXING STRATEGY)

Để đảm bảo máy chủ phản hồi trong vòng < 5ms ngay cả khi có hàng trăm kết nối đồng thời:
1. `idx_students_student_id` trên `students(student_id)`: Tăng tốc đối soát thông tin đăng nhập và lấy Public Key.
2. `idx_exams_exam_code` trên `exams(exam_code)`: Tăng tốc tìm kiếm ca thi đang mở.
3. `idx_questions_exam_id` trên `questions(exam_id, question_index)`: Lấy toàn bộ đề thi được sắp xếp chuẩn xác chỉ bằng 1 câu truy vấn index scan.
4. `idx_submissions_student_exam` trên `submissions(student_id, exam_id)`: Ràng buộc mỗi thí sinh chỉ có 1 bài nộp chính thức hợp lệ cho 1 đề thi.
5. `idx_violations_student_exam` trên `violation_logs(student_id, exam_id, timestamp_ms)`: Tối ưu cho dashboard giám thị lọc nhật ký vi phạm theo từng thí sinh theo trình tự thời gian.

---

### 5. KIẾN TRÚC TRUY CẬP ĐA LUỒNG AN TOÀN (CONCURRENCY SAFETY)

- **Chế độ WAL (Write-Ahead Logging):** Kích hoạt `PRAGMA journal_mode=WAL;`. Chế độ này cho phép nhiều luồng đọc (Readers) thực hiện đồng thời mà không bị chặn bởi luồng ghi (Writer).
- **Busy Timeout:** Kích hoạt `PRAGMA busy_timeout=5000;`. Khi có luồng đang thực hiện Transaction ghi, các luồng khác sẽ chờ tối đa 5000ms thay vì văng lỗi `SQLITE_BUSY`.
- **Thread-Local Connection Isolation:** Mỗi luồng xử lý socket (`Client-Handler Thread`) sở hữu một kết nối `sqlite3.Connection` riêng biệt thông qua `threading.local()`, tránh hoàn toàn lỗi chia sẻ socket/connection giữa các luồng trong Python.
- **Write Transaction Serialization Lock:** Sử dụng `threading.Lock()` bao quanh các tác vụ ghi nhạy cảm (Ghi bài thi, lưu biên lai) nhằm bảo đảm tính ACID và ngăn ngừa race condition tuyệt đối.
