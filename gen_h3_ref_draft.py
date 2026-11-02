#!/usr/bin/env python3
"""
H3 Ref Draft -- STAGE 1 of the chained MiniMax H3 build: one character reference image (+ RMBG
background clean-up) + a structured H3 prompt -> a low-resolution draft video WITH audio.
Feed its output into stage 2 (`h3-regen2k`, gen_h3_regen2k.py) for the NVIDIA 2K regenerate.

Derived from the 2026-10-28 `MinimaxH3_2Stage-NVRegen2k` ComfyUI graph (its "Models", "Conditioning",
"User Inputs", "LoRAs", "Patches" and "1st Sampling" groups).

--------------------------------------------------------------------------------------------
PREFLIGHT (preflight-plan / KI-009)
--------------------------------------------------------------------------------------------
INTENT  : reference image + prompt -> short H3 draft video with soundtrack (the first half of the user's
          two-stage graph), sized for the stage-2 regenerate.
VEHICLE : the user's own node chain, kept, with the platform-hostile pieces swapped out.

Kept from the user's graph: MiniMaxH3ReferenceToVideo, MiniMaxH3SigmaShift (12 / 3), core
BlockSparseAttention (sol-attn, tau 1.3, 0.2-1.0), KJNodes MiniMaxChunkFeedForward (2 / 4096),
RMBG (1038lab/ComfyUI-RMBG, background "Color" #c7c7c7), ImageResizeKJv2 (crop), and euler/simple 8-step sampling. (The duration->length math was collapsed, see RISKS.)

RMBG (user's call, 2026-11-02: the weights are mirrored in their HF bucket Jacob121294/RMBG-2.0-bucket):
  * Read from SOURCE (ComfyUI-RMBG py/AILab_RMBG.py): the node's own downloader pulls `1038lab/RMBG-2.0`
    and considers the model present iff models/RMBG/RMBG-2.0/{config.json, model.safetensors,
    birefnet.py, BiRefNet_config.py} all exist. Staging exactly those four from the bucket via
    concept_mapping means nothing is downloaded inside the ~180 s clock (KI-005) and no gated repo is hit.
  * The pack loads every module in try/except and RMBG needs only torch/PIL/torchvision/numpy/
    huggingface_hub, so `requirements.pip` stays empty despite the pack's long requirements.txt
    (groundingdino/onnxruntime-gpu etc. are for other nodes -- compiled deps would trip KI-007 sec 1).
  * UNVERIFIED: the HF *bucket* resolve-URL form used in concept_db.json (`.../buckets/<ns>/<name>/resolve/<file>`).
    HF is blocked from the authoring sandbox. Test with `curl -sI` first; if it 404s, mirror the 4 files
    into a normal model repo and swap the host/path only.

Dropped from the user's graph, deliberately (each is a decision the user can reverse):
  * easy cleanGpuUsed / clearCacheAll : they flush VRAM between stage 1 and 2 inside one job; here the
    stages are separate jobs.
  * PathchSageAttentionKJ + MiniMaxH3MemoryEfficientSageAttentionPatch : sageattention is a compiled
    dependency (KI-007 sec 1); sol-attn already covers the speed-up. ModelPatchTorchSettings skipped.
  * Turbo 4-step LoRA, r34l1sm realism LoRA (and its trigger-word StringConcatenate): no source URL was
    given for either. The base here is the user's own pasted `10Eros_Max_h3_8stepTURBO_beta7_SingularityV2_int8HQ`
    (8-step turbo baked in, 8 steps matches the user's scheduler), taken from their live singularity2b7-h3.
  * VHS_VideoCombine : replaced by CreateVideo + SaveVideo (confirmed Graydient pattern; avoids the 3-file
    output-picker trap, KI-007 sec 10). Stage-1 preview combine removed.
  * Set/Get nodes: virtual in the canvas, resolved to direct links.

KNOWN RISKS
  * NO in-graph size/length clamp. The user's graph derived width/height/length with PrimitiveInt /
    PrimitiveFloat + ComfyMathExpression; the repo linter (UI_ONLY_CLASSES) rejects Primitive* nodes in the
    API graph, so `width`/`height` map straight onto the ReferenceToVideo + resize widgets and `slot4` is
    FRAMES (17k+5 grid), not seconds. A /size that is not a multiple of 32, or a length off the grid, is NOT
    corrected (KI-007 sec 44 wants the clamp in the graph). A snapping node that is not a Primitive*
    (e.g. a glue node) would be the fix if this bites.
  * MiniMaxChunkFeedForward / ImageResizeKJv2 widget names come from the user's saved graph (KJNodes
    1.5.0), not from source -- KJNodes was not cloned this session.
  * Every weight URL except the RMBG four is the user's own (pasted live-workflow list); none were fetched.
  * Default prompt keeps the user's multi-line H3 format; newlines collapse when the prompt arrives via
    Telegram/API (KI-007 sec 37).

Outputs: GraydientWorkflow-h3-ref-draft-v1.json  (+ plain ComfyUI h3-ref-draft-v1.json / -api.json)
"""

