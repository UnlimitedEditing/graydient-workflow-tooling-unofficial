# Fluxdon's Graydient Workflow Engineering Toolchain (not officially supported by graydient)

This repository contains the complete, unified toolchain for authoring, linting, packaging, and staging ComfyUI workflows on **Graydient SaaS** ephemeral GPU runners. It bundles programmatic workflow building APIs, local pre-flight validation rules, a verified model weights registry, and agent skills to prevent quota-burning errors.

---

## Quick Start (setup wizard)

```bash
python setup_wizard.py          # interactive: checks everything, offers to install/build what's missing
python setup_wizard.py --check  # report only
```

It checks Python >= 3.9, git, Node >= 22 + npm, Edge/Chrome, builds the bundled `cli/`, installs and logs in the Hugging Face CLI (`hf`; needed to host concept weights), and tells you how to add your Graydient API key and your Telegram magic-link sessions. It never takes a secret itself: `hf auth login` uses Hugging Face's own prompt, and the Graydient steps just print the command for you to run.

---

## Repository Structure

```
graydient-workflow-tooling/
├── .agents/                    # Custom agent integrations
│   └── skills/                 # Antigravity IDE Agent Skills
│       ├── preflight-plan/     # Pre-build validation workflow
│       ├── harvest-session/    # Post-build knowledge ingestion
│       ├── graydient-archive/  # Deploy/describe workflows in the community web UI
│       └── graydient-concepts/ # Install/manage Concepts (LoRAs) in the web UI
├── .claude/                    # Claude Code integrations
│   └── skills/                 # Same four skills, for Claude Code
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
├── cli/                        # `graydient` CLI (Node/TypeScript): render, query, and drive the archive + concept web UIs
├── setup_wizard.py             # Dependency checker / first-run setup
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
To prevent runtime timeouts (ComfyUI **run time** is capped at **~180 seconds**, startup included; downloads staged by `concept_mapping`, repo clones, pip installs and first-time machine startup happen *before* that clock and are not counted. Plan for `Prompt executed in` <= ~120 s), model weights must be pre-downloaded via the `concept_mapping` list:
- `url`: Direct HTTP/S link (from HuggingFace, ModelScope, etc.).
- `destination`: Relative path to ComfyUI's model directory (e.g. `unet/model.safetensors` stages under `{ComfyUI}/models/unet/model.safetensors`).

> [!IMPORTANT]
> **Custom Node Offline Rule**: Any custom node code running on Graydient *must* check if staged files exist locally on disk before attempting to download them from the network. Failing to do so causes network timeouts or 403 blocks.

### Field Mappings & Param Indexing (KI-003)
Field mappings map Graydient SaaS UI fields (like `prompt_positive`, `seed`, `slot1`..`slot8`, `init_image_url`, `init_audio_url`; note `prompt` is NOT delivered to the node, and slot4..slot8 accept numbers only: there is no slot9) to widgets on the ComfyUI nodes:
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

### Other checks added by later harvests
- **`SLOT_DOES_NOT_EXIST`** (WARNING): a mapping to `slot9` or higher can never receive a value.
- **`SLOT4_9_NON_NUMERIC_DEFAULT`** (INFO): slot4..slot8 take numbers only from users; string choices belong on a numeric slot driving a lazy `ComfySwitchNode`.
- **Node titles in `concept_mapping`**: a title containing `.` (with `-`) in a `field_mapping` string made a real job fail at preparation with a bare `ValueError` (ERROR); a hyphen alone is a WARNING.
- **Dynamic-LoRA entries** (`type: "local"`, `allow_dynamic: true`) are accepted, not flagged as missing a URL.
- **`PIP_SPEC_MAYBE_DROPPED`** (INFO): pip entries with `<`, `>`, `[extras]` or `@` were once omitted from a job's install command; check the job's COMMAND block (KI-007 sec 19).

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

## 6. Agent Skills (`.agents/skills/`, mirrored in `.claude/skills/`)

Four skills are provided: two for the build loop (`preflight-plan`, `harvest-session`) and two for operating the Graydient community web UI (`graydient-archive`, `graydient-concepts`).

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

### Skill 3: `graydient-archive` (Deploy & Describe Workflows)
**Run after a `gen_*.py` writes a `GraydientWorkflow-*.json` that needs deploying, or to edit a workflow's public-facing details.**
- Drives the community archive page (the one behind Telegram `/archive`) with the `graydient archive` CLI: restore or create from a backup JSON, set name/description/cover image, read any tab (Fields, Models, Logs), check feature flags.
- Encodes the hard-won rules: a restore does not reliably carry flags or the description (use `--fix`); never click *New Workflow* casually; confirm the target id before restoring (it overwrites); one render at a time per account; first run of a fresh restore can take ~2000 s.
- Going public needs a working run, a description and a picture, and is always the owner's explicit decision (`--public` needs `--confirm-public`).

### Skill 4: `graydient-concepts` (Install Concepts / LoRAs)
**Run when asked to add a LoRA from Civitai or Hugging Face to Graydient.**
- Drives the concept manager (Telegram `/concept /edit`) with `graydient archive concept new|edit|delete|list`: host the weights on a public Hugging Face repo (never hotlink Civitai), then fill name, token, download URL, family, type, description and example image.
- A concept needs a description and an example picture to be shareable; `delete` is permanent and needs `--confirm-delete`.

> **Prerequisite for skills 3 and 4:** they use the `graydient` CLI bundled in [`cli/`](cli/) (Node >= 22 + Playwright with Edge or Chrome installed). Build it once with `cd cli && npm ci && npm run build` (optionally `npm link` to get a `graydient` command), then log in with a magic link from the Graydient Telegram bot (`/archive` or `/concept /edit`). The login is kept in `~/.graydient/archive-session.json`. Some paths in the skills are the author's machine; adjust them.
