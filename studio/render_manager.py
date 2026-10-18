"""
Render Manager & Persistent Local Library for Graydient Studio.
Dispatches renders via the Graydient CLI, monitors streaming output,
and automatically extracts M3DS 3D payloads upon download.
"""

import os
import json
import time
import subprocess
import threading
from pathlib import Path
from typing import Optional, List, Dict
from .m3ds_codec import unpack_and_save

BASE_DIR = Path(__file__).resolve().parent.parent
RENDERS_DIR = BASE_DIR / "renders"
LIBRARY_FILE = RENDERS_DIR / "library.json"

class RenderManager:
    def __init__(self):
        os.makedirs(RENDERS_DIR, exist_ok=True)
        self.jobs: Dict[str, dict] = {}
        self.lock = threading.Lock()
        self._load_library()

    def _load_library(self):
        if LIBRARY_FILE.exists():
            try:
                with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
                    self.jobs = json.load(f)
            except Exception as e:
                print(f"Error loading render library: {e}")
                self.jobs = {}
        else:
            self.jobs = {}

    def _save_library(self):
        with self.lock:
            try:
                with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
                    json.dump(self.jobs, f, indent=2)
            except Exception as e:
                print(f"Error saving render library: {e}")

    def get_all_renders(self) -> List[dict]:
        with self.lock:
            return sorted(list(self.jobs.values()), key=lambda x: x.get("created_at", 0), reverse=True)

    def get_render(self, job_id: str) -> Optional[dict]:
        with self.lock:
            return self.jobs.get(job_id)

    def submit_render(
        self,
        workflow_slug: str,
        prompt: str,
        slot1: Optional[str] = None,
        slot2: Optional[str] = None,
        slot3: Optional[str] = None,
        slot4: Optional[str] = None,
        init_image: Optional[str] = None,
        init_audio: Optional[str] = None
    ) -> dict:
        job_id = f"job_{int(time.time() * 1000)}"
        job_dir = RENDERS_DIR / job_id
        os.makedirs(job_dir, exist_ok=True)

        job_entry = {
            "id": job_id,
            "workflow": workflow_slug,
            "prompt": prompt,
            "slots": {"slot1": slot1, "slot2": slot2, "slot3": slot3, "slot4": slot4},
            "status": "QUEUED",
            "created_at": time.time(),
            "output_files": [],
            "m3ds_assets": [],
            "error": None,
            "job_dir": str(job_dir)
        }

        with self.lock:
            self.jobs[job_id] = job_entry
        self._save_library()

        # Start execution thread
        t = threading.Thread(target=self._execute_render_job, args=(job_id, workflow_slug, prompt, slot1, slot2, slot3, slot4, init_image, init_audio, job_dir))
        t.daemon = True
        t.start()

        return job_entry

    def _execute_render_job(self, job_id, workflow, prompt, s1, s2, s3, s4, img, audio, job_dir):
        with self.lock:
            self.jobs[job_id]["status"] = "RUNNING"
        self._save_library()

        # Build CLI command
        # Uses npx or node cli/dist/index.js render
        cmd = ["graydient", "render", workflow, prompt, "--output", str(job_dir), "--timeout", "45"]
        if s1: cmd.extend(["--slot1", str(s1)])
        if s2: cmd.extend(["--slot2", str(s2)])
        if s3: cmd.extend(["--slot3", str(s3)])
        if s4: cmd.extend(["--slot4", str(s4)])
        if img: cmd.extend(["--init-image", str(img)])
        if audio: cmd.extend(["--init-audio", str(audio)])

        try:
            # Execute render
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE_DIR), timeout=300)
            output_files = []
            m3ds_assets = []

            # Check outputs in job_dir
            for f in job_dir.glob("*.*"):
                if f.is_file():
                    output_files.append(str(f))
                    # Auto-check for M3DS container
                    if f.suffix.lower() == ".png":
                        try:
                            unpack_res = unpack_and_save(f, job_dir)
                            if unpack_res.get("is_m3ds"):
                                m3ds_assets.append(unpack_res)
                        except Exception as e:
                            print(f"Error checking M3DS on {f}: {e}")

            with self.lock:
                if proc.returncode == 0:
                    self.jobs[job_id]["status"] = "SUCCESS"
                else:
                    self.jobs[job_id]["status"] = "FAILED"
                    self.jobs[job_id]["error"] = proc.stderr or proc.stdout
                self.jobs[job_id]["output_files"] = output_files
                self.jobs[job_id]["m3ds_assets"] = m3ds_assets
            self._save_library()

        except Exception as e:
            with self.lock:
                self.jobs[job_id]["status"] = "FAILED"
                self.jobs[job_id]["error"] = str(e)
            self._save_library()

    def add_existing_render(self, file_path: str) -> dict:
        """Import an existing file into the local library, auto-extracting M3DS."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        job_id = f"import_{int(time.time() * 1000)}"
        job_dir = RENDERS_DIR / job_id
        os.makedirs(job_dir, exist_ok=True)

        # Copy original file
        import shutil
        dest = job_dir / path.name
        shutil.copy2(path, dest)

        m3ds_assets = []
        if dest.suffix.lower() == ".png":
            try:
                res = unpack_and_save(dest, job_dir)
                if res.get("is_m3ds"):
                    m3ds_assets.append(res)
            except Exception as e:
                print(f"M3DS unpack error on import: {e}")

        job_entry = {
            "id": job_id,
            "workflow": "imported",
            "prompt": path.stem,
            "slots": {},
            "status": "SUCCESS",
            "created_at": time.time(),
            "output_files": [str(dest)],
            "m3ds_assets": m3ds_assets,
            "error": None,
            "job_dir": str(job_dir)
        }

        with self.lock:
            self.jobs[job_id] = job_entry
        self._save_library()
        return job_entry
