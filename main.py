import signal
import sys
import cfs_commands
import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.auth.settings import AuthSettings
from pydantic import AnyHttpUrl
from utils.auth import create_auth0_verifier

load_dotenv()

token_verifier = create_auth0_verifier()

auth0_domain = os.getenv("AUTH0_DOMAIN")
resource_server_url = os.getenv("RESOURCE_SERVER_URL")

def signal_handler(_sig, _frame):
    print("Shutting down server gracefully")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

mcp = FastMCP(
    "yt-mcp",
    host="0.0.0.0",
    token_verifier=token_verifier,
    auth=AuthSettings(
        issuer_url = AnyHttpUrl(f"https://{auth0_domain}/"),
        resource_server_url = AnyHttpUrl(resource_server_url),
        required_scopes=["openid", "profile", "email", "address", "phone"],
    ),
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
def message_cFS() -> str:
    try:
        return cfs_commands.message_cFS()
    except Exception:
        return "Error"

@mcp.tool()
def sample_noop() -> str:
    try:
        return cfs_commands.sample_app_noop()
    except Exception:
        return "Error"

@mcp.tool()
def sample_reset_counters() -> str:
    try:
        return cfs_commands.sample_app_reset_counters()
    except Exception:
        return "Error"

@mcp.tool()
def sample_process() -> str:
    try:
        return cfs_commands.sample_app_process()
    except Exception:
        return "Error"

@mcp.tool()
def sample_display_param(val_u32: int, val_i16: int, val_str: str) -> str:
    """Send sample_app DISPLAY_PARAM (requires correct SAMPLE_APP_MISSION_STRING_VAL_LEN in cfs_commands.py)."""
    try:
        return cfs_commands.sample_app_display_param(val_u32=val_u32, val_i16=val_i16, val_str=val_str)
    except Exception:
        return "Error"

@mcp.tool()
def set_attitude_demo(yaw_deg: float, pitch_deg: float, roll_deg: float) -> str:
    """Movement demo command.

    NOTE: Requires you to add CC=4 (or whatever you choose) in sample_app on the VM.
    """
    try:
        return cfs_commands.set_attitude_demo(yaw_deg=yaw_deg, pitch_deg=pitch_deg, roll_deg=roll_deg)
    except Exception:
        return "Error"

if __name__ == "__main__":
    try:
        print("Starting MCP server 'count-r' on 127.0.0.1:5000")
        mcp.run()
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)