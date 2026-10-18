# ComfyUI Workflow Reference

Everything learned building production ComfyUI pipelines (image, video, 3D mesh,
audio), reframed for plain local/self-hosted ComfyUI. This is the ComfyUI knowledge
underneath our Graydient work — none of it requires Graydient.

---

## 1. The Two Workflow JSON Formats

ComfyUI has two distinct JSON representations of the same graph. Confusing them is
the single most common source of "why won't this run" bugs.

### Standard / UI format — what you drag into ComfyUI

This is what ComfyUI exports when you click "Save" in the UI, and what it accepts via
drag-and-drop or "Open" onto the canvas.

```json
{
  "last_node_id": 9,
  "last_link_id": 7,
  "nodes": [
    {
      "id": 1,
      "type": "LoadImage",
      "pos": [0, 120],
      "size": [300, 58],
      "order": 0,
      "mode": 0,
      "inputs": [],
      "outputs": [
        {"name": "IMAGE", "type": "IMAGE", "links": [1], "slot_index": 0},
        {"name": "MASK",  "type": "MASK",  "links": [], "slot_index": 1}
      ],
      "title": "Load Image",
      "widgets_values": ["example.png"]
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

- Each node has `"type"` (the node's class name) + canvas position/size +
  `"widgets_values"` array holding whatever's typed/set into that node's widgets.
- `links`: `[link_id, from_node_id, from_slot, to_node_id, to_slot, "TYPE"]`.
- `"order"` is a **display hint only**. ComfyUI executes by graph topology
  (topological sort from the output nodes backward), not by this field.
- `last_node_id` / `last_link_id` should match the highest IDs actually used — the
  UI uses these to know what ID to hand out next if you add a node.

**This is the file you want as a deliverable for another human.** Anyone can drag it
straight into their ComfyUI and see the exact graph, node positions, and all.

### API / prompt format — what you POST to `/prompt`

This is the format ComfyUI's backend actually executes. It's what the "Save (API
Format)" UI option produces, and what any programmatic caller (a Python script, a
hosting layer like Graydient, ComfyUI's own `/prompt` REST endpoint) sends.

```json
{
  "1": {
    "inputs": {"image": "example.png"},
    "class_type": "LoadImage",
    "_meta": {"title": "Load Image"}
  },
  "4": {
    "inputs": {
      "model": ["2", 0],
      "positive": ["3", 0],
      "seed": 42,
      "steps": 20,
      "cfg": 7.0
    },
    "class_type": "KSampler",
    "_meta": {"title": "KSampler"}
  }
}
```

- Nodes are keyed by **string** ID (`"1"`, `"4"` — never bare integers).
- Uses `"class_type"` — there is **no** `"type"` field in this format.
- Widget values *and* linked-input values live together in the same `"inputs"` dict.
- A link is a `["source_node_id_string", output_slot_index]` tuple, e.g.
  `"model": ["2", 0]` means "the MODEL output (slot 0) of node 2".

**Most common mistake**: pasting the standard-format JSON where the API format is
expected. The executor sees `class_type: null` on every node and fails with
`"node X has no class_type"`.

**Second most common mistake**: a `PrimitiveNode` surviving into the API JSON.
`PrimitiveNode` is a UI-only convenience node (lets you expose a shared value to
multiple widgets on the canvas) — it has no backend executor. Replace it with the
literal value directly in whichever node actually consumes it.

### Converting between them

ComfyUI's own UI does this for you (`Save` vs `Save (API Format)` in the menu, or the
"Export API" option under the workflow menu depending on version). If you're hand
building a workflow programmatically, build both from the same node list so they never
drift out of sync — see `comfyui-workflow-porting/SKILL.md` for the pattern we use.

---

## 2. Custom Node Pitfalls

### Name collisions

ComfyUI loads custom node packages alphabetically by folder name. A later-loaded
package **silently overwrites** an earlier one's `NODE_CLASS_MAPPINGS` key if they
share a class name — no error, no warning, just the wrong node code running.

- `LoadImageFromURL` (capital R, capital L) — fine if unique.
- `LoadImageFromUrl` (lowercase r) — collides with `comfyui-art-venture`'s node of
  the same (differently-cased-but-often-normalized) name in some environments.

If you're writing your own custom node, pick a globally distinctive class name and
grep GitHub for it first.

### `LoadImage` and URLs

The built-in `LoadImage` node's `VALIDATE_INPUTS` checks that the given filename
physically exists in ComfyUI's `input/` directory **before the node ever runs**.
Passing it a URL, or a path that doesn't yet exist locally, fails validation at graph
load time with no useful error. If you need to load an image from a URL, use a
dedicated "load from URL" custom node instead (downloads first, then hands ComfyUI a
real local path/tensor) — see `LoadImageFromURL` in §4 below for our implementation.

### `VHS_LoadVideo*` nodes and dropdowns

Several VideoHelperSuite nodes (`VHS_LoadVideo`, `VHS_LoadVideoFFmpeg`) expose their
`video` input as a **COMBO widget** — a dropdown populated from files already present
in ComfyUI's `input/` folder. It cannot receive a URL or arbitrary path as a literal
string; the value has to be one of the enumerated filenames. If your source video
lives at a URL, download it into `input/` first (or use a "load video from URL" node
that does that internally) rather than trying to feed the URL to the dropdown.

### Execution order is topology, not the `order` field

ComfyUI runs nodes in topological order — nodes with no unmet dependencies run first,
regardless of what `"order"` says in the standard-format JSON (that field is purely a
UI hint for redraw order). Practically: if two large model loaders both sit at
dependency depth 0 (nothing feeds into either), ComfyUI may load them concurrently,
which can spike VRAM/RAM during startup. If that's a problem, add an artificial data
dependency (e.g. route a dummy value through one loader into the other) to force
serialization.

### Dot-namespaced class names

Some custom node packages register class names with dots, e.g.
`huchenlei.LoadOpenposeJSON`. A few workflow converters/hosting layers mishandle these
and null out the type on conversion to API format. If you're publishing a node for
others to build workflows around, avoid dots in the class name.

---

## 3. VRAM & Step-Time Math (Diffusion Transformers)

This applies to any transformer-based diffusion model (video or image), not just a
specific pipeline. Useful for sizing what resolution/frame-count/step-count is
actually runnable on a given card before you hit "Queue Prompt" and wait 10 minutes
to find out it OOMs.

### Token / sequence-length formula (video, patch size 16)

```
h_patches = HEIGHT // 16
w_patches = WIDTH  // 16
t_len     = (FRAMES - 1) // 4 + 1        # temporal compression, VAE-dependent — 4 is common (Wan, Hunyuan family)
seq_len   = t_len × h_patches × w_patches
```

Both `WIDTH` and `HEIGHT` must be divisible by 16 for these architectures.

### Step-time scaling (empirical, Wan 2.x-class 14B model, RTX 5090)

```
step_time ≈ 50 × (seq_len / 32760) ^ 1.5   seconds
```

(Baseline: 832×480, 81 frames → seq_len 32,760 → ~50 s/step on a 5090. Scale the
baseline constant for your own card by timing one step at a known resolution.)

| Resolution | seq_len (81f) | step_time | 14 steps total |
|---|---|---|---|
| 832×480 | 32,760 | 50 s | 700 s |
| 640×352 | 18,480 | 20 s | 280 s |
| 512×288 | 12,096 | 11 s | 154 s |
| 432×240 | 8,505 | 6.6 s | 92 s |
| 384×208 | 5,824 | 3.9 s | 55 s |

Cost is roughly cubic in linear resolution (quadratic in pixel count × the seq_len^1.5
exponent) — halving resolution is far more effective than halving step count if
you're time/VRAM constrained.

### Activation VRAM (HunyuanVideo-family, rule of thumb)

Roughly **0.206 MB of activation VRAM per token** (`seq_len` above) during sampling,
on top of the model weights themselves. A 24 GB card with a ~13–15 GB transformer
loaded has only a few GB of headroom before activations spill — spilling shows up as
a sudden slowdown (weights/activations round-tripping through system RAM) rather than
an outright crash if your ComfyUI has any RAM-overflow mechanism enabled; without one,
it OOMs outright.

**Frame-count constraint for 4x-temporal-compression VAEs**: valid frame counts
satisfy `(FRAMES - 1) % 4 == 0` — e.g. 25, 29, 33, 37, ... 81, 85, ... 129.

### Practical guidance

- Always use a **tiled** VAE decode/encode node (e.g. `VAEDecodeTiled`) for video —
  a full-frame decode on 65+ frame sequences OOMs on 24 GB cards even when sampling
  itself fit fine.
- Step-distilled models (FastHunyuan, Bernini/Wan2.2-distilled, etc.) typically want
  `euler` + `sgm_uniform` and CFG close to 1.0–6.0 depending on the specific distill.
  `dpm`/`dpm++` samplers tend to introduce artifacts on step-distilled checkpoints —
  stick to what the model card recommends.
- Native 1080p+ generation is usually infeasible directly on a single consumer GPU for
  these architectures; the standard workaround is generate-low-res → GAN upscale
  (e.g. a 4x ESRGAN-family model) → downscale to target resolution.

---

## 4. Pipeline: Image → 3D Mesh (TripoSG)

### Graph

```
LoadImageFromURL (or LoadImage)
  → TripoSGPrepareImage           (crop to subject, background removal, 10% pad, square)
      → TripoSGInference          (diffusion → raw TRIMESH)
          → BakeVertexColorsFromViews    (project photo colour onto mesh vertices)
              → SaveTrimesh       (write file to disk)
