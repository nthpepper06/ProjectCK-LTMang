-- ==============================================================================
-- Secure Examination & Proctoring Platform
-- server/database/schema.sql - Production Database Schema Definition
-- Compatible with SQLite (WAL Mode) and PostgreSQL
-- ==============================================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------------------------
-- 1. Table: students (Hồ sơ Sinh viên & Sinh trắc học)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id VARCHAR(32) NOT NULL UNIQUE,
    full_name VARCHAR(128) NOT NULL,
    rsa_public_key TEXT,
    face_embedding BLOB,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_students_student_id ON students(student_id);

-- ------------------------------------------------------------------------------
-- 2. Table: exams (Ca thi & Đề thi)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS exams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_code VARCHAR(64) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    duration_minutes INTEGER NOT NULL DEFAULT 60,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_exams_exam_code ON exams(exam_code);

-- ------------------------------------------------------------------------------
-- 3. Table: questions (Ngân hàng câu hỏi trong đề)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER NOT NULL,
    question_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    question_type VARCHAR(32) NOT NULL DEFAULT 'essay',
    options_json TEXT,
    correct_answer_hash TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_questions_exam_id ON questions(exam_id, question_index);

-- ------------------------------------------------------------------------------
-- 4. Table: submissions (Bài nộp & Chữ ký số kép chống chối bỏ)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER NOT NULL,
    student_id VARCHAR(32) NOT NULL,
    answers_payload TEXT NOT NULL,
    sha256_hash VARCHAR(64) NOT NULL,
    digital_signature TEXT NOT NULL,
    server_receipt_signature TEXT NOT NULL,
    submitted_at_ms INTEGER NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'VERIFIED',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (exam_id) REFERENCES exams(id),
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    CONSTRAINT uq_student_exam_submission UNIQUE (exam_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_submissions_student_exam ON submissions(student_id, exam_id);

-- ------------------------------------------------------------------------------
-- 5. Table: violation_logs (Nhật ký vi phạm & Bằng chứng AI Proctoring)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS violation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id VARCHAR(32) NOT NULL,
    exam_id INTEGER NOT NULL,
    violation_type VARCHAR(64) NOT NULL,
    suspicion_score REAL NOT NULL DEFAULT 1.0,
    details TEXT,
    evidence_path VARCHAR(255),
    timestamp_ms INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (exam_id) REFERENCES exams(id)
);

CREATE INDEX IF NOT EXISTS idx_violations_student_exam ON violation_logs(student_id, exam_id, timestamp_ms);
