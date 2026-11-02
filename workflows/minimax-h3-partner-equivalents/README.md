# MiniMax H3 — local equivalents of the six partner nodes

Six Graydient **backup-restore** workflows, one per capability from the merged PR
`[Partner Nodes] feat(MiniMax): add H3 Max Recast, Extend, Reframe, Insert, Lip Sync and Camera Control nodes`.

**These are local open-weights reconstructions, not the partner nodes.** Every node in the
PR is `is_api_node=True` — cloud-only, billed in comfy.org credits. You chose the local
route, so these graphs reproduce the six capabilities with your staged H3 weights and
consume no partner credits.

| File | Capability |
|---|---|
| `GraydientWorkflow-minimax-h3-recast-v1.json` | Swap the identity in a clip, keep its motion |
| `GraydientWorkflow-minimax-h3-extend-v1.json` | Continue a clip forward |
| `GraydientWorkflow-minimax-h3-reframe-v1.json` | Re-canvas a clip, fill the new borders |
| `GraydientWorkflow-minimax-h3-insert-v1.json` | Replace an interior window of a clip |
| `GraydientWorkflow-minimax-h3-lipsync-v1.json` | Animate a portrait to a speech track |
| `GraydientWorkflow-minimax-h3-camera-control-v1.json` | Orbit / elevate / dolly a still |

Regenerate all six from the repo root:

```bash
python3 templates/gen_minimax_h3_partner_equivalents.py
```

The generator is the source of truth. These six JSONs are explicitly exempted from
the repo's general generated-workflow ignore rule so they can be retrieved from the branch.

---

## Shared architecture

All six are emitted from one node registry, so the model/sampling spine is byte-identical
across the batch — same node IDs, same wiring, same widgets:

- **19 nodes byte-identical in all six:** `119, 120, 121, 127, 128, 130, 140, 141, 142, 143, 144, 145, 148, 171, 172, 317, 318, 319, 320`
- Loaders → TaoMate LoRA → Easy-Use LoRA stack → H3 sigma shift → `SamplerCustomAdvanced` → decode → `CreateVideo` → `SaveVideo`
- Each graph uses its corresponding `FluxdonH3*` preparation node from the
  `fluxdon-local-h3/` custom-node pack. Source loaders and downstream MCR
  trim/assembly remain separate graph nodes.

### Measured similarity — please read

You asked for ~95% identical. Honest numbers, not asserted ones:

| Workflow | Nodes | UI-graph text vs Recast | Whole backup file vs Recast |
|---|---|---|---|
| recast | 25 | 100% | 100% |
| extend | 25 | 78.2% | 88.4% |
| reframe | 24 | 84.7% | 90.0% |
| insert | 24 | 79.8% | 86.8% |
| lipsync | 24 | 85.6% | 89.3% |
| camera-control | 26 | 80.4% | 87.5% |

**~86–90% at the file level, not 95%.** The shared spine is genuinely identical; the
remaining delta is the task-specific nodes and prompt defaults that make each capability
work. Reaching a literal 95% would mean padding every graph with the other five tasks'
unused nodes — that inflates the metric without improving the batch, so I did not do it.
Say the word if you want that anyway.

They are batch-appropriate in the way that matters: one generator, one spine, one asset
set, one requirements list, consistent field names.

---

## Staged assets (all 10, exact node/widget mapping)

| # | Asset | Node · widget | Destination |
|---|---|---|---|
| 1 | `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | 128 · `clip_name` | `text_encoders/` |
| 2 | `minimax_h3_audio_vae_fp32.safetensors` | 120 · `vae_name` | `vae/` |
| 3–7 | **dynamic concept: H3 lora** ×5, weight-mapped | 171 · `lora_1_name` … `lora_5_name` | dynamic |
| 8 | `minimax_h3_video_vae_int8_convrot.safetensors` | 119 · `vae_name` | `vae/` |
| 9 | `TaoMate-H3-3step-ComfyUI.safetensors` | 317 · `lora_name` | `loras/` |
| 10 | `10Eros_Max_h3_8stepTURBO_beta7_SingularityV2_int8HQ.safetensors` | 127 · `unet_name` | `diffusion_models/` |

Loader widgets carry the bare filename; `destination` carries the folder prefix — ComfyUI
resolves each widget relative to its own model folder. This matches the repo's live-proven
templates.

The five LoRA concepts use `type: "local"`, `allow_dynamic: true`, `dynamic_family: "H3"`,
`dynamic_type: "lora"`, with `weight_field_mapping`. Their numeric suffixes
(`12/39, 34/14, 15/17, 27/25, 33/2`) are **Graydient's fixed convention** copied from live
Ltx2/H3 exports — they are not widget indices. All five default to `"None"`, which
Easy-Use skips safely.

## Node-pack requirements

All seven originally requested repos are included, plus
`https://github.com/UnlimitedEditing/fluxdon-local-h3`. **Upload the contents of
`fluxdon-local-h3/` in this branch to the root of that repository first**; its
GitHub requirement cannot install the nodes until the repository contains the
files and is accessible to Graydient. The pack also needs a recent ComfyUI with
built-in H3 support. `requirements.pip` is
deliberately **`[]`** — `opencv-python` / `imageio-ffmpeg` pin `numpy` 1.26.4 under a SciPy
that needs ≥2 and crash ComfyUI on import.

