---
id: "KI-007"
title: "Runtime Environment Constraints & Anti-Patterns Graveyard"
version: "1.0.0"
type: "constraints_and_graveyard"
tags:
  - constraints
  - graveyard
  - anti-patterns
  - graydient-runtime
  - pure-python
  - package-clashes
sources:
  - "GRAYDIENT-COMPLETE-REFERENCE.md"
  - "CLAUDE.md"
  - "gen_ltx2.5_i2v.py"
  - "gen_higgs_v2.py"
---

# KI-007: Runtime Environment Constraints & Anti-Patterns Graveyard

This document records the hard physical constraints of Graydient's ephemeral cloud runtime and indexes confirmed **dead-end patterns (The Graveyard)**. Any build violating these rules will fail in the cloud and burn quota.

---

## 1. The Pure Python / Pre-Compiled Wheels Rule

> [!CAUTION]
> **NEVER attempt to install packages requiring source compilation (Rust, C++, CMake, Maturin) in `requirements.pip`.**

* **The Reality**: Graydient runners are minimal, non-root, ephemeral Linux containers without `cargo`, `rustc`, `gcc-c++`, or Linux kernel headers.
* **Failure Mode**: `pip install` attempts to build from source distribution (`.tar.gz`), hangs for 5 minutes compiling, and fails with `Command 'cargo' not found` or `error: command 'gcc' failed with exit status 1`.
* **The Rule**: Every PyPI dependency in `requirements.pip` must provide pre-built **`manylinux` wheels** for Python 3.10/3.11/3.12, or be **100% pure Python**.
* **Solution**: When native speed is desired, use standard pre-compiled libraries already present in the ComfyUI base (`torch`, `scipy`, `numpy`, `torchaudio`, `cv2`) rather than custom C/Rust extensions.

---

## 2. Remote URL vs. Local Pre-Staged File Ambiguity

> [!WARNING]
> Standard ComfyUI `LoadAudio` or `LoadImage` nodes only accept local filenames from the `input/` folder and will crash if passed remote HTTP(S) URLs.

* **The Reality**: Graydient submission channels behave inconsistently:
  * Some job submission paths pre-stage user files into ComfyUI's local `input/` directory and pass `filename.wav`.
  * Other job submission paths (e.g., Telegram bot API, webhook triggers) pass raw HTTP URLs like `https://api.telegram.org/file/...`.
* **The Graveyard / Trap**: Using standard `LoadAudio` or naive `requests.get()` inside custom nodes.
* **The Proven Solution**: Use the universal loader pattern (e.g. `Load Audio Any` from `UnlimitedEditing/comfy-audio-duration`), which checks:
  ```python
  if url_or_path.startswith(("http://", "https://")):
      # Download to temp cache
  else:
      # Resolve against folder_paths.get_input_directory()
  ```

---

## 3. Custom Node Offline-First Requirement

> [!IMPORTANT]
> Custom node Python code **MUST** check local disk before calling HuggingFace Hub or ModelScope APIs.

* **Failure Mode**: Calling `snapshot_download()` or `pipeline.from_pretrained("repo_id")` directly at runtime triggers HuggingFace 403 WAF blocks, rate limits, or consumes the 380s execution budget.
* **The Rule**: Pre-stage all weights in `concept_mapping` to `{ComfyUI}/models/...`. The node's `load_model()` method must check `os.path.isfile(...)` first and only fall back to network download if local weights are absent.

---

## 4. Fork Identity & Comfy Registry Collision

* **Failure Mode**: Forking an upstream ComfyUI node repository into `UnlimitedEditing/<repo>` but leaving the original author's `pyproject.toml` (`[project] name` or `[tool.comfy] PublisherId`) unchanged.
* **The Trap**: Graydient / ComfyUI manager registry caches node metadata by package identity rather than Git URL. If upstream identity is retained, the instance will check out cached upstream code instead of your fork.
* **The Rule**: When forking a custom node repo to patch or add nodes:
  1. Update `pyproject.toml` package name.
  2. Verify that `NODE_CLASS_MAPPINGS` export keys match exactly (including case and spaces).

---

## 5. Field Mapping Widget Indexing Rules

* **Failure Mode**: Graydient UI slider or prompt modifies the wrong widget or crashes node execution.
* **The Rule**: `node_input_index` in `field_mapping` is a **0-based index counting ONLY primitive widgets in `widgets_values`**.
* Connected socket inputs (incoming link handles) **MUST BE EXCLUDED** from the count.
* String values sent to `slot1`/`slot2` only match dropdown `COMBO` widgets or `STRING` widgets. They cannot be wired directly into `BOOLEAN` widgets without a glue node.

