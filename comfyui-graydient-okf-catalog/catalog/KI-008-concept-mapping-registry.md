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
| **LTX-2.5 (PinkCherry t2v)** | Undistilled dev finetune (42GB bf16) -- needs distill LoRA @1.0 | `https://huggingface.co/Jacob121294/PinkCherry_NSFW_LTX25/resolve/main/potatoes.safetensor` | `diffusion_models/pinkcherry_ltx25_dev.safetensors` |
| **LTX-2.5 (PinkCherry t2v)** | Distilled LoRA rank 450 (8.9GB, official; use the ungated mirror) | `https://huggingface.co/comfyicu/LTX-2.5/resolve/main/loras/ltx-2.5-22b-distilled-lora-450-bf16.safetensors` | `loras/ltx-2.5-22b-distilled-lora-450-bf16.safetensors` |
| **LTX-2.5 (PinkCherry t2v)** | Video VAE, conv variant | `https://huggingface.co/comfyicu/LTX-2.5/resolve/main/vae/ltx-2.5-video-vae-conv-bf16.safetensors` | `vae/ltx-2.5-video-vae-conv-bf16.safetensors` |
| **TripoSG 3D** | STL Generator | `https://huggingface.co/VAST-AI/TripoSG/resolve/main/model.safetensors` | `triposg/model.safetensors` |
| **SAM3 Segmentation** | Checkpoint | `https://huggingface.co/facebook/sam2-hiera-large/resolve/main/sam2_hiera_large.pt` | `sams/sam2_hiera_large.pt` |
| **HunyuanWorld-Mirror** | Model weights | `https://huggingface.co/tencent/HunyuanWorld-Mirror/resolve/main/model.safetensors` | `HunyuanWorld-Mirror/HunyuanWorld-Mirror.safetensors` (deliberately NOT `model.safetensors` -- see rule below) |
| **HunyuanWorld-Mirror** | Config | `https://huggingface.co/tencent/HunyuanWorld-Mirror/resolve/main/config.json` | `HunyuanWorld-Mirror/config.json` |
| **Audio2Face-3D v2.3 Mark** (NVIDIA Open Model License, not gated) | All 11 repo files: `model.json`, `network.onnx`, `network_info.json`, `model_config.json`, `model_data.npz`, `implicit_emo_db.npz`, `bs_skin.npz`, `bs_skin_config.json`, `bs_tongue.npz`, `bs_tongue_config.json`, `trt_info.json` | `https://huggingface.co/nvidia/Audio2Face-3D-v2.3-Mark/resolve/main/<file>` | `audio2face/mark-v2.3/<file>` -- confirmed staged by a live job (render 39o388, rigstudio-a2f-probe, 2026-09-24, model_s 0). `network.trt` is NOT in the repo: build it in-job from `network.onnx` (see KI-007 §13). Do NOT stage Audio2Emotion (licence). |
| **Whisper Medium** (faster-whisper) | `model.bin`, `config.json`, `tokenizer.json`, `vocabulary.txt` (NOT .json, no preprocessor_config -- HF listing checked) | `https://huggingface.co/Systran/faster-whisper-medium/resolve/main/<file>` | `whisper/medium/<file>` -- confirmed staged live (render ZVe419, rig-direct, 2026-09-30) |
| **Ollama qwen3:14b** (Q4_K_M, Ollama library build) | 5 registry blobs: config `78b3b822...`, model `a8cc1361...` (9.28 GB GGUF), template `ae370d88...`, license `d18a5cc7...`, params `cff3f395...` | `https://registry.ollama.ai/v2/library/qwen3/blobs/sha256:<digest>` (no auth, 200) | `ollama/blobs/sha256-<digest>` (Ollama's on-disk blob name) -- confirmed live (render ZVe419); the node writes the manifest itself (KI-007 §16) |
| **Ollama 0.34.2 runtime** (not a model) | `ollama-linux-amd64.tar.zst` (1.43 GB; bin/ + lib/ollama/cuda_v12 used) | `https://github.com/ollama/ollama/releases/download/v0.34.2/ollama-linux-amd64.tar.zst` (302 to GitHub CDN -- concept_mapping follows it) | `rigstudio/ollama/ollama-linux-amd64-v0.34.2.tar.zst` -- confirmed live (render ZVe419) |

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

---

## 5. Destination Filename Must Match the Node's Own Local-Path Resolution Logic — Not the HF Filename

* **Failure Mode**: `tencent/HunyuanWorld-Mirror`'s real HF filename is `model.safetensors`. `LoadHunyuanWorldMirrorModel`'s own `_resolve_model_path()` (confirmed via source read) only checks `models/HunyuanWorld-Mirror/{model_name}`, `models/HunyuanWorld-Mirror/{model_name}.safetensors`, and the fixed fallback `models/HunyuanWorld-Mirror/HunyuanWorld-Mirror.safetensors` — a `destination` of `model.safetensors` (matching the real HF filename) would match none of those, silently falling through to treating the model as a live-downloadable Hub repo id every single run.
* **The Fix**: set `destination` to `HunyuanWorld-Mirror/HunyuanWorld-Mirror.safetensors`, matching the node's fixed-fallback candidate exactly, even though that's not the file's real name on HuggingFace.
* **Rule**: `destination` is not just "wherever ComfyUI's folder convention expects this asset type" (§3 rule 2) — it must match the SPECIFIC node's own local-path resolution logic exactly, which is sometimes a fixed filename unrelated to the source repo's real filename. Read the actual node source for its path-resolution function before assuming the HF filename is fine to reuse as `destination`.

---

## 6. Undistilled LTX-2.5 Finetunes: Keep bf16 and Add the Distill LoRA

* **Context (confirmed live, pinkcherry-ltx25, 2026-10-02)**: community LTX-2.5 finetunes can ship as the undistilled DEV checkpoint (PinkCherry: 42GB bf16). Run it with the official distilled LoRA at strength 1.0 (LoraLoaderModelOnly) and the distilled graph (8+3 manual sigmas, euler_ancestral, CFG 1/1) -- it then samples like the distilled model. A real job ran in 107s on an RTX 5090 (fp8-cast run: base 8 steps ~6s at 1.18 it/s after a one-time 33s model init, refine 3 steps ~11s).
* **Quality finding**: casting the bf16 checkpoint to fp8 at load (`UNETLoader.weight_dtype = fp8_e4m3fn`) with the rank-256 community LoRA gave faded, soft output; weight_dtype `default` (bf16) + the official rank-450 LoRA + the conv video VAE was reported "much better". Three changes together -- not isolated.
* **Rule**: for a dev-weights finetune keep bf16 and use the official rank-450 distill LoRA, staged from the ungated `comfyicu/LTX-2.5` mirror (the Lightricks original is gated, see section 4 -- the official LoRA returned 401 again this session). Rename odd HF filenames (e.g. `potatoes.safetensor`) to `.safetensors` in `destination`.

---

## 7. WorldStereo Light: Destinations Are the Loader's Own Local Paths (confirmed live 2026-10-04)

* **Context**: `VNCCS_LoadWorldStereoLightModel` checks these paths under `{ComfyUI}/models/` before any download and logged "Model cached" / "Using local WorldStereo UMT5 encoder" / "Using local WorldStereo Wan VAE" on the first real job, so concept_mapping pre-staged all of it (15.1GB):
  * `WorldStereoLight/vnccs-worldstereo-memory-dmd-int4.safetensors` (8.39GB) + `WorldStereoLight/vnccs-worldstereo-memory-dmd-int4.json`
  * `clip/WorldStereo_umt5-xxl-encoder-fp8.safetensors` (6.27GB)
  * `vae/WorldStereo_wan_2.1_vae.safetensors` (0.47GB)
  * all from `https://huggingface.co/MIUProject/VNCCS_WorldStereoLight/resolve/main/{models,clip,vae}/...` (ungated, 302/307 verified). Registered in `concept_db.json` as `worldstereo-light-memory-dmd`.
* **Left to runtime (small, worked)**: `hanshanxue/WorldStereo` config.json, `Wan-AI/Wan2.1-I2V-14B-480P-Diffusers` aux files (1.2GB), `Ruicheng/moge-2-vitl-normal`. ~6-10s total; pre-staging them isn't needed.

---

## 8. LTX Ripple FFAF IC-LoRA (confirmed live 2026-10-07)

* **Entry**: `ltx-2.5-ripple` in `concept_db.json` -> `https://huggingface.co/WepeNerd/LTX-Ripple/resolve/main/LTX25_Ripple_v11.safetensors` -> `loras/LTX25_Ripple_v11.safetensors` (654,443,392 bytes, ungated; 302->200 verified). Staged by `concept_mapping` and used by a real job (ripple-ltx25 v3, render `39yNVD`).
* **Base files**: reuse the `ltx-2.5-i2v` entries (distilled int8 transformer, Gemma 4 12B text encoder, audio VAE) from the ungated `comfyicu/LTX-2.5` mirror, plus the **conv** video VAE `vae/ltx-2.5-video-vae-conv-bf16.safetensors` (registered under `ltx-2.5-pinkcherry-t2v`). The author's own list links the gated `Lightricks/LTX-2.5` repo; the mirror worked.
* **Rule**: the Ripple LoRA is loaded with a plain `LoraLoaderModelOnly` (strength 1.35); its safetensors header metadata is empty, so no `reference_downscale_factor` exists and `LTXAddVideoICLoRAGuide.latent_downscale_factor` is the literal 1.0. Mind KI-007 section 24 when titling the loader node in the concept_mapping field_mapping string.
