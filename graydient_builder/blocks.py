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


# ── Media metadata probe ──────────────────────────────────────────────────────
# The custom node that reads the media Graydient attached to the job and reports
# what that file actually is. The URL is a parameter so a workflow can point at
# a fork if the host repo moves.
MEDIA_METADATA_REPO = "https://github.com/UnlimitedEditing/UnlimitedEditing-ComfyUI-MediaMetadata"

# The six init_<type>_* inputs of the probe node, in the node's widget order.
MEDIA_METADATA_SLOTS = [
    ("init_video_url", "video_url", 0),
    ("init_video_filename", "video_filename", 1),
    ("init_image_url", "image_url", 2),
    ("init_image_filename", "image_filename", 3),
    ("init_audio_url", "audio_url", 4),
    ("init_audio_filename", "audio_filename", 5),
]


def add_media_metadata_probe_block(
    wf: GraydientWorkflow,
    probe_id: int = 1,
    save_id: int = 2,
    card_width: int = 1600,
    card_height: int = 1000,
    caption_field: str = "prompt_positive",
    map_size_fields: bool = True,
    github_url: str = MEDIA_METADATA_REPO
) -> Dict[str, Any]:
    """
    Injects the media metadata block:
    'Media Metadata Probe' -> 'SaveImage'

    The probe resolves the init_video / init_image / init_audio triplet (both
    the _url and the _filename flavour, because which one a given submission
    path populates is architecturally unpredictable -- KI-007 section 7), reads
    the file's real metadata with ffprobe/PIL, and returns it as a rendered
    metadata card image.

    All six media fields are mapped so a job cannot silently lose its media
    (KI-007 sections 7 and 29). `prompt_positive` becomes the card's caption
    (KI-007 section 15: 'prompt' is NOT delivered to the node).
    """
    wf.add_github_requirement(github_url)
    wf.add_pip_requirement("pillow")

    for local_field, input_name, index in MEDIA_METADATA_SLOTS:
        wf.add_field_mapping(
            node_id=probe_id,
            node_input_name=input_name,
            local_field=local_field,
            node_name="Media Metadata Probe",
            node_input_index=index,
            default_value="",
            help_text=f"Attached media reference ({local_field}) - URL or platform-staged filename"
        )

    wf.add_field_mapping(
        node_id=probe_id,
        node_input_name="caption",
        local_field=caption_field,
        node_name="Media Metadata Probe",
        node_input_index=6,
        default_value="",
        help_text="Optional caption printed on the metadata card"
    )

    if map_size_fields:
        # width/height drive the card size. No min/max: the platform injects its
        # own default size when the user gives no /size, and a minimum above
        # that default is rejected with 'width is below minimum N' (KI-007 s44).
        wf.add_field_mapping(
            node_id=probe_id,
            node_input_name="card_width",
            local_field="width",
            node_name="Media Metadata Probe",
            node_input_index=7,
            default_value=str(card_width),
            help_text="Metadata card width in pixels (0 = auto)"
        )
        wf.add_field_mapping(
            node_id=probe_id,
            node_input_name="card_height",
            local_field="height",
            node_name="Media Metadata Probe",
            node_input_index=8,
            default_value=str(card_height),
            help_text="Metadata card height in pixels (0 = auto)"
        )

    probe_widgets = ["", "", "", "", "", "", "", card_width, card_height, True]

    return {
        "probe_node": {
            "id": probe_id,
            "type": "MediaMetadataProbe",
            "pos": [60, 120],
            "size": [440, 340],
            "order": 0,
            "mode": 0,
            "inputs": [],
            "outputs": [
                {"name": "report", "type": "STRING", "links": None, "slot_index": 0},
                {"name": "report_json", "type": "STRING", "links": None, "slot_index": 1},
                {"name": "card", "type": "IMAGE", "links": [1], "slot_index": 2},
            ],
            "title": "Media Metadata Probe",
            "widgets_values": probe_widgets,
        },
        "save_node": {
            "id": save_id,
            "type": "SaveImage",
            "pos": [580, 120],
            "size": [360, 120],
            "order": 1,
            "mode": 0,
            "inputs": [{"name": "images", "type": "IMAGE", "link": 1, "slot_index": 0}],
            "outputs": [],
            "title": "Save Metadata Card",
            "widgets_values": ["media_metadata/card"],
        },
        "links": [[1, probe_id, 2, save_id, 0, "IMAGE"]],
    }
