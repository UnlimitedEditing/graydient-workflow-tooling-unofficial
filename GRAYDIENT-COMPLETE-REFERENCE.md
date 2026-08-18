# Graydient Workflow Building — Complete Reference

Everything known about authoring, deploying, debugging, and optimising workflows on
Graydient's cloud ComfyUI platform. Covers all modalities: image, video, 3D mesh, audio.
Designed to be dropped into any Claude project's CLAUDE.md or used as a standalone reference.

**This is the single-file Graydient handoff** — platform mechanics (§1–17) plus the
active workflow inventory (§18), the ForgeExpress data-image convention (§19), and
pipeline families not covered in the original §1–17 draft (§20). If you only read one
file for Graydient knowledge, read this one.

## 0. Companion doc, and things worth knowing before you touch anything

- **`D:\tripostl\COMFYUI-REFERENCE.md`** is the companion doc — plain ComfyUI mechanics
  (workflow JSON internals, custom-node pitfalls, VRAM/step-time math) with **zero**
  Graydient-specific material (no `field_mapping`, `concept_mapping`, backup/restore
  JSON, ephemeral containers, or timeout budget). This file is everything *on top of*
  that — the hosting layer. Read both; they don't duplicate each other.
- **Search for an existing ComfyUI node repo before writing a custom one.** By the time
  a model's been on Hugging Face more than a few days there's almost always a node repo
  for it already. This project has repeatedly burned time building from scratch when a
  maintained node existed (e.g. `Saganaki22/Higgs_v3-TTS-ComfyUI` for Higgs Audio v3 —
  found only after investigating a needlessly risky vllm-omni server architecture). If
  an existing repo covers most of what's needed, add a small glue-node repo for the gap
  rather than reimplementing the whole wrapper.
