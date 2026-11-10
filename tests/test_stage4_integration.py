"""
Integration Test for Stage 4: Proctor Web Dashboard & Real-Time Sync
Verifies:
1. ExamTCPServer + WebBridge startup (TCP + HTTP + WebSocket).
2. HTTP Serving of proctor_web/index.html & REST endpoints (/api/overview, /api/sessions, etc.).
3. WebSocket connection & INITIAL_STATE reception.
4. Candidate TCP Connect -> Auth -> Session update pushed over WebSocket.
5. AI Violation Report with Snapshot -> Saved to storage & NEW_VIOLATION pushed over WebSocket.
6. Exam Submission with RSA Signature -> Verified & NEW_SUBMISSION pushed over WebSocket.
7. Multicast Exam Action from Web -> Multicast broadcast & MULTICAST_DISPATCHED event pushed over WebSocket.
"""

import asyncio
import base64
import json
import logging
import os
import queue
import socket
import sys
import threading
import time
import urllib.request

import websockets

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.crypto_utils import compute_sha256, generate_rsa_keypair, sign_data
from common.protocol import CommandType, recv_packet, send_packet
from server.tcp_server import ExamTCPServer

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("TEST_STAGE4")

TEST_TCP_PORT = 8899
TEST_HTTP_PORT = 8089
TEST_WS_PORT = 8091


async def test_websocket_client(event_queue: queue.Queue, ready_event: threading.Event, stop_event: threading.Event):
    uri = f"ws://127.0.0.1:{TEST_WS_PORT}"
    logger.info(f"Connecting test WebSocket client to {uri}...")
    try:
        async with websockets.connect(uri) as ws:
            ready_event.set()
            while not stop_event.is_set():
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=0.5)
                    data = json.loads(msg)
                    event_queue.put(data)
                except asyncio.TimeoutError:
                    continue
    except Exception as e:
        logger.warning(f"Test WebSocket closed: {e}")


