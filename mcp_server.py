import socket
import struct

# Configuration
TARGET_IP = "192.168.136.128"  # Ubuntu VM IP
CI_LAB_UDP_PORT = 1234  # cFS CI_Lab UDP port

# --- cFS MID mapping (derived from cfe/modules/core_api/config/default_cfe_core_api_msgid_mapping.h) ---
# From your grep output:
#   #define CFE_PLATFORM_CMD_TOPICID_TO_MIDV(topic) (CFE_PLATFORM_BASE_MIDVAL(CMD) | (topic))
# So numeric MID == (CMD base MID) OR topic id
# We still need CMD base MID value. In many default cFS configs, CMD base is 0x1800.
# If your mission differs, update CFE_PLATFORM_CMD_BASE_MID.
CFE_PLATFORM_CMD_BASE_MID = 0x1800


def cfe_platform_cmd_topicid_to_mid(topic_id: int) -> int:
    return (CFE_PLATFORM_CMD_BASE_MID | (topic_id & 0x07FF))


# --- cFS CI_Lab UDP command packet builder ---
# CI_LAB expects a *binary* CCSDS/cFS command packet, not arbitrary text.
# A minimal cFS command packet typically is:
#   - CCSDS Primary Header (6 bytes)
#   - cFS Command Secondary Header (2 bytes: cmdCode, checksum)
#   - (optional payload)
#   - checksum computed over entire packet with checksum field initially 0


def _ccsds_primary_header(stream_id: int, seq: int, pkt_len_minus_1: int) -> bytes:
    """Build CCSDS primary header.

    stream_id: 11-bit APID plus flags. For cFS, this is the Message ID (MID).
    seq: sequence count (0-16383)
    pkt_len_minus_1: (total_packet_bytes - 1) - 6
    """
    # CCSDS: first 2 bytes are packet ID (type/secondary header/APID); next 2 are seq/flags,
    # last 2 are length.
    # cFS uses: version=0, type=1 (command), sec_hdr=1.
    pkt_id = (0 << 13) | (1 << 12) | (1 << 11) | (stream_id & 0x07FF)
    seq_ctrl = (3 << 14) | (seq & 0x3FFF)  # 3 = "unsegmented" per CCSDS
    return struct.pack(">HHH", pkt_id, seq_ctrl, pkt_len_minus_1 & 0xFFFF)


def _cfs_checksum_xor(packet: bytes) -> int:
    """Compute the classic cFS XOR checksum used in many sample apps.

    NOTE: Some deployments use different checksum algorithms; CI_LAB commonly uses XOR.
    """
    c = 0
    for b in packet:
        c ^= b
    return c & 0xFF


def build_cfs_command(mid: int, cmd_code: int, payload: bytes = b"", seq: int = 0) -> bytes:
    """Build a basic cFS command packet suitable for CI_LAB ingest.

    mid: Message ID (aka Stream ID). Example values depend on your mission/apps.
    cmd_code: command code.
    payload: command-specific payload.
    seq: CCSDS sequence count.
    """
    # Secondary header: cmd_code (1 byte), checksum (1 byte)
    sec = struct.pack("BB", cmd_code & 0xFF, 0)

    total_len = 6 + len(sec) + len(payload)
    pkt_len_minus_1 = (total_len - 1) - 6

    hdr = _ccsds_primary_header(mid, seq, pkt_len_minus_1)

    pkt_wo_cksum = hdr + sec + payload

    # Set checksum byte so that XOR over entire packet == 0x00
    # With XOR checksum, setting checksum field to XOR(all_bytes_with_checksum0)
    # makes final XOR become 0.
    c = _cfs_checksum_xor(pkt_wo_cksum)
    sec_with_cksum = struct.pack("BB", cmd_code & 0xFF, c)
    pkt = hdr + sec_with_cksum + payload

    return pkt


def send_ci_lab(packet: bytes, target_ip: str = TARGET_IP, port: int = CI_LAB_UDP_PORT) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(packet, (target_ip, port))
    finally:
        sock.close()


if __name__ == "__main__":
    # From your Ubuntu VM:
    #   DEFAULT_CFE_MISSION_ES_CMD_TOPICID = 6
    ES_CMD_TOPICID = 6

    # Compute on-wire MID from topic id
    EXAMPLE_MID = cfe_platform_cmd_topicid_to_mid(ES_CMD_TOPICID)

    # CFE_ES NOOP is typically command code 0
    EXAMPLE_CMD_CODE = 0

    pkt = build_cfs_command(EXAMPLE_MID, EXAMPLE_CMD_CODE, payload=b"", seq=1)
    print(
        f"Sending {len(pkt)} bytes to {TARGET_IP}:{CI_LAB_UDP_PORT} "
        f"(MID=0x{EXAMPLE_MID:04X}, CC={EXAMPLE_CMD_CODE}) ..."
    )
    send_ci_lab(pkt)
    print("Sent.")
