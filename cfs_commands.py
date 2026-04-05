import socket
import struct
import threading
import sys


def _log(msg: str):
    """Log to stderr so we don't corrupt MCP's stdout JSON-RPC transport."""
    print(msg, file=sys.stderr, flush=True)

# Import configuration from local config file (not committed to git)
# Each team member sets their own VM IP in config.py
try:
    from config import TARGET_IP, CI_LAB_UDP_PORT
except ImportError:
    # Fallback defaults if config.py doesn't exist
    _log("WARNING: config.py not found. Copy config.example.py to config.py and set your VM IP.")
    TARGET_IP = "192.168.136.129"
    CI_LAB_UDP_PORT = 1234

# ============================================================================
# Telemetry Decoder
# ============================================================================
TO_LAB_TLM_PORT = 2234

# APID lookup table for known cFS telemetry packets
APID_TABLE = {
    0x0000: "CFE_ES HK",
    0x0001: "CFE_EVS HK",
    0x0002: "CFE_TBL HK",
    0x0003: "CFE_SB HK",
    0x0004: "CFE_EVS Long Event",   # <-- has human-readable text!
    0x0005: "CFE_TIME HK",
    0x0006: "CFE_TIME Diag",
    0x0008: "CFE_EVS Short Event",  # <-- same as long but WITHOUT message text
    0x0080: "TO_LAB HK",
    0x0083: "SAMPLE_APP HK",
    0x0084: "CI_LAB HK",
}


def parse_tlm_packet(data: bytes) -> dict:
    """Parse a raw cFS telemetry packet and return a structured dict."""
    if len(data) < 6:
        return {"raw_hex": data.hex(), "length": len(data)}

    pkt_id = struct.unpack(">H", data[0:2])[0]
    seq_ctrl = struct.unpack(">H", data[2:4])[0]
    pkt_len_field = struct.unpack(">H", data[4:6])[0]
    apid = pkt_id & 0x07FF
    seq_count = seq_ctrl & 0x3FFF
    name = APID_TABLE.get(apid, f"UNKNOWN(0x{apid:04X})")

    result = {
        "apid": f"0x{apid:04X}",
        "name": name,
        "seq": seq_count,
        "length": len(data),
        "is_event": apid in (0x0004, 0x0008),
    }

    # Parse CFE_EVS Long Event messages (APID 0x0004) to extract text
    # cFS Draco v7 uses an extended telemetry header (76 bytes before event payload)
    # Layout from hex dump analysis:
    #   Bytes 0-5:    CCSDS Primary Header
    #   Bytes 6-75:   Extended telemetry header (timestamp, padding, etc.)
    #   Bytes 76-79:  PacketID/SubsystemID (4 bytes)
    #   Bytes 80-81:  EventType (uint16 LE): 1=DEBUG, 2=INFO, 3=ERROR, 4=CRITICAL
    #   Bytes 82-83:  EventID (uint16 LE)
    #   Bytes 84-91:  SpacecraftID + ProcessorID (8 bytes)
    #   Bytes 92-111: AppName[20] (null-terminated ASCII)
    #   Bytes 112+:   Message text (null-terminated ASCII)
    if apid == 0x0004 and len(data) >= 112:
        try:
            event_type = struct.unpack("<H", data[80:82])[0]
            event_id = struct.unpack("<H", data[82:84])[0]
            app_name = data[92:112].split(b'\x00')[0].decode('ascii', errors='replace')
            msg_text = ""
            if len(data) > 112:
                msg_text = data[112:].split(b'\x00')[0].decode('ascii', errors='replace')

            event_type_names = {1: "DEBUG", 2: "INFO", 3: "ERROR", 4: "CRITICAL"}
            result["app"] = app_name
            result["event_id"] = event_id
            result["event_type"] = event_type_names.get(event_type, f"TYPE_{event_type}")
            result["message"] = msg_text
        except Exception as e:
            result["parse_error"] = str(e)    # Parse CFE_EVS Short Event messages (APID 0x0008)
    # Short events have a COMPACT header (no 70-byte extended padding).
    # Verified layout from hex dump of actual 172-byte packet:
    #   Bytes 0-5:    CCSDS Primary Header
    #   Bytes 6-15:   Secondary header (timestamp)
    #   Bytes 16-35:  AppName[20] (null-terminated ASCII)
    #   Bytes 36-37:  EventID (uint16 LE)
    #   Bytes 38-39:  EventType (uint16 LE): 1=DEBUG, 2=INFO, 3=ERROR, 4=CRITICAL
    #   Bytes 40-43:  SpacecraftID (uint32 LE)
    #   Bytes 44-47:  ProcessorID (uint32 LE)
    #   Bytes 48+:    Message text (null-terminated ASCII)
    elif apid == 0x0008 and len(data) >= 40:
        try:
            app_name = data[16:36].split(b'\x00')[0].decode('ascii', errors='replace')
            event_id = struct.unpack("<H", data[36:38])[0]
            event_type = struct.unpack("<H", data[38:40])[0]
            msg_text = ""
            if len(data) > 48:
                msg_text = data[48:].split(b'\x00')[0].decode('ascii', errors='replace')

            event_type_names = {1: "DEBUG", 2: "INFO", 3: "ERROR", 4: "CRITICAL"}
            result["app"] = app_name
            result["event_id"] = event_id
            result["event_type"] = event_type_names.get(event_type, f"TYPE_{event_type}")
            result["message"] = msg_text if msg_text else f"(short event, EventID={event_id})"
        except Exception as e:
            result["parse_error"] = str(e)

    return result


