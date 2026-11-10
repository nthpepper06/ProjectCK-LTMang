# ĐẶC TẢ KỸ THUẬT GIAO THỨC & AN NINH HỆ THỐNG
# (TECHNICAL SPECIFICATION: NETWORK PROTOCOL & CRYPTOGRAPHY)

> **Dự án:** Smart AI Proctoring & Secure Examination Platform  
> **Cấp độ kiến trúc:** Level 6 Spec-Driven / Single Source of Truth (SSOT)  
> **Tài liệu tham chiếu:** [ARCHITECTURE.md](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/docs/ARCHITECTURE.md), [DATABASE_DESIGN.md](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/docs/DATABASE_DESIGN.md)

---

## 1. QUY CHUẨN ĐÓNG GÓI NHỊ PHÂN TCP 23-BYTE HEADER

Mọi gói tin trao đổi qua socket TCP giữa Kiosk Desktop Client và Server đều bắt buộc tuân thủ cấu trúc nhị phân tiền tố cố định **23 bytes**, biểu diễn theo thứ tự **Network Byte Order (Big-Endian)**.

### 1.1. Định dạng Nhị Phân (`struct: !4sBHIQI`)

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                    Magic Identifier (4B)                      |
|                      b"EXAM" (0x4558414D)                     |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|  Version (1B) |       Command Type (2B, uint16)               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                 Sequence Number / Nonce (4B, uint32)          |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                                                               |
+                   Timestamp in ms (8B, uint64)                +
|                                                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                  Payload Length (4B, uint32)                  |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                                                               |
+                        PAYLOAD BYTES                          +
|                    (JSON UTF-8 / Raw Bytes)                   |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

### 1.2. Bảng Phân Tích Trường Dữ Liệu Header (Field Breakdown)

| Byte Offset | Độ dài (Bytes) | Trường dữ liệu | Kiểu dữ liệu | Mô tả kỹ thuật |
| :---: | :---: | :--- | :--- | :--- |
| `0 - 3` | 4 | **Magic Identifier** | `char[4]` | Bắt buộc là chuỗi `b"EXAM"` (`0x45 0x58 0x41 0x4D`). Gói tin không khớp Magic sẽ bị hủy ngay để chống quét cổng rác. |
| `4` | 1 | **Protocol Version** | `uint8` (`B`) | Phiên bản giao thức hiện tại là `0x01`. Cho phép nâng cấp Backward Compatibility sau này. |
| `5 - 6` | 2 | **Command Type** | `uint16` (`H`) | Định danh mã lệnh (16-bit Opcode), phân luồng xử lý tại tầng Router [`SocketHandler`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/server/handlers/socket_handler.py). |
| `7 - 10` | 4 | **Sequence / Nonce** | `uint32` (`I`) | Số thứ tự tăng dần hoặc giá trị Nonce ngẫu nhiên, chống tấn công phát lại (Replay Attack). |
| `11 - 18` | 8 | **Timestamp (ms)** | `uint64` (`Q`) | Thời gian gửi gói tin theo mili-giây Unix Epoch UTC. Dùng để đối soát độ trễ (Latency/Ping). |
| `19 - 22` | 4 | **Payload Length** | `uint32` (`I`) | Kích thước chính xác của phần thân gói tin (Payload) theo byte ($0 \le N \le 16\text{ MB}$). |
| `23 - (23+N)`| $N$ | **Payload** | `bytes` | Dữ liệu nghiệp vụ mã hóa UTF-8 JSON hoặc mảng byte nhị phân. |

---

## 2. BẢNG ĐẶC TẢ DANH MỤC MÃ LỆNH (PACKET COMMAND OPCODES)

