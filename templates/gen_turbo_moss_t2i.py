import json
import os

# MOSS-Image Turbo Text-to-Image Workflow Generator (v1 - DMD 8-Step Turbo Pipeline)
# Model: OpenMOSS MOSS-Image 5B DiT (Apache-2.0)
# Turbo LoRA: lodestones/MOSS-Image-SFT-8-steps-dmd (1.19 GB, 8-step data-space DMD)
# Latent: FLUX.2 latent space (128 channels, 16x downsampling) via flux2-vae
# Text Encoder: Qwen3.5-9B (4K tokens, CoT reasoning prompt wrap, English/Chinese layout & text rendering)
# Nodes: ComfyUI Core native support (PR #17095) + stock LoraLoaderModelOnly
# Precision: int8 convrot base weights + fp32 DMD LoRA (~16.7 GB total staged via concept_mapping)
#
# Key Architectural Constraints (from KI-007 section 31):
# 1. NO ModelSamplingSD3: MOSSImage in ComfyUI core natively defines shift: 5.0.
# 2. REQUIRED Scheduler: 'simple' (flow-matching linear schedule from 1.0 to 0.0).
# 3. REQUIRED Sampler: 'er_sde' (or 'euler'), cfg 2.5, steps 8.
# 4. SLG: SkipLayerGuidanceDiTSimple single_layers='22', double_layers='', start_percent=0.0, end_percent=0.5.
# 5. Denoise: 1.0 (pure txt2img/layout; no img2img weights exist in MOSS-Image).

