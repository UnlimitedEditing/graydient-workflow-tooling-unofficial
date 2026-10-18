import json
import os

# MOSS-Image Text-to-Image Workflow Generator (v2 - Canonical Flow-Matching Pipeline)
# Model: OpenMOSS MOSS-Image 5B DiT (Apache-2.0)
# Latent: FLUX.2 latent space (128 channels, 16x downsampling) via flux2-vae
# Text Encoder: Qwen3.5-9B (4K tokens, CoT reasoning prompt wrap, English/Chinese layout & text rendering)
# Nodes: ComfyUI Core native support (PR #17095)
# Precision: int8 convrot weights (5.41 GB DiT + 9.75 GB text encoder + 0.34 GB VAE = ~15.5 GB total staged)
#
# Key Architectural Fixes from v1:
# 1. REMOVED ModelSamplingSD3: MOSSImage in ComfyUI core already defines native shift: 5.0.
#    Wrapping it with SD3 ModelSampling double-shifts and corrupts the timesteps.
# 2. FIXED Scheduler: Changed from 'sgm_uniform' to 'simple' (flow-matching linear schedule from 1.0 to 0.0).
#    Flow models require 'simple'; 'sgm_uniform' caused the un-denoised static noise.
# 3. FIXED Sampler: Default 'er_sde' (or 'euler'), cfg 2.5, steps 25-50 per PR #17095 reference.
# 4. FIXED SLG: SkipLayerGuidanceDiTSimple single_layers='22', double_layers='', start_percent=0.0, end_percent=0.5.
# 5. Negative prompt default is empty string "" for true unconditional guidance.

DESCRIPTION = """\
MOSS-Image: A 5B-parameter open diffusion model with layout control and text rendering in English and Chinese. Powered by Qwen3.5-9B and the FLUX.2 latent space.

Telegram Commands:
/run:moss-image [prompt] - Generate an image from description or spatial layout
/steps:25 - Sampling steps (default: 25, recommended: 25-50)
/guidance:2.5 - Prompt guidance / CFG (default: 2.5, range: 1.5-5.0)
/seed:42 - Reproducible random seed
/size:1024x1024 - Output canvas size (multiples of 16, e.g. 1024x1024, 1280x768, 768x1280)
/slot1:22 - SLG uncond skip layer (22 = default reference; 24 or 26 also valid; blank = off)
/sampler:er_sde - Sampling algorithm (er_sde or euler)

Tips:
- Text Rendering: Put text in quotes within the prompt or use newlines (\\n) for line breaks.
- Negative Prompt: Default is clean/empty for optimal unconditional guidance.
- Layout Control: Supports 4K token prompts and structured JSON bounding boxes.
"""

api = {
    "1": {
        "inputs": {
            "unet_name": "moss_image_sft_int8_convrot.safetensors",
            "weight_dtype": "default"
        },
        "class_type": "UNETLoader",
        "_meta": {"title": "Load MOSS-Image SFT DiT (int8)"}
    },
    "2": {
        "inputs": {
            "model": ["1", 0],
            "double_layers": "",
            "single_layers": "22",
            "start_percent": 0.0,
            "end_percent": 0.5
        },
        "class_type": "SkipLayerGuidanceDiTSimple",
        "_meta": {"title": "SLG Uncond Skip (Layer 22)"}
    },
    "3": {
        "inputs": {
            "clip_name": "qwen3.5_9b_int8_convrot.safetensors",
            "type": "moss_image",
            "device": "default"
        },
        "class_type": "CLIPLoader",
        "_meta": {"title": "Load Qwen3.5-9B (moss_image)"}
    },
    "4": {
        "inputs": {
            "vae_name": "flux2-vae.safetensors"
        },
        "class_type": "VAELoader",
        "_meta": {"title": "Load FLUX.2 VAE"}
    },
    "5": {
        "inputs": {
            "clip": ["3", 0],
            "text": "A beautiful scenic landscape of an ancient mossy stone shrine in an autumn forest, golden hour lighting, rays of sun piercing through morning mist, 8k resolution, photorealistic"
        },
        "class_type": "CLIPTextEncode",
        "_meta": {"title": "Positive Prompt"}
    },
    "6": {
        "inputs": {
            "clip": ["3", 0],
            "text": ""
        },
        "class_type": "CLIPTextEncode",
        "_meta": {"title": "Negative Prompt"}
    },
    "7": {
        "inputs": {
            "width": 1024,
            "height": 1024,
            "batch_size": 1
        },
        "class_type": "EmptyFlux2LatentImage",
        "_meta": {"title": "Empty FLUX.2 Latent"}
    },
    "8": {
        "inputs": {
            "model": ["2", 0],
            "positive": ["5", 0],
            "negative": ["6", 0],
            "latent_image": ["7", 0],
            "seed": 42,
            "steps": 25,
            "cfg": 2.5,
            "sampler_name": "er_sde",
            "scheduler": "simple",
            "denoise": 1.0
        },
        "class_type": "KSampler",
        "_meta": {"title": "KSampler"}
    },
    "9": {
        "inputs": {
            "samples": ["8", 0],
            "vae": ["4", 0]
        },
        "class_type": "VAEDecode",
        "_meta": {"title": "Decode Image"}
    },
    "10": {
        "inputs": {
            "images": ["9", 0],
            "filename_prefix": "moss_image"
        },
        "class_type": "SaveImage",
        "_meta": {"title": "Save Image"}
    }
}

