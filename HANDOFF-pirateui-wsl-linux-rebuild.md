# Handoff: PirateUI WSL2 & Linux Environment Parity & Rebuild Playbook

**Date**: 2026-10-18  
**Subject**: Guide to Rebuilding, Porting, and Validating PirateUI in Linux & Windows Subsystem for Linux (WSL2)  
**Status**: Ready for Implementation & Testing  
**Primary Files Affected**: `studio/game_dev_bridge.py`, `studio/godot_mcp_runner.js`, `studio/server.py`, `studio.py`, `requirements.txt`

---

## 1. Context & Motivation

PirateUI was initially bootstrapped on Windows 11 (`D:\tripostl`) with:
- Windows Python 3.14 (`python studio.py --port 8765`)
- Node.js ESM with Windows drive URLs (`file:///D:/godot-mcp/...`)
- Godot Engine Windows console binary (`Godot_v4.6.1-stable_mono_win64_console.exe`)
- Unreal Engine 5.8 running on the Windows host (`D:\UE5.8\vailtest`) communicating over TCP `127.0.0.1:55557`

Running PirateUI directly inside **Linux / WSL2 (Ubuntu 22.04 or 24.04 LTS)** provides crucial advantages:
1. **Production & Graydient Container Parity**: Headless ComfyUI instances, PyTorch CUDA extensions (xFormers, flash-attn), and containerized pipelines run natively on Linux; developing within Linux eliminates cross-OS path and wheel discrepancies.
2. **Filesystem Performance**: Running on native ext4 (`~/tripostl`) eliminates the 9P filesystem translation latency observed when Linux accesses `/mnt/d/`, boosting Python startup, hot reloading, and 3D mesh I/O by up to 10x–50x.
3. **Python 3.11/3.12 Wheel Stability**: ComfyUI and many scientific AI wheels have precompiled Linux CUDA binaries that are currently unavailable for Windows Python 3.14.

---

## 2. Core Differences & Architectural Challenges in WSL2

### 2.1. Filesystem Location (`/mnt/d/` vs Native `~/`)
- **Pitfall**: Running `git clone` or workspace operations directly inside `/mnt/d/tripostl` causes Windows-to-Linux permission translation overhead, file watching failures, and slow disk I/O.
- **Directive**: Always clone or rsync the project to the native Linux filesystem:
  ```bash
  # Inside WSL2:
  mkdir -p ~/projects
  cd ~/projects
  git clone https://github.com/UnlimitedEditing/graydient-workflow-tooling-unofficial.git tripostl
  # Or rsync from Windows drive if iterating locally:
  rsync -av --exclude='.venv' --exclude='__pycache__' --exclude='node_modules' /mnt/d/tripostl/ ~/tripostl/
  ```

---

### 2.2. Cross-Boundary Networking (WSL2 $\leftrightarrow$ Windows Host UE5 VAIL)

Unreal Engine 5.8 runs on the Windows host with GPU display, listening on `127.0.0.1:55557`. When PirateUI runs inside WSL2, connecting to `127.0.0.1` connects to the *WSL virtual machine*, NOT the Windows host.

There are two solutions:

#### Solution A: WSL Mirrored Networking (Recommended for Windows 11 23H2+)
In `%USERPROFILE%\.wslconfig` on Windows:
```ini
[wsl2]
networkingMode=mirrored
localhostForwarding=true
```
With mirrored networking, `127.0.0.1:55557` inside WSL connects directly to `127.0.0.1:55557` on Windows. Zero code changes required!

#### Solution B: Dynamic Host Gateway Resolution (Fallback for NAT mode)
In standard WSL2 NAT mode, the Windows host IP is the default gateway in `/etc/resolv.conf`. Update `studio/game_dev_bridge.py`:
```python
def resolve_host_ip(preferred_host: str = "127.0.0.1") -> str:
    """Detects whether running in WSL2 NAT mode and resolves Windows host IP."""
    if preferred_host not in ["127.0.0.1", "localhost"]:
        return preferred_host
    
    # Check if inside WSL
    if os.path.exists("/proc/sys/fs/binfmt_misc/WSLInterop"):
        # Test if localhost works (mirrored mode)
        try:
            with socket.create_connection(("127.0.0.1", VAIL_PORT), timeout=0.2):
                return "127.0.0.1"
        except Exception:
            pass
        # Fallback to default gateway in /etc/resolv.conf
        try:
            with open("/etc/resolv.conf", "r") as f:
                for line in f:
                    if line.startswith("nameserver"):
                        return line.split()[1]
        except Exception:
            pass
    return preferred_host
```

---

### 2.3. Node.js ESM Loader & Dynamic Import Paths

In `studio/godot_mcp_runner.js`, Windows paths require `pathToFileURL` conversion because `import("D:\\...")` fails in Node ESM. On Linux, standard POSIX paths or `pathToFileURL` work cleanly, but Windows drive letter heuristics must not be invoked on Linux.

