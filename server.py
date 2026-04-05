from mcp.server.fastmcp import FastMCP
import time
import signal
import sys
import cfs_commands

def signal_handler(sig, frame):
    print("Shutting down server gracefully", file=sys.stderr)
    cfs_commands.stop_telemetry_listener()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

mcp = FastMCP(
    name="cfs_commander",
    host="127.0.0.1",
    port=5000
)

@mcp.tool()
def count_r(word: str) -> int:
    """Count the number of 'r' letters in a given word."""
    try:
        if not isinstance(word, str):
            return 0
        return word.lower().count("r")
    except Exception as e:
        return 0

@mcp.tool()
def count_vowels(word: str) -> int:
    try:
        if not isinstance(word, str):
            return 0
        return word.lower().count("a") + word.lower().count("e") + word.lower().count("i") + word.lower().count("o") + word.lower().count("u")
    except Exception as e:
        return 0

@mcp.tool()
def fibonacci(n: int) -> int:
    if not isinstance(n, int):
        return 0
    if n <= 1: 
        return n
    curr = 0
    prev1 = 1
    prev2 = 0
    for i in range(2, n + 1):
        curr = prev1 + prev2
        prev2 = prev1
        prev1 = curr
    return curr

@mcp.tool()
def enable_telemetry(dest_ip: str = "") -> str:
    """Enable cFS to send telemetry back to this computer.
    
    This must be called once after cFS starts to receive confirmations.
    If dest_ip is not provided, it will use the gateway IP (e.g., 192.168.136.1).
    """
    try:
        ip = dest_ip if dest_ip else None
        return str(cfs_commands.enable_telemetry(dest_ip=ip))
    except Exception as e:
        return f"Error: {e}"


def _send_and_wait_for_event(send_fn, description, wait_secs=2.0):
    """Send a command and wait briefly for an event confirmation from cFS."""
    # Record the event count before sending
    before_count = 0
    with cfs_commands._tlm_lock:
        before_count = cfs_commands._event_count

    # Send the command
    result = send_fn()

    # Wait for a new event to arrive (up to wait_secs)
    deadline = time.time() + wait_secs
    while time.time() < deadline:
        with cfs_commands._tlm_lock:
            if cfs_commands._event_count > before_count:
                evt = cfs_commands._last_event
                app = evt.get("app", "?")
                etype = evt.get("event_type", "?")
                eid = evt.get("event_id", "?")
                msg = evt.get("message", "")
                return (
                    f"{result}\n"
                    f"cFS Response: [{app}] {etype} (EventID={eid})"
                    + (f" - {msg}" if msg else "")
                )
        time.sleep(0.1)

    return f"{result}\n(no event confirmation received within {wait_secs}s)"


@mcp.tool()
def message_cFS() -> str:
    """Send ES NOOP command to cFS and wait for confirmation event."""
    try:
        return _send_and_wait_for_event(cfs_commands.message_cFS, "ES NOOP")
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def sample_noop() -> str:
    """Send NOOP command to sample_app and wait for confirmation event."""
    try:
        return _send_and_wait_for_event(cfs_commands.sample_app_noop, "SAMPLE_APP NOOP")
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def sample_reset_counters() -> str:
    """Reset sample_app command counters and wait for confirmation event."""
    try:
        return _send_and_wait_for_event(cfs_commands.sample_app_reset_counters, "SAMPLE_APP RESET_COUNTERS")
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def sample_process() -> str:
    """Send PROCESS command to sample_app and wait for confirmation event."""
    try:
        return _send_and_wait_for_event(cfs_commands.sample_app_process, "SAMPLE_APP PROCESS")
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def sample_display_param(val_u32: int, val_i16: int, val_str: str) -> str:
    """Send sample_app DISPLAY_PARAM command and wait for confirmation event."""
    try:
        return _send_and_wait_for_event(
            lambda: cfs_commands.sample_app_display_param(val_u32=val_u32, val_i16=val_i16, val_str=val_str),
            "SAMPLE_APP DISPLAY_PARAM"
        )
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def set_attitude_demo(yaw_deg: float, pitch_deg: float, roll_deg: float) -> str:
    """Set spacecraft attitude (yaw, pitch, roll in degrees) and wait for confirmation event."""
    try:
        return _send_and_wait_for_event(
            lambda: cfs_commands.set_attitude_demo(yaw_deg=yaw_deg, pitch_deg=pitch_deg, roll_deg=roll_deg),
            "SET_ATTITUDE"
        )
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def get_recent_events(count: int = 10) -> str:
    """Get the most recent cFS event messages (command confirmations, errors, etc.).
    
    Returns the last N events received from cFS telemetry.
    Events include app name, event type, event ID, and message text.
    """
    try:
        events = cfs_commands.get_recent_events(count=count)
        if not events:
            return "No events received yet. Make sure telemetry is enabled (call enable_telemetry first)."
        lines = [f"Last {len(events)} cFS events:"]
        for i, evt in enumerate(events):
            app = evt.get("app", "?")
            etype = evt.get("event_type", "?")
            eid = evt.get("event_id", "?")
            msg = evt.get("message", "")
            apid = evt.get("apid", "?")
            lines.append(f"  [{i+1}] [{app}] {etype} (EventID={eid}, APID={apid})"
                         + (f" - {msg}" if msg else ""))
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def get_telemetry_status() -> str:
    """Get current telemetry listener status: total packets, events, last event details."""
    try:
        evt = cfs_commands.get_last_event()
        status_parts = [
            f"Total packets received: {evt.get('total_packets', 0)}",
            f"Total events received: {evt.get('total_events', 0)}",
        ]
        if "app" in evt:
            status_parts.append(f"Last event: [{evt['app']}] {evt.get('event_type','?')} "
                                f"(EventID={evt.get('event_id','?')}) {evt.get('message','')}")
        else:
            status_parts.append(f"Last event: {evt.get('status', 'none')}")
        return "\n".join(status_parts)
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    try:
        print("Starting MCP server 'cfs-commander' on 127.0.0.1:5000", file=sys.stderr)
        mcp.run()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        time.sleep(5)