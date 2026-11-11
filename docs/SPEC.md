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
| **Session & Auth** | `REQ_CONNECT` | `0x0001` | C $\to$ S | `{"student_id", "student_name", "public_key_pem"}` | Bắt tay kết nối khởi tạo, đăng ký Public Key của thí sinh. |
| | `RES_CONNECT_OK` | `0x0002` | S $\to$ C | `{"server_public_key_pem", "server_time_ms", "message"}` | Server chấp nhận kết nối, gửi Server Public Key. |
| | `RES_CONNECT_ERR` | `0x0003` | S $\to$ C | `{"error_code", "message"}` | Bắt tay thất bại (sai version, trùng session). |
| | `REQ_AUTH_LOGIN` | `0x0007` | C $\to$ S | `{"username", "password"}` | Xác thực tài khoản đa vai trò (ADMIN, PROCTOR, STUDENT) bằng mật khẩu băm bcrypt. |
| | `REQ_AUTH_REGISTER`| `0x0008` | C $\to$ S | `{"username", "password", "full_name", "role", "face_image_b64"}` | Đăng ký tài khoản người dùng mới vào hệ thống CSDL. |
| **Sinh trắc** | `REQ_AUTH_BIOMETRIC` | `0x0010` | C $\to$ S | `{"student_id", "match_confidence", "face_embedding"}` | Gửi kết quả so khớp khuôn mặt kèm vector đặc trưng 128 chiều. |
| | `RES_AUTH_SUCCESS` | `0x0011` | S $\to$ C | `{"status": "SUCCESS", "token", "role", "full_name", "user_id"}` | Cấp Token phiên có chữ ký HMAC, trả về vai trò và thông tin cá nhân. |
| | `RES_AUTH_FAILED` | `0x0012` | S $\to$ C | `{"status": "FAILED", "reason", "confidence"}` | Thất bại xác thực (sai mật khẩu, sai sinh trắc học). |
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

### 2.1. Đặc tả Chi tiết Bản tin Xác thực RBAC (`REQ_AUTH_LOGIN` & `REQ_AUTH_REGISTER`)

#### A. Bản tin Đăng nhập Đa vai trò (`REQ_AUTH_LOGIN` - `0x0007`)
- **Chiều:** Client $\to$ Server
- **Payload:**
```json
{
  "username": "SV2026_01",
  "password": "Student@2026"
}
```
- **Phản hồi Thành công (`RES_AUTH_SUCCESS` - `0x0011`):**
```json
{
  "status": "SUCCESS",
  "token": "SV2026_01:STUDENT:1794334000000:d3f4a...<hmac_sha256>",
  "role": "STUDENT",
  "full_name": "Nguyễn Văn A",
  "user_id": 3,
  "message": "Xác thực danh tính thành công."
}
```
- **Phản hồi Thất bại (`RES_AUTH_FAILED` - `0x0012`):**
```json
{
  "status": "FAILED",
  "reason": "Mật khẩu không chính xác hoặc tài khoản không tồn tại."
}
```

#### B. Bản tin Đăng ký Tài khoản (`REQ_AUTH_REGISTER` - `0x0008`)
- **Chiều:** Client $\to$ Server
- **Payload:**
```json
{
  "username": "giamthi_02",
  "password": "Proctor@2026",
  "full_name": "Trần Thị Cán Bộ",
  "role": "PROCTOR",
  "email": "giamthi02@exam.edu.vn",
  "face_image_b64": null
}
```
- **Phản hồi:**
```json
{
  "status": "SUCCESS",
  "message": "Đăng ký tài khoản thành công.",
  "user_id": 4
}
```

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

---

## 5. CƠ CHẾ TỰ ĐỘNG KHÁM PHÁ MẠNG LAN & ĐIỀU KHIỂN PHÒNG THI (ZERO-CONFIG LAN)

Để loại bỏ hoàn toàn việc thí sinh phải nhập địa chỉ IP máy chủ thủ công trong phòng thi, hệ thống sử dụng cơ chế **UDP Broadcast Auto-Discovery** chạy trên cổng `5006`:

