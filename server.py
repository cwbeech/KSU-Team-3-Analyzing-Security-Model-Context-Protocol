# Local MCP server for Claude Desktop (stdio transport, no Auth0)
# main.py is for the web deployment (streamable-http + Auth0)
import signal
import sys
import time
import cfs_commands
from mcp.server.fastmcp import FastMCP


def signal_handler(_sig, _frame):
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
    except Exception:
        return 0


@mcp.tool()
def count_vowels(word: str) -> int:
    try:
        if not isinstance(word, str):
            return 0
        return (word.lower().count("a") + word.lower().count("e") +
                word.lower().count("i") + word.lower().count("o") +
                word.lower().count("u"))
    except Exception:
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
    for _ in range(2, n + 1):
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
    before_count = 0
    with cfs_commands._tlm_lock:
        before_count = cfs_commands._event_count

    result = send_fn()

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
    
# -------------------------------
# Mock Telemetry Synchronization Test Tools
# -------------------------------

mock_sync_state = {
    "subsystem_status": "OFF",
    "previous_subsystem_status": "OFF",
    "test_mode": "normal",  # normal, delayed, stale_once
    "last_command": "None",
    "last_write_time": None,
    "last_read_time": None
}


def _current_time():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


@mcp.tool()
def set_sync_test_mode(mode: str) -> str:
    """Set synchronization test mode: normal, delayed, or stale_once."""
    allowed_modes = ["normal", "delayed", "stale_once"]

    if mode not in allowed_modes:
        return f"Invalid mode. Choose one of: {allowed_modes}"

    mock_sync_state["test_mode"] = mode
    return f"Synchronization test mode set to: {mode}"


@mcp.tool()
def turn_mock_subsystem_on() -> str:
    """Simulate sending a command that turns a mock subsystem ON."""
    mock_sync_state["previous_subsystem_status"] = mock_sync_state["subsystem_status"]
    mock_sync_state["subsystem_status"] = "ON"
    mock_sync_state["last_command"] = "TURN_ON"
    mock_sync_state["last_write_time"] = _current_time()

    return (
        "Command sent: TURN_ON\n"
        f"Actual subsystem state is now: {mock_sync_state['subsystem_status']}\n"
        f"Write time: {mock_sync_state['last_write_time']}"
    )


@mcp.tool()
def turn_mock_subsystem_off() -> str:
    """Simulate sending a command that turns a mock subsystem OFF."""
    mock_sync_state["previous_subsystem_status"] = mock_sync_state["subsystem_status"]
    mock_sync_state["subsystem_status"] = "OFF"
    mock_sync_state["last_command"] = "TURN_OFF"
    mock_sync_state["last_write_time"] = _current_time()

    return (
        "Command sent: TURN_OFF\n"
        f"Actual subsystem state is now: {mock_sync_state['subsystem_status']}\n"
        f"Write time: {mock_sync_state['last_write_time']}"
    )


@mcp.tool()
def read_mock_telemetry() -> str:
    """Read mock telemetry. Can return normal, delayed, or stale data depending on test mode."""
    mode = mock_sync_state["test_mode"]

    if mode == "delayed":
        time.sleep(4)

    if mode == "stale_once":
        reported_status = mock_sync_state["previous_subsystem_status"]
        mock_sync_state["test_mode"] = "normal"
    else:
        reported_status = mock_sync_state["subsystem_status"]

    mock_sync_state["last_read_time"] = _current_time()

    return (
        f"Telemetry mode: {mode}\n"
        f"Reported telemetry status: {reported_status}\n"
        f"Actual internal subsystem status: {mock_sync_state['subsystem_status']}\n"
        f"Last command: {mock_sync_state['last_command']}\n"
        f"Last write time: {mock_sync_state['last_write_time']}\n"
        f"Telemetry read time: {mock_sync_state['last_read_time']}"
    )


if __name__ == "__main__":
    try:
        print("Starting MCP server 'cfs-commander' on stdio", file=sys.stderr)
        mcp.run()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        time.sleep(5)
