"""
Autonomous Coding Agent Engine for PirateUI.
Equips Google Gemini 3.8 Flash (1M Context) with native workspace tools:
- File reading, writing, and targeted editing
- Zero-defect ComfyUI workflow linting (25+ checks)
- Shell command execution (graydient CLI, git, python)
- OKF catalog & Graveyard constraint search
- Log diagnostics & M3DS steganography decoding
"""

import os
import json
import subprocess
import traceback
from pathlib import Path
from typing import Optional, Generator, List, Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR

def diagnose_log_text(log_text: str) -> dict:
    import re
    from wf import DIAGNOSTIC_RULES
    matches = []
    for rule in DIAGNOSTIC_RULES:
        m = re.search(rule["pattern"], log_text, re.IGNORECASE)
        if m:
            matches.append({
                "issue": rule["issue"],
                "catalog_rule": rule["ki"],
                "recommendation": rule["advice"],
                "matched_snippet": m.group(0)
            })
    if matches:
        return {
            "summary": f"Detected {len(matches)} container failure pattern(s)",
            "root_cause": matches[0]["issue"],
            "recommendation": matches[0]["recommendation"],
            "matches": matches
        }
    return {
        "summary": "No known failure pattern match in KI-007 Graveyard rules",
        "root_cause": "Unrecognized error or generic exception",
        "recommendation": "Review container stdout/stderr, verify requirements.pip, and test custom node dependencies.",
        "matches": []
    }