```

Feed the **same** `TripoSGPrepareImage` output into both `TripoSGInference.image` and
`BakeVertexColorsFromViews.front_image` — the UV projection math in the bake node
assumes the exact padding TripoSGPrepareImage applied, so if inference and baking see
different crops, the baked colour misaligns with the mesh.

### Node reference

| class_type | Key inputs/widgets | Notes |
|---|---|---|
| `LoadImage` | filename (COMBO, from `input/`) | Built-in. Use for local files. |
| `TripoSGModelLoader` (custom) | model dropdown | Loads the TripoSG diffusion model; downloads on first use (~10 GB) |
| `TripoSGPrepareImage` (custom) | `image` | Crops, removes background, pads 10%, squares. `pad_ratio=0.1` is baked into the bake node's UV math — don't change independently. |
| `TripoSGInference` (custom) | `model`, `image`, `seed`, `steps`, `cfg` | Outputs `trimesh` + `parts`. **Single-image only** — a list input creates a batch, not multi-view conditioning. |
| `TripoSGConditioning` (custom) | `prompt`, confidences | For the scribble variant of the model; CFG-distilled (`guidance_scale=0` hardcoded internally). |
| `BakeVertexColorsFromViews` (custom) | `trimesh`, `front_image`, `cam_dist`, optional `back_image` | Perspective-correct projection bake. Front/back blended by vertex-normal Z. `cam_dist` default 2.5 — increase if texture looks too zoomed at mesh edges, decrease if stretched. |
| `SaveTrimesh` (custom) | `trimesh`, `filename_prefix`, `file_format` | `file_format` ∈ glb/obj/ply/stl/3mf/dae. |

### Model weights

| Model | Hugging Face repo | Notes |
|---|---|---|
| TripoSG base | `VAST-AI/TripoSG` | ~10 GB, auto-downloads to HF cache on first node run |
| TripoSG scribble | `VAST-AI/TripoSG-scribble` | Sketch-conditioned variant |
| PartCrafter | `wgsxm/PartCrafter` | Multi-part decomposition variant |

### pip requirements

```
diffusers transformers accelerate safetensors trimesh omegaconf scikit-image peft
jaxtyping typeguard pymeshlab opencv-python ninja
```

### Export format reference

| Format | Vertex colours | Best for |
|---|---|---|
| `glb` | ✓ | Games, web, AR, Blender — recommended default |
| `obj` | via MTL sidecar | Universal 3D software compatibility |
| `ply` | ✓ | Research/scanning workflows |
| `stl` | ✗ | 3D printing — geometry only |
| `3mf` | ✓ (slicer-dependent) | Modern 3D printing (PrusaSlicer, Bambu, Orca) |
| `dae` | ✓ | Animation/rigging exchange (Blender, Maya, Cinema4D) |

Not practical without heavy extra native deps: FBX, USDZ, STEP/IGES, BLEND.

---

## 5. Pipeline: Video-to-Video (Bernini / Wan 2.2 14B cascade)

### Graph

```
Load source video (VHS_LoadVideo, or a "load from URL" node → local file)
  → WanAnimatePlus Bernini node       (VAE-encodes source, builds image_embeds, task_type="v2v")
      → Sampler HIGH stage            (Wan22 HIGH fp8 transformer, cfg≈3, steps 0→10, add_noise=True)
          → Sampler LOW stage         (Wan22 LOW fp8 transformer, cfg≈1, steps 10→end, add_noise=False)
              → Decode
                  → VHS_VideoCombine  (writes MP4)
