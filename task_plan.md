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

## Phase 3: Layered Backend Architecture Preparation & Concurrency Analysis
- [x] Scaffold `server/core/`, `server/services/`, and `server/handlers/`
- [x] Explain thread-safe database concurrency model (WAL mode, Thread-local connections, Write serialization lock vs read concurrency)
- [x] Implement `server/core/session_manager.py` with `ClientSession` and `SessionManager` watchdog
- [x] Implement `server/services/auth_service.py`, `exam_service.py`, `audit_service.py`
- [x] Implement `server/handlers/socket_handler.py` and modularize `server/tcp_server.py`
- [x] Verify full integration tests and watchdog kick functionality (100% passed)
