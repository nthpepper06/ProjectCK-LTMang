"""
Secure Examination & Proctoring Platform
server/database/seed_data.py - Database Initialization & Seed Script
Populates sample exam data, questions, and registered student biometric profiles.
"""

import os
import struct
import sys

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from server.database.connection import get_db_manager
from server.database.repositories import ExamRepository, StudentRepository


def generate_mock_face_embedding(seed_val: float) -> bytes:
    """Generates a 128-dimensional mock face embedding packed into binary float bytes."""
    # 128 float32 values normalized
    vector = [float(seed_val + (i * 0.005)) for i in range(128)]
    return struct.pack("128f", *vector)


def seed_database():
    """Initializes tables and seeds initial test data."""
    print("🚀 Initializing SQLite database schema...")
    db_mgr = get_db_manager()
    db_mgr.init_database()

    student_repo = StudentRepository(db_mgr)
    exam_repo = ExamRepository(db_mgr)

    # 1. Seed Students
    print("👤 Seeding student profiles & biometric embeddings...")
    # Clear test artifacts
    with db_mgr.write_transaction() as conn:
        conn.execute("DELETE FROM violation_logs WHERE violation_type LIKE 'TEST_%'")
        conn.execute("DELETE FROM submissions WHERE student_id LIKE 'TEST_%'")
    student1_emb = generate_mock_face_embedding(0.1)
    student2_emb = generate_mock_face_embedding(0.5)

    s1_id = student_repo.create_student(
        student_id="SV2026_01",
        full_name="Nguyễn Văn A",
        face_embedding=student1_emb
    )
    s2_id = student_repo.create_student(
        student_id="SV2026_02",
        full_name="Trần Thị B",
        face_embedding=student2_emb
    )
    print(f"   ✔ Student 1: SV2026_01 - Nguyễn Văn A (Row ID: {s1_id})")
    print(f"   ✔ Student 2: SV2026_02 - Trần Thị B (Row ID: {s2_id})")

    # 2. Seed Active Exam
    print("📋 Seeding exam session...")
    exam_id = exam_repo.create_exam(
        exam_code="LTM_2026_FINAL",
        title="Kỳ thi Cuối kỳ Lập trình Mạng & An toàn Hệ thống",
        duration_minutes=60,
        is_active=True
    )
    print(f"   ✔ Exam: LTM_2026_FINAL (Row ID: {exam_id})")

    # 3. Seed Exam Questions
    print("❓ Seeding exam questions...")
    q1_id = exam_repo.add_question(
        exam_id=exam_id,
        question_index=1,
        content="Giao thức TCP và UDP khác nhau cơ bản ở điểm nào trong việc kiểm soát luồng và độ tin cậy?",
        question_type="essay"
    )
    q2_id = exam_repo.add_question(
        exam_id=exam_id,
        question_index=2,
        content="Tại sao UDP Multicast được ưu tiên sử dụng để phát thông điệp đồng loạt trong mạng cục bộ thay vì gửi nhiều gói tin Unicast TCP?",
        question_type="essay"
    )
    q3_id = exam_repo.add_question(
        exam_id=exam_id,
        question_index=3,
        content="Chữ ký số (Digital Signature) kết hợp giữa thuật toán hàm băm SHA-256 và RSA giải quyết được những bài toán an ninh thông tin nào?",
        question_type="essay"
    )
    print(f"   ✔ Question 1 ID: {q1_id}")
    print(f"   ✔ Question 2 ID: {q2_id}")
    print(f"   ✔ Question 3 ID: {q3_id}")

    print("\n✅ DATABASE SEEDING COMPLETED SUCCESSFULLY!")
    print(f"📁 SQLite Database File: {db_mgr.db_path}")


if __name__ == "__main__":
    seed_database()