import os

from graydient_builder import GraydientWorkflow, stage_model
from gen_h3_common import (FLAGS_OFF, build_api, build_standard, fm, write_json)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONCEPT_KEY = "h3-ref-draft"

DEFAULT_PROMPT = (
    "subject_definitions:\n<Subject 1> is the young woman whose appearance comes from <Picture 1>, with long, "
    "straight powder-blue hair with blunt bangs falling past her waist, a thin silver necklace, a white "
    "off-shoulder bandeau top, black high-waisted wide-leg trousers with a slim black belt, and white low-top "
    "sneakers.\n\nsummary:\n[reference generation] The target video is a warm lifestyle short of <Subject 1> "
    "spending an off-duty afternoon in the city: pulling a record from a crate in a vinyl shop, walking a "
    "tree-lined street in dappled light, and settling at a cafe window with a warm cup, all shot in soft "
    "natural light with gentle camera drift.\n\nretention_analysis:\n<Subject 1> (appears in [Shot 1], "
    "[Shot 2], [Shot 3]): fully_preserved - her powder-blue straight hair with blunt bangs, thin silver "
    "necklace, white off-shoulder bandeau top, black wide-leg trousers with slim belt, and white sneakers are "
    "retained across all shots.\n\ndetailed_description:\nThe target video uses a natural-light lifestyle film "
    "style with warm cream tones, soft window glow and a shallow, breathing depth of field.\n[Shot 1] A close "
    "shot at a record shop crate. <Subject 1>'s fingers walk slowly along the inner sleeves of vinyl records, "
    "the powder-blue hair falling forward past her cheek, blunt bangs brushing her lashes as she leans in to "
    "read a spine. The camera pushes in with small amplitude at slow speed; her fingertips stop, hook one "
    "sleeve, and draw a record halfway out of the crate, her thin necklace swinging a little as she "
    "straightens. Warm tungsten shop light rims the blue of her hair.\n[Shot 2] At 00:03.000, the shot cuts to "
    "a full-body street view. <Subject 1> walks toward the camera down a quiet tree-lined lane, the wide legs "
    "of her black trousers swaying over the white sneakers with each unhurried step, sunlight dappling through "
    "the leaves in slow-moving patches across the fabric. She lifts one hand and tucks the long blue hair "
    "behind her ear, then lets it fall again, and the camera tracks backward at a steady walking pace, keeping "
    "her centered as a soft lens flare drifts past her shoulder.\n[Shot 3] At 00:05.500, the shot cuts to an "
    "intimate close framing by a cafe window. <Subject 1> sits sideways on a wooden stool, both feet flat on "
    "the floor, knees together, her weight easy on the stool's edge, the record from the first shot resting on "
    "the small table beside a warm cup. She wraps both hands around the cup, lifts it an inch, and turns her "
    "gaze from the window to the lens with a small, unhurried smile; dust motes drift through the shaft of "
    "afternoon light across her bare shoulders and the white bandeau top. The camera arcs gently around her at "
    "slow speed and settles as she lowers the cup back to the saucer with a soft click.\nThe whole clip "
    "breathes at a lazy afternoon pace, cuts soft and late on the beat.\n\noverall_soundscape:\nThe dry slide "
    "of record sleeves in a crate, muffled street ambience with distant bicycle bells and leaf rustle, a cup "
    "settling onto a saucer, and low cafe chatter through warm room tone.\n\nnon_diegetic_music:\nA mellow "
    "lo-fi chill beat at 82 BPM: soft piano chords, brushed snare, warm vinyl crackle, holding one gentle "
    "level from first frame to last."
)

