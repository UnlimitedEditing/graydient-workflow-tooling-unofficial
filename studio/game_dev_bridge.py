"""
Game Dev Bridge for PirateUI.
Provides unified integration with:
1. VAIL (Virtual Agent Interface Layer for Unreal Engine 5.8 over TCP: 55557)
2. Godot MCP (Model Context Protocol bridge for Godot 4.6.1)
3. 3D Asset Pipeline (Ships PirateUI M3DS/decoded .glb/.ply models straight to game projects)
"""

import os
import sys
import json
import socket
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List

BASE_DIR = Path(__file__).resolve().parent.parent
STUDIO_DIR = Path(__file__).resolve().parent
RUNNER_JS = STUDIO_DIR / "godot_mcp_runner.js"

# Unreal VAIL Configuration
VAIL_HOST = "127.0.0.1"
VAIL_PORT = 55557
VAIL_CLI = Path(r"D:\UE5.8\VAIL\python\vail_cli.py")

# Godot MCP Configuration
GODOT_EXE = Path(r"D:\Godot_v4.6.1-stable_mono_win64\Godot_v4.6.1-stable_mono_win64_console.exe")
GODOT_MCP_DIR = Path(r"D:\godot-mcp")

# Unity Bridge Configuration (PirateUIBridge.cs HTTP listener)
UNITY_HOST = "127.0.0.1"
UNITY_PORT = 55558
UNITY_HUB_PATH = Path(r"C:\Program Files\Unity\Hub\Editor")

def check_vail_connection(timeout: float = 1.0) -> Dict[str, Any]:
    """Probes whether Unreal Engine 5.8 is currently running with the VAIL plugin active."""
    status = {
        "engine": "Unreal Engine 5.8",
        "plugin": "VAIL (Virtual Agent Interface Layer)",
        "host": VAIL_HOST,
        "port": VAIL_PORT,
        "online": False,
        "details": None
    }
    try:
        with socket.create_connection((VAIL_HOST, VAIL_PORT), timeout=timeout) as s:
            status["online"] = True
            # Send quick version probe
            payload = json.dumps({"command": "vail_plugin_version", "params": {}}).encode("utf-8") + b"\n"
            s.sendall(payload)
            buf = b""
            s.settimeout(2.0)
            while True:
                chunk = s.recv(4096)
                if not chunk: break
                buf += chunk
                try:
                    res = json.loads(buf.decode("utf-8"))
                    status["details"] = res
                    break
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        status["error"] = str(e)
    return status

