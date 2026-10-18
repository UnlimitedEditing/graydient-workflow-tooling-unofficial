import json

# Text-to-Sound Effect Workflow using AudioLDM (deconstructed Modular Loader/Sampler nodes)
#
# Field mappings:
#   prompt -> AudioLDMSampler prompt
#   negative_prompt -> AudioLDMSampler negative_prompt
#   length -> AudioLDMSampler audio_length (duration in seconds)
#   steps -> AudioLDMSampler num_steps
#   guidance -> AudioLDMSampler guidance_scale
#   seed -> AudioLDMSampler seed
#   slot1 -> AudioLDMSampler sample_rate (default 48000)

DESCRIPTION = """\
Modular Text-to-Sound Effect pipeline using AudioLDM.
Exposes control over prompt, negative_prompt, guidance_scale, seed, duration, steps, and sample_rate (supports up to 48kHz high-fidelity output).
Deconstructed loader/sampler nodes allow the model to be loaded once and pre-cached on the SaaS local store via Graydient's concept_mapping.\
"""

standard = {
  "last_node_id": 3,
  "last_link_id": 2,
  "nodes": [
    {
      "id": 1,
      "type": "AudioLDMModelLoader",
      "pos": [10, 200],
      "size": [280, 80],
      "order": 0,
      "mode": 0,
      "inputs": [],
      "outputs": [
        {"name": "audioldm_model", "type": "AUDIOLDM_MODEL", "links": [1], "slot_index": 0}
      ],
      "title": "AudioLDM Model Loader",
      "widgets_values": ["audioldm-l-full"]
    },
    {
      "id": 2,
      "type": "AudioLDMSampler",
      "pos": [320, 200],
      "size": [380, 260],
      "order": 1,
      "mode": 0,
      "inputs": [
        {"name": "audioldm_model", "type": "AUDIOLDM_MODEL", "link": 1, "slot_index": 0}
      ],
      "outputs": [
        {"name": "audio", "type": "AUDIO", "links": [2], "slot_index": 0}
      ],
      "title": "AudioLDM Sampler",
      "widgets_values": [
        "A hammer slowly hitting a wooden table",  # prompt
        "low quality, static, noise",               # negative_prompt
        10.0,                                       # audio_length
        25,                                         # num_steps
        3.5,                                        # guidance_scale
        48000,                                      # sample_rate
        0,                                          # seed
      ]
    },
    {
      "id": 3,
      "type": "SaveAudio",
      "pos": [730, 200],
      "size": [280, 80],
      "order": 2,
      "mode": 0,
      "inputs": [
        {"name": "audio", "type": "AUDIO", "link": 2, "slot_index": 0}
      ],
      "outputs": [],
      "title": "Save Audio",
      "widgets_values": ["audioldm/output"]
    }
  ],
  "links": [
    [1, 1, 0, 2, 0, "AUDIOLDM_MODEL"],
    [2, 2, 0, 3, 0, "AUDIO"]
  ],
  "groups": [],
  "config": {},
  "extra": {"ds": {"scale": 1.0, "offset": [0, 0]}, "frontendVersion": "1.43.18"},
  "version": 0.4
}

api = {
  "1": {
    "inputs": {
      "model_name": "audioldm-l-full"
    },
    "class_type": "AudioLDMModelLoader",
    "_meta": {"title": "AudioLDM Model Loader"}
  },
  "2": {
    "inputs": {
      "audioldm_model": ["1", 0],
      "prompt": "A hammer slowly hitting a wooden table",
      "negative_prompt": "low quality, static, noise",
      "audio_length": 10.0,
      "num_steps": 25,
      "guidance_scale": 3.5,
      "sample_rate": 48000,
      "seed": 0
    },
    "class_type": "AudioLDMSampler",
    "_meta": {"title": "AudioLDM Sampler"}
  },
  "3": {
    "inputs": {
      "audio": ["2", 0],
      "filename_prefix": "audioldm/output"
    },
    "class_type": "SaveAudio",
    "_meta": {"title": "Save Audio"}
  }
}

