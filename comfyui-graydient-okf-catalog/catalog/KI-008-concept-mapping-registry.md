---
id: "KI-008"
title: "Concept Mapping Registry & Verified Weight Destinations"
version: "1.0.0"
type: "model_registry"
tags:
  - concept_mapping
  - model_staging
  - weights
  - huggingface
  - modelscope
sources:
  - "GRAYDIENT-COMPLETE-REFERENCE.md"
  - "GraydientWorkflow-*.json"
---

# KI-008: Concept Mapping Registry & Verified Weight Destinations

Pre-staging model weights via `concept_mapping` ensures models are downloaded directly into `{ComfyUI}/models/` prior to instance boot. This document indexes verified, production-tested model staging locations.

---

## 1. Verified Model Concept Matrix

| Model Family | Sub-type / File | Canonical Source URL | Destination Path under `{ComfyUI}/models/` |
|---|---|---|---|
| **Whisper Large v3** | Model bin | `https://huggingface.co/Systran/faster-whisper-large-v3/resolve/main/model.bin` | `whisper/large-v3/model.bin` |
| **Whisper Large v3** | Config / Tokenizer | `https://huggingface.co/Systran/faster-whisper-large-v3/resolve/main/config.json` | `whisper/large-v3/config.json` |
| **AudioLDM Full** | UNet PyTorch | `https://huggingface.co/cvssp/audioldm-l-full/resolve/main/unet/diffusion_pytorch_model.bin` | `audioldm-l-full/unet/diffusion_pytorch_model.bin` |
| **AudioLDM Full** | VAE / Vocoder | `https://huggingface.co/cvssp/audioldm-l-full/resolve/main/vae/diffusion_pytorch_model.bin` | `audioldm-l-full/vae/diffusion_pytorch_model.bin` |
| **Higgs Audio v3** | Voice Clone Model | `https://huggingface.co/Saganaki22/Higgs-Audio-v3-TTS/resolve/main/model.safetensors` | `tts/higgs-v3/model.safetensors` |
| **LTX-2.5 (i2v)** | Diffusion transformer (22B distilled, int8) | `https://huggingface.co/comfyicu/LTX-2.5/resolve/main/diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors` | `diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors` |
| **LTX-2.5 (i2v)** | Video VAE | `https://huggingface.co/comfyicu/LTX-2.5/resolve/main/vae/ltx-2.5-video-vae-bf16.safetensors` | `vae/ltx-2.5-video-vae-bf16.safetensors` |
| **LTX-2.5 (i2v)** | Audio VAE | `https://huggingface.co/comfyicu/LTX-2.5/resolve/main/vae/ltx-2.5-audio-vae-bf16.safetensors` | `vae/ltx-2.5-audio-vae-bf16.safetensors` |
| **LTX-2.5 (i2v)** | Main text encoder (Gemma 4 12B, int8) | `https://huggingface.co/comfyicu/LTX-2.5/resolve/main/text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors` | `text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors` |
| **LTX-2.5 (i2v)** | Prompt-enhancer text encoder (small Gemma 4) | `https://huggingface.co/Comfy-Org/gemma-4/resolve/main/text_encoders/gemma4_e2b_it_bf16.safetensors` | `text_encoders/gemma4_e2b_it_bf16.safetensors` |
| **LTX-2.5 (i2v)** | Spatial upscaler (2x, for two-pass refine) | `https://huggingface.co/comfyicu/LTX-2.5/resolve/main/latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors` | `latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors` |
| **TripoSG 3D** | STL Generator | `https://huggingface.co/VAST-AI/TripoSG/resolve/main/model.safetensors` | `triposg/model.safetensors` |
| **SAM3 Segmentation** | Checkpoint | `https://huggingface.co/facebook/sam2-hiera-large/resolve/main/sam2_hiera_large.pt` | `sams/sam2_hiera_large.pt` |

---

## 2. Concept Mapping JSON Template

```json
{
  "allow_dynamic": false,
  "concept_name": null,
  "concept_type": null,
  "dynamic_family": null,
  "dynamic_subtype_1": null,
  "dynamic_subtype_2": null,
  "dynamic_type": null,
  "field_mapping": "",
  "is_zipped": false,
  "type": "url",
  "url": "https://huggingface.co/org/repo/resolve/main/model.safetensors",
  "destination": "checkpoints/model.safetensors",
  "weight": null,
  "weight_field_mapping": null
}
```

---

## 3. Pre-Flight Rules for Adding New Concepts
1. Always test that direct downloads from the URL return `HTTP 200`/`302` (a `resolve/main/` link redirects to blob storage — that's success, not a failure) without requiring an interactive HuggingFace auth gate (gated repos must use direct tokens or mirror endpoints).
2. The `destination` must match the exact subfolder expected by ComfyUI's `folder_paths.get_folder_paths(...)` (e.g., `checkpoints`, `clip`, `vae`, `unet`, `whisper`).

---

## 4. Gated HuggingFace Repos — Confirmed Pattern and Fix

* **Failure Mode**: A `concept_mapping` URL from a gated repo (`gated: true`/`"auto"` per the HF API) returns `401 Unauthorized` when Graydient's downloader has no token for it — the file silently never downloads, and the actual error surfaces much later as `'<filename>' not in (list of length N)` inside a `VALIDATE_INPUTS`/COMBO-widget error, which does NOT obviously point back to "the download failed."
* **Confirmed live**: `Lightricks/LTX-2.5` (`gated: "auto"` — auto-approves on accepting the license, but Graydient still has no token) caused exactly this failure.
* **The Fix**: Search HuggingFace for an **ungated mirror with identical filenames** before assuming a workaround is needed. Confirmed pattern: `comfyicu/LTX-2.5` mirrors `Lightricks/LTX-2.5` with byte-identical filenames (`gated: false`, verified via `https://huggingface.co/api/models/<repo>` returning `"gated": false` and a real `curl -sI` returning `302`, not `401`). Swap the `concept_mapping` URL host only — `destination` paths stay identical.
* **Rule**: before wiring any `concept_mapping` entry, check `https://huggingface.co/api/models/<org>/<repo>` for `"gated"` — if not `false`, search for an ungated mirror rather than assuming the workflow will simply fail to deploy.
