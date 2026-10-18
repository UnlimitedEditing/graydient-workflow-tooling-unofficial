"""
Graydient Studio Application Server.
FastAPI backend powering the Desktop Studio with zero-cost Gemini Flash intelligence,
native M3DS 3D unpacking, live linting, and render management.
"""

import os
import json
import subprocess
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict

from .gemini_agent import GeminiStudioAgent
from .render_manager import RenderManager
from .m3ds_codec import unpack_and_save, is_m3ds_image

BASE_DIR = Path(__file__).resolve().parent.parent
STUDIO_DIR = Path(__file__).resolve().parent
STATIC_DIR = STUDIO_DIR / "static"
RENDERS_DIR = BASE_DIR / "renders"

app = FastAPI(title="Graydient Studio", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize engines
agent = GeminiStudioAgent()
render_mgr = RenderManager()

# Ensure directories exist
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(RENDERS_DIR, exist_ok=True)

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[dict]] = None

class KeyRequest(BaseModel):
    api_key: str

class LintRequest(BaseModel):
    code: Optional[str] = None
    script_path: Optional[str] = None

class DiagnoseRequest(BaseModel):
    log_text: str

class RenderSubmitRequest(BaseModel):
    workflow_slug: str
    prompt: str
    slot1: Optional[str] = None
    slot2: Optional[str] = None
    slot3: Optional[str] = None
    slot4: Optional[str] = None
    init_image: Optional[str] = None
    init_audio: Optional[str] = None

class SyncRequest(BaseModel):
    commit_message: Optional[str] = "Update via Graydient Studio"
    push: Optional[bool] = False

# ── API Endpoints ──────────────────────────────────────────────────────────

@app.get("/api/status")
def get_status():
    ki7_path = BASE_DIR / "comfyui-graydient-okf-catalog" / "catalog" / "KI-007-runtime-constraints-and-graveyard.md"
    graveyard_count = 34
    if ki7_path.exists():
        text = ki7_path.read_text(encoding="utf-8")
        graveyard_count = text.count("## ")

    return {
        "status": "online",
        "has_gemini_key": bool(agent.api_key),
        "total_renders": len(render_mgr.jobs),
        "graveyard_rules": graveyard_count,
        "repo_dir": str(BASE_DIR)
    }

@app.post("/api/settings/key")
def set_api_key(req: KeyRequest):
    agent.update_api_key(req.api_key)
    # Also save to local config file
    cfg_file = BASE_DIR / ".gemini_key"
    try:
        cfg_file.write_text(req.api_key.strip(), encoding="utf-8")
    except Exception:
        pass
    return {"status": "saved", "has_key": bool(agent.api_key)}

@app.post("/api/agent/chat")
def chat_agent(req: ChatRequest):
    chunks = list(agent.chat(req.message, req.history))
    return {"responses": chunks}

@app.post("/api/agent/lint")
def lint_code(req: LintRequest):
    target = req.code or req.script_path
    if not target:
        raise HTTPException(status_code=400, detail="Missing code or script_path")
    res = agent._tool_lint(target)
    return res

@app.post("/api/agent/diagnose")
def diagnose_log(req: DiagnoseRequest):
    return agent._tool_diagnose(req.log_text)

@app.get("/api/templates")
def list_templates():
    tpl_candidates = [
        BASE_DIR / "templates",
        BASE_DIR / "graydient-workflow-tooling-unofficial" / "templates"
    ]
    tpl_dir = next((d for d in tpl_candidates if d.exists()), BASE_DIR / "templates")
    templates = []
    if tpl_dir.exists():
        for f in tpl_dir.glob("gen_*.py"):
            templates.append({
                "name": f.name,
                "path": str(f),
                "size": f.stat().st_size
            })
    return {"templates": templates}

@app.get("/api/template/{name}")
def get_template(name: str):
    tpl_candidates = [
        BASE_DIR / "templates" / name,
        BASE_DIR / "graydient-workflow-tooling-unofficial" / "templates" / name
    ]
    tpl_path = next((f for f in tpl_candidates if f.exists()), None)
    if not tpl_path:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"name": name, "content": tpl_path.read_text(encoding="utf-8")}

@app.post("/api/m3ds/decode-file")
def decode_local_file(path: str = Form(...)):
    p = Path(path)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    res = unpack_and_save(p, RENDERS_DIR / "decoded")
    return res

@app.post("/api/m3ds/upload")
async def upload_and_decode(file: UploadFile = File(...)):
    dest_path = RENDERS_DIR / "uploads" / file.filename
    os.makedirs(dest_path.parent, exist_ok=True)
    contents = await file.read()
    with open(dest_path, "wb") as f:
        f.write(contents)

    res = unpack_and_save(dest_path, RENDERS_DIR / "decoded")
    return res

@app.get("/api/renders")
def list_renders():
    return {"renders": render_mgr.get_all_renders()}

@app.post("/api/render/submit")
def submit_render(req: RenderSubmitRequest):
    job = render_mgr.submit_render(
        workflow_slug=req.workflow_slug,
        prompt=req.prompt,
        slot1=req.slot1,
        slot2=req.slot2,
        slot3=req.slot3,
        slot4=req.slot4,
        init_image=req.init_image,
        init_audio=req.init_audio
    )
    return job

@app.get("/api/render/{job_id}")
def get_render_job(job_id: str):
    job = render_mgr.get_render(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.post("/api/render/import-sample")
def import_sample(sample_name: str = Form(...)):
    candidates = [
        BASE_DIR / "Samples" / sample_name,
        BASE_DIR / sample_name,
        BASE_DIR.parent / "Samples" / sample_name,
        BASE_DIR.parent / sample_name,
        BASE_DIR / "graydient-workflow-tooling-unofficial" / sample_name
    ]
    target = next((c for c in candidates if c.exists()), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"Sample {sample_name} not found")

    job = render_mgr.add_existing_render(str(target))
    return job

@app.post("/api/sync")
def sync_repository(req: SyncRequest):
    cmd = ["python", str(BASE_DIR / "wf.py"), "sync", "-m", req.commit_message]
    if req.push:
        cmd.append("--push")
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BASE_DIR))
    return {
        "status": "success" if proc.returncode == 0 else "error",
        "stdout": proc.stdout,
        "stderr": proc.stderr
    }

# ── Serve Local Files & Static UI ──────────────────────────────────────────

@app.get("/files/{filepath:path}")
def serve_file(filepath: str):
    file_path = RENDERS_DIR / filepath
    if not file_path.exists():
        # Try absolute path fallback if within base dir
        file_path = Path(filepath)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Serve with appropriate media type
    suffix = file_path.suffix.lower()
    media_types = {
        ".glb": "model/gltf-binary",
        ".ply": "model/ply",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".mp4": "video/mp4",
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".json": "application/json"
    }
    return FileResponse(file_path, media_type=media_types.get(suffix, "application/octet-stream"))

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
def index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h3>Graydient Studio is starting up... Please reload in a moment.</h3>")
