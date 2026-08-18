---
id: "KI-002"
title: "Model Staging & Offline Custom Node Loading Rules"
version: "1.0.0"
type: "guidelines"
tags:
  - concept_mapping
  - model-staging
  - offline-loading
  - custom-nodes
sources:
  - "GRAYDIENT-COMPLETE-REFERENCE.md"
---

# KI-002: Model Staging & Offline Custom Node Loading Rules

## 1. Model Staging (`concept_mapping`)
`concept_mapping` pre-downloads remote model files (HuggingFace, ModelScope, S3) directly into the instance's `{ComfyUI}/models/` directory **before** ComfyUI initializes.

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
- `destination` is relative to `{ComfyUI}/models/`.

---

## 2. Mandatory Offline Loading Rule
> [!IMPORTANT]
> Custom Node Python code **MUST** check for local staged files before making any network calls (`snapshot_download()`, `requests.get()`, `urllib.request()`).

If a node attempts to connect to external sites when files are already present on disk:
- It causes execution delays and network timeouts.
- It risks getting blocked by WAF / network isolation rules on SaaS runners.

### 2.1 Standard Implementation Pattern

```python
import os
import folder_paths
import torch
from diffusers import AudioLDMPipeline

class AudioLDMModelLoader:
    def load_model(self, model_name: str):
        model_path = os.path.join(folder_paths.models_dir, model_name)
        
        # 1. Check if model files were pre-downloaded locally via concept_mapping
        if not os.path.isfile(os.path.join(model_path, "model_index.json")):
            # 2. Fallback to network download ONLY if missing
            if check_huggingface_access():
                download_model_hf(model_path, f"cvssp/{model_name}")
            else:
                download_model_modelscope(model_path, f"cutemodel/{model_name}")

        # 3. Load directly from local disk offline
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32
        model = AudioLDMPipeline.from_pretrained(model_path, torch_dtype=dtype)
        return (model.to(device),)
```
