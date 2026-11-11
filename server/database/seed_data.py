"""
Secure Examination & Proctoring Platform
server/database/seed_data.py - Database Initialization & Seed Script with Multi-Role RBAC
Populates system roles (ADMIN, PROCTOR, STUDENT), default user accounts, exam session, and questions.
"""

import os
import struct
import sys

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from server.database.connection import get_db_manager
from server.database.repositories import (
    ExamRepository,
    RoleRepository,
    UserRepository,
    hash_password,
)


def generate_mock_face_embedding(seed_val: float) -> bytes:
    """Generates a 128-dimensional mock face embedding packed into binary float bytes."""
    vector = [float(seed_val + (i * 0.005)) for i in range(128)]
    return struct.pack("128f", *vector)


def seed_database():
    """Initializes schema and seeds multi-role accounts, exam sessions, and questions."""
    print("🚀 Initializing SQLite database schema...")
    db_mgr = get_db_manager()
    db_mgr.init_database()

    role_repo = RoleRepository(db_mgr)
    user_repo = UserRepository(db_mgr)
    exam_repo = ExamRepository(db_mgr)

    # 1. Seed Roles
    print("🛡️ Seeding system RBAC roles...")
    r_admin_id = role_repo.get_or_create_role("ADMIN", "Quản trị viên hệ thống & Giảng viên ra đề")
    r_proctor_id = role_repo.get_or_create_role("PROCTOR", "Giám thị phòng thi & Giám sát AI trực tiếp")
    r_student_id = role_repo.get_or_create_role("STUDENT", "Thí sinh dự thi")
    print(f"   ✔ Role ADMIN ID: {r_admin_id}")
    print(f"   ✔ Role PROCTOR ID: {r_proctor_id}")
    print(f"   ✔ Role STUDENT ID: {r_student_id}")

    # 2. Seed Default Accounts
    print("👤 Seeding multi-role accounts with bcrypt-hashed credentials...")
    admin_id = user_repo.create_user(
        username="admin_gv",
        password_hash=hash_password("Admin@2026"),
        full_name="Quản Trị Viên & Giảng Viên",
        role_name="ADMIN",
        email="admin@ptit.edu.vn",
        status="ACTIVE"
    )
    print(f"   ✔ [ADMIN] admin_gv / Admin@2026 (User ID: {admin_id})")

    proctor_id = user_repo.create_user(
        username="giamthi_01",
        password_hash=hash_password("Proctor@2026"),
        full_name="Cán Bộ Coi Thi 01",
        role_name="PROCTOR",
        email="proctor01@ptit.edu.vn",
        status="ACTIVE"
    )
    print(f"   ✔ [PROCTOR] giamthi_01 / Proctor@2026 (User ID: {proctor_id})")

    student1_emb = generate_mock_face_embedding(0.1)
    student2_emb = generate_mock_face_embedding(0.5)

    s1_id = user_repo.create_user(
        username="SV2026_01",
        password_hash=hash_password("Student@2026"),
        full_name="Nguyễn Văn A",
        role_name="STUDENT",
        email="sv2026_01@ptit.edu.vn",
        face_embedding=student1_emb,
        status="ACTIVE"
    )
    s2_id = user_repo.create_user(
        username="SV2026_02",
        password_hash=hash_password("Student@2026"),
        full_name="Trần Thị B",
        role_name="STUDENT",
        email="sv2026_02@ptit.edu.vn",
        face_embedding=student2_emb,
        status="ACTIVE"
    )
    print(f"   ✔ [STUDENT] SV2026_01 / Student@2026 - Nguyễn Văn A (User ID: {s1_id})")
    print(f"   ✔ [STUDENT] SV2026_02 / Student@2026 - Trần Thị B (User ID: {s2_id})")

    # 3. Seed Active Exam
    print("📋 Seeding exam session...")
    exam_id = exam_repo.create_exam(
        exam_code="LTM_2026_FINAL",
        title="Kỳ thi Cuối kỳ Lập trình Mạng & An toàn Hệ thống",
        duration_minutes=60,
        is_active=True,
        created_by=admin_id
    )
    print(f"   ✔ Exam: LTM_2026_FINAL (Exam ID: {exam_id}, Created By User: {admin_id})")

    # 4. Seed Questions (Multiple Choice & Essay)
    print("❓ Seeding exam questions (Multiple-Choice & Essay)...")
    q1_id = exam_repo.add_question(
        exam_id=exam_id,
        question_index=1,
        content="Đặc điểm nào sau đây KHÔNG PHẢI là tính chất của giao thức UDP?",
        question_type="multiple_choice",
        options=[
            "A. Hướng kết nối (Connection-oriented) và bảo đảm truyền tin cậy",
            "B. Tốc độ truyền tải nhanh và overhead tiêu đề nhỏ (8 bytes)",
            "C. Hỗ trợ cơ chế phát đa hướng (Multicast) và quảng bá (Broadcast)",
            "D. Không thực hiện cơ chế bắt tay 3 bước (Three-way handshake)"
        ],
        correct_answer_hash="A"
    )
    q2_id = exam_repo.add_question(
        exam_id=exam_id,
        question_index=2,
        content="Địa chỉ IP nào sau đây thuộc dải địa chỉ dành riêng cho IPv4 Multicast (Class D)?",
        question_type="multiple_choice",
        options=[
            "A. 192.168.1.1",
            "B. 224.1.1.1",
            "C. 10.0.0.1",
            "D. 255.255.255.255"
        ],
        correct_answer_hash="B"
    )
    q3_id = exam_repo.add_question(
        exam_id=exam_id,
        question_index=3,
        content="Sơ đồ đệm an toàn nào được khuyến nghị kết hợp với RSA-2048 trong chữ ký số hiện đại chống giả mạo?",
        question_type="multiple_choice",
        options=[
            "A. PKCS#1 v1.5",
            "B. PSS (Probabilistic Signature Scheme)",
            "C. OAEP (Optimal Asymmetric Encryption Padding)",
            "D. NoPadding"
        ],
        correct_answer_hash="B"
    )
    q4_id = exam_repo.add_question(
        exam_id=exam_id,
        question_index=4,
        content="Phân tích cơ chế bắt tay 3 bước (Three-way handshake) của TCP và cách phòng chống tấn công SYN Flood.",
        question_type="essay"
    )
    q5_id = exam_repo.add_question(
        exam_id=exam_id,
        question_index=5,
        content="Trình bày vai trò của Chữ ký số (Digital Signature) và hàm băm SHA-256 trong việc chống chối bỏ bài thi trực tuyến.",
        question_type="essay"
    )
    print(f"   ✔ Question 1 (Multiple Choice) ID: {q1_id}")
    print(f"   ✔ Question 2 (Multiple Choice) ID: {q2_id}")
    print(f"   ✔ Question 3 (Multiple Choice) ID: {q3_id}")
    print(f"   ✔ Question 4 (Essay) ID: {q4_id}")
    print(f"   ✔ Question 5 (Essay) ID: {q5_id}")

    print("\n✅ DATABASE SEEDING COMPLETED SUCCESSFULLY!")
    print(f"📁 SQLite Database File: {db_mgr.db_path}")


if __name__ == "__main__":
    seed_database()
