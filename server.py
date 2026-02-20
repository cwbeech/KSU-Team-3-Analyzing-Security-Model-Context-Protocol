from mcp.server.fastmcp import FastMCP
import time
import signal
import sys
import mcp_server

def signal_handler(sig, frame):
    print("Shutting down server gracefully")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

mcp = FastMCP(
    name="count-r",
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
def message_cFS() -> str:
    try:
        return mcp_server.message_cFS()
    except Exception as e:
        return "Error"

if __name__ == "__main__":
    try:
        print("Starting MCP server 'count-r' on 127.0.0.1:5000")
        mcp.run()
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)