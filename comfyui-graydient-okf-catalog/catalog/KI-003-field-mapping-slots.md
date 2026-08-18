---
id: "KI-003"
title: "Field Mapping Specification & Widget Parameter Indexing"
version: "1.0.0"
type: "specification"
tags:
  - field_mapping
  - slots
  - widgets
  - node_input_index
sources:
  - "GRAYDIENT-COMPLETE-REFERENCE.md"
---

# KI-003: Field Mapping Specification & Widget Parameter Indexing

## 1. Overview
`field_mapping` maps user controls from the Graydient frontend UI or API request body (`prompt`, `seed`, `slot1`, `slot2`, `init_image_url`, `init_audio_url`) to specific input widgets of nodes in the standard ComfyUI graph.

---

## 2. Widget Indexing Rule (`node_input_index`)
> [!CAUTION]
> `node_input_index` is a **0-based index counting ONLY primitive widgets in `widgets_values`**. Connected socket inputs with incoming link IDs are **EXCLUDED** from index calculation.

### 2.1 Example Calculation
Consider a node with inputs defined in Python `INPUT_TYPES`:
1. `model` (SOCKET / LINK input from loader) ❌ *Skipped*
2. `prompt` (STRING widget) 👉 **index 0**
3. `negative_prompt` (STRING widget) 👉 **index 1**
4. `audio_length` (FLOAT widget) 👉 **index 2**
5. `num_steps` (INT widget) 👉 **index 3**
6. `guidance_scale` (FLOAT widget) 👉 **index 4**
7. `sample_rate` (INT widget) 👉 **index 5**
8. `seed` (INT widget) 👉 **index 6**

### 2.2 Field Mapping Definition Structure
```json
{
  "default_value": 48000,
  "help_text": "Sample rate of output audio file (e.g. 16000, 32000, 48000).",
  "local_field": "slot1",
  "maximum_value": 48000,
  "minimum_value": 8000,
  "node_id": 2,
  "node_input_index": 5,
  "node_input_name": "sample_rate",
  "node_name": "AudioLDM Sampler"
}
```

---

## 3. Canonical Local Field Names

**CORRECTED 2026-08-17** — the `slot1`-`slot3` cap and the plain `init_image_url`/
`init_audio_url` picture above were both wrong/incomplete. Source: Graydient's own
field list, provided directly by the user (a real platform screenshot), not
independently re-derived or job-tested this session — treat the *names* below as
authoritative, but re-verify actual runtime behavior (which of a triplet's three
fields a given submission path populates) against a real job before depending on it.

### 3.1 Generic instruction slots — `slot1` through `slot9`
Text/numeric/dropdown controls that don't fit one of the premapped fields below
(`length`, `fps`, `size`, `cfg`, `controlguidance`, `strength`, `guidance`, and a few
more rarely used) all go here. **All nine work**, not just slot1-3 — the KI-003 v1.0.0
table undersold this and caused unnecessary hedging in at least one session (the
subtitle-burn-in workflow avoided slot4/slot5 out of caution that turned out to be
unfounded).

### 3.2 Media transport fields — one triplet per media type, `1` through `9`
Each media type gets its own numbered family, each entry being a `{bool, filename,
url}` triplet:

- `init_image_bool` / `init_image_filename` / `init_image_url` (and `image1`...`image9`
  for additional images)
- `init_video_bool` / `init_video_filename` / `init_video_url` (and `video1`...`video9`)
- `init_audio_bool` / `init_audio_filename` / `init_audio_url` (and `audio1`...`audio9`)

`_bool` flags whether that media slot is populated at all; `_filename` is a local
ComfyUI `input/` directory filename (pre-staged upload); `_url` is a fetchable
http(s) link. **Which of `_filename` vs `_url` actually gets populated for a given
submission is not guaranteed** — map BOTH into the node (as two separate widget
inputs, first-non-empty-wins, same pattern as the `Load Audio Any` node in
`node_schema_db.json`), don't assume `_url` alone covers every case. A node that
only accepts a single `url`-named input and relies on a `field_mapping` entry
targeting just `init_video_url` will silently receive nothing on submissions that
populate `init_video_filename` instead.

### 3.3 The one-media-type-per-workflow rule
**A Graydient job can only initialize ONE media type from the "reply to this
message" transport** (this is the Telegram reply-to-media flow — you can only reply
to one attachment at a time). If a workflow genuinely needs two different media
types (e.g. an image AND a separate audio clip), only ONE of them can come in
through the `init_<type>_*` triplet; the other must be supplied via the numbered
per-type slots (`image1`, `video1`, `audio1`, etc.), not by defaulting it to
`init_image_url` out of convenience.

**Known anti-pattern, not yet fully audited**: multiple existing `gen_*.py` scripts
in this project default a secondary media input to `init_image_url` even when the
workflow's actual second input is a video or audio file. This needs a project-wide
audit, not a blanket fix — check `node_schema_db.json` / KI-007 before assuming which
scripts are actually affected.

### 3.4 Other canonical fields
- `prompt` / `prompt_positive`: Main positive text prompt.
- `prompt_negative`: Negative prompt.
- `seed`: Random seed integer.
- `length`: Output length budget (duration in seconds or token limit).
- `steps`: Step count.
- `fps`, `size`, `cfg`, `controlguidance`, `strength`, `guidance`: premapped fields for
  their obvious purposes — use these instead of a generic slot when the control
  genuinely is one of these, so Graydient's own UI can render the right widget type.
