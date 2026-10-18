import json

# Higgs Audio v3 TTS -- PRESET-VOICE-ONLY variant, split off gen_higgs_v2.py.
#
# Split rationale (2026-08-02): gen_higgs_v2.py did double duty as both a
# plain TTS workflow (pick one of 6 preset voices) and a cloning workflow
# (supply your own reference clip via init_audio*), with cloning silently
# falling back to the preset whenever no clip resolved. That's convenient
# but makes failures invisible -- a user asking for their own voice with a
# broken URL just quietly gets Jake instead, no error. Splitting into two
# single-purpose workflows lets each one be honest about what it does:
# this one ONLY ever uses a named preset voice, cloning inputs aren't
# exposed at all, so there's no ambiguity about which voice you'll get.
# See gen_higgs_clone.py for the cloning-only counterpart, which hardlocks
# require_clone_source=True instead (fails loudly if no clip resolves,
# never falls back to a preset).
#
# HiggsV3VoicePreset's custom_audio_url* inputs still exist on the node
# (can't remove them without editing the node class itself, which is shared
# with the clone workflow) but are deliberately left OUT of field_mapping
# here, so no Graydient field can ever populate them on this workflow --
# they'll always be empty, so the node always falls through to the preset
# path. This is the standardization the split is for: not "two copies of
# the same flexible node," but "the same node, two different exposed
# surfaces."
#
# All other design notes (prompt_positive local_field, tags:: marker as the
# only reliable tag mechanism, device="auto" not "cuda", model repo id
# pinned to the local folder name) carry over unchanged from gen_higgs_v2.py
# -- see that file's history for why each of those is the way it is.
#
# Graph: HiggsV3LoadModel -> HiggsV3VoiceClone
#        HiggsV3VoicePreset (preset only) -> HiggsV3WhisperTranscribe -> HiggsV3VoiceClone.reference_text
#                                          -> HiggsV3VoiceClone.reference_audio
#        HiggsV3TagBuilder -> HiggsV3VoiceClone.text
#        HiggsV3VoiceClone -> SaveAudio

standard = {
    "last_node_id": 6, "last_link_id": 6,
    "nodes": [
        {
            "id": 1, "type": "HiggsV3LoadModel",
            "pos": [0, 200], "size": [340, 140],
            "order": 0, "mode": 0,
            "inputs": [],
            "outputs": [{"name": "higgs_model", "type": "HIGGSV3TTS_MODEL", "links": [1], "slot_index": 0}],
            "title": "Higgs v3 Load Model",
            "widgets_values": [
                "higgs-audio-v3-tts-4b",
                "bf16", "auto", "sdpa", True,
            ],
        },
        {
            "id": 2, "type": "HiggsV3VoicePreset",
            "pos": [0, 400], "size": [280, 100],
            "order": 1, "mode": 0,
            "inputs": [],
            "outputs": [{"name": "reference_audio", "type": "AUDIO", "links": [3, 4], "slot_index": 0}],
            "title": "Higgs v3 Voice Preset  (slot1 = voice -- preset only, no cloning)",
            "widgets_values": ["jake", "", "", "", False],
        },
        {
            "id": 3, "type": "HiggsV3WhisperTranscribe",
            "pos": [340, 400], "size": [320, 160],
            "order": 2, "mode": 0,
            "inputs": [{"name": "audio", "type": "AUDIO", "link": 3, "slot_index": 0}],
            "outputs": [{"name": "transcript", "type": "STRING", "links": [5], "slot_index": 0}],
            "title": "Higgs v3 Whisper Transcribe",
            "widgets_values": [
                "whisper-large-v3-turbo (auto-download)", "auto", "auto", "transcribe", 30, True,
            ],
        },
        {
            "id": 4, "type": "HiggsV3TagBuilder",
            "pos": [0, 600], "size": [340, 140],
            "order": 3, "mode": 0,
            "inputs": [],
            "outputs": [{"name": "combined_text", "type": "STRING", "links": [2], "slot_index": 0}],
            "title": "Higgs v3 Tag Builder  (prompt = text, use tags::speech marker for control tags)",
            "widgets_values": ["Hello! This is Higgs Audio v3 running natively inside ComfyUI.", ""],
        },
        {
            "id": 5, "type": "HiggsV3VoiceClone",
            "pos": [720, 200], "size": [380, 300],
            "order": 4, "mode": 0,
            "inputs": [
                {"name": "higgs_model", "type": "HIGGSV3TTS_MODEL", "link": 1, "slot_index": 0},
                {"name": "text", "type": "STRING", "link": 2, "slot_index": 1},
                {"name": "reference_audio", "type": "AUDIO", "link": 4, "slot_index": 2},
                {"name": "reference_text", "type": "STRING", "link": 5, "slot_index": 3},
            ],
            "outputs": [{"name": "audio", "type": "AUDIO", "links": [6], "slot_index": 0}],
            "title": "Higgs v3 Voice Clone (used here for preset conditioning, not user cloning)",
            "widgets_values": [
                2048, 1.0, 0.95, 50, 0, True, 45, False, 0.15,
            ],
        },
        {
            "id": 6, "type": "SaveAudio",
            "pos": [1140, 200], "size": [280, 80],
            "order": 5, "mode": 0,
            "inputs": [{"name": "audio", "type": "AUDIO", "link": 6, "slot_index": 0}],
            "outputs": [],
            "title": "Save Audio",
            "widgets_values": ["higgs/output"],
        },
    ],
    "links": [
        [1, 1, 0, 5, 0, "HIGGSV3TTS_MODEL"],
        [2, 4, 0, 5, 1, "STRING"],
        [3, 2, 0, 3, 0, "AUDIO"],
        [4, 2, 0, 5, 2, "AUDIO"],
        [5, 3, 0, 5, 3, "STRING"],
        [6, 5, 0, 6, 0, "AUDIO"],
    ],
    "groups": [
        {
            "title": "slot1: voice preset (jake/chloe/eleanor/marcus/nora/oliver)",
            "bounding": [-20, 360, 400, 220],
            "color": "#3f789e",
            "font_size": 18,
        },
        {
            "title": "prompt: text -- prefix with 'tags::' for control tags",
            "bounding": [-20, 560, 400, 220],
            "color": "#3f9e5f",
            "font_size": 18,
        },
    ],
    "config": {},
    "extra": {"ds": {"scale": 1.0, "offset": [0, 0]}, "frontendVersion": "1.43.18"},
    "version": 0.4,
}

