#!/usr/bin/env python3
"""
Anima Role Ref KV -- reference-guided anime illustration (text + 1 character reference -> image).

Model      : AnticPan/Anima-Role-Ref-KV v1.0 (adapter) on circlestone-labs/Anima Base v1.0 (2B DiT)
Node pack  : https://github.com/UnlimitedEditing/ComfyUI-AnimaRoleRefKV  (GPL-3.0 mirror of the
             upstream `comfyui/` folder + one Graydient glue node)
Modality   : Text-to-Image / Image-to-Image (the reference image is mandatory, not optional)

---------------------------------------------------------------------------------------------
PREFLIGHT (`.agents/skills/preflight-plan/SKILL.md`, KI-009) -- what was checked before coding
---------------------------------------------------------------------------------------------
INTENT : generate new poses / outfits / expressions / scenes of an existing character from one
         reference image plus a text prompt, with no per-character training and no trigger word.

VEHICLE 1 (rejected): install the adapter as a Graydient Anima-family *Concept* (LoRA) and use
         `<anima-role-ref-kv:1.0>` in the prompt with a stock `LoraLoaderModelOnly` + `KSampler`.
         Rejected for two source-verified reasons, not taste:
           a) The adapter's weight keys ARE standard ComfyUI LoRA keys
              (`diffusion_model.blocks.{b}.{target}.lora_{down,up}.weight`), so a LoraLoader would
              happily attach them -- but the release only produces a character when the reference
              image is encoded into a per-block KV cache and concatenated ahead of the noisy
              stream's k/v (`comfyui/native.py: block()` -> `torch.cat([ref[0], k], 2)`). A plain
              LoRA load applies the weights with no reference stream at all: silent wrong output,
              which is the worst failure class in KI-007 (structurally valid graph, bad result).
           b) The node hard-refuses a patched model: `if model.patches or
              model.model_options["transformer_options"]["patches"]: raise ValueError(...)`.
              Any LoRA/Concept applied upstream of this node is a hard job failure.
         => `supports_dynamic_concepts: false` in the Graydient config, deliberately.

VEHICLE 2 (accepted): ship the custom node in a GitHub repo under UnlimitedEditing and list it in
         `requirements.github`. Graydient clones custom nodes from GitHub on every run; it cannot
         clone from Hugging Face, so the upstream `comfyui/` folder has to be mirrored to a repo
         first. That mirror is the reason this build needs a new repo at all.

Catalog checks actually run (not recalled):
  * `python wf.py search anima` / `qwen_image_vae` / `unetloader` / `lora` / `kv-cache`
    -> no Graveyard entry collides with this vehicle. No `anima` key existed in
       `graydient_builder/concept_db.json`; one is added by this build (harvest step).
  * Pure-Python rule (KI-007): the node imports only `torch`, `numpy`, `PIL`, `folder_paths`,
    `comfy.model_management`, `comfy.utils` and uses `F.scaled_dot_product_attention`. No
    `flash-attn`, no maturin/cargo/cmake/rust, no compiled dep. `requirements.pip` is therefore
    EMPTY -- KI-005 sec 3 says do not re-list torch/numpy/Pillow, they are already in ComfyUI.
  * Gated-repo check: both HF repos report `"gated": false` via the HF API. No token needed.
  * Quantization gate (preflight Step 2b): DOES NOT APPLY, and applying it would break the build.
    Total staged weight is ~6.15 GB (> 4 GB) so it must go in `concept_mapping` (KI-005 sec 1),
    but the node explicitly rejects anything that is not BF16 or FP32:
      `if dtype not in (torch.bfloat16, torch.float32): raise ValueError(...)`
    So `UNETLoader.weight_dtype` MUST stay `"default"` -- never `fp8_e4m3fn`. No ZeroGPU
    cloud-to-cloud FP8 conversion, no GGUF, no NF4. 6.15 GB resident is far inside the KI-005
    sec 2 20 GB budget on a 24 GB runner, so there is nothing to gain from quantizing anyway.
  * Node signature verified against REAL SOURCE, never guessed (node_schema_db.json _readme rule):
      - `comfyui/nodes.py` `AnimaRoleRefKV.INPUT_TYPES` read directly off Hugging Face.
      - every attribute the engine touches cross-checked against ComfyUI core at master:
        `comfy/ldm/anima/model.py` (Anima.llm_adapter, Anima.preprocess_text_embeds) and
        `comfy/ldm/cosmos/predict2.py` (MiniTrainDIT.blocks / pos_embedder / x_embedder /
        t_embedder / t_embedding_norm / final_layer / unpatchify / model_channels / num_heads;
        Block.adaln_modulation_{self_attn,cross_attn,mlp} + layer_norm_*; Attention.q_proj/
        k_proj/v_proj/output_proj/q_norm/k_norm/n_heads; GPT2FeedForward.layer1/layer2/activation).
        `Block.forward` chunk(3) -> (shift, scale, gate) and `norm*(x)*(1+scale)+shift` match the
        node's own `norm()` helper exactly.
      - loader widget values cross-checked against ComfyUI's OWN official blueprint
        `blueprints/Text to Image (Anima Base 1.0).json`: UNETLoader
        ["anima-base-v1.0.safetensors","default"], CLIPLoader
        ["qwen_3_06b_base.safetensors","stable_diffusion","default"], VAELoader
        ["qwen_image_vae.safetensors"]. Byte-identical to what this script emits.
  * Node-class-name collision (COMFYUI-REFERENCE sec 2): `AnimaRoleRefKV` and
    `AnimaRoleRefKVGlue` are not registered by any other pack in the org or upstream.
  * COMBO validation: UNETLoader / CLIPLoader / VAELoader / the node's `adapter` combo are all
    validated for the whole graph BEFORE execution (KI-007), so all four weight files are staged
    in `concept_mapping` even though only one path runs.
  * Reference transport: `image1` on Graydient resolves to a pre-staged FILENAME in `input/`, not
    a URL, so the correct loader is core `LoadImage` -- NOT `LoadImageFromURL` (confirmed the hard
    way in node_schema_db.json's LoadImage note). Default widget is `example.png`, which ships in
    ComfyUI's `input/` and on Graydient runners, so prompt validation still passes when no
    reference is supplied.
  * width/height: mapped to the platform `width`/`height` fields (mandatory on any visual-output
    workflow, never a slot -- KI-003 sec 3.4) with NO `minimum_value`/`maximum_value`, per KI-007
    sec 44 (`WIDTH_HEIGHT_MIN_REJECTS_DEFAULT_SIZE`: Telegram injects its own default /size and a
    mapping minimum below it rejects the job before it is queued). The clamp lives in the graph
    instead -- here, inside the glue node, which snaps each side DOWN to a multiple of 16. That is
    the whole reason `AnimaRoleRefKVGlue` exists: upstream raises
    `ValueError("Dimensions must be multiples of 16 ...")`, so an arbitrary `/size:1000x1000`
    would hard-fail the job.

---------------------------------------------------------------------------------------------
WIDGET INDEXING (KI-003) -- the numbers used in `field_mapping` below
---------------------------------------------------------------------------------------------
`AnimaRoleRefKV.INPUT_TYPES` declares 5 sockets then 6 widgets. Sockets are excluded; the frontend
inserts a `control_after_generate` widget after `seed`, so standard-format `widgets_values` is:

    [adapter, seed, control_after_generate, width, height, steps, cfg]
       0       1            2                 3       4       5      6

This matches upstream's own `workflows/anima-role-ref-kv-v1.0.json` widgets_values array, and the
same "index counts control_after_generate" convention node_schema_db.json documents for KSampler.

---------------------------------------------------------------------------------------------
RUN-TIME BUDGET (KI-005) -- estimate, NOT yet measured on a live job
---------------------------------------------------------------------------------------------
28 steps x 2 velocity passes (cond + uncond) + 1 reference pass over 28 blocks = ~85 DiT forwards
of a 2B model at ~4k tokens. Expected `Prompt executed in N seconds` well inside the ~120 s target
on a 4090/5090, but `steps` is capped at 50 in field_mapping so a user cannot blow the ~180 s
budget with /steps:100. `avg_elapsed` and `peak_vram_usage` below are ESTIMATES until a real
render confirms them -- do not quote them as measured.

Outputs:
  GraydientWorkflow-anima-role-ref-kv-v1.json   (Graydient backup/restore; uses the glue node)
  anima-role-ref-kv-v1.0.json                   (plain ComfyUI standard; drag onto the canvas)
  anima-role-ref-kv-v1.0-api.json               (plain ComfyUI API/prompt format)
The two plain files are byte-for-byte what ships in the node repo's `workflows/` folder.
"""

