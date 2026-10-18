import json

# Boilerplate Generator Script Template for Graydient ComfyUI Workflows
# Output: GraydientWorkflow-<slug>-v1.json

DESCRIPTION = """\
Summary of the workflow feature, target models, slots, and capabilities.\
"""

standard = {
  "last_node_id": 2,
  "last_link_id": 1,
  "nodes": [
    {
      "id": 1,
      "type": "YourModelLoaderNode",
      "pos": [10, 200],
      "size": [280, 80],
      "order": 0,
      "mode": 0,
      "inputs": [],
      "outputs": [
        {"name": "model", "type": "YOUR_MODEL", "links": [1], "slot_index": 0}
      ],
      "title": "Model Loader",
      "widgets_values": ["your-model-name"]
    },
    {
      "id": 2,
      "type": "YourSamplerNode",
      "pos": [320, 200],
      "size": [380, 260],
      "order": 1,
      "mode": 0,
      "inputs": [
        {"name": "model", "type": "YOUR_MODEL", "link": 1, "slot_index": 0}
      ],
      "outputs": [
        {"name": "output", "type": "IMAGE", "links": [], "slot_index": 0}
      ],
      "title": "Sampler",
      "widgets_values": [
        "A sample text prompt", # index 0
        0,                      # index 1 (seed)
      ]
    }
  ],
  "links": [
    [1, 1, 0, 2, 0, "YOUR_MODEL"]
  ],
  "groups": [],
  "config": {},
  "extra": {"ds": {"scale": 1.0, "offset": [0, 0]}, "frontendVersion": "1.43.18"},
  "version": 0.4
}

api = {
  "1": {
    "inputs": {
      "model_name": "your-model-name"
    },
    "class_type": "YourModelLoaderNode",
    "_meta": {"title": "Model Loader"}
  },
  "2": {
    "inputs": {
      "model": ["1", 0],
      "prompt": "A sample text prompt",
      "seed": 0
    },
    "class_type": "YourSamplerNode",
    "_meta": {"title": "Sampler"}
  }
}

concept_mapping = [
  {
    "allow_dynamic": False,
    "concept_name": None, "concept_type": None,
    "dynamic_family": None, "dynamic_subtype_1": None,
    "dynamic_subtype_2": None, "dynamic_type": None,
    "field_mapping": "", "is_zipped": False,
    "type": "url",
    "url": "https://huggingface.co/your-org/your-repo/resolve/main/model.safetensors",
    "destination": "your-model-name/model.safetensors",
    "weight": None, "weight_field_mapping": None
  }
]

cfg = {
  "graydient_workflow": {
    "avg_elapsed": 30,
    "concept_mapping": concept_mapping,
    "description": DESCRIPTION,
    "external_config": None, "external_provider": None, "extra_data": None,
    "field_mapping": [
      {
        "default_value": "A sample text prompt",
        "help_text": "Text prompt description.",
        "local_field": "prompt",
        "maximum_value": None, "minimum_value": None,
        "node_id": 2, "node_input_index": 0,
        "node_input_name": "prompt",
        "node_name": "Sampler"
      },
      {
        "default_value": 0,
        "help_text": "Random seed.",
        "local_field": "seed",
        "maximum_value": None, "minimum_value": 0,
        "node_id": 2, "node_input_index": 1,
        "node_input_name": "seed",
        "node_name": "Sampler"
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
      "github": ["https://github.com/UnlimitedEditing/Your-Custom-Node"],
      "pip": ["torch", "diffusers", "transformers"],
    },
    "split_prompt_pos_neg": False,
    "supports_dynamic_concepts": False,
    "supports_img2img": False, "supports_img2vid": False,
    "supports_low_memory": False,
    "supports_txt2img": True, "supports_txt2vid": False,
    "supports_txt2wav": False, "supports_vid2img": False,
    "supports_vid2vid": False, "supports_vid2wav": False,
    "supports_wav2txt": False,
    "version": 1,
    "workflow":   json.dumps(standard, indent=2),
    "workflow_2": json.dumps(api,      indent=2)
  }
}

with open(r"D:\tripostl\GraydientWorkflow-template-v1.json", "w") as f:
    json.dump(cfg, f, indent=2)

print("gen_template written OK")
