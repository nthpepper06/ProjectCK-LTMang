# Task Plan: System Architecture, Persistent Database & Layered Backend

## Goal
Transform the system from an ad-hoc in-memory server to an enterprise-grade, layered Client-Server architecture with persistent database storage, repository pattern, multi-threading safety, and formal architecture documentation.

## Phase 1: Planning with Files & Architecture Documentation
- [x] Initialize `task_plan.md`, `findings.md`, `progress.md`
- [x] Create `docs/ARCHITECTURE.md`
  - System Component Diagram (Mermaid)
  - Sequence Diagram (Mermaid)
  - Session State Machine (Mermaid & tabular analysis)
- [x] Create `docs/DATABASE_DESIGN.md`
  - ERD Diagram (Mermaid)
  - Table schemas (`students`, `exams`, `questions`, `submissions`, `violation_logs`)
  - Indexing and constraints strategy

## Phase 2: Persistent Database Implementation (`server/database/`)
- [x] Create `server/database/schema.sql` with SQLite/Postgres compatibility, foreign keys, indexes
- [x] Create `server/database/connection.py` with Thread-Local connection isolation, WAL mode, foreign key enforcement, and connection factory
- [x] Create `server/database/repositories.py`:
  - `StudentRepository`: find_by_student_id, register_key, verify_face_embedding
  - `ExamRepository`: get_active_exam, get_questions_for_exam
  - `SubmissionRepository`: create_submission_tx, get_submission, verify_non_repudiation
  - `ViolationRepository`: log_violation, count_by_student
- [x] Create `server/database/seed_data.py` to seed sample exam and 2 students with mock/sample face embeddings and RSA keys
- [x] Execute `seed_data.py` and verify data persistence in `server_storage/exam_system.db`

## Phase 4: Proctor Web Dashboard & Real-Time WebSocket Bridge
- [x] Implement `server/web_bridge.py`:
  - Unified HTTP + WebSocket server running alongside `tcp_server.py`
  - REST endpoints: `/api/overview`, `/api/sessions`, `/api/submissions`, `/api/violations`, `/evidence/<filename>`
  - WebSocket hub for live push: `NEW_VIOLATION`, `SESSION_UPDATE`, `NEW_SUBMISSION`, `MULTICAST_DISPATCHED`
  - Integration with `MulticastSender` to trigger `START`, `PAUSE`, `RESUME`, `FORCE_SUBMIT` from Web Dashboard
- [x] Hook `AuditService`, `SessionManager`, and `ExamService` to notify `web_bridge` on new events
- [x] Integrate `web_bridge` startup and shutdown into `server/tcp_server.py`
- [x] Implement `proctor_web/index.html` (Modern, premium Dark Mode UI):
  - Metric counters (Total Connected, In Exam, Submitted, Total AI Alerts)
  - Control Panel for UDP Multicast Exam operations
  - Live Candidates Session Table (MSSV, Name, Status, Last Heartbeat, Violations)
  - Live AI Proctoring Violation Feed (Webcam Snapshot thumbnail, violation type, details, timestamp, modal zoom)
  - Non-Repudiation RSA Audit Table (Student, SHA-256 Digest, Digital Signature, Verified status)
- [x] Run automated end-to-end integration test (Client -> Server -> Web Bridge WebSocket & Multicast)
- [x] Prepare final report (NO git commit/push as instructed by user)

## Phase 5: Commercial-Grade Enterprise Hardening & Multi-Modal AI (SEB / LockDown Level)
- [x] Part 1: UDP LAN Auto-Discovery (`common/discovery.py`) & Time-out Auto-Submission (`client_desktop/ui/screen_exam.py`)
- [x] Part 2: Deep OS Hardening via Win32 API (`client_desktop/security/windows_guard.py` - Anti-VM, WH_KEYBOARD_LL, SetWindowDisplayAffinity)
- [x] Part 3: Multi-Modal Vision & Audio AI (`client_desktop/ai_proctor_thread.py`, `client_desktop/security/audio_monitor.py` - EAR liveness, YOLOv8/object detector, acoustic RMS)
- [x] Part 4: Exam UX - Diverse Question Types (Multiple Choice + Essay in `client_desktop/ui/screen_exam.py`, Cyber Camera HUD, Scroll fix, Mouse wheel pass-through, End action card)
- [x] Automated Enterprise Test Suite (`tests/test_enterprise_security.py` & `tests/test_full_system_integration.py` - 8/8 tests passed)

## Sprint 1: Multi-Role RBAC Data Architecture & Enterprise Auth Engine (TASK-01 & TASK-02)
- [x] Step 1: Update SSOT Documents (`docs/DATABASE_DESIGN.md` ERD + Data Dictionary, `docs/SPEC.md` Opcode table & TCP auth packets)
- [x] Step 2: Database Schema & Repositories (`server/database/schema.sql` roles/users, `server/database/repositories.py` UserRepository, RoleRepository)
- [x] Step 3: Auth Engine & Seeder (`server/services/auth_service.py` bcrypt + session token, `server/database/seed_data.py` admin_gv, giamthi_01, SV2026_01)
- [x] Step 4: Automated Testing (`tests/test_rbac_auth.py` 100% PASS) & Verification Report