import json
import os

from graydient_builder import GraydientWorkflow, load_concept_db, stage_model

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

NODE_REPO = "https://github.com/UnlimitedEditing/ComfyUI-AnimaRoleRefKV"

# ----------------------------------------------------------------------------------------------
# Weight staging (KI-008 format) comes from graydient_builder/concept_db.json under the key
# 'anima-role-ref-kv', via stage_model() -- the catalog is the single source of truth, so this
# script and `wf.py staging anima` cannot drift apart. Sizes/sha256 recorded there were verified
# 2026-11-01 from the HF API '?blobs=true' listing on both repos (ungated).
# ~6.16 GB total, downloaded BEFORE the ComfyUI clock starts (KI-005 sec 1).
#
#   diffusion_models/anima-base-v1.0.safetensors   4,182,218,328 B  Anima Base v1.0 2B DiT, BF16.
#            MUST be loaded with weight_dtype='default' -- the node rejects fp8/quantized casts.
#   text_encoders/qwen_3_06b_base.safetensors      1,192,135,096 B  Qwen3 0.6B, via CLIPLoader
#            type='stable_diffusion' (matches ComfyUI's own official Anima Base 1.0 blueprint).
#   vae/qwen_image_vae.safetensors                   253,806,246 B  Qwen-Image VAE; encodes the
#            reference and decodes the output latent.
#   loras/anima-role-ref-kv-v1.0.safetensors         528,546,184 B  the adapter, rank 128 /
#            alpha 128, FP32. Under loras/ because the node resolves it with
#            folder_paths.get_filename_list('loras') -- but do NOT wire a LoraLoader to it.
# ----------------------------------------------------------------------------------------------
CONCEPT_KEY = "anima-role-ref-kv"

