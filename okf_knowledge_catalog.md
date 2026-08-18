---
schema_version: "1.0.0"
id: "okf-graydient-comfyui-workflow-catalog"
title: "OKF Knowledge Catalog: Graydient & ComfyUI Workflow Engineering"
version: "1.0.0"
type: "architecture_and_guidelines"
tags:
  - comfyui
  - graydient
  - backup-restore
  - concept_mapping
  - field_mapping
  - custom-nodes
  - audio-generation
  - dynamicvram
sources:
  - "GRAYDIENT-COMPLETE-REFERENCE.md"
  - "COMFYUI-REFERENCE.md"
  - "gen_audioldm_t2s.py"
  - "gen_higgs_v2.py"
---

# OKF Knowledge Catalog: Graydient & ComfyUI Workflow Engineering

## 1. Overview & System Architecture

Graydient deploys ComfyUI workflows on ephemeral SaaS GPU instances via single-file **Backup/Restore JSON** configurations (`GraydientWorkflow-*.json`). Workflows are authored programmatically via Python generator scripts (`gen_*.py`).

### 1.1 The Dual-Workflow Requirement
Every Graydient JSON configuration must contain two distinct ComfyUI representation formats:

```
┌────────────────────────────────────────────────────────────────────────┐
│                      Graydient Backup JSON                             │
├──────────────────────────────────┬─────────────────────────────────────┤
│  "workflow" (Standard Format)    │  "workflow_2" (API / Prompt Format) │
│  - Drag-and-drop UI graph        │  - Keyed by string Node IDs ("1")   │
│  - Contains `nodes` & `links`    │  - Contains `class_type` & `inputs` │
│  - Used for visual UI rendering  │  - What Graydient API executes      │
└──────────────────────────────────┴─────────────────────────────────────┘
```

---

## 2. Model Staging & Concept Mapping (`concept_mapping`)

### 2.1 Staging Directory Convention
`concept_mapping` pre-downloads remote model files (from HuggingFace, ModelScope, S3) directly into the instance's `{ComfyUI}/models/` directory **before** ComfyUI initializes:

```json
"concept_mapping": [
  {
    "allow_dynamic": false,
    "concept_name": null,
    "concept_type": null,
    "dynamic_family": null,
    "field_mapping": "",
    "is_zipped": false,
    "type": "url",
    "url": "https://huggingface.co/cvssp/audioldm-l-full/resolve/main/unet/diffusion_pytorch_model.bin",
    "destination": "audioldm-l-full/unet/diffusion_pytorch_model.bin"
  }
]
```
- `destination` is relative to `{ComfyUI}/models/`. The above entry stages the UNet model at `{ComfyUI}/models/audioldm-l-full/unet/diffusion_pytorch_model.bin`.

### 2.2 Critical Offline Loading Rule for Custom Nodes
> [!IMPORTANT]
> Custom Node Python code **MUST** check for local staged files before making any network requests or invoking HuggingFace `snapshot_download()` / `requests.get()`. Failing to check local disk first causes network timeouts, 403 WAF blocks, or container crashes on isolated SaaS runtimes.

```python
# PREFERRED PATTERN in Custom Node load_model()
def load_model(self, model_name: str):
    model_path = os.path.join(folder_paths.models_dir, model_name)
    
    # 1. Check if model files were pre-downloaded via concept_mapping
    if not os.path.isfile(os.path.join(model_path, "model_index.json")):
        # 2. Fallback to network download only if missing
        if check_huggingface_access():
            download_model_hf(model_path, f"cvssp/{model_name}")
        else:
            download_model_modelscope(model_path, f"cutemodel/{model_name}")

    # 3. Load directly from local disk offline
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    pipeline = AudioLDMPipeline.from_pretrained(model_path, torch_dtype=dtype)
    return (pipeline.to(device),)
```

---

## 3. Field Mapping Specification (`field_mapping`)

`field_mapping` connects user inputs from the Graydient SaaS UI / API payload (`prompt`, `seed`, `slot1`, `slot2`, `init_image_url`, `init_audio_url`) to specific node parameters.

### 3.1 Parameter Indexing Rule
- `node_id`: Target node ID (integer).
- `node_input_name`: Parameter key in the node's `INPUT_TYPES` dictionary.
- `node_input_index`: **0-based index counting ONLY primitive widgets in `widgets_values`**. Connected socket inputs with incoming links are **EXCLUDED** from index counting.

```json
{
  "default_value": 48000,
  "help_text": "Sample rate of output audio file",
  "local_field": "slot1",
  "maximum_value": 48000,
  "minimum_value": 8000,
  "node_id": 2,
  "node_input_index": 5,
  "node_input_name": "sample_rate",
  "node_name": "AudioLDM Sampler"
}
```

