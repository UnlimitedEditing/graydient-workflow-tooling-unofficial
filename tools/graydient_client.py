"""
Python SDK Client for Graydient.
Provides a clean Pythonic API over the Node-based `graydient` CLI:
- Windows CLI argument sanitization (handling metacharacters, slashes, newlines)
- Automatic resolution of `node` and `graydient-cli` paths
- Chat completions with Graydient LLM personas
- Synchronous and asynchronous render dispatching with progress streaming
- Skill invocations
"""

import subprocess
import json
import os
import re
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List

DEFAULT_PERSONA = "ProductionAssistantbot"

def sanitize_cli_arg(text: str) -> str:
    """
    Sanitize text arguments for the Graydient CLI on Windows.
    Flattens newlines to spaces, and replaces metacharacters (<, >, |, /) to prevent command parser errors.
    """
    if not text:
        return ""
    s = text.replace("\r\n", " ").replace("\n", " ")
    s = s.replace("<", "(").replace(">", ")").replace("|", ", ").replace("/", " - ")
    return s.strip()

class GraydientClient:
    def __init__(self, cli_bin: str = "graydient"):
        self.node_bin = shutil.which("node") or "node"
        global_cli_js = Path(os.environ.get("APPDATA", "")) / "npm" / "node_modules" / "graydient-cli" / "dist" / "index.js"
        if global_cli_js.exists():
            self.base_cmd = [self.node_bin, str(global_cli_js)]
        else:
            resolved = shutil.which(cli_bin) or cli_bin
            self.base_cmd = [resolved]

    def _run_cmd(self, args: List[str], timeout: int = 1200) -> Dict[str, Any]:
        """Execute a Graydient CLI command and return parsed output."""
        cmd = self.base_cmd + args
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=False,
            timeout=timeout
        )
        if proc.returncode != 0:
            err_msg = proc.stderr.strip() or proc.stdout.strip()
            raise RuntimeError(f"Graydient CLI error ({proc.returncode}): {err_msg}")

        out_str = proc.stdout.strip()
        try:
            return json.loads(out_str)
        except json.JSONDecodeError:
            return {"raw_text": out_str}

    def chat(self, persona: str, prompt: str) -> str:
        """Send a prompt to a Graydient persona and return text response."""
        clean_prompt = sanitize_cli_arg(prompt)
        res = self._run_cmd(["chat", clean_prompt, "--persona", persona, "--json"])
        return res.get("response", res.get("raw_text", ""))

    def render(
        self,
        prompt: str,
        workflow: Optional[str] = None,
        out_path: Optional[str] = None,
        init_image: Optional[str] = None,
        init_video: Optional[str] = None,
        init_audio: Optional[str] = None,
        timeout_minutes: int = 20
    ) -> Dict[str, Any]:
        """Submit a render and wait for completion."""
        args = ["render", prompt, "--timeout", str(timeout_minutes), "--json"]
        if workflow:
            args.extend(["--workflow", workflow])
        if out_path:
            args.extend(["--out", out_path])
        if init_image:
            args.extend(["--init-image", init_image])
        if init_video:
            args.extend(["--init-video", init_video])
        if init_audio:
            args.extend(["--init-audio", init_audio])
        return self._run_cmd(args, timeout=timeout_minutes * 60 + 60)

    def invoke_skill(self, skill_slug: str, prompt: str) -> Dict[str, Any]:
        """Invoke a Graydient skill."""
        return self._run_cmd(["skills", "invoke", skill_slug, prompt, "--json"])
