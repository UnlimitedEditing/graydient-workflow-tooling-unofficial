# Unofficial Graydient Workflow Tooling Suite

A unified, production-grade toolkit, CLI, knowledge catalog, and agent skill suite for authoring, validating, deploying, and maintaining cloud ComfyUI workflows on [Graydient.ai](https://graydient.ai).

Maintained by **UnlimitedEditing** and compiled from dozens of live cloud deployments spanning Text-to-Image, Flow-Matching DiT, Video Generation, Audio/Music Synthesis, Voice Cloning, and 3D Mesh Reconstruction.

---

## 🌟 The End-to-End Workflow Engineering Lifecycle

This repository covers the entire Graydient workflow lifecycle — from the moment a new model is announced on Hugging Face or Civitai, all the way to continuous maintenance and log retrieval.

```
 ┌───────────────────────┐
 │ 1. Ideation & Research│ ──► HF / Civitai audit, weight format check, preflight-plan skill (KI-009)
 └──────────┬────────────┘
            ▼
 ┌───────────────────────┐
 │ 2. Graph Authoring    │ ──► graydient_builder (core, blocks), field & socket slot mappings
 └──────────┬────────────┘
            ▼
 ┌───────────────────────┐
 │ 3. Pre-Flight Linting │ ──► wf.py lint (node_schema_db.json, anti-patterns, flow schedulers)
 └──────────┬────────────┘
            ▼
 ┌───────────────────────┐
 │ 4. Weight Staging     │ ──► concept_mapping (~2.4 Gbps pre-stage) & ZeroGPU cloud quantization
 └──────────┬────────────┘
            ▼
 ┌───────────────────────┐
 │ 5. Archive Deployment │ ──► graydient archive new / restore --fix (Playwright automation)
 └──────────┬────────────┘
            ▼
 ┌───────────────────────┐
 │ 6. Execution & Test   │ ──► graydient render (sequential test, auto-media upload, timeout 45)
 └──────────┬────────────┘
            ▼
 ┌───────────────────────┐
 │ 7. Cover & Publishing │ ──► archive meta (--image cover.jpg, bot docs, owner-gated public)
 └──────────┬────────────┘
            ▼
 ┌───────────────────────┐
 │ 8. Log Diagnostics   │ ──► wf.py diagnose (automated failure analysis & KI-007 cross-ref)
 └──────────┬────────────┘
            ▼
 ┌───────────────────────┐
 │ 9. Session Harvesting │ ──► harvest-session skill ──► wf.py sync --push ──► GitHub repo
 └───────────────────────┘
```

---

## 📦 What's Inside the Suite

### 1. The Core Builder Engine (`graydient_builder/`)
- **`core.py`**: Clean object-oriented abstraction for generating both standard ComfyUI canvas JSON (`workflow`) and API execution JSON (`workflow_2`), managing inputs, outputs, and field mappings.
- **`blocks.py`**: Battle-tested reusable subgraph modules (such as `add_audio_duration_sync_block` to sync video length to audio clips).
- **`linter.py`**: Pre-flight zero-defect linter with 25+ automated checks:
  - Banned C++/Rust compilation packages (`maturin`, `flash-attn`).
  - Strict separation of linked input sockets vs 0-based primitive widget indices in `field_mapping` (KI-003).
  - Slot indexing constraints (`slot1`–`slot8` only; slot4..slot8 accept numbers only).
  - Flow-matching scheduler validation (`simple` vs `sgm_uniform`).
  - Redundant flow-matching shift detection (e.g. MOSS-Image native shift 5.0 vs `ModelSamplingSD3`).
  - Partial denoise img2img verification (flagging models with dormant vision towers).
  - Safe output-picker flags (`VHS_MetadataImage: false`, `VHS_KeepIntermediate: false`).
- **`concept_db.json`**: Registry of live-tested direct model download URLs and container target paths.
- **`node_schema_db.json`**: Exhaustive catalog of verified ComfyUI node class types, parameter keys, widget orders, and output socket signatures.

### 2. The Python Management CLI (`wf.py` & `wf.bat`)
Single-entrypoint command-line utility for local workflow development:
- `python wf.py search "<query>"`: Search nodes, staged model concepts, generator scripts, and Graveyard rules.
- `python wf.py staging [filter]`: Query verified model URLs and container target destinations.
- `python wf.py lint <target>`: Execute a `gen_*.py` script and lint its output JSON with zero runtime surprises.
- `python wf.py new <slug> [--template <tpl>]`: Scaffold a new generator script from canonical templates.
- `python wf.py bury "<title>" --reason "<reason>"`: Append newly discovered container failure modes to `KI-007`.
- `python wf.py diagnose [path]`: Diagnostic log parser. Analyzes `workflow-failure-R*.txt` or raw container logs, extracts tracebacks, and points to the exact matching Graveyard rule and resolution.
- `python wf.py sync [--push] [-m "<msg>"]`: Synchronize resident files from your local workspace to this unified repository and push directly to GitHub.

### 3. The Official Graydient Node.js CLI (`cli/`)
Full TypeScript CLI (`graydient`) built with Commander and Playwright:
- **`graydient render`**: Submit prompts, stream events, auto-upload local media (`--init-image`, `--init-video`, `--init-audio`, `--init-mesh`, `--placeholder`), poll and download output assets.
- **`graydient archive`**: Complete Community Archive UI automation (`list`, `show`, `new`, `restore --fix`, `meta`, `dump --tab Fields|Models|Logs|Use|Details`).
- **`graydient concepts`**: LoRA and Concept management (`new`, `edit`, `delete`, `list`).
- **`graydient workflows`**: Search and query remote public/community workflows.
- **`graydient chat`**: Communicate with Graydient personas / LLMs.
- **`graydient ui`**: Local web UI with video queue and background worker.

### 4. The Knowledge Catalog & Graveyard (`comfyui-graydient-okf-catalog/`)
Comprehensive documentation of all architectural rules and hard-won lessons:
- **`KI-001`**: Architecture overview (ephemeral containers, DynamicVRAM, ComfyUI core).
- **`KI-002`**: Concept mapping pre-startup staging pipeline (~2.4 Gbps CDN).
- **`KI-003`**: Field mapping slot and widget indexing math (0-based widget counting excluding sockets).
- **`KI-004`**: Decoupled node patterns.
- **`KI-005`**: SaaS execution constraints (VRAM budgets, prompt execution timeouts $\le$ 120s).
- **`KI-006`**: Audio generation standards (sampling rates, duration matching).
- **`KI-007`**: Runtime constraints & Graveyard — **34 documented failure modes**, including flow-matching scheduler traps, TAEHV Wan latent upscale, residential upstream bandwidth limits, and Playwright timeouts.
- **`KI-008`**: Concept mapping registry — **14 verified staging stacks** with live-tested URLs and byte sizes.
- **`KI-009`**: Intent-vs-Vehicle Pivot Protocol — 3-step divergence protocol when a proposed technical method collides with catalog constraints.

### 5. Agent Skills (`.agents/skills/` and `.claude/skills/`)
Turnkey skill packages for AI pair programmers:
- **`preflight-plan`**: Pre-build gate isolating intent from vehicle, checking catalog constraints, and enforcing KI-009 before code is written.
- **`harvest-session`**: Post-build loop ingesting confirmed node schemas, model URLs, and runtime gotchas into the catalog, with automated sync to GitHub.
- **`graydient-archive`**: Playwright automation and deployment etiquette for Community Archive.
- **`graydient-concepts`**: Concept and LoRA installation, Hugging Face weight hosting, and Civitai handling.
- **`higgs-voice`**: Speech synthesis and voice cloning prompt patterns.
- **`comfyui-workflow-porting`**: Exporting Graydient pipeline graphs to plain local ComfyUI installations.

### 6. Tools & SDK (`tools/`)
- **`diagnose_log.py`**: Standalone failure analyzer for Graydient job error logs.
- **`zerogpu_quantize_template.py`**: Cloud-to-cloud ZeroGPU converter template for large model weights (KI-007 §32).
- **`graydient_client.py`**: Python SDK wrapper for the Graydient CLI with argument sanitization and media handling.

### 7. Canonical Workflow Templates (`templates/`)
- `gen_moss_image_t2i.py`: Text-to-Image / Layout generation with MOSS-Image 5B + Qwen3.5-9B.
- `gen_turbo_moss_t2i.py`: 8-step DMD Turbo Text-to-Image generation.
- `gen_fastwan13_720p_t2v.py`: 2-Stage Latent Upscale Video Generation (FastWan 1.3B 720p 3+1 step + TAEHV).
- `gen_audio_synced_video.py`: Audio-duration-synchronized video generator (`Load Audio Any` + `ComfyMathExpression`).
- `gen_higgs_tts.py`: Higgs Audio v3 Text-to-Speech / Voice Cloning.

---

## 🚀 Quickstart & Setup

### 1. Python Environment Setup
Install core Python dependencies:
```bash
pip install -r requirements.txt
```
*(Dependencies: `torch`, `safetensors`, `requests`, `pillow`, `huggingface_hub`)*

### 2. Graydient Node.js CLI Setup
Build and globally link the CLI:
```bash
cd cli
npm ci
npm run build
npm link
```

### 3. Log into Graydient Archive
1. Send `/archive` (or `/concept /edit`) to the Graydient Telegram bot and copy the magic link.
2. Log in using the CLI:
```bash
graydient archive login "<your-magic-link>"
graydient archive status
```
*(Session cookies are kept locally in `~/.graydient/archive-session.json`)*

---

## 🛠️ Typical Development & Deployment Loop

### Step 1: Preflight Check
Before writing generator code, check for known blockers:
```bash
python wf.py search "moss"
python wf.py staging "moss-image"
```

### Step 2: Build & Lint Workflow
Scaffold and edit your generator script, then build and lint:
```bash
python wf.py new my-workflow --template video-audio
python wf.py lint gen_my-workflow.py
```

### Step 3: Deploy to Archive
Deploy the generated backup JSON to your Graydient account as a private workflow:
```bash
graydient archive new GraydientWorkflow-my-workflow-v1.json --name "my-workflow"
```

### Step 4: Validate with a Live Test Render
Always test with a sequential render using a 45-minute timeout for cold-machine staging:
```bash
graydient render "a cinematic landscape /run:my-workflow /seed:42" --out ./test_out/test.png --timeout 45
```

### Step 5: Set Cover Image & Bot Documentation
```bash
graydient archive meta <workflow_id> --image ./test_out/cover.jpg
```

### Step 6: Diagnose Failures (If Any Occur)
If a render fails, inspect the error log with the diagnostic engine:
```bash
python wf.py diagnose
```

### Step 7: Harvest & Sync
When a build is confirmed working, harvest discoveries and push updates:
```bash
python wf.py sync --push -m "Harvest: my-workflow - confirmed node signatures and staging"
```

---

## 📖 Deep References
- **[`GRAYDIENT-COMPLETE-REFERENCE.md`](GRAYDIENT-COMPLETE-REFERENCE.md)**: 104 KB comprehensive encyclopedia of all Graydient mechanics, container limits, and active workflow inventory.
- **[`COMFYUI-REFERENCE.md`](COMFYUI-REFERENCE.md)**: Complete guide to plain ComfyUI graph mechanics, slot indexing, widgets, and JSON conversions.
- **[`cli/docs/`](cli/docs/)**: Telegram prompt syntax, API support notes, and agent integration guides.

---

## ⚖️ License & Credits
- Maintained by [UnlimitedEditing](https://github.com/UnlimitedEditing).
- Open-source under MIT License.
