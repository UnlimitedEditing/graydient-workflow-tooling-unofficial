#!/usr/bin/env python3
"""
H3 Regen 2K -- STAGE 2 of the chained MiniMax H3 build: NVIDIA Open-H3-Regenerate-2K + Sol-Attn.

Takes ONE finished low-res draft video (e.g. the output of stage 1, gen_h3_ref_draft.py /
`h3-ref-draft`) and regenerates it natively at 2560x1440 in 3 Euler steps, with the fast H3 VAE
decoder, and returns an mp4 with the draft's own soundtrack.

Derived from the 2026-10-28 `MinimaxH3_2Stage-NVRegen2k` ComfyUI graph (its "2nd Stage Upscale" /
"Decode 2" groups) -- see DEVIATIONS below.

--------------------------------------------------------------------------------------------
PREFLIGHT (preflight-plan / KI-009) -- what was checked, and what is still UNVERIFIED
--------------------------------------------------------------------------------------------
INTENT  : draft video in -> 2K H3 video out, NVIDIA's open regenerate recipe + Sol-Attn.
VEHICLE : port to Graydient as its own workflow, chained after stage 1 (user choice, 2026-11-02).

Checked against sources, not memory:
  * `python wf.py search` for MiniMax H3 / NVRegen / sol upscale: no Graveyard entry; no staged H3 weights
    existed in concept_db.json (added here as `h3-regen2k`).
  * Node signatures read from SOURCE cloned 2026-11-02:
      - rdh9616/ComfyUI-Open-H3-Regenerate @ 9b686c5 : OpenH3RegenLora / PrepareDraft / Upscale /
        RefineLatent / Sigmas / FastVAEDecode / Finish; its example workflow
        "Open-H3 Regenerate 2K - Draft Video.json" is the wiring used below.
      - LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler : node `MinimaxH3LatentUpscaler3D`,
        accepts .safetensors from models/latent_upscale_models.
      - ComfyUI core comfy_extras/nodes_sparse_attention.py @ bb878b9 : BlockSparseAttention is a
        DynamicCombo, so API keys are `selection` + `selection.tau`.
  * Pure-Python rule (KI-007 sec 1): pack deps are `av`, `safetensors` only; no flash-attn / sage /
    compiled kernels. NOTE `ck.sol_attn` comes from ComfyUI core (comfy_kitchen): it needs a
    Graydient ComfyUI new enough to ship BlockSparseAttention (pack says tested on 0.42.0; KI-007
    sec 38 shows Graydient already runs 0.42).
  * RMBG / Easy-Use flush nodes: not in this stage (no reference image; separate job = no VRAM to flush).

NOT verified (Hugging Face is blocked from the authoring sandbox -- every URL below is from the
README / the user's own files, not fetched): file existence, sizes, gated flags. See concept_db.json
`_status` fields. Before deploying run `curl -sI <url>` on each and check
https://huggingface.co/api/models/<repo> for "gated" (KI-008 sec 4).

--------------------------------------------------------------------------------------------
KNOWN RISKS (read before spending quota)
--------------------------------------------------------------------------------------------
1. RUN BUDGET (KI-005): the README measured 122 s refine + 24 s decode for a 5 s clip at 2K on a
   72 GB Blackwell. Graydient runners are 24-32 GB and the ~180 s clock includes model loading.
   This will very likely OOM or time out at 2K. `max_frames` is exposed as slot4 so a first test
   can use e.g. 49 frames; lower the `resolution` widget in the graph (node 11) to "1080p (1920x1080)"
   for a first live test.
2. VRAM: the fast VAE decoder is ~20 GB peak for 5 s at 2K. Node 19 gets the H3 video VAE as its
   `vae` fallback so an oversized clip decodes tiled instead of failing.
3. Staged weight is very large (LoRA 12.4 GB + decoder 6.5 GB + two int8 checkpoints + text encoder).
   It is staged BEFORE the clock (KI-005 sec 1), but disk/download time is real.
4. No width/height field mapping: output size is set by the `resolution` widget, not by /size.
   KI-003 sec 3.4 says width/height are mandatory on visual-output workflows -- the linter decides.
5. KI-007 sec 37: newlines collapse in prompt fields. H3 prompts are multi-line (subject_definitions /
   [Shot N] / overall_soundscape); the default prompt is a single paragraph for that reason.

DEVIATIONS from the 2026-10-28 graph (all deliberate):
  * The 2-stage in-graph hand-off is replaced by the chain: stage 1 is a separate job, so the draft
    arrives as a VIDEO (LoadVideo -> VAEEncode), not as a live latent.
  * MMH3UltimateUpscale + MMH3 Split Params are replaced by the NVIDIA recipe (OpenH3RegenUpscale ->
    RefineLatent -> 3 Euler steps). The user's own file loads the NVIDIA LoRA with a plain
    LoraLoaderModelOnly, but that file is Diffusers-keyed and would load silently as a no-op --
    OpenH3RegenLora (user choice 2026-11-02) converts the keys and installs the sharp curve branches.
  * Base model is the reference FL2VA pruned int8 (the pack's tested base), not the Singularity finetune.
  * Sol-Attn uses the pack's recipe values (tau 1.2, 0.0-0.9, dense blocks 0,1,49), not the
    draft-stage values (tau 1.3, 0.2-1.0) from the user's graph.
  * No OpenH3SaveRefinedLatent (writes extra files to output/; Graydient's output-picker, KI-007 sec 10).
  * Output is CreateVideo + SaveVideo (the confirmed Graydient pattern), not VHS_VideoCombine.

Outputs: GraydientWorkflow-h3-regen2k-v1.json  (+ plain ComfyUI h3-regen2k-v1.json / -api.json)
"""