api = {
    "1": {
        "inputs": {
            "model": "higgs-audio-v3-tts-4b",
            "dtype": "bf16",
            "device": "auto",
            "attention": "sdpa",
            "download_if_missing": True,
        },
        "class_type": "HiggsV3LoadModel",
        "_meta": {"title": "Higgs v3 Load Model"},
    },
    "2": {
        "inputs": {
            "voice": "jake",
            "custom_audio_url": "",
            "custom_audio_url_alt": "",
            "custom_audio_filename": "",
            "require_clone_source": False,
        },
        "class_type": "HiggsV3VoicePreset",
        "_meta": {"title": "Higgs v3 Voice Preset"},
    },
    "3": {
        "inputs": {
            "audio": ["2", 0],
            "model": "whisper-large-v3-turbo (auto-download)",
            "dtype": "auto",
            "language": "auto",
            "task": "transcribe",
            "chunk_length_s": 30,
            "download_if_missing": True,
        },
        "class_type": "HiggsV3WhisperTranscribe",
        "_meta": {"title": "Higgs v3 Whisper Transcribe"},
    },
    "4": {
        "inputs": {
            "text": "Hello! This is Higgs Audio v3 running natively inside ComfyUI.",
            "tags": "",
        },
        "class_type": "HiggsV3TagBuilder",
        "_meta": {"title": "Higgs v3 Tag Builder"},
    },
    "5": {
        "inputs": {
            "higgs_model": ["1", 0],
            "text": ["4", 0],
            "reference_audio": ["2", 0],
            "reference_text": ["3", 0],
            "max_new_tokens": 2048,
            "temperature": 1.0,
            "top_p": 0.95,
            "top_k": 50,
            "seed": 0,
            "longform_chunking": True,
            "words_per_chunk": 45,
            "tag_chunk": False,
            "pause_between_chunks": 0.15,
        },
        "class_type": "HiggsV3VoiceClone",
        "_meta": {"title": "Higgs v3 Voice Clone"},
    },
    "6": {
        "inputs": {
            "audio": ["5", 0],
            "filename_prefix": "higgs/output",
        },
        "class_type": "SaveAudio",
        "_meta": {"title": "Save Audio"},
    },
}

VOICE_HELP = (
    "jake: energetic, slightly dramatic male, sports-enthusiastic | "
    "chloe: friendly, clear female, standard American | "
    "eleanor: calm, professional female, educational | "
    "marcus: enthusiastic, confident, professorial male | "
    "nora: calm, clear, narrative female | "
    "oliver: calm, articulate, thoughtful male"
)