# ============================================================================
# Telemetry Listener (UDP port 2234)
# ============================================================================
_tlm_sock = None
_tlm_thread = None
_tlm_running = False
_last_tlm = None
_last_event = None
_tlm_lock = threading.Lock()
_tlm_count = 0
_event_count = 0
_event_log = []  # stores recent event messages


def _telemetry_listener():
    """Background thread to listen for telemetry from TO_LAB on port 2234."""
    global _tlm_running, _tlm_sock, _last_tlm, _last_event, _tlm_count, _event_count, _event_log
    while _tlm_running:
        try:
            if _tlm_sock:
                _tlm_sock.settimeout(1.0)
                data, addr = _tlm_sock.recvfrom(4096)
                parsed = parse_tlm_packet(data)
                with _tlm_lock:
                    _last_tlm = data
                    _tlm_count += 1
                    # Only log event messages (the interesting ones with text)
                    if parsed.get("is_event"):
                        _last_event = parsed
                        _event_count += 1
                        _event_log.append(parsed)
                        # Keep only last 50 events
                        if len(_event_log) > 50:
                            _event_log = _event_log[-50:]
                        app = parsed.get("app", "?")
                        etype = parsed.get("event_type", "?")
                        msg = parsed.get("message", "")
                        _log(f"[EVENT #{_event_count}] [{app}] ({etype}) {msg}")
        except socket.timeout:
            continue
        except Exception as e:
            if _tlm_running:
                _log(f"[TLM ERROR] {e}")


def start_telemetry_listener(port: int = TO_LAB_TLM_PORT):
    """Start listening for cFS telemetry in background on UDP port 2234."""
    global _tlm_thread, _tlm_running, _tlm_sock
    if _tlm_thread is not None and _tlm_thread.is_alive():
        return f"Telemetry listener already running on port {port}"
    _tlm_running = True
    _tlm_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    _tlm_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    _tlm_sock.bind(("0.0.0.0", port))
    _log(f"[INFO] Telemetry listener bound to 0.0.0.0:{port}")
    _tlm_thread = threading.Thread(target=_telemetry_listener, daemon=True)
    _tlm_thread.start()
    return f"Telemetry listener started on port {port}"


def stop_telemetry_listener():
    """Stop the telemetry listener."""
    global _tlm_running, _tlm_sock
    _tlm_running = False
    if _tlm_sock:
        try:
            _tlm_sock.close()
        except Exception:
            pass
        _tlm_sock = None
    return "Telemetry listener stopped"


