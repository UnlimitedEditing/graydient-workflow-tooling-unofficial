---
id: "KI-004"
title: "Custom Node Decoupling: ModelLoader + Sampler Architecture"
version: "1.0.0"
type: "architecture"
tags:
  - node-decoupling
  - model-loader
  - sampler
  - performance
sources:
  - "COMFYUI-REFERENCE.md"
  - "GRAYDIENT-COMPLETE-REFERENCE.md"
---

# KI-004: Custom Node Decoupling: ModelLoader + Sampler Architecture

## 1. The Monolithic Node Problem
Monolithic nodes perform model downloading, loading, and sampling in a single function call.
In SaaS serverless environments, monolithic nodes force model re-instantiation on every inference run, causing VRAM thrashing and high execution latency.

---

## 2. Decoupled Architecture Pattern
Always split monolithic node implementations into two separate custom nodes:

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

### 2.1 Benefits
1. **Model Memory Caching**: ComfyUI caches node outputs. The model is loaded into VRAM once by `ModelLoader` and reused across subsequent sampling runs.
2. **Clean Field Mapping**: User controls (`prompt`, `steps`, `sample_rate`, `guidance_scale`) map directly to `Sampler` input widgets without tangling loader parameters.
3. **Offline Reliability**: The model loader checks local staged files before downloading, guaranteeing offline 0-second loading.