def run_test_suite():
    print("=" * 80)
    print("  BẮT ĐẦU KIỂM THỬ TÍCH HỢP GIAI ĐOẠN 4: PROCTOR WEB & REAL-TIME WEBSOCKET")
    print("=" * 80)

    # 1. Start Server on test ports
    server = ExamTCPServer(
        host="127.0.0.1",
        port=TEST_TCP_PORT,
        evidence_dir="server_storage/evidence",
        enable_web=True,
        http_port=TEST_HTTP_PORT,
        ws_port=TEST_WS_PORT
    )
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()
    time.sleep(1.0)  # wait for listeners

    # 2. Test HTTP Endpoints
    print("\n[BƯỚC 1] Kiểm tra HTTP Server & REST API Endpoints...")
    base_url = f"http://127.0.0.1:{TEST_HTTP_PORT}"

    # GET /
    with urllib.request.urlopen(f"{base_url}/") as res:
        assert res.status == 200, f"HTTP status was {res.status}"
        html = res.read().decode("utf-8")
        assert "Smart AI Proctoring" in html
        print("  ✓ GET / (index.html) -> 200 OK (Loaded Proctor Web Dashboard)")

    # GET /api/overview
    with urllib.request.urlopen(f"{base_url}/api/overview") as res:
        assert res.status == 200
        overview = json.loads(res.read().decode("utf-8"))
        assert "active_students" in overview
        print(f"  ✓ GET /api/overview -> 200 OK: {overview}")

    # GET /api/sessions
    with urllib.request.urlopen(f"{base_url}/api/sessions") as res:
        assert res.status == 200
        sessions = json.loads(res.read().decode("utf-8"))
        print(f"  ✓ GET /api/sessions -> 200 OK (Current active: {len(sessions)})")

    # 3. Start Background WebSocket Monitor
    print("\n[BƯỚC 2] Khởi tạo WebSocket Client Giám Thị kết nối ws://127.0.0.1:8091...")
    event_queue = queue.Queue()
    ready_event = threading.Event()
    stop_event = threading.Event()

    def _ws_runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(test_websocket_client(event_queue, ready_event, stop_event))

    ws_thread = threading.Thread(target=_ws_runner, daemon=True)
    ws_thread.start()

    # Wait for WS ready
    timeout = 3.0
    start_t = time.time()
    while not ready_event.is_set() and time.time() - start_t < timeout:
        time.sleep(0.05)
    assert ready_event.is_set(), "WebSocket failed to connect in time!"
    print("  ✓ WebSocket Client đã kết nối thành công tới Proctor Web Bridge!")

    # Verify INITIAL_STATE event
    init_event = event_queue.get(timeout=3.0)
    assert init_event.get("type") == "INITIAL_STATE"
    print(f"  ✓ Nhận sự kiện INITIAL_STATE từ WebSocket: {list(init_event.keys())}")

    # 4. Simulate Candidate Client Connection & Authentication
    print("\n[BƯỚC 3] Thí sinh kết nối TCP & Đăng nhập sinh trắc học...")
    client_priv, client_pub = generate_rsa_keypair(2048)
    client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_sock.connect(("127.0.0.1", TEST_TCP_PORT))

    # REQ_CONNECT
    send_packet(client_sock, CommandType.REQ_CONNECT, {
        "student_id": "SV2026_01",
        "student_name": "Nguyễn Văn A",
        "public_key_pem": client_pub.decode("utf-8")
    })
    h, p = recv_packet(client_sock)
    assert h["cmd"] == CommandType.RES_CONNECT_OK

    # REQ_AUTH_BIOMETRIC
    send_packet(client_sock, CommandType.REQ_AUTH_BIOMETRIC, {
        "student_id": "SV2026_01",
        "match_confidence": 0.98
    })
    h, p = recv_packet(client_sock)
    assert h["cmd"] == CommandType.RES_AUTH_SUCCESS
    token = p["session_token"]
    print(f"  ✓ Thí sinh SV2026_01 xác thực thành công. Session Token: {token[:16]}...")

    # Verify WebSocket received SESSION_UPDATE
    session_event = event_queue.get(timeout=3.0)
    assert session_event.get("type") == "SESSION_UPDATE"
    active_s = session_event["sessions"]
    assert any(s["student_id"] == "SV2026_01" for s in active_s)
    print("  ✓ WebSocket Dashboard lập tức nhận sự kiện [SESSION_UPDATE] (Thí sinh SV2026_01 xuất hiện)")

    # 5. Fetch Exam Paper
    print("\n[BƯỚC 4] Thí sinh nhận đề thi & Chuyển trạng thái IN_EXAM...")
    send_packet(client_sock, CommandType.REQ_EXAM_PAPER, {"exam_id": "LTM_2026_FINAL"})
    h, paper = recv_packet(client_sock)
    assert h["cmd"] == CommandType.RES_EXAM_PAPER
    assert len(paper["questions"]) > 0
    print(f"  ✓ Thí sinh nhận đề thi thành công ({len(paper['questions'])} câu hỏi)")

    # Wait for SESSION_UPDATE (IN_EXAM)
    in_exam_event = event_queue.get(timeout=3.0)
    assert in_exam_event.get("type") == "SESSION_UPDATE"
    print("  ✓ WebSocket Dashboard nhận sự kiện [SESSION_UPDATE] (Chuyển trạng thái IN_EXAM)")

    # 6. Candidate reports AI Proctoring Violation with Snapshot
    print("\n[BƯỚC 5] Thí sinh gửi cảnh báo vi phạm AI kèm Snapshot bằng chứng...")
    dummy_jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
    dummy_b64 = base64.b64encode(dummy_jpeg_bytes).decode("utf-8")

    send_packet(client_sock, CommandType.REPORT_VIOLATION, {
        "exam_id": "LTM_2026_FINAL",
        "violation_type": "HEAD_TURNED",
        "suspicion_score": 0.85,
        "details": "Quay đầu quá 35 độ liên tục trong 4 giây. Yaw=-38.5 deg.",
        "evidence_image_b64": dummy_b64,
        "timestamp_ms": int(time.time() * 1000)
    })
    h, ack = recv_packet(client_sock)
    assert h["cmd"] == CommandType.VIOLATION_ACK
    assert ack["success"] is True
    print(f"  ✓ Server TCP đã lưu log vi phạm & lưu snapshot: {ack.get('evidence_saved')}")

    # Verify WebSocket received NEW_VIOLATION
    viol_event = event_queue.get(timeout=3.0)
    assert viol_event.get("type") == "NEW_VIOLATION"
    assert viol_event["data"]["student_id"] == "SV2026_01"
    assert viol_event["data"]["violation_type"] == "HEAD_TURNED"
    evidence_url = viol_event["data"]["evidence_url"]
    assert evidence_url is not None
    print(f"  ✓ WebSocket Dashboard lập tức nhận sự kiện [NEW_VIOLATION]: {viol_event['data']['violation_type']} (Evidence: {evidence_url})")

    # Verify HTTP serves the evidence image
    with urllib.request.urlopen(f"{base_url}{evidence_url}") as img_res:
        assert img_res.status == 200
        content = img_res.read()
        assert len(content) == len(dummy_jpeg_bytes)
        print(f"  ✓ HTTP Server phục vụ ảnh snapshot tại {evidence_url} thành công (Size: {len(content)} bytes)")

    # 7. Candidate Submits Paper with RSA Digital Signature
    print("\n[BƯỚC 6] Thí sinh ký số RSA-2048 & Nộp bài thi...")
    answers = {"1": "B", "2": "C", "3": "A"}
    answers_bytes = json.dumps(answers, sort_keys=True).encode("utf-8")
    paper_digest = compute_sha256(answers_bytes)
    client_sig = sign_data(client_priv, answers_bytes)

    send_packet(client_sock, CommandType.SUBMIT_EXAM_PAPER, {
        "student_id": "SV2026_01",
        "exam_id": "LTM_2026_FINAL",
        "answers": answers,
        "paper_hash": paper_digest,
        "signature": client_sig
    })
    h, sub_ack = recv_packet(client_sock)
    assert h["cmd"] == CommandType.SUBMIT_ACK
    assert sub_ack["success"] is True
    print(f"  ✓ Server đối soát chữ ký số RSA hợp lệ và cấp biên lai: {sub_ack.get('receipt')}")

    # Verify WebSocket received NEW_SUBMISSION
    sub_event = event_queue.get(timeout=3.0)
    assert sub_event.get("type") == "NEW_SUBMISSION"
    assert sub_event["data"]["student_id"] == "SV2026_01"
    assert sub_event["data"]["status"] == "VERIFIED_RSA"
    print("  ✓ WebSocket Dashboard lập tức nhận sự kiện [NEW_SUBMISSION] kèm chứng thực RSA!")

    # 8. Test Multicast Control from Web Dashboard
    print("\n[BƯỚC 7] Giám thị điều khiển phòng thi qua UDP Multicast từ Web Dashboard...")
    req_data = json.dumps({"action": "START", "duration_minutes": 60}).encode("utf-8")
    req = urllib.request.Request(f"{base_url}/api/multicast", data=req_data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as m_res:
        assert m_res.status == 200
        res_json = json.loads(m_res.read().decode("utf-8"))
        assert res_json["success"] is True
        print(f"  ✓ HTTP POST /api/multicast -> 200 OK: {res_json['message']}")

    # Verify WebSocket received MULTICAST_DISPATCHED
    m_event = event_queue.get(timeout=3.0)
    assert m_event.get("type") == "MULTICAST_DISPATCHED"
    assert m_event.get("action") == "START"
    print(f"  ✓ WebSocket Dashboard nhận sự kiện đồng bộ [MULTICAST_DISPATCHED]: {m_event['action']}")

    # Clean disconnect
    client_sock.close()
    time.sleep(0.5)

    # Teardown
    stop_event.set()
    server.stop()
    print("\n" + "=" * 80)
    print("  GIAI ĐOẠN 4 HOÀN TẤT THÀNH CÔNG 100%! TOÀN BỘ CÁC BÀI KIỂM THỬ ĐÃ ĐẠT!")
    print("=" * 80)


if __name__ == "__main__":
    run_test_suite()