```

Two-stage HIGH→LOW cascade is standard for this model family: the first stage
establishes large-scale structure/motion, the second refines detail. Feeding the
second stage `add_noise=False` and continuing the same sigma schedule (rather than
restarting) is what makes the two samplers act as one continuous denoise rather than
two independent runs.

### Settings that matter

- `attention_mode: "sdpa"` on the model loaders unless you have `sageattn` installed
  (sageattn is faster but an extra native build — sdpa is the safe universal default).
- Resolution/frame-count budget follows the VRAM/step-time math in §3 — 432×240 at
  81 frames (seq_len 8,505) keeps inference well under a minute per step even on
  mid-range cards.

### Model weights

| File | Hugging Face repo | Size |
|---|---|---|
| `Wan22_Bernini_HIGH_fp8_e4m3fn_scaled.safetensors` | `Kijai/WanVideo_comfy_fp8_scaled` (path `Bernini/`) | ~15.6 GB |
| `Wan22_Bernini_LOW_fp8_e4m3fn_scaled.safetensors` | `Kijai/WanVideo_comfy_fp8_scaled` (path `Bernini/`) | ~15.6 GB |
| `Wan2_1_VAE_bf16.safetensors` | `Kijai/WanVideo_comfy` | ~254 MB |
| `umt5-xxl-enc-bf16.safetensors` | `Kijai/WanVideo_comfy` | ~11.4 GB |

Place under `ComfyUI/models/diffusion_models/`, `models/vae/`, `models/text_encoders/`
respectively (standard ComfyUI model-folder conventions — no special staging needed
outside of Graydient's ephemeral containers).

### Required custom node repos

- `wuwukaka/ComfyUI-WanAnimatePlus` — the Bernini pipeline nodes themselves
- `kijai/ComfyUI-WanVideoWrapper` — backend WanAnimatePlus depends on
- `Kosinkadink/ComfyUI-VideoHelperSuite` — video load/combine nodes

---

## 6. Debugging Checklist

**`"node X has no class_type"`**
→ Standard-format JSON was submitted where API format was expected. Confirm the
JSON uses `class_type` (not `type`) and string-keyed nodes.

**`missing_node_type: PrimitiveNode`**
→ `PrimitiveNode` survived into the API-format JSON. Replace with a literal value on
the consuming node.

**OOM at step 1 of the sampler**
→ Activation memory exceeded available VRAM. Reduce resolution first (cubic effect),
then frame count (see §3).

**Model not found / node import fails**
→ Missing custom node package, or the model file isn't in the folder ComfyUI expects
for its type (checkpoints/, diffusion_models/, vae/, text_encoders/, etc.). Check
`ComfyUI/models/` subfolder conventions for the node's model type.

**`No module named 'X'` on a custom node with a compiled extension**
→ The extension wasn't built. Needs `ninja` installed and the package's own
`setup.py build_ext` (or equivalent) run — check the node repo's README for its
specific build step.

**Step time much higher than expected, or VRAM usage jumps mid-run**
→ Check whether weights or activations spilled out of VRAM (visible in ComfyUI's
console as slow loads or a sudden step-time cliff). Reduce resolution/frames, or use
a lower-precision/quantized version of the model if one exists.

**Vertex colours missing from an exported 3D file**
→ STL doesn't store colour at all. Use GLB, PLY, 3MF, or DAE if colour matters.
