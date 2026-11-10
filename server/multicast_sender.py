"""
Secure Examination & Proctoring Platform
server/multicast_sender.py - UDP Multicast Exam Command Broadcaster
"""

import json
import logging
import os
import socket
import sys
import time
from typing import Any, Dict

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from common.protocol import CommandType, pack_packet

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [MULTICAST SENDER] %(message)s")
logger = logging.getLogger("MulticastSender")

DEFAULT_MULTICAST_GROUP = "224.1.1.1"
DEFAULT_MULTICAST_PORT = 5005


class MulticastSender:
    """
    Sends synchronized UDP Multicast broadcast commands to all exam clients on the LAN.
    """

    def __init__(self, group_ip: str = DEFAULT_MULTICAST_GROUP, port: int = DEFAULT_MULTICAST_PORT, ttl: int = 2):
        self.group_ip = group_ip
        self.port = port
        self.ttl = ttl
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        
        # Set IP_MULTICAST_TTL to control broadcast scope (1 = same subnet, 2 = local network)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, self.ttl)

    def broadcast_command(self, cmd: CommandType, payload: Dict[str, Any]) -> None:
        """Packs and broadcasts a command over UDP multicast."""
        packet_bytes = pack_packet(cmd, payload)
        self.sock.sendto(packet_bytes, (self.group_ip, self.port))
        logger.info(
            f"📢 Broadcasted {cmd.name} to {self.group_ip}:{self.port} (Size: {len(packet_bytes)} bytes). "
            f"Payload: {json.dumps(payload, ensure_ascii=False)}"
        )

    def start_exam(self, exam_id: str = "LTM_2026_FINAL", duration_minutes: int = 60) -> None:
        """Broadcasts signal to unlock exam papers and start timer."""
        payload = {
            "exam_id": exam_id,
            "duration_minutes": duration_minutes,
            "start_time_ms": int(time.time() * 1000),
            "instructions": "BẮT ĐẦU THI: Thí sinh làm bài tập trung, tuân thủ quy chế thi."
        }
        self.broadcast_command(CommandType.CMD_EXAM_START, payload)

    def pause_exam(self, reason: str = "Tạm dừng kiểm tra sự cố mạng") -> None:
        """Broadcasts signal to temporarily freeze exam client."""
        payload = {
            "reason": reason,
            "paused_at_ms": int(time.time() * 1000)
        }
        self.broadcast_command(CommandType.CMD_EXAM_PAUSE, payload)

    def resume_exam(self, added_minutes: int = 0) -> None:
        """Broadcasts signal to resume paused exam."""
        payload = {
            "added_minutes": added_minutes,
            "resumed_at_ms": int(time.time() * 1000)
        }
        self.broadcast_command(CommandType.CMD_EXAM_RESUME, payload)

    def finish_exam(self, message: str = "HẾT GIỜ LÀM BÀI! Toàn bộ client tự động nộp bài.") -> None:
        """Broadcasts signal to force paper lock and submit."""
        payload = {
            "message": message,
            "finish_time_ms": int(time.time() * 1000),
            "force_submit": True
        }
        self.broadcast_command(CommandType.CMD_EXAM_FINISH, payload)

    def send_announcement(self, message: str) -> None:
        """Broadcasts general announcement message to all screens."""
        payload = {
            "message": message,
            "timestamp_ms": int(time.time() * 1000)
        }
        self.broadcast_command(CommandType.CMD_ANNOUNCEMENT, payload)

    def close(self) -> None:
        self.sock.close()


def interactive_cli():
    sender = MulticastSender()
    print("=" * 60)
    print("  GIÁM THỊ - BỘ ĐIỀU KHIỂN PHÁT LỆNH UDP MULTICAST")
    print(f"  Địa chỉ Multicast: {DEFAULT_MULTICAST_GROUP}:{DEFAULT_MULTICAST_PORT}")
    print("=" * 60)
    print("1. Phát lệnh: BẮT ĐẦU THI (START_EXAM)")
    print("2. Phát lệnh: TẠM DỪNG THI (PAUSE_EXAM)")
    print("3. Phát lệnh: TIẾP TỤC THI (RESUME_EXAM)")
    print("4. Phát lệnh: HẾT GIỜ THU BÀI (FINISH_EXAM)")
    print("5. Phát thông báo khẩn (ANNOUNCEMENT)")
    print("0. Thoát")
    print("=" * 60)

    while True:
        try:
            choice = input("\nNhập lựa chọn (0-5): ").strip()
            if choice == "1":
                duration = int(input("Thời gian thi (phút) [mặc định 60]: ") or "60")
                sender.start_exam(duration_minutes=duration)
            elif choice == "2":
                reason = input("Lý do tạm dừng: ") or "Kiểm tra phòng thi"
                sender.pause_exam(reason)
            elif choice == "3":
                add_min = int(input("Cộng thêm phút bù giờ (mặc định 0): ") or "0")
                sender.resume_exam(add_min)
            elif choice == "4":
                sender.finish_exam()
            elif choice == "5":
                msg = input("Nội dung thông báo: ")
                if msg:
                    sender.send_announcement(msg)
            elif choice == "0":
                break
            else:
                print("Lựa chọn không hợp lệ.")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Lỗi: {e}")

    sender.close()
    print("Đã đóng Multicast Sender.")


if __name__ == "__main__":
    interactive_cli()
