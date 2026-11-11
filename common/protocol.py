"""
Secure Examination & Proctoring Platform
common/protocol.py - Network Protocol Definition & Packet Serialization
"""

import json
import struct
import time
from enum import IntEnum
from typing import Any, Dict, Optional, Tuple, Union

# Protocol Magic Header & Version
MAGIC_HEADER = b"EXAM"
PROTOCOL_VERSION = 1

# Header format:
# - Magic (4s): 4 bytes (b"EXAM")
# - Version (B): 1 byte uint8
# - Command Type (H): 2 bytes uint16
# - Sequence Number / Nonce (I): 4 bytes uint32
# - Timestamp in ms (Q): 8 bytes uint64
# - Payload Length (I): 4 bytes uint32
HEADER_FORMAT = "!4sBHIQI"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)  # 23 bytes


class CommandType(IntEnum):
    # Session & Handshake
    REQ_CONNECT = 0x0001
    RES_CONNECT_OK = 0x0002
    RES_CONNECT_ERR = 0x0003

    # Multi-Role RBAC Account Authentication & Registration
    REQ_AUTH_LOGIN = 0x0007
    REQ_AUTH_REGISTER = 0x0008

    # Biometric Authentication (Face embedding/photo verification)
    REQ_AUTH_BIOMETRIC = 0x0010
    RES_AUTH_SUCCESS = 0x0011
    RES_AUTH_FAILED = 0x0012

    # Heartbeat & Clock Synchronization
    PING = 0x0020
    PONG = 0x0021
    TIME_SYNC = 0x0022

    # Exam Lifecycle Broadcasts (TCP & UDP Multicast)
    CMD_EXAM_START = 0x0030
    CMD_EXAM_PAUSE = 0x0031
    CMD_EXAM_RESUME = 0x0032
    CMD_EXAM_FINISH = 0x0033
    CMD_ANNOUNCEMENT = 0x0034

    # Exam Questions & Paper Transfer
    REQ_EXAM_PAPER = 0x0040
    RES_EXAM_PAPER = 0x0041

    # Submission & Anti-repudiation Digital Signatures
    SUBMIT_EXAM_PAPER = 0x0050
    SUBMIT_ACK = 0x0051

    # Real-time Proctoring & Violation Detection
    REPORT_VIOLATION = 0x0060
    VIOLATION_ACK = 0x0061

    # Termination
    DISCONNECT = 0x0099


class ProtocolError(Exception):
    """Custom exception raised for protocol framing and validation errors."""
    pass


def get_current_timestamp_ms() -> int:
    """Return current Unix timestamp in milliseconds."""
    return int(time.time() * 1000)


def pack_packet(
    cmd: Union[CommandType, int],
    payload: Union[Dict[str, Any], str, bytes] = b"",
    seq: int = 0,
    timestamp_ms: Optional[int] = None
) -> bytes:
    """
    Packs command, metadata and payload into a binary frame with standard header.
    
    Args:
        cmd: CommandType or integer command identifier.
        payload: Dictionary (serialized to JSON), string, or raw bytes.
        seq: Nonce/sequence number for anti-replay verification.
        timestamp_ms: Optional explicit timestamp in ms.
    
    Returns:
        bytes: Complete packet containing Header (23 bytes) + Payload.
    """
    if timestamp_ms is None:
        timestamp_ms = get_current_timestamp_ms()

    # Convert payload to bytes
    if isinstance(payload, dict):
        payload_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    elif isinstance(payload, str):
        payload_bytes = payload.encode("utf-8")
    elif isinstance(payload, bytes):
        payload_bytes = payload
    else:
        raise TypeError(f"Unsupported payload type: {type(payload)}")

    payload_length = len(payload_bytes)
    cmd_val = int(cmd)

    header = struct.pack(
        HEADER_FORMAT,
        MAGIC_HEADER,
        PROTOCOL_VERSION,
        cmd_val,
        seq,
        timestamp_ms,
        payload_length
    )

    return header + payload_bytes


def unpack_header(header_bytes: bytes) -> Dict[str, Any]:
    """
    Decodes the 23-byte header and validates magic bytes and version.
    
    Returns:
        dict: Parsed header fields.
    """
    if len(header_bytes) != HEADER_SIZE:
        raise ProtocolError(f"Invalid header size: expected {HEADER_SIZE}, got {len(header_bytes)}")

    magic, version, cmd, seq, timestamp_ms, payload_length = struct.unpack(
        HEADER_FORMAT, header_bytes
    )

    if magic != MAGIC_HEADER:
        raise ProtocolError(f"Invalid magic bytes: expected {MAGIC_HEADER!r}, got {magic!r}")

    if version != PROTOCOL_VERSION:
        raise ProtocolError(f"Unsupported protocol version: {version}")

    return {
        "magic": magic,
        "version": version,
        "cmd": cmd,
        "cmd_name": CommandType(cmd).name if cmd in CommandType._value2member_map_ else f"UNKNOWN_0x{cmd:04X}",
        "seq": seq,
        "timestamp_ms": timestamp_ms,
        "payload_length": payload_length
    }


def recv_exact(sock, n_bytes: int) -> bytes:
    """
    Reliably reads exactly n_bytes from a TCP streaming socket.
    Raises ConnectionResetError if the socket closes before n_bytes are received.
    """
    buf = bytearray()
    while len(buf) < n_bytes:
        chunk = sock.recv(n_bytes - len(buf))
        if not chunk:
            if len(buf) == 0:
                raise ConnectionResetError("Connection closed by remote peer.")
            raise ConnectionResetError(
                f"Incomplete packet read: received {len(buf)} of {n_bytes} bytes."
            )
        buf.extend(chunk)
    return bytes(buf)


def recv_packet(sock) -> Tuple[Dict[str, Any], Union[Dict[str, Any], bytes]]:
    """
    Receives and parses a full packet from a connected TCP socket.
    
    Returns:
        Tuple[header_dict, payload_obj]:
            - header_dict: Dictionary containing parsed header metadata.
            - payload_obj: Decoded JSON dict if valid JSON, otherwise raw bytes.
    """
    header_bytes = recv_exact(sock, HEADER_SIZE)
    header = unpack_header(header_bytes)

    payload_length = header["payload_length"]
    if payload_length == 0:
        return header, {}

    raw_payload = recv_exact(sock, payload_length)

    # Attempt to decode as JSON; fallback to raw bytes if binary
    try:
        payload_str = raw_payload.decode("utf-8")
        payload_data = json.loads(payload_str)
        return header, payload_data
    except (UnicodeDecodeError, json.JSONDecodeError):
        return header, raw_payload


def send_packet(
    sock,
    cmd: Union[CommandType, int],
    payload: Union[Dict[str, Any], str, bytes] = b"",
    seq: int = 0
) -> None:
    """
    Packs and sends a full packet across a connected socket using sendall.
    """
    data = pack_packet(cmd, payload, seq)
    sock.sendall(data)
