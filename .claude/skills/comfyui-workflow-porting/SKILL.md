---
name: comfyui-workflow-porting
description: Given a Hugging Face model link that matches one of our known pipelines (TripoSG image-to-3D, Bernini/Wan2.2 video-to-video, MisoTTS text-to-speech), emit a ready-to-drag-in ComfyUI workflow JSON, a custom-node/model install list, and a short usage doc. Plain local ComfyUI only — no Graydient/hosting dependency.
---

# ComfyUI Workflow Porting

Turns a Hugging Face model link into a working local ComfyUI package: the workflow
graph, what to install, where model files go, and how to run/prompt it. This is the
plain-ComfyUI counterpart of the `graydient-workflow-authoring` skill — same node
graphs and hard-won pitfalls, none of the Graydient deployment plumbing
(`field_mapping`, `concept_mapping`, backup/restore JSON, ephemeral containers).

Read `../../COMFYUI-REFERENCE.md` first if you haven't — it covers the two workflow JSON
formats and the general pitfalls this skill assumes you already know.

## When to use

- Someone hands you a Hugging Face repo link for a model and wants a runnable ComfyUI
  workflow for it, matching one of the pipelines we've already built and battle-tested.
- Porting one of our existing pipelines to a teammate's plain local ComfyUI install.

## What this is NOT

Not a general "any HF model → arbitrary new ComfyUI graph" generator. It only knows
the pipelines below. For a genuinely new model/architecture, you're building a new
graph from scratch — start from `../../COMFYUI-REFERENCE.md` §1 (workflow JSON anatomy)
and the target model's own repo/paper for what nodes it actually needs, not this
skill.

## Known pipeline → Hugging Face link map

| HF link contains | Pipeline | Modality |
|---|---|---|
| `VAST-AI/TripoSG` or `VAST-AI/TripoSG-scribble` or `wgsxm/PartCrafter` | Image → 3D mesh | 3D |
| `Kijai/WanVideo_comfy_fp8_scaled` (path `Bernini/...`) | Bernini video-to-video | Video |
| MisoTTS checkpoint repos (see `pipelines/misotts.md`) | Text-to-speech | Audio |

If the link doesn't match any row, say so plainly rather than guessing a graph — stop
and tell the user this pipeline isn't in the known set yet.

## Procedure

1. **Identify the pipeline** from the HF link using the table above.
2. **Read the matching pipeline file** in `pipelines/` (below) — it has the exact
   node graph (standard *and* API format), model placement table, custom node repos,
   and pip requirements for that pipeline.
3. **Emit three files** into the user's target directory:
   - `<pipeline>-workflow.json` — the **standard format** graph (drag straight into
     ComfyUI's canvas). Build it from the node list in the pipeline file, filling in
     any user-supplied specifics (e.g. seed, steps) at sane defaults.
   - `<pipeline>-INSTALL.md` — custom node git-clone list, pip requirements, and a
     model-placement table (HF file → exact path under `ComfyUI/models/...`).
   - `<pipeline>-USAGE.md` — 10-20 lines: what each exposed widget controls, what a
     good first prompt/input looks like, and one likely failure mode with the fix
     (pull from `../../COMFYUI-REFERENCE.md` §6 if relevant).
4. **Do not** wrap the output in a Graydient-style config object, and do not invent
   `field_mapping`/`concept_mapping`/`avg_elapsed`/`peak_vram_usage` fields — those
   are Graydient hosting metadata with no meaning in plain ComfyUI.
5. If asked to build the API-format JSON too (e.g. the user wants to call ComfyUI's
   own `/prompt` REST endpoint programmatically rather than using the UI), build it
   node-for-node from the same graph, keyed by string node ID, using `class_type`
   (never `type`) — see `../../COMFYUI-REFERENCE.md` §1 for the exact shape and the two
   most common mistakes converting between formats.

## Building the standard-format JSON

Author it as a small Python script (mirrors how we build these internally) so the
graph is easy to review and re-run rather than hand-typed:

```python
import json

nodes = [
    {"id": 1, "type": "LoadImage", "pos": [0, 120], "size": [300, 58],
     "order": 0, "mode": 0, "inputs": [],
     "outputs": [{"name": "IMAGE", "type": "IMAGE", "links": [1], "slot_index": 0}],
     "widgets_values": ["example.png"]},
    # ...one dict per node, straight from the pipeline file's node table
]
links = [
    # [link_id, from_node, from_slot, to_node, to_slot, "TYPE"]
]
workflow = {
    "last_node_id": max(n["id"] for n in nodes),
    "last_link_id": len(links),
    "nodes": nodes, "links": links,
    "groups": [], "config": {},
    "extra": {"ds": {"scale": 0.8, "offset": [0, 0]}, "frontendVersion": "1.43.18"},
    "version": 0.4,
}
with open("pipeline-workflow.json", "w") as f:
    json.dump(workflow, f, indent=2)
```

`json.dump` handles escaping — never hand-build the JSON string.

## Pipeline files

- [`pipelines/triposg.md`](pipelines/triposg.md) — image → 3D mesh
- [`pipelines/bernini.md`](pipelines/bernini.md) — video-to-video
- [`pipelines/misotts.md`](pipelines/misotts.md) — text-to-speech

Each contains: exact node list with IDs/positions/widgets ready to paste into the
Python builder above, the API-format equivalent, model placement table, custom node
repos, pip requirements, and known pitfalls specific to that pipeline.