POSITIVE_PROMPT = (
    "masterpiece, best quality, safe, 1girl, solo, upper body, looking at viewer, smile, "
    "simple background, white background"
)
NEGATIVE_PROMPT = (
    "worst quality, low quality, score_1, score_2, score_3, artist name, blurry, jpeg artifacts, "
    "chromatic aberration"
)

DESCRIPTION = """\
Anima Role Ref KV v1.0: reference-guided anime illustration. Send ONE clear character reference plus a text prompt and get that same character in a new pose, outfit, expression or scene -- no per-character training, no trigger word, no LoRA to install.

The reference is encoded into a per-block KV cache once and reused across every denoising step, so identity holds far better than prompt-only character description. Runs on Anima Base v1.0 (2B DiT, CircleStone Labs / Comfy Org) with Qwen3 0.6B and the Qwen-Image VAE.

Telegram / API:
/run:anima-role-ref-kv [prompt] - reply to (or right-click) the character reference image, then describe the new pose, outfit and scene
/image1:URL - the character reference, if you are not replying to an image. One clear, unobstructed single character works best
/size:832x1216 - output canvas. Must be a multiple of 16; anything else is snapped DOWN to the nearest 16. Roughly 1 megapixel is the validated range (1024x1024, 832x1216, 1216x832)
/steps:28 - sampling steps (default 28; the model author's range is 28-50, capped at 50 here to stay inside the run-time budget)
/cfg:4 - prompt guidance (default 4.0; Anima's documented range is 4-5)
/seed:42 - reproducible seed

Prompting (Anima is Danbooru-tag trained, lowercase tags, spaces not underscores):
- Recommended positive prefix: "masterpiece, best quality, safe, "
- Recommended negative: "worst quality, low quality, score_1, score_2, score_3, artist name, blurry, jpeg artifacts, chromatic aberration"
- Tag order: [quality/meta/safety] [1girl/1boy] [character] [series] [artist] [general tags]
- Prefix artist tags with @ or they are near-inert. Prompt weighting needs to be heavier than SDXL, e.g. (chibi:2)
- Describe the pose/outfit/scene you WANT; the reference supplies the identity

Known limits (from the model author, unchanged by this port):
- LoRAs and Concepts cannot be stacked on this workflow. The node deliberately refuses any patched MODEL, so <concept:0.7> tags and dynamic concepts are off.
- BF16 or FP32 base weights only; fp8/GGUF/quantized Anima is not validated and the node raises rather than silently degrading.
- One reference image, one positive/negative pair. Batched, regional (area/mask) or ControlNet conditioning is rejected.
- Details can drift on difficult references or with large prompt changes. Not a realism model -- it is trained for anime and non-photorealistic illustration.

Model weights: AnticPan/Anima-Role-Ref-KV (adapter) on circlestone-labs/Anima (base), CircleStone Non-Commercial License. ComfyUI integration GPL-3.0. Not an official CircleStone Labs or AnticPan product.
"""