**Linux-Safe Implementation (`studio/godot_mcp_runner.js`)**:
```javascript
import { pathToFileURL } from 'url';
import path from 'path';

function getModuleUrl(targetPath) {
    if (process.platform === 'win32') {
        const normalized = targetPath.replace(/^[A-Za-z]:/, match => match.toUpperCase());
        return pathToFileURL(normalized).href;
    }
    return pathToFileURL(path.resolve(targetPath)).href;
}
```

---

### 2.4. Godot Engine 4.6.1 on Linux

On Windows: `D:\Godot_v4.6.1-stable_mono_win64\Godot_v4.6.1-stable_mono_win64_console.exe`.  
On Linux:
1. Download Linux binary:
   ```bash
   wget https://github.com/godotengine/godot/releases/download/4.6.1-stable/Godot_v4.6.1-stable_linux.x86_64.zip
   unzip Godot_v4.6.1-stable_linux.x86_64.zip
   sudo mv Godot_v4.6.1-stable_linux.x86_64 /usr/local/bin/godot
   chmod +x /usr/local/bin/godot
   ```
2. In Linux, Godot commands executed headless (without an X11 server) must pass `--headless`.
3. Update `studio/game_dev_bridge.py`:
   ```python
   def get_default_godot_exe() -> Path:
       if sys.platform == "win32":
           return Path(r"D:\Godot_v4.6.1-stable_mono_win64\Godot_v4.6.1-stable_mono_win64_console.exe")
       else:
           # Check PATH or local standard install
           which_godot = shutil.which("godot")
           if which_godot:
               return Path(which_godot)
           return Path("/usr/local/bin/godot")
   ```

---

## 3. Step-by-Step Linux / WSL Provisioning Playbook

Execute the following commands inside Ubuntu on WSL2:

### Step 1: Install System Dependencies
```bash
sudo apt update && sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    nodejs \
    npm \
    git \
    curl \
    unzip \
    libgl1 \
    libglib2.0-0 \
    libegl1
```

### Step 2: Set Up Python 3.11/3.12 Virtual Environment
```bash
cd ~/tripostl
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install fastapi uvicorn pydantic google-genai pillow aiofiles requests trimesh numpy
```

### Step 3: Configure Godot MCP under Linux
```bash
# Clone or link godot-mcp
cd ~
git clone https://github.com/Coding-with-Adam/godot-mcp.git
cd godot-mcp
npm install
npm run build
```

### Step 4: Configure API Key & Environment
Ensure your `.gemini_key` is present in the workspace root:
```bash
echo "AQ..." > ~/tripostl/.gemini_key
chmod 600 ~/tripostl/.gemini_key
```

### Step 5: Launch PirateUI Studio Daemon
```bash
cd ~/tripostl
source .venv/bin/activate
python3 studio.py --port 8765 --no-browser
```

PirateUI will bind to `0.0.0.0:8765` or `127.0.0.1:8765`. On Windows host, open your browser and navigate to:
```
http://127.0.0.1:8765/
```
WSL2 automatically forwards port 8765 to the Windows localhost interface.

---

## 4. End-to-End Linux Verification Checklist

Run these test cases to verify complete functional parity:

| Test ID | Subsystem | Action | Expected Output | Status |
|---|---|---|---|---|
| **LNX-01** | **Server Core** | `curl -s http://127.0.0.1:8765/api/status` | `{"status":"online","port":8765,"gemini_configured":true}` | Pending |
| **LNX-02** | **Gemini Flash** | Run test query to `/api/agent/chat` | Valid JSON response with streaming tokens; no 400/404 errors | Pending |
| **LNX-03** | **Godot MCP** | `GET /api/gamedev/godot/status` | Returns version `4.6.1-stable` and 16 registered tools | Pending |
| **LNX-04** | **Unreal VAIL** | `GET /api/gamedev/vail/status` | If UE5 open on host: connects via mirrored network or host gateway | Pending |
| **LNX-05** | **M3DS Stego** | Decode test PNG via `/api/m3ds/decode` | Returns extracted 3D mesh (`.glb` / `.ply`) in `renders/decoded/` | Pending |
| **LNX-06** | **Asset Deploy**| `POST /api/gamedev/asset/deploy` | Copies `.glb` into Linux project target or symlinked Windows dir | Pending |

---

## 5. Summary of Recommended Code Hardening for Linux Parity

1. **`studio/game_dev_bridge.py`**:
   - Make `GODOT_EXE`, `GODOT_MCP_DIR`, and `VAIL_HOST` platform-agnostic using `os.getenv()` and dynamic fallback detection.
2. **`studio/godot_mcp_runner.js`**:
   - Replace hardcoded Windows `D:\\` paths with `process.env.GODOT_MCP_DIR || path.resolve(process.env.HOME, 'godot-mcp')`.
3. **`studio.py`**:
   - Check `sys.platform == "linux"` and gracefully handle browser launch attempts in headless/WSL environments without throwing `xdg-open` warnings.
