"""
Reusable Subgraph Blocks for Graydient ComfyUI Workflows.
Encapsulates battle-tested node chains so you never have to re-solve them from scratch.
"""

import json
import os
from typing import Dict, Any, List
from .core import GraydientWorkflow

CONCEPT_DB_PATH = os.path.join(os.path.dirname(__file__), "concept_db.json")

def load_concept_db() -> Dict[str, List[Dict[str, str]]]:
    """Loads verified concept staging definitions."""
    if os.path.isfile(CONCEPT_DB_PATH):
        with open(CONCEPT_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def stage_model(wf: GraydientWorkflow, model_key: str) -> GraydientWorkflow:
    """
    Injects pre-verified concept mapping entries from the catalog into the workflow.
    Example model keys: 'whisper-large-v3', 'audioldm-l-full', 'higgs-v3-tts', 'ltx-video-2.5', 'triposg-3d', 'sam2-large'
    """
    db = load_concept_db()
    if model_key not in db:
        raise KeyError(f"Model key '{model_key}' not found in concept DB. Available keys: {list(db.keys())}")

    for entry in db[model_key]:
        wf.add_concept_mapping(url=entry["url"], destination=entry["destination"])

    return wf

def add_audio_duration_sync_block(
    wf: GraydientWorkflow,
    load_audio_id: int = 2,
    duration_node_id: int = 4,
    math_node_id: int = 5,
    fps: int = 30,
    field_name: str = "init_audio_url"
) -> Dict[str, Any]:
    """
    Injects the verified audio duration synchronization block:
    'Load Audio Any' -> 'Audio Duration' -> 'ComfyMathExpression' round(a * fps)
    
    Ensures safe dual HTTP/local path handling and frame calculation for video models (LTX, Wan, Cosmos).
    """
    # Add GitHub repo requirement
    wf.add_github_requirement("https://github.com/UnlimitedEditing/comfy-audio-duration")
    
    # Map input field
    wf.add_field_mapping(
        node_id=load_audio_id,
        node_input_name="audio",
        local_field=field_name,
        node_name="Load Audio Any",
        node_input_index=0,
        help_text="Reference voiceover or audio clip (URL or filename)"
    )

    # Return standard node definitions that can be merged into graphs
    return {
        "load_audio_node": {
            "id": load_audio_id,
            "type": "Load Audio Any",
            "widgets_values": [""]
        },
        "audio_duration_node": {
            "id": duration_node_id,
            "type": "Audio Duration",
            "widgets_values": []
        },
        "math_node": {
            "id": math_node_id,
            "type": "ComfyMathExpression",
            "widgets_values": [f"round(a * {fps})"]
        }
    }
