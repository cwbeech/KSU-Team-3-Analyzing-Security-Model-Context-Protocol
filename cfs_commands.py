import socket
import struct

# Import configuration from local config file (not committed to git)
# Each team member sets their own VM IP in config.py
try:
    from config import TARGET_IP, CI_LAB_UDP_PORT
except ImportError:
    # Fallback defaults if config.py doesn't exist
    print("WARNING: config.py not found. Copy config.example.py to config.py and set your VM IP.")
    TARGET_IP = "192.168.136.129"
    CI_LAB_UDP_PORT = 1234

# --- cFS MID mapping (derived from cfe/modules/core_api/config/default_cfe_core_api_msgid_mapping.h) ---
# From your grep output:
#   #define CFE_PLATFORM_CMD_TOPICID_TO_MIDV(topic) (CFE_PLATFORM_BASE_MIDVAL(CMD) | (topic))
# So numeric MID == (CMD base MID) OR topic id
# We still need CMD base MID value. In many default cFS configs, CMD base is 0x1800.
# If your mission differs, update CFE_PLATFORM_CMD_BASE_MID.
CFE_PLATFORM_CMD_BASE_MID = 0x1800

# --- sample_app IDs (from your VM headers) ---
# sample_app topicids.h: DEFAULT_SAMPLE_APP_MISSION_CMD_TOPICID = 0x82
SAMPLE_APP_CMD_TOPICID = 0x82
SAMPLE_APP_CMD_MID = (CFE_PLATFORM_CMD_BASE_MID | SAMPLE_APP_CMD_TOPICID)

# sample_app fcncode values: NOOP=0, RESET_COUNTERS=1, PROCESS=2, DISPLAY_PARAM=3
SAMPLE_APP_NOOP_CC = 0
SAMPLE_APP_RESET_COUNTERS_CC = 1
SAMPLE_APP_PROCESS_CC = 2
SAMPLE_APP_DISPLAY_PARAM_CC = 3

# This comes from sample_app_mission_cfg.h (not provided yet). Set it once you grep it in the VM.
# grep -R "SAMPLE_APP_MISSION_STRING_VAL_LEN" -n ~/Desktop/cFS/apps/sample_app | head
SAMPLE_APP_MISSION_STRING_VAL_LEN = 32  # TODO: update to match VM


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


def send_command(mid: int, cc: int, payload: bytes = b"", seq: int = 1) -> None:
    pkt = build_cfs_command(mid, cc, payload=payload, seq=seq)
    send_ci_lab(pkt)


def sample_app_noop() -> str:
    send_command(SAMPLE_APP_CMD_MID, SAMPLE_APP_NOOP_CC, payload=b"", seq=1)
    return "Sent SAMPLE_APP NOOP"


def sample_app_reset_counters() -> str:
    send_command(SAMPLE_APP_CMD_MID, SAMPLE_APP_RESET_COUNTERS_CC, payload=b"", seq=1)
    return "Sent SAMPLE_APP RESET_COUNTERS"


def sample_app_process() -> str:
    send_command(SAMPLE_APP_CMD_MID, SAMPLE_APP_PROCESS_CC, payload=b"", seq=1)
    return "Sent SAMPLE_APP PROCESS"


def sample_app_display_param(val_u32: int, val_i16: int, val_str: str) -> str:
    # Payload (from default_sample_app_msgdefs.h):
    #   uint32 ValU32;
    #   int16  ValI16;
    #   char   ValStr[SAMPLE_APP_MISSION_STRING_VAL_LEN];
    s = (val_str or "").encode("ascii", errors="ignore")
    s = s[:SAMPLE_APP_MISSION_STRING_VAL_LEN]
    s = s + (b"\x00" * (SAMPLE_APP_MISSION_STRING_VAL_LEN - len(s)))

    payload = struct.pack(">Ih", int(val_u32) & 0xFFFFFFFF, int(val_i16) & 0xFFFF
    ) + s

    send_command(SAMPLE_APP_CMD_MID, SAMPLE_APP_DISPLAY_PARAM_CC, payload=payload, seq=1)
    return "Sent SAMPLE_APP DISPLAY_PARAM"


def set_attitude_demo(yaw_deg: float, pitch_deg: float, roll_deg: float) -> str:
    """Placeholder 'movement' API.

    This will NOT do anything in stock sample_app until you add a new command
    in the VM (recommended CC=4) that consumes these three values.

    Once the VM side is added, update MOVE_CC and the payload layout to match the
    struct you implement.
    """

    MOVE_CC = 4  # recommended next free CC after DISPLAY_PARAM

    yaw_cdeg = int(round(float(yaw_deg) * 100.0))
    pitch_cdeg = int(round(float(pitch_deg) * 100.0))
    roll_cdeg = int(round(float(roll_deg) * 100.0))

    # Proposed payload for your future command (int16 centi-deg): >hhh
    payload = struct.pack(">hhh", yaw_cdeg, pitch_cdeg, roll_cdeg)

    send_command(SAMPLE_APP_CMD_MID, MOVE_CC, payload=payload, seq=1)
    return "Sent movement demo command (requires VM-side implementation)"


def message_cFS() -> str:
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
    return "Sent."


if __name__ == "__main__":
    message_cFS()
