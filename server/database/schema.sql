-- ==============================================================================
-- Secure Examination & Proctoring Platform
-- server/database/schema.sql - Production Multi-Role RBAC Database Schema
-- Compatible with SQLite (WAL Mode) and PostgreSQL
-- ==============================================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ------------------------------------------------------------------------------
-- 1. Table: roles (Vai trò & Phân quyền RBAC)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(32) NOT NULL UNIQUE,
    description VARCHAR(255)
);

CREATE INDEX IF NOT EXISTS idx_roles_name ON roles(name);

-- ------------------------------------------------------------------------------
-- 2. Table: users (Tài khoản Người dùng Đa vai trò - ADMIN, PROCTOR, STUDENT)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(64) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name VARCHAR(128) NOT NULL,
    role_id INTEGER NOT NULL,
    email VARCHAR(128),
    rsa_public_key TEXT,
    face_embedding BLOB,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role_id ON users(role_id);
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);

-- ------------------------------------------------------------------------------
-- 3. Table: exams (Ca thi & Đề thi)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS exams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_code VARCHAR(64) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    created_by INTEGER,
    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    duration_minutes INTEGER NOT NULL DEFAULT 60,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_exams_exam_code ON exams(exam_code);
CREATE INDEX IF NOT EXISTS idx_exams_created_by ON exams(created_by);

-- ------------------------------------------------------------------------------
-- 4. Table: questions (Ngân hàng câu hỏi trong đề)
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
-- 5. Table: submissions (Bài nộp & Chữ ký số kép chống chối bỏ)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    answers_payload TEXT NOT NULL,
    sha256_hash VARCHAR(64) NOT NULL,
    digital_signature TEXT NOT NULL,
    server_receipt_signature TEXT NOT NULL,
    submitted_at_ms INTEGER NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'VERIFIED',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_student_exam_submission UNIQUE (exam_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_submissions_student_exam ON submissions(student_id, exam_id);

-- ------------------------------------------------------------------------------
-- 6. Table: violation_logs (Nhật ký vi phạm & Bằng chứng AI Proctoring)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS violation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    exam_id INTEGER NOT NULL,
    violation_type VARCHAR(64) NOT NULL,
    suspicion_score REAL NOT NULL DEFAULT 1.0,
    details TEXT,
    evidence_path VARCHAR(255),
    timestamp_ms INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_violations_student_exam ON violation_logs(student_id, exam_id, timestamp_ms);

-- ------------------------------------------------------------------------------
-- 7. View: students (Tương thích ngược cho các truy vấn cũ)
-- ------------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS students AS
SELECT 
    u.id AS id,
    u.username AS student_id,
    u.full_name AS full_name,
    u.rsa_public_key AS rsa_public_key,
    u.face_embedding AS face_embedding,
    u.created_at AS created_at
FROM users u
JOIN roles r ON u.role_id = r.id
WHERE r.name = 'STUDENT';
