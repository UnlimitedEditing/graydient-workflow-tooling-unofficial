"""
MiniMax H3 "Partner Node" equivalents -- six local-weights Graydient workflows.

WHAT THIS IS
------------
Comfy-Org/ComfyUI PR #17424 ("[Partner Nodes] feat(MiniMax): add H3 Max Recast,
Extend, Reframe, Insert, Lip Sync and Camera Control nodes") adds six *API* nodes
(`MinimaxHailuo03Max*Node`, all `is_api_node=True` with USD price badges). Those
call the hosted MiniMax service and burn comfy.org credits; they cannot run the
user's staged local weights.

This generator builds the six *local open-weights equivalents* instead, using the
user's exact 10 staged assets and node IDs. All six share one backbone and differ only in a small task-specific conditioning/output island,
which is what makes them reasonable to ship as one batch.

ONE SOURCE OF TRUTH
-------------------
Both ComfyUI JSON formats are emitted from a single ordered node registry, so the
UI graph (`workflow`) and the API prompt graph (`workflow_2`) cannot drift apart
-- the classic porting bug where a widget index is right in one and wrong in the
other. `Graph.to_standard()` and `Graph.to_api()` walk the same declarations.

STATUS: built and statically verified, NOT yet run on a live Graydient GPU.
See README.md next to the emitted JSONs for the caveats that matter before
spending quota (LoRA strength vs step count, lip-sync tightness, reframe
approximation, and the dynamic-LoRA field_mapping convention).

Usage:
    python templates/gen_minimax_h3_partner_equivalents.py [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graydient_builder import GraydientWorkflow, lint_workflow, format_lint_report  # noqa: E402

# ---------------------------------------------------------------------------
# Constants -- H3 runs at a fixed 24 fps; lengths snap to the 17k+5 grid.
# ---------------------------------------------------------------------------
FPS = 24
DEFAULT_W, DEFAULT_H = 1024, 576          # both multiples of 32
DEFAULT_LENGTH = 124                       # 17*7+5, ~5.2 s
DEFAULT_STEPS = 4                          # see README: TaoMate 3-step vs 8-step turbo base
DEFAULT_TAOMATE_STRENGTH = 1.0

UNET = "10Eros_Max_h3_8stepTURBO_beta7_SingularityV2_int8HQ.safetensors"
CLIP = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
VAE_VIDEO = "minimax_h3_video_vae_int8_convrot.safetensors"
VAE_AUDIO = "minimax_h3_audio_vae_fp32.safetensors"
LORA_TAOMATE = "TaoMate-H3-3step-ComfyUI.safetensors"

HF_H3 = "https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main"

GITHUB_REQUIREMENTS = [
    "https://github.com/UnlimitedEditing/fluxdon-local-h3",
    "https://github.com/rgthree/rgthree-comfy",
    "https://github.com/yolain/ComfyUI-Easy-Use",
    "https://github.com/WASasquatch/was-node-suite-comfyui",
    "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite",
    "https://github.com/DoctorDiffusion/ComfyUI-MediaMixer",
    "https://github.com/seitanism/ComfyUI-H3-Motion-Context-MultiRef",
    "https://github.com/BitVectorApp/comfyui-optional-asset-loader",
]

# Graydient's fixed internal widget-suffix convention for easy loraStack dynamic
# LoRA slots, copied from node_schema_db.json's verified note (identical across
# the live Ltx2/H3 exports). These are NOT indices into our widgets_values.
LORA_SLOT_SUFFIX = {1: (12, 39), 2: (34, 14), 3: (15, 17), 4: (27, 25), 5: (33, 2)}

# ---------------------------------------------------------------------------
# Output socket registry -- (name, type) in slot order, verified against source.
# ---------------------------------------------------------------------------
OUTPUTS = {
    "UNETLoader": [("MODEL", "MODEL")],
    "CLIPLoader": [("CLIP", "CLIP")],
    "VAELoader": [("VAE", "VAE")],
    "LoraLoader": [("MODEL", "MODEL"), ("CLIP", "CLIP")],
    "easy loraStack": [("LORA_STACK", "LORA_STACK")],
    "easy loraStackApply": [("MODEL", "MODEL"), ("CLIP", "CLIP")],
    "MiniMaxH3SigmaShift": [("MODEL", "MODEL")],
    "MiniMaxH3AudioVAECompatibility": [("audio_vae", "VAE")],
    "MiniMaxH3ImageToVideo": [("CONDITIONING", "CONDITIONING"), ("LATENT", "LATENT")],
    "MiniMaxH3ReferenceToVideo": [("CONDITIONING", "CONDITIONING"), ("LATENT", "LATENT")],
    "MiniMaxH3AddGuide": [("CONDITIONING", "CONDITIONING")],
    "MiniMaxH3ExistingVideoMaskedContext": [
        ("latent", "LATENT"), ("trim_frames", "INT"),
        ("insert_frame", "INT"), ("preserved_frames", "INT"),
    ],
    "MiniMaxH3MotionContextTrim": [
        ("images", "IMAGE"), ("audio", "AUDIO"),
        ("crossfade_images", "IMAGE"), ("crossfade_frames", "INT"),
    ],
    "MiniMaxH3AssembleExtension": [("images", "IMAGE"), ("audio", "AUDIO")],
    "MiniMaxH3AssembleInterior": [("images", "IMAGE"), ("audio", "AUDIO")],
    "RandomNoise": [("NOISE", "NOISE")],
    "KSamplerSelect": [("SAMPLER", "SAMPLER")],
    "BasicScheduler": [("SIGMAS", "SIGMAS")],
    "BasicGuider": [("GUIDER", "GUIDER")],
    "SamplerCustomAdvanced": [("output", "LATENT"), ("denoised_output", "LATENT")],
    "VAEDecode": [("IMAGE", "IMAGE")],
    "VAEDecodeAudio": [("AUDIO", "AUDIO")],
    "CreateVideo": [("VIDEO", "VIDEO")],
    "SaveVideo": [],
    "VHS_LoadVideoPath": [
        ("IMAGE", "IMAGE"), ("frame_count", "INT"),
        ("audio", "AUDIO"), ("video_info", "VHS_VIDEOINFO"),
    ],
    "VHS_LoadAudio": [("audio", "AUDIO"), ("duration", "FLOAT")],
    "LoadImageOptional": [
        ("IMAGE", "IMAGE"), ("MASK", "MASK"),
        ("has_image", "BOOLEAN"), ("resolved_path", "STRING"),
    ],
    "ResizeAndPadImage": [("IMAGE", "IMAGE")],
    "ComfyMathExpression": [("FLOAT", "FLOAT"), ("INT", "INT"), ("BOOL", "BOOLEAN")],
    "PrimitiveInt": [("INT", "INT")],
    "PrimitiveFloat": [("FLOAT", "FLOAT")],
    "StringFormat": [("STRING", "STRING")],
    "StringConcatenate": [("STRING", "STRING")],
}


class Graph:
    """Ordered node registry that emits BOTH ComfyUI JSON formats."""

    def __init__(self):
        self.nodes = OrderedDict()
        self._links = []

    def add(self, nid, class_type, title, widgets, sockets=(), pos=(0, 0),
            size=(340, 200), linked_widgets=()):
        """
        widgets        ordered [(name, value)] -> widgets_values / API scalars
        sockets        ordered [(name, type, (src_id, src_slot) | None)]
        linked_widgets ordered [(name, type, (src_id, src_slot))] -- a widget
                       converted to an input. Keeps its widget value in the UI
                       graph but becomes a link in the API graph.
        """
        assert nid not in self.nodes, f"duplicate node id {nid}"
        assert class_type in OUTPUTS, f"unregistered class {class_type}"
        self.nodes[nid] = {
            "id": nid, "class_type": class_type, "title": title,
            "widgets": list(widgets), "sockets": list(sockets),
            "linked_widgets": list(linked_widgets),
            "pos": list(pos), "size": list(size),
        }
        return nid

    # -- API prompt format --------------------------------------------------
    def to_api(self):
        api = OrderedDict()
        for nid, n in self.nodes.items():
            inputs = OrderedDict()
            linked = {w[0]: w[2] for w in n["linked_widgets"]}
            for name, value in n["widgets"]:
                if name in linked:
                    src, slot = linked[name]
                    inputs[name] = [str(src), slot]
                else:
                    inputs[name] = value
            for name, _typ, src in n["sockets"]:
                if src is not None:
                    inputs[name] = [str(src[0]), src[1]]
            for name, _typ, src in n["linked_widgets"]:
                if name not in inputs:
                    inputs[name] = [str(src[0]), src[1]]
            api[str(nid)] = {"class_type": n["class_type"], "inputs": inputs,
                             "_meta": {"title": n["title"]}}
        return api

    # -- Standard UI format -------------------------------------------------
    def to_standard(self, workflow_id=None):
        """
        Converted widgets keep their slot in `widgets_values` AND gain an input
        entry carrying `widget: {name: ...}` -- that is how ComfyUI/litegraph
        serialises a widget promoted to an input, and it is what keeps
        field_mapping's node_input_index stable. Verified against the upstream
        MCR example workflows (a node whose context_length is link-driven still
        carries its scalar in widgets_values).
        """
        entries = {}
        for nid, n in self.nodes.items():
            e = [(nm, ty, src, False) for nm, ty, src in n["sockets"] if src is not None]
            e += [(nm, ty, src, True) for nm, ty, src in n["linked_widgets"]]
            entries[nid] = e

        out_links = {nid: {i: [] for i in range(len(OUTPUTS[n["class_type"]]))}
                     for nid, n in self.nodes.items()}
        inputs = {nid: [] for nid in self.nodes}
        links, lid = [], 0
        for nid in self.nodes:
            for slot, (nm, ty, src, is_linked) in enumerate(entries[nid]):
                if src[0] not in self.nodes:
                    raise ValueError(
                        f"node {nid} ({self.nodes[nid]['class_type']}) input '{nm}' "
                        f"references node {src[0]}, which was never added")
                lid += 1
                entry = {"name": nm, "type": ty, "link": lid}
                if is_linked:
                    entry["widget"] = {"name": nm}
                inputs[nid].append(entry)
                links.append([lid, src[0], src[1], nid, slot, ty])
                out_links[src[0]][src[1]].append(lid)

        rank = {nid: i for i, nid in enumerate(self._topo_order())}
        nodes = []
        for nid, n in self.nodes.items():
            outs = [{"name": nm, "type": ty, "links": out_links[nid][i], "slot_index": i}
                    for i, (nm, ty) in enumerate(OUTPUTS[n["class_type"]])]
            nodes.append({
                "id": nid, "type": n["class_type"], "title": n["title"],
                "pos": n["pos"], "size": n["size"], "flags": {},
                "order": rank[nid], "mode": 0,
                "inputs": inputs[nid], "outputs": outs,
                "properties": {"Node name for S&R": n["class_type"]},
                "widgets_values": [v for _k, v in n["widgets"]],
            })

        return {
            "id": workflow_id or str(uuid.uuid5(uuid.NAMESPACE_URL, "graydient/minimax-h3")),
            "revision": 0,
            "last_node_id": max(self.nodes), "last_link_id": lid,
            "nodes": nodes, "links": links, "groups": [], "config": {},
            "extra": {"ds": {"scale": 0.55, "offset": [0, 0]},
                      "VHS_MetadataImage": False, "VHS_KeepIntermediate": False},
            "version": 0.4,
        }

    def _topo_order(self):
        deps = {nid: {s[0] for _n, _t, s in n["sockets"] if s} |
                     {s[0] for _n, _t, s in n["linked_widgets"]}
                for nid, n in self.nodes.items()}
        done, order = set(), []
        while len(order) < len(self.nodes):
            ready = [nid for nid in self.nodes if nid not in done and deps[nid] <= done]
            if not ready:
                raise ValueError(f"cycle among {set(self.nodes) - done}")
            for nid in ready:
                order.append(nid)
                done.add(nid)
        return order

    def title(self, nid):
        return self.nodes[nid]["title"]

    def widget_index(self, nid, name):
        for i, (k, _v) in enumerate(self.nodes[nid]["widgets"]):
            if k == name:
                return i
        raise KeyError(f"{nid} has no widget {name}")

    def widget_value(self, nid, name):
        return dict(self.nodes[nid]["widgets"])[name]


# ---------------------------------------------------------------------------
# Shared backbone -- identical node IDs and wiring in all six workflows.
# ---------------------------------------------------------------------------
def add_backbone(g: Graph):
    g.add(127, "UNETLoader", "Load Diffusion Model",
          [("unet_name", UNET), ("weight_dtype", "default")], pos=(-40, 40), size=(400, 110))
    g.add(128, "CLIPLoader", "Load CLIP",
          [("clip_name", CLIP), ("type", "minimax"), ("device", "default")],
          pos=(-40, 210), size=(400, 130))
    g.add(119, "VAELoader", "Load VAE",
          [("vae_name", VAE_VIDEO)], pos=(-40, 400), size=(400, 80))
    g.add(120, "VAELoader", "Load VAE",
          [("vae_name", VAE_AUDIO)], pos=(-40, 530), size=(400, 80))

    # Single source of truth for the turbo-LoRA strength, linked into BOTH
    # strength_model and strength_clip so `strength 0` is a true bypass.
    g.add(318, "PrimitiveFloat", "Turbo LoRA Strength",
          [("value", DEFAULT_TAOMATE_STRENGTH)], pos=(420, -90), size=(360, 80))
    # Single source of truth for the canvas, shared by the H3 node and (in
    # reframe) the pad node, so the guide and the latent can never mismatch.
    g.add(319, "PrimitiveInt", "Width", [("value", DEFAULT_W)],
          pos=(-40, 660), size=(400, 80))
    g.add(320, "PrimitiveInt", "Height", [("value", DEFAULT_H)],
          pos=(-40, 790), size=(400, 80))

    g.add(317, "LoraLoader", "Load LoRA",
          [("lora_name", LORA_TAOMATE),
           ("strength_model", DEFAULT_TAOMATE_STRENGTH),
           ("strength_clip", DEFAULT_TAOMATE_STRENGTH)],
          sockets=[("model", "MODEL", (127, 0)), ("clip", "CLIP", (128, 0))],
          linked_widgets=[("strength_model", "FLOAT", (318, 0)),
                          ("strength_clip", "FLOAT", (318, 0))],
          pos=(420, 40), size=(360, 150))

    lora_widgets = [("toggle", True), ("mode", "simple"), ("num_loras", 5)]
    for i in range(1, 11):
        lora_widgets += [(f"lora_{i}_name", "None"), (f"lora_{i}_strength", 1.0),
                         (f"lora_{i}_model_strength", 1.0), (f"lora_{i}_clip_strength", 1.0)]
    g.add(171, "easy loraStack", "EasyLoraStack", lora_widgets,
          pos=(420, 250), size=(360, 700))

    g.add(172, "easy loraStackApply", "Apply LoRA Stack", [],
          sockets=[("lora_stack", "LORA_STACK", (171, 0)),
                   ("model", "MODEL", (317, 0)),
                   ("optional_clip", "CLIP", (317, 1))],
          pos=(840, 40), size=(300, 110))

    g.add(130, "MiniMaxH3SigmaShift", "ModelSamplingMiniMaxH3",
          [("shift_video", 12.0), ("shift_audio", 3.0)],
          sockets=[("model", "MODEL", (172, 0))], pos=(840, 210), size=(300, 110))

    g.add(121, "MiniMaxH3AudioVAECompatibility", "H3 Audio VAE Compatibility", [],
          sockets=[("audio_vae", "VAE", (120, 0))], pos=(840, 380), size=(300, 70))

    g.add(140, "RandomNoise", "RandomNoise",
          [("noise_seed", 123456789), ("mode", "fixed")], pos=(2680, 40), size=(300, 90))
    g.add(141, "KSamplerSelect", "KSamplerSelect",
          [("sampler_name", "res_multistep")], pos=(2680, 180), size=(300, 80))


def add_sampler_and_output(g: Graph, conditioning_src, latent_src, images_src, audio_src,
                           prefix, steps=DEFAULT_STEPS, decode_audio=True):
    # `prefix` is kept in the signature for readability at the call sites but is
    # deliberately NOT used: a single shared prefix keeps node 148 byte-identical
    # across all six workflows, which is the point of shipping them as a batch.
    g.add(142, "BasicScheduler", "BasicScheduler",
          [("scheduler", "simple"), ("steps", steps), ("denoise", 1.0)],
          sockets=[("model", "MODEL", (130, 0))], pos=(2680, 300), size=(300, 130))
    g.add(143, "BasicGuider", "BasicGuider", [],
          sockets=[("model", "MODEL", (130, 0)),
                   ("conditioning", "CONDITIONING", conditioning_src)],
          pos=(2680, 480), size=(300, 90))
    g.add(144, "SamplerCustomAdvanced", "SamplerCustomAdvanced", [],
          sockets=[("noise", "NOISE", (140, 0)), ("guider", "GUIDER", (143, 0)),
                   ("sampler", "SAMPLER", (141, 0)), ("sigmas", "SIGMAS", (142, 0)),
                   ("latent_image", "LATENT", latent_src)],
          pos=(3040, 40), size=(320, 150))
    g.add(145, "VAEDecode", "VAEDecode", [],
          sockets=[("samples", "LATENT", (144, 0)), ("vae", "VAE", (119, 0))],
          pos=(3040, 250), size=(280, 90))
    # Lip-sync muxes the ORIGINAL speech track and never consumes a decoded audio
    # latent, so it opts out. Extend/insert DO need it (their trim/assemble nodes
    # take it), even though their mux reads from the assembler instead.
    if decode_audio:
        g.add(146, "VAEDecodeAudio", "VAEDecodeAudio", [],
              sockets=[("samples", "LATENT", (144, 0)), ("vae", "VAE", (121, 0))],
              pos=(3040, 390), size=(280, 90))
    g.add(147, "CreateVideo", "Create Video",
          [("fps", float(FPS)), ("bit_depth", 8)],
          sockets=[("images", "IMAGE", images_src), ("audio", "AUDIO", audio_src)],
          pos=(3400, 40), size=(300, 130))
    # format/codec 'auto' resolves to MP4/H.264 for a CreateVideo image source.
    # This flat auto/auto pair is the shape confirmed by a real Graydient job
    # (gen_ltx25_ripple.py, render 39yNVD) -- see node_schema_db.json.
    g.add(148, "SaveVideo", "Save Video",
          [("filename_prefix", "video/MiniMax_H3"), ("format", "auto"), ("codec", "auto")],
          sockets=[("video", "VIDEO", (147, 0))], pos=(3400, 230), size=(340, 150))


def add_source_video(g: Graph, y=700):
    g.add(201, "VHS_LoadVideoPath", "Load Video (Path)",
          [("video", ""), ("force_rate", FPS), ("custom_width", 0), ("custom_height", 0),
           ("frame_load_cap", 0), ("skip_first_frames", 0), ("select_every_nth", 1)],
          pos=(420, y), size=(380, 250))


def add_optional_image(g: Graph, nid, y, title="Load Image (Optional)", required=True):
    g.add(nid, "LoadImageOptional", title,
          [("image_path", ""),
           ("fallback_patterns", "blank_start.png, none, null, empty, undefined"),
           ("missing_behavior", "Raise Error" if required else "Return None"),
           ("blank_width", 512), ("blank_height", 512), ("blank_color", "black")],
          pos=(420, y), size=(380, 200))


def i2v_widgets(prompt, length=DEFAULT_LENGTH, w=DEFAULT_W, h=DEFAULT_H):
    return [("prompt", prompt), ("width", w), ("height", h), ("length", length)]


# ---------------------------------------------------------------------------
# Task builders. Each returns (graph, field_mapping_specs, description).
# A spec is (node_id, widget_name, local_field, help_text, min, max).
# ---------------------------------------------------------------------------
def build_recast():
    g = Graph()
    add_backbone(g)
    add_source_video(g)
    add_optional_image(g, 202, 1000, "Load Image (Optional) - Identity 1")
    add_optional_image(g, 203, 1240, "Load Image (Optional) - Identity 2", required=False)
    prompt = ("Replace the person in <Video 1> with the person shown in <Picture 1>. "
              "Preserve the exact body motion, camera move, framing and timing of <Video 1>. "
              "Keep the original background and lighting.")
    g.add(210, "MiniMaxH3ReferenceToVideo", "MiniMax H3 Reference to Video",
          i2v_widgets(prompt) + [("ref_image_size", "match")],
          sockets=[("clip", "CLIP", (172, 1)), ("vae", "VAE", (119, 0)),
                   ("audio_vae", "VAE", (121, 0)),
                   ("ref_images.ref_image_0", "IMAGE", (202, 0)),
                   ("ref_images.ref_image_1", "IMAGE", (203, 0)),
                   ("ref_videos.ref_video_0", "IMAGE", (201, 0)),
                   ("ref_video_audios.ref_video_audio_0", "AUDIO", (201, 2))],
          linked_widgets=[("width", "INT", (319, 0)), ("height", "INT", (320, 0))],
          pos=(1240, 40), size=(460, 400))
    add_sampler_and_output(g, (210, 0), (210, 1), (145, 0), (146, 0), "video/h3_recast")
    fm = [
        (210, "prompt", "prompt_positive", "Use <Picture 1>/<Picture 2> for the new identity and <Video 1> for the source motion.", None, None),
        (201, "video", "init_video_filename", "Source video whose motion is kept.", None, None),
        (202, "image_path", "image1", "New identity reference (required).", None, None),
        (203, "image_path", "image2", "Second identity reference (optional).", None, None),
    ]
    return g, fm, ("Recast a source video with a new identity from a reference photo, keeping the "
                   "original motion, camera and timing. Local-weights equivalent of the H3 Max Recast partner node.")


def build_extend():
    g = Graph()
    add_backbone(g)
    add_source_video(g)
    prompt = ("Continue the action seamlessly from the preserved opening. Same subject, "
              "same wardrobe, same lighting, same lens. Natural continuous motion, no cut.")
    g.add(210, "MiniMaxH3ImageToVideo", "MiniMax H3 Image to Video",
          i2v_widgets(prompt, length=243),
          sockets=[("clip", "CLIP", (172, 1)), ("vae", "VAE", (119, 0))],
          linked_widgets=[("width", "INT", (319, 0)), ("height", "INT", (320, 0))],
          pos=(1240, 40), size=(460, 300))
    g.add(212, "MiniMaxH3ExistingVideoMaskedContext", "H3 Existing Video Masked Context",
          [("source_fps", 24.0), ("context_length", 39), ("crop", "center"),
           ("audio_feather_ticks", 8), ("insert_frame", 0)],
          sockets=[("latent", "LATENT", (210, 1)), ("vae", "VAE", (119, 0)),
                   ("audio_vae", "VAE", (121, 0)),
                   ("source_frames", "IMAGE", (201, 0)), ("source_audio", "AUDIO", (201, 2))],
          pos=(1760, 40), size=(440, 260))
    add_sampler_and_output(g, (210, 0), (212, 0), (214, 0), (214, 1), "video/h3_extend")
    g.add(213, "MiniMaxH3MotionContextTrim", "H3 Motion Context Trim",
          [("fps", 24.0), ("match_tail", True), ("video_crossfade_frames", 39)],
          sockets=[("images", "IMAGE", (145, 0)), ("audio", "AUDIO", (146, 0)),
                   ("trim_frames", "INT", (212, 1))],
          pos=(3040, 540), size=(360, 160))
    g.add(214, "MiniMaxH3AssembleExtension", "H3 Assemble Extension",
          [("source_fps", 24.0), ("fps", 24.0), ("crop", "center")],
          sockets=[("source_frames", "IMAGE", (201, 0)), ("source_audio", "AUDIO", (201, 2)),
                   ("continuation_images", "IMAGE", (213, 0)),
                   ("continuation_audio", "AUDIO", (213, 1))],
          pos=(3040, 750), size=(380, 190))
    fm = [
        (210, "prompt", "prompt_positive", "Describe what happens AFTER the source clip ends.", None, None),
        (201, "video", "init_video_filename", "Clip to continue. Must be constant 24 fps (loader forces it).", None, None),
        (212, "context_length", "slot2", "Preserved tail of the source, snapped to 39/90/141/192 frames.", 5, 192),
        (210, "length", "length", "TOTAL timeline length incl. the preserved prefix (17k+5 grid).", 5, 361),
    ]
    return g, fm, ("Extend a clip forward: the source tail is preserved pixel-exactly and H3 generates "
                   "the continuation, then both are assembled with sample-exact audio. Local equivalent of H3 Max Extend.")


def build_insert():
    g = Graph()
    add_backbone(g)
    add_source_video(g)
    prompt = ("Generate the middle section of this shot. Match the subject, wardrobe, "
              "lighting and lens of the preserved footage on both sides. Continuous motion, no cut.")
    g.add(210, "MiniMaxH3ImageToVideo", "MiniMax H3 Image to Video",
          i2v_widgets(prompt, length=243),
          sockets=[("clip", "CLIP", (172, 1)), ("vae", "VAE", (119, 0))],
          linked_widgets=[("width", "INT", (319, 0)), ("height", "INT", (320, 0))],
          pos=(1240, 40), size=(460, 300))
    g.add(212, "MiniMaxH3ExistingVideoMaskedContext", "H3 Existing Video Masked Context",
          [("source_fps", 24.0), ("context_length", 39), ("crop", "center"),
           ("audio_feather_ticks", 8), ("insert_frame", 51)],
          sockets=[("latent", "LATENT", (210, 1)), ("vae", "VAE", (119, 0)),
                   ("audio_vae", "VAE", (121, 0)),
                   ("source_frames", "IMAGE", (201, 0)), ("source_audio", "AUDIO", (201, 2))],
          pos=(1760, 40), size=(440, 260))
    add_sampler_and_output(g, (210, 0), (212, 0), (214, 0), (214, 1), "video/h3_insert")
    g.add(214, "MiniMaxH3AssembleInterior", "H3 Assemble Interior",
          [("source_fps", 24.0), ("fps", 24.0), ("crop", "center")],
          sockets=[("continuation_images", "IMAGE", (145, 0)),
                   ("continuation_audio", "AUDIO", (146, 0)),
                   ("source_frames", "IMAGE", (201, 0)), ("source_audio", "AUDIO", (201, 2)),
                   ("insert_frame", "INT", (212, 2)), ("preserved_frames", "INT", (212, 3))],
          pos=(3040, 540), size=(400, 230))
    fm = [
        (210, "prompt", "prompt_positive", "Describe the replacement middle section.", None, None),
        (201, "video", "init_video_filename", "Source clip. Must be constant 24 fps (loader forces it).", None, None),
        (212, "insert_frame", "slot1", "Frame where the generated section starts; snaps down to a multiple of 17.", 0, 340),
        (212, "context_length", "slot2", "Generated window length, snapped to 39/90/141/192 frames.", 5, 192),
        (210, "length", "length", "TOTAL timeline length; set to the source frame count (17k+5 grid).", 5, 361),
    ]
    return g, fm, ("Replace an interior window of a clip while keeping the footage before and after it "
                   "pixel-exact. Local equivalent of the H3 Max Insert partner node.")


def build_reframe():
    g = Graph()
    add_backbone(g)
    add_source_video(g)
    prompt = ("Fill the newly added border areas with a natural continuation of the existing scene. "
              "Keep the original subject, its motion and the original framing unchanged in the centre. "
              "Match perspective, grain and lighting across the whole frame.")
    g.add(205, "ResizeAndPadImage", "Resize And Pad Image",
          [("target_width", DEFAULT_W), ("target_height", DEFAULT_H),
           ("padding_color", "black"), ("interpolation", "lanczos")],
          sockets=[("image", "IMAGE", (201, 0))],
          linked_widgets=[("target_width", "INT", (319, 0)),
                          ("target_height", "INT", (320, 0))],
          pos=(880, 700), size=(360, 160))
    g.add(210, "MiniMaxH3ImageToVideo", "MiniMax H3 Image to Video",
          i2v_widgets(prompt),
          sockets=[("clip", "CLIP", (172, 1)), ("vae", "VAE", (119, 0))],
          linked_widgets=[("width", "INT", (319, 0)), ("height", "INT", (320, 0))],
          pos=(1240, 40), size=(460, 300))
    g.add(211, "MiniMaxH3AddGuide", "Add Guide for MiniMax H3",
          [("frame_idx", 0)],
          sockets=[("positive", "CONDITIONING", (210, 0)), ("vae", "VAE", (119, 0)),
                   ("audio_vae", "VAE", (121, 0)), ("latent", "LATENT", (210, 1)),
                   ("image", "IMAGE", (205, 0)), ("audio", "AUDIO", (201, 2))],
          pos=(1760, 40), size=(420, 220))
    add_sampler_and_output(g, (211, 0), (210, 1), (145, 0), (146, 0), "video/h3_reframe")
    fm = [
        (210, "prompt", "prompt_positive", "Describe what should fill the new border area.", None, None),
        (201, "video", "init_video_filename", "Source clip to reframe.", None, None),
        (210, "length", "length", "Output length; match the source frame count (17k+5 grid).", 5, 361),
    ]
    return g, fm, ("Reframe a clip onto a new canvas: the source is letter/pillar-boxed onto the target "
                   "size and used as a guide while H3 fills the new borders. Guide-based approximation of H3 Max Reframe.")


def build_lipsync():
    g = Graph()
    add_backbone(g)
    add_optional_image(g, 202, 700, "Load Image (Optional) - Portrait")
    g.add(203, "VHS_LoadAudio", "Load Audio (VHS)",
          [("audio_file", ""), ("seek_seconds", 0.0), ("duration", 0.0)],
          pos=(420, 960), size=(380, 150))
    # Duration (FLOAT, slot 1) -> frames, clamped to the trained range. INT is slot 1.
    g.add(204, "ComfyMathExpression", "Math Expression",
          [("expression", "min(max(round(a * 24), 5), 243)")],
          sockets=[("values.a", "FLOAT", (203, 1))], pos=(880, 960), size=(340, 120))
    prompt = ("The person speaks the provided audio. Accurate lip and jaw movement synced to the "
              "speech, natural micro-expressions, subtle head motion, occasional blinks. "
              "Static camera, unchanged background.")
    g.add(210, "MiniMaxH3ImageToVideo", "MiniMax H3 Image to Video",
          i2v_widgets(prompt),
          sockets=[("clip", "CLIP", (172, 1)), ("vae", "VAE", (119, 0)),
                   ("first_frame", "IMAGE", (202, 0))],
          linked_widgets=[("length", "INT", (204, 1)),
                          ("width", "INT", (319, 0)), ("height", "INT", (320, 0))],
          pos=(1240, 40), size=(460, 320))
    g.add(211, "MiniMaxH3AddGuide", "Add Guide for MiniMax H3",
          [("frame_idx", 0)],
          sockets=[("positive", "CONDITIONING", (210, 0)), ("vae", "VAE", (119, 0)),
                   ("audio_vae", "VAE", (121, 0)), ("latent", "LATENT", (210, 1)),
                   ("audio", "AUDIO", (203, 0))],
          pos=(1760, 40), size=(420, 220))
    # Mux the ORIGINAL audio, not the VAE round-trip (node_schema_db CreateVideo note).
    add_sampler_and_output(g, (211, 0), (210, 1), (145, 0), (203, 0), "video/h3_lipsync",
                           decode_audio=False)
    fm = [
        (210, "prompt", "prompt_positive", "Describe the speaker and delivery style.", None, None),
        (202, "image_path", "image1", "Portrait / first frame of the speaker.", None, None),
        (203, "audio_file", "init_audio_filename", "Speech track. Its duration sets the video length automatically.", None, None),
    ]
    return g, fm, ("Animate a portrait so the mouth follows a speech track. Video length is derived from "
                   "the audio and the original audio is muxed back untouched. Local equivalent of H3 Max Lip Sync.")


def build_camera():
    g = Graph()
    add_backbone(g)
    add_optional_image(g, 202, 700, "Load Image (Optional) - First Frame")
    g.add(207, "PrimitiveInt", "Azimuth (degrees)", [("value", 45)],
          pos=(420, 960), size=(320, 80))
    g.add(208, "PrimitiveInt", "Elevation (degrees)", [("value", 10)],
          pos=(420, 1090), size=(320, 80))
    g.add(209, "PrimitiveFloat", "Distance (x)", [("value", 1.0)],
          pos=(420, 1220), size=(320, 80))
    g.add(206, "StringFormat", "Format Text",
          [("f_string", ("Camera move: orbit {a} degrees in azimuth (positive = move right around "
                         "the subject), {b} degrees in elevation (positive = rise above), and dolly "
                         "to {c}x the starting distance. One smooth continuous move, no cuts."))],
          sockets=[("values.a", "INT", (207, 0)), ("values.b", "INT", (208, 0)),
                   ("values.c", "FLOAT", (209, 0))],
          pos=(880, 960), size=(400, 200))
    g.add(215, "StringConcatenate", "Concatenate Text",
          [("string_a", "Cinematic shot, stable subject, consistent lighting."),
           ("string_b", ""), ("delimiter", "\n")],
          linked_widgets=[("string_b", "STRING", (206, 0))],
          pos=(1240, 700), size=(400, 200))

    g.add(210, "MiniMaxH3ImageToVideo", "MiniMax H3 Image to Video",
          i2v_widgets(""),
          sockets=[("clip", "CLIP", (172, 1)), ("vae", "VAE", (119, 0)),
                   ("first_frame", "IMAGE", (202, 0))],
          linked_widgets=[("prompt", "STRING", (215, 0)),
                          ("width", "INT", (319, 0)), ("height", "INT", (320, 0))],
          pos=(1760, 40), size=(460, 320))
    add_sampler_and_output(g, (210, 0), (210, 1), (145, 0), (146, 0), "video/h3_camera")
    fm = [
        (215, "string_a", "prompt_positive", "Scene description; the camera move is appended automatically.", None, None),
        (202, "image_path", "image1", "First frame / scene image.", None, None),
        (207, "value", "slot1", "Azimuth in degrees (+ = orbit right).", -360, 360),
        (208, "value", "slot2", "Elevation in degrees (+ = rise).", -90, 90),
        (209, "value", "slot3", "Dolly distance multiplier (1.0 = hold).", 0.1, 5.0),
    ]
    return g, fm, ("Drive a virtual camera around a still image with numeric azimuth / elevation / dolly "
                   "controls compiled into the prompt. Local equivalent of H3 Max Camera Control.")


TASKS = OrderedDict([
    ("recast", build_recast),
    ("extend", build_extend),
    ("reframe", build_reframe),
    ("insert", build_insert),
    ("lipsync", build_lipsync),
    ("camera-control", build_camera),
])


# The local custom-node pack owns task-specific H3 preparation. Existing core
# sampling/decoding and the original asset-loader IDs stay visible in the graph.
LOCAL_CLASSES = {
    "recast": "FluxdonH3Recast", "extend": "FluxdonH3Extend",
    "reframe": "FluxdonH3Reframe", "insert": "FluxdonH3Insert",
    "lipsync": "FluxdonH3LipSync", "camera-control": "FluxdonH3CameraControl",
}
for _slug, _class in LOCAL_CLASSES.items():
    OUTPUTS[_class] = ([("positive", "CONDITIONING"), ("latent", "LATENT")] +
        ([("trim_frames", "INT"), ("insert_frame", "INT"), ("preserved_frames", "INT")]
         if _slug in ("extend", "insert") else []))


def use_local_task_node(slug, g, specs):
    n = g.nodes[210]
    n["class_type"] = LOCAL_CLASSES[slug]
    n["title"] = f"Fluxdon H3 {slug.replace('-', ' ').title()} Local"
    if slug == "recast":
        names = {"ref_images.ref_image_0": "identity", "ref_images.ref_image_1": "identity_2",
                 "ref_videos.ref_video_0": "source_frames", "ref_video_audios.ref_video_audio_0": "source_audio"}
        n["sockets"] = [(names.get(name, name), typ, src) for name, typ, src in n["sockets"]]
    elif slug in ("extend", "insert"):
        context = g.nodes.pop(212)
        n["widgets"].extend(context["widgets"])
        n["sockets"].extend(s for s in context["sockets"] if s[0] != "latent" and s[0] != "vae")
        # Old context outputs (latent, trim, insert, preserved) become slots 1..4.
        for node in g.nodes.values():
            for field in ("sockets", "linked_widgets"):
                node[field] = [(name, typ, (210, src[1] + 1) if src and src[0] == 212 else src)
                               for name, typ, src in node[field]]
        specs = [(210 if nid == 212 else nid, widget, local, help_text, mn, mx)
                 for nid, widget, local, help_text, mn, mx in specs]
    elif slug in ("reframe", "lipsync"):
        guide = g.nodes.pop(211)
        n["sockets"].extend((name if name != "image" else "guide_frames", typ, src)
                            for name, typ, src in guide["sockets"]
                            if name not in ("positive", "latent", "vae"))
        if slug == "reframe":
            n["sockets"] = [("source_audio" if name == "audio" else name, typ, src)
                            for name, typ, src in n["sockets"]]
        else:
            n["sockets"] = [("portrait" if name == "first_frame" else "speech" if name == "audio" else name, typ, src)
                            for name, typ, src in n["sockets"]]
        for node in g.nodes.values():
            for field in ("sockets", "linked_widgets"):
                node[field] = [(name, typ, (210, 0) if src and src[0] == 211 else src)
                               for name, typ, src in node[field]]
    elif slug == "camera-control":
        prompt = g.nodes[215]["widgets"][0][1]
        n["widgets"] = [(name, prompt if name == "prompt" else val) for name, val in n["widgets"]]
        n["widgets"].extend([("azimuth", 45), ("elevation", 10), ("dolly", 1.0)])
        n["linked_widgets"] = [x for x in n["linked_widgets"] if x[0] != "prompt"]
        n["linked_widgets"].extend([("azimuth", "INT", (207, 0)),
                                    ("elevation", "INT", (208, 0)), ("dolly", "FLOAT", (209, 0))])
        del g.nodes[206], g.nodes[215]
        specs = [(210, "prompt", local, help_text, mn, mx) if nid == 215 else
                 (nid, widget, local, help_text, mn, mx)
                 for nid, widget, local, help_text, mn, mx in specs]
    return specs


# ---------------------------------------------------------------------------
# Concept + field mapping
# ---------------------------------------------------------------------------
def add_concepts(wf: GraydientWorkflow, g: Graph):
    def static(url, dest, node_id, widget):
        wf.add_concept_mapping(url, dest)
        wf.concept_mapping[-1]["field_mapping"] = (
            f"{node_id}-{g.title(node_id)}.{g.widget_index(node_id, widget)}-{widget}")

    static(f"{HF_H3}/text_encoders/{CLIP}", f"text_encoders/{CLIP}", 128, "clip_name")
    static(f"{HF_H3}/vae/{VAE_AUDIO}", f"vae/{VAE_AUDIO}", 120, "vae_name")
    static(f"{HF_H3}/vae/{VAE_VIDEO}", f"vae/{VAE_VIDEO}", 119, "vae_name")
    static(f"https://huggingface.co/CZMartin22/TaoMate-H3-3step-ComfyUI/resolve/main/{LORA_TAOMATE}",
           f"loras/{LORA_TAOMATE}", 317, "lora_name")
    static(f"https://huggingface.co/OliviaRossi/Minimax-h3_Singularity-x-10Eros-Max_PRISM/resolve/main/{UNET}",
           f"diffusion_models/{UNET}", 127, "unet_name")

    # Five dynamic H3 LoRA slots, weight-mapped.
    for slot in range(1, 6):
        name_idx, strength_idx = LORA_SLOT_SUFFIX[slot]
        wf.concept_mapping.append({
            "allow_dynamic": True, "concept_name": None, "concept_type": None,
            "dynamic_family": "H3", "dynamic_subtype_1": None, "dynamic_subtype_2": None,
            "dynamic_type": "lora",
            "field_mapping": f"171-EasyLoraStack.{name_idx}-lora_{slot}_name",
            "is_zipped": False, "type": "local", "url": None, "destination": None,
            "weight": None,
            "weight_field_mapping": f"171-EasyLoraStack.{strength_idx}-lora_{slot}_strength",
        })


def add_fields(wf: GraydientWorkflow, g: Graph, specs):
    seen = set()
    for nid, widget, local, help_text, mn, mx in specs:
        wf.add_field_mapping(
            node_id=nid, node_input_name=widget, local_field=local,
            node_name=g.title(nid), node_input_index=g.widget_index(nid, widget),
            default_value=g.widget_value(nid, widget),
            minimum_value=mn, maximum_value=mx, help_text=help_text)
        seen.add(local)

    # Common controls present in every graph.
    common = [
        (140, "noise_seed", "seed", "Random seed.", 0, 2147483647),
        (142, "steps", "steps", "Sampling steps. 4 = TaoMate 3-step LoRA + 1; use 8 with strength 0.", 1, 20),
        (318, "value", "strength", "TaoMate turbo LoRA strength, applied to model AND clip. 0.0 disables it (then use 8 steps).", 0.0, 2.0),
        (319, "value", "width", "Canvas width (multiple of 32). Shared by the H3 node and the reframe pad.", None, None),
        (320, "value", "height", "Canvas height (multiple of 32). Shared by the H3 node and the reframe pad.", None, None),
    ]
    if 210 in g.nodes and g.nodes[210]["class_type"] in LOCAL_CLASSES.values():
        if "length" not in seen and not any(w[0] == "length" for w in g.nodes[210]["linked_widgets"]):
            common.append((210, "length", "length", "Frame count at 24 fps, snapped to the 17k+5 grid.", 5, 361))
    for nid, widget, local, help_text, mn, mx in common:
        wf.add_field_mapping(
            node_id=nid, node_input_name=widget, local_field=local,
            node_name=g.title(nid), node_input_index=g.widget_index(nid, widget),
            default_value=g.widget_value(nid, widget),
            minimum_value=mn, maximum_value=mx, help_text=help_text)


# ---------------------------------------------------------------------------
# Structural self-check (independent of the Graydient linter)
# ---------------------------------------------------------------------------
def verify(g: Graph, standard, api):
    errs = []
    ids = set(g.nodes)
    for nid, node in api.items():
        for key, val in node["inputs"].items():
            if isinstance(val, list) and len(val) == 2 and isinstance(val[0], str):
                src, slot = val
                if int(src) not in ids:
                    errs.append(f"api {nid}.{key} -> missing node {src}")
                elif not (0 <= slot < len(OUTPUTS[g.nodes[int(src)]["class_type"]])):
                    errs.append(f"api {nid}.{key} -> bad slot {slot} on {src}")
    by_id = {n["id"]: n for n in standard["nodes"]}
    if set(by_id) != ids:
        errs.append("standard/api node id sets differ")
    for lid, src, slot, dst, dslot, ty in standard["links"]:
        if src not in by_id or dst not in by_id:
            errs.append(f"link {lid} dangling")
            continue
        if by_id[dst]["inputs"][dslot]["link"] != lid:
            errs.append(f"link {lid} target slot mismatch")
        if lid not in by_id[src]["outputs"][slot]["links"]:
            errs.append(f"link {lid} missing from source output links")
    # Every API link must have a matching standard link and vice versa.
    api_edges = {(int(nid), k, v[0], v[1])
                 for nid, n in api.items() for k, v in n["inputs"].items()
                 if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str)}
    std_edges = {(dst, by_id[dst]["inputs"][ds]["name"], str(src), sl)
                 for _l, src, sl, dst, ds, _t in standard["links"]}
    if api_edges != std_edges:
        errs.append(f"edge mismatch: api-only={api_edges - std_edges} std-only={std_edges - api_edges}")
    # Reachability from the output node.
    reach, stack = set(), [148]
    while stack:
        cur = stack.pop()
        if cur in reach:
            continue
        reach.add(cur)
        for _n, _t, s in g.nodes[cur]["sockets"]:
            if s:
                stack.append(s[0])
        for _n, _t, s in g.nodes[cur]["linked_widgets"]:
            stack.append(s[0])
    orphans = ids - reach
    if orphans:
        errs.append(f"nodes unreachable from SaveVideo: {sorted(orphans)}")
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="workflows/minimax-h3-partner-equivalents")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    graphs, failures = {}, 0
    for slug, builder in TASKS.items():
        g, specs, description = builder()
        specs = use_local_task_node(slug, g, specs)
        wid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"graydient/minimax-h3/{slug}"))
        standard, api = g.to_standard(workflow_id=wid), g.to_api()
        problems = verify(g, standard, api)
        graphs[slug] = (g, standard, api)

        wf = GraydientWorkflow(name=f"minimax-h3-{slug}-v1", description=description)
        wf.set_workflows(standard, api)
        add_concepts(wf, g)
        add_fields(wf, g, specs)
        for repo in GITHUB_REQUIREMENTS:
            wf.add_github_requirement(repo)
        # requirements.pip MUST stay empty: opencv-python / imageio-ffmpeg pins
        # numpy 1.26.4 under a SciPy that needs >=2 and crashes ComfyUI on import.
        wf.avg_elapsed = 150
        wf.set_flag("supports_txt2vid", True)
        wf.set_flag("supports_img2vid", slug in ("recast", "lipsync", "camera-control"))
        wf.set_flag("supports_vid2vid", slug in ("recast", "extend", "reframe", "insert"))
        # All six carry five allow_dynamic H3 LoRA concepts.
        wf.set_flag("supports_dynamic_concepts", True)
        wf.set_flag("install_detected_nodes", True)

        data = wf.to_dict()
        ok, issues = lint_workflow(data)
        errors = [i for i in issues if i.level == "ERROR"]
        warnings = [i for i in issues if i.level == "WARNING"]
        print(f"\n{'=' * 70}\n{slug}: {len(g.nodes)} nodes, "
              f"{len(errors)} lint errors, {len(warnings)} warnings, "
              f"{len(problems)} structural problems")
        if problems:
            for p in problems:
                print("  [STRUCT]", p)
        if errors or warnings:
            print(format_lint_report([i for i in issues if i.level != "INFO"]))
        if errors or problems:
            failures += 1
            continue
        path = os.path.join(args.out, f"GraydientWorkflow-minimax-h3-{slug}-v1.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"  [SAVED] {path}")

    # Batch similarity. Two complementary numbers, both reported so the claim
    # "~95% the same" can be judged rather than asserted.
    import difflib
    print(f"\n{'=' * 70}\nBatch similarity:")
    core = None
    for slug, (g, _s, api) in graphs.items():
        sigs = {nid: json.dumps(api[str(nid)], sort_keys=True) for nid in g.nodes}
        core = dict(sigs) if core is None else {
            k: v for k, v in core.items() if sigs.get(k) == v}
    print(f"  Nodes byte-identical in ALL six: {len(core)} -> {sorted(core)}")
    base_txt = json.dumps(graphs['recast'][1], indent=2).splitlines()
    base_file = open(os.path.join(args.out, "GraydientWorkflow-minimax-h3-recast-v1.json"),
                     encoding="utf-8").read().splitlines()
    for slug, (g, std, api) in graphs.items():
        txt = json.dumps(std, indent=2).splitlines()
        ratio = difflib.SequenceMatcher(None, base_txt, txt).ratio()
        fp = os.path.join(args.out, f"GraydientWorkflow-minimax-h3-{slug}-v1.json")
        fratio = difflib.SequenceMatcher(
            None, base_file, open(fp, encoding="utf-8").read().splitlines()).ratio()
        print(f"  {slug:<16} {len(g.nodes):>2} nodes | graph {ratio * 100:5.1f}% | "
              f"whole backup file {fratio * 100:5.1f}%")

    if failures:
        print(f"\n[FAIL] {failures} workflow(s) failed verification.")
        return 1
    print("\n[OK] All six workflows passed structural + Graydient lint verification.")
    return 0


if __name__ == "__main__":
    sys.exit(main())