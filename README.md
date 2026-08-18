# Graydient Workflow Engineering Toolchain

This repository contains the complete, unified toolchain for authoring, linting, packaging, and staging ComfyUI workflows on **Graydient SaaS** ephemeral GPU runners. It bundles programmatic workflow building APIs, local pre-flight validation rules, a verified model weights registry, and agent skills to prevent quota-burning errors.

---

## Repository Structure

```
graydient-workflow-tooling/
├── .agents/                    # Custom agent integrations
│   └── skills/                 # Antigravity IDE Agent Skills
│       ├── preflight-plan/     # Pre-build validation workflow
│       └── harvest-session/    # Post-build knowledge ingestion
├── .claude/                    # Claude Code integrations
│   └── skills/                 # Claude-specific agent skills duplicate
├── graydient_builder/          # Core workflow builder Python package
│   ├── __init__.py
│   ├── core.py                 # GraydientWorkflow builder class
│   ├── linter.py               # Pre-flight linter logic and rules
│   ├── blocks.py               # Reusable subgraphs (e.g. audio sync)
│   ├── concept_db.json         # Local model weight staging database
│   └── node_schema_db.json     # Hand-verified ComfyUI node inputs registry
├── comfyui-graydient-okf-catalog/ # Open Knowledge Format (OKF) Catalog
│   ├── okf.yaml                # Index of all knowledge items (KI-001 - KI-009)
│   └── catalog/                # Markdown files detailing platform rules
├── wf.py                       # Unified CLI Tool
├── wf.bat                      # Windows CLI wrapper
├── GRAYDIENT-COMPLETE-REFERENCE.md # Complete system developer reference
└── okf_knowledge_catalog.md    # Summary index of OKF catalog
```

---

## 1. System Architecture & The Dual-Workflow Cycle

Graydient runs ComfyUI workflows on temporary, clean GPU containers. Because there is no persistent state, workflows are deployed via a single **Backup/Restore JSON** file (`GraydientWorkflow-*.json`). 

### The Dual-Workflow Requirement (KI-001)
Every backup JSON must contain two separate representations of the ComfyUI graph:
1. **`workflow` (Standard Format)**: A serialized drag-and-drop visual graph containing UI coordinates (`nodes` and `links`). It is used exclusively to render the UI on the Graydient dashboard.
2. **`workflow_2` (API / Prompt Format)**: A clean execution graph keyed by string Node IDs (`"1"`, `"2"`). Each node contains a `class_type` and its literal `inputs`. This is what the Graydient backend actually executes.

> [!WARNING]
> A common mistake is submitting the standard format under `workflow_2`. The engine will fail to execute it because it expects `class_type` instead of `type` and does not parse visual UI lists.

---

## 2. Programmatic Workflow Building

Workflows are authored in Python scripts (`gen_*.py`) using the `GraydientWorkflow` API.

### Scaffolding a New Workflow
Use the CLI to create a template script:
```bash
python wf.py new my-workflow-slug
```
This generates `gen_my-workflow-slug.py` containing a boilerplate build.

### Core Builder API (`graydient_builder/core.py`)
```python
from graydient_builder import GraydientWorkflow, stage_model

# 1. Initialize the workflow container
wf = GraydientWorkflow(
    name="my-workflow-slug",
    description="My custom workflow description"
)

# 2. Stage model weight requirements
# Injects concept mapping entries to download files before ComfyUI boots
stage_model(wf, "ltx-video-2.5")

# 3. Add custom input fields (Field Mappings)
wf.add_field_mapping(
    node_id=1,
    node_input_name="prompt",
    local_field="prompt",
    help_text="Positive prompt for video generation"
)

# 4. Set Standard & API workflows
wf.set_workflows(standard_workflow_dict, api_workflow_dict)

# 5. Validate & Save
# Automatically runs the local pre-flight linter on save
wf.save()
```

### Model Staging & Concept Mapping (`concept_mapping`) (KI-002)
To prevent runtime timeouts (maximum execution budget is **~380 seconds**), model weights must be pre-downloaded via the `concept_mapping` list:
- `url`: Direct HTTP/S link (from HuggingFace, ModelScope, etc.).
- `destination`: Relative path to ComfyUI's model directory (e.g. `unet/model.safetensors` stages under `{ComfyUI}/models/unet/model.safetensors`).

> [!IMPORTANT]
> **Custom Node Offline Rule**: Any custom node code running on Graydient *must* check if staged files exist locally on disk before attempting to download them from the network. Failing to do so causes network timeouts or 403 blocks.

### Field Mappings & Param Indexing (KI-003)
Field mappings map Graydient SaaS UI fields (like `prompt`, `seed`, `slot1`, `slot2`, `init_image_url`, `init_audio_url`) to widgets on the ComfyUI nodes:
- `node_id`: Target node ID.
- `node_input_name`: Input parameter key in the node's Python class.
- `node_input_index`: **0-based index counting only primitive widgets** (strings, integers, floats, dropdowns). Any inputs that receive links from other nodes (sockets) **must be excluded** when calculating this index.