- **Two open contradictions in this doc's own history, unresolved — don't silently pick
  one:**
  1. **`concept_mapping` reliability.** §2/§6 below (and this project's CLAUDE.md) say
     "always add `concept_mapping`." But machine-class filesystem fragmentation (§6)
     means a model downloaded via `concept_mapping` on one machine class is *not*
     available if the next run lands on a different class — so it's best-effort, not
     guaranteed, especially for large multi-file downloads. Treat it as "worth adding,
     don't rely on it alone" — pair it with a node that auto-downloads on cache miss
     rather than assuming pre-staging always worked.
  2. **Timeout budget.** §1/§6 say "~300 s public tier." A separate empirical
     measurement (this project's CLAUDE.md, ny4-g machines) says ~380–400 s. These may
     be different tiers or machine classes — don't assume either number without
     checking which machine class/tier a workflow is likely to land on. Budget to the
     more conservative ~300 s when you don't know the tier.

---

## 1. What Graydient Is

Cloud ComfyUI execution platform. Spins up ephemeral GPU servers on demand.

- Each run gets a **fresh container** — no state persists in VRAM between runs
- ComfyUI custom nodes are **cloned fresh from GitHub every run** via the workflow config
  — **mostly true, not absolute**: confirmed live 2026-08-02 that some machines cache a
  prior checkout rather than always re-cloning (§6). After pushing a node-repo fix, don't
  assume the very next job reflects it — retry if it doesn't.
- Pip packages are installed fresh every run from the workflow config
- Files written to `/datapool/` DO persist across runs
- Public timeout: ~300 seconds from ComfyUI start. Pro tier is longer.
- DynamicVRAM (`comfy-aimdo`) is enabled on all instances — models can overflow VRAM into system RAM

---

## 2. The Backup / Restore Deployment Cycle

**This is the only correct way to author and deploy Graydient workflows.**

Never configure workflows through the Graydient UI tabs manually for new or updated workflows.
Instead, use the backup/restore cycle:

1. Write (or update) a `gen_*.py` Python script that builds the complete workflow config
2. Run the script — it writes `GraydientWorkflow-name-vN.json`
3. Upload that JSON to Graydient using the **Restore** (backup import) function
4. Graydient reads every field — custom nodes, pip deps, field mappings, both workflow
   formats, capability flags, metadata — in one step. No manual tab entry needed.

When Graydient **exports** a workflow (the "backup" button), it produces the same format.
This exported JSON is the canonical source of truth and can be re-imported as-is.

### Why not the UI tabs?

The UI tabs (Models, Custom Nodes, Pip Requirements, Fields) are how Graydient originally
exposed configuration. They still work but are tedious, error-prone, and produce no
version-controlled artifact. The backup JSON contains everything those tabs configure,
in a single versionable file.

---

## 3. Canonical Backup JSON Structure

```json
{
  "graydient_workflow": {
    "version": 17,
    "description": "Human-readable description of what this workflow does.",
    "avg_elapsed": 142.9,
    "peak_vram_usage": 19810.8,
    "platform": "comfyui",

    "requirements": {
      "github": [
        "https://github.com/org/repo-one",
        "https://github.com/org/repo-two"
      ],
      "pip": [
        "diffusers", "transformers", "trimesh", "opencv-python", "ninja"
      ]
    },

    "field_mapping": [
      {
        "local_field":      "init_image_url",
        "node_id":          1,
        "node_input_index": 0,
        "node_input_name":  "url",
        "node_name":        "Load Image From URL",
        "default_value":    "",
        "help_text":        null,
        "minimum_value":    null,
        "maximum_value":    null
      }
    ],

    "workflow":   "<STANDARD ComfyUI JSON as escaped string>",
    "workflow_2": "<API ComfyUI JSON as escaped string>",

    "supports_txt2img":  false,
    "supports_img2img":  true,
    "supports_txt2vid":  false,
    "supports_img2vid":  false,
    "supports_vid2vid":  false,
    "supports_txt2mesh": false,
    "supports_img2mesh": true,
    "supports_mesh2img": false,
    "supports_mesh2vid": false,
    "supports_txt2wav":  false,
    "supports_vid2wav":  false,
    "supports_wav2txt":  false,
    "supports_low_memory":       false,
    "supports_dynamic_concepts": false,
    "install_detected_nodes": true,
    "split_prompt_pos_neg":   false,
    "concept_mapping":  null,
    "external_config":  null,
    "external_provider": null,
    "extra_data":       null,
    "max_collect_attempts": null,
    "is_public":   true,
    "is_deleted":  false,
    "image_url":   "https://...",
    "post_install_script": null,
    "pre_install_script":  null
  }
}
```

Set only the `supports_*` flags that match the workflow's actual modality — Graydient uses
these to categorise and filter workflows in the UI. All others default to `false`.

### gen_*.py authoring pattern

```python
import json

DESCRIPTION = """\
One paragraph description of what this workflow does, what the slots control,
and any important caveats.\
"""

standard = { ... }   # standard ComfyUI workflow dict (see §4)
api      = { ... }   # API ComfyUI workflow dict (see §4)

cfg = {
  "graydient_workflow": {
    "version":          1,
    "description":      DESCRIPTION,
    "avg_elapsed":      120.0,       # seconds, from a real measured run
    "peak_vram_usage":  18187.5,     # MB, virtual (physical + DynamicVRAM overflow)
    "platform":         "comfyui",
    "requirements": {
      "github": ["https://github.com/org/repo"],
      "pip":    ["package-one", "package-two"],
    },
    "field_mapping": [ ... ],
    "workflow":   json.dumps(standard, indent=2),
    "workflow_2": json.dumps(api,      indent=2),
    "supports_img2img": True,
    "supports_txt2img": False,
    "install_detected_nodes": True,
    "is_public": True,
    # ... all other flags False / null
  }
}

with open("GraydientWorkflow-name-vN.json", "w") as f:
    json.dump(cfg, f, indent=2)

print("Workflow vN written OK")
```

`json.dumps()` handles all nested escaping automatically. Never hand-escape.

---

## 4. The Two ComfyUI Workflow Formats

Both must be present and correct. They serve different purposes.

### Standard format (`"workflow"` key) — drag into ComfyUI UI

```json
{
  "last_node_id": 9,
  "last_link_id": 7,
  "nodes": [
    {
      "id": 1,
      "type": "LoadImageFromURL",
      "pos": [0, 120],
      "size": [300, 58],
      "order": 0,
      "mode": 0,
      "inputs": [],
      "outputs": [
        {"name": "IMAGE", "type": "IMAGE", "links": [1], "slot_index": 0},
        {"name": "MASK",  "type": "MASK",  "links": [], "slot_index": 1}
      ],
      "title": "Load Image From URL",
      "widgets_values": [""]
    }
  ],
  "links": [
    [1, 1, 0, 3, 0, "IMAGE"]
  ],
  "groups": [],
  "config": {},
  "extra": {"ds": {"scale": 0.8, "offset": [0, 0]}, "frontendVersion": "1.43.18"},
  "version": 0.4
}
```

- Each node has `"type"` (class name) + pixel positions + `"widgets_values"` array
- Links array format: `[link_id, from_node_id, from_slot, to_node_id, to_slot, "TYPE"]`
- `"order"` is a **display hint only** — ComfyUI executes by graph topology, not this field
- `last_node_id` and `last_link_id` should match the highest IDs used

### API format (`"workflow_2"` key) — what Graydient actually executes

```json
{
  "1": {
    "inputs": {"url": ""},
    "class_type": "LoadImageFromURL",
    "_meta": {"title": "Load Image From URL"}
  },
  "4": {
    "inputs": {
      "model":   ["2", 0],
      "image":   ["3", 0],
      "seed":    42,
      "steps":   50,
      "cfg":     7.0
    },
    "class_type": "TripoSGInference",
    "_meta": {"title": "TripoSG Inference"}
  }
}
```

- Nodes keyed by **string** ID (`"1"`, `"4"` — never integers)
- Uses `"class_type"` — NO `"type"` field
- Widget values AND link values both go in `"inputs"` dict together
- Links are `["source_node_id_string", output_slot_index]` tuples

**Most common mistake**: pasting standard format as `workflow_2`. The engine sees
`class_type: null` and fails with `"node X has no class_type"`.

**Second most common mistake**: `PrimitiveNode` in the API JSON. `PrimitiveNode` is
UI-only — it must not appear in `workflow_2` as a `class_type`. Use direct widget
values instead and expose them via field_mapping.

---

## 5. Field Mapping — Connecting Graydient Slots to Nodes

`field_mapping` connects Graydient's user-facing parameter slots to specific node
widget values in the workflow.

```json
{
  "local_field":      "prompt",
  "node_id":          3,
  "node_input_index": 0,
  "node_input_name":  "text",
  "node_name":        "CLIPTextEncode",
  "default_value":    "A cinematic shot",
  "help_text":        "Main text prompt describing the scene.",
  "minimum_value":    null,
  "maximum_value":    null
}
```

### All slot types

**CORRECTED 2026-08-17** — the table below previously capped generic slots at
slot1/slot2 and only listed `init_image_url`. Both were wrong/incomplete. Source:
Graydient's own field list, provided directly by the user — see KI-003 §3 for the
full corrected picture and the caveats on it (not yet job-confirmed which of a
media triplet's fields actually gets populated for a given submission path).

| `local_field` value | What Graydient does at runtime |
|---|---|
| `prompt` / `prompt_positive` | Text string → node widget |
| `negative_prompt` | Text string → node widget |
| `seed` | Integer → node widget |
| `steps` | Integer → node widget |
| `guidance` | Float → node widget |
| `length` | Integer → node widget (frame count) |
| `fps` | Integer → node widget |
| `size`, `cfg`, `controlguidance`, `strength` | premapped fields — use instead of a generic slot when the control genuinely is one of these |
| `slot1` … `slot9` | Generic INT / FLOAT / STRING — **all nine work**, not just slot1/slot2 |
| `init_image_bool` / `init_image_filename` / `init_image_url` (+ `image1`…`image9`) | Media triplet for images. `_url` downloads; `_filename` is a pre-staged local `input/` file; `_bool` flags presence. Map at least `_filename` and `_url` into the node (two widgets, first-non-empty-wins) — don't assume `_url` alone covers every submission path. |
| `init_video_bool` / `init_video_filename` / `init_video_url` (+ `video1`…`video9`) | Same triplet pattern, for video. |
| `init_audio_bool` / `init_audio_filename` / `init_audio_url` (+ `audio1`…`audio9`) | Same triplet pattern, for audio. |

**One-media-type-per-workflow rule**: only ONE media type can come in through the
`init_<type>_*` triplet per job (the Telegram "reply to one attachment" transport). A
workflow needing two different media types must route the second one through the
numbered per-type slots (`image1`, `video1`, `audio1`, …), not by defaulting it to
`init_image_url`. **Known anti-pattern, not yet audited**: several `gen_*.py` scripts
in this project default a secondary media input to `init_image_url` even when that
input is actually video or audio — needs a project-wide pass, not a blanket fix.

### `node_input_index` — widgets only, sockets excluded

`node_input_index` is the **zero-based position of the widget in the node's
`widgets_values` array** in the standard format. Linked input sockets do NOT count
toward this index — only widget values do.

Example: `TripoSGInference` has linked sockets `model` and `image`, then widgets
`seed` (index 0), `steps` (index 1), `cfg` (index 2).

`node_input_name` is the key Graydient uses to patch `workflow_2`'s `inputs` dict.
Both fields must be correct — `node_input_name` is what actually gets applied at
runtime; `node_input_index` is used to patch the standard format's `widgets_values`.

### `slot1` / `slot2` with custom STRING widgets

`slot1` and `slot2` are not restricted to simple text. They can target **any STRING
widget on any custom node**, including:
- **Format selector dropdowns** — e.g. `slot1` → `file_format` on `SaveTrimesh`
  lets users choose `glb`, `stl`, `obj`, etc. at runtime
- **Optional URL fields** — e.g. `slot2` → `back_image_url` on
  `BakeVertexColorsFromViews` lets users supply a back-view photo URL

Graydient passes the string value directly. For enum/dropdown widgets, the value must
match one of the allowed options — the node enforces this at runtime.

### `forceInput: True` on STRING widgets

In a custom node's `INPUT_TYPES`, adding `"forceInput": True` to a STRING input makes
it a **required link socket** rather than a text widget. Omit this flag when the value
will come from Graydient's field mapping — it must arrive as a literal, not a link.

---

## 6. Graydient Environment

### Ephemeral containers

Every run spins a completely fresh container. Nothing persists except `/datapool/`.
Custom nodes are cloned fresh from GitHub on every run via `requirements.github`.
Pip packages are installed fresh every run via `requirements.pip`.

**Correction, confirmed live 2026-08-02**: "fresh every run" is not absolute —
some machines appear to cache a cloned custom-node repo rather than always re-cloning.
Confirmed via `ComfyUI-HiggsV3Glue`: pushed a fix, one machine (`tls-pro-ny4-g4`) picked
it up and ran the new code correctly; a later job on a *different* machine
(`tls-pro-ny2-g0`) ran an older cached checkout from before that push (confirmed by
comparing the exact error message text between the two jobs' logs, not just guessing —
the older job's error was missing a clause only present in the current source). Not
clear what triggers a fresh re-clone vs reusing a cached one (per-machine cache with some
unknown TTL, most likely). **Practical implication**: after pushing a fix to a custom
node repo, don't assume the very next job run has it — if a run doesn't reflect a
recent push, retry rather than assume the push failed; a different machine is likely to
have (or fetch) the current version.

**Implication**: first-run model downloads happen every run unless the model was
pre-staged to `/datapool/`. HuggingFace snapshot_download caches to `~/.cache/huggingface/`
which does NOT persist. Budget time for model downloads on every run.

### DynamicVRAM (`comfy-aimdo`)

Enabled on all Graydient instances. Allows model weights to overflow VRAM into system RAM.

- `"X models unloaded"` in logs = weight eviction to RAM (slow)
- `"loaded completely; full load: True"` = model fully in VRAM (fast)
- `"loaded partially; full load: False"` = weights streaming from RAM (slow)

`peak_vram_usage` in the workflow JSON is **virtual** — it includes both physical VRAM
and DynamicVRAM RAM overflow. A 24 GB 4090 can report `peak_vram_usage: 31036` if
7 GB overflowed to RAM. Setting this value high does NOT route to machines with more
physical VRAM — any machine can reach arbitrary virtual totals via RAM overflow.

### Machine classes (as of 2026-06)

Graydient runs multiple machine class types with **separate filesystems**. Models
downloaded via concept mapping on one class are NOT available on another.

| Class path fragment | GPU | VRAM | RAM |
|---|---|---|---|
| `comfyui_launcher_projects_g0_embedded` | RTX 5090 | 32 GB | ~400+ GB |
| `comfyui_launcher_projects_g1_embedded` | RTX 4090 | 24 GB | ~386 GB |
| `comfyui_launcher_projects_0` | RTX 4090 | 24 GB | ~386 GB |

Machine class appears in the log path:
`/datapool/stablebot/comfyui_launcher_projects_g1_embedded/...`

### Concept mapping

Graydient UI feature to download remote model URLs to the instance's model store.
**Unreliable**: downloads go to the current machine class's filesystem only. A model
downloaded on a g0 class run is missing on g1 class runs. For universal workflows,
use only pre-loaded models or models that auto-download inside the node code.

### Timeout budget

~300 seconds from ComfyUI start. Total budget includes:
- GitHub node clone (~15–30 s per repo)
- Pip install (~10–30 s depending on package count)
- Model download (if not pre-loaded — can consume entire budget for large models)
- Model loading into VRAM (~10–20 s)
- Inference (N steps × T seconds/step)
- VAE decode / encode (~15–35 s for video)

**Target inference ≤ 200 s** to leave headroom. At risk: any configuration that
downloads large models (>5 GB) at run time, or spills >3 GB of activations to
DynamicVRAM RAM.

### pip requirements rules

- Plain package names only — Graydient strips `[]`, `>=`, `<=`, `~=`
  - ✓ `trimesh` — ✗ `trimesh[easy]>=3.0`
- Do NOT re-list these — already in base ComfyUI: `torch`, `torchvision`, `numpy`,
  `Pillow`, `scipy`, `einops`, `huggingface_hub`, `filelock`, `pyyaml`
- `opencv-python` (`cv2`) is listed as base but is **absent in some slot configs** —
  always add it explicitly if a node imports `cv2`
- Compiled CUDA extensions (`.so` files) won't be built automatically — requires
  `ninja` in pip deps and a `setup.py build_ext` call in the custom node's `__init__.py`
- Use `onnxruntime-gpu` on GPU instances; fall back to `onnxruntime` if conflicts arise

---

## 7. VRAM Budget — HunyuanVideo on RTX 4090 (24 GB)

### 7a. Weight memory

| Model | Size | Notes |
|---|---|---|
| FastHunyuan Q8_0 UNET | ~13.4 GB | Pre-loaded on all classes |
| FastHunyuan Q6_K UNET | ~10.5 GB | On most classes |
| FastHunyuan Q4_K_S UNET | ~7.7 GB | On some classes |
| CLIP (clip_l.safetensors) | ~0.5 GB | Universal |
| LLaVA CLIP (Q4_0 GGUF) | ~4.6 GB | Universal |
| HunyuanVideo VAE (bf16) | ~0.5 GB | Universal |

With Q8_0 fully loaded: **13.4 + 5.1 = 18.5 GB** → **5.5 GB headroom** for activations.

### 7b. Activation memory

Transformer attention scratch space. Scales with token count.
Each step needs roughly **0.206 MB per token** in VRAM.

**Token count formula:**
```
h_patches = HEIGHT // 16
w_patches = WIDTH  // 16
t_len     = (FRAMES - 1) // 4 + 1
tokens    = h_patches × w_patches × t_len
```

**HunyuanVideo frame constraint**: `(FRAMES - 1) % 4 == 0`
Valid frame counts: 25, 29, 33, 37, 41, 45, 49, 53, 57, 61, 65, 69, 73, 77, 81, 85,
89, 93, 97, 101, 105, 109, 113, 117, 121, 125, 129

### 7c. Budget tables

**720p (1280×720) — 80×45 = 3600 spatial patches — Q8_0 UNET:**

| Frames | t_len | Tokens | Activation | Overflow | Step time | 6-step total | Status |
|---|---|---|---|---|---|---|---|
| 25 | 7 | 25,200 | 5.2 GB | 0 | ~5–8 s | ~45 s | ✓ default |
| 33 | 9 | 32,400 | 6.7 GB | 1.1 GB | ~10–15 s | ~95 s | ✓ ok |
| 49 | 13 | 46,800 | 9.6 GB | 4.1 GB | ~25–30 s | ~195 s | ⚠ risky |
| 65 | 17 | 61,200 | 12.6 GB | 7.0 GB | ~49 s | ~327 s | ✗ timeout |

**480p (848×480) — 53×30 = 1590 spatial patches — Q8_0 UNET:**

| Frames | t_len | Tokens | Activation | Overflow | Step time | 6-step total | Status |
|---|---|---|---|---|---|---|---|
| 25 | 7 | 11,130 | 2.3 GB | 0 | ~1–2 s | ~20 s | ✓ very fast |
| 65 | 17 | 27,030 | 5.6 GB | ~0 | ~5–7 s | ~55 s | ✓ sweet spot |
| 97 | 25 | 39,750 | 8.2 GB | 2.6 GB | ~15–20 s | ~125 s | ✓ ok |
| 129 | 33 | 52,470 | 10.8 GB | 5.2 GB | ~25–30 s | ~205 s | ⚠ borderline |

**Why 480p/65f is the Graydient default**: sits exactly at the Q8_0 activation
threshold on a 4090 — maximises clip length while staying in budget.

---

## 8. Two-Step 1080p Pipeline Strategy

Native 1080p generation is impossible on a 4090:
- 1080p spatial patches: 120×68 = 8160 (2.27× more than 720p)
- Even at 17 frames: 138,720 tokens → ~28 GB activations → OOM

**Working approach**: generate at lower resolution → GAN upscale.

### 720p → 1080p (short clips / confirmation runs)
```
1280×720 → resize to 960×540 → 4x GAN → 3840×2160 → lanczos → 1920×1080
```

### 480p → 1080p (production-length clips)
```
848×480 → 4x GAN → 3392×1920 → lanczos → 1920×1080
```
GAN model: `4x-ClearRealityV1.pth` (pre-loaded on all classes)

---

## 9. Pre-Loaded Models (No Download Needed)

Available on all Graydient machine classes — safe to reference directly in workflows.

**HunyuanVideo UNET:**
- `fast-hunyuan-video-t2v-720p-Q8_0.gguf` — confirmed universal (Q8, 13.4 GB)
- `fast-hunyuan-video-t2v-720p-Q6_K.gguf` — on most classes (10.5 GB)
- `fast-hunyuan-video-t2v-720p-Q4_K_S.gguf` — on some classes (7.7 GB)

**CLIP:**
- `clip_l.safetensors` — universal
- `llava-llama-3-8b-v1_1.Q4_0.gguf` — universal

**VAE:**
- `hunyuan_video_vae_bf16.safetensors` — universal

**Upscale:**
- `4x-ClearRealityV1.pth` — universal

**Models requiring concept mapping (unreliable across machine classes):**
- `hunyuan_video_accvid_t2v-5-steps_Q8_0.gguf` — AccVid; 14 GB, per-class download
  - URL: `https://huggingface.co/Kijai/HunyuanVideo_comfy/resolve/main/hunyuan_video_accvid_t2v-5-steps_Q8_0.gguf`
  - Dest: `unet/hunyuan_video_accvid_t2v-5-steps_Q8_0.gguf`

---

## 10. FastHunyuan vs AccVid

Both use the HunyuanVideo transformer architecture with GGUF quantisation.

| Property | FastHunyuan | AccVid |
|---|---|---|
| Distillation | FastVideo (flow matching) | Adversarial consistency |
| Steps | 6 (target) | 5 (target) |
| Training res | 1280×720 | 1280×720 |
| Training frames | 25 (native) | 129 |
| Pre-loaded | ✓ universal | ✗ concept mapping only |
| Reliability | ✓ runs first attempt | ✗ machine-class lottery |

Use FastHunyuan for any workflow that must run reliably on any machine. AccVid is
higher quality for long clips but concept mapping fragility makes it unreliable.

---

## 11. SEGA (Spatial/Temporal Extrapolation for AccVid)

Training-free RoPE extrapolation. Allows running AccVid above its training resolution.
Patches `double_blocks` and `pe_embedder` in the transformer to extend positional
encodings beyond training dimensions.

**Nodes** (from `comfyui-sega-hyvideo` custom node):
- `HunyuanVideoSEGAConfig` — sets training reference dimensions and SEGA strength
- `HunyuanVideoSEGAPatch` — applies patch to MODEL before sampling

**Fixed parameters** (always match AccVid training config):
- `training_height=720, training_width=1280, training_t_len=33`
- `temporal_sega_strength=0.0` — disable temporal extrapolation unless doing long clips

**Resolution limits:**
- 1080p SEGA on 4090: OOM regardless of quantisation — 120×68 spatial patches exceed
  4090 headroom even with Q/K/V weight offloading. **1080p SEGA requires RTX 5090.**
- Token count at 1080p/65f on 5090: 120×68×17 = 138,720 → ~28 GB → ~80s/step → timeout
- Safe 5090 config for SEGA: 720p/33–45 frames

---

## 12. Video Workflow Settings

### KSampler for HunyuanVideo distilled models

| Model | Steps | CFG | Sampler | Scheduler |
|---|---|---|---|---|
| FastHunyuan | 6 | 6.0 | euler | sgm_uniform |
| AccVid | 5 | 6.0 | euler | sgm_uniform |
| AccVid + SEGA | 5 | 6.0 | euler | sgm_uniform |

These are step-distilled, not CFG-distilled. CFG=1.0 is valid. Do not use `dpm` or
`dpm++` — they produce noise artifacts with distilled models.

### VAEDecodeTiled

Always use tiled decode for video to avoid VRAM spikes:

```json
{
  "class_type": "VAEDecodeTiled",
  "inputs": {
    "samples":          ["sampler_node_id", 0],
    "vae":              ["vae_loader_node_id", 0],
    "tile_size":        256,
    "overlap":          64,
    "temporal_size":    64,
    "temporal_overlap": 8
  }
}
```

`VAEDecode` (non-tiled) on 65+ frame sequences will OOM on a 4090.

---

## 13. Custom Node Pitfalls

### Name collisions

ComfyUI loads custom node packages alphabetically. A later-loaded package silently
overwrites a `NODE_CLASS_MAPPINGS` key from an earlier one.

- `LoadImageFromURL` (capital R, capital L) ✓ — unique
- `LoadImageFromUrl` (lowercase r) ✗ — collides with `comfyui-art-venture`

Always use globally unique class names. Check that no popular existing node package
uses the same key before publishing.

### VALIDATE_INPUTS and URLs

The built-in `LoadImage` node has `VALIDATE_INPUTS` which checks that the file path
physically exists on disk. **Never pass a URL to `LoadImage`** — it will fail
validation before the node even runs. Use `LoadImageFromURL` (custom node) instead.

### VHS_LoadVideoUpload and URLs

`VHS_LoadVideoUpload` expects a local file path. When Graydient passes `init_image_url`
to it, the URL is written to the local path field. VideoHelperSuite handles URLs natively
via its `video` input — verify this works with the VHS version on the target Graydient
instance before relying on it.

### PrimitiveNode in API format

`PrimitiveNode` is a UI convenience node. It must NEVER appear in `workflow_2` as a
`class_type`. It causes a `missing_node_type` error. Replace all PrimitiveNode usage
with direct widget values in the API JSON, and expose them via `field_mapping`.

### Execution order is topology, not `order` field

ComfyUI determines execution order from **graph topology** (topological sort). The
`order` field in standard JSON is a UI display hint only. Nodes with no inputs run at
depth 0 before nodes with inputs. If two heavy model loaders have no dependencies,
they load simultaneously and can OOM. Fix: add a data dependency to defer one.

### Dot-namespaced class names

Some custom node packages use dot-namespaced type strings like `huchenlei.LoadOpenposeJSON`.
Graydient's workflow-to-API converter may null out the `class_type` for these at upload
time. Avoid dot-namespaced type strings in any node you want to use through Graydient.

### ComfyUI-OpenClaw IMPORT FAILED

Graydient's own infrastructure node logs `Security Gate FAILED` when `--listen` is set
without the `OPENCLAW_ADMIN_TOKEN` env var. This is not your workflow's fault — ComfyUI
continues booting. Ignore this log line.

---

## 14. Required GitHub Repos by Workflow Type

| Workflow type | `requirements.github` entries |
|---|---|
| FastHunyuan video | `city96/ComfyUI-GGUF`, `Kosinkadink/ComfyUI-VideoHelperSuite` |
| AccVid (no SEGA) | `city96/ComfyUI-GGUF`, `Kosinkadink/ComfyUI-VideoHelperSuite` |
| AccVid + SEGA | `city96/ComfyUI-GGUF`, `Kosinkadink/ComfyUI-VideoHelperSuite`, SEGA repo |
| Video upscale | `Kosinkadink/ComfyUI-VideoHelperSuite` |
| 3D mesh (TripoSG) | `UnlimitedEditing/ComfyUI-TripoSG` |
| 3D mesh + smuggle | `UnlimitedEditing/ComfyUI-TripoSG`, `UnlimitedEditing/Meshsmuggler` |

---

## 15. 3D Mesh Pipeline — TripoSG

All custom nodes live in `UnlimitedEditing/ComfyUI-TripoSG`.
Meshsmuggler (optional exfiltration) lives in `UnlimitedEditing/Meshsmuggler`.

### Standard pipeline

```
LoadImageFromURL
  → TripoSGPrepareImage           (crop, remove background, pad 10%, square)
      → TripoSGInference          (diffusion → raw TRIMESH)
          → BakeVertexColorsFromViews    (project photo colours onto vertices)
              → SaveTrimesh       (write file, return path string(s))
```

For smuggling output back to the client as a PNG image:
```
SaveTrimesh → MeshSmuggleGate → SmuggleMeshAsImage
```

The prepared image **feeds both inference and baking** — pass the same `TripoSGPrepareImage`
output to both `TripoSGInference.image` and `BakeVertexColorsFromViews.front_image` so the
UV projection math matches exactly what the model saw.

### Full node reference

| class_type | Key inputs / widgets | Notes |
|---|---|---|
| `LoadImageFromURL` | `url` (STRING widget) | No `VALIDATE_INPUTS` — the only safe way to pass a URL as an image input on Graydient |
| `TripoSGModelLoader` | `model` dropdown | `VAST-AI/TripoSG`, `VAST-AI/TripoSG-scribble`, `wgsxm/PartCrafter` — downloads ~10 GB on first use; no pre-staging available |
| `TripoSGPrepareImage` | `image` (IMAGE), optional `mask` | Crops to subject bounding box, alpha-extracts or white-bg-removes, adds 10% padding on all sides, squares to the dominant dimension. pad_ratio=0.1 is used in the bake UV calculation — changing this breaks baking. |
| `TripoSGInference` | `model`, `image`, `seed`, `steps`, `cfg`; optional `conditioning` | Outputs `trimesh` (combined mesh) + `parts` (list). Single-image only — passing a list creates a batch, NOT multi-view conditioning. |
| `TripoSGConditioning` | `prompt`, `prompt_confidence`, `scribble_confidence` | For TripoSG-scribble model. CFG-distilled: `guidance_scale=0` is hardcoded in the pipeline regardless of the `cfg` widget. |
| `PartCrafterConditioning` | `num_parts`, `num_tokens`, `max_num_expanded_coords` | For PartCrafter multi-part decomposition model. |
| `BakeVertexColorsFromViews` | `trimesh`, `front_image`, `cam_dist`, `back_image_url`; optional `back_image` | See §15a. |
| `SaveTrimesh` | `trimesh`, `filename_prefix`, `file_format`, `also_save`, `save_file` | See §15b. |
| `SimplifyMesh` | `mesh` (MESH), `faces` (INT) | pymeshlab quadric edge collapse decimation. `faces=0` = no simplification. |
| `TrimeshToMESH` | `trimesh` (TRIMESH) | Converts TRIMESH object → ComfyUI native MESH type (vertices + faces as torch tensors). |
| `MESHToTrimesh` | `mesh` (MESH) | Converts ComfyUI MESH → trimesh.Trimesh object. |
| `MeshSmuggleGate` | `glb_path` (STRING in), `enable` (INT widget) | `enable=0` passes path through unchanged; `enable=1` activates encoding. Map Graydient `slot1` → `enable` to let users toggle. |
| `SmuggleMeshAsImage` | `glb_path`, `filename_prefix`, `save_file`, `max_size` | Encodes GLB binary → PNG pixel data (M3DS container, gzip-compressed + CRC32 checksum). Output PNG looks like noise but contains the complete mesh. |

### 15a. BakeVertexColorsFromViews — details

Projects the source photograph onto mesh vertices using perspective-correct UV
mapping that replicates the 10% padding applied by `TripoSGPrepareImage`. Front
and back projections are blended by the vertex normal Z component:
- nz = +1 → fully front image
- nz = -1 → fully back image
- sides get a smooth blend

**Back image resolution priority** (highest wins):
1. Wired `back_image` socket — an IMAGE tensor linked from another node
2. `back_image_url` STRING widget — URL fetched via `requests` at runtime if non-empty
3. Fallback — horizontally mirrored copy of the front image (default)

**`cam_dist` widget** (default 2.5) — virtual camera distance along +Z for perspective
correction. Increase if texture is zoomed too tightly on mesh edges; decrease if
stretched. TripoSG training camera is approximately 2.0–3.5.

**Graydient field mapping for back view**: map `slot2` → `back_image_url`
(`node_input_index: 1`, `node_input_name: "back_image_url"`). Empty string →
mirrors front. Users paste a back-view URL to enable full front+back baking.

**Caveat**: back-view baking is approximate. Quality depends on how well the photo
geometry matches the reconstructed mesh. Results will be hit-and-miss on anything
other than simple symmetric objects. A dedicated mesh painter workflow is the correct
long-term solution.

### 15b. SaveTrimesh — dual-format output

```python
RETURN_TYPES  = ("STRING", "STRING")
RETURN_NAMES  = ("file_path", "also_path")
```

- `file_format` dropdown — primary export format (glb, obj, ply, stl, 3mf, dae)
- `also_save` optional — saves a second format simultaneously; `"none"` to disable
- If `also_save == file_format`, the second write is skipped and `also_path` returns `""`
- Both files share the same counter suffix so they are clearly paired

**Graydient field mapping for format selection**: map `slot1` → `file_format`
(`node_input_index: 1`, `node_input_name: "file_format"`) with `default_value: "glb"`.
Include a `help_text` listing all six formats and their use cases.

### 15c. Meshsmuggler — GLB steganography

`SmuggleMeshAsImage` reads a GLB file and encodes the binary data as pixel values in
a PNG using the **M3DS container format**: gzip-compressed GLB binary with dual CRC32
checksums (per chunk + final). The output image looks like noise but is a valid PNG
containing the complete mesh.

**Decoding**: open `unsmuggle.html` in a browser — drag the PNG in; it decodes the
mesh and displays it in a Three.js viewer with a download button for the original GLB.

### 15d. pip requirements for TripoSG workflows

```
diffusers
transformers
accelerate
safetensors
trimesh
omegaconf
scikit-image
peft
jaxtyping
typeguard
pymeshlab
opencv-python
ninja
```

---

## 16. 3D Export Format Reference

### Formats working natively via trimesh (no extra dependencies)

| Format | Extension | Vertex colours | Animation/rigging | Primary use case |
|---|---|---|---|---|
| GLB | `.glb` | ✓ | ✓ | Games, web, Android AR, Blender import — **recommended default** |
| OBJ | `.obj` | via MTL sidecar | ✗ | Universal 3D software compatibility |
| PLY | `.ply` | ✓ | ✗ | Research, scanning, point-cloud workflows |
| STL | `.stl` | ✗ | ✗ | 3D printing — geometry only, no colour |
| 3MF | `.3mf` | ✓ (slicer-dependent) | ✗ | Modern 3D printing — PrusaSlicer, Bambu, Orca Slicer |
| DAE | `.dae` | ✓ | ✓ | Animation/rigging exchange — Blender, Maya, Cinema4D |

### Not feasible on ephemeral Graydient instances

| Format | Reason |
|---|---|
| FBX | Requires Autodesk proprietary SDK or `pyassimp` (Linux shared-library dependency hell) |
| USDZ | Requires Pixar's OpenUSD library (~500 MB install) |
| STP / STEP | Requires OpenCASCADE via `pythonOCC` or `cadquery` (~600 MB) |
| IGES | Same OpenCASCADE dependency as STEP |
| BLEND | Requires a running Blender instance — impossible as a pure Python library |

### Practical guidance

- Use **GLB** for everything going into a game engine, Blender, or web viewer
- Use **STL** for 3D printing when colour is irrelevant; **3MF** if colour matters
- Use **DAE** when the downstream tool is Maya, Cinema4D, or needs rigging slots
- GLB is also the correct input format for the Meshsmuggler pipeline
- Vertex colours baked by `BakeVertexColorsFromViews` are preserved in GLB, PLY, and DAE;
  silently dropped in STL

---

## 17. Debugging Checklist

**`Failed to validate prompt for output N: * <NodeClass> <id>: Required input is missing: <name>`**
→ A `"required"` `INPUT_TYPES` entry was added to an existing, already-in-use node
without also re-uploading every workflow that uses it. Confirmed live 2026-08-02
(`ComfyUI-HiggsV3Glue`'s `HiggsV3VoicePreset`, adding `require_clone_source`): ComfyUI's
prompt validation demands every `"required"` input be **explicitly present in the
submitted API JSON**, regardless of whether the node's Python function has a default
value for that parameter — a Python-level default does **not** provide backward
compatibility on its own the way you'd expect. **Fix**: put a new input under
`"optional"` instead of `"required"` if you need already-uploaded/stored workflows
(whose `workflow_2` JSON predates the new key) to keep working without a restore — only
`"optional"` inputs skip this presence check, and the Python default still applies when
the key is genuinely absent from the submitted `inputs` dict.

**`WorkflowInstallStuckException: <job> stuck in download_comfyui > 1800s`, `"created": false`, `"inner_port": null`, `"peak_vram_usage": 0.0`, traceback is pure `utils_comfyui.py` recursion (`find_project`/`start_project` calling each other repeatedly)**
→ Not a bug in your workflow. This is Graydient's own platform-side orchestration
getting stuck provisioning the ComfyUI environment itself, before your workflow's
custom nodes, pip deps, or ComfyUI startup logs even appear — confirmed live
2026-07-29 (`tls-pro-ny4-g2`): all `concept_mapping` assets showed `"fetched"`/`"exists"`
(the download stage completed fine) but ComfyUI itself never launched. Check
`inner_port`/`peak_vram_usage` — if both are null/0 and the traceback is entirely inside
Graydient's own `utils_comfyui.py` with no mention of your custom nodes, it's platform
infrastructure, not your config. **Fix: just retry** — a fresh run gets a different
server. If it recurs repeatedly on the same machine class, that's worth flagging to
Graydient support rather than continuing to debug workflow config.

**`init_image`/`init_audio`/`init_video` field value looks mangled — all `:`/`/`/`_`
stripped out, doesn't start with `http://`/`https://`, e.g.
`init_audio__httpsapi.telegram.orgfilebot...oga`**
→ Confirmed live 2026-08-01 (Higgs TTS workflow, a Telegram voice-message reply): the
submitting client passed a raw/internal file reference (an un-uploaded Telegram
attachment) instead of a real public URL. **Graydient has no upload endpoint of its
own** (confirmed via `graydient-cli`'s docs — any local file must be uploaded to a real
public URL *before* being passed as `init_image`/`init_audio`/`init_video`; the CLI's
own `--init-*` flags do this automatically via `resolveMediaInput()`/`graydient upload`).
This mangled-looking value is what happens when whatever bot/frontend layer sits between
the attachment and Graydient skips that upload step — not a bug in the receiving ComfyUI
node. The proper fix is still upstream (the submitting client should upload the
attachment and pass a real URL), but **for Telegram specifically this is narrowly
reconstructable**: Telegram Bot API file URLs follow a fixed shape
(`https://api.telegram.org/file/bot<id>:<secret>/<kind>/file_<n>.<ext>`), so the mangled
string can be regex-reconstructed back into a real fetchable URL — see
`_unmangle_telegram_file_url()` in `ComfyUI-HiggsV3Glue/nodes.py` for the implementation
and its test cases. Anchor the secret-token capture on Telegram's known attachment-type
words (`voice`/`photo`/`video`/etc., non-greedy match), **not a fixed character length**
— bot secret length isn't reliably 35 chars as commonly assumed (a real confirmed example
was 34), so a length-bounded or greedy match mis-splits the string. This reconstruction
is deliberately narrow — it only recognizes this one known URL shape, not a general
"guess any mangled URL" heuristic, since the mangling is lossy and unrecoverable for
arbitrary URLs. For any *other* mangled `init_*` value that doesn't match this pattern,
the node still fails with a clear "not a valid URL" error instead of a raw `urllib`
traceback.

**`"node X has no class_type"`**
→ Standard format submitted as `workflow_2`. Check that `workflow_2` uses `class_type`,
not `type`, and that nodes are keyed by string ID.

**`missing_node_type: PrimitiveNode`**
→ PrimitiveNode included in `workflow_2`. Remove it; use direct widget values + field_mapping.

**Model not found / ValidationError on model name**
→ Model needs concept mapping, or was downloaded on a different machine class.
→ Switch to a pre-loaded model, or have the node auto-download via `snapshot_download`.

**`Failed to create AudioDecoder for <path>: _AudioDecoder() takes no arguments`**
→ `torchaudio.load()` on recent torchaudio versions routes through torchcodec's
`AudioDecoder`, which is broken on at least some Graydient instances (confirmed live,
`comfyui_launcher_projects_g1_embedded`, RTX 4090, 2026-07-29) — the installed
torchcodec's `AudioDecoder.__init__` doesn't accept the argument torchaudio passes it.
Some node packs try to work around this at import time by stubbing
`sys.modules["torchcodec"]` (see `Higgs_v3-TTS-ComfyUI/__init__.py`'s
`_block_broken_torchcodec()`), but that guard only fires if torchcodec wasn't already
imported by something else first — unreliable, don't depend on another package's stub
protecting your own `torchaudio.load()` call. Recent torchaudio also dropped the old
multi-backend dispatch (no more reliable `backend="ffmpeg"`/`"soundfile"` kwarg fallback).
**Fix**: don't call `torchaudio.load()` for anything that must work reliably on
Graydient — decode via a direct `ffmpeg` subprocess instead (ffmpeg is already a hard
dependency of this project's video pipelines, so it's a safe thing to shell out to):
```python
proc = subprocess.run(
    ["ffmpeg", "-v", "error", "-i", path, "-f", "s16le", "-acodec", "pcm_s16le",
     "-ar", str(sample_rate), "-ac", "1", "-"],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
)
arr = np.frombuffer(proc.stdout, dtype="<i2").astype("float32") / 32768.0
waveform = torch.from_numpy(arr.copy()).unsqueeze(0)  # [channels=1, samples]
```
Use raw PCM (`-f s16le`), not `-f wav`, on a piped subprocess — ffmpeg can't know the
final size upfront when writing to a pipe, so it writes a WAV header with a placeholder
max-int frame count, and Python's `wave` module trusts that header blindly, reporting a
bogus multi-hour duration. Raw PCM has no header to get wrong. See
`UnlimitedEditing/ComfyUI-HiggsV3Glue`'s `_decode_audio_via_ffmpeg()` for the full
working version (tested end-to-end against a real file before shipping, then confirmed
on an actual Graydient run).

**A `requirements.github` node runs different code than what's in its GitHub repo /
`expected value at line 1 column 1` parsing a `tokenizer.json` or similar config file**
→ New variant of the name-collision pitfall above, confirmed live 2026-07-29
(`tls-pro-ny1-g0`): a **second copy of the same node pack got installed under a
different folder name** than the one we specified — we listed
`https://github.com/Saganaki22/Higgs_v3-TTS-ComfyUI` (underscore) in
`requirements.github`, expecting `custom_nodes/Higgs_v3-TTS-ComfyUI/`, but the actual
traceback showed execution happening in `custom_nodes/Higgs-V3-TTS-ComfyUI/` (hyphenated,
capital V) — a folder we never asked for. Both printed `Registered 5 node(s).` at
startup (i.e. both successfully claimed the same `NODE_CLASS_MAPPINGS` keys); whichever
one ComfyUI's loader processed last for a given key is the one that actually runs.
The extra copy's code was **stale relative to current upstream** — it still pointed an
"(auto-download)" default at a wrong/broken HF repo id that current upstream had already
fixed. Root cause not fully confirmed, but the leading suspect is ComfyUI-Manager's own
node registry independently resolving and installing the "same" package under its
registry-normalized slug, in parallel with our explicit git clone — this can apparently
happen even with `install_detected_nodes: False` in the workflow config (that flag only
governs auto-installing *missing pip deps* for detected-but-uninstalled nodes, not a
registry-triggered second install of the node itself).
→ **Don't trust a node's own "(auto-download)" / repo-id default if you have any
say over it** — it's pinned inside whichever copy of the code happens to run, which you
don't fully control. Prefer pointing the node at a `concept_mapping`-staged **local
path/folder name** instead, if the node supports local-model selection (most model-loader
nodes do, since it's needed for offline/pre-staged use anyway) — this sidesteps the
auto-download codepath (and whichever copy of the node's code ends up executing)
entirely, since local-folder-loading logic is far less likely to have drifted between a
stale mirror and current upstream than a hardcoded remote repo id is.

**`TypeError: int() argument must be a string, a bytes-like object or a real number, not
'NoneType'` inside `comfy_aimdo`/`ModelVBAR`/`control.get_devctx(int(device_id))`**
→ Confirmed live 2026-07-29 (`tls-pro-ny4-g3`): weights had already loaded successfully
(this fires during **DynamicVRAM registration**, a step after the weights are in memory,
not a weight-loading failure). Root cause: a node's `device` widget was set to the
literal string `"cuda"`, which most nodes resolve via plain `torch.device("cuda")` — that
constructs a device with `.index == None` (no explicit GPU index). Graydient's own
`comfy_aimdo` DynamicVRAM wrapper (`ModelVBAR`) needs a real integer device index and
crashes on `int(None)`. The literal `"cpu"` option is unaffected (this only bites
CUDA-loading nodes using DynamicVRAM). **Fix**: use `"auto"` instead of `"cuda"` if the
node offers it — `"auto"` typically resolves via
`comfy.model_management.get_torch_device()`, which constructs
`torch.device(torch.cuda.current_device())` and **does** carry an explicit index. If a
node only offers a bare device string with no "auto", explicitly use `"cuda:0"` instead
of `"cuda"` where the node's widget allows arbitrary text.

**OOM at step 1 of KSampler**
→ Activation overflow — reduce resolution or frame count (see §7c).
→ At 1080p on 4090: structurally impossible regardless of quantisation.

**Step time ~40–50 s, timeout at step 2–3**
→ DynamicVRAM activation overflow — see §7c budget table.
→ Fix: reduce frames (720p: 25–33 frames), or switch to 480p for longer clips.

**`"X models unloaded"` in logs, very slow steps**
→ Weight offloading: model too large for available VRAM plus activation headroom.
→ Fix: use a smaller quantisation (Q6_K or Q4_K_S if available on that class).

**`peak_vram_usage` > physical VRAM (e.g. 31036 on a 24 GB card)**
→ Normal — virtual total (physical + DynamicVRAM overflow). Not a routing signal.

**Concept mapping model available one run, missing the next**
→ Machine class fragmentation. Different runs land on different hardware pools.
→ Download only persisted on the class from the first run.
→ Only fix: use pre-loaded models or accept non-deterministic availability.

**Timeout at ~492 s with fast model**
→ Too many tokens. Check frame count. 5090 at 1080p/129f ≈ 400–500 s for diffusion alone.

**`torch.OutOfMemoryError` + 10 MB CUDA free on fresh server**
→ `cudaMallocAsync` pool retained from a prior run on the same server, OR two heavy
model loaders at dependency depth 0 running simultaneously.
→ Re-run (gets a fresh server); or add a data dependency to serialise model loading.

**`No module named 'custom_rasterizer'`**
→ A CUDA-compiled rasterizer extension wasn't built. Add `ninja` to pip deps and a
`setup.py build_ext` call in the custom node's `__init__.py`.

**`ComfyUI-OpenClaw` IMPORT FAILED — Security Gate FAILED**
→ Graydient infrastructure node; not your workflow's fault. ComfyUI continues booting.
Ignore this log line — it does not affect workflow execution.

**Workflow logs from a completely different pipeline**
→ A previous workflow in a different slot ran on the same server. Check job ID in the
log path to confirm you're looking at the right run.

**3D: TripoSG model download times out**
→ The ~10 GB model downloads fresh every run (no pre-staging available). On slow
instances this can exhaust the 300 s budget. Cold runs may need to be retried.

**3D: Vertex colours missing from exported file**
→ STL does not store colour. Use GLB, PLY, or 3MF if colours must be preserved.

**3D: Back-view bake looks smeared or misaligned**
→ Projection math assumes the same 10% padding as `TripoSGPrepareImage`. A back image
that was not cropped and padded identically will misalign. Results are always approximate.

**3D: `also_path` output is empty string**
→ `also_save` is skipped when it equals `file_format`. Set them to different values.

---

## 18. Active Workflow Inventory

Every `gen_*.py` in `D:\tripostl\` as of 2026-07-29, grouped by pipeline family. Pulled
directly from each script's `DESCRIPTION` string and `requirements.github`, not guessed
— where a family isn't detailed elsewhere in this doc, that's flagged explicitly rather
than fabricated. Read the script itself for full node graph / field_mapping detail.

### 3D mesh (TripoSG / PartCrafter / Meshsmuggler) — see §15

| Script | Output | Purpose |
|---|---|---|
| `gen_stl.py` | `GraydientWorkflow-triposg-stl-v17.json` | img→mesh, vertex bake, slot1=format, slot2=back URL, STL+GLB dual output |
| `gen_v10.py` | `GraydientWorkflow-meshmuggler-v10.json` | photo→mesh→vertex bake→smuggle |
| `gen_scribble.py` | `GraydientWorkflow-triposg-scribble-v1.json` | sketch+prompt→mesh→smuggle |

### Hunyuan3D (separate repo, kept out of ComfyUI-TripoSG by design)

| Script | Repos | Purpose |
|---|---|---|
| `gen_hunyuan3d_mv.py` | `UnlimitedEditing/ComfyUI-Hunyuan3D` | multi-view textured mesh generation, mesh smuggling output |
| `gen_hy3d_paint_wheelbuilder.py` | `UnlimitedEditing/ComfyUI-Hunyuan3D`, `kijai/ComfyUI-Hunyuan3DWrapper`, `UnlimitedEditing/Meshsmuggler` | **One-shot setup job, not a content pipeline**: builds Linux/CUDA wheels for `ComfyUI-Hunyuan3DWrapper`'s `custom_rasterizer` and `differentiable_renderer` native extensions on a Graydient GPU instance (upstream only ships Windows prebuilt wheels), then smuggles the resulting wheel(s) out as PNG via Meshsmuggler. Run once to harvest wheels for reuse in other Hunyuan3D-paint workflows, not per-job. |

### MeshScript / CanvasScript (procedural modeling IR — see [[project-meshscript-vision]] memory)

| Script | Repos | Purpose |
|---|---|---|
| `gen_meshscript_txt2mesh_v1.py`, `gen_meshscript_txt2mesh_ir_v1.py` | `UnlimitedEditing/ComfyUI-MeshScript`, `UnlimitedEditing/meshscript` | text → procedural 3D mesh via the MeshScript op-library DSL; `_ir_` variant uses schema-constrained IR generation (xgrammar-enforced JSON) rather than free-form DSL text |
| `gen_meshscript_mesh2mesh_v1.py` | same | mesh-conditioned procedural editing |
| `gen_canvasscript_txt2doc_ir_v1.py` | same | **2D sibling of MeshScript** — text → 2D document via a CanvasScript IR path: Qwen2.5-Coder-7B emits a schema-constrained JSON IR (every op/argument/`$ref` enforced token-by-token via xgrammar) that a separate renderer executes. Not yet documented elsewhere — read the script for the op vocabulary. |

### Video

| Script | Repos | Purpose |
|---|---|---|
| `gen_bernini_v1.py` | see §5/§14 | Bernini (Wan2.2 14B cascade) video-to-video, 432×240/81f |
| `gen_dreamx_sequence_v1.py` | `AMAP-ML/DreamX-World`, `UnlimitedEditing/ComfyUI-DreamX-World`, `Kosinkadink/ComfyUI-VideoHelperSuite`, `UnlimitedEditing/ComfyUI-TripoSG` | Camera-controlled world navigation from a single photo — image + scene description + a sequence of camera moves; the model generates continuous video exploring the scene, one chunk per move (25 latent frames ≈ 6s @16fps default), last frame of each chunk conditions the next for continuity. New pipeline, not previously in this doc. |
| `gen_bg_camera_v1.py` | `UnlimitedEditing/ComfyUI-TripoSG` | Moving-background-from-still-image using Wan2.2 Fun Camera Control (14B fp8, lightx2v 4-step distilled) — stand-in for PixWorld until its code/weights ship. Produces a short MP4 with real pan/zoom/rotate camera movement over a still, for layer-based 2D animation kits where a plain image-to-video render isn't enough. |

### TTS (audio) — see §20 below for node reference, not previously documented here

| Script | Output | Purpose |
|---|---|---|
| `gen_misotts_v1.py`, `gen_misotts_v2.py` | `GraydientWorkflow-misotts-v{1,2}.json` | earlier MisoTTS iterations, superseded by v3 |
| `gen_misotts_v3.py` | `GraydientWorkflow-misotts-v3.json` | current MisoTTS: text→speech, slot1=speaker (0=friend/1=teacher/2=voiceover), ~22GB peak VRAM |
| `gen_misotts_voiceclone_v1.py` | `GraydientWorkflow-misotts-voiceclone-v1.json` | MisoTTS with reference-audio voice cloning |
| `gen_higgs_v1.py` | `GraydientWorkflow-higgs-v3-tts-v1.json` | Superseded by v2 — kept for reference. Spliced emotion/style into a text prefix via slot1/slot2, which broke inline tag placement (see v2 note). |
| `gen_higgs_v2.py` | `GraydientWorkflow-higgs-v3-tts-v2.json` | Higgs Audio v3 (4B) TTS via `Saganaki22/Higgs_v3-TTS-ComfyUI` + `UnlimitedEditing/ComfyUI-HiggsV3Glue`. `prompt_positive` (not `prompt` — that local_field never works for this workflow, root-caused via `graydient-cli`, see §20) carries everything: plain speech, or `emotion:sad,style:whispering::speech` (the confirmed-working `tags::speech` marker — `negative_prompt` and `[...]` bracket syntax are both confirmed dead ends). slot1=voice preset (jake/chloe/eleanor/marcus/nora/oliver), `init_audio`=custom voice-clone URL (overrides slot1), auto-transcribed reference text via `HiggsV3WhisperTranscribe`. Both glue nodes log resolved inputs/outputs to the console. ~11-14GB VRAM, built 2026-07-29. **Full pipeline (text/tags/voice preset/voice cloning) confirmed working end-to-end via real Graydient renders 2026-08-02.** See §20. |

### Music-video generation pipeline (chained jobs — not previously documented here)

A multi-stage pipeline that turns an audio file into a structured music-video concept.
Each stage's output image is decoded by **ForgeExpress** (see §19) and fed as input to
the next stage — this is a cross-job orchestration pattern, not a single workflow.

```
gen_whisper.py        audio URL → timed lyrics (faster-whisper large-v3), lyrics card image
gen_music_analyze.py   audio URL → BPM/energy timeline/beat timestamps/section boundaries,
                        annotated mel spectrogram + data image
gen_lyric_concept.py   audio URL → lyrics + concept JSON in ONE job (whisper + Qwen2.5 LLM
                        combined) — three images out: lyrics card, concept_data, concept_card
gen_lyric_concept_v2.py  timed-lyrics JSON in (from gen_whisper.py) → concept JSON via
                        Qwen2.5-Coder LLM — concept_data + concept_card images
gen_lyric_scene_gen.py  combined {"lyrics": ..., "energy": ...} JSON in (whisper + music-analyze
                        outputs merged) → energy-aware scene concept generation
```

`gen_lyric_concept.py` (one-shot) and the `gen_whisper.py` → `gen_lyric_concept_v2.py` /
`gen_music_analyze.py` → `gen_lyric_scene_gen.py` (chained) paths appear to be two
different iterations of the same goal — check which is the current production path
before building on either; not resolved as of this doc.

### Puppet Studio character rigging (SAM3 segmentation — not previously documented here)

| Script | Repos | Purpose |
|---|---|---|
| `gen_character_body_segment.py` | `1038lab/ComfyUI-RMBG`, `UnlimitedEditing/ComfyUI-TripoSG` | Segments one named body region (e.g. "head", "torso", "left arm") out of a flat 2D character illustration using SAM3 text-prompted segmentation → RGBA cutout, everything outside the region made transparent, rest of image/colours/resolution untouched. Call once per body part for independent rig layers. |
| `gen_character_face_segment.py` | same | Same pattern, tuned tighter for small facial features (lower confidence threshold — SAM3 is less confident on small regions than large flat-coloured ones) |

### General-purpose LLM / VLM utility workflows (ForgeExpress pattern — see §19)

| Script | Purpose |
|---|---|
| `gen_llm.py` | General text LLM inference (default Qwen/Qwen2.5-7B-Instruct — strong structured JSON output) |
| `gen_vlm.py` | General multimodal inference (Qwen2.5-VL) — image URL + text prompt in, response + data image out |

### Cosmos3 (NVIDIA Cosmos3-Nano, 16B omnimodal world model)

| Script | Modality | Status |
|---|---|---|
| `gen_cosmos3_t2i.py` | text→image | ✅ working, confirmed (see §21 for prior VRAM/timing notes) |
| `gen_cosmos3_i2i.py` | image→image editing | Present in repo — status not re-confirmed since build; the memory this doc was assembled from (51 days stale as of 2026-07-29) called T2V/I2V "deferred" but scripts for **all four** modalities now exist. Treat that "deferred" note as outdated — verify current status against Graydient's actual run history, not this doc, before assuming any of the four works first try. |
| `gen_cosmos3_t2v.py` | text→video | Present in repo, same caveat |
| `gen_cosmos3_i2v.py` | image→video | Present in repo, same caveat |

---

## 19. The ForgeExpress pixel-data-image convention

A second data-exfiltration pattern alongside Meshsmuggler (§15c), used by the
LLM/VLM/whisper/lyric/music-analyze family (§18). Distinct mechanism, same underlying
problem: Graydient jobs return **images**, so returning arbitrary structured data (JSON,
transcripts, analysis results) means encoding it as pixels.

- Meshsmuggler (§15c) encodes **binary** GLB data via a custom gzip+CRC32 M3DS container
  read by a bespoke `unsmuggle.html` decoder.
- The LLM/VLM/whisper/lyric family instead produces a **"data image"**: UTF-8 JSON bytes
  written directly into RGB pixel values, losslessly, decoded by **ForgeExpress** (an
  external tool/service referenced by these scripts — not itself part of this repo).
  Several of these workflows also emit a second, human-readable **"card" image**
  (e.g. `concept_card`, lyrics card) purely for visual review, alongside the
  machine-readable data image.

**Chaining pattern**: several of these jobs are designed to feed each other — one job's
data-image output becomes JSON that's merged with another job's output and passed as the
next job's `prompt` field (see the music-video pipeline in §18). This is Graydient-level
job orchestration external to any single workflow JSON — nothing in `field_mapping` or
`concept_mapping` describes it; it happens in whatever calls these jobs in sequence.

**Not yet documented in this file**: the exact pixel-encoding scheme (bytes-per-pixel,
row-major vs other ordering, any length header) — read `gen_llm.py`'s SaveImage/encode
node for the ground truth before building a new workflow that needs to interoperate with
ForgeExpress-decoded data.

---

## 20. TTS Pipelines — Node Reference

Not covered in §1–17 (audio TTS was added to this project after this file's original
17 sections were written). Two independent TTS pipelines exist; neither depends on the
other.

### Chat frontend eats bare `<` / `>` — escape them, any tag-based workflow

Confirmed live 2026-07-29: any inline control-tag syntax using `<...>` (Higgs v3's
`<|emotion:x|>`, an OVI/Wan22 workflow's `<S>...<E>` speech tags, etc.) gets silently
mangled by whatever Telegram/Graydient chat frontend is used to submit these jobs —
bare angle brackets are treated as the frontend's own markup and stripped before the
text reaches the workflow's `prompt` field. Symptom: the tag doesn't error, it just gets
read out loud as literal leftover text (e.g. Higgs speaking the words *"emotion sad"*
instead of applying a sad emotion) — easy to misdiagnose as "the model is ignoring my
tags" when the model never saw the real tag at all. **Fix**: escape with a backslash
immediately before each `<` and `>`, confirmed working pattern from an OVI/Wan22
workflow: `\<S\>text\<E\>`. For Higgs tags this means `\<|emotion:sad|\>` rather than
`<|emotion:sad|>`. This is a frontend-layer issue, not something fixable in the
workflow JSON/`field_mapping` itself — applies to any tag-heavy workflow used through
that same chat interface.

### MisoTTS (`UnlimitedEditing/ComfyUI-MisoTTS`, wraps `MisoLabs/MisoTTS` 8B)

```
MisoTTSModelLoader → MisoTTSGenerate → SaveAudio
```

| class_type | Key inputs/widgets | Notes |
|---|---|---|
| `MisoTTSModelLoader` | `model_repo` (STRING, default `MisoLabs/MisoTTS`) | ~22GB peak VRAM (measured) |
| `MisoTTSGenerate` | `text`, `speaker` (INT 0-2), `max_audio_length_ms`; optional `context_audio` (AUDIO, for cloning) | speaker: 0=friend (warm/conversational), 1=teacher (clear/instructional), 2=voiceover (professional). English only. |
| `LoadAudioFromURL` | `url` (STRING) | Downloads audio from URL → AUDIO tensor, no `VALIDATE_INPUTS` gate — same pattern as `LoadImageFromURL` |

pip: `moshi==0.2.2`, `bitsandbytes==0.45.5`, `silentcipher==1.0.5`,
`git+https://github.com/UnlimitedEditing/MisoTTS.git`. Field mapping: `prompt`→text,
`slot1`→speaker.

### Higgs Audio v3 (`Saganaki22/Higgs_v3-TTS-ComfyUI` + `UnlimitedEditing/ComfyUI-HiggsV3Glue`)

Built 2026-07-29, revised to v2 same day — see [[feedback-search-before-building-nodes]]
for *why* this uses a third-party node instead of a custom wrapper (an in-depth detour
into a vllm-omni server architecture was investigated and correctly abandoned once the
existing plain-`transformers` node was found).

**v1 → v2 design correction**: v1 spliced `slot1`/`slot2` (emotion/style) into the text
as a fixed prefix via a `HiggsV3TagBuilder` glue node. That's wrong — Higgs v3's tags are
designed to go *anywhere* inline (e.g. `<|sfx:laughter|>` at the exact word it should
land on; the upstream node's own tooltip says as much), and prefix-splicing strips that
placement ability. v2 (first cut) fixed this by mapping `prompt` directly to
`HiggsV3VoiceClone.text` as a plain literal widget. **That later turned out to be
insufficient** — see the chat-frontend tag-mangling note below; the graph has since been
revised again within v2 to route tags through `negative_prompt` instead. `slot1` was
repurposed for something that *is* legitimately global/non-positional — voice selection,
which v1 had none of at all (plain `HiggsV3Generate` with no reference audio picks an
uncontrolled voice each generation).

**No speaker-description mechanism exists** — Higgs v3 has no natural-language voice
descriptor (no "deep male voice, calm and slow" style prompting like Parler-TTS); the
only voice control is cloning via reference audio. Boson's *hosted API* (not the open
weights) has six named presets — jake/chloe/eleanor/marcus/nora/oliver — each with a real
description, and their public demo clips (confirmed live, `HTTP 200`,
`docs.boson.ai/public/audio/higgs-audio-tts-voices/<Name>_intro.mp3`) work locally as
`HiggsV3VoiceClone` reference audio, approximating the preset via zero-shot cloning. Not
the actual server-side reference clips Boson uses — just their public demo intros — so
treat quality as "close, not guaranteed identical."

**Style/emotion tag syntax notes** (from the model card's `PROMPTING.md`, worth knowing
regardless of the frontend issue below): valid `style` values are exactly `singing`,
`shouting`, `whispering` — not `whisper` or other near-misses. *"Only the tags below are
recognized — anything else degrades output or gets read literally."* Style tags are also
**sentence-level only**: *"Put at the start of the sentence; it colors the whole
sentence"* — they can't be repositioned mid-sentence to switch styles partway through,
unlike `<|sfx:x|>` tags which are genuinely positional.

**Chat frontend mangles bare `<`/`>` — this is why tags looked broken.** Confirmed live
2026-07-29: whatever Telegram/Graydient chat frontend is used to submit these jobs
strips or corrupts literal `<...>` in message text before it reaches the workflow.
Symptom: `<|emotion:sad|>` came out as the model **literally speaking the words "emotion
sad"** — not an error, not silently ignored, just read aloud as leftover text once the
frontend stripped the delimiters. This looks exactly like "the model is ignoring my
tags" but isn't a Higgs/node issue at all. A backslash-escape trick that works for a
different (OVI/Wan22) workflow's `\<S\>...\<E\>` speech tags did **not** fix this for
Higgs's tags when tried. **Fix, first attempt**: stop typing `<`/`>` in chat at all —
`prompt` stays plain spoken text; a new `negative_prompt`→`HiggsV3TagBuilder.tags` field
takes bracket-free tag content instead.

**`negative_prompt` field_mapping root cause found — Graydient auto-synthesizes a
clobbering `prompt_positive` entry.** Confirmed live 2026-07-30 via `graydient-cli`
(`D:\ForgeExpress\cli\`, a headless Node client for Graydient's API — see below) running
`graydient workflows show audio-higgs --json`: the **live API response for our own
uploaded workflow** contains a `field_mapping` entry we never configured —
`{"local_field": "prompt_positive", "node_id": 4, "node_input_index": 1,
"node_input_name": "text", ...}` — targeting the exact same node input slot
(`HiggsV3TagBuilder`, index 1) that our own `negative_prompt`→`tags` mapping used, but
mislabeled `"text"` (index 1 is actually `tags` per the node's real `INPUT_TYPES` order).
Almost certainly triggered by `"split_prompt_pos_neg": true` — Graydient appears to
auto-generate a `prompt_positive` companion mapping when that flag is set, and it grabbed
the wrong index. If Graydient patches `field_mapping` entries in array order, this
entry (which sorted last) would silently overwrite whatever `negative_prompt` had just
written to that slot — a full explanation for "tags never apply no matter what's typed
into negative_prompt," independent of anything in our own node code. Also independently
confirmed via `graydient-cli`'s own docs (`docs/telegram-prompt-syntax.md`,
`docs/render-quality-notes.md`): **there is no separate negative-prompt transport at the
raw API level at all** — `[text]` square brackets are embedded inline in the single
prompt string; the CLI's own `--negative` flag is documented as "just sugar that wraps
text in `[...]` for you." A `negative_prompt` UI box, wherever it exists, is presumably
doing the same inline-bracket embedding before submission — not a genuinely separate
channel our `field_mapping` can safely target for a non-image workflow.

**FULLY RESOLVED 2026-08-02, confirmed live via `graydient-cli`.** The `[...]`-in-prompt
theory above turned out to be only half right, and cost most of a day of testing to
fully pin down. The real, complete picture:

1. **`local_field: "prompt"` never works for this workflow — must be `"prompt_positive"`.**
   Every test with `local_field: "prompt"` fell back to the field_mapping default,
   *no matter what else changed* — raw `graydient q` vs structured `graydient render`
   (a genuinely separate, clean `prompt` API body field, no string-parsing involved),
   `[...]` vs no brackets, flag ordering, `split_prompt_pos_neg` true/false (including
   toggling it directly in the Graydient UI, reverified via `workflows show --json`
   each time). Only `slot1`/`slot2`/`seed`/`length` ever worked, proving field_mapping
   patching itself was fine — something specific to the name `"prompt"` wasn't. The one
   variable never tried was the local_field *name itself* — and `"prompt_positive"` is
   exactly what Graydient had auto-synthesized on its own back at the start of this
   investigation (§ above), which in hindsight was a real clue, not just a bug to route
   around. Renaming `prompt` → `prompt_positive` (same target: `HiggsV3TagBuilder.text`)
   fixed it immediately — first time correct spoken text came through in the entire
   session. **Lesson: Graydient's `local_field` names must match its actual expected
   convention for the platform/workflow type, verify via `workflows show`, don't assume
   `prompt` is universal across all workflow platforms.**
2. **`negative_prompt` never works for this workflow, full stop — not a clobbering
   artifact, a dead end.** Re-added cleanly (no auto-synthesis collision possible this
   time, single deliberate mapping) once `prompt_positive` was proven working, and
   tested multiple ways including `graydient render --negative` (confirmed to reach a
   genuine separate `negative_prompt` API body field, not embedded in text). Tags
   still never applied. Root cause unknown — left mapped (harmless if unused) but
   **do not rely on it**.
3. **What actually works: a `tags::speech` marker embedded in the *same* `prompt_positive`
   text**, e.g. `"emotion:sadness,style:whispering::I sure would love to eat a taco!"`
   — no cross-field routing at all, just our own node parsing one string. Confirmed
   live with a real sad/whispered result. `[...]` square-bracket syntax is **not**
   reliable — `graydient render`'s own client-side parser strips it into the (broken)
   `negative_prompt` field before submission, and other paths showed no evidence of it
   surviving either. **`tags::speech` is now the sole documented mechanism.**

`HiggsV3TagBuilder` and `HiggsV3VoicePreset` both `print()` their resolved
inputs/outputs to the ComfyUI console (visible in Graydient job logs) — this is what
made the whole chain diagnosable at all; without it, every failure would have looked
identical (default sentence spoken, no error) regardless of which of the three
mechanisms above was the actual culprit at each step.

```
HiggsV3LoadModel ──────────────────────┐
HiggsV3VoicePreset (ours, slot1/init_audio) ├→ HiggsV3VoiceClone → SaveAudio
    ├→ HiggsV3WhisperTranscribe (auto-transcribes the reference clip) ┘
HiggsV3TagBuilder (ours, prompt_positive only -- tags::speech marker) ┘
```

### `graydient-cli` — a headless test loop for this whole debugging process

`D:\ForgeExpress\cli\` (`graydient` on PATH after `npm link`) is a small Node CLI wrapping
Graydient's hosted API — the same request logic that powers the ForgeExpress Electron
app, factored out for terminal/script/agent use. Auth via `graydient auth login --key
<key>` or a `GRAYDIENT_API_KEY` env var. Key commands: `workflows list/show <slug>
--json` (ground truth for what Graydient actually has stored for a workflow — caught the
`prompt_positive` bug above), `render "<prompt>" --workflow <slug> --negative <text>
--json` (CLI's own reduced mini-language: `/run:`, `/key:value`, `[negative]`,
`<concept:weight>` only — silently drops anything else), `q "<command>"` / `quick`
(sends a raw Telegram-syntax string completely unparsed — use this for anything the
mini-language doesn't cover), `status <hash>`, `download <hash> --out path`. This
finally allows testing Graydient jobs directly instead of only through pasted logs —
worth reaching for whenever debugging a field_mapping/prompt-routing issue like this one,
since `workflows show --json` is the authoritative source for what's actually
configured, not just what we uploaded.

| class_type | Key inputs/widgets | Notes |
|---|---|---|
| `HiggsV3LoadModel` | `model`, `dtype` (auto/bf16), `device`, `attention` (auto/sdpa/flash_attention/sageattention), `download_if_missing` | Native `transformers` inference, **no vllm-omni** — ~11GB VRAM, fits a 24GB card with room to spare. `model` set to the literal local folder name `"higgs-audio-v3-tts-4b"`, **not** the node's "(auto-download)" default — see §17, `expected value at line 1 column 1` |
| `HiggsV3VoicePreset` (ours, `ComfyUI-HiggsV3Glue`) | `voice` (COMBO: jake/chloe/eleanor/marcus/nora/oliver), `custom_audio_url` (STRING, optional, Graydient's `init_audio`) | Loads the matching Boson demo clip as AUDIO — reads a `concept_mapping`-staged local copy if present, else downloads directly (concept_mapping isn't guaranteed to persist across machine classes, §0). `custom_audio_url`, when non-empty, takes priority over `voice` and downloads that URL instead — lets a Graydient user clone their own voice, same pattern as `BakeVertexColorsFromViews.back_image_url` (§15a). Target clip shape: ~5-20s, single speaker, clean audio, natural/expressive delivery — matches the six working preset clips. Decodes via direct `ffmpeg` subprocess, not `torchaudio.load()` — see §17 debugging checklist, `_AudioDecoder() takes no arguments`. All downloads in this node send a browser-like `User-Agent` header — `urllib`'s default UA got a `403` from `docs.boson.ai`'s WAF during testing, a real risk for arbitrary user-supplied URLs too. `local_field: "init_audio"` matches `graydient-cli`'s own `--init-audio` flag (a real API body field, same mechanism as `init_image`) — more discoverable in a chat UI than a bare slot |
| `HiggsV3WhisperTranscribe` (upstream) | `audio` (linked from VoicePreset), `model` (default `whisper-large-v3-turbo (auto-download)`), `dtype`, `language`, `task`, `chunk_length_s`, `download_if_missing` | Auto-transcribes whichever reference clip is selected, feeds `HiggsV3VoiceClone.reference_text` — avoids hand-typing (and risking mis-transcribing) a reference transcript, for presets or custom clips alike |
| `HiggsV3TagBuilder` (ours, `ComfyUI-HiggsV3Glue`) | `text` (STRING, Graydient's `prompt_positive` — carries the `tags::speech` marker), `tags` (STRING, Graydient's `negative_prompt` — confirmed dead end, don't rely on it) | If `tags` is non-empty, uses it (takes priority, but this path has never worked live). Else, if `text` contains `::` with a `:` before it, treats the part before `::` as bracket-free tags and the rest as speech — **this is the confirmed-working mechanism**. Splits tags on `;`/`,`, wraps each piece in `<\|...\|>`, prepends to the speech text. Also strips `[...]` bracket groups from `text` as a secondary fallback, but this hasn't been confirmed reliable through a real chat frontend (client-side parsers tend to intercept/strip `[...]` before submission) |
| `HiggsV3VoiceClone` | `higgs_model` (linked), `text` (linked from TagBuilder), `reference_audio` (linked), `reference_text` (linked), `max_new_tokens`, `temperature`, `top_p`, `top_k`, `seed`, `longform_chunking`, `words_per_chunk`, `pause_between_chunks` | All four non-generation-control inputs are now links — none are literal widgets, which shifted every `field_mapping` `node_input_index` down (e.g. `seed` moved from 5→4) versus the first v2 cut |
| `HiggsV3Generate` | same minus reference audio | Not used — no voice control, kept for reference |
| `HiggsV3MultiSpeaker` | up to 6 `speaker_N_audio`/`speaker_N_reference_text` pairs | Not wired into our workflow — multi-speaker dialogue is a possible future v3 |

Model: `bosonai/higgs-audio-v3-tts-4b` (9.31GB safetensors), pre-staged via
`concept_mapping` to `higgsv3tts/higgs-audio-v3-tts-4b/`; six voice clips pre-staged to
`higgsv3tts/voices/`. pip: `transformers>=5.3.0,<5.6.0` (pinned explicitly — Graydient's
base image version is unknown, and upstream's own `requirements.txt` deliberately avoids
pinning it, assuming a host environment already has the right version). `split_prompt_pos_neg: False`.
Field mapping (**final, confirmed working 2026-08-02**): `prompt_positive`→TagBuilder.text
(carries the `tags::speech` marker inline — the confirmed mechanism, not `[...]`),
`negative_prompt`→TagBuilder.tags (kept mapped, but confirmed dead end, don't rely on
it), `slot1`→VoicePreset.voice, `init_audio`/`init_audio_url`/`init_audio_filename`→
VoicePreset's three separate custom-clip slots (`custom_audio_url`/`custom_audio_url_alt`/
`custom_audio_filename` — mapped defensively to three different local_field name
variants since it's unclear which one a given submission path actually populates, same
"don't assume the raw API body key matches Graydient's local_field convention" lesson as
`prompt`/`prompt_positive`; each targets its own node slot so none can clobber another,
first non-empty wins, checked in that order), `seed`, `length`→max_new_tokens.

**Live run progress log** (revise this as further runs land):
- 2026-07-29 run 1 (`g1_embedded`, 4090): failed in `HiggsV3VoicePreset` — broken
  torchcodec `AudioDecoder`. Fixed (§17, ffmpeg subprocess decode).
- 2026-07-29 run 2 (`tls-pro-ny1-g0`, 5090): `HiggsV3VoicePreset` and
  `HiggsV3WhisperTranscribe` both confirmed working live — transcript came back correct
  (*"Hi, I'm Chloe Adams..."*) for the `chloe` preset clip. Failed loading
  `HiggsV3LoadModel` — wrong repo id from a stale duplicate node-pack copy. Fixed (§17,
  local folder name instead of "(auto-download)").
- 2026-07-29 run 3 (`tls-pro-ny4-g2`): failed before ComfyUI even started — Graydient
  platform-side install stuck (`WorkflowInstallStuckException`, §17). Not our bug, just
  a stuck machine; retried.
- 2026-07-29 run 4 (`tls-pro-ny4-g3`, 5090): `HiggsV3LoadModel` weights loaded correctly
  this time (401 tensors) — the local-folder fix from run 2 held up. New failure one
  step later, in Graydient's own DynamicVRAM registration — `device: "cuda"` has no
  explicit GPU index, which `comfy_aimdo` needs. Fixed (§17, `device: "auto"` instead of
  `"cuda"`).
- 2026-07-29 run 5 (`tls-pro-ny7-g0`, 4090): **first fully clean run, zero errors**,
  `Prompt executed in 27.73 seconds`. Confirmed all of the above fixes hold
  simultaneously. But confirmed a *user* mistake, not a bug: the actual text sent was
  the `prompt` field's literal default value, not the intended sentence — the chat
  frontend routed the user's text into a different field (the positive/negative prompt
  split) than expected. Log evidence:
  `Higgs v3 generating chunk 1/1: Hello! This is Higgs Audio v3 running natively inside ComfyUI.`
- 2026-07-29, first correctly-routed test: audio rendered successfully with the intended
  spoken text (confirmed via user-supplied `.ogg`, `ffprobe`: opus, 24kHz→48kHz output,
  duration matched expected sentence length) — **end-to-end pipeline confirmed working**,
  including `HiggsV3VoiceClone` generation itself. But `<|emotion:sad|>`/`<|style:whisper|>`
  tags typed directly into `prompt` did not apply — led to the chat-frontend
  angle-bracket-mangling discovery above and the `HiggsV3TagBuilder`/`negative_prompt`
  redesign (first attempt).
- 2026-07-29, later same day: `prompt` confirmed working correctly on its own (tags
  removed from the equation). Tried the `negative_prompt`→`HiggsV3TagBuilder.tags` path —
  confirmed (via `.json` diff-inspection of the actual uploaded workflow, not
  assumption) that the graph and `field_mapping` were wired exactly as intended, and
  independently confirmed the user has a genuine fillable `negative_prompt` field in
  their chat UI — yet tags still never applied across repeated tests. Log evidence of a
  failed attempt where tags were typed directly into `prompt` with square brackets
  instead (`[emotion:elated][style:shouting]`) showed the model reading them as literal
  words. **Re-diagnosed 2026-07-30** (see below) — this wasn't a failed manual-typing
  experiment, it's exactly what Graydient's real `[...]` inline negative-prompt syntax
  looks like when the receiving node doesn't know to parse it out; the fix needed was in
  our node, not the user's input.
- 2026-07-30: got direct Graydient API access via `graydient-cli` (`D:\ForgeExpress\cli\`).
  `graydient workflows show audio-higgs --json` revealed an auto-synthesized
  `local_field: "prompt_positive"` field_mapping entry (not something we configured)
  clobbering the same node slot `negative_prompt`→`tags` used. Fixed at the time:
  `split_prompt_pos_neg` off, no `negative_prompt` field_mapping, `[...]` parsing added
  as primary mechanism. This turned out to be an incomplete fix — see the next entries.
- 2026-08-01/02, extended live test session via `graydient-cli` (first time testing
  jobs directly rather than through pasted logs): systematically tested every
  combination of `local_field: "prompt"` submission — raw `q` vs structured `render`,
  `[...]` vs no brackets, flag ordering, `split_prompt_pos_neg` true/false (toggled
  directly in the Graydient UI, reverified via `workflows show` each time, confirmed via
  a real 403-style value change from true→false mid-session) — **every single one** fell
  back to the field_mapping default, confirmed via the node's own debug-log `print()`
  output pasted back from real job logs. `slot1` (proven via a non-default `oliver`
  voice actually speaking) confirmed field_mapping patching itself works fine; something
  specific to `"prompt"` as a name did not. Duration-matching was tried as a cheap
  proxy signal and turned out unreliable (generation-timing variance produced different
  durations for identical default-text output) — user's direct listen-confirmation was
  the only trustworthy signal throughout.
- 2026-08-02: renamed `local_field` from `"prompt"` to `"prompt_positive"` (same target).
  **First correct spoken text of the entire session**, confirmed live. Re-added
  `negative_prompt`→`tags` cleanly (single mapping, no auto-synthesis collision possible)
  — confirmed via `workflows show` the upload was clean, but tags **still never applied**
  in a live test (`emotion:sadness,style:whispering` via `graydient render --negative`,
  confirmed to reach a genuine separate `negative_prompt` API body field at the request
  level) — a real dead end, not a clobbering artifact. Final fix: `tags::speech` marker
  embedded directly in the same `prompt_positive` text (e.g.
  `"emotion:sadness,style:whispering::I sure would love to eat a taco!"`), sent as one
  field with zero cross-field routing — **confirmed live, correct sad/whispered
  delivery**. Also swapped `slot2`→`custom_audio_url` for `init_audio`→`custom_audio_url`
  (matches `graydient-cli`'s own `--init-audio`, a real native API field) for
  discoverability, not because slot2 was broken.
- 2026-08-02, same day: `init_audio` confirmed live — `slot1:jake` set but `init_audio`
  pointed at Chloe's preset clip URL, combined with `tags::speech` for
  `emotion:sadness,style:whispering`. Result: correctly cloned Chloe's voice (proving
  `init_audio` overrides `slot1` as designed) speaking sadly and whispered (proving tags
  and voice cloning compose correctly in the same request). Also confirmed `init_audio`
  auto-sets a generic `init_image` fallback to the same URL client-side (per
  `graydient-cli`'s own documented behavior for audio-only workflows) — harmless, we
  don't map `init_image` to anything.

**Every piece of this workflow (text, tags, voice preset, custom voice cloning) is now
confirmed working end-to-end via real Graydient renders — this workflow is done, not
just "should work."**

**2026-08-02, revised same day — two bugs found once real cloning attempts accumulated:**

1. **Cloning was silently unreliable without `require_clone_source: true`.** Confirmed by
   the user: cloning "definitely doesn't work" unless `HiggsV3VoicePreset`'s
   `require_clone_source` optional input (added earlier the same day, see §17's
   required-vs-optional entry) is explicitly forced `true`. With it `false` (the default),
   a clip that fails to resolve for whatever reason falls through to the `jake` preset
   with no error — so "cloning is incidental" was actually **silent fallback masking
   failed clip resolution**, not the model cloning inconsistently. This directly caused
   the split below.
2. **Tag text was bleeding into spoken audio — root cause: dead `negative_prompt`→`tags`
   path still checked FIRST.** `HiggsV3TagBuilder.build()`'s priority order checked the
   external `tags` input (fed by `negative_prompt`, already documented above as a
   confirmed dead end) *before* parsing `[...]`/`tags::` out of `text`. Whenever
   Graydient populated that field with anything at all — even unreliably — steps 2/3 were
   skipped entirely, so a `tags::` marker typed directly in the prompt was never stripped
   and got spoken aloud as literal text (e.g. `"emotion:relief,prosody:expressive_high::"`
   coming out as spoken words). **Fixed in `ComfyUI-HiggsV3Glue` commit `9224d11`**: the
   external `tags` input is now ignored entirely — `text` is always checked for
   `[...]`/`tags::` regardless of what (if anything) still routes into that kwarg.

**No text-described voice generation exists — reconfirmed by reading the actual upstream
node source** (`Saganaki22/Higgs_v3-TTS-ComfyUI`'s `nodes.py`/`native.py` on GitHub,
2026-08-02), not just inferred: `HiggsV3VoiceClone.reference_text` is gated in
`generate_higgs_audio()` — `if reference_text and num_ref_tokens > 0` — where
`num_ref_tokens` is `0` whenever `reference_audio` is `None`. So `reference_text` only
ever functions as a transcript *of an existing reference clip* (it strongly improves
cloning fidelity per the node's own tooltip — a clip Whisper mistranscribes will clone
noticeably worse even though the job succeeds, worth checking the
`[HiggsV3WhisperTranscribe]` job-log line before assuming a weak clone is the clip's
fault), never as a free-form style/voice descriptor. `HiggsV3Generate` (the no-reference
path) takes no text-description input at all — every generation is a fresh unconditioned
random voice. This matches the "No speaker-description mechanism exists" note earlier in
this section; there is no way to describe a new voice into existence with this node pack,
only clone an existing clip or accept whatever the model samples.

**Split into two workflows, `gen_higgs_tts.py` and `gen_higgs_clone.py`**, replacing the
single flexible `gen_higgs_v2.py` (kept for history, no longer the recommended script to
run). Rationale: a single workflow that *might* clone or *might* fall back to a preset
made failures invisible to the end user — same problem as bug 1 above, just structural
instead of a flag default. Splitting makes each workflow's contract explicit:
  - **`gen_higgs_tts.py`** → `GraydientWorkflow-higgs-v3-tts-preset-v1.json` — preset
    voices only (`slot1`: jake/chloe/eleanor/marcus/nora/oliver). `custom_audio_url*`
    inputs exist on the shared `HiggsV3VoicePreset` node (can't be removed without
    forking the node class) but are deliberately left out of `field_mapping`, so no
    Graydient field can ever populate them — always falls through to the chosen preset,
    no ambiguity.
  - **`gen_higgs_clone.py`** → `GraydientWorkflow-higgs-v3-tts-clone-v1.json` —
    cloning only. `require_clone_source` is hardlocked `true` directly in the `workflow_2`
    API json (not exposed via `field_mapping` at all — no Graydient input can turn it
    off). `slot1`/voice is not exposed either, since there's no preset fallback path to
    pick one for. Job fails loudly if none of `init_audio`/`init_audio_url`/
    `init_audio_filename` resolve to a real clip, instead of quietly handing back Jake.

Both scripts otherwise inherit every fix documented above (`prompt_positive` local_field,
`tags::` marker as the sole tag mechanism, `device: "auto"`, pinned local model folder
name).

**2026-08-02, same day, root cause found for "cloning still isn't working" even with
`require_clone_source: true` and the tag-bleed fix live.** A real clone-workflow render
(`clone-h34b-3370-2`, RTX 4090) confirmed everything upstream of generation was correct —
`custom_audio_url_alt` resolved a real Telegram voice-note URL, clip stats looked healthy
(`duration=9.75s peak=-0.0dBFS rms=-20.1dBFS frames_below_-42dB=25%`), Whisper transcribed
it fine, `reference_audio`/`reference_text` both linked into `HiggsV3VoiceClone` — yet the
output still didn't sound cloned. `HiggsV3TagBuilder`'s logged `combined_text` was
`'<|emotion:relief|><|prosody:expressive_high|>OMG finally!...'` — **two control tags
stacked at the absolute front, before a single word of speech.**

Checked `Saganaki22/Higgs_v3-TTS-ComfyUI`'s GitHub issues directly (not guessing) —
[issue #3](https://github.com/Saganaki22/Higgs_v3-TTS-ComfyUI/issues/3), closed, maintainer
reply: *"stronger emotions... can overpower the cloned-speaker conditioning when placed at
the very beginning, causing the voice to drift... let the model establish the reference
voice with at least one word first"* — documented example: `"This <|emotion:sadness|>is a
short test sentence"`, tag placed directly after word 1, **no space** before word 2. This
is a Higgs v3 model-level limitation (autoregressive, single-pass architecture — the
maintainer is explicit this isn't fixable node-side), not a wiring bug in our glue code —
matches this session's symptom exactly: structurally correct cloning, tags placed before
any reference-establishing word, voice drifted onto something else.

**Fixed in `ComfyUI-HiggsV3Glue` commit `20363a1`**: `HiggsV3TagBuilder.build()` now
splits `working_text` on the first whitespace run and inserts the tag prefix directly after
word 1 (no space before word 2), reproducing the maintainer's documented shape
automatically. Callers still type `tags::speech` up front — the reordering happens
server-side, no change needed on the Graydient-field-mapping or chat-syntax side.

**Also worth knowing from the same issue thread**: longform chunking (`words_per_chunk`
splitting long text into multiple generation passes) is explicitly called out as
**experimental and expected to drift voice identity across chunks regardless of
settings** — a single-pass-model limitation, not something `words_per_chunk`/seed tuning
can fix. If a long cloned utterance drifts partway through, that's this same limitation,
not a new bug — keep clone-workflow text short (a sentence or two) rather than relying on
`longform_chunking` for voice consistency.

**Not yet re-verified live after the tag-reorder fix** — the diagnosis is solid (direct
maintainer confirmation of the exact failure shape observed in a real job log), but no
render has been run against the fixed node yet as of this edit. Next real test should
confirm cloning holds up with a single tag placed correctly, before declaring this fully
resolved.

**Same day, follow-up: `tags::` only ever parsed ONE marker, at the very start of the
message — a second tag block placed mid-message was spoken literally instead of applied.**
User feedback: "tags placed in the middle of a prompt seem to be ignored." Root cause was
exactly that — `HiggsV3TagBuilder.build()` only checked for a marker at the very start of
`text`; anything after the first `::` was untouched, `::` and all, so a second attempted
tag block just got read aloud as literal punctuation-laden text.

**Fixed in `ComfyUI-HiggsV3Glue` commit `f7892b3`**: `HiggsV3TagBuilder` now supports
multiple tag/speech segments in one message:
```
firsttag:thing:: speech ... ::secondtag:thing:: more speech ...
```
The leading segment has no leading `::` (nothing precedes it to delimit against, same as
before); every segment AFTER the first needs `::` on BOTH sides (`::tags::`) so the parser
can distinguish "a new tag block starts here" from an ordinary `::` a user might type as
punctuation. A candidate match whose inner content has no `:` in it (not a real tag list)
is left as literal text rather than force-split — degrades safely instead of mangling
ordinary speech that happens to contain `::`. Each segment independently gets the
first-word-after-tag treatment from the previous fix, so per-segment cloning-conditioning
safety (see above) holds across the whole message, not just the first sentence. Updated in
`.claude/skills/higgs-tts/SKILL.md` with a worked multi-segment example.

**Live-verified 2026-08-02, also revealed the per-machine node caching issue again** — a
render against the `clone-h34b` slug came back completely unprocessed (old `resolved_tags=`
debug format, not the new `segments=` one — proof the machine ran pre-`f7892b3` cached
code). **User's workaround, now the recommended practice**: register a **fresh Graydient
workflow slug** after any node-repo push rather than restoring into the existing one — this
forces a clean pull with no stale-cache risk, more reliably than hoping a retry lands on an
uncached machine. `clone-h34b` is now considered stale/retired; `clone-higgs1` is current.
Re-tested against `clone-higgs1` and multi-segment splitting confirmed working — the
`[HiggsV3TagBuilder]` log's `segments=` list showed all three tag blocks
(`style:singing`/`sfx:laughter`/`style:whispering`) split and placed correctly.

**Immediately surfaced a second, distinct issue: `style` tags placed after word 1 (the
emotion/cloning-drift fix) were being silently ignored, while an `sfx` tag in the same
message fired correctly.** The job log proved this wasn't a parsing bug — `combined_text`
had exactly the intended shape. Cross-referencing the *other*, separately-sourced
Higgs `PROMPTING.md` quote already in this doc (style section above): style tags are a
**registration requirement** — *"put at the start of the sentence; it colors the whole
sentence"* — not merely a drift-avoidance nicety like the emotion/issue-#3 fix. Applying
the emotion fix uniformly to every tag category broke style's registration requirement.

**Fixed in `ComfyUI-HiggsV3Glue` commit `8945449`**: `_apply_tags` (renamed from
`_apply_tags_after_first_word`) now branches by category — `style` tags, and segments
containing ONLY `sfx` tags, are placed at the literal start of the segment (also fixes
`sfx`'s tag/word ordering to match *"pair each token with the matching onomatopoeia
immediately after it"* — previously placed after the word). `emotion` (and anything else,
e.g. `prosody`) keeps the after-word-1 placement from the previous fix. **Not yet
re-verified live** — the category split follows directly from evidence already in this
doc, but hasn't been confirmed against a real render since this specific fix landed.

**2026-08-02, ROOT CAUSE FOUND (via Graydient support) for the entire "API-submitted
clone renders always fail with `require_clone_source ... all empty`, zero fetch attempt
ever logged" saga that consumed most of a day.** Every hypothesis chased across dozens of
render attempts — field naming, `field_mapping` misconfiguration, per-machine node
caching, a server-side routing gap for the API-submission path — turned out to be one
specific, narrow parser bug, unrelated to anything in `ComfyUI-HiggsV3Glue` or this
workflow's JSON:

**A literal URL cannot be embedded inline in a `/key:value` slash parameter inside the
`prompt` string.** The prompt mini-language uses `:` and `/` as its own token delimiters,
and any real URL (`https://api.telegram.org/file/bot123:ABC/voice/file.oga`) is full of
exactly those characters — Graydient's parser silently failed to extract the value, so it
never reached the node's inputs at all (explaining the "empty, no fetch attempt" signature
consistently observed — the value was lost during prompt-string parsing, before the
render request's `field_mapping` patching or the ComfyUI graph ever ran).

**Fix, confirmed working by Graydient support**: register the URL as a named entry in a
top-level `placeholders` object in the request body, and reference it by that name inside
the `prompt` string — never inline the raw URL after a `:`. Verbatim confirmed-working
example:
```json
{
  "placeholders": { "URL1": "https://api.telegram.org/file/bot5714594430:AAFo.../music/file_2037999.mp3" },
  "prompt": "/workflow /run:clone-higgs /initaudio:URL1 I think the gray aliens are really just dinosaurs!",
  "callback_url": "https://mydev.ngrok.io/webhook/render"
}
```
Also note: the raw-prompt slash parameter is **`/initaudio`, no underscore** — distinct
from `field_mapping`'s `local_field` naming (`init_audio`, underscored) used for
structured/non-prompt-string API calls, which is a separate mechanism unaffected by this
bug (those values go in as their own top-level JSON fields, never through the colon-
delimited slash-token parser). Real Telegram voice-message attachments were unaffected all
along because Graydient resolves those server-side without ever routing the raw URL
through this same parser.

**General rule**: any value passed through the `prompt` string containing `:` or `/`
(mainly URLs) needs a `placeholders` entry, not inline embedding. Values without those
characters (plain words, `slot1:jake`, tag blocks like `emotion:relief::`) are unaffected
and can stay inline. Full write-up with a programmatic-prompt-builder reference
implementation: `HIGGS-CLONE-HANDOFF.md` §0 and §6.

---

## 21. Cosmos3 — prior working notes (T2I confirmed; see §18 for current script inventory)

- **T2I**: producing cinematic-quality images. ~277s on RTX 5090 (BF16 + sequential CPU
  offload). Graydient fields: `prompt_positive`, `prompt_negative`, `seed`, `steps`,
  `scale`, `slot1` (quality preset), `slot3` (quantization).
- **Quantization**: torchao int8/int4 available but NOT working on RTX 5090 (Blackwell
  sm_120) — CUDA kernels compiled for sm_90a (Hopper) only. Falls back gracefully to
  BF16 sequential offload. Check for Blackwell torchao wheels when available.
- **Step budget on 5090 (32GB BF16 sequential)**: ~53s warmup + ~6s/step. Stay ≤25
  steps to fit in ~277s-confirmed timeout.
- **enable_model_cpu_offload vs enable_sequential_cpu_offload**: model offload moves
  entire sub-models (faster, needs each sub-model to fit in VRAM); sequential offload
  moves layer-by-layer (slower, most memory efficient). INT8 would unlock model offload
  — revisit when Blackwell torchao lands.
- `Cosmos3OmniDiffusersPipeline` lives in **`diffusers-cosmos3`** (NVIDIA's plugin), NOT
  in diffusers itself — monkey-patches `diffusers` at import time, so
  `import diffusers_cosmos3` must run before `DiffusionPipeline.from_pretrained`.
- `diffusers>=0.37.0` required, install from git HEAD (may not be on PyPI yet).
- `device_map="auto"` NOT supported — use `"balanced"` (supported: `balanced`, `cuda`,
  `cpu`).
- Model is Linux-only, bfloat16-only (FP16/FP8 unsupported per NVIDIA).
- Local node dir: `D:\ComfyUI-Cosmos3\`.
- **T2V/I2V/I2I status**: this section's notes predate those scripts existing — the
  timing/VRAM figures above are T2I-only. Don't assume they transfer to the other three
  modalities without checking.