### 5.1. Luồng Giao Thức Khám Phá (Discovery Protocol)
```
Client (Pre-flight Screen)                           Server (Broadcast Responder)
         |                                                       |
         |---- 1. UDP Broadcast (Port 5006) -------------------->|
         |     Payload: {"cmd": "DISCOVER_EXAM_SERVER"}          |
         |                                                       |
         |<--- 2. UDP Unicast/Broadcast Response ----------------|
         |     Payload: {                                        |
         |       "cmd": "SERVER_ANNOUNCEMENT",                   |
         |       "server_ip": "192.168.1.100",                   |
         |       "tcp_port": 8888,                               |
         |       "http_port": 8080,                              |
         |       "ws_port": 8081,                                |
         |       "exam_title": "Kỳ thi Cuối kỳ Lập trình Mạng"   |
         |     }                                                 |
         |                                                       |
 3. Tự động bind IP & Lưu `client_config.json`                   |
    (Fallback: Cho phép nhập thủ công nếu mạng chặn broadcast)   |
```

### 5.2. Cơ chế Đồng Hồ Cưỡng Chế Nộp Bài (Time-out & Multicast Auto-Submission)
Khi đồng hồ đếm ngược bài thi chạm mốc `00:00:00` hoặc khi nhận được gói tin UDP Multicast `CMD_EXAM_FINISH` (`0x0033`):
1. **Khóa Cương Tỏa Giao Diện:** Ngay lập tức gọi `setReadOnly(True)` trên mọi trường tự luận `QTextEdit`, vô hiệu hóa (`setEnabled(False)`) toàn bộ các nút trắc nghiệm `QRadioButton` và bảng chọn câu `Question Palette`.
2. **Tự Động Ký Số:** Thu thập đáp án hiện thời, chuẩn hóa JSON, băm `SHA-256`, tạo chữ ký số `RSA-2048 PSS` từ khóa riêng của thí sinh.
3. **Phát Gói Nộp Bài:** Bắn gói tin `SUBMIT_EXAM_PAPER` (`0x0050`) lên Server qua TCP Socket. Thí sinh tuyệt đối không thể bấm hủy (Cancel) hay hoãn nộp bài.

---

## 6. PHÒNG THỦ TẦNG SÂU HỆ ĐIỀU HÀNH (DEEP OS HARDENING VIA WIN32 API)

Tầng an ninh hệ điều hành trực tiếp can thiệp vào nhân Windows thông qua `ctypes` và Win32 API (`client_desktop/security/windows_guard.py`):

### 6.1. Nhận Diện Máy Ảo & Giám Sát Hypervisor (Anti-VM Detection)
* **Quét BIOS & Phần Cứng qua Registry:** Truy vấn khóa `HKEY_LOCAL_MACHINE\HARDWARE\Description\System\BIOS`:
  - `SystemManufacturer`, `SystemProductName`, `BIOSVersion`, `VideoBiosVersion`.
  - Từ khóa phát hiện máy ảo: `"VMware"`, `"VirtualBox"`, `"VBOX"`, `"QEMU"`, `"KVM"`, `"Hyper-V"`, `"Virtual Machine"`, `"Xen"`, `"Parallels"`.
* **Quét Tiền Tố Địa Chỉ MAC (OUI Filtering):** Duyệt qua các card mạng (`psutil.net_if_addrs()`):
  - `00:05:69`, `00:0C:29`, `00:50:56` (VMware).
  - `08:00:27` (VirtualBox).
  - `52:54:00` (QEMU / KVM).
  - `00:1C:42` (Parallels).
  - `00:15:5D` (Microsoft Hyper-V).
* **Xử lý:** Khi phát hiện chạy trong môi trường ảo hóa, ứng dụng lập tức từ chối cho phép vào thi và hiển thị cảnh báo vi phạm bảo mật cấp hệ thống.

### 6.2. Móc Bàn Phím Tầng Thấp (`WH_KEYBOARD_LL = 13`)
* Sử dụng Win32 API `SetWindowsHookExW` với loại hook `WH_KEYBOARD_LL`:
  - Chặn và nuốt (trả về `1` không chuyển tiếp): Phím Windows (`VK_LWIN = 0x5B`, `VK_RWIN = 0x5C`), `Alt + Tab` (kiểm tra flag `LLKHF_ALTDOWN`), `Alt + Esc`, `Ctrl + Esc`, các phím chức năng nguy hiểm `VK_F1` đến `VK_F12`.
* **Cơ chế An Toàn (Clean Cleanup):** Luôn đăng ký hàm dọn dẹp `UnhookWindowsHookEx` tại `atexit` và trong sự kiện kết thúc thi/đóng ứng dụng để không làm tê liệt bàn phím Windows sau kỳ thi.

