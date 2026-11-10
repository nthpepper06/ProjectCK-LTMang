# Production-Ready AI Proctoring & Secure Examination Platform Implementation Plan

> **Execution:** Follow this plan task-by-task within the user-authorized scope. If the installed environment provides an executing-plans skill, read it before use; this catalog entry does not bundle that dependency.

**Goal:** Nâng cấp hệ thống Khảo thí Trực tuyến & Giám sát Chống Gian lận Thông minh thành Production-Ready Desktop Application gồm 4 màn hình vòng đời thi cử (QStackedWidget), an ninh tầng OS (Multi-Monitor Blocker, Process Watchdog qua psutil, Clipboard Hook), SQLite Local Auto-Save, Network Auto-Reconnect, QR Code Receipt, cùng bộ kiểm thử toàn diện và quy trình Git chuẩn.

**Architecture:** 
1. Client Desktop tái cấu trúc theo mô hình phân tầng: `client_desktop/security/` (Watchdog, Screen Blocker, Clipboard), `client_desktop/storage/` (SQLite Encrypted Drafts), `client_desktop/ui/` (QStackedWidget: Preflight -> Biometric Login -> Exam View with Question Palette -> Audit Receipt with QR Code).
2. Server Core mở rộng với Multi-Threaded TCP Server (quản lý JWT/Session token, chữ ký RSA 2048-bit, countersigned receipt) và UDP Multicast Controller 224.1.1.1:5005.
3. Cryptography & Protocol: Binary Header 23-byte, mã hóa AES-256-GCM, chữ ký SHA-256 PSS.

**Tech Stack:** Python 3.10+, PyQt6, OpenCV (cv2), MediaPipe, Cryptography, psutil, qrcode (PIL), SQLite3, Sockets (TCP/UDP Multicast).

---

### Task 1: Module An ninh tầng Hệ điều hành (OS-Level Security)
**Files:**
- Create: `client_desktop/security/__init__.py`
- Create: `client_desktop/security/monitor_blocker.py`
- Create: `client_desktop/security/process_watchdog.py`
- Create: `client_desktop/security/clipboard_hook.py`

### Task 2: Module Lưu trữ cục bộ & Tự động lưu nháp (Local Storage & Auto-Save)
**Files:**
- Create: `client_desktop/storage/__init__.py`
- Create: `client_desktop/storage/local_db.py`

### Task 3: Tái cấu trúc Giao diện Client Desktop với 4 Màn hình (QStackedWidget)
**Files:**
- Create: `client_desktop/ui/__init__.py`
- Create: `client_desktop/ui/screen_preflight.py` (Screen 1: Camera, Mic, Server Ping < 100ms, Battery, Single Monitor)
- Create: `client_desktop/ui/screen_login.py` (Screen 2: Form MSSV, căn khung mặt, Face embedding match, nhận Session Token)
- Create: `client_desktop/ui/screen_exam.py` (Screen 3: Question Palette lưới, Auto-save 15s, Widget mạng auto-reconnect, Modal nộp bài)
- Create: `client_desktop/ui/screen_receipt.py` (Screen 4: Timestamp ms, Hash SHA-256, Chữ ký RSA, Mã QR tra cứu)
- Modify: `client_desktop/main_window.py` (Tích hợp QStackedWidget điều phối 4 màn hình, Kiosk Fullscreen, Focus Lost)

### Task 4: Hoàn thiện Server Core & Network Protocol
**Files:**
- Modify: `server/tcp_server.py` (Hỗ trợ cấp Session Token, xử lý ngắt kết nối an toàn, lưu trữ bài thi và biên lai)
- Modify: `server/multicast_sender.py` (Hoàn thiện bộ phát lệnh Multicast phòng thi)
- Modify: `common/crypto_utils.py` (Tối ưu hóa các hàm RSA, SHA-256, AES-256-GCM)

### Task 5: Rà soát & Kiểm thử Tích hợp Tự động (@verification-before-completion)
**Files:**
- Modify: `tests/test_integration.py` (Mở rộng test: Security Watchdog, Multi-screen check, SQLite local draft, QR Code)
- Test: Chạy toàn bộ test suite để đảm bảo 0 lỗi.

### Task 6: Tài liệu hóa & Quy trình Git Commit (@git-pushing)
**Files:**
- Create: `.gitignore`
- Create: `README.md`
- Create: `requirements.txt`
- Git: `git init`, `git add`, `git commit -m "feat: complete full-lifecycle proctoring desktop app and multi-thread server"`, `git push`.