NOTE_PLAIN = """\
Anima Role Ref KV v1.0  (plain ComfyUI)

1. Clone UnlimitedEditing/ComfyUI-AnimaRoleRefKV into
   ComfyUI/custom_nodes/ and restart.
2. anima-base-v1.0.safetensors  -> models/diffusion_models/
   qwen_3_06b_base.safetensors  -> models/text_encoders/
   qwen_image_vae.safetensors   -> models/vae/
   anima-role-ref-kv-v1.0.safetensors -> models/loras/
3. Upload ONE clear single-character reference.
4. Edit the positive prompt and Queue.

Start at 28 steps, CFG 4, 832 x 1216 (or 1024 x 1024).
Dimensions must be multiples of 16.

IMPORTANT
- UNETLoader weight_dtype must stay "default" (BF16).
  fp8 / quantized casts are rejected by the node.
- Do NOT put a LoraLoader between the UNETLoader and this
  node. It loads the adapter itself and refuses a patched
  MODEL.
"""

NOTE_GRAYDIENT = """\
Anima Role Ref KV v1.0  (Graydient build)

Same graph as the plain ComfyUI workflow except node 7 is
AnimaRoleRefKVGlue, which snaps width/height DOWN to a
multiple of 16 instead of raising. That is the KI-007 sec 44
mitigation: Telegram injects its own /size when the user
gives none, and an arbitrary /size:1000x1000 would otherwise
hard-fail the job.

Weights are staged by concept_mapping (~6.15 GB) so nothing
downloads inside the run-time budget. The node pack is
cloned from requirements.github on every run.

field_mapping (widget indices per KI-003, counting the
control_after_generate slot the frontend inserts after seed):
  prompt_positive     -> 4 text  [0]
  prompt_negative     -> 5 text  [0]
  init_image_filename -> 6 image [0]
  image1              -> 6 image [0]
  seed                -> 7 seed  [1]
  width               -> 7 width [3]  (no min/max)
  height              -> 7 height[4]  (no min/max)
  steps               -> 7 steps [5]  (4..50)
  cfg                 -> 7 cfg   [6]  (1..10)

supports_dynamic_concepts is OFF on purpose: the node raises
on any patched MODEL, so Concepts/LoRAs cannot be stacked.
"""

# ----------------------------------------------------------------------------------------------
# Graph tables. Socket (link) inputs and primitive widgets are declared separately so the
# standard-format widgets_values array and the API-format inputs dict are generated from ONE
# source of truth and cannot drift (COMFYUI-REFERENCE sec 1).
# ----------------------------------------------------------------------------------------------

