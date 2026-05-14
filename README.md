# KSU-Team-3-Analyzing-Security-Model-Context-Protocol

## Local NASA cFS Command Integration via MCP Server

This project enables sending commands from Claude to NASA cFS running on an Ubuntu VM using the Model Context Protocol (MCP).

---

## Setup

### 1. Configure Your VM IP

Copy the example config and set your VM's IP address:

```powershell
copy config.example.py config.py
```

Edit `config.py` and set your Ubuntu VM's IP:

```python
TARGET_IP = "192.168.136.XXX"  # Replace with your VM's IP
```

### 2. Configure Claude Desktop

Copy the contents of `EXAMPLE_claude_desktop_config.json` into your local `claude_desktop_config.json` file.

### 3. Install Dependencies

```powershell
pip install -r requirements.txt
```

---

## Running the MCP Server

Start the FastMCP server (for Claude Desktop integration):

```powershell
python server.py
```

---

## Testing Commands

### Quick Test (ES NOOP)

Send a test command directly to verify connectivity:

```powershell
python test_noop.py
```

You should see on the VM console:

```
EVS Port1 ... CFE_ES 3: No-op command:
```

### Using the Command Library

```python
import cfs_commands

# Send ES NOOP (Executive Services No-Op)
cfs_commands.message_cFS()

# Send sample_app commands
cfs_commands.sample_app_noop()
cfs_commands.sample_app_reset_counters()
cfs_commands.sample_app_process()
cfs_commands.sample_app_display_param(val_u32=123, val_i16=456, val_str="hello")

# Send attitude command (requires VM-side implementation)
cfs_commands.set_attitude_demo(yaw_deg=10.0, pitch_deg=5.0, roll_deg=-3.0)
```

---

## Available MCP Tools (via server.py)

| Tool                                              | Description                               |
| ------------------------------------------------- | ----------------------------------------- |
| `count-r(str)`                                    | Count number of Rs in a string            |
| `count_vowels(str)`                               | Count number of vowels in a string        |
| `count-r(str)`                                    | Count number of Rs in a string            |
| `enable_telemetry()`                              | Enable telemetry streaming and status report-ing from the cFS environment |
| `message_cFS()`                                   | Send ES NOOP command                      |
| `sample_noop()`                                   | Send sample_app NOOP                      |
| `sample_reset_counters()`                         | Reset sample_app counters                 |
| `sample_process()`                                | Trigger sample_app process                |
| `sample_display_param(val_u32, val_i16, val_str)` | Display parameters                        |
| `set_attitude_demo(yaw_deg, pitch_deg, roll_deg)` | Set attitude (requires VM implementation) |
| `get_recent_events()`                             | Retrieve recently generated cFS event messages and system logs |
| `get_telemetry_status()`                          | Retrieve current telemetry connection and data stream status information |
| `configure_mode()`                                | Configure telemetry synchronization and latency testing modes |
| `execute command()`                               | Send operational commands to cFS subsystems through MCP |
| `read_status()`                                   | Retrieve current subsystem telemetry and execution state |
| `reset_system()`                                  | Reset subsystem state and telemetry synchronization variables |

---

## Project Structure

| File                | Description                                  |
| ------------------- | -------------------------------------------- |
| `server.py`         | MCP Server exposing cFS commands as tools    |
| `cfs_commands.py`   | cFS command library (CCSDS packet builder)   |
| `test_noop.py`      | Standalone test script                       |
| `config.py`         | Local config with your VM IP (not committed) |
| `config.example.py` | Template for config.py                       |
| `secrets/`          | SSH keys (not committed)                     |

---

## VM Requirements

On your Ubuntu VM, ensure cFS is running:

```bash
cd ~/Desktop/cFS/build/exe/cpu1
sudo ./core-cpu1
```

CI_LAB should be listening on UDP port 1234.

## cFS Forked Repositories
The following repositories contain our modified cFS applications and lab components used for MCP
integration, telemetry support, and movement command testing. These repositories should be copied into
the corresponding application directories within the local cFS installation to replace the default files.

Sample_App: `https://github.com/SebastianAlturckCarlos/sample_app`

To_Lab: `https://github.com/SebastianAlturckCarlos/to_lab`

Sch_Lab: `https://github.com/SebastianAlturckCarlos/sch_lab`

## Deployed Mock NASA cFS Command Integration via MCP Server

This project enables testing authentication by mocking cFS response. Mocked reponses have a 20% chance of performing a simulated failure.

## How to Connect Claude MCP-cFS

1. Navigate to `https://claude.ai/settings/connectors`
2. Click Add custom connecter
3. Insert `https://ksu-team-3-analyzing-security-model-context-prot-production.up.railway.app/mcp` into the "Remote MCP server URL" field
4. Click "Add" to confirm
5. Click "Connect"
6. If it is your first time logging in you will need to create an account. Click sign up and create an account. It doesn't have to be a real email, but you do need to remember your login info
7. From there, you should be redirected back. Feel free to test it by sending the following message to claude:
```Count the number of vowels from the following sentence: "The quick brown fox jumps over the lazy dog" using the appropriate tool.```
8. Claude should reply with "11"

Note: For ChatGPT, the steps are roughly the same. However, before adding the new app to ChatGTP one should disable all scopes in "Advanced OAuth Settings" and then create app.
