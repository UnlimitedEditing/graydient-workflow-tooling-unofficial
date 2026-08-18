---
id: "KI-001"
title: "Dual-Workflow JSON Architecture & Deployment Cycle"
version: "1.0.0"
type: "architecture"
tags:
  - comfyui
  - graydient
  - backup-restore
  - generator-scripts
sources:
  - "GRAYDIENT-COMPLETE-REFERENCE.md"
  - "COMFYUI-REFERENCE.md"
---

# KI-001: Dual-Workflow JSON Architecture & Deployment Cycle

## 1. Overview
Graydient deploys ComfyUI workflows on ephemeral SaaS GPU instances using single-file **Backup/Restore JSON** configurations named `GraydientWorkflow-<slug>-v<version>.json`.

Workflows are authored programmatically via Python generator scripts (`gen_<slug>.py`), which construct the dictionary structure and output the single JSON artifact.

---

## 2. Dual-Workflow JSON Structure
Every backup JSON file wrapper contains a top-level `"graydient_workflow"` dictionary holding two required ComfyUI format keys:

```json
{
  "graydient_workflow": {
    "version": 1,
    "description": "User-facing description of the workflow...",
    "avg_elapsed": 45,
    "peak_vram_usage": 8000,
    "platform": "comfyui",
    "requirements": {
      "github": ["https://github.com/UnlimitedEditing/ComfyUI-AudioLDM"],
      "pip": ["diffusers", "transformers", "accelerate"]
    },
    "field_mapping": [...],
    "concept_mapping": [...],
    "workflow": "{ ... serialized standard UI graph JSON ... }",
    "workflow_2": "{ ... serialized API prompt JSON ... }"
  }
}
```

### 2.1 Standard Format (`"workflow"` key)
- Represents the drag-and-drop ComfyUI web interface.
- Serialized JSON string containing `"nodes"`, `"links"`, `"groups"`, `"extra"`, `"version"`.
- Nodes are identified by an integer `id` field inside objects in a list.
- Used when a user drags the JSON into a visual ComfyUI canvas.

### 2.2 API / Prompt Format (`"workflow_2"` key)
- Represents the API payload executed by the ComfyUI server.
- Serialized JSON object keyed directly by string Node IDs (`"1"`, `"2"`, `"3"`).
- Each node entry contains `"class_type"`, `"inputs"`, and `"_meta"`.
- Linked inputs reference previous node outputs via 2-element tuples: `["1", 0]` (Node ID string, Output Slot Index).

---

## 3. The `gen_*.py` Authoring Pattern
To guarantee consistency across production workflows:
1. Define the `standard` graph dictionary in Python.
2. Define the `api` dictionary in Python.
3. Define the metadata, `requirements`, `field_mapping`, and `concept_mapping`.
4. Serialize `standard` and `api` using `json.dumps(standard, indent=2)`.
5. Dump the final dictionary to `D:\tripostl\GraydientWorkflow-<slug>-v<version>.json`.