DESCRIPTION = """\
H3 Ref Draft: send ONE character reference image and a structured MiniMax H3 prompt and get a short low-resolution draft video with its own soundtrack. The reference is background-cleaned with RMBG-2.0 first so the character is kept without its backdrop. Use the result as the input to h3-regen2k for the NVIDIA 2K regenerate.

Telegram / API:
/run:h3-ref-draft [prompt] - reply to (or attach) the character reference, then paste an H3-style prompt (refer to the character as <Subject 1> / <Picture 1>)
/image1:URL - the reference, if you are not replying to an image
/size:864x480 - draft size. Use multiples of 32 (NOT snapped). 864x480 is the draft size from the source graph
/slot4:121 - frames at 24 fps (default 121 = ~5 s). Must be on H3's 17k+5 grid: 22, 39, 56, ... 121, 138, ...
/steps:8 - sampling steps (default 8; the staged model is an 8-step turbo)
/seed:43 - reproducible seed

Known limits: the base is an 8-step TURBO merge, so more steps will not add quality. Newlines collapse in Graydient prompts; write the H3 sections as one paragraph. Weights: Comfy-Org/MiniMax-H3, OliviaRossi/Minimax-h3_Singularity-x-10Eros-Max_PRISM, RMBG-2.0 - each under its own license. Not an official MiniMax product.
"""

NOTE = (
    "H3 Ref Draft (stage 1). Custom nodes: kijai/ComfyUI-KJNodes, 1038lab/ComfyUI-RMBG. RMBG-2.0 files go in "
    "models/RMBG/RMBG-2.0/ (config.json, model.safetensors, birefnet.py, BiRefNet_config.py). "
    "Output feeds h3-regen2k."
)


def nd(id, type, title, pos, inputs, widgets, outputs, wdefault=None, size=None):
    return {"id": id, "type": type, "title": title, "pos": pos, "size": size or [340, 160],
            "inputs": inputs, "widgets": widgets, "outputs": outputs, "wdefault": wdefault or {}}