HF_BASE = "https://huggingface.co/bosonai/higgs-audio-v3-tts-4b/resolve/main"
MODEL_DEST = "higgsv3tts/higgs-audio-v3-tts-4b"
VOICE_BASE = "https://docs.boson.ai/public/audio/higgs-audio-tts-voices"
VOICE_DEST = "higgsv3tts/voices"
VOICE_FILES = [
    "Jake_Rivers_intro.mp3", "Chloe_Adams_intro.mp3", "Eleanor_Reed_intro.mp3",
    "Marcus_Webb_intro.mp3", "Nora_Vance_intro.mp3", "Oliver_Grant_intro.mp3",
]

cfg = {
    "graydient_workflow": {
        "avg_elapsed": None,
        "peak_vram_usage": 14000.0,
        "description": (
            "Text-to-speech using Higgs Audio v3 (4B, bosonai/higgs-audio-v3-tts-4b), "
            "native transformers inference, via Saganaki22/Higgs_v3-TTS-ComfyUI. "
            "PRESET VOICES ONLY -- no cloning inputs exposed on this workflow. For "
            "cloning your own reference clip, use the separate audio-h34b-clone "
            "workflow instead.\n"
            "prompt is the text to speak -- no < > characters, the chat frontend mangles "
            "them before they reach the workflow. To add control tags, prefix prompt "
            "with 'tags::' -- e.g. "
            "'emotion:elation,style:shouting::I sure would love to eat a taco!' -- "
            "bracket-free tags before the FIRST '::' (semicolon/comma separated), "
            "speech after. This is the only reliable tag mechanism -- the separate "
            "negative_prompt field is not wired to anything on this workflow. The "
            "workflow adds the <|...|> wrapper itself. Tags apply to the whole "
            "utterance (prepended), not positioned mid-sentence. Valid emotion values: elation, "
            "amusement, enthusiasm, determination, pride, contentment, affection, "
            "relief, contemplation, confusion, surprise, awe, longing, arousal, anger, "
            "fear, disgust, bitterness, sadness, shame, helplessness. Valid style "
            "values: singing, shouting, whispering (misspelled/invalid values get read "
            "aloud as literal text instead of applying). Inline sfx tags "
            "(<|sfx:laughter|> etc) can go anywhere in the text, followed by matching "
            "onomatopoeia.\n"
            "slot1 picks the speaker: " + VOICE_HELP + "\n"
            "~11-14GB VRAM, fits a 24GB card with headroom. Outputs a FLAC/WAV file."
        ),
        "external_config": None, "external_provider": None, "extra_data": None,
        "field_mapping": [
            {
                "default_value": "Hello! This is Higgs Audio v3 running natively inside ComfyUI.",
                "help_text": (
                    "Text to speak. No <> tags -- the chat frontend mangles them. To add "
                    "control tags, prefix the text with 'tags::' e.g. "
                    "'emotion:elation,style:shouting::Hey there!'."
                ),
                "local_field": "prompt_positive",
                "maximum_value": None, "minimum_value": None,
                "node_id": 4,
                "node_input_index": 0,
                "node_input_name": "text",
                "node_name": "Higgs v3 Tag Builder",
            },
            {
                "default_value": "jake",
                "help_text": VOICE_HELP,
                "local_field": "slot1",
                "maximum_value": None, "minimum_value": None,
                "node_id": 2,
                "node_input_index": 0,
                "node_input_name": "voice",
                "node_name": "Higgs v3 Voice Preset",
            },
            {
                "default_value": "0",
                "help_text": "Random seed",
                "local_field": "seed",
                "maximum_value": None, "minimum_value": None,
                "node_id": 5,
                "node_input_index": 4,
                "node_input_name": "seed",
                "node_name": "Higgs v3 Voice Clone",
            },
            {
                "default_value": "2048",
                "help_text": "Output length budget (codec tokens), not literal seconds",
                "local_field": "length",
                "maximum_value": "8192", "minimum_value": "32",
                "node_id": 5,
                "node_input_index": 0,
                "node_input_name": "max_new_tokens",
                "node_name": "Higgs v3 Voice Clone",
            },
        ],
        "image_url": None,
        "install_detected_nodes": False,
        "is_deleted": False,
        "is_public": True,
        "max_collect_attempts": None,
        "platform": "comfyui",
        "post_install_script": None,
        "pre_install_script": None,
        "concept_mapping": [
            {
                "allow_dynamic": False,
                "concept_name": None, "concept_type": None,
                "dynamic_family": None, "dynamic_subtype_1": None,
                "dynamic_subtype_2": None, "dynamic_type": None,
                "field_mapping": "", "is_zipped": False,
                "type": "url",
                "url": f"{HF_BASE}/model.safetensors",
                "destination": f"{MODEL_DEST}/model.safetensors",
                "weight": None, "weight_field_mapping": None,
            },
            {
                "allow_dynamic": False,
                "concept_name": None, "concept_type": None,
                "dynamic_family": None, "dynamic_subtype_1": None,
                "dynamic_subtype_2": None, "dynamic_type": None,
                "field_mapping": "", "is_zipped": False,
                "type": "url",
                "url": f"{HF_BASE}/model.safetensors.index.json",
                "destination": f"{MODEL_DEST}/model.safetensors.index.json",
                "weight": None, "weight_field_mapping": None,
            },
            {
                "allow_dynamic": False,
                "concept_name": None, "concept_type": None,
                "dynamic_family": None, "dynamic_subtype_1": None,
                "dynamic_subtype_2": None, "dynamic_type": None,
                "field_mapping": "", "is_zipped": False,
                "type": "url",
                "url": f"{HF_BASE}/config.json",
                "destination": f"{MODEL_DEST}/config.json",
                "weight": None, "weight_field_mapping": None,
            },
            {
                "allow_dynamic": False,
                "concept_name": None, "concept_type": None,
                "dynamic_family": None, "dynamic_subtype_1": None,
                "dynamic_subtype_2": None, "dynamic_type": None,
                "field_mapping": "", "is_zipped": False,
                "type": "url",
                "url": f"{HF_BASE}/tokenizer.json",
                "destination": f"{MODEL_DEST}/tokenizer.json",
                "weight": None, "weight_field_mapping": None,
            },
            {
                "allow_dynamic": False,
                "concept_name": None, "concept_type": None,
                "dynamic_family": None, "dynamic_subtype_1": None,
                "dynamic_subtype_2": None, "dynamic_type": None,
                "field_mapping": "", "is_zipped": False,
                "type": "url",
                "url": f"{HF_BASE}/tokenizer_config.json",
                "destination": f"{MODEL_DEST}/tokenizer_config.json",
                "weight": None, "weight_field_mapping": None,
            },
        ] + [
            {
                "allow_dynamic": False,
                "concept_name": None, "concept_type": None,
                "dynamic_family": None, "dynamic_subtype_1": None,
                "dynamic_subtype_2": None, "dynamic_type": None,
                "field_mapping": "", "is_zipped": False,
                "type": "url",
                "url": f"{VOICE_BASE}/{fname}",
                "destination": f"{VOICE_DEST}/{fname}",
                "weight": None, "weight_field_mapping": None,
            }
            for fname in VOICE_FILES
        ],
        "requirements": {
            "github": [
                "https://github.com/Saganaki22/Higgs_v3-TTS-ComfyUI",
                "https://github.com/UnlimitedEditing/ComfyUI-HiggsV3Glue",
            ],
            "pip": [
                "transformers>=5.3.0,<5.6.0",
                "accelerate",
                "safetensors",
                "tokenizers",
                "huggingface_hub",
                "tqdm",
            ],
        },
        "split_prompt_pos_neg": False,
        "supports_dynamic_concepts": False,
        "supports_img2img": False,
        "supports_img2vid": False,
        "supports_low_memory": False,
        "supports_txt2img": False,
        "supports_txt2vid": False,
        "supports_txt2wav": True,
        "supports_vid2img": False,
        "supports_vid2vid": False,
        "supports_vid2wav": False,
        "supports_wav2txt": False,
        "version": 1,
        "workflow":   json.dumps(standard, indent=2),
        "workflow_2": json.dumps(api,      indent=2),
    }
}

with open(r"D:\tripostl\GraydientWorkflow-higgs-v3-tts-preset-v1.json", "w") as f:
    json.dump(cfg, f, indent=2)

print("gen_higgs_tts (preset-only) written OK")
print(f"  github: {cfg['graydient_workflow']['requirements']['github']}")
print(f"  pip:    {cfg['graydient_workflow']['requirements']['pip']}")
print(f"  concept_mapping entries: {len(cfg['graydient_workflow']['concept_mapping'])}")
