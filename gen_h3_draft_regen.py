#!/usr/bin/env python3
"""
H3 Draft + Regen 2K -- ALL-IN-ONE MiniMax H3 build: character reference image (+ RMBG) + structured
H3 prompt -> low-res draft video with audio -> NVIDIA Open-H3-Regenerate-2K refine -> 2K mp4, in ONE job.

Merges the two chained builds (gen_h3_ref_draft.py = stage 1, gen_h3_regen2k.py = stage 2) by importing
their node tables, so the node signatures/widget orders cannot drift from the chained versions.

--------------------------------------------------------------------------------------------
PREFLIGHT (preflight-plan / KI-009)
--------------------------------------------------------------------------------------------
INTENT  : reference image + prompt -> finished 2K H3 video with soundtrack, one submit.
VEHICLE : stage 1 and stage 2 graphs in one prompt graph. Hand-off = DECODE the draft latent to
          frames (VAEDecode, node 24) and RE-ENCODE with the FL2VA VAE (node 110), not a live latent
          pass (that in-graph latent hand-off, with MMH3 Split Params, is what the earlier attempt used).
          The draft's own audio (node 25) is carried to OpenH3RegenFinish.

Checked: node signatures reused from the two existing generators (read from source 2026-11-02, see their
docstrings); no new node types. Catalog search: no Graveyard entry for the H3 regenerate recipe.
NOT verified: Hugging Face is blocked from the authoring sandbox -> every URL is unfetched; no live run.

KNOWN RISKS (read before spending quota)
  1. RUN BUDGET (KI-005): stage 1 (8 steps) + model swap + 3 Euler steps at target res + fast VAE decode
     must fit one ~180 s clock on a 24-32 GB runner. The README's 122 s refine + 24 s decode for 5 s @ 2K
     was on a 72 GB Blackwell. Default here is 1080p + 56 frames for the FIRST live test (slot4 raises length; rebuild with H3_RES for 2K).
  2. VRAM/RAM: two ~20 GB int8 DiTs + a 12.4 GB FP32 LoRA are used in sequence. No VRAM-flush nodes
     (easy-use cleanGpuUsed) were added (extra dependency); ComfyUI's model manager should offload the stage-1
     model, but if the run OOMs at node 101/102 that is the first suspect -- add the flush then.
  3. Sampling-seed: stage 2 uses NVIDIA's fixed seed; only stage 1 follows /seed.
  4. All risks of the two parents (no size snapping, 17k+5 length grid, newline collapse) still apply.

Outputs: GraydientWorkflow-h3-draft-regen-v1.json (+ plain ComfyUI h3-draft-regen-v1.json / -api.json)
"""

import copy
import os

from graydient_builder import GraydientWorkflow, stage_model
from gen_h3_common import FLAGS_OFF, build_api, build_standard, fm, write_json
import gen_h3_ref_draft as s1
import gen_h3_regen2k as s2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONCEPT_KEY = "h3-draft-regen"
OFF = 100            # stage-2 node id offset
Y_OFF = 900          # stage-2 canvas offset
# Final resolution is a combo (non-numeric) so it cannot be a slot (KI-007 sec 23): fixed at build time.
# Rebuild with H3_RES="2k (2560x1440)" for full 2K once a 1080p run is proven.
TEST_RES = os.environ.get("H3_RES", "1080p (1920x1080)")
TEST_FRAMES = 56  # on the 17k+5 grid (3 -> 56), ~2.3 s: first live test length

DESCRIPTION = """\
H3 Draft + Regen 2K: send ONE character reference image and a structured MiniMax H3 prompt and get a finished high-resolution video with soundtrack in a single job. Stage 1 makes a low-resolution H3 draft (reference background removed with RMBG-2.0, 8-step turbo model); stage 2 regenerates it at 1920x1080 (2K build available) with NVIDIA's Open-H3-Regenerate-2K recipe, Sol-Attn sparse attention and the fast H3 VAE decoder. The draft's own audio is kept.

Telegram / API:
/run:h3-draft-regen [prompt] - reply to (or attach) the character reference, then paste an H3-style prompt (refer to the character as <Subject 1> / <Picture 1>)
/image1:URL - the reference, if you are not replying to an image
/size:864x480 - DRAFT size, multiples of 32 (not snapped)
/slot4:56 - frames at 24 fps, on H3's 17k+5 grid: 22, 39, 56, 73, 90, 107, 124 ...
/slot5:0 - regen start sigma (0 = NVIDIA release recipe; 0.8 stays closer to the draft)
/steps:8 - draft steps, min 3 (staged base is an 8-step turbo)
/slot6:3 - regenerate refine steps (default 3 = NVIDIA recipe, min 1)
/seed:43 - draft seed

Known limits: very heavy. Both stages share one render clock; if it times out lower /slot4, or use the separate h3-ref-draft + h3-regen2k workflows. Weights: Comfy-Org/MiniMax-H3, OliviaRossi/Minimax-h3_Singularity-x-10Eros-Max_PRISM, Efficient-Large-Model/Open-H3-Regenerate-2K (NVIDIA), LBH-123-AI latent upscaler, RMBG-2.0 - each under its own license. Not an official MiniMax or NVIDIA product.
"""
NOTE = ("H3 Draft + Regen 2K (all-in-one). Custom nodes: kijai/ComfyUI-KJNodes, 1038lab/ComfyUI-RMBG, "
        "rdh9616/ComfyUI-Open-H3-Regenerate, LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler. "
        "Stage 1 = nodes 1-25, stage 2 = nodes 101-120. Weights: concept_db.json 'h3-draft-regen'.")