NODES = [
    nd(1, "UNETLoader", "Load H3 (Singularity x 10Eros 8-step)", [30, 60],
       {"unet_name": "10Eros_Max_h3_8stepTURBO_beta7_SingularityV2_int8HQ.safetensors", "weight_dtype": "default"},
       ["unet_name", "weight_dtype"], [("MODEL", "MODEL")]),
    nd(2, "CLIPLoader", "Load Qwen3-VL text encoder", [30, 240],
       {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "type": "minimax", "device": "default"},
       ["clip_name", "type", "device"], [("CLIP", "CLIP")]),
    nd(3, "VAELoader", "Load H3 video VAE", [30, 420],
       {"vae_name": "minimax_h3_video_vae_int8_convrot.safetensors"}, ["vae_name"], [("VAE", "VAE")]),
    nd(4, "VAELoader", "Load H3 audio VAE", [30, 540],
       {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}, ["vae_name"], [("VAE", "VAE")]),
    nd(5, "MiniMaxChunkFeedForward", "Chunk feed-forward", [420, 60],
       {"model": [1, 0], "chunks": 2, "seq_threshold": 4096}, ["chunks", "seq_threshold"],
       [("model", "MODEL")]),
    nd(6, "BlockSparseAttention", "Sol-Attn (sparse attention)", [420, 220],
       {"model": [5, 0], "selection": "sol-attn", "selection.tau": 1.3,
        "start_percent": 0.2, "end_percent": 1.0, "dense_blocks": "",
        "min_tokens": 12288, "extra_tokens": 256,
        "sink_conditioning": "exact_kv_and_rows", "verbose": False},
       ["selection", "selection.tau", "start_percent", "end_percent", "dense_blocks",
        "min_tokens", "extra_tokens", "sink_conditioning", "verbose"],
       [("MODEL", "MODEL")]),
    nd(7, "MiniMaxH3SigmaShift", "Sigma shift", [420, 460],
       {"model": [6, 0], "shift_video": 12, "shift_audio": 3}, ["shift_video", "shift_audio"],
       [("MODEL", "MODEL")]),
    nd(8, "LoadImage", "Character reference", [800, 60],
       {"image": "example.png"}, ["image", "upload"], [("IMAGE", "IMAGE"), ("MASK", "MASK")],
       wdefault={"upload": "image"}),
    nd(9, "RMBG", "Remove background (RMBG-2.0)", [800, 260],
       {"image": [8, 0], "model": "RMBG-2.0", "sensitivity": 1.0, "process_res": 1024,
        "mask_blur": 0, "mask_offset": 0, "invert_output": False, "refine_foreground": False,
        "background": "Color", "background_color": "#c7c7c7"},
       ["model", "sensitivity", "process_res", "mask_blur", "mask_offset", "invert_output",
        "refine_foreground", "background", "background_color"],
       [("IMAGE", "IMAGE"), ("MASK", "MASK"), ("MASK_IMAGE", "IMAGE")]),
    nd(14, "ImageResizeKJv2", "Resize reference (crop)", [1180, 60],
       {"image": [9, 0], "width": 864, "height": 480, "upscale_method": "nearest-exact",
        "keep_proportion": "crop", "pad_color": "0, 0, 0", "crop_position": "center",
        "divisible_by": 2, "device": "cpu"},
       ["width", "height", "upscale_method", "keep_proportion", "pad_color", "crop_position",
        "divisible_by", "device"],
       [("IMAGE", "IMAGE"), ("width", "INT"), ("height", "INT"), ("mask", "MASK")]),
    nd(18, "MiniMaxH3ReferenceToVideo", "Reference to video", [1560, 420],
       {"clip": [2, 0], "vae": [3, 0], "audio_vae": [4, 0],
        "ref_images.ref_image_0": [14, 0], "prompt": DEFAULT_PROMPT,
        "width": 864, "height": 480, "length": 121, "ref_image_size": "match"},
       ["prompt", "width", "height", "length", "ref_image_size"],
       [("positive", "CONDITIONING"), ("LATENT", "LATENT")]),
    nd(19, "BasicGuider", "Guider", [2200, 60],
       {"model": [7, 0], "conditioning": [18, 0]}, [], [("GUIDER", "GUIDER")]),
    nd(20, "KSamplerSelect", "Sampler", [2200, 200],
       {"sampler_name": "euler"}, ["sampler_name"], [("SAMPLER", "SAMPLER")]),
    nd(21, "BasicScheduler", "Scheduler", [2200, 320],
       {"model": [7, 0], "scheduler": "simple", "steps": 8, "denoise": 1.0},
       ["scheduler", "steps", "denoise"], [("SIGMAS", "SIGMAS")]),
    nd(22, "RandomNoise", "Noise", [2200, 500],
       {"noise_seed": 43}, ["noise_seed", "control_after_generate"], [("NOISE", "NOISE")]),
    nd(23, "SamplerCustomAdvanced", "Sampler", [2580, 60],
       {"noise": [22, 0], "guider": [19, 0], "sampler": [20, 0], "sigmas": [21, 0], "latent_image": [18, 1]},
       [], [("output", "LATENT"), ("denoised_output", "LATENT")]),
    nd(24, "VAEDecode", "Decode video", [2580, 240],
       {"samples": [23, 1], "vae": [3, 0]}, [], [("IMAGE", "IMAGE")]),
    nd(25, "VAEDecodeAudio", "Decode audio", [2580, 360],
       {"samples": [23, 1], "vae": [4, 0]}, [], [("AUDIO", "AUDIO")]),
    nd(26, "CreateVideo", "Create video", [2580, 480],
       {"images": [24, 0], "audio": [25, 0], "fps": 24.0}, ["fps"], [("VIDEO", "VIDEO")]),
    nd(27, "SaveVideo", "Save video", [2580, 640],
       {"video": [26, 0], "filename_prefix": "video/h3_ref_draft", "codec": "auto", "format": "auto"},
       ["filename_prefix", "format", "codec"], []),
]