# Widget order as the ComfyUI frontend serialises it. `control_after_generate` is a frontend-only
# companion widget inserted after any INT widget named seed/noise_seed; it has no API counterpart.
WIDGETS = {
    "UNETLoader": ["unet_name", "weight_dtype"],
    "CLIPLoader": ["clip_name", "type", "device"],
    "VAELoader": ["vae_name"],
    "CLIPTextEncode": ["text"],
    "LoadImage": ["image", "upload"],
    "AnimaRoleRefKV": ["adapter", "seed", "control_after_generate", "width", "height", "steps", "cfg"],
    "AnimaRoleRefKVGlue": ["adapter", "seed", "control_after_generate", "width", "height", "steps", "cfg"],
    "VAEDecode": [],
    "SaveImage": ["filename_prefix"],
    "Note": ["text"],
}

# Output socket names, in slot order.
OUTPUTS = {
    "UNETLoader": ["MODEL"],
    "CLIPLoader": ["CLIP"],
    "VAELoader": ["VAE"],
    "CLIPTextEncode": ["CONDITIONING"],
    "LoadImage": ["IMAGE", "MASK"],
    "AnimaRoleRefKV": ["LATENT"],
    "AnimaRoleRefKVGlue": ["LATENT"],
    "VAEDecode": ["IMAGE"],
    "SaveImage": [],
    "Note": [],
}

LAYOUT = {
    1:  {"pos": [30, 60],    "size": [340, 110]},
    2:  {"pos": [30, 220],   "size": [340, 130]},
    3:  {"pos": [30, 400],   "size": [340, 90]},
    10: {"pos": [30, 540],   "size": [340, 470]},
    4:  {"pos": [410, 60],   "size": [380, 200]},
    5:  {"pos": [410, 300],  "size": [380, 200]},
    6:  {"pos": [410, 540],  "size": [380, 340]},
    7:  {"pos": [830, 160],  "size": [380, 340]},
    8:  {"pos": [1250, 220], "size": [260, 80]},
    9:  {"pos": [1550, 220], "size": [380, 340]},
}

GROUPS = [
    {"title": "1. Weights (BF16 only -- no fp8, no quantized Anima)",
     "bounding": [16, -10, 368, 1030], "color": "#3f789e"},
    {"title": "2. Conditioning + character reference",
     "bounding": [396, -10, 408, 900], "color": "#8A8"},
    {"title": "3. Role Ref KV sampling (adapter loaded inside the node)",
     "bounding": [816, 90, 408, 430], "color": "#b58b2a"},
    {"title": "4. Decode + save",
     "bounding": [1236, 150, 706, 430], "color": "#88A"},
]


def build_api(sample_class: str) -> dict:
    """API / prompt format: nodes keyed by string id, `class_type` (never `type`), widgets and
    links together in one `inputs` dict, a link being a ["<node id>", <slot>] pair."""
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                # weight_dtype MUST be "default": the node raises on anything that is not
                # BF16/FP32. This is the single most likely mis-setting on this graph.
                "unet_name": "anima-base-v1.0.safetensors",
                "weight_dtype": "default",
            },
            "_meta": {"title": "Load Anima Base DiT"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen_3_06b_base.safetensors",
                # "stable_diffusion" is not a typo: this is what ComfyUI's own official
                # Anima Base 1.0 blueprint uses for qwen_3_06b_base.
                "type": "stable_diffusion",
                "device": "default",
            },
            "_meta": {"title": "Load Qwen3 06B Text Encoder"},
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "qwen_image_vae.safetensors"},
            "_meta": {"title": "Load Qwen Image VAE"},
        },
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["2", 0], "text": POSITIVE_PROMPT},
            "_meta": {"title": "Positive Prompt"},
        },
        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["2", 0], "text": NEGATIVE_PROMPT},
            "_meta": {"title": "Negative Prompt"},
        },
        "6": {
            # example.png ships in ComfyUI's input/ and on Graydient runners, so prompt
            # validation still passes when no reference is supplied; Graydient overwrites
            # this widget with the staged filename when image1 / init_image is given.
            "class_type": "LoadImage",
            "inputs": {"image": "example.png"},
            "_meta": {"title": "Character Reference"},
        },
        "7": {
            "class_type": sample_class,
            "inputs": {
                "model": ["1", 0],
                "vae": ["3", 0],
                "positive": ["4", 0],
                "negative": ["5", 0],
                "reference": ["6", 0],
                "adapter": "anima-role-ref-kv-v1.0.safetensors",
                "seed": 0,
                "width": 832,
                "height": 1216,
                "steps": 28,
                "cfg": 4.0,
            },
            "_meta": {"title": "Anima Role Ref KV"},
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["7", 0], "vae": ["3", 0]},
            "_meta": {"title": "Decode Image"},
        },
        "9": {
            "class_type": "SaveImage",
            "inputs": {"images": ["8", 0], "filename_prefix": "Anima-Role-Ref-KV"},
            "_meta": {"title": "Save Image"},
        },
    }