def build_nodes():
    nodes = []
    for n in s1.NODES:
        if n["id"] in (26, 27):          # stage-1 CreateVideo / SaveVideo: replaced by the final save
            continue
        nodes.append(copy.deepcopy(n))
    for n in s2.NODES:
        if n["id"] in (7, 8):            # LoadVideo / GetVideoComponents: the draft is in-graph now
            continue
        m = copy.deepcopy(n)
        m["id"] += OFF
        m["pos"] = [m["pos"][0], m["pos"][1] + Y_OFF]
        for k, v in m["inputs"].items():
            if isinstance(v, list):
                m["inputs"][k] = [v[0] + OFF, v[1]]
        nodes.append(m)
    by = {n["id"]: n for n in nodes}
    by[109]["inputs"]["images"] = [24, 0]                 # decoded draft frames
    by[109]["inputs"]["source_fps"] = 24.0
    by[109]["inputs"]["max_frames"] = TEST_FRAMES
    by[109]["inputs"]["size"] = "768p (1344x768)"
    by[111]["inputs"]["resolution"] = TEST_RES
    by[120]["inputs"]["audio"] = [25, 0]                  # draft's own soundtrack
    by[121]["inputs"]["audio"] = [120, 1]
    by[122]["inputs"]["filename_prefix"] = "video/h3_draft_regen"
    by[110]["inputs"]["vae"] = [105, 0]
    # stage-1 length default also drops to the test length
    by[18]["inputs"]["length"] = TEST_FRAMES
    return nodes


NODES = build_nodes()
GROUPS = [(t, b, c) for (t, b, c) in s1.GROUPS] + [
    ("S2-1. Models + Regen LoRA + Sol-Attn", [16, Y_OFF - 10, 740, 800], "#3f789e"),
    ("S2-2. Prepare / encode draft", [766, Y_OFF - 10, 380, 760], "#8A8"),
    ("S2-3. Upscale + refine setup", [1146, Y_OFF - 10, 380, 760], "#b58b2a"),
    ("S2-4. Sample", [1526, Y_OFF - 10, 380, 760], "#a1309b"),
    ("S2-5. Decode + save", [1906, Y_OFF - 10, 380, 760], "#88A"),
]

api = build_api(NODES)
for spec in api.values():
    for k, v in spec["inputs"].items():
        if isinstance(v, list):
            spec["inputs"][k] = [str(v[0]), v[1]]
standard = build_standard(NODES, GROUPS, NOTE)

wf = GraydientWorkflow(name="h3-draft-regen-v1", description=DESCRIPTION)
wf.author = "UnlimitedEditing"
wf.set_workflows(standard, api)
stage_model(wf, CONCEPT_KEY)
for url in ("https://github.com/kijai/ComfyUI-KJNodes",
            "https://github.com/1038lab/ComfyUI-RMBG",
            "https://github.com/rdh9616/ComfyUI-Open-H3-Regenerate",
            "https://github.com/LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler"):
    wf.add_github_requirement(url)

fields = []
for f in s1.wf.field_mapping:                      # stage-1 fields, unchanged node ids
    if f["local_field"] == "slot4":
        f = dict(f); f["default_value"] = str(TEST_FRAMES)
    if f["local_field"] == "steps":
        f = dict(f); f["minimum_value"] = "3"   # parent capped at 4; 3 must be reachable
    fields.append(f)
fields += [
    fm("slot4", 109, "max_frames", 1, "Prepare draft", default_value=TEST_FRAMES, minimum_value=5,
       maximum_value=361, help_text="Kept equal to the draft length (slot4)."),
    fm("slot5", 113, "start_sigma", 1, "Regen sigmas", default_value=0.0, minimum_value=0.0,
       maximum_value=0.95, help_text="0 = NVIDIA release recipe (start sigma 0.909). 0.8 stays closer to the draft."),
]
fields.append(fm("slot6", 113, "steps", 0, "Regen sigmas", default_value=3, minimum_value=1, maximum_value=8,
                 help_text="Regenerate refine steps. 3 = NVIDIA's release recipe (sub-minute on consumer GPUs)."))
wf.field_mapping = fields
wf.avg_elapsed = None
wf.metadata.update(FLAGS_OFF)
wf.metadata.update({"supports_img2vid": True, "peak_vram_usage": 24000})  # estimate, NOT measured

if __name__ == "__main__":
    write_json(os.path.join(BASE_DIR, "h3-draft-regen-v1.json"), standard)
    write_json(os.path.join(BASE_DIR, "h3-draft-regen-v1-api.json"), api)
    wf.save(os.path.join(BASE_DIR, "GraydientWorkflow-h3-draft-regen-v1.json"))
    print(f"Graph: {len(api)} API nodes; {len(wf.concept_mapping)} staged files.")
