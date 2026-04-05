# Comprehensive cFS telemetry capture & diagnostic tool.
# Sends a NOOP, then captures ALL packets for 20 seconds,
# dumping hex for every unique APID (first 3 per APID) into event_dump.txt.
# Also prints a live summary to the console.
import socket
import struct
import sys
import time

sys.path.insert(0, ".")

LISTEN_PORT = 2234
OUTPUT_FILE = "event_dump.txt"
CAPTURE_SECONDS = 10


def hex_dump(data):
    """Return hex dump lines for a raw packet."""
    lines = []
    for i in range(0, len(data), 16):
        hex_part = ' '.join(f'{b:02x}' for b in data[i:i+16])
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in data[i:i+16])
        lines.append(f"  {i:4d}: {hex_part:<48s} | {ascii_part}")
    return lines


def ascii_strings(data, min_len=2):
    """Extract printable ASCII strings from raw data."""
    lines = []
    current_str = ""
    start_pos = 0
    for i, b in enumerate(data):
        if 32 <= b < 127:
            if not current_str:
                start_pos = i
            current_str += chr(b)
        else:
            if len(current_str) >= min_len:
                lines.append(f"  offset {start_pos:3d}: \"{current_str}\"")
            current_str = ""
    if len(current_str) >= min_len:
        lines.append(f"  offset {start_pos:3d}: \"{current_str}\"")
    return lines


# ---------------------------------------------------------------------------
print("=== cFS Diagnostic Capture Tool ===")
print(f"Listening on UDP port {LISTEN_PORT}")
print(f"Will capture for {CAPTURE_SECONDS} seconds")
print()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.bind(("0.0.0.0", LISTEN_PORT))
except OSError as e:
    print(f"ERROR: Cannot bind port {LISTEN_PORT}: {e}")
    print("Close any other listener (simple_listener.py, MCP server, etc.) first.")
    input("Press Enter to exit...")
    sys.exit(1)

sock.settimeout(1.0)

# Send a NOOP so we get a real event packet in the stream
import cfs_commands
print("Sending SAMPLE_APP NOOP to trigger an event response...")
cfs_commands.sample_app_noop()
print(f"Capturing all packets for {CAPTURE_SECONDS}s...\n")

# Tracking
apid_stats = {}         # apid -> {"count": int, "sizes": set, "packets": [bytes]}
all_output = []         # lines for output file
MAX_DUMPS_PER_APID = 3  # dump first N packets of each APID type

deadline = time.time() + CAPTURE_SECONDS
total = 0

try:
    while time.time() < deadline:
        try:
            data, addr = sock.recvfrom(4096)
        except socket.timeout:
            continue

        total += 1
        pkt_id = struct.unpack(">H", data[0:2])[0]
        apid = pkt_id & 0x07FF

        if apid not in apid_stats:
            apid_stats[apid] = {"count": 0, "sizes": set(), "packets": []}
        apid_stats[apid]["count"] += 1
        apid_stats[apid]["sizes"].add(len(data))

        # Keep first few raw packets per APID for hex dump
        if len(apid_stats[apid]["packets"]) < MAX_DUMPS_PER_APID:
            apid_stats[apid]["packets"].append(data)

        # Live console progress (every 50 packets)
        if total % 50 == 0:
            parts = []
            for a in sorted(apid_stats.keys()):
                parts.append(f"0x{a:04X}({apid_stats[a]['count']})")
            print(f"  [{total} pkts] APIDs: {', '.join(parts)}")

except KeyboardInterrupt:
    print("\nCapture interrupted by user.")

sock.close()

# ---------------------------------------------------------------------------
# Build output
# ---------------------------------------------------------------------------
sep = "=" * 70
print(f"\n{sep}")
print(f"CAPTURE COMPLETE: {total} packets, {len(apid_stats)} unique APIDs")
print(f"{sep}\n")

KNOWN_NAMES = {
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

all_output.append(f"cFS Telemetry Capture - {time.strftime('%Y-%m-%d %H:%M:%S')}")
all_output.append(f"Total packets: {total}, Unique APIDs: {len(apid_stats)}")
all_output.append(f"Capture duration: {CAPTURE_SECONDS}s")
all_output.append("")

# Summary table
all_output.append(sep)
all_output.append("APID SUMMARY")
all_output.append(sep)
for apid in sorted(apid_stats.keys()):
    s = apid_stats[apid]
    name = KNOWN_NAMES.get(apid, "UNKNOWN")
    sizes_str = ', '.join(str(x) for x in sorted(s["sizes"]))
    line = f"  APID 0x{apid:04X} ({name:25s}): {s['count']:5d} pkts, sizes=[{sizes_str}]"
    all_output.append(line)
    print(line)

all_output.append("")

# Hex dumps for each APID
for apid in sorted(apid_stats.keys()):
    s = apid_stats[apid]
    name = KNOWN_NAMES.get(apid, "UNKNOWN")
    for idx, pkt in enumerate(s["packets"]):
        all_output.append(sep)
        all_output.append(f"APID 0x{apid:04X} ({name}) - Sample #{idx+1}: {len(pkt)} bytes")
        all_output.append(sep)
        all_output.extend(hex_dump(pkt))        # Try event parsing for 0x0004 and 0x0008
        if apid in (0x0004, 0x0008) and len(pkt) >= 40:
            all_output.append("")
            all_output.append("  Event field extraction:")
            try:
                et_names = {1: "DEBUG", 2: "INFO", 3: "ERROR", 4: "CRITICAL"}
                if apid == 0x0004 and len(pkt) >= 112:
                    # Long event: extended 76-byte header
                    et = struct.unpack("<H", pkt[80:82])[0]
                    eid = struct.unpack("<H", pkt[82:84])[0]
                    app = pkt[92:112].split(b'\x00')[0].decode('ascii', errors='replace')
                    all_output.append(f"    [LONG EVENT]")
                    all_output.append(f"    EventType : {et} ({et_names.get(et, '?')})")
                    all_output.append(f"    EventID   : {eid}")
                    all_output.append(f"    AppName   : \"{app}\"")
                    if len(pkt) > 112:
                        msg = pkt[112:].split(b'\x00')[0].decode('ascii', errors='replace')
                        all_output.append(f"    Message   : \"{msg}\"")
                elif apid == 0x0008 and len(pkt) >= 40:
                    # Short event: compact 16-byte header
                    app = pkt[16:36].split(b'\x00')[0].decode('ascii', errors='replace')
                    eid = struct.unpack("<H", pkt[36:38])[0]
                    et = struct.unpack("<H", pkt[38:40])[0]
                    all_output.append(f"    [SHORT EVENT]")
                    all_output.append(f"    AppName   : \"{app}\"")
                    all_output.append(f"    EventID   : {eid}")
                    all_output.append(f"    EventType : {et} ({et_names.get(et, '?')})")
                    if len(pkt) > 48:
                        msg = pkt[48:].split(b'\x00')[0].decode('ascii', errors='replace')
                        all_output.append(f"    Message   : \"{msg}\"")
            except Exception as e:
                all_output.append(f"    Parse error: {e}")

        all_output.append("")
        strs = ascii_strings(pkt)
        if strs:
            all_output.append("  ASCII strings:")
            all_output.extend(strs)
        all_output.append("")

# Write output file
with open(OUTPUT_FILE, "w") as f:
    f.write("\n".join(all_output))

print(f"\nFull dump saved to {OUTPUT_FILE}")
print("Done! You can close this window.")