import os

from graydient_builder import GraydientWorkflow, stage_model
from gen_h3_common import (FLAGS_OFF, build_api, build_standard, fm, write_json)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONCEPT_KEY = "h3-regen2k"

DEFAULT_PROMPT = (
    "A natural, high-quality video that preserves the content, layout and motion of the draft, "
    "with crisp fine detail in faces, skin, fabric, hair and foliage, soft natural light and a "
    "shallow, breathing depth of field."
)

DESCRIPTION = """\
H3 Regen 2K: send a finished low-resolution draft video (an H3 render from the h3-ref-draft stage, or any 384p-768p clip) and get it regenerated natively at 2560x1440 in three diffusion steps with NVIDIA's Open-H3-Regenerate-2K recipe, Sol-Attn sparse attention and the fast H3 VAE decoder. Layout and motion come from the draft; the refine redraws faces, fabric, fur and foliage at full size. The draft's own soundtrack is kept.

Telegram / API:
/run:h3-regen2k [prompt] - reply to (or attach) the draft video, optionally describe it
/video1:URL - the draft video, if you are not replying to one
/slot4:121 - max frames used from the draft (default 121 = 5 s at 24 fps; 17k+5 grid: 49, 85, 121...)
/slot5:0 - start sigma (0 = NVIDIA's release recipe; 0.8 stays closer to the draft and avoids identity drift)
/seed:42 - reproducible seed

Known limits: very heavy. A 5 s 2K clip needs a large GPU; if a run times out lower /slot4 first.
Weights: Comfy-Org/MiniMax-H3, Efficient-Large-Model/Open-H3-Regenerate-2K (NVIDIA), LBH-123-AI latent upscaler - each under its own license. Nodes: rdh9616/ComfyUI-Open-H3-Regenerate, LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler. Not an official MiniMax or NVIDIA product.
"""

NOTE = (
    "H3 Regen 2K (stage 2). Install custom nodes: rdh9616/ComfyUI-Open-H3-Regenerate and "
    "LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler. Weights: see concept_db.json 'h3-regen2k'. "
    "Load a draft video in node 7. Lower node 11 resolution to 1080p for a first test."
)

REGEN_RES = "2k (2560x1440)"


def nd(id, type, title, pos, inputs, widgets, outputs, wdefault=None, size=None):
    return {"id": id, "type": type, "title": title, "pos": pos, "size": size or [340, 160],
            "inputs": inputs, "widgets": widgets, "outputs": outputs, "wdefault": wdefault or {}}