def build_standard(api: dict, note_text: str) -> dict:
    """Derive the standard/UI graph from the API graph so the two can never drift apart."""
    nodes = []
    links = []
    link_id = 0

    # Note is UI-only: it has no executor, so it belongs in the standard graph and is
    # deliberately absent from the API graph (a PrimitiveNode/Note surviving into API JSON
    # is one of the two classic conversion bugs, COMFYUI-REFERENCE sec 1).
    order = 0
    for key, spec in list(api.items()) + [("10", None)]:
        nid = int(key)
        layout = LAYOUT[nid]

        if spec is None:  # the Note node
            nodes.append({
                "id": nid,
                "type": "Note",
                "pos": layout["pos"],
                "size": layout["size"],
                "flags": {},
                "order": 99,
                "mode": 0,
                "inputs": [],
                "outputs": [],
                "properties": {},
                "widgets_values": [note_text],
                "color": "#232b3c",
                "bgcolor": "#343b4d",
            })
            continue

        class_type = spec["class_type"]
        title = spec["_meta"]["title"]

        widget_values = []
        for widget in WIDGETS[class_type]:
            if widget == "control_after_generate":
                widget_values.append("fixed")
            elif widget == "upload":
                widget_values.append("image")
            else:
                widget_values.append(spec["inputs"].get(widget, ""))

        node_inputs = []
        for in_name, in_val in spec["inputs"].items():
            if not isinstance(in_val, list):
                continue  # a primitive widget, not a socket
            src_id, src_slot = in_val
            src_type = OUTPUTS[api[src_id]["class_type"]][src_slot]
            link_id += 1
            links.append([link_id, int(src_id), src_slot, nid, len(node_inputs), src_type])
            node_inputs.append({"name": in_name, "type": src_type, "link": link_id})

        # Output `links` back-references are filled in a SECOND pass below: a link is created
        # while walking the *consumer* node, so a producer walked earlier (node 1 UNETLoader is
        # consumed by node 7) would otherwise serialise an empty links array. ComfyUI tolerates
        # it, but the canvas then draws no wires out of the loaders.
        node_outputs = []
        for slot, out_type in enumerate(OUTPUTS[class_type]):
            node_outputs.append({
                "name": out_type,
                "type": out_type,
                "links": [],
                "slot_index": slot,
            })

        nodes.append({
            "id": nid,
            "type": class_type,
            "pos": layout["pos"],
            "size": layout["size"],
            "flags": {},
            "order": order,
            "mode": 0,
            "inputs": node_inputs,
            "outputs": node_outputs,
            "title": title,
            "properties": {"Node name for S&R": class_type},
            "widgets_values": widget_values,
        })
        order += 1

    # Second pass: back-fill each producer output's `links` array now that every link exists.
    by_id = {n["id"]: n for n in nodes}
    for lid, from_node, from_slot, _to_node, _to_slot, _type in links:
        by_id[from_node]["outputs"][from_slot]["links"].append(lid)

    return {
        "last_node_id": max(n["id"] for n in nodes),
        "last_link_id": link_id,
        "nodes": nodes,
        "links": links,
        "groups": [
            {"id": i + 1, "title": g["title"], "bounding": g["bounding"],
             "color": g["color"], "font_size": 22, "flags": {}}
            for i, g in enumerate(GROUPS)
        ],
        "config": {},
        "extra": {"ds": {"scale": 0.55, "offset": [60, 90]}},
        "version": 0.4,
    }