def get_last_telemetry() -> dict:
    """Get the last telemetry packet received (any type)."""
    with _tlm_lock:
        if _last_tlm is None:
            return {"status": "no telemetry received", "total_packets": _tlm_count}
        return parse_tlm_packet(_last_tlm)


def get_last_event() -> dict:
    """Get the last event message (APID 0x0004) — the human-readable confirmations."""
    with _tlm_lock:
        if _last_event is None:
            return {"status": "no events received", "total_events": _event_count, "total_packets": _tlm_count}
        return {**_last_event, "total_events": _event_count, "total_packets": _tlm_count}


def get_recent_events(count: int = 10) -> list:
    """Get the most recent event messages."""
    with _tlm_lock:
        return list(_event_log[-count:])


# ============================================================================
# cFS MID mapping
# ============================================================================
CFE_PLATFORM_CMD_BASE_MID = 0x1800

# --- TO_LAB ---
TO_LAB_CMD_TOPICID = 0x80
TO_LAB_CMD_MID = CFE_PLATFORM_CMD_BASE_MID | TO_LAB_CMD_TOPICID  # 0x1880
TO_LAB_OUTPUT_ENABLE_CC = 6

# --- SAMPLE_APP ---
SAMPLE_APP_CMD_TOPICID = 0x82
SAMPLE_APP_CMD_MID = (CFE_PLATFORM_CMD_BASE_MID | SAMPLE_APP_CMD_TOPICID)  # 0x1882
SAMPLE_APP_NOOP_CC = 0
SAMPLE_APP_RESET_COUNTERS_CC = 1
SAMPLE_APP_PROCESS_CC = 2
SAMPLE_APP_DISPLAY_PARAM_CC = 3
SAMPLE_APP_SET_ATTITUDE_CC = 4

SAMPLE_APP_MISSION_STRING_VAL_LEN = 32


def cfe_platform_cmd_topicid_to_mid(topic_id: int) -> int:
    return (CFE_PLATFORM_CMD_BASE_MID | (topic_id & 0x07FF))


# ============================================================================
# CCSDS / cFS command packet builder
# ============================================================================

def _ccsds_primary_header(stream_id: int, seq: int, pkt_len_minus_1: int) -> bytes:
    """Build CCSDS primary header (always big-endian per CCSDS spec)."""
    pkt_id = (0 << 13) | (1 << 12) | (1 << 11) | (stream_id & 0x07FF)
    seq_ctrl = (3 << 14) | (seq & 0x3FFF)
    return struct.pack(">HHH", pkt_id, seq_ctrl, pkt_len_minus_1 & 0xFFFF)


def _cfs_checksum_xor(packet: bytes) -> int:
    c = 0
    for b in packet:
        c ^= b
    return c & 0xFF


def build_cfs_command(mid: int, cmd_code: int, payload: bytes = b"", seq: int = 0) -> bytes:
    """Build a cFS command packet suitable for CI_LAB ingest."""
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
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(packet, (target_ip, port))
    finally:
        sock.close()


def send_command(mid: int, cc: int, payload: bytes = b"", seq: int = 1) -> None:
    pkt = build_cfs_command(mid, cc, payload=payload, seq=seq)
    send_ci_lab(pkt)


# ============================================================================
# TO_LAB Commands
# ============================================================================

def enable_telemetry(dest_ip: str = None) -> str:
    """Enable cFS to send telemetry back to this computer.
    
    This must be called once after cFS starts to receive confirmations.
    If dest_ip is not provided, it will use the gateway IP (e.g., 192.168.136.1).
    """
    if dest_ip is None:
        # Derive Windows host IP from VM IP (gateway is .1 on VMware NAT)
        parts = TARGET_IP.split('.')
        dest_ip = f"{parts[0]}.{parts[1]}.{parts[2]}.1"

    # Payload: char dest_IP[16] - null-padded ASCII string
    ip_bytes = dest_ip.encode('ascii')[:16]
    ip_bytes = ip_bytes + b'\x00' * (16 - len(ip_bytes))

    send_command(TO_LAB_CMD_MID, TO_LAB_OUTPUT_ENABLE_CC, payload=ip_bytes, seq=1)

    # Also start the telemetry listener if not already running
    listener_status = start_telemetry_listener()

    return f"Sent TO_LAB ENABLE_OUTPUT: dest={dest_ip} - {listener_status}"