NODES = [
    nd(1, "UNETLoader", "Load H3 FL2VA (pruned int8)", [30, 60],
       {"unet_name": "minimax_h3_fl2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"},
       ["unet_name", "weight_dtype"], [("MODEL", "MODEL")]),
    nd(2, "OpenH3RegenLora", "Open-H3 Regen LoRA + Sharp curves", [30, 260],
       {"model": [1, 0],
        "lora_name": "open_h3_regenerate_2k_lora.safetensors",
        "curve_name": "sharp_curve_branches.safetensors",
        "curve_table": "minimax_h3_ref2va_pruned_int8_convrot.safetensors",
        "strength": 1.0, "curve_strength": 1.0, "lora_dtype": "bf16"},
       ["lora_name", "curve_name", "curve_table", "strength", "curve_strength", "lora_dtype"],
       [("model", "MODEL"), ("report", "STRING")]),
    nd(3, "BlockSparseAttention", "Sol-Attn (sparse attention)", [30, 520],
       {"model": [2, 0], "selection": "sol-attn", "selection.tau": 1.2,
        "start_percent": 0.0, "end_percent": 0.9, "dense_blocks": "0,1,49",
        "min_tokens": 12288, "extra_tokens": 256,
        "sink_conditioning": "exact_kv_and_rows", "verbose": False},
       ["selection", "selection.tau", "start_percent", "end_percent", "dense_blocks",
        "min_tokens", "extra_tokens", "sink_conditioning", "verbose"],
       [("MODEL", "MODEL")]),
    nd(4, "CLIPLoader", "Load Qwen3-VL text encoder", [400, 60],
       {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "type": "minimax", "device": "default"},
       ["clip_name", "type", "device"], [("CLIP", "CLIP")]),
    nd(5, "VAELoader", "Load H3 video VAE", [400, 220],
       {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}, ["vae_name"], [("VAE", "VAE")]),
    nd(6, "VAELoader", "Load H3 audio VAE", [400, 340],
       {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}, ["vae_name"], [("VAE", "VAE")]),
    nd(7, "LoadVideo", "Draft video", [780, 60],
       {"file": "draft.mp4"}, ["file"], [("VIDEO", "VIDEO")]),
    nd(8, "GetVideoComponents", "Get video components", [780, 200],
       {"video": [7, 0]}, [],
       [("images", "IMAGE"), ("audio", "AUDIO"), ("fps", "FLOAT")]),
    nd(9, "OpenH3RegenPrepareDraft", "Prepare draft", [780, 340],
       {"images": [8, 0], "size": "768p (1344x768)", "max_frames": 121, "source_fps": [8, 2]},
       ["size", "max_frames", "source_fps"],
       [("images", "IMAGE"), ("frame_count", "INT"), ("width", "INT"), ("height", "INT")],
       wdefault={"source_fps": 24.0}),
    nd(10, "VAEEncode", "Encode draft", [780, 540],
       {"pixels": [9, 0], "vae": [5, 0]}, [], [("LATENT", "LATENT")]),
    nd(11, "OpenH3RegenUpscale", "Latent upscale (LBH 3D)", [1160, 60],
       {"latent": [10, 0], "model_name": "minimax_h3_latent_upscaler_3d_conv_v1_bf16.safetensors",
        "resolution": REGEN_RES, "precision": "bf16", "temporal_chunking": False},
       ["model_name", "resolution", "precision", "temporal_chunking"],
       [("latent", "LATENT"), ("width", "INT"), ("height", "INT")]),
    nd(12, "OpenH3RegenRefineLatent", "Refine latent (silent audio)", [1160, 260],
       {"latent": [11, 0], "audio_mode": "silence (reference)", "audio_vae": [6, 0]},
       ["audio_mode"], [("latent", "LATENT"), ("frame_count", "INT")]),
    nd(13, "OpenH3RegenSigmas", "Regen sigmas (3 steps)", [1160, 440],
       {"steps": 3, "start_sigma": 0.0}, ["steps", "start_sigma"], [("SIGMAS", "SIGMAS")]),
    nd(14, "RandomNoise", "Noise", [1160, 580],
       {"noise_seed": 1766580932}, ["noise_seed", "control_after_generate"], [("NOISE", "NOISE")]),
    nd(15, "KSamplerSelect", "Sampler", [1540, 60],
       {"sampler_name": "euler"}, ["sampler_name"], [("SAMPLER", "SAMPLER")]),
    nd(16, "CLIPTextEncode", "Prompt", [1540, 200],
       {"clip": [4, 0], "text": DEFAULT_PROMPT}, ["text"], [("CONDITIONING", "CONDITIONING")]),
    nd(17, "BasicGuider", "Guider (CFG 1)", [1540, 420],
       {"model": [3, 0], "conditioning": [16, 0]}, [], [("GUIDER", "GUIDER")]),
    nd(18, "SamplerCustomAdvanced", "Refine sampler", [1540, 540],
       {"noise": [14, 0], "guider": [17, 0], "sampler": [15, 0], "sigmas": [13, 0], "latent_image": [12, 0]},
       [], [("output", "LATENT"), ("denoised_output", "LATENT")]),
    nd(19, "OpenH3RegenFastVAEDecode", "Fast VAE decode (StreamRender-H3)", [1920, 60],
       {"samples": [18, 0], "vae_name": "fast_h3_vae_noncausal_24l.safetensors",
        "keep_loaded": False, "vae": [5, 0]},
       ["vae_name", "keep_loaded"], [("IMAGE", "IMAGE")]),
    nd(20, "OpenH3RegenFinish", "Finish frames", [1920, 240],
       {"images": [19, 0], "frame_count": [9, 1],
        "crop": "auto (1088 -> 1080, 2176 -> 2160)", "audio": [8, 1]},
       ["frame_count", "crop"], [("images", "IMAGE"), ("audio", "AUDIO")],
       wdefault={"frame_count": 121}),
    nd(21, "CreateVideo", "Create video", [1920, 440],
       {"images": [20, 0], "audio": [20, 1], "fps": 24.0}, ["fps"], [("VIDEO", "VIDEO")]),
    nd(22, "SaveVideo", "Save video", [1920, 600],
       {"video": [21, 0], "filename_prefix": "video/open_h3_regen_2k", "codec": "auto", "format": "auto"},
       ["filename_prefix", "format", "codec"], []),
]
GROUPS = [
    ("1. Models + Regen LoRA + Sol-Attn", [16, -10, 740, 800], "#3f789e"),
    ("2. Draft in / prepare / encode", [766, -10, 380, 760], "#8A8"),
    ("3. Upscale + refine setup", [1146, -10, 380, 760], "#b58b2a"),
    ("4. Sample", [1526, -10, 380, 760], "#a1309b"),
    ("5. Decode + save", [1906, -10, 380, 760], "#88A"),
]


