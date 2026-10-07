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
**ComfyUI run time is limited to ~180 seconds** (some grace on top) — stated by Jacob 2026-10-04 and
confirmed by `worldstereo-recon-v1` (R20164194), which logged `SavePLY SUCCESS` and then timed out with no
`Prompt executed` line. The clock starts when ComfyUI starts. Earlier versions of this file said ~380 s;
that (and the ~300 s / ~277 s figures elsewhere) were observed upper bounds, not budgets. **Plan to 180 s,
target <= 150 s.**

### NOT counted (happen before ComfyUI starts)
1. Node repository git cloning & setup (~15–30s)
2. Pip dependency installation (10s – several minutes)
3. `concept_mapping` model downloads
4. First-time machine startup (up to ~2000s)

### Counted (everything after ComfyUI is up)
1. ComfyUI startup to `got prompt` (~15s lean, up to ~80s with heavy node packs)
2. Any model download performed *inside a node* at run time
3. Model weight loading into VRAM (~10–35s per large model)
4. Inference sampling steps
5. VAE/Audio encoding, **post-processing, saving and export** (easy to forget; recon-v1's reconstruction + export
   stages came after inference and pushed it past 180 s)

The clock is **ComfyUI startup (~15–30 s) + the log's `Prompt executed in N seconds`**, so N alone is not the
budget: `worldstereo-recon-v1` (R20164820) logged N = 168.65 s, no errors, and was still flagged `timed_out`
(`success: false`, `files: []`). **Target N <= ~120 s.** The result's `elapsed` is not the number either (it
includes the uncounted pip/clone/download phase).

> [!WARNING]
> Large model downloads (>5GB) **MUST** be staged in `concept_mapping`. Attempting to download multi-gigabyte models inside a node at runtime counts against the ~180 s run-time budget and triggers job cancellations; a `concept_mapping` download happens before the clock starts.

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