GROUPS = [
    ("1. Models", [16, -10, 380, 640], "#3f789e"),
    ("2. Patches (chunk FF, Sol-Attn, sigma shift)", [406, -10, 370, 640], "#b58b2a"),
    ("3. Reference + RMBG + size", [786, -10, 1000, 840], "#8A8"),
    ("4. Prompt + reference conditioning", [1546, -10, 640, 700], "#a1309b"),
    ("5. Sample + decode + save", [2186, -10, 780, 760], "#88A"),
]


def api_graph():
    api = build_api(NODES)
    for spec in api.values():
        for k, v in spec["inputs"].items():
            if isinstance(v, list):
                spec["inputs"][k] = [str(v[0]), v[1]]
    return api


api = api_graph()
standard = build_standard(NODES, GROUPS, NOTE)

wf = GraydientWorkflow(name="h3-ref-draft-v1", description=DESCRIPTION)
wf.author = "UnlimitedEditing"
wf.set_workflows(standard, api)
stage_model(wf, CONCEPT_KEY)
wf.add_github_requirement("https://github.com/kijai/ComfyUI-KJNodes")
wf.add_github_requirement("https://github.com/1038lab/ComfyUI-RMBG")
# pip empty on purpose: see the RMBG notes in the module docstring.

wf.field_mapping = [
    # ReferenceToVideo widget order (all literal): prompt 0, width 1, height 2, length 3, ref_image_size 4.
    fm("prompt_positive", 18, "prompt", 0, "Reference to video", default_value=DEFAULT_PROMPT,
       help_text="Structured H3 prompt. Refer to the character as <Subject 1> / <Picture 1>. Newlines "
                 "collapse in Graydient (KI-007 sec 37): write the sections as one paragraph."),
    fm("init_image_filename", 8, "image", 0, "Character reference", default_value="example.png",
       help_text="One clear character reference (reply to an image). Background is removed with RMBG-2.0."),
    fm("image1", 8, "image", 0, "Character reference", default_value="example.png",
       help_text="The reference supplied as /image1:URL; Graydient stages it into input/ and fills the filename."),
    fm("seed", 22, "noise_seed", 0, "Noise", default_value=43, help_text="Random seed."),
    # NO min/max on width/height (KI-007 sec 44). Each is mapped onto BOTH the video size and the
    # reference crop size so they cannot disagree. There is NO in-graph snap-to-32 (the linter forbids the
    # Primitive nodes it needed): the help text tells users to use multiples of 32.
    fm("width", 18, "width", 1, "Reference to video", default_value=864,
       help_text="Draft width. USE A MULTIPLE OF 32 (864x480 validated). Not snapped by the graph."),
    fm("width", 14, "width", 0, "Resize reference (crop)", default_value=864,
       help_text="Reference crop width, kept equal to the video width."),
    fm("height", 18, "height", 2, "Reference to video", default_value=480,
       help_text="Draft height. USE A MULTIPLE OF 32."),
    fm("height", 14, "height", 1, "Resize reference (crop)", default_value=480,
       help_text="Reference crop height, kept equal to the video height."),
    fm("steps", 21, "steps", 1, "Scheduler", default_value=8, minimum_value=4, maximum_value=12,
       help_text="Sampling steps. The staged base is an 8-step turbo merge; 8 is the user's setting."),
    fm("slot4", 18, "length", 3, "Reference to video", default_value=121, minimum_value=22, maximum_value=241,
       help_text="Frames at 24 fps. MUST be on H3's 17k+5 grid: 22, 39, 56, 73, 90, 107, 124 (~5 s), 141, ... "
                 "Default 121 follows the stage-2 README. Capped at 241 (~10 s) for the ~180 s budget."),
]

wf.avg_elapsed = None  # no live render yet
wf.metadata.update(FLAGS_OFF)
wf.metadata.update({"supports_img2vid": True, "peak_vram_usage": 24000})  # estimate, NOT measured

if __name__ == "__main__":
    write_json(os.path.join(BASE_DIR, "h3-ref-draft-v1.json"), standard)
    write_json(os.path.join(BASE_DIR, "h3-ref-draft-v1-api.json"), api)
    wf.save(os.path.join(BASE_DIR, "GraydientWorkflow-h3-ref-draft-v1.json"))
    print(f"Graph: {len(api)} API nodes, {len(standard['nodes'])} standard nodes, "
          f"{standard['last_link_id']} links; {len(wf.concept_mapping)} staged files.")