---

## 3. Reusable Subgraph Blocks (`graydient_builder/blocks.py`)

The toolchain provides pre-built, verified chains to solve common challenges.

### Audio Duration Sync Block
For video generators (LTX 2.5, Wan, Cosmos), you often need to sync the generated video frame count to an uploaded voiceover or soundtrack clip:
```python
from graydient_builder.blocks import add_audio_duration_sync_block

# Injects: Load Audio Any -> Audio Duration -> Math Expression: round(a * fps)
audio_block = add_audio_duration_sync_block(
    wf,
    load_audio_id=2,
    duration_node_id=4,
    math_node_id=5,
    fps=30,
    field_name="init_audio_url"
)
```

---

## 4. Pre-Flight Linter (`graydient_builder/linter.py`) (KI-007)

The linter automatically checks for common SaaS execution constraints, preventing expensive GPU quota failures.

### Verified Node Input Schemas (`node_schema_db.json`)
The linter parses the execution graph (`workflow_2`) and cross-references inputs against `node_schema_db.json`.
- **Known Node Class + Unknown Input Key**: Triggers a blocker **[ERROR]** (`SCHEMA_UNKNOWN_INPUT_KEY`). Historically, guessed input keys (e.g. `.samples` instead of `.av_latent`) were the #1 cause of failed SaaS jobs.
- **Unknown Node Class**: Triggers an **[INFO]** warning (`SCHEMA_UNVERIFIED_NODE`). This reminds you to check the custom node source code, rather than assuming silence means the node is configured correctly.

### Banned Dependencies & Banned Packages
- Ephemeral runners do not have Rust (`cargo`), C++ compilers, or Python setuptools-rust toolchains.
- Packages like `flash-attn`, `deepspeed`, or `maturin` are banned or flagged with warnings.
- *Note: `ninja` is allowed since it ships pre-built manylinux wheels.*

### Platform Gotchas Checked
1. **LoadAudio Ambiguity**: Flags standard `LoadAudio` nodes mapped to URL inputs, as they will crash if they resolve a remote URL. Warns to use `Load Audio Any` instead.
2. **VHS Output-Picker Fix**: Flags `VHS_VideoCombine` nodes receiving audio if the workflow's top-level `"extra"` dictionary lacks `VHS_MetadataImage: false` and `VHS_KeepIntermediate: false`. Without these, VHS leaves multiple temp files in the output directory, causing the Graydient output-picker to non-deterministically return the wrong file (e.g., a static PNG instead of the compiled video).

---

## 5. Unified CLI Tool (`wf.py`)

A single entrypoint command line utility to manage tasks.

### Commands

| Command | Arguments | Description |
|---|---|---|
| `search` | `<query>` | Search nodes, concept staging database, and Graveyard constraints. |
| `staging` | `[filter]` | List verified HuggingFace/ModelScope model weight sources. |
| `lint` | `<target>` | Lint a completed `GraydientWorkflow-*.json` or execute and lint a `gen_*.py` script. |
| `new` | `<name> [--template <tpl>]` | Scaffold a new generator script. Templates: `video-audio` (default), `basic`. |
| `bury` | `<title> --reason <reason>` | Log a newly discovered container failure mode or anti-pattern to the Graveyard file. |

*Example usage:*
```bash
# Scaffold
python wf.py new subtitles-gen

# Lint a file
python wf.py lint gen_subtitles-gen.py

# Search database
python wf.py search "audioldm"
```

---

## 6. Agent Skills (`.agents/skills/`)

Two runnable skills are provided in this repository to automate pre-build planning and post-build knowledge ingestion:

### Skill 1: `preflight-plan` (Pre-Build)
**Run BEFORE writing any code for a new or speculative workflow.**
- **Goal**: Separates functional intent from the proposed vehicle (packages, custom nodes).
- **Process**:
  1. Isolate *Intent* (what user wants) vs *Vehicle* (how we build it).
  2. Cross-reference the proposed vehicle against the Graveyard (`KI-007`) and node schemas (`node_schema_db.json`).
  3. If a blocker is detected, run the **Intent-vs-Vehicle Pivot Protocol (KI-009)**: Acknowledge intent, explain the failure mode constraint, and offer 1–2 verified routes.

### Skill 2: `harvest-session` (Post-Build)
**Run AFTER a session delivers a confirmed working workflow.**
- **Goal**: Ingest new discoveries (new custom node input keys, model weight weights staging URLs, platform bugs) back into the linter and catalog database.
- **Process**:
  1. Capture only confirmed, real-world data (not speculative guesses).
  2. Update `node_schema_db.json` with new node signatures.
  3. Update `concept_db.json` and `KI-008-concept-mapping-registry.md` with verified staging links.
  4. Update `linter.py` if custom rules are needed to catch new failure modes.
  5. Run `python wf.py lint` one last time to ensure the new rule passes on the working generator script.