def api_graph():
    api = build_api(NODES)
    # build_api copies inputs verbatim; links are [id, slot] with INT ids -> API wants string ids
    for spec in api.values():
        for k, v in spec["inputs"].items():
            if isinstance(v, list):
                spec["inputs"][k] = [str(v[0]), v[1]]
    return api


api = api_graph()
standard = build_standard(NODES, GROUPS, NOTE)

wf = GraydientWorkflow(name="h3-regen2k-v1", description=DESCRIPTION)
wf.author = "UnlimitedEditing"
wf.set_workflows(standard, api)
stage_model(wf, CONCEPT_KEY)
wf.add_github_requirement("https://github.com/rdh9616/ComfyUI-Open-H3-Regenerate")
wf.add_github_requirement("https://github.com/LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler")
# pip deliberately empty: the pack needs `av` + `safetensors` only, both already present (KI-007 sec 17
# shows PyAV in the runner image); adding them risks a numpy/av downgrade (KI-007 'VHS pip deps').

wf.field_mapping = [
    fm("prompt_positive", 16, "text", 0, "Prompt", default_value=DEFAULT_PROMPT,
       help_text="Optional description of the clip in H3 style (summary / [Shot N] / soundscape). "
                 "Newlines collapse in Graydient prompt fields (KI-007 sec 37), so write one paragraph."),
    fm("init_video_filename", 7, "file", 0, "Draft video", default_value="draft.mp4",
       help_text="The low-resolution draft video (reply to it in Telegram)."),
    fm("video1", 7, "file", 0, "Draft video", default_value="draft.mp4",
       help_text="The draft video supplied as /video1:URL; Graydient stages it into input/."),
    fm("seed", 14, "noise_seed", 0, "Noise", default_value=1766580932,
       help_text="Random seed (NVIDIA's reference seed by default)."),
    fm("slot4", 9, "max_frames", 1, "Prepare draft", default_value=121, minimum_value=5, maximum_value=361,
       help_text="Max frames taken from the draft (121 = 5 s at 24 fps). Lower this first if a run times out."),
    fm("slot5", 13, "start_sigma", 1, "Regen sigmas", default_value=0.0, minimum_value=0.0, maximum_value=0.95,
       help_text="0 = NVIDIA's release recipe (start sigma 0.909). 0.8 stays closer to the draft."),
]

wf.avg_elapsed = None  # no live render yet
wf.metadata.update(FLAGS_OFF)
wf.metadata.update({"supports_vid2vid": True, "peak_vram_usage": 24000})  # estimate, NOT measured

if __name__ == "__main__":
    write_json(os.path.join(BASE_DIR, "h3-regen2k-v1.json"), standard)
    write_json(os.path.join(BASE_DIR, "h3-regen2k-v1-api.json"), api)
    wf.save(os.path.join(BASE_DIR, "GraydientWorkflow-h3-regen2k-v1.json"))
    print(f"Graph: {len(api)} API nodes, {len(standard['nodes'])} standard nodes, "
          f"{standard['last_link_id']} links; {len(wf.concept_mapping)} staged files.")