### 3.2 Canonical Local Fields
| Graydient `local_field` | Standard UI Usage | Common Target Input |
|---|---|---|
| `prompt` / `prompt_positive` | Main positive text prompt | Sampler text / CLIP Text Encode |
| `prompt_negative` | Negative text prompt | Sampler negative text / CLIP |
| `seed` | Random seed integer | Sampler seed |
| `length` | Output duration / step count | Sampler audio_length / max_tokens |
| `steps` | Inference steps | Sampler steps |
| `guidance` | Guidance scale (CFG) | Sampler guidance_scale |
| `slot1`, `slot2`, `slot3` | Extra dropdowns / sliders | Sample rate, style, quantization |
| `init_image_url` | Primary input image link | LoadImageFromURL `url` |
| `init_audio` / `init_audio_url` | Input audio clip link | LoadAudioFromURL `url` |

---

## 4. Custom Node Architecture: Modular Loader/Sampler Pattern

Monolithic nodes (which combine model loading and sampling into a single step) re-load models on every run, leading to high latency and VRAM thrashing.

### 4.1 Decoupled Node Design
Always split complex model integrations into two decoupled ComfyUI custom nodes:

```
┌──────────────────────────┐          ┌──────────────────────────────────┐
│   AudioLDMModelLoader    │          │         AudioLDMSampler          │
├──────────────────────────┤          ├──────────────────────────────────┤
│ Inputs:                  │          │ Inputs:                          │
│  - model_name (STRING)   │          │  - audioldm_model (AUDIOLDM_MODEL)│
│                          │          │  - prompt (STRING)               │
│ Outputs:                 ├─────────►│  - negative_prompt (STRING)      │
│  - audioldm_model        │ (Handle) │  - audio_length (FLOAT)          │
│    (Custom Type)         │          │  - num_steps (INT)               │
└──────────────────────────┘          │  - guidance_scale (FLOAT)        │
                                      │  - sample_rate (INT)             │
                                      │  - seed (INT)                    │
                                      │ Outputs:                         │
                                      │  - audio (AUDIO Dict)            │
                                      └──────────────────────────────────┘
```

### 4.2 Audio Signal & Resampling Standard
- **Native AudioLDM Output**: Synthesizes audio natively at 16kHz (`16000Hz`).
- **High-Fidelity Resampling**: Polyphase resampling via `scipy.signal.resample_poly(audio, 16000, target_sr)` upsamples audio up to **48kHz (48000Hz)** for crispy sound without changing pitch or playback speed.
- **ComfyUI Audio Dictionary Standard**: Returns `{"waveform": tensor, "sample_rate": sample_rate}` where `waveform` is a 3D float32 tensor `[batch, channels, samples]`.

---

## 5. Execution Constraints & Gotchas Checklist

1. **Timeout Budget**: Total job execution budget is **~380s**. Model downloads must be staged in `concept_mapping` to avoid consuming the inference time budget.
2. **VRAM Allocation**: Model weights + activation memory must fit within instance limits (e.g. 24GB RTX 4090).
3. **Execution Order**: ComfyUI computes node execution order strictly based on graph topology links, NOT the numerical `"order"` field.
4. **Escape HTML Frontend Tags**: The Graydient web frontend strips bare `<` and `>` characters from text inputs. Workflows requiring prompt tags must use prefix syntax (e.g., `tags::emotion:elation::`) or bracket-free strings.

---

## 6. The Graveyard & Runtime Constraints (KI-007)

- **Pure Python Rule**: No Rust `cargo` or C++ compiler toolchains exist on ephemeral Graydient runners. All `requirements.pip` packages must have pre-built `manylinux` wheels or be pure Python.
- **Universal Input Resolution**: Always use `Load Audio Any` to handle both remote HTTP URLs (Telegram/webhooks) and pre-staged local filenames safely.
- **Offline-First Rule**: Custom node `load_model()` methods must check local `{ComfyUI}/models/` disk first before attempting HuggingFace network calls.
- **Comfy Registry Fork Naming**: When forking node repos, update `pyproject.toml` package identity to prevent caching collisions.

---

## 7. Concept Mapping Registry (KI-008)

Canonical, verified HuggingFace / ModelScope weight links and destination paths are cataloged in `KI-008` and indexed in `graydient_builder/concept_db.json` for instant lookup across all model families (Whisper, AudioLDM, Higgs, LTX-Video, TripoSG, SAM3).

---

## 8. Intent-vs-Vehicle Pivot Protocol (KI-009)

When planning workflows, agents and developers separate functional intent (e.g. "sync frame count to speech duration") from proposed technical vehicle (e.g. "compile a custom rust audio parser"). If a proposed method violates runtime constraints, the agent triggers the Pivot Protocol to offer 1–2 pre-validated compliant routes.