```
rgthree/rgthree-comfy                        yolain/ComfyUI-Easy-Use
WASasquatch/was-node-suite-comfyui           Kosinkadink/ComfyUI-VideoHelperSuite
DoctorDiffusion/ComfyUI-MediaMixer           seitanism/ComfyUI-H3-Motion-Context-MultiRef
BitVectorApp/comfyui-optional-asset-loader
```

---

## Controls

Shared by all six: `prompt_positive`, `seed`, `steps`, `strength`, `width`, `height`.

`strength`, `width` and `height` each map to **one** primitive (`318`, `319`, `320`) fanned
out over real links. This is deliberate: mapping one `local_field` to two widgets is
unverified on Graydient, and a split `width` would desynchronise reframe's pad from its
canvas. `strength` drives both `strength_model` and `strength_clip`, so `0` is a true bypass.

| Workflow | Extra controls |
|---|---|
| recast | `init_video_filename`, `image1` (new identity, required), `image2` (optional), `length` |
| extend | `init_video_filename`, `slot2` = preserved context frames, `length` (total) |
| reframe | `init_video_filename`, `length` |
| insert | `init_video_filename`, `slot1` = insert frame, `slot2` = window length, `length` (total) |
| lipsync | `image1` (portrait), `init_audio_filename` — **length is derived from the audio** |
| camera-control | `image1`, `slot1` = azimuth°, `slot2` = elevation°, `slot3` = dolly ×, `length` |

H3 runs at **24 fps**; canvas is a multiple of 32; frame counts snap to the `17k+5` grid.
Source clips should be constant 24 fps (the loader forces the rate).

---

## Caveats — validation status

**No live Graydient render has been run.** Every check below is static. Treat first render
as a smoke test.

What passed, for all six:
- Graydient linter: **0 errors, 0 warnings**
- Generator structural check: **0 problems** (link/slot validity, topo order, no orphans)
- CPU-only mock tests for all six custom-node implementations and their generated
  graph input/output contracts; no actual H3 execution was tested.
- Field indices, duplicate mappings, ten asset concepts, the new repository
  requirement and empty pip list are covered by the tests.

Known limitations:
- **Reframe is guide-based**, not true masked outpainting. Current ComfyUI has no
  single-node border-mask source (`ImagePadForOutpaint` is gone; `PadImageNode` returns no
  MASK). The source is letter/pillar-boxed and used as a guide while H3 fills the borders —
  centre pixels are steered, not guaranteed pixel-exact.
- **Lip sync is prompt+audio-guided H3**, not a dedicated lip-sync model. Expect approximate
  sync. The source speech is passed to the output mux rather than VAE-round-tripped.
  Video length is capped at 243 frames; longer speech may outlast the generated video.
- **Extend / insert** use the MCR context → trim → assemble path to retain
  source content. Encoding the final output can change pixels/audio; this has
  not been verified by a live render.
- **Steps default to 4 at strength 1.0.** The base UNET is an 8-step TURBO merge and TaoMate
  is a 3-step LoRA; that combination is untested. If motion looks overcooked, try
  `strength 0` + `steps 8` to fall back to the base model's own schedule.
- `avg_elapsed` is set to 150 s against the platform's 180 s budget — unmeasured.

## Restoring

First upload `fluxdon-local-h3/` to the repository named above. The six backups
reference it but cannot install the pack while that repository is empty.


Restoring **un-publishes** the workflow, and restoring under an existing slug can leave a
duplicate where the slug still resolves to the old one. Restore, then re-list and confirm
the slug points at the new ID before rendering.

Nothing here has been deployed or published.