def send_vail_command(command: str, params: Optional[Dict[str, Any]] = None, timeout: float = 10.0) -> Dict[str, Any]:
    """Sends a direct JSON command to Unreal Engine 5.8 VAIL plugin over TCP."""
    params = params or {}
    try:
        with socket.create_connection((VAIL_HOST, VAIL_PORT), timeout=timeout) as s:
            payload = json.dumps({"command": command, "params": params}).encode("utf-8") + b"\n"
            s.sendall(payload)
            buf = b""
            s.settimeout(timeout)
            while True:
                chunk = s.recv(4096)
                if not chunk: break
                buf += chunk
                try:
                    return json.loads(buf.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
            return {"status": "error", "message": "Connection closed before complete response received."}
    except (ConnectionRefusedError, TimeoutError, socket.timeout):
        # Fallback to check if CLI can give more context
        return {
            "status": "offline",
            "message": f"Unreal Engine 5.8 is not running with VAIL listening on {VAIL_HOST}:{VAIL_PORT}. Start your Unreal project (e.g. D:\\UE5.8\\vailtest) to activate live commands.",
            "command": command
        }
    except Exception as e:
        return {"status": "error", "message": f"VAIL communication error: {str(e)}"}

def check_godot_status() -> Dict[str, Any]:
    """Inspects local Godot Engine 4.x and Godot MCP installation status."""
    has_exe = GODOT_EXE.exists()
    has_mcp = (GODOT_MCP_DIR / "build" / "tools" / "ToolRegistry.js").exists()
    
    version_info = "Unknown"
    tools = []
    
    if has_mcp:
        try:
            res = send_godot_tool("get_godot_version", {})
            if res.get("status") == "success" and "result" in res:
                content = res["result"].get("content", [])
                if content and len(content) > 0:
                    version_info = content[0].get("text", "4.6.1")
            
            # Fetch registered tools
            list_res = send_godot_tool("list_tools", {})
            if list_res.get("status") == "success":
                tools = list_res.get("tools", [])
        except Exception:
            pass

    return {
        "engine": "Godot Engine 4.x",
        "mcp_server": "Godot MCP",
        "executable_path": str(GODOT_EXE),
        "executable_exists": has_exe,
        "mcp_installed": has_mcp,
        "version": version_info,
        "online": has_exe and has_mcp,
        "available_tools": tools
    }

def send_godot_tool(tool_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Executes a tool from the Godot MCP ToolRegistry via godot_mcp_runner.js."""
    params = params or {}
    cmd = [
        "node",
        str(RUNNER_JS),
        tool_name,
        json.dumps(params)
    ]
    env = os.environ.copy()
    env["GODOT_PATH"] = str(GODOT_EXE)

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=30
        )
        if proc.returncode != 0:
            return {
                "status": "error",
                "message": proc.stderr.strip() or proc.stdout.strip() or f"Process exited with code {proc.returncode}"
            }
        try:
            return json.loads(proc.stdout.strip())
        except json.JSONDecodeError:
            return {"status": "success", "raw_output": proc.stdout.strip()}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": f"Godot MCP tool '{tool_name}' timed out after 30s"}
    except Exception as e:
        return {"status": "error", "message": f"Error running Godot MCP tool: {str(e)}"}

def check_unity_connection(timeout: float = 1.0) -> Dict[str, Any]:
    """Probes whether Unity Editor is active with PirateUIBridge listening on 55558."""
    import urllib.request
    status = {
        "engine": "Unity",
        "plugin": "PirateUI Unity Bridge",
        "host": UNITY_HOST,
        "port": UNITY_PORT,
        "online": False,
        "details": None
    }
    try:
        url = f"http://{UNITY_HOST}:{UNITY_PORT}/status"
        req = urllib.request.Request(url, headers={"User-Agent": "PirateUI"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                status["online"] = True
                status["details"] = data
    except Exception as e:
        status["error"] = str(e)
    return status

def send_unity_command(command: str, payload: Any = "", timeout: float = 10.0) -> Dict[str, Any]:
    """Sends an editor command to Unity via the local bridge (http://127.0.0.1:55558/command)."""
    import urllib.request
    url = f"http://{UNITY_HOST}:{UNITY_PORT}/command"
    payload_str = json.dumps(payload) if isinstance(payload, (dict, list)) else str(payload or "")
    body = json.dumps({"command": command, "payload": payload_str}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"status": "error", "message": f"Unity bridge error: {str(e)}"}

def deploy_mesh_to_game(
    mesh_path: str,
    target_engine: str = "godot",
    custom_project_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Copies a generated or decoded 3D mesh (.glb / .ply) from PirateUI
    into a Godot or Unreal Engine project directory.
    """
    src = Path(mesh_path)
    if not src.is_absolute():
        candidates = [
            BASE_DIR / "renders" / "decoded" / mesh_path,
            BASE_DIR / "renders" / mesh_path,
            BASE_DIR / mesh_path
        ]
        src = next((c for c in candidates if c.exists()), src)

    if not src.exists():
        return {"status": "error", "message": f"Source 3D asset not found: {mesh_path}"}

    target_engine = target_engine.lower()
    if target_engine in ["godot", "godot4", "godot-mcp"]:
        dest_dir = Path(custom_project_dir) if custom_project_dir else (BASE_DIR / "game_exports" / "godot_assets")
    elif target_engine in ["unreal", "ue", "ue5", "vail"]:
        dest_dir = Path(custom_project_dir) if custom_project_dir else (Path(r"D:\UE5.8\vailtest\Content\Imported_PirateUI"))
    elif target_engine in ["unity", "unity-engine", "unity6", "unity2022"]:
        dest_dir = Path(custom_project_dir) if custom_project_dir else (BASE_DIR / "game_exports" / "unity_assets")
    else:
        dest_dir = BASE_DIR / "game_exports" / target_engine

    try:
        os.makedirs(dest_dir, exist_ok=True)
        dest_file = dest_dir / src.name
        shutil.copy2(src, dest_file)

        # If deploying to Unity, attempt to trigger live asset database refresh
        if target_engine in ["unity", "unity-engine", "unity6", "unity2022"]:
            try:
                unity_status = check_unity_connection(timeout=0.5)
                if unity_status.get("online"):
                    send_unity_command("refresh_assets")
            except Exception:
                pass

        return {
            "status": "success",
            "message": f"Successfully deployed {src.name} to {target_engine.upper()}",
            "source": str(src),
            "destination": str(dest_file),
            "destination_dir": str(dest_dir),
            "engine": target_engine
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to deploy mesh: {str(e)}"}