DESCRIPTION = """\
Turbo-MOSS: High-speed 8-step variant of MOSS-Image 5B DiT with 8-step DMD Turbo LoRA. Generates high-fidelity images with layout control and typography in English and Chinese in ~15 seconds.

Telegram Commands:
/run:turbo-moss [prompt] - Generate an image from description or spatial layout
/steps:8 - Sampling steps (default: 8, recommended: 6-12)
/guidance:2.5 - Prompt guidance / CFG (default: 2.5, recommended: 1.5-3.5)
/seed:42 - Reproducible random seed
/size:1024x1024 - Output canvas size (multiples of 16, e.g. 1024x1024, 1280x768, 768x1280)
/slot1:22 - SLG uncond skip layer (22 = default reference; blank = off)
/slot2:1.0 - Turbo LoRA strength (default: 1.0; 0.7 for milder effect; 0.0 to disable)
/sampler:er_sde - Sampling algorithm (er_sde or euler)

Tips:
- Rapid 8-step generation cuts latency by ~70% compared to baseline MOSS.
- Text Rendering: Put text in quotes within the prompt or use newlines (\\n) for line breaks.
- Negative Prompt: Default is empty string for clean unconditional guidance.
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
            "lora_name": "moss_image_sft_8_steps_dmd.safetensors",
            "strength_model": 1.0
        },
        "class_type": "LoraLoaderModelOnly",
        "_meta": {"title": "MOSS-Image 8-Step Turbo LoRA"}
    },
    "3": {
        "inputs": {
            "model": ["2", 0],
            "double_layers": "",
            "single_layers": "22",
            "start_percent": 0.0,
            "end_percent": 0.5
        },
        "class_type": "SkipLayerGuidanceDiTSimple",
        "_meta": {"title": "SLG Uncond Skip (Layer 22)"}
    },
    "4": {
        "inputs": {
            "clip_name": "qwen3.5_9b_int8_convrot.safetensors",
            "type": "moss_image",
            "device": "default"
        },
        "class_type": "CLIPLoader",
        "_meta": {"title": "Load Qwen3.5-9B (moss_image)"}
    },
    "5": {
        "inputs": {
            "vae_name": "flux2-vae.safetensors"
        },
        "class_type": "VAELoader",
        "_meta": {"title": "Load FLUX.2 VAE"}
    },
    "6": {
        "inputs": {
            "clip": ["4", 0],
            "text": "A beautiful scenic landscape of an ancient mossy stone shrine in an autumn forest, golden hour lighting, rays of sun piercing through morning mist, 8k resolution, photorealistic"
        },
        "class_type": "CLIPTextEncode",
        "_meta": {"title": "Positive Prompt"}
    },
    "7": {
        "inputs": {
            "clip": ["4", 0],
            "text": ""
        },
        "class_type": "CLIPTextEncode",
        "_meta": {"title": "Negative Prompt"}
    },
    "8": {
        "inputs": {
            "width": 1024,
            "height": 1024,
            "batch_size": 1
        },
        "class_type": "EmptyFlux2LatentImage",
        "_meta": {"title": "Empty FLUX.2 Latent"}
    },
    "9": {
        "inputs": {
            "model": ["3", 0],
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["8", 0],
            "seed": 42,
            "steps": 8,
            "cfg": 2.5,
            "sampler_name": "er_sde",
            "scheduler": "simple",
            "denoise": 1.0
        },
        "class_type": "KSampler",
        "_meta": {"title": "KSampler (8 steps Turbo)"}
    },
    "10": {
        "inputs": {
            "samples": ["9", 0],
            "vae": ["5", 0]
        },
        "class_type": "VAEDecode",
        "_meta": {"title": "Decode Image"}
    },
    "11": {
        "inputs": {
            "images": ["10", 0],
            "filename_prefix": "turbo_moss"
        },
        "class_type": "SaveImage",
        "_meta": {"title": "Save Image"}
    }
}

# Widget definitions for standard UI format
WIDGETS = {
    "UNETLoader": ["unet_name", "weight_dtype"],
    "LoraLoaderModelOnly": ["lora_name", "strength_model"],
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
    "LoraLoaderModelOnly": ["MODEL"],
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
    fm("prompt_positive", 6, "text", 0, "", "Detailed text description or spatial layout prompt (up to 4096 tokens).", "Positive Prompt"),
    fm("prompt_negative", 7, "text", 0, "", "Negative prompt (leave blank for default unconditioned guidance).", "Negative Prompt"),
    fm("seed", 9, "seed", 0, 42, "Random generation seed for reproducibility.", "KSampler (8 steps Turbo)"),
    fm("steps", 9, "steps", 2, 8, "Inference steps (8 = reference turbo; 4-12 range).", "KSampler (8 steps Turbo)", 4, 25),
    fm("guidance", 9, "cfg", 3, 2.5, "Prompt guidance (CFG scale). 2.5 = reference; 1.0-4.0 recommended for DMD.", "KSampler (8 steps Turbo)", 1.0, 6.0),
    fm("sampler", 9, "sampler_name", 4, "er_sde", "Sampling algorithm (er_sde or euler).", "KSampler (8 steps Turbo)"),
    fm("scheduler", 9, "scheduler", 5, "simple", "Schedule type (simple is required for flow matching).", "KSampler (8 steps Turbo)"),
    fm("width", 8, "width", 0, 1024, "Image width (multiple of 16).", "Empty FLUX.2 Latent", 512, 1536),
    fm("height", 8, "height", 1, 1024, "Image height (multiple of 16).", "Empty FLUX.2 Latent", 512, 1536),
    fm("slot1", 3, "single_layers", 1, "22", "SLG uncond skip layer (22 = reference; blank = off).", "SLG Uncond Skip (Layer 22)"),
    fm("slot2", 2, "strength_model", 1, 1.0, "Turbo LoRA strength (1.0 = reference; 0.7 = mild; 0.0 = disable).", "MOSS-Image 8-Step Turbo LoRA", 0.0, 2.0),
]

def cm(url, dest):
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
        "url": url,
        "destination": dest,
        "weight": None,
        "weight_field_mapping": None
    }

HF_BASE = "https://huggingface.co/Comfy-Org/MOSS-Image/resolve/main/"

concept_mapping = [
    cm(HF_BASE + "diffusion_models/moss_image_sft_int8_convrot.safetensors", "diffusion_models/moss_image_sft_int8_convrot.safetensors"),
    cm(HF_BASE + "text_encoders/qwen3.5_9b_int8_convrot.safetensors", "text_encoders/qwen3.5_9b_int8_convrot.safetensors"),
    cm(HF_BASE + "vae/flux2-vae.safetensors", "vae/flux2-vae.safetensors"),
    cm("https://huggingface.co/lodestones/MOSS-Image-SFT-8-steps-dmd/resolve/main/lora.safetensors", "loras/moss_image_sft_8_steps_dmd.safetensors"),
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
        "version": 1,
        "workflow": json.dumps(standard, indent=2),
        "workflow_2": json.dumps(api, indent=2)
    }
}

out_path = r"D:\tripostl\GraydientWorkflow-turbo-moss-v1.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=2)

print(f"Generated {out_path} ({len(api)} API nodes, {len(links)} links)")

try:
    from graydient_builder.linter import lint_workflow, format_lint_report
    report = format_lint_report(lint_workflow(cfg)[1])
    print(report)
except Exception as e:
    print("Lint skipped/error:", e)
