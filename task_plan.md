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