---

## 6. Frontend HTML Tag Stripping

* **Failure Mode**: Prompts containing `<lora:name:1.0>` or `<style>` lose their tags because Graydient's frontend sanitizes HTML `<` and `>`.
* **The Rule**: Use bracket-free or prefix syntax (e.g., `tags::lora:name:1.0::` or plain descriptive phrases).

---

## 7. A Single `local_field` Can Resolve to THREE Different Shapes Across Submission Paths

* **Failure Mode**: Confirmed live across multiple real jobs on the SAME `local_field` name (`init_audio_url`), on the SAME workflow: one job resolved it to a pre-staged local filename, a later job resolved it to a real `http(s)://` URL. This is not "sometimes wrong," it is architecturally unpredictable per submission path (chat frontend vs Telegram reply vs API call vs webhook).
* **The Rule**: never assume a single resolution shape for an `init_*`/`*_url` field. Use a loader that tries, in order: (1) real `http(s)://` URL → download; (2) a **mangled/delimiter-stripped reference** (see §8 below) → reconstruct then download; (3) bare filename → resolve against `folder_paths.get_input_directory()`.
* **Defensive field mapping**: it is also unclear which *local_field name* (not just which value shape) a given submission path populates — `init_audio`, `init_audio_url`, and `init_audio_filename` are all real, distinct field names Graydient may use. Map all three to separate inputs on the same loader node, first non-empty wins, rather than picking one and hoping. Confirmed working pattern: `ComfyUI-HiggsV3Glue`'s `HiggsV3VoicePreset` (`custom_audio_url`/`custom_audio_url_alt`/`custom_audio_filename`) and this project's `Load Audio Any` (`audio_source`/`audio_source_alt`/`audio_source_filename`).

---

## 8. Mangled Telegram File References

* **Failure Mode**: Confirmed live: a Telegram voice/photo message reply can produce a value with every `:`/`/` delimiter stripped out, e.g. `init_audio__httpsapi.telegram.orgfilebot5714594430AAFo...voicefile2033054.oga` — neither a valid URL nor a real local filename. This happens when the submitting client skips uploading the attachment first (Graydient has no upload endpoint of its own for this path).
* **The Reconstruction**: this specific shape is recoverable via a narrow, known-format regex matching Telegram's Bot API file-download URL convention (`https://api.telegram.org/file/bot<id>:<secret>/<voice|photo|video|...>/file_<id>.<ext>`), NOT a general "guess any mangled URL" heuristic — mangling is lossy for arbitrary URLs and can't be reversed in general.
  ```python
  _MANGLED_TELEGRAM_FILE_RE = re.compile(
      r'^(?:[a-z_]+__)?(https?)api\.telegram\.orgfilebot(\d+)([A-Za-z0-9_-]+?)'
      r'(voice|photo|video_note|video|audio|document|animation|sticker)file(\d+)\.([a-z0-9]+)$',
      re.IGNORECASE,
  )
  ```
* **Reference implementation**: `ComfyUI-HiggsV3Glue`'s `_unmangle_telegram_file_url`, ported into this project's `Load Audio Any` node.

---

## 9. Encoding Audio Into the Graph ≠ The Model Uses It For Sync

* **Failure Mode**: Confirmed live: a workflow that correctly loads a real reference audio file, correctly plays it back in the final video, AND correctly encodes it into an `audio_latent` slot via `LTXVAudioVAEEncode` can still produce video motion that is completely unrelated to the audio's content (e.g. a subject silently walks off frame while unrelated correct audio plays). "The audio is in the graph and gets muxed correctly" is NOT the same claim as "the model is conditioning generation on it."
* **Two separate root causes found, both real**:
  1. **Silent placeholder trap**: using `LTXVEmptyLatentAudio` (a placeholder of zeros) anywhere in the audio_latent path instead of `LTXVAudioVAEEncode`'s real-audio output means the model has nothing to condition on at all, regardless of what plays in the final muxed file.
  2. **Prompting**: even with real audio encoded, the model does not infer "this person is speaking, animate their mouth" from the audio_latent alone. The official LTX-2.5/2.3 templates' own default prompt examples explicitly describe the subject as speaking AND quote the actual spoken words (`...says: "The old gods are silent. I am not."`) — this quoted-dialogue pattern is a CONFIRMED requirement for speech lip-sync, not optional flavor text. For non-speech audio (music, rhythmic sound), the same principle likely generalizes to describing the specific physical action synced to the audio (unconfirmed for non-speech, treat as the working hypothesis, not proven).
  3. **The actual sync mechanism** (once real audio is used and the prompt is right): `SetLatentNoiseMask` with a `SolidMask(value=0)` locks the encoded audio latent as FIXED conditioning for the sampling run — confirmed by reading `LTXVImgToVideoInplace`'s own `noise_mask = 1.0 - strength` formula in source. Wiring `LTXVAudioVAEEncode`'s output straight into `LTXVConcatAVLatent` without this lock is a weaker, unconfirmed form of conditioning; the official `ia2v` template does the lock, an earlier revision of this project's LTX-2.5 workflow did not, and users reported the difference as noticeably "choppy"/imprecise sync.