# Widget definitions for standard UI format
WIDGETS = {
    "UNETLoader": ["unet_name", "weight_dtype"],
    "SkipLayerGuidanceDiTSimple": ["double_layers", "single_layers", "start_percent", "end_percent"],
    "CLIPLoader": ["clip_name", "type", "device"],
    "VAELoader": ["vae_name"],
    "CLIPTextEncode": ["text"],
    "EmptyFlux2LatentImage": ["width", "height", "batch_size"],
    "KSampler": ["seed", "control_after_generate", "steps", "cfg", "sampler_name", "scheduler", "denoise"],
    "VAEDecode": [],
    "SaveImage": ["filename_prefix"]
}

OUT = {
    "UNETLoader": ["MODEL"],
    "SkipLayerGuidanceDiTSimple": ["MODEL"],
    "CLIPLoader": ["CLIP"],
    "VAELoader": ["VAE"],
    "CLIPTextEncode": ["CONDITIONING"],
    "EmptyFlux2LatentImage": ["LATENT"],
    "KSampler": ["LATENT"],
    "VAEDecode": ["IMAGE"],
    "SaveImage": []
}

nodes = {}
for k, v in api.items():
    ctype = v["class_type"]
    w_vals = []
    for w in WIDGETS.get(ctype, []):
        if w == "control_after_generate":
            w_vals.append("fixed")
        else:
            w_vals.append(v["inputs"].get(w, ""))
    nodes[k] = {
        "id": int(k),
        "type": ctype,
        "title": v["_meta"]["title"],
        "pos": [0, 0],
        "size": [300, 120],
        "order": int(k),
        "mode": 0,
        "inputs": [],
        "outputs": [],
        "widgets_values": w_vals
    }

links = []
lid = 0
for k, v in api.items():
    for in_name, in_val in v["inputs"].items():
        if isinstance(in_val, list):
            src_id, src_slot = in_val
            src_ctype = api[src_id]["class_type"]
            out_types = OUT[src_ctype]
            conn_type = out_types[src_slot] if src_slot < len(out_types) else "*"
            lid += 1
            in_slot = len(nodes[k]["inputs"])
            links.append([lid, int(src_id), src_slot, int(k), in_slot, conn_type])
            nodes[k]["inputs"].append({"name": in_name, "type": conn_type, "link": lid})
            
            src_outs = nodes[src_id]["outputs"]
            while len(src_outs) <= src_slot:
                ot = out_types[len(src_outs)] if len(src_outs) < len(out_types) else "*"
                src_outs.append({"name": ot, "type": ot, "links": []})
            src_outs[src_slot]["links"].append(lid)

standard = {
    "last_node_id": len(api),
    "last_link_id": lid,
    "nodes": list(nodes.values()),
    "links": links,
    "groups": [],
    "config": {},
    "extra": {},
    "version": 0.4
}