def fm(local_field, node_id, node_input_name, node_input_index, node_name,
       default_value=None, minimum_value=None, maximum_value=None, help_text=""):
    """Graydient stores field_mapping values as strings (KI-007 sec 44 observed '640', not 640)."""
    as_str = lambda v: None if v is None else str(v)
    return {
        "default_value": as_str(default_value),
        "help_text": help_text,
        "local_field": local_field,
        "maximum_value": as_str(maximum_value),
        "minimum_value": as_str(minimum_value),
        "node_id": node_id,
        "node_input_index": node_input_index,
        "node_input_name": node_input_name,
        "node_name": node_name,
    }


# ----------------------------------------------------------------------------------------------
# Variant A -- plain local ComfyUI (upstream node class, drag straight onto the canvas)
# ----------------------------------------------------------------------------------------------
plain_api = build_api("AnimaRoleRefKV")
plain_standard = build_standard(plain_api, NOTE_PLAIN)

# ----------------------------------------------------------------------------------------------
# Variant B -- Graydient archive build (glue node: 16-multiple snap, everything else identical)
# ----------------------------------------------------------------------------------------------
graydient_api = build_api("AnimaRoleRefKVGlue")
graydient_standard = build_standard(graydient_api, NOTE_GRAYDIENT)

wf = GraydientWorkflow(name="anima-role-ref-kv-v1", description=DESCRIPTION)
wf.author = "UnlimitedEditing"
wf.set_workflows(graydient_standard, graydient_api)

stage_model(wf, CONCEPT_KEY)

wf.add_github_requirement(NODE_REPO)
# requirements.pip is deliberately EMPTY. The node needs only torch / numpy / Pillow, which
# KI-005 sec 3 says not to re-list, and every one of them is already in the ComfyUI image.
# Anything with a compiled dep would trip GRAVEYARD_BANNED_PIP anyway.

# --- field_mapping -----------------------------------------------------------------------------
wf.field_mapping = [
    fm("prompt_positive", 4, "text", 0, "Positive Prompt",
       default_value="",
       help_text="What the character should now be doing / wearing / where. Anima is Danbooru-tag "
                 "trained: lowercase tags, spaces not underscores, prefix artists with @. "
                 "Recommended prefix 'masterpiece, best quality, safe, '."),
    fm("prompt_negative", 5, "text", 0, "Negative Prompt",
       default_value="",
       help_text="Anima's documented default negative: 'worst quality, low quality, score_1, "
                 "score_2, score_3, artist name, blurry, jpeg artifacts, chromatic aberration'."),
    # Two local_fields on the SAME widget is the established pattern (pinkcherry-ltx25, and the
    # LoadImage note in node_schema_db.json): whichever transport Graydient populates for a given
    # submission arrives. Both are filename-based, which is what core LoadImage needs -- image1
    # resolves to a pre-staged input/ filename, NOT a URL, so LoadImageFromURL would be wrong here.
    fm("init_image_filename", 6, "image", 0, "Character Reference",
       default_value="example.png",
       help_text="The character reference (reply to an image in Telegram). One clear, unobstructed "
                 "single character. Resized internally to fit 768x768 before VAE encoding."),
    fm("image1", 6, "image", 0, "Character Reference",
       default_value="example.png",
       help_text="The character reference, supplied as /image1:URL instead of a reply. Same widget "
                 "as init_image_filename; Graydient stages it into input/ and fills the filename."),
    fm("seed", 7, "seed", 1, "Anima Role Ref KV",
       default_value=0,
       help_text="Random seed. 0 with control_after_generate='fixed' reproduces a render exactly."),
    # NO minimum_value / maximum_value on width or height -- KI-007 sec 44. Telegram supplies its
    # own default /size when the user gives none and a mapping minimum below it rejects the job
    # before it is queued. The 16-multiple clamp lives in AnimaRoleRefKVGlue instead.
    fm("width", 7, "width", 3, "Anima Role Ref KV",
       default_value=832,
       help_text="Output width. Snapped DOWN to a multiple of 16 by the node. Validated range is "
                 "roughly 1 megapixel: 1024x1024, 832x1216 or 1216x832."),
    fm("height", 7, "height", 4, "Anima Role Ref KV",
       default_value=1216,
       help_text="Output height. Snapped DOWN to a multiple of 16 by the node. 832x1216 portrait "
                 "is the model author's default."),
    fm("steps", 7, "steps", 5, "Anima Role Ref KV",
       default_value=28, minimum_value=4, maximum_value=50,
       help_text="Sampling steps. 28 is the author's recommended start, 30-50 is Anima's range. "
                 "Capped at 50 so /steps:100 cannot blow the ~180 s run-time budget (KI-005)."),
    fm("cfg", 7, "cfg", 6, "Anima Role Ref KV",
       default_value=4.0, minimum_value=1.0, maximum_value=10.0,
       help_text="Prompt guidance. 4.0 is the author's recommended default; Anima documents 4-5."),
]

