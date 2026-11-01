#!/usr/bin/env python3
"""
Workflow Generator: Media Metadata Report.

A diagnostic/utility workflow with no model in it. It takes the media
Graydient attached to the job (init_video / init_image / init_audio) and
returns a single IMAGE: a rendered metadata card describing that file.

For a video the card carries the full file-level metadata: container format,
duration, bit rate, codec + profile, resolution, display aspect ratio, frame
rate (average and real), TOTAL FRAME COUNT, pixel format, bit depth, colour
space/primaries/transfer, field order, rotation, time base, per-stream tags
(creation_time, encoder, language), the audio stream's codec / sample rate /
channels / bit rate, the file size and its modification time.

For an image: format, resolution, colour mode, frame count, DPI and the EXIF
block (DateTimeOriginal, make, model, GPS...). For audio: codec, sample rate,
channels, layout, duration, bit rate.

WHY A CUSTOM NODE: no node in ComfyUI core (or in any pack this project uses)
surfaces file-level metadata as text. VHS's `video_info` is an unprintable
dict socket, and TripoSG's LoadVideoFromURLMatched returns the RESOLVED target
width/height/length/fps, not the source file's own metadata. Getting
`creation_time`, `bit_rate`, `nb_frames` and the container's format name means
running ffprobe and formatting the result -- which is what the probe node does.

ONE OUTPUT ONLY: the card is the only file written. A second output file would
re-open the output-picker race documented in KI-007 section 10 (VHS writes three
candidate files and the platform non-deterministically returns the wrong one).
The same data is also available machine-readably on the node's `report_json`
output socket for any workflow that wants to chain it.

Usage:
    python templates/gen_media_metadata_report.py
"""

import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BASE_DIR)
for _p in (REPO_ROOT, BASE_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from graydient_builder import GraydientWorkflow, add_media_metadata_probe_block

wf = GraydientWorkflow(
    name="media-metadata-report",
    description=(
        "Media Metadata Report - describes the file Graydient attached to the job.\n"
        "\n"
        "Attach (or reply with) a video, an image or an audio file and this workflow\n"
        "returns ONE image: a metadata card for that file.\n"
        "\n"
        "VIDEO cards carry: container format, duration, bit rate, stream count,\n"
        "creation time, codec + profile + level, resolution (and coded resolution),\n"
        "display/sample aspect ratio, average and real frame rate, TOTAL FRAMES,\n"
        "pixel format, bit depth, colour space/primaries/transfer, chroma location,\n"
        "field order, rotation, time base, per-stream tags, the audio stream's\n"
        "codec/sample rate/channels/bit rate, file size and modification time.\n"
        "\n"
        "IMAGE cards carry: format, resolution, colour mode, frame count, animation,\n"
        "DPI and the EXIF block (DateTimeOriginal, make, model, software, GPS...).\n"
        "AUDIO cards carry: codec, sample rate, channels, channel layout, duration,\n"
        "bit rate and sample format.\n"
        "\n"
        "SETTINGS:\n"
        "  - prompt_positive: optional caption printed on the card's header line\n"
        "  - width / height: card size in pixels (the card grows taller if the\n"
        "    report needs it; text is never shrunk below legibility)\n"
        "\n"
        "No model, no GPU, no quota burn: it only reads the attached file."
    ),
)

wf.author = "UnlimitedEditing / Graydient Pipeline"
wf.avg_elapsed = 25

# ── the block: MediaMetadataProbe -> SaveImage ─────────────────────────────────
block = add_media_metadata_probe_block(
    wf,
    probe_id=1,
    save_id=2,
    card_width=1600,
    card_height=1000,
)

standard_workflow = {
    "last_node_id": 2,
    "last_link_id": 1,
    "nodes": [
        block["probe_node"],
        block["save_node"],
    ],
    "links": block["links"],
    "groups": [],
    "config": {},
    "extra": {
        "ds": {"scale": 0.75, "offset": [0, 0]},
        "frontendVersion": "1.43.18",
    },
    "version": 0.4,
}

api_workflow = {
    "1": {
        "inputs": {
            "video_url": "",
            "video_filename": "",
            "image_url": "",
            "image_filename": "",
            "audio_url": "",
            "audio_filename": "",
            "caption": "",
            "card_width": 1600,
            "card_height": 1000,
            "include_thumbnail": True,
        },
        "class_type": "MediaMetadataProbe",
        "_meta": {"title": "Media Metadata Probe"},
    },
    "2": {
        "inputs": {
            "images": ["1", 2],
            "filename_prefix": "media_metadata/card",
        },
        "class_type": "SaveImage",
        "_meta": {"title": "Save Metadata Card"},
    },
}

wf.set_workflows(standard_workflow, api_workflow)

# ── archive flags ─────────────────────────────────────────────────────────────
wf.set_flag("version", 1)
wf.set_flag("platform", "comfyui")
wf.set_flag("peak_vram_usage", 512)
wf.set_flag("supports_txt2img", False)
wf.set_flag("supports_img2img", True)      # media in -> image out
wf.set_flag("supports_txt2vid", False)
wf.set_flag("supports_img2vid", False)
wf.set_flag("supports_vid2vid", False)
wf.set_flag("supports_txt2wav", False)
wf.set_flag("supports_vid2wav", False)
wf.set_flag("supports_wav2txt", False)
wf.set_flag("supports_low_memory", True)
wf.set_flag("supports_dynamic_concepts", False)
wf.set_flag("install_detected_nodes", True)
wf.set_flag("split_prompt_pos_neg", False)
wf.set_flag("is_public", True)

if __name__ == "__main__":
    out = os.path.join(REPO_ROOT, "GraydientWorkflow-media-metadata-report-v1.json")
    wf.save(out)
    print(json.dumps({"written": out}, indent=2))