### 6.3. Chống Quay Màn Hình & Chụp Lén (`SetWindowDisplayAffinity`)
* Gọi hàm `SetWindowDisplayAffinity(hwnd, WDA_MONITOR = 0x00000001)` hoặc `WDA_EXCLUDEFROMCAPTURE = 0x00000011` trên Handle (`winId()`) của cửa sổ Kiosk thi.
* **Hiệu Ứng Thực Tế:** Cửa sổ làm bài của thí sinh vẫn hiển thị bình thường trước mắt thí sinh trên màn hình vật lý, nhưng trên toàn bộ các phần mềm quay màn hình, chụp ảnh hay chia sẻ màn hình từ xa (OBS Studio, Discord Screen Share, Zoom, MS Teams, Windows Snipping Tool) sẽ bị hệ điều hành Windows che đen hoàn toàn (Blackout).

---

## 7. AI GIÁM SÁT ĐA PHƯƠNG THỨC (MULTI-MODAL VISION & AUDIO PROCTORING)

### 7.1. Kiểm Tra Liveness & Chớp Mắt (MediaPipe Face Mesh - EAR)
* Trích xuất tọa độ 3D của 6 điểm mốc trên mỗi mắt:
  - Mắt trái: `[33, 160, 158, 133, 153, 144]`.
  - Mắt phải: `[362, 385, 387, 263, 373, 380]`.
* Công thức tính tỉ lệ mở mắt **Eye Aspect Ratio (EAR)**:
  $$\text{EAR} = \frac{\|p_2 - p_6\| + \|p_3 - p_5\|}{2 \cdot \|p_1 - p_4\|}$$
* Khi thí sinh nhắm mắt (chớp mắt), $\text{EAR} < 0.20$.
* **Phát Hiện Ảnh Giả Mạo (Static Spoofing):** Nếu trong vòng 20 giây liên tục không ghi nhận bất kỳ lần chớp mắt tự nhiên nào, hệ thống cảnh báo nghi vấn sử dụng ảnh tĩnh/vật thể mô phỏng trước webcam (`STATIC_FACE_DETECTED`).

### 7.2. Nhận Diện Vật Thể Cấm Bằng ONNX Runtime (YOLOv8-Nano)
* Sử dụng mô hình `yolov8n.onnx` siêu nhẹ (kích thước ~6MB, chạy tối ưu hóa trên CPU):
  - Định kỳ chạy suy luận (Inference) mỗi **2 giây/lần** trong luồng xử lý riêng biệt để không làm giảm FPS webcam.
  - Theo dõi 2 đối tượng nguy hiểm: `cell phone` (điện thoại di động) và `person` (số lượng người trong khung hình $> 1$).
  - Khi phát hiện với độ tin cậy $> 0.50$, lập tức chụp ảnh snapshot, viền đỏ hộp chứa trên màn hình và gửi gói tin `REPORT_VIOLATION` lên Server.

### 7.3. Giám Sát Âm Thanh Môi Trường (Acoustic Monitoring)
* Thu âm ngầm từ Microphone phòng thi qua `sounddevice`:
  - Tính toán giá trị năng lượng âm thanh hiệu dụng Root Mean Square (RMS) trên từng khung thời gian 100ms:
    $$\text{RMS} = \sqrt{\frac{1}{N} \sum_{i=1}^{N} x_i^2}$$
  - Ngưỡng kích hoạt đàm thoại (Conversational Threshold): $\text{RMS} > 0.05$.
  - Nếu phát hiện âm lượng vượt ngưỡng liên tục trong thời gian $\ge 3$ giây, kích hoạt ghi nhật ký vi phạm `CONVERSATION_DETECTED` / `SUSPICIOUS_AUDIO`.

---

## 8. ĐA DẠNG HÓA LOẠI CÂU HỎI (EXAM UX & DATA STRUCTURE)

Hệ thống hỗ trợ đồng thời cả hai loại câu hỏi trong cùng một đề thi:
1. **Câu hỏi trắc nghiệm (`MULTIPLE_CHOICE`):** Thí sinh chọn đáp án thông qua `QRadioButton` nhóm trong `QButtonGroup`.
2. **Câu hỏi tự luận (`ESSAY`):** Thí sinh soạn thảo bài làm trong ô nhập văn bản đa dòng `QPlainTextEdit` có bộ đếm ký tự và tự động lưu từng ký tự gõ.
3. **Định dạng Lưu Trữ Nháp Cục Bộ (`exam_local_drafts.db`):**
   ```json
   {
     "exam_id": "LTM_2026_FINAL",
     "student_id": "SV2026_01",
     "answers": {
       "1": "B",
       "2": "C",
       "3": "UDP Multicast cho phép gửi 1 gói tin duy nhất tới nhóm địa chỉ 224.0.0.0/4..."
     },
     "last_saved_ms": 1794330500123
   }
   ```