# ============================================================================
# SAMPLE_APP Commands
# ============================================================================

def sample_app_noop() -> str:
    """Send NOOP command to sample_app."""
    send_command(SAMPLE_APP_CMD_MID, SAMPLE_APP_NOOP_CC, payload=b"", seq=1)
    return "Sent SAMPLE_APP NOOP"


def sample_app_reset_counters() -> str:
    """Reset sample_app command counters."""
    send_command(SAMPLE_APP_CMD_MID, SAMPLE_APP_RESET_COUNTERS_CC, payload=b"", seq=1)
    return "Sent SAMPLE_APP RESET_COUNTERS"


def sample_app_process() -> str:
    """Send PROCESS command to sample_app."""
    send_command(SAMPLE_APP_CMD_MID, SAMPLE_APP_PROCESS_CC, payload=b"", seq=1)
    return "Sent SAMPLE_APP PROCESS"


def sample_app_display_param(val_u32: int, val_i16: int, val_str: str) -> str:
    """Send sample_app DISPLAY_PARAM command."""
    # Payload: uint32 ValU32; int16 ValI16; char ValStr[32]
    # cFS on x86 Linux uses little-endian for struct payloads
    s = (val_str or "").encode("ascii", errors="ignore")
    s = s[:SAMPLE_APP_MISSION_STRING_VAL_LEN]
    s = s + (b"\x00" * (SAMPLE_APP_MISSION_STRING_VAL_LEN - len(s)))

    payload = struct.pack("<Ih", int(val_u32) & 0xFFFFFFFF, int(val_i16) & 0xFFFF) + s

    send_command(SAMPLE_APP_CMD_MID, SAMPLE_APP_DISPLAY_PARAM_CC, payload=payload, seq=1)
    return "Sent SAMPLE_APP DISPLAY_PARAM"


def set_attitude_demo(yaw_deg: float, pitch_deg: float, roll_deg: float) -> str:
    """Set spacecraft attitude (yaw, pitch, roll in degrees)."""
    yaw_cdeg = int(round(float(yaw_deg) * 100.0))
    pitch_cdeg = int(round(float(pitch_deg) * 100.0))
    roll_cdeg = int(round(float(roll_deg) * 100.0))

    # cFS on x86 Linux uses little-endian for struct payloads
    payload = struct.pack("<hhh", yaw_cdeg, pitch_cdeg, roll_cdeg)

    send_command(SAMPLE_APP_CMD_MID, SAMPLE_APP_SET_ATTITUDE_CC, payload=payload, seq=1)
    return f"Sent SET_ATTITUDE: yaw={yaw_deg}, pitch={pitch_deg}, roll={roll_deg}"


# ============================================================================
# CFE_ES Commands
# ============================================================================

def message_cFS() -> str:
    """Send ES NOOP command to cFS."""
    ES_CMD_TOPICID = 6
    EXAMPLE_MID = cfe_platform_cmd_topicid_to_mid(ES_CMD_TOPICID)
    EXAMPLE_CMD_CODE = 0

    pkt = build_cfs_command(EXAMPLE_MID, EXAMPLE_CMD_CODE, payload=b"", seq=1)
    _log(
        f"Sending {len(pkt)} bytes to {TARGET_IP}:{CI_LAB_UDP_PORT} "
        f"(MID=0x{EXAMPLE_MID:04X}, CC={EXAMPLE_CMD_CODE}) ..."
    )
    send_ci_lab(pkt)
    return "Sent."


if __name__ == "__main__":
    message_cFS()
