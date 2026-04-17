# This is used for the deployed MCP Server found at https://ksu-team-3-analyzing-security-model-context-prot-production.up.railway.app/mcp
# cFS integration does not work in deployed environment. Results are mocked.

import random
import signal
import sys
import cfs_commands
import os
import time
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.authorization import require_scopes
from fastmcp.server.auth import JWTVerifier, RemoteAuthProvider
from pydantic import AnyHttpUrl

load_dotenv()

auth0_domain = os.getenv("AUTH0_DOMAIN")
resource_server_url = os.getenv("RESOURCE_SERVER_URL")

if not auth0_domain:
    raise ValueError("AUTH0_DOMAIN environment variable is required")
if not resource_server_url:
    raise ValueError("RESOURCE_SERVER_URL environment variable is required")

token_verifier = JWTVerifier(
    jwks_uri=AnyHttpUrl(f"https://{auth0_domain}/.well-known/jwks.json"),
    issuer=f"https://{auth0_domain}/",
    audience=resource_server_url
)

def signal_handler(_sig, _frame):
    print("Shutting down server gracefully", file=sys.stderr)
    cfs_commands.stop_telemetry_listener()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

mcp = FastMCP(
    "mcp-cfs",
    auth=RemoteAuthProvider(
        token_verifier=token_verifier,
        authorization_servers=[AnyHttpUrl(f"https://{auth0_domain}/")],
        base_url=AnyHttpUrl(resource_server_url)
    )
)

@mcp.tool(auth=require_scopes("read:cFS"))
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
        return word.lower().count("a") + word.lower().count("e") + word.lower().count("i") + word.lower().count("o") + word.lower().count("u")
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
    
    This must be called once after cFS starts to receive confirmations.    If dest_ip is not provided, it will use the gateway IP (e.g., 192.168.136.1).
    """
    try:
        if (random.randint(1, 10) <= 2):  # 20% chance to simulate an error
            raise RuntimeError("Simulated telemetry enable failure")
        else:
            return "Simulated telemetry enabled successfully."
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
        if (random.randint(1, 10) <= 2):  # 20% chance to simulate an error
            raise RuntimeError("Simulated cFS NOOP failure")
        else:
            return "Simulated cFS NOOP sent successfully."
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def sample_noop() -> str:
    """Send NOOP command to sample_app and wait for confirmation event."""
    try:
        if (random.randint(1, 10) <= 2):  # 20% chance to simulate an error
            raise RuntimeError("Simulated sample_app NOOP failure")
        else:
            return "Simulated sample_app NOOP sent successfully."
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def sample_reset_counters() -> str:
    """Reset sample_app command counters and wait for confirmation event."""
    try:
        if (random.randint(1, 10) <= 2):  # 20% chance to simulate an error
            raise RuntimeError("Simulated sample_app reset counters failure")
        else:
            return "Simulated sample_app reset counters sent successfully."
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def sample_process() -> str:
    """Send PROCESS command to sample_app and wait for confirmation event."""
    try:
        if (random.randint(1, 10) <= 2):  # 20% chance to simulate an error
            raise RuntimeError("Simulated process command failure")
        else:
            return "Simulated process command sent successfully."
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def sample_display_param(val_u32: int, val_i16: int, val_str: str) -> str:
    """Send sample_app DISPLAY_PARAM command and wait for confirmation event."""
    try:
        if (random.randint(1, 10) <= 2):  # 20% chance to simulate an error
            raise RuntimeError("Simulated sample_app DISPLAY_PARAM failure")
        else:
            return "Simulated sample_app DISPLAY_PARAM sent successfully."
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def set_attitude_demo(yaw_deg: float, pitch_deg: float, roll_deg: float) -> str:
    """Set spacecraft attitude (yaw, pitch, roll in degrees) and wait for confirmation event."""
    try:
        if (random.randint(1, 10) <= 2):  # 20% chance to simulate an error
            raise RuntimeError("Simulated set_attitude_demo failure")
        else:
            return "Simulated set_attitude_demo sent successfully."
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def get_recent_events(count: int = 10) -> str:
    """Get the most recent cFS event messages (command confirmations, errors, etc.).
    
    Returns the last N events received from cFS telemetry.
    Events include app name, event type, event ID, and message text.
    """
    try:
        if (random.randint(1, 10) <= 2):  # 20% chance to simulate an error
            raise RuntimeError("Simulated get_recent_events failure")
        else:
            return "Simulated get_recent_events sent successfully."
    except Exception as e:
        return f"Error: {e}"

@mcp.tool()
def get_telemetry_status() -> str:
    """Get current telemetry listener status: total packets, events, last event details."""
    try:
        if (random.randint(1, 10) <= 2):  # 20% chance to simulate an error
            raise RuntimeError("Simulated get_telemetry_status failure")
        else:
            return "Simulated get_telemetry_status sent successfully."
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    try:
        print("Starting MCP server 'mcp-cfs'", file=sys.stderr)
        mcp.run(transport='streamable-http')
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        time.sleep(5)