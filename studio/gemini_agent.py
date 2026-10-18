"""
Gemini Flash Agent Engine for Graydient Studio.
Drives autonomous workflow engineering, linting, diagnostics, concept staging, and render jobs
using Google's 1M-token Gemini 2.0 / 1.5 Flash API at zero cost.
"""

import os
import json
import traceback
from pathlib import Path
from typing import Optional, Generator, Any

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR

class GeminiStudioAgent:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.client = None
        self.system_instruction = self._build_system_instruction()
        self._init_client()

    def _init_client(self):
        if not self.api_key:
            return
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
        except Exception as e:
            print(f"Failed to initialize google.genai Client: {e}")
            self.client = None

    def update_api_key(self, api_key: str):
        self.api_key = api_key.strip()
        self._init_client()

    def _build_system_instruction(self) -> str:
        """Inject catalog rules, graveyard rules, and schema summary into the 1M context window."""
        docs = []
        docs.append("You are the autonomous Graydient Workflow Engineer embedded inside Graydient Studio.")
        docs.append("Your role is to author, lint, test, deploy, and diagnose ComfyUI cloud workflows on Graydient.ai.")
        docs.append("You have zero token cost constraints — use precise architectural reasoning and zero-defect checks.\n")

        # 1. Load Graveyard rules (KI-007)
        ki7_path = REPO_ROOT / "comfyui-graydient-okf-catalog" / "catalog" / "KI-007-runtime-constraints-and-graveyard.md"
        if ki7_path.exists():
            docs.append("=== KI-007: GRAYDIENT RUNTIME CONSTRAINTS & GRAVEYARD RULES ===")
            docs.append(ki7_path.read_text(encoding="utf-8")[:18000])

        # 2. Load Slot / Field Mapping rules (KI-003)
        ki3_path = REPO_ROOT / "comfyui-graydient-okf-catalog" / "catalog" / "KI-003-field-mapping-slots.md"
        if ki3_path.exists():
            docs.append("\n=== KI-003: FIELD MAPPING & SLOT INDEXING ===")
            docs.append(ki3_path.read_text(encoding="utf-8")[:8000])

        # 3. Load Concept Mapping rules (KI-008)
        ki8_path = REPO_ROOT / "comfyui-graydient-okf-catalog" / "catalog" / "KI-008-concept-mapping-registry.md"
        if ki8_path.exists():
            docs.append("\n=== KI-008: VERIFIED MODEL STAGING RECIPES ===")
            docs.append(ki8_path.read_text(encoding="utf-8")[:10000])

        # 4. Instructions on M3DS Steganography
        docs.append("""
=== M3DS STEGANOGRAPHY & 3D WORKFLOWS ===
Graydient collects images (SaveImage, PreviewImage) and videos (VHS_VideoCombine).
For 3D meshes (GLB, OBJ, PLY) and complex data (YuE2 scores), workflows use M3DS steganography
(via SmuggleMeshAsImage or similar custom nodes) to encode binary files into raw PNG pixels.
The Studio automatically detects M3DS payloads, recovers the embedded GLB/PLY/JSON file,
and directly renders it in the interactive 3D WebGL viewer!
""")
        return "\n\n".join(docs)

    def execute_tool(self, name: str, args: dict) -> dict:
        """Execute deterministic local tools on behalf of the agent."""
        try:
            if name == "lint_workflow":
                return self._tool_lint(args.get("code") or args.get("script_path"))
            elif name == "search_knowledge":
                return self._tool_search(args.get("query", ""))
            elif name == "diagnose_log":
                return self._tool_diagnose(args.get("log_text", ""))
            elif name == "list_templates":
                return self._tool_list_templates()
            elif name == "read_template":
                return self._tool_read_template(args.get("name", ""))
            elif name == "save_generator_script":
                return self._tool_save_script(args.get("filename", ""), args.get("code", ""))
            elif name == "decode_m3ds":
                from .m3ds_codec import unpack_and_save
                return unpack_and_save(args.get("image_path"))
            else:
                return {"error": f"Unknown tool: {name}"}
        except Exception as e:
            return {"error": str(e), "traceback": traceback.format_exc()}

    def _tool_lint(self, target: str) -> dict:
        """Run the Graydient zero-defect linter on code string or file path."""
        import tempfile
        import subprocess

        linter_py = REPO_ROOT / "graydient_builder" / "linter.py"
        if not target:
            return {"error": "No script code or path provided"}

        # If code was passed directly, write to temp file
        if "\n" in target or not os.path.exists(target):
            with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tmp:
                tmp.write(target)
                tmp_path = tmp.name
        else:
            tmp_path = target

        try:
            # First execute the gen script to emit workflow json
            proc = subprocess.run(["python", tmp_path], capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=15)
            # Find any emitted json in current dir
            json_candidates = list(REPO_ROOT.glob("GraydientWorkflow-*.json"))
            if not json_candidates:
                return {"output": proc.stdout, "stderr": proc.stderr, "status": "Script executed but no GraydientWorkflow-*.json found"}

            latest_json = max(json_candidates, key=os.path.getmtime)
            # Run linter
            from graydient_builder.linter import lint_workflow_file
            report = lint_workflow_file(str(latest_json))
            return {
                "json_file": str(latest_json),
                "is_valid": report.is_valid,
                "error_count": report.error_count,
                "warning_count": report.warning_count,
                "issues": [{"severity": i.severity.name, "rule": i.rule, "message": i.message} for i in report.issues]
            }
        except Exception as e:
            return {"error": str(e)}

    def _tool_search(self, query: str) -> dict:
        """Search node schemas, concept mappings, and graveyard."""
        q = query.lower()
        results = {"nodes": [], "concepts": [], "templates": []}

        # Node schema
        node_db = REPO_ROOT / "graydient_builder" / "node_schema_db.json"
        if node_db.exists():
            with open(node_db, "r", encoding="utf-8") as f:
                nodes = json.load(f)
            for k, v in nodes.items():
                if k.startswith("_"): continue
                if q in k.lower() or q in str(v).lower():
                    results["nodes"].append({"node_type": k, "inputs": list(v.get("inputs", {}).keys()), "note": v.get("note")})
                    if len(results["nodes"]) >= 5: break

        # Concept DB
        concept_db = REPO_ROOT / "graydient_builder" / "concept_db.json"
        if concept_db.exists():
            with open(concept_db, "r", encoding="utf-8") as f:
                concepts = json.load(f)
            for k, v in concepts.items():
                if k.startswith("_"): continue
                if q in k.lower() or q in str(v).lower():
                    results["concepts"].append({"id": k, "data": v})
                    if len(results["concepts"]) >= 5: break

        # Templates
        tpl_dir = REPO_ROOT / "templates"
        if tpl_dir.exists():
            for f in tpl_dir.glob("gen_*.py"):
                if q in f.name.lower():
                    results["templates"].append(f.name)

        return results

    def _tool_diagnose(self, log_text: str) -> dict:
        """Check failed container log against Graveyard rules."""
        from tools.diagnose_log import diagnose_content
        return diagnose_content(log_text)

    def _tool_list_templates(self) -> dict:
        tpl_dir = REPO_ROOT / "templates"
        files = [f.name for f in tpl_dir.glob("gen_*.py")] if tpl_dir.exists() else []
        return {"templates": files}

    def _tool_read_template(self, name: str) -> dict:
        tpl_path = REPO_ROOT / "templates" / name
        if not tpl_path.exists():
            return {"error": f"Template not found: {name}"}
        return {"name": name, "content": tpl_path.read_text(encoding="utf-8")}

    def _tool_save_script(self, filename: str, code: str) -> dict:
        clean_name = os.path.basename(filename)
        if not clean_name.endswith(".py"):
            clean_name += ".py"
        target_path = REPO_ROOT / "templates" / clean_name
        target_path.write_text(code, encoding="utf-8")
        return {"status": "saved", "path": str(target_path)}

    def chat(self, user_message: str, history: list = None) -> Generator[dict, None, None]:
        """
        Chat with Gemini 2.0 Flash in streaming / agent loop.
        Yields status updates and assistant output chunks.
        """
        if not self.client:
            yield {
                "type": "error",
                "message": "Gemini API Key is not set. Please enter your free Google AI Studio API key in Settings."
            }
            return

        try:
            # We call Gemini 2.0 Flash (or 1.5 Flash as fallback)
            model_name = "gemini-2.0-flash"

            prompt = f"{self.system_instruction}\n\nUser Request: {user_message}"
            yield {"type": "status", "message": "Reasoning with Gemini Flash 1M context..."}

            # Generate content
            response = self.client.models.generate_content(
                model=model_name,
                contents=user_message,
                config={
                    "system_instruction": self.system_instruction,
                    "temperature": 0.2,
                }
            )

            response_text = response.text if response and response.text else "No response generated."
            yield {"type": "content", "text": response_text}

        except Exception as e:
            yield {
                "type": "error",
                "message": f"Gemini API error: {str(e)}",
                "traceback": traceback.format_exc()
            }
