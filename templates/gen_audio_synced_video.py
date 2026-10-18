"""
Canonical Audio-Synced Video Generator Template.
Uses `add_audio_duration_sync_block` to automatically derive the required video frame count
from a user-uploaded audio track (`init_audio_url` / `init_audio`).
"""

import json
from graydient_builder import GraydientWorkflow, stage_model, add_audio_duration_sync_block

wf = GraydientWorkflow(
    name="audio-synced-video",
    description="Video generation dynamically synchronized to an uploaded audio track duration"
)

# 1. Pre-stage Model Weights (e.g. LTX-2.5 or Wan)
stage_model(wf, "ltx-2.5-i2v")

# 2. Add Audio Duration Sync Block
# Derives: Audio -> Audio Duration -> Math Expression: round(duration * fps) -> frame count
audio_block = add_audio_duration_sync_block(
    wf,
    load_audio_id=2,
    duration_node_id=4,
    math_node_id=5,
    fps=30,
    field_name="init_audio_url"
)

# 3. Add Common Inputs
wf.add_field_mapping(node_id=1, node_input_name="prompt", local_field="prompt_positive", help_text="Positive prompt")
wf.add_field_mapping(node_id=1, node_input_name="seed", local_field="seed", help_text="Random seed")

# 4. Standard & API Workflow Graphs
standard_workflow = {
    "nodes": [
        {"id": 1, "type": "KSampler", "widgets_values": ["video prompt", 42, 25, 3.0, "euler", "simple", 1.0]},
        audio_block["load_audio_node"],
        audio_block["audio_duration_node"],
        audio_block["math_node"]
    ],
    "links": []
}

api_workflow = {
    "1": {"class_type": "KSampler", "inputs": {"prompt": "video prompt", "seed": 42}},
    "2": {"class_type": "Load Audio Any", "inputs": {"audio": ""}},
    "4": {"class_type": "Audio Duration", "inputs": {"audio": ["2", 0]}},
    "5": {"class_type": "ComfyMathExpression", "inputs": {"expression": "round(a * 30)", "a": ["4", 1]}}
}

# 5. Output Picker Safety (KI-007 §28)
wf.set_extra({
    "VHS_MetadataImage": False,
    "VHS_KeepIntermediate": False
})

wf.set_workflows(standard_workflow, api_workflow)

if __name__ == "__main__":
    wf.save()