* **The Rule**: when building an audio-conditioned generation workflow, (1) confirm the real audio actually reaches an `*Encode` node, not a placeholder; (2) confirm the prompt explicitly describes the audio-driven action, quoting/paraphrasing content for speech; (3) confirm there's an explicit conditioning-lock mechanism (noise mask, or whatever the model family's equivalent is), not just "the tensors are connected."


### ⚠️ faster-whisper-small vocabulary filename mismatch
* **Platform Failure**: Systran/faster-whisper-small ships vocabulary.txt and no preprocessor_config.json, unlike faster-whisper-large-v3 which ships vocabulary.json + preprocessor_config.json. Assuming same-family HF repos share a file layout caused 'Cannot load the vocabulary from the model directory' on Graydient. Always check the HF API file listing (huggingface.co/api/models/<repo>) per model size before writing concept_mapping, don't copy an existing staged entry's filenames.
* **Rule**: Avoid this pattern in future builds.

---

## 10. VHS_VideoCombine + Audio Writes 3 Files; Graydient's Output-Picker Isn't Reliable About Which One It Returns

* **Failure Mode**: Confirmed live on the subtitle-burn-in workflow (`gen_subtitles.py`): a job returned a static PNG image as "the result" instead of the rendered video, with no error anywhere in the job log — execution succeeded end-to-end, transcription was correct, nothing crashed. A retry of the byte-identical workflow correctly returned the video. Non-deterministic, not a wiring bug.
* **Root cause** (confirmed by reading `ComfyUI-VideoHelperSuite`'s actual source, `videohelpersuite/nodes.py`'s `combine_video()`, not guessed): whenever `VHS_VideoCombine` is given an `audio` input, it writes **three** files into the output directory per run:
  1. `<prefix>_<counter>.png` — first frame, saved for metadata, written unconditionally unless suppressed.
  2. `<prefix>_<counter>.<ext>` — a video-only intermediate (no audio), written before muxing.
  3. `<prefix>_<counter>-audio.<ext>` — the final audio-muxed file. The node's own internal `file` variable is reassigned to point at this one — it's unambiguous *inside the node* which file is "the real result."
* **The Rule**: Graydient's job-output harvesting does not reliably read the node's own declared final file (`ui.gifs[0].filename` in the node's return value) when multiple candidate files exist in the output directory for that job — it can pick any of the three. Do not treat "the job succeeded with no errors" as proof the *correct* file was returned when `VHS_VideoCombine` has an audio input; check which file actually came back.
* **Fix, confirmed working on a real job**: two flags read via the hidden `EXTRA_PNGINFO` input (`extra_pnginfo['workflow']['extra'][...]` in VHS's source) — these are **workflow-level flags, not node widgets**, and belong in the submitted standard-format workflow's top-level `"extra"` dict, alongside the usual `ds`/`frontendVersion` keys:
  ```json
  "extra": {
    "ds": {"scale": 1.0, "offset": [0, 0]}, "frontendVersion": "1.43.18",
    "VHS_MetadataImage": false,
    "VHS_KeepIntermediate": false
  }
  ```
  `VHS_MetadataImage: false` suppresses file (1). `VHS_KeepIntermediate: false` deletes file (2) after muxing. With both set, only the final `-audio.<ext>` file exists in the output dir — nothing left for the output-picker to get wrong.
* **Reusable, not subtitle-specific**: applies to any Graydient workflow using `VHS_VideoCombine` with an audio input — v2v, i2v+audio, TTS-to-video, anything muxing a real audio track. Reference implementation: `gen_subtitles.py`'s `standard["extra"]`.
