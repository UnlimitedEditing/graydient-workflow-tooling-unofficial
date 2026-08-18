---
id: "KI-005"
title: "SaaS Execution Constraints, VRAM & Timeout Budgets"
version: "1.0.0"
type: "constraints"
tags:
  - saas-constraints
  - vram-budget
  - timeout
  - dynamicvram
sources:
  - "GRAYDIENT-COMPLETE-REFERENCE.md"
---

# KI-005: SaaS Execution Constraints, VRAM & Timeout Budgets

## 1. Execution Timeout Budget
The total execution timeout budget per job on Graydient is **~380 seconds**.

### Budget Components
1. Node repository git cloning & setup (~15–30s)
2. Pip dependency installation (~10–30s)
3. Model weight loading into VRAM (~10–20s)
4. Inference sampling steps
5. VAE/Audio encoding & saving

> [!WARNING]
> Large model downloads (>5GB) **MUST** be staged in `concept_mapping`. Attempting to download multi-gigabyte models at runtime will consume the timeout budget and trigger job cancellations.

---

## 2. VRAM & Memory Allocation Rules
- Target typical runner GPUs (e.g. RTX 4090 24GB or RTX 5090 32GB).
- Keep total weight VRAM + activation memory below 20GB to prevent OOM errors.
- Support `float16` or `bfloat16` precision for CUDA execution; fall back to `float32` on CPU.
- Utilize `comfy-aimdo` (DynamicVRAM) when managing multi-model pipelines.

---

## 3. Custom Node & Requirement Rules
- List repository dependencies under `requirements.github`.
- List PyPI packages under `requirements.pip` using plain package names without strict version caps unless required.
- Do not re-list base packages already present in standard ComfyUI (`torch`, `torchvision`, `numpy`, `Pillow`).