Các mã lệnh được định nghĩa tập trung tại [`common/protocol.py`](file:///C:/Users/PC/OneDrive/Documents/LapTrinhMang_Project/common/protocol.py):

| Nhóm nghiệp vụ | Tên mã lệnh (`CommandType`) | Mã Hex | Chiều truyền | Cấu trúc Payload chính | Ý nghĩa & Mô tả |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **Session** | `REQ_CONNECT` | `0x0001` | C $\to$ S | `{"student_id", "student_name", "public_key_pem"}` | Bắt tay kết nối khởi tạo, đăng ký Public Key của thí sinh. |
| | `RES_CONNECT_OK` | `0x0002` | S $\to$ C | `{"server_public_key_pem", "server_time_ms", "message"}` | Server chấp nhận kết nối, gửi Server Public Key. |
| | `RES_CONNECT_ERR` | `0x0003` | S $\to$ C | `{"error_code", "message"}` | Bắt tay thất bại (sai version, trùng session). |
| **Sinh trắc** | `REQ_AUTH_BIOMETRIC` | `0x0010` | C $\to$ S | `{"student_id", "match_confidence", "face_embedding"}` | Gửi kết quả so khớp khuôn mặt kèm vector đặc trưng 128 chiều. |
| | `RES_AUTH_SUCCESS` | `0x0011` | S $\to$ C | `{"session_token", "confidence", "message"}` | Cấp Token phiên có chữ ký HMAC, mở khóa vào phòng thi. |
| | `RES_AUTH_FAILED` | `0x0012` | S $\to$ C | `{"reason", "confidence"}` | Thất bại sinh trắc học, từ chối cấp đề. |
| **Giám sát mạng** | `PING` | `0x0020` | C $\to$ S | `{"seq", "client_time_ms"}` | Gói tin nhịp tim giữ kết nối (Heartbeat) định kỳ 5s. |
| | `PONG` | `0x0021` | S $\to$ C | `{"echo", "server_timestamp_ms"}` | Phản hồi nhịp tim, reset Watchdog Timer trên Server. |
| | `TIME_SYNC` | `0x0022` | S $\to$ C | `{"ntp_time_ms"}` | Đồng bộ giờ làm bài chính xác. |
| **Đề & Bài thi** | `REQ_EXAM_PAPER` | `0x0040` | C $\to$ S | `{"exam_id", "student_id"}` | Yêu cầu phát đề thi sau khi đã Authenticated. |
| | `RES_EXAM_PAPER` | `0x0041` | S $\to$ C | `{"exam_id", "title", "duration_minutes", "questions": [...]}` | Gói đề thi hoàn chỉnh chứa các câu hỏi trắc nghiệm/tự luận. |
| | `SUBMIT_EXAM_PAPER` | `0x0050` | C $\to$ S | `{"student_id", "answers", "paper_hash", "signature"}` | Nộp bài kèm mã băm SHA-256 và chữ ký số RSA thí sinh. |
| | `SUBMIT_ACK` | `0x0051` | S $\to$ C | `{"receipt", "server_signature", "student_signature"}` | Cấp biên lai nộp bài có chữ ký số xác thực của Server. |
| **Cảnh báo AI** | `REPORT_VIOLATION` | `0x0060` | C $\to$ S | `{"violation_type", "suspicion_score", "evidence_image_b64"}` | Gửi log gian lận MediaPipe kèm ảnh chụp snapshot webcam. |
| | `VIOLATION_ACK` | `0x0061` | S $\to$ C | `{"status": "LOGGED", "evidence_saved"}` | Xác nhận đã lưu bằng chứng vào kho máy chủ. |
| **Kết thúc** | `DISCONNECT` | `0x0099` | C $\to$ S | `{"reason"}` | Ngắt kết nối có kiểm soát. |

---

## 3. QUY CHUẨN ĐIỀU KHIỂN PHÒNG THI QUA UDP MULTICAST

Giao thức phát thông điệp đồng loạt không định hướng (One-to-Many Broadcasting) sử dụng UDP Multicast để giải quyết bài toán đồng bộ thời gian thực cho hàng trăm máy thí sinh trong cùng phân mạng LAN:

* **Địa chỉ Multicast Group:** `224.1.1.1`
* **Cổng dịch vụ (Port):** `5005`
* **Socket Options:**
  - `IP_MULTICAST_TTL = 2` (Giới hạn trong mạng trường/phòng thi).
  - `SO_REUSEADDR = 1` (Cho phép bind nhiều socket kiểm thử trên cùng host).
  - Tham gia nhóm qua `struct ip_mreq`: `inet_aton("224.1.1.1") + inet_aton("0.0.0.0")`.

### Danh mục lệnh Multicast Lifecycle

| Lệnh Multicast | Opcode | Tham số Payload | Hành vi Kiosk Client |
| :--- | :---: | :--- | :--- |
| `CMD_EXAM_START` | `0x0030` | `{"exam_id", "duration_minutes", "start_time_ms"}` | Đồng loạt mở khóa đề thi, hiển thị Palette và đếm ngược đồng hồ. |
| `CMD_EXAM_PAUSE` | `0x0031` | `{"reason", "paused_at_ms"}` | Khóa màn hình làm bài, phủ bảng thông báo tạm dừng khẩn cấp. |
| `CMD_EXAM_RESUME` | `0x0032` | `{"added_minutes", "resumed_at_ms"}` | Mở khóa tiếp tục, cộng bù thêm phút làm bài vào đồng hồ. |
| `CMD_EXAM_FINISH` | `0x0033` | `{"message", "force_submit": true}` | Đóng bài thi ngay lập tức, tự động ký số RSA và gửi bài lên Server. |
| `CMD_ANNOUNCEMENT` | `0x0034` | `{"message", "timestamp_ms"}` | Hiển thị Banner/Popup thông báo chữ to từ Giám thị trên Kiosk. |

---

## 4. QUY CHUẨN MẬT MÃ CHỮ KÝ SỐ ĐỐI ỨNG (NON-REPUDIATION ARCHITECTURE)

Hệ thống triển khai mô hình **Chống chối bỏ kép (Dual Non-Repudiation)**:

```
Thí sinh (Client)                                          Máy chủ (Server)
+-----------------------+                                  +-----------------------+
|  1. Chuẩn hóa JSON    |                                  |                       |
|     (Canonicalize)    |                                  |                       |
|          v            |                                  |                       |
|  2. SHA-256 Digest    |                                  |                       |
|     $H_{paper}$       |                                  |                       |
|          v            |                                  |                       |
|  3. Ký số RSA-2048    |                                  |                       |
|     (PSS + SHA-256)   |                                  |                       |
|     $S_{student}$     |        Gói tin SUBMIT            |                       |
|          |------------|--------------------------------->|  4. Lấy Public Key    |
|                       |  {"answers", $H$, $S_{student}$} |     thí sinh từ DB    |
|                       |                                  |          v            |
|                       |                                  |  5. Đối soát chữ ký   |
|                       |                                  |     $S_{student}$ OK? |
|                       |                                  |          v            |
|                       |                                  |  6. Tạo Biên lai điện |
|                       |                                  |     tử (Receipt)      |
|                       |                                  |          v            |
|                       |                                  |  7. Server Countersign|
|                       |        Gói tin SUBMIT_ACK        |     $S_{server}$      |
|  8. Nhận biên lai kép |<---------------------------------|     (PSS + SHA-256)   |
|     & Lưu trữ Offline |  {"receipt", $S_{server}$, $S$}  |          v            |
|     Tạo mã QR tra cứu |                                  |  8. Ghi DB (WAL Tx)   |
+-----------------------+                                  +-----------------------+
```

### 4.1. Quy chuẩn Chữ ký Thí sinh ($S_{student}$)
1. **Dữ liệu ký:** Chuỗi Byte JSON của đáp án sau khi sắp xếp khóa cố định (`json.dumps(answers, sort_keys=True).encode("utf-8")`).
2. **Thuật toán băm:** `SHA-256` ($256\text{-bit}$ cryptographic hash).
3. **Thuật toán ký:** `RSA-2048` với sơ đồ đệm an toàn `PSS (Probabilistic Signature Scheme)`:
   - Mask Generation Function: `MGF1(hashes.SHA256())`.
   - Salt Length: `PSS.MAX_LENGTH`.
4. **Mục đích:** Chứng minh bài làm xuất phát từ duy nhất khóa riêng của thí sinh, không bị sửa đổi trên đường truyền.

### 4.2. Quy chuẩn Chữ ký Biên lai Server ($S_{server}$ - Countersignature)
1. **Dữ liệu ký:** Chuỗi Byte JSON của bản ghi biên lai gồm:
   - `receipt_id`: Chuỗi định danh duy nhất (`REC_{MSSV}_{TIMESTAMP}`).
   - `student_id`: MSSV thí sinh.
   - `paper_hash`: Mã băm SHA-256 của bài làm.
   - `submitted_at_ms`: Dấu thời gian tiếp nhận bài nộp có giá trị pháp lý.
2. **Khóa ký:** Khóa riêng tư RSA-2048 chính thức của Hội đồng thi (`server_private_key.pem`).
3. **Mục đích:** Ngăn chặn hội đồng thi chối bỏ việc đã tiếp nhận bài thi của thí sinh; thí sinh dùng biên lai này làm bằng chứng đối chất.
