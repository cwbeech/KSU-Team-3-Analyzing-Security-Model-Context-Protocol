"""
Simple cFS Command Sender - ES NOOP only
Sends a CFE_ES NOOP command to CI_LAB on the Ubuntu VM.
"""

import socket
import struct

# Import configuration from local config file (not committed to git)
try:
    from config import TARGET_IP, CI_LAB_UDP_PORT
except ImportError:
    print("WARNING: config.py not found. Copy config.example.py to config.py and set your VM IP.")
    TARGET_IP = "192.168.136.129"
    CI_LAB_UDP_PORT = 1234

# cFS constants
CFE_PLATFORM_CMD_BASE_MID = 0x1800
ES_CMD_TOPICID = 6
ES_CMD_MID = CFE_PLATFORM_CMD_BASE_MID | ES_CMD_TOPICID  # 0x1806
ES_NOOP_CC = 0


def _ccsds_primary_header(stream_id: int, seq: int, pkt_len_minus_1: int) -> bytes:
    """Build CCSDS primary header (6 bytes)."""
    pkt_id = (0 << 13) | (1 << 12) | (1 << 11) | (stream_id & 0x07FF)
    seq_ctrl = (3 << 14) | (seq & 0x3FFF)
    return struct.pack(">HHH", pkt_id, seq_ctrl, pkt_len_minus_1 & 0xFFFF)


def _cfs_checksum_xor(packet: bytes) -> int:
    """Compute XOR checksum."""
    c = 0
    for b in packet:
        c ^= b
    return c & 0xFF


def build_cfs_command(mid: int, cmd_code: int, payload: bytes = b"", seq: int = 0) -> bytes:
    """Build a cFS command packet."""
    sec = struct.pack("BB", cmd_code & 0xFF, 0)
    total_len = 6 + len(sec) + len(payload)
    pkt_len_minus_1 = (total_len - 1) - 6

    hdr = _ccsds_primary_header(mid, seq, pkt_len_minus_1)
    pkt_wo_cksum = hdr + sec + payload

    c = _cfs_checksum_xor(pkt_wo_cksum)
    sec_with_cksum = struct.pack("BB", cmd_code & 0xFF, c)
    pkt = hdr + sec_with_cksum + payload

    return pkt


def send_ci_lab(packet: bytes, target_ip: str = TARGET_IP, port: int = CI_LAB_UDP_PORT) -> None:
    """Send packet via UDP to CI_LAB."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(packet, (target_ip, port))
    finally:
        sock.close()


def message_cFS() -> str:
    """Send ES NOOP command to cFS."""
    pkt = build_cfs_command(ES_CMD_MID, ES_NOOP_CC, payload=b"", seq=1)
    print(
        f"Sending {len(pkt)} bytes to {TARGET_IP}:{CI_LAB_UDP_PORT} "
        f"(MID=0x{ES_CMD_MID:04X}, CC={ES_NOOP_CC}) ..."
    )
    send_ci_lab(pkt)
    return "Sent."


if __name__ == "__main__":
    result = message_cFS()
    print(result)
