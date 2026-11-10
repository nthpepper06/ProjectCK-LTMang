# AI Proctoring & Secure Examination Platform Implementation Plan

> **Execution:** Follow this plan task-by-task within the user-authorized scope. If the installed environment provides an executing-plans skill, read it before use; this catalog entry does not bundle that dependency.

**Goal:** Xây dựng hệ thống thi trực tuyến an toàn & giám sát chống gian lận thông minh gồm Desktop Exam Client (PyQt6 + MediaPipe), Multi-thread TCP Server, UDP Multicast broadcast, Chữ ký số RSA/Mã hóa AES, và Proctor Web Dashboard thời gian thực.

**Architecture:** Kiến trúc Client-Server phân tán kết hợp Peer/Multicast:
1. Multi-Thread TCP Server quản lý kết nối tin cậy (phiên thi, heartbeat, nộp bài có chữ ký số RSA, nhật ký gian lận).
2. UDP Multicast (224.1.1.1:5005) dùng cho kênh phát lệnh tập trung từ Giám thị (Start, Pause, Finish).
3. Client Kiosk (PyQt6) tích hợp luồng nền AI FaceMesh (MediaPipe) giám sát tư thế đầu/hướng mắt/số lượng người và chống thoát ứng dụng (anti-alt-tab, focus-lost).
4. Proctor Dashboard thông qua WebSocket hiển thị cảnh báo thời gian thực và hình ảnh chứng cứ.

**Tech Stack:** Python 3.10+, PyQt6, OpenCV (cv2), MediaPipe, Cryptography (RSA 2048, SHA-256, AES-256-GCM), Sockets (TCP/UDP Multicast), WebSockets / HTML5.

---

### Task 1: Thiết lập cấu trúc thư mục dự án và protocol cốt lõi
- Tạo các package `common/`, `server/`, `client_desktop/`, `proctor_web/`, `docs/`.
- Định nghĩa binary header chuẩn hóa (Magic bytes, Command ID, Seq, Timestamp, Payload Length) và parser trong `common/protocol.py`.
- Viết tiện ích mật mã `common/crypto_utils.py` (sinh khóa RSA, băm SHA-256, ký/xác thực chữ ký số, mã hóa/giải mã AES).

### Task 2: Xây dựng Multi-thread TCP Server & UDP Multicast Broadcast
- Tạo `server/tcp_server.py` hỗ trợ quản lý đa luồng client đồng thời, xác thực sinh trắc học, nhận nhịp tim heartbeat, nhận bài nộp kèm chữ ký số và phản hồi biên nhận có chữ ký server.
- Tạo `server/multicast_sender.py` gửi lệnh broadcast (BẮT ĐẦU THI, TẠM DỪNG, NỘP BÀI) tới toàn bộ phòng thi qua UDP Multicast IP.

### Task 3: Xây dựng Kiosk Exam Client & AI Proctoring Thread
- Tạo `client_desktop/ai_proctor_thread.py`: `QThread` chạy ngầm phân tích webcam (đếm khuôn mặt, ước lượng góc quay đầu Yaw/Pitch/Roll, phát hiện mắt nhìn lệch hướng).
- Tạo `client_desktop/multicast_listener.py`: Lắng nghe lệnh UDP Multicast 224.1.1.1:5005 từ Giám thị.
- Tạo `client_desktop/network_client.py`: Quản lý kết nối TCP, trao đổi khóa RSA, gửi nhịp tim và nộp bài kèm chữ ký điện tử.
- Tạo `client_desktop/main_window.py`: Giao diện thi Kiosk Mode toàn màn hình, chặn phím tắt nguy hiểm, phát hiện mất focus cửa sổ.

### Task 4: Xây dựng Proctor Web Dashboard & WebSocket Alert Hub
- Tạo `proctor_web/dashboard_server.py`: WebSocket server chuyển tiếp sự kiện vi phạm từ TCP Server tới trình duyệt giám thị.
- Tạo `proctor_web/index.html`: Giao diện Dashboard hiển thị danh sách thí sinh, trạng thái thi, nhật ký vi phạm và ảnh bằng chứng thời gian thực.
