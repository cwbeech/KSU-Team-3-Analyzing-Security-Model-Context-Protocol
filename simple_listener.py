# cFS Telemetry Listener with packet decoding
# Filters to show EVENT messages (command confirmations) prominently
import socket
import struct

LISTEN_PORT = 2234

# APID lookup table
APID_TABLE = {
    0x0000: "CFE_ES HK",
    0x0001: "CFE_EVS HK",
    0x0002: "CFE_TBL HK",
    0x0003: "CFE_SB HK",
    0x0004: "CFE_EVS Long Event",
    0x0005: "CFE_TIME HK",
    0x0006: "CFE_TIME Diag",
    0x0008: "CFE_EVS Short Event",
    0x0080: "TO_LAB HK",
    0x0083: "SAMPLE_APP HK",
    0x0084: "CI_LAB HK",
}

EVENT_TYPE_NAMES = {1: "DEBUG", 2: "INFO", 3: "ERROR", 4: "CRITICAL"}

print(f"=== cFS Telemetry Listener on UDP port {LISTEN_PORT} ===")
print(f"Event messages (command confirmations) shown in detail")
print(f"HK packets shown as one-line summaries")
print(f"Press Ctrl+C to stop\n")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.bind(("0.0.0.0", LISTEN_PORT))
    print(f"Bound to port {LISTEN_PORT} - waiting for telemetry...\n")
except Exception as e:
    print(f"ERROR binding to port: {e}")
    exit(1)

packet_count = 0
event_count = 0
hk_count = 0

try:
    while True:
        data, addr = sock.recvfrom(4096)
        packet_count += 1

        if len(data) < 6:
            print(f"[{packet_count}] Short packet: {len(data)} bytes")
            continue

        pkt_id = struct.unpack(">H", data[0:2])[0]
        apid = pkt_id & 0x07FF
        pkt_len = struct.unpack(">H", data[4:6])[0]
        name = APID_TABLE.get(apid, f"UNKNOWN(0x{apid:04X})")

                # ---- EVENT MESSAGE (APID 0x0004 long, APID 0x0008 short) ----
        if apid in (0x0004, 0x0008) and len(data) >= 40:
            event_count += 1
            try:
                evt_kind = "SHORT EVENT"
                app_name = "?"
                event_type = 0
                event_id = 0
                msg_text = ""

                if apid == 0x0004 and len(data) >= 112:
                    # Long event: extended 76-byte header
                    #   80-81: EventType, 82-83: EventID, 92-111: AppName, 112+: Message
                    evt_kind = "LONG EVENT"
                    event_type = struct.unpack("<H", data[80:82])[0]
                    event_id = struct.unpack("<H", data[82:84])[0]
                    app_name = data[92:112].split(b'\x00')[0].decode('ascii', errors='replace')
                    if len(data) > 112:
                        msg_text = data[112:].split(b'\x00')[0].decode('ascii', errors='replace')

                elif apid == 0x0008 and len(data) >= 40:
                    # Short event: compact 16-byte header
                    #   16-35: AppName, 36-37: EventID, 38-39: EventType, 48+: Message
                    evt_kind = "SHORT EVENT"
                    app_name = data[16:36].split(b'\x00')[0].decode('ascii', errors='replace')
                    event_id = struct.unpack("<H", data[36:38])[0]
                    event_type = struct.unpack("<H", data[38:40])[0]
                    if len(data) > 48:
                        msg_text = data[48:].split(b'\x00')[0].decode('ascii', errors='replace')

                etype_str = EVENT_TYPE_NAMES.get(event_type, f"TYPE_{event_type}")

                print(f"")
                print(f"  *** {evt_kind} #{event_count} ***")
                print(f"  App:     {app_name}")
                print(f"  Type:    {etype_str} (EventID={event_id})")
                if msg_text:
                    print(f"  Message: {msg_text}")
                else:
                    print(f"  Message: (no text)")
                print(f"  (APID=0x{apid:04X}, packet #{packet_count}, {len(data)} bytes)")
                print(f"")
            except Exception as e:
                print(f"[{packet_count}] EVENT parse error: {e}")

        # ---- HK PACKETS - one-line summary ----
        else:
            hk_count += 1
            # Only print every 10th HK packet to reduce noise
            if hk_count % 10 == 1:
                print(f"  [HK #{hk_count}] {name} ({len(data)}B) | total: {packet_count} pkts, {event_count} events")

except KeyboardInterrupt:
    print(f"\n=== Stopped ===")
    print(f"Total packets: {packet_count}")
    print(f"  Events: {event_count}")
    print(f"  HK:     {hk_count}")
finally:
    sock.close()