# --- archive flags -----------------------------------------------------------------------------
wf.avg_elapsed = None            # ESTIMATE PENDING: no live render yet, do not invent a number
wf.metadata.update({
    "version": 1,
    "platform": "comfyui",
    # Estimated, NOT measured: ~6.15 GB of resident weights (the node calls
    # mm.load_models_gpu(..., force_full_load=True)) plus ~1 GB of held reference KV cache and
    # activations at 832x1216. peak_vram_usage is virtual and is not a routing signal.
    "peak_vram_usage": 11000,
    "supports_txt2img": True,     # image output
    "supports_img2img": True,     # consumes a reference image via init_image / image1
    "supports_txt2vid": False,
    "supports_img2vid": False,
    "supports_vid2img": False,
    "supports_vid2vid": False,
    "supports_txt2wav": False,
    "supports_vid2wav": False,
    "supports_wav2txt": False,
    "supports_low_memory": False,     # force_full_load=True; there is no low-memory path
    # OFF ON PURPOSE. The node raises ValueError on any patched MODEL, so Graydient Concepts /
    # LoRAs cannot be stacked on this workflow. See the VEHICLE 1 rejection in the docstring.
    "supports_dynamic_concepts": False,
    "install_detected_nodes": True,
    "split_prompt_pos_neg": True,     # genuine separate CLIPTextEncode pair, as in moss-image v2
    "is_public": False,               # owner flips this after a live test render + cover image
    "is_deleted": False,
    "image_url": None,
    "external_config": None,
    "external_provider": None,
    "extra_data": None,
    "max_collect_attempts": None,
    "pre_install_script": None,
    "post_install_script": None,
})


def _write(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"[WROTE] {path}")


if __name__ == "__main__":
    # Plain ComfyUI deliverables (these are what ships in the node repo's workflows/ folder).
    _write(os.path.join(BASE_DIR, "anima-role-ref-kv-v1.0.json"), plain_standard)
    _write(os.path.join(BASE_DIR, "anima-role-ref-kv-v1.0-api.json"), plain_api)

    # Graydient backup/restore JSON. GraydientWorkflow.save() runs the pre-flight linter itself
    # and refuses to write on ERROR unless force=True -- no force here, by design.
    wf.save(os.path.join(BASE_DIR, "GraydientWorkflow-anima-role-ref-kv-v1.json"))

    staged = load_concept_db()[CONCEPT_KEY]
    total = sum(e.get("_bytes", 0) for e in staged)
    print(f"\nStaged weight total: {total / 1e9:.2f} GB across {len(staged)} files "
          f"(all ungated, all BF16/FP32 -- no quantization step, the node forbids it).")
    assert len(wf.concept_mapping) == len(staged), "stage_model did not stage every file"
    assert [c["destination"] for c in wf.concept_mapping] == [e["destination"] for e in staged]
    print(f"Graph: {len(plain_api)} API nodes, {len(plain_standard['nodes'])} standard nodes "
          f"(+1 UI-only Note), {plain_standard['last_link_id']} links.")