HF_BASE = "https://huggingface.co/cvssp/audioldm-l-full/resolve/main"
files = [
    "model_index.json",
    "scheduler/scheduler_config.json",
    "text_encoder/config.json",
    "text_encoder/pytorch_model.bin",
    "tokenizer/merges.txt",
    "tokenizer/special_tokens_map.json",
    "tokenizer/tokenizer.json",
    "tokenizer/tokenizer_config.json",
    "tokenizer/vocab.json",
    "unet/config.json",
    "unet/diffusion_pytorch_model.bin",
    "vae/config.json",
    "vae/diffusion_pytorch_model.bin",
    "vocoder/config.json",
    "vocoder/pytorch_model.bin"
]
concept_mapping = [
    {
        "allow_dynamic": False,
        "concept_name": None, "concept_type": None,
        "dynamic_family": None, "dynamic_subtype_1": None,
        "dynamic_subtype_2": None, "dynamic_type": None,
        "field_mapping": "", "is_zipped": False,
        "type": "url",
        "url": f"{HF_BASE}/{f}",
        "destination": f"audioldm-l-full/{f}",
        "weight": None, "weight_field_mapping": None
    }
    for f in files
]

cfg = {
  "graydient_workflow": {
    "avg_elapsed": 45,
    "concept_mapping": concept_mapping,
    "description": DESCRIPTION,
    "external_config": None, "external_provider": None, "extra_data": None,
    "field_mapping": [
      {
        "default_value": "A hammer slowly hitting a wooden table",
        "help_text": "Text prompt describing the desired sound effect.",
        "local_field": "prompt",
        "maximum_value": None, "minimum_value": None,
        "node_id": 2, "node_input_index": 0,
        "node_input_name": "prompt",
        "node_name": "AudioLDM Sampler"
      },
      {
        "default_value": "low quality, static, noise",
        "help_text": "Negative prompt containing qualities to avoid.",
        "local_field": "negative_prompt",
        "maximum_value": None, "minimum_value": None,
        "node_id": 2, "node_input_index": 1,
        "node_input_name": "negative_prompt",
        "node_name": "AudioLDM Sampler"
      },
      {
        "default_value": 10.0,
        "help_text": "Duration of the generated audio in seconds (1.0 to 30.0).",
        "local_field": "length",
        "maximum_value": 30.0, "minimum_value": 1.0,
        "node_id": 2, "node_input_index": 2,
        "node_input_name": "audio_length",
        "node_name": "AudioLDM Sampler"
      },
      {
        "default_value": 25,
        "help_text": "Number of inference steps (higher is better but slower).",
        "local_field": "steps",
        "maximum_value": 100, "minimum_value": 1,
        "node_id": 2, "node_input_index": 3,
        "node_input_name": "num_steps",
        "node_name": "AudioLDM Sampler"
      },
      {
        "default_value": 3.5,
        "help_text": "Guidance scale (CFG) controls adherence to the text prompt.",
        "local_field": "guidance",
        "maximum_value": 20.0, "minimum_value": 1.0,
        "node_id": 2, "node_input_index": 4,
        "node_input_name": "guidance_scale",
        "node_name": "AudioLDM Sampler"
      },
      {
        "default_value": 48000,
        "help_text": "Sample rate of output audio file (e.g. 16000, 32000, 48000).",
        "local_field": "slot1",
        "maximum_value": 48000, "minimum_value": 8000,
        "node_id": 2, "node_input_index": 5,
        "node_input_name": "sample_rate",
        "node_name": "AudioLDM Sampler"
      },
      {
        "default_value": 0,
        "help_text": "Random seed for generation.",
        "local_field": "seed",
        "maximum_value": None, "minimum_value": 0,
        "node_id": 2, "node_input_index": 6,
        "node_input_name": "seed",
        "node_name": "AudioLDM Sampler"
      }
    ],
    "image_url": None,
    "install_detected_nodes": False,
    "is_deleted": False,
    "is_public": True,
    "max_collect_attempts": None,
    "peak_vram_usage": 8000,
    "platform": "comfyui",
    "post_install_script": None,
    "pre_install_script": None,
    "requirements": {
      "github": ["https://github.com/UnlimitedEditing/ComfyUI-AudioLDM"],
      "pip": ["diffusers", "transformers", "accelerate", "safetensors", "loguru", "scipy", "modelscope"],
    },
    "split_prompt_pos_neg": False,
    "supports_dynamic_concepts": False,
    "supports_img2img": False, "supports_img2vid": False,
    "supports_low_memory": False,
    "supports_txt2img": False, "supports_txt2vid": False,
    "supports_txt2wav": True, "supports_vid2img": False,
    "supports_vid2vid": False, "supports_vid2wav": False,
    "supports_wav2txt": False,
    "version": 1,
    "workflow":   json.dumps(standard, indent=2),
    "workflow_2": json.dumps(api,      indent=2)
  }
}

with open(r"D:\tripostl\GraydientWorkflow-audioldm-t2s-v1.json", "w") as f:
    json.dump(cfg, f, indent=2)
print("gen_audioldm_t2s written OK")