def fm(local, node_id, name, idx, default, help_, node_name, lo=None, hi=None):
    st = lambda x: None if x is None else str(x)
    return {
        "default_value": st(default),
        "help_text": help_,
        "local_field": local,
        "maximum_value": st(hi),
        "minimum_value": st(lo),
        "node_id": node_id,
        "node_input_index": idx,
        "node_input_name": name,
        "node_name": node_name
    }

field_mapping = [
    fm("prompt_positive", 5, "text", 0, "", "Detailed text description or spatial layout prompt (up to 4096 tokens).", "Positive Prompt"),
    fm("prompt_negative", 6, "text", 0, "", "Negative prompt (leave blank for default unconditioned guidance).", "Negative Prompt"),
    fm("seed", 8, "seed", 0, 42, "Random generation seed for reproducibility.", "KSampler"),
    fm("steps", 8, "steps", 2, 25, "Inference steps (25 = reference fast; 50 = maximum quality).", "KSampler", 10, 100),
    fm("guidance", 8, "cfg", 3, 2.5, "Prompt guidance (CFG scale). 2.5 = reference.", "KSampler", 1.0, 8.0),
    fm("sampler", 8, "sampler_name", 4, "er_sde", "Sampling algorithm (er_sde or euler).", "KSampler"),
    fm("scheduler", 8, "scheduler", 5, "simple", "Schedule type (simple is required for flow matching).", "KSampler"),
    fm("width", 7, "width", 0, 1024, "Image width (multiple of 16).", "Empty FLUX.2 Latent", 512, 1536),
    fm("height", 7, "height", 1, 1024, "Image height (multiple of 16).", "Empty FLUX.2 Latent", 512, 1536),
    fm("slot1", 2, "single_layers", 1, "22", "SLG uncond skip layer (22 = reference; 24 or 26 also valid; blank = off).", "SLG Uncond Skip (Layer 22)"),
]

HF_BASE = "https://huggingface.co/Comfy-Org/MOSS-Image/resolve/main/"

def cm(rel_url, dest):
    return {
        "allow_dynamic": False,
        "concept_name": None,
        "concept_type": None,
        "dynamic_family": None,
        "dynamic_subtype_1": None,
        "dynamic_subtype_2": None,
        "dynamic_type": None,
        "field_mapping": "",
        "is_zipped": False,
        "type": "url",
        "url": HF_BASE + rel_url,
        "destination": dest,
        "weight": None,
        "weight_field_mapping": None
    }

concept_mapping = [
    cm("diffusion_models/moss_image_sft_int8_convrot.safetensors", "diffusion_models/moss_image_sft_int8_convrot.safetensors"),
    cm("text_encoders/qwen3.5_9b_int8_convrot.safetensors", "text_encoders/qwen3.5_9b_int8_convrot.safetensors"),
    cm("vae/flux2-vae.safetensors", "vae/flux2-vae.safetensors"),
]

cfg = {
    "graydient_workflow": {
        "avg_elapsed": None,
        "concept_mapping": concept_mapping,
        "description": DESCRIPTION,
        "external_config": None,
        "external_provider": None,
        "extra_data": None,
        "field_mapping": field_mapping,
        "image_url": None,
        "install_detected_nodes": False,
        "is_deleted": False,
        "is_public": False,
        "max_collect_attempts": None,
        "peak_vram_usage": 18000,
        "platform": "comfyui",
        "post_install_script": None,
        "pre_install_script": None,
        "requirements": {
            "github": [],
            "pip": []
        },
        "split_prompt_pos_neg": True,
        "supports_dynamic_concepts": False,
        "supports_img2img": False,
        "supports_img2vid": False,
        "supports_low_memory": False,
        "supports_txt2img": True,
        "supports_txt2vid": False,
        "supports_txt2wav": False,
        "supports_vid2img": False,
        "supports_vid2vid": False,
        "supports_vid2wav": False,
        "supports_wav2txt": False,
        "version": 2,
        "workflow": json.dumps(standard, indent=2),
        "workflow_2": json.dumps(api, indent=2)
    }
}

out_path = r"D:\tripostl\GraydientWorkflow-moss-image-v2.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=2)

print(f"Generated {out_path} ({len(api)} API nodes, {len(links)} links)")

try:
    from graydient_builder.linter import lint_workflow, format_lint_report
    report = format_lint_report(lint_workflow(cfg)[1])
    print(report)
except Exception as e:
    print("Lint skipped/error:", e)