class GeminiStudioAgent:
    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            for kf in [BASE_DIR / ".gemini_key", BASE_DIR.parent / ".gemini_key", Path.home() / ".gemini_key"]:
                if kf.exists():
                    try:
                        key = kf.read_text(encoding="utf-8").strip()
                        if key: break
                    except Exception:
                        pass
        self.api_key = key
        self.client = None
        self.chat_session = None
        self.system_instruction = self._build_system_instruction()
        self._init_client()

    def _init_client(self):
        if not self.api_key:
            return
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            self._init_chat_session()
        except Exception as e:
            print(f"Failed to initialize google.genai Client: {e}")
            self.client = None

    def update_api_key(self, api_key: str):
        self.api_key = api_key.strip()
        self._init_client()

    def _build_system_instruction(self) -> str:
        docs = []
        docs.append("You are the autonomous Lead Workflow Engineer & Full Coding Agent embedded inside PirateUI.")
        docs.append("You have FULL autonomous capability to read code, write generator scripts, execute terminal commands,")
        docs.append("run zero-defect linting, search schemas, and interact with the Graydient cloud platform.\n")

        # 1. Load Graveyard rules (KI-007)
        ki7_path = REPO_ROOT / "comfyui-graydient-okf-catalog" / "catalog" / "KI-007-runtime-constraints-and-graveyard.md"
        if not ki7_path.exists():
            ki7_path = REPO_ROOT.parent / "comfyui-graydient-okf-catalog" / "catalog" / "KI-007-runtime-constraints-and-graveyard.md"
        if ki7_path.exists():
            docs.append("=== KI-007: GRAYDIENT RUNTIME CONSTRAINTS & GRAVEYARD RULES ===")
            docs.append(ki7_path.read_text(encoding="utf-8")[:18000])

        # 2. Load Slot / Field Mapping rules (KI-003)
        ki3_path = REPO_ROOT / "comfyui-graydient-okf-catalog" / "catalog" / "KI-003-field-mapping-slots.md"
        if not ki3_path.exists():
            ki3_path = REPO_ROOT.parent / "comfyui-graydient-okf-catalog" / "catalog" / "KI-003-field-mapping-slots.md"
        if ki3_path.exists():
            docs.append("\n=== KI-003: FIELD MAPPING & SLOT INDEXING ===")
            docs.append(ki3_path.read_text(encoding="utf-8")[:8000])

        # 3. Load Concept Mapping rules (KI-008)
        ki8_path = REPO_ROOT / "comfyui-graydient-okf-catalog" / "catalog" / "KI-008-concept-mapping-registry.md"
        if not ki8_path.exists():
            ki8_path = REPO_ROOT.parent / "comfyui-graydient-okf-catalog" / "catalog" / "KI-008-concept-mapping-registry.md"
        if ki8_path.exists():
            docs.append("\n=== KI-008: VERIFIED MODEL STAGING RECIPES ===")
            docs.append(ki8_path.read_text(encoding="utf-8")[:10000])

        docs.append("""
=== WORKFLOW CODING STANDARDS ===
1. Use `graydient_builder` (core.py, blocks.py) or canonical scripts in `templates/` as starting points.
2. ALWAYS run `lint_workflow_script` after generating or modifying any `gen_*.py` script.
3. If the linter reports any error, self-heal the code immediately before reporting completion.
4. M3DS Steganography: When generating 3D meshes (GLB, PLY), use SmuggleMeshAsImage or M3DS nodes so Graydient can collect the PNG and PirateUI can auto-render the 3D model.

=== GAME DEV AGENT & ENGINE BRIDGES (VAIL & GODOT MCP) ===
You are also the autonomous Game Development Lead Agent inside PirateUI.
You control TWO primary game engine interfaces:
1. Unreal Engine 5.8 via VAIL (Virtual Agent Interface Layer):
   - Direct TCP socket (127.0.0.1:55557) communicating with the VAIL plugin in Unreal Engine 5.8.
   - Use `vail_execute_command(command, params_json)` to inspect actor trees (`vail_get_tree`), spawn actors (`vail_level_spawn_actor`), mutate properties (`vail_set_property`), connect Blueprint graph pins, and trigger live coding compiles (`vail_trigger_live_coding`).
   - If Unreal is offline, explain that the user can launch their Unreal project (e.g. `D:\\UE5.8\\vailtest`).
2. Godot Engine 4.x via Godot MCP:
   - Interfaces directly with Godot 4.6.1 Mono (`D:\\Godot_v4.6.1-stable_mono_win64`) and the Godot MCP ToolRegistry (`D:\\godot-mcp`).
   - Use `godot_mcp_execute(tool_name, params_json)` to launch editor (`launch_editor`), run/stop projects (`run_project`, `stop_project`), create scenes (`create_scene`), add/edit nodes (`add_node`, `edit_node`), and capture live debug output (`get_debug_output`).
3. 3D Game Asset Staging:
   - Use `deploy_3d_asset_to_game(mesh_name, target_engine)` to ship generated `.glb` or `.ply` meshes directly into Godot (`res://assets`) or Unreal Content directories.
4. Game Scripting:
   - Author clean, typed GDScript 2.0 or C# for Godot.
   - Author Blueprint construction or C++ logic for Unreal Engine.
""")
        return "\n\n".join(docs)

    def _init_chat_session(self):
        if not self.client:
            return
        from google.genai import types

        # Define workspace tool functions for the agent
        def read_workspace_file(filepath: str) -> str:
            """Reads the contents of any file in the workspace or repository."""
            target = Path(filepath)
            if not target.is_absolute():
                candidates = [BASE_DIR / filepath, BASE_DIR.parent / filepath]
                target = next((c for c in candidates if c.exists()), BASE_DIR / filepath)
            if not target.exists():
                return f"Error: File not found: {filepath}"
            try:
                return target.read_text(encoding="utf-8", errors="replace")[:25000]
            except Exception as e:
                return f"Error reading file: {e}"

        def write_workspace_file(filepath: str, content: str) -> str:
            """Creates or completely overwrites a file in the workspace."""
            target = Path(filepath)
            if not target.is_absolute():
                target = BASE_DIR / filepath
            try:
                os.makedirs(target.parent, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                return f"Successfully wrote {len(content)} characters to {target.name}"
            except Exception as e:
                return f"Error writing file: {e}"

        def run_terminal_command(command: str) -> str:
            """Executes a shell command (CLI, git, python) in the workspace directory."""
            try:
                proc = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=str(BASE_DIR),
                    timeout=60
                )
                stdout = proc.stdout or ""
                stderr = proc.stderr or ""
                return f"Exit code: {proc.returncode}\nSTDOUT:\n{stdout[:8000]}\nSTDERR:\n{stderr[:4000]}"
            except subprocess.TimeoutExpired:
                return "Error: Command timed out after 60 seconds."
            except Exception as e:
                return f"Command execution error: {e}"

        def lint_workflow_script(script_path_or_json: str) -> str:
            """Executes the Graydient zero-defect linter with 25+ automated architectural checks."""
            try:
                cmd = ["python", str(BASE_DIR / "wf.py"), "lint", script_path_or_json]
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=str(BASE_DIR),
                    timeout=30
                )
                out = (proc.stdout or "") + "\n" + (proc.stderr or "")
                return out.strip()
            except Exception as e:
                return f"Linter error: {e}"

        def search_knowledge_catalog(query: str) -> str:
            """Searches ComfyUI node schemas, concept DB staging URLs, and Graveyard anti-pattern rules."""
            q = query.lower()
            results = []

            # 1. Check Node Schema DB
            node_db = BASE_DIR / "graydient_builder" / "node_schema_db.json"
            if not node_db.exists(): node_db = BASE_DIR.parent / "graydient_builder" / "node_schema_db.json"
            if node_db.exists():
                try:
                    with open(node_db, "r", encoding="utf-8") as f:
                        nodes = json.load(f)
                    for k, v in nodes.items():
                        if k.startswith("_"): continue
                        if q in k.lower() or q in str(v).lower():
                            results.append(f"Node '{k}': inputs={list(v.get('inputs', {}).keys())}, note={v.get('note')}")
                            if len(results) >= 6: break
                except Exception:
                    pass

            # 2. Check Graveyard rules
            ki7 = BASE_DIR / "comfyui-graydient-okf-catalog" / "catalog" / "KI-007-runtime-constraints-and-graveyard.md"
            if not ki7.exists(): ki7 = BASE_DIR.parent / "comfyui-graydient-okf-catalog" / "catalog" / "KI-007-runtime-constraints-and-graveyard.md"
            if ki7.exists():
                text = ki7.read_text(encoding="utf-8", errors="replace")
                for line in text.split("\n"):
                    if line.startswith("## ") and q in line.lower():
                        results.append(f"Graveyard Rule: {line}")

            return "\n".join(results) if results else f"No direct catalog matches found for '{query}'."

        def diagnose_failure_log(log_text: str) -> str:
            """Analyzes container failure logs against KI-007 Graveyard rules to provide the root cause and fix."""
            diag = diagnose_log_text(log_text)
            return json.dumps(diag, indent=2)

        def decode_m3ds_steganography(image_path: str) -> str:
            """Unpacks embedded 3D models (GLB, PLY) or scores from a Graydient M3DS carrier PNG."""
            from .m3ds_codec import unpack_and_save
            res = unpack_and_save(image_path)
            return json.dumps(res, indent=2)

        def vail_execute_command(command: str, params_json: str = "{}") -> str:
            """Sends a command to Unreal Engine 5.8 VAIL plugin (TCP 55557), e.g. vail_get_tree, vail_trigger_live_coding, vail_level_spawn_actor."""
            from .game_dev_bridge import send_vail_command
            try:
                p = json.loads(params_json) if params_json.strip() else {}
            except Exception:
                p = {}
            res = send_vail_command(command, p)
            return json.dumps(res, indent=2)

        def godot_mcp_execute(tool_name: str, params_json: str = "{}") -> str:
            """Executes any tool from the Godot MCP ToolRegistry (launch_editor, run_project, create_scene, add_node, list_projects, get_debug_output)."""
            from .game_dev_bridge import send_godot_tool
            try:
                p = json.loads(params_json) if params_json.strip() else {}
            except Exception:
                p = {}
            res = send_godot_tool(tool_name, p)
            return json.dumps(res, indent=2)

        def game_dev_probe() -> str:
            """Probes the live status of Unreal Engine 5.8 (VAIL on port 55557) and Godot Engine / Godot MCP."""
            from .game_dev_bridge import check_vail_connection, check_godot_status
            vail = check_vail_connection()
            godot = check_godot_status()
            return json.dumps({"unreal_vail": vail, "godot_mcp": godot}, indent=2)

        def deploy_3d_asset_to_game(mesh_name_or_path: str, target_engine: str = "godot", custom_project_dir: str = "") -> str:
            """Deploys a generated 3D model (.glb/.ply) into a Godot or Unreal Engine project folder."""
            from .game_dev_bridge import deploy_mesh_to_game
            res = deploy_mesh_to_game(mesh_name_or_path, target_engine, custom_project_dir or None)
            return json.dumps(res, indent=2)

        # Store tool functions
        self.tools = [
            read_workspace_file,
            write_workspace_file,
            run_terminal_command,
            lint_workflow_script,
            search_knowledge_catalog,
            diagnose_failure_log,
            decode_m3ds_steganography,
            vail_execute_command,
            godot_mcp_execute,
            game_dev_probe,
            deploy_3d_asset_to_game
        ]

        # Initialize multi-turn chat session with automatic tool calling enabled
        self.active_model = "gemini-3.7-flash"
        self.chat_session = self.client.chats.create(
            model=self.active_model,
            config=types.GenerateContentConfig(
                system_instruction=self.system_instruction,
                tools=self.tools,
                temperature=0.2,
            )
        )

    def chat(self, user_message: str, history: list = None) -> Generator[dict, None, None]:
        """
        Chat with Gemini Flash in an autonomous coding and game dev agent loop.
        Automatically executes tools, reads/writes code, and lints workflows.
        """
        if not self.client or not self.chat_session:
            self._init_client()

        if not self.client or not self.chat_session:
            yield {
                "type": "error",
                "message": "Gemini API Key is not set or invalid. Please configure your key in PirateUI Settings."
            }
            return

        models_to_try = [self.active_model] + [m for m in ["gemini-3.7-flash", "gemini-3.5-flash", "gemini-3.8-flash"] if m != self.active_model]
        last_err = None

        for model_name in models_to_try:
            try:
                if model_name != self.active_model:
                    from google.genai import types
                    self.active_model = model_name
                    self.chat_session = self.client.chats.create(
                        model=self.active_model,
                        config=types.GenerateContentConfig(
                            system_instruction=self.system_instruction,
                            tools=self.tools,
                            temperature=0.2,
                        )
                    )

                yield {"type": "status", "message": f"Reasoning & coordinating tools with Gemini ({self.active_model})..."}
                response = self.chat_session.send_message(user_message)
                response_text = response.text if response and response.text else "Operation complete."
                yield {"type": "content", "text": response_text}
                return

            except Exception as e:
                last_err = e
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "404" in err_str:
                    continue  # Failover to next model
                else:
                    break

        yield {
            "type": "error",
            "message": f"Gemini Agent error: {str(last_err)}",
            "traceback": traceback.format_exc()
        }

    def _tool_lint(self, target: str) -> dict:
        """Runs the zero-defect linter for the UI /api/agent/lint endpoint."""
        import sys, tempfile
        from graydient_builder.linter import GraydientLinter, format_lint_report
        # 1. Direct JSON string check
        try:
            trimmed = target.strip()
            if (trimmed.startswith("{") and trimmed.endswith("}")):
                data = json.loads(trimmed)
                linter = GraydientLinter()
                issues = linter.lint(data)
                has_errors = any(i.level == "ERROR" for i in issues)
                return {
                    "is_valid": not has_errors,
                    "error_count": sum(1 for i in issues if i.level == "ERROR"),
                    "issues": [{"rule": i.code, "message": i.message, "level": i.level} for i in issues],
                    "raw_report": format_lint_report(issues)
                }
        except Exception:
            pass

        # 2. File path check
        p = Path(target)
        if p.exists():
            cmd = ["python", str(BASE_DIR / "wf.py"), "lint", str(p)]
            proc = subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
            out = (proc.stdout or "") + "\n" + (proc.stderr or "")
            return {
                "is_valid": proc.returncode == 0,
                "error_count": 0 if proc.returncode == 0 else 1,
                "issues": [] if proc.returncode == 0 else [{"rule": "LINT_FAIL", "message": out.strip()[:1000], "level": "ERROR"}],
                "raw_report": out.strip()
            }

        # 3. Raw python code string in editor
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(target)
            tmp_py = f.name
        try:
            proc = subprocess.run([sys.executable, tmp_py], cwd=str(BASE_DIR), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
            out = (proc.stdout or "") + "\n" + (proc.stderr or "")
            return {
                "is_valid": proc.returncode == 0,
                "error_count": 0 if proc.returncode == 0 else 1,
                "issues": [] if proc.returncode == 0 else [{"rule": "EXEC_FAIL", "message": out.strip()[:1000], "level": "ERROR"}],
                "raw_report": out.strip()
            }
        finally:
            try: os.unlink(tmp_py)
            except Exception: pass

    def _tool_diagnose(self, log_text: str) -> dict:
        """Analyzes log text using Graveyard rules."""
        return diagnose_log_text(log_text)
