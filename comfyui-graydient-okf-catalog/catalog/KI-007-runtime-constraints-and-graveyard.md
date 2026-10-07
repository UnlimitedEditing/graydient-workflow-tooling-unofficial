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

### ⚠️ `pre_install_script` has NO confirmed-working precedent anywhere in this project -- do not build startup-time-critical logic on it
* **Platform Failure**: Built a real optimization (gen_trellis2_shape.py/gen_trellis2_texture.py v3) on `pre_install_script` executing a curl+tar extraction of a prebuilt dependency tarball into the job's venv site-packages, reasoning by analogy from `gen_hy3d21_mv_texture_v1.py`'s use of `pre_install_script` for wheel installs. Confirmed live (2026-09-03): **it never ran at all** -- none of its `echo` output appeared anywhere in the job log (checked the full log, not just a grep miss), and `ComfyUI-Trellis2` failed to import with `ModuleNotFoundError: No module named 'trimesh'`, the exact package the tarball was supposed to provide. The job's printed `COMMAND` block only ever shows the `requirements.pip`-derived `pip install` chain -- `pre_install_script`'s own commands are not visible in that block at all, meaning either it runs in a separate untracked step whose output isn't surfaced in this log export, or it silently didn't execute.
* **Why this was an easy trap**: every OTHER `gen_*.py` in this project that uses `pre_install_script` (`gen_cosmos3_i2i.py`, `gen_cosmos3_i2v.py`, `gen_cosmos3_t2i.py`, `gen_cosmos3_t2v.py`, `gen_hy3d21_mv_texture_v1.py`, `gen_hy3d21_texture_v1.py`) is *also* flagged in its own memory/description as never having been run live and confirmed. There was no actual prior evidence `pre_install_script` works as assumed in this project -- only an untested pattern copied forward script-to-script, each one inheriting the last one's unverified assumption without anyone actually confirming it.
* **The Fix**: reverted to declaring the same packages directly in `requirements.pip` (the proven mechanism, confirmed working every prior run this session).
* **Rule**: do not build a workflow around `pre_install_script` for anything startup-time-critical (dependency installs, environment setup a later node needs to import) without first running a minimal confirmation job that proves it actually executes and in the right environment (i.e., does a `pre_install_script` that just runs `echo` + `which python` + `python -c "import sys; print(sys.executable)"` actually show that output in a real job log, and does that python match the venv the job's node code actually runs under). Until one of `gen_cosmos3_*.py`/`gen_hy3d21_*.py`/this pair has that confirmation, treat `pre_install_script` project-wide as unverified, not as a working feature.

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


## 11. A Custom Node Repo's Own `requirements.txt` Can Be Incomplete

* **Failure Mode**: Confirmed live on `gen_audio_superres.py` (`ComfyUI-AudioSR`, wrapping `versatile_audio_super_resolution`): a job's first attempt failed the custom node's import entirely — `ModuleNotFoundError: No module named 'pandas'`, inside `audiosr/clap/training/data.py`. The `pip` requirements list had been mirrored from the upstream repo's own `requirements.txt` — and `pandas` genuinely isn't in it. This isn't a transcription mistake on this project's side; it's a real gap in the upstream repo's own dependency declaration (`audiosr/clap/training/data.py` does `import pandas as pd` directly, several import-hops deep from the node's `__init__.py`, and nothing in the declared requirements pulls it in transitively either).
* **The Rule**: treat a custom node repo's own `requirements.txt` as a strong starting point, not a guaranteed-complete one — especially for repos with deep import chains through vendored/bundled sub-packages (this one imports through `vasr_node.py` → `versatile_audio_super_resolution.audiosr.pipeline` → `...latent_diffusion.models.ddpm` → `...modules.encoders.modules` → `...clap.training.data`, four hops past the top-level module). A real job's import traceback is the actual ground truth for "does this pip list work," not the repo's own declared file. When a job fails on `ModuleNotFoundError` for something not in the mirrored requirements, add it directly — don't assume the omission means it's actually unneeded.
* **Fix, confirmed working on a real job**: added `pandas` on top of an exact mirror of upstream's `requirements.txt`. Second job run got past node import and into actual DDIM sampling with no further missing-module errors.


### ⚠️ longcat-i2v-v1
* **Platform Failure**: First real Graydient run: glitchy/incoherent video output, exported as GIF instead of MP4 despite VHS_VideoCombine format=video/h264-mp4. No audio (expected — this I2V workflow has no audio node, not a bug). Suspect causes: (1) distill LoRA filename substituted at build time (LongCat_distill_lora_alpha64_bf16.safetensors) since the example workflow's original filename (rank128 variant) no longer exists on HF — unverified this is the correct/compatible LoRA for the 10-step longcat_distill_euler schedule, wrong LoRA would explain glitchy/incoherent motion; (2) GIF fallback suggests ffmpeg was not resolved by VHS_VideoCombine in the ephemeral container despite imageio-ffmpeg being in pip requirements — needs verification whether system ffmpeg binary vs imageio-ffmpeg bundled binary is what VHS_VideoCombine actually calls. Needs job log inspection before retrying.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ longcat-i2v-v1-clean-run-bad-output
* **Platform Failure**: Correction to prior bury: job log confirmed clean execution (no crashes, no ffmpeg fallback, no shape errors) yet output was glitchy/bad quality. This means the graph is structurally valid but has a silent wrong-config bug. Top suspects, both unverified guesses at build time: (1) substituted distill LoRA filename LongCat_distill_lora_alpha64_bf16.safetensors in place of the example workflow's LongCat_distill_lora_rank128_bf16.safetensors (no longer on HF) -- loads without error but alpha/strength convention may not match what longcat_distill_euler+shift=12 was tuned against; (2) WanVideoEncode's last two widget values (0, 1) were guessed by position since this node's real INPUT_TYPES source (core WanVideoWrapper nodes.py, not the LongCat/ subfile) was never located/read. Before retrying: find WanVideoEncode's actual source to confirm widget order, and check WanVideoWrapper GitHub issues/discussions for the correct distill LoRA filename+strength for LongCat's 10-step distilled schedule.
* **Rule**: Avoid this pattern in future builds.


## 12. Stale Per-Machine Custom-Node Cache — Fork to a Never-Cached URL

* **Failure Mode**: `gen_krea2_regional.py`'s job repeatedly failed with `missing_node_type` for `Compare-🔬` (`class_type: "Compare-🔬"`), from `theUpsider/ComfyUI-Logic`, across multiple back-to-back runs on an unmodified workflow that had previously worked. `requirements.github` correctly listed the repo, and the repo itself was reachable (`curl -sI` → 200 OK). The ComfyUI startup log's "Import times for custom nodes" block never listed `ComfyUI-Logic` at all — not even a failed-import line — meaning the clone step for that one URL was being silently skipped, while the other two repos in the same `requirements.github` list (`ComfyUI-Krea2-Regional`, `comfyui-propost`) cloned fine every run. This matches the pre-existing "some machines cache a cloned custom-node repo rather than always re-cloning" note (`GRAYDIENT-COMPLETE-REFERENCE.md` §Ephemeral containers, first confirmed live 2026-08-02) — this is the second live confirmation of that bug, and the first confirmation of a working fix.
* **The Trap**: the ComfyUI startup log alone (`python main.py ...`) only shows what happened *after* node cloning — it never shows the clone step itself, so there's no direct evidence available from a normal job log to prove *why* a repo failed to clone. Diagnosis here was by elimination: repo reachable, JSON correct, other repos in the same list clone fine, error is byte-for-byte identical across consecutive runs → points at a per-machine cache keyed by the old URL, not a repo/network/JSON problem.
* **The Fix, confirmed working on a real job**: forked all three `requirements.github` repos to `UnlimitedEditing` (`ComfyUI-Krea2-Regional`, `comfyui-propost`, `ComfyUI-Logic`) and repointed `gen_krea2_regional.py`'s `requirements.github` at the fork URLs instead of upstream. A fork URL has never been cloned by any Graydient machine before, so there's no stale cache keyed to it — this forces a fresh clone regardless of which machine the job lands on. Confirmed by the user on a real Graydient run: workflow completed successfully.
* **The Rule**: if a `requirements.github` repo starts silently failing to clone on a previously-working, unmodified workflow — especially if the failure is byte-identical across consecutive runs while other repos in the same list clone fine — don't treat it as a code or network problem. Fork the repo to `UnlimitedEditing` and repoint `requirements.github` at the fork. This is now the standard first response to this failure signature, not just a one-off workaround; note it also happens to satisfy [[Section 4]]'s general recommendation to fork every dependency this project doesn't control, for exactly this kind of platform-side unreliability, not only for patching node code.
* **Caveat**: none of these three repos publish to the ComfyUI Registry (no `pyproject.toml` `[tool.comfy] PublisherId`), so Section 4's registry-identity-collision trap didn't apply here and the fork worked with zero further changes. If a future fork target *does* publish to the registry, Section 4's `pyproject.toml` identity fix is still required on top of this — forking the URL alone would not be enough in that case.


## 13. Native/GPU Dependencies That Can't Be pip-Installed Into ComfyUI: Private `pip --target` + Prebuilt Binaries (confirmed working)

* **Reference implementation**: `UnlimitedEditing/ComfyUI-RigStudio` (`rigstudio/runtime.py`), confirmed live 2026-09-24, render `39o388` (`rigstudio-a2f-probe`, `gen_rigstudio_a2f_probe.py`), RTX 4090 / driver 580.126.18 / Python 3.12.3 / glibc 2.39.
* **Problem it solves**: NVIDIA Audio2Face-3D is a C++/TensorRT SDK — no compiler on runners (§1), and pip-installing TensorRT/CUDA wheels into ComfyUI's venv risks fighting torch's pinned `nvidia-*` wheels (same class as the VHS numpy crash below).
* **The pattern (all confirmed in that job)**:
  1. Prebuilt Linux binary + `.so` shipped as a GitHub **release asset**, downloaded inside the node with `asyncio.to_thread(urllib.request.urlretrieve, ...)` (0.4 s). Built on Ubuntu 22.04 (glibc 2.35) + CUDA 12.9 — runs fine on the runner's glibc 2.39 / driver 580.
  2. Native deps installed **from inside the node** with an async subprocess: `python -m pip install --no-deps --target <private dir> --extra-index-url https://pypi.nvidia.com tensorrt-cu12-libs==10.13.3.9 tensorrt-cu12-bindings==10.13.3.9 nvidia-cuda-runtime-cu12==12.9.79 nvidia-cublas-cu12==12.9.1.4 nvidia-curand-cu12==10.3.10.19` — **42 s**, ComfyUI venv untouched. (On PyPI `tensorrt-cu12-libs` is only an sdist stub; the real wheel is on pypi.nvidia.com.)
  3. Children run with `LD_LIBRARY_PATH` = bundle `lib/` + `<private>/tensorrt_libs` + `<private>/nvidia/*/lib`, and `PYTHONPATH=<private>` for the TensorRT Python bindings.
  4. TensorRT engines are GPU-specific; build from ONNX in-job with the TensorRT **Python API** (`trtexec` is not in pip) with `config.hardware_compatibility_level = AMPERE_PLUS` so one engine runs on every Ampere+ GPU. Audio2Face-3D v2.3 Mark: **59 s, 89.8 MB** on a 4090; inference on 4 s audio **1.2 s**.
  5. Smuggle the engine out once with Meshsmuggler (works for any binary, CRC-verified) and pass it back to later jobs by URL instead of rebuilding.
* **The Rule**: for native/GPU deps, prefer this over `requirements.pip` (venv conflicts) and over `pre_install_script` (§ unverified). Keep every subprocess async (`asyncio.create_subprocess_exec`, own process group) — see the bpy event-loop timeout entry.

## 14. `lyric-llm` (id 3210) Ignores API Prompts; Finding Restored Workflow Slugs

* **Failure Mode**: `/run:lyric-llm` via the render API returned the literal reply `{}` for every prompt, including a one-line "return JSON with key word = banana" (renders `QYjKDb`, `5NqG3P`, 2026-09-24). The render's own record (`GET /api/v3/render/<hash>` → `attributes.clean_prompt`) shows the full prompt **did arrive intact**, braces and newlines included — so it is not Graydient's prompt parser mangling it; the deployed workflow definition evidently doesn't wire `prompt` to `HFTextGenerate.user_prompt`, and the model answers the JSON-only system prompt with `{}`.
* **The Rule**: don't use `lyric-llm` for API text generation; build a workflow that links the prompt into `HFTextGenerate` itself (see `gen_rigstudio_intent.py`). When debugging "the model ignored my prompt", read `clean_prompt` on the render record before blaming prompt syntax.
* **Useful**: `GET https://app.graydient.ai/api/v3/workflows/` (Bearer API key) lists workflows with their `slug` — the name chosen at Restore time can differ from what a script assumes (`unknown /run:<slug>` → HTTP 403 "small mistake in your prompt").

## 15. Use `prompt_positive`, Not `prompt`, for the Main Text Field; Slot Values Can't Contain `/`

* **Failure Mode (confirmed by an A/B pair of real jobs, 2026-09-24)**: `rig-track` v1 mapped `local_field: "prompt"` → `RigStudioBuildTrack.intent`. Render `ZVzPB9`: the render record's `clean_prompt` held the full intent string, yet the node received `""` — the track came out emotionally neutral (0 `emotion` events, outer-brow max 0.017). v2, identical except `local_field: "prompt_positive"`, delivered it (render `PZJPBn`: 12 `emotion` events, outer-brow max 0.365, smile max 0.568). `prompt_positive` is what 390 deployed workflows use (25 use `prompt`). This is very likely also why `lyric-llm` (§14, `local_field: "prompt"`) answers `{}`.
* **Second gotcha, same session**: Graydient's options parser splits slot values on `/` — `/slot1:https://github.com/...` fails with HTTP 403 "small mistake in your prompt. unknown `/<last path segment>`". URLs and hub ids (`Qwen/Qwen2.5-3B-Instruct`) cannot be passed through slots; give the node a sensible default instead (e.g. `RigStudioBuildTrack` falls back to its published engine URL).
* **The Rule**: map the main text input with `local_field: "prompt_positive"` (the linter now WARNs on `"prompt"`). Never design a slot to carry a URL or a `/`-containing id.
* **Also confirmed**: pre-staging the LLM via concept_mapping (Qwen2.5-7B-Instruct → `llm/Qwen2.5-7B-Instruct/`) and passing the local folder to `HFTextGenerate.model_id` (via `RigStudioModelPath`) cut `rig-intent` from 404 s / avg 390.6 s to **281 s** — `HFTextGenerate` given a hub id downloads the 15 GB model inside the job budget.


## 16. An LLM Server Run From Inside the Node: Ollama + Registry Blobs via concept_mapping (confirmed working)

* **Reference implementation**: `UnlimitedEditing/ComfyUI-RigStudio` `rigstudio/llm_runtime.py` + `gen_rigstudio_direct.py`, confirmed live 2026-09-30, render `ZVe419` (`rig-direct`), RTX 4090: whole job 223 s including faster-whisper medium on 188 s audio and 5 LLM calls.
* **Why**: the director was benchmarked on Ollama's library `qwen3:14b` (Q4_K_M). bf16 14B (28 GB) does not fit 24 GB; re-quantising with another runtime would not reproduce the benchmark. Running the exact same Ollama build + model blobs does.
* **The pattern**: (1) concept_mapping stages the official GitHub release asset `ollama-linux-amd64.tar.zst` (a 302 redirect -- the downloader follows it) and every blob of the model from `https://registry.ollama.ai/v2/library/<name>/blobs/sha256:<digest>` (no auth) to `ollama/blobs/sha256-<digest>`; (2) the node unpacks the tarball with `zstandard` from a private `pip --target` dir (skipping cuda_v13/rocm/vulkan/mlx), builds a private `OLLAMA_MODELS` dir of symlinks + writes the manifest JSON itself (copied from a local pull); (3) `ollama serve` on a free port as an async child in its own process group, killed on exit. Get the digests from a local `ollama pull` (`manifests/registry.ollama.ai/library/<name>/<tag>`).
* **The Rule**: to reproduce a locally benchmarked Ollama model on Graydient, stage its registry blobs + the same Ollama version rather than swapping runtime/quantisation. Qwen3 needs `"think": false` in the chat request for line-format output.

## 17. Graydient's PyAV Breaks faster-whisper's Own Audio Decoder (confirmed 2026-09-30)

* **Failure Mode**: `rig-direct` v1 first run: `faster_whisper/audio.py decode_audio -> av.open(input_file, mode="r", metadata_errors="ignore")` raised `TypeError: open() got an unexpected keyword argument 'metadata_errors'` (ComfyUI 0.38.0, torch 2.11.0+cu128, Python 3.12.3 image). The same Whisper path worked in `rig-intent` a week earlier -- the platform image's PyAV changed underneath it. Any faster-whisper node that passes a file PATH is exposed (TranscribeAudioFromURL included).
* **The Fix (confirmed, render ZVe419)**: never give faster-whisper a path. Decode with the system `ffmpeg` to 16 kHz mono s16 WAV, read it with the stdlib `wave` module into float32 / 32768, and pass the ARRAY to `model.transcribe()` -- faster-whisper skips `decode_audio` for arrays.
* **The Rule**: treat PyAV / torchaudio decoding on Graydient as unreliable (same family as the torchcodec note in ComfyUI-YuE2Fast); decode audio with the system ffmpeg binary.

## 18. Warm Machines Keep /tmp Between Different Workflows -- Symlinks Dangle (confirmed 2026-09-30)

* **Failure Mode**: `rig-perform` v1 first run landed on a machine that had run `rig-track` before: `/tmp/rigstudio` (the nodes' work dir) survived, with symlinks pointing into the *previous workflow's* project dir (`.../rig-track-3789-.../comfyui/models/...`), which Graydient had deleted. `os.path.exists()` is False for a dangling link, so the code tried `os.symlink()` again -> `FileExistsError: [Errno 17]`. The log's "bundle 0.0s, analysis deps 0.0s" is the tell that /tmp was warm.
* **The Fix (confirmed, render ndxPNV)**: re-point every link on every run (`if os.path.lexists(dst): os.remove(dst)` then `os.symlink`), never "create only if missing".
* **The Rule**: caches in /tmp can be reused across DIFFERENT workflows on the same machine, and anything they reference inside a project dir (models/, custom_nodes/) may be gone. Cache self-contained files freely; never cache pointers into a project dir.

### ⚠️ hy3d-views-v1 first live attempt
* **Platform Failure**: Not a workflow bug: Graydient's own ComfyUI-Launcher server on machine tls-pro-ny4-g2 threw a 500 during import_project because its internal companion service (localhost:33666, /api/comfyui-launcher/setup_workflow_json) refused the connection -- the workflow JSON never reached ComfyUI itself. All 5 concept_mapping assets (qwen_image_edit_2511_fp8mixed, qwen_2.5_vl_7b_fp8_scaled, qwen_image_vae, Lightning LoRA, Multi-Angles LoRA) staged fine (exists/fetched/mirror-fetched). This looks like a Graydient machine-side infra issue, possibly worth reporting to Graydient support or retrying on a different machine class, not a node-graph/model problem.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ hy3d-views-v1 2511->2509 matched-set pivot
* **Platform Failure**: Original 2511 Qwen Image Edit base + fal 2511 multi-angle LoRA is an unofficial third-party pairing never validated together; official Comfy-Org 1-click-multi-angle template uses a matched 2509 base+Lightning+multi-angle-LoRA set with plain literal rotation prompts instead of jtydhr88/ComfyUI-qwenmultiangle. Switched gen_hy3d_views_v1.py to the 2509 matched set, ImageScaleToTotalPixels, shift=3, and literal prompts; dropped the qwenmultiangle github dep. Not yet run on a live job -- still first-attempt untested.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ hy3d-views-v1 second live attempt (different machine)
* **Platform Failure**: Identical failure to the first attempt (see 'hy3d-views-v1 first live attempt' entry) but on a DIFFERENT machine: tls-pro-ny4-g3 this time (first was tls-pro-ny4-g2). Same signature: Graydient's own ComfyUI-Launcher server's import_project call to its internal companion service (localhost:33666, /api/comfyui-launcher/setup_workflow_json) got Connection refused, before ComfyUI itself ever saw the workflow. Failed near-instantly this time (0.098s elapsed) vs the first attempt. All 5 concept_mapping assets (now the corrected 2509 set: qwen_image_edit_2509_fp8_e4m3fn, qwen_2.5_vl_7b_fp8_scaled, qwen_image_vae, Qwen-Image-Edit-2509-Lightning-4steps, Qwen-Edit-2509-Multiple-angles) showed status exists/cached, so model staging is not the issue either time. Two different machines hitting the identical internal-service-unreachable error raises confidence this is a systemic Graydient infra issue (their internal setup_workflow_json companion service being down/misconfigured fleet-wide or intermittently), not a single flaky box -- worth reporting to Graydient support directly rather than continuing to retry blind.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ alice-t2v-14b-moe
* **Platform Failure**: Abandoned pre-launch (never ran a confirmed Graydient job): checkpoint is fp32-only on HF (~126GB, not the README's claimed ~27GB — 2 x 14B DiT experts x ~53GB fp32 each + T5 11.4GB). convert_model_dtype casts fp32->bf16 AFTER load (needed just to fit ~28GB VRAM with offload_model=True), but does nothing for the ~126GB download cost, which is unaffected either way. No fp8/bf16 requantized checkpoint exists anywhere on HF, and the vendored alice/models/attention.py has no fp8 kernel path (only flash_attn/sdpa bf16/fp32) so a hand-rolled fp8 cast wouldn't even run correctly without real calibrated quantization work. Fork with vendored source + offline-first ckpt_dir patch still exists at github.com/UnlimitedEditing/Eric-Alice-T2V-ComfyUI-Wrapper and gen_alice_t2v.py/GraydientWorkflow-alice-t2v-v1.json are in the repo if this is ever revisited, but LTX2.5 and MiniMax/Hunyuan3 (H3) are judged superior and preferred instead.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ hy3d-views-v1 third live attempt (with FluxKontextMultiReferenceLatentMethod fix)
* **Platform Failure**: Same localhost:33666 setup_workflow_json connection-refused signature as the first two occurrences, but this time on machine tls-pro-ny6-g0 -- a DIFFERENT machine class family entirely (first two were tls-pro-ny4-g2 and tls-pro-ny4-g3). Near-instant failure again (0.101s elapsed), before ComfyUI ever saw the workflow -- so this is unrelated to the FluxKontextMultiReferenceLatentMethod addition just made to gen_hy3d_views_v1.py, which was never actually tested. Three occurrences across two different machine class families (ny4 and ny6) is strong evidence this is a persistent/widespread Graydient-side infra issue (their internal ComfyUI-Launcher companion service being down or misconfigured), not single-machine flakiness. Worth reporting to Graydient support directly rather than continuing to retry blind -- prior retries did eventually get through once (per the working screenshot earlier in this project), so it's intermittent rather than a hard outage, but happening often enough across enough machines to be worth flagging upstream.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ hy3d-views-v1 fourth live attempt
* **Platform Failure**: Same localhost:33666 setup_workflow_json connection-refused signature, fourth occurrence, back on tls-pro-ny4-g2 (same machine as the very first failure). Near-instant (0.051s). User is switching to a fresh workflow slot on Graydient (rather than restoring into the same existing slot repeatedly) to see if that changes anything -- untested whether workflow-slot identity affects which machine/container a job lands on.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ hunyuanworld-mirror-v1 fifth/sixth/seventh live attempts, including a fresh workflow slot
* **Platform Failure**: Same localhost:33666 signature, three more occurrences (2026-09-01), on machines tls-pro-ny8-g0 and tls-pro-ny4-g3, elapsed 0.14-0.24s each time. Critically, the SEVENTH occurrence was on a brand-new Graydient workflow slot (never restored into before) -- answers the "untested whether workflow-slot identity affects which machine/container a job lands on" question from the hy3d-views-v1 fourth attempt above: it does not. A fresh slot hit the identical failure just as readily as a repeatedly-reused one, ruling out per-slot staleness/corruption as a contributing factor and further strengthening the case that this is generic Graydient launcher-fleet flakiness, unrelated to workflow identity, content, or history. Combined with the hy3d-views-v1 occurrences, this signature has now been confirmed 7 times across 2 unrelated pipelines, 5 distinct machines, 2 machine-class families, and both reused and fresh workflow slots.
* **Rule**: Stop trying to diagnose this via workflow-side changes (slot freshness, requirements.github forks, field_mapping, node code) -- none of those variables correlate with occurrence. This is now solidly confirmed as a Graydient-side infra issue worth reporting directly to their support with this accumulated evidence. Retrying (sometimes after a wait) remains the only known workaround; it is intermittent, not a hard outage.


### ⚠️ hunyuanworld-mirror-v1 first draft used wrong image-input shape
* **Platform Failure**: First draft copied the object-turnaround pipeline's fixed front/right/back/left 4-slot pattern (correct for Hunyuan3D's mv-turbo conditioning) onto a scene-reconstruction workflow where it doesn't make sense -- a scene has no natural 'left/right/back' relative to a single subject. Fixed by adding a new node (Hy3DLoadImageBatchFromURLList, in UnlimitedEditing/ComfyUI-Hunyuan3D) that takes one multiline STRING field (one URL per line) and batches however many images are provided, since Graydient's field_mapping can only expose a fixed number of named fields, not a true variadic list -- this is the workaround for that platform constraint. Lesson: don't reuse a prior workflow's input shape without checking whether the new model's actual input semantics (fixed conditioning slots vs. a genuine variable-length sequence) still fit.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ hunyuanworld-mirror-v1 second field-mapping correction: real Graydient vocabulary
* **Platform Failure**: The variadic-single-multiline-field approach (Hy3DLoadImageBatchFromURLList) from the prior correction was ALSO wrong -- not because variable image count was a bad goal, but because Graydient's field_mapping only recognizes a fixed, documented vocabulary of named fields (per GRAYDIENT-COMPLETE-REFERENCE.md's 'All slot types' table): init_image_url for the primary image, plus image1..image9 for up to 9 more (10 total). A custom multiline URL-list field isn't part of that vocabulary and Graydient's UI has no way to expose 'paste many URLs in one box' for it. Rebuilt with 10 Hy3DLoadImageFromURL nodes (one per real slot name) batched via 9 chained ImageBatch nodes. Lesson: when GRAYDIENT-COMPLETE-REFERENCE.md documents an exact field vocabulary, use it verbatim -- don't invent a field name that seems reasonable, even to solve a real UX problem (arbitrary image count). The platform's actual constraint (bounded named slots, not true variadic) has to be worked within, not around.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ hunyuanworld-mirror-v1 live run: real node collision, 15s render, everything else worked
* **Platform Failure**: First fully-successful live run otherwise: 15.42s total, model loaded correctly (fixed-fallback filename fix from earlier correction worked), all 10 images batched and preprocessed correctly (518x518), HWMInference ran cleanly producing depth/normals/points3d/poses/intrinsics/gaussians for all 10 frames, SaveCameraParams and SaveDepthMap and Save3DGaussians (170422 Gaussians after 95th-percentile scale filtering) all succeeded. gsplat's JIT-compile-on-first-use never triggered, confirming the earlier source-read (dead import in worldmirror.py) was correct. ONLY failure: SavePointCloud (node 23) failed prompt validation asking for width/viewport_state/filename_prefix/model_3d/height -- NONE of which are cedarconnor's actual node's params. Root cause: ComfyUI core (this job ran v0.34.0) added its OWN native SavePointCloud node this month (comfy_extras/nodes_save_3d.py) as part of its rapidly-expanding 3D asset support (Pixal3D/TRELLIS2/SaveGLB/SaveGaussianSplat etc all landed recently per release notes read earlier this session) -- an exact NODE_CLASS_MAPPINGS key collision, core wins at registration. Fixed by forking cedarconnor's repo (UnlimitedEditing/ComfyUI-HunyuanWorld-Mirror) and renaming just the registration key to HWMSavePointCloud, matching this project's established globally-unique-node-name convention. General lesson for future gen_*.py builds: as ComfyUI core keeps adding native 3D/asset nodes, generic node names (SavePointCloud, SaveMesh, LoadImage-style genericism) in any THIRD-PARTY node pack are increasingly likely to collide with newly-added core nodes -- worth a quick core-repo name check for any generically-named custom node before wiring it into a workflow, not just at first build but each time a workflow is revived after a ComfyUI version gap.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ hunyuanworld-mirror-v1 blank-frame filter added
* **Platform Failure**: Live testing with only init_image_url filled showed 'Input: 10 images' in the log -- confirmed the 9 unused image1..image9 slots' blank-placeholder frames (constant white, from Hy3DLoadImageFromURL's empty-URL fallback) were being batched in as if they were real observations of the scene, diluting/corrupting what should have been a clean single-image reconstruction. Fixed with a new node (Hy3DBatchImagesSkippingBlanks, UnlimitedEditing/ComfyUI-Hunyuan3D) that detects the constant-~1.0 blank signature and drops those frames before they reach HWMInference, replacing the naive 9-node ImageBatch chain (which had no filtering at all). General lesson: any Graydient workflow using the init_image_url/image1..imageN media-slot convention with an underlying node that returns a placeholder-on-empty rather than erroring needs an explicit filter step before batching multiple such slots together -- otherwise partially-filled slot sets silently degrade quality rather than erroring, which is much harder to notice.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ hunyuanworld-mirror-v1 model repo id fallback fix (confirmed live)
* **Platform Failure**: `concept_mapping` is confirmed best-effort, not guaranteed -- a model pre-staged on one Graydient machine class is not available if the job lands on a different class. `LoadHunyuanWorldMirrorModel`'s `_resolve_model_path()` falls through to treating the `model_name` widget value as a live HuggingFace Hub repo id whenever the local pre-staged file isn't found. The widget had been set to the bare string `"HunyuanWorld-Mirror"` (not a valid repo id) -- reproduced live locally: `huggingface_hub.errors.RepositoryNotFoundError: 404` for `https://huggingface.co/HunyuanWorld-Mirror/resolve/main/model.safetensors`.
* **The Fix, confirmed working live**: changed the widget to `"tencent/HunyuanWorld-Mirror"` (the real repo id). Local-path resolution is unaffected (its final candidate is a fixed filename regardless of `model_name`); the fallback path now also succeeds instead of hard-crashing. Confirmed via a real local ComfyUI repro: HEAD requests against `config.json` and `model.safetensors` both resolved (200/302) instead of 404ing.
* **Rule**: Any `model_name`-style widget that can fall through to a live HF Hub download must be a real, valid `<org>/<repo>` id -- never a bare model name, even if a local/pre-staged path is expected to cover it in the common case. `concept_mapping`'s non-guarantee means the fallback path WILL be exercised in production sooner or later.


### ⚠️ hunyuanworld-mirror-v1 gsplat import-time dependency (confirmed live)
* **Platform Failure**: An earlier assumption ("gsplat is declared but never called, so its JIT-CUDA-compile should never trigger") was wrong at the import level, not just the compile level. `worldmirror.py` imports `GaussianSplatRenderer` at module scope, which imports `gsplat.rendering.rasterization` at module scope -- so merely loading the model (not calling the rasterization function) requires a working `gsplat` import. Reproduced live locally on a 6GB GTX 1660 Ti without `gsplat` installed: model loading failed with a misleading generic "WorldMirror class not found" error masking the real `ModuleNotFoundError` underneath.
* **The Fix**: `gsplat` is already in this workflow's `requirements.pip`, so this specific failure shouldn't reproduce on Graydient itself -- this entry exists to correct the wrong assumption for future sessions, and as a confirmed live repro of gsplat installing/importing cleanly (~6s, no CUDA JIT-compile failure observed) once present.
* **Rule**: "This dependency's function is never called" does not mean the dependency is skippable -- check whether it's imported at module scope by anything in the actual call chain, not just whether the specific function using it gets invoked.


### ⚠️ hunyuanworld-mirror-v1 export-only-channel problem, solved with Meshsmuggler (confirmed live)
* **Platform Failure**: Graydient's hosted ComfyUI API has no `.ply`/`.glb`/output-file slot -- `HWMSavePointCloud`/`Save3DGaussians`/`SaveDepthMap`/`SaveCameraParams` only ever wrote into the ephemeral container's local disk, discarded when the job ends, regardless of whether the job "succeeded." This is the same platform constraint the TripoSG mesh pipelines already solved via Meshsmuggler for GLB.
* **The Fix, confirmed working live**: wired `MeshSmuggleGate` + `SmuggleMeshAsImage` (`UnlimitedEditing/Meshsmuggler`) onto `Save3DGaussians`'s `filepath` output, encoding the Gaussian-splat PLY as one or more lossless PNGs returned through the normal image channel. `SmuggleMeshAsImage` is binary-format-agnostic (just reads whatever bytes are at the given path) despite the mesh/glb-specific naming -- confirmed working unchanged for a PLY. Confirmed end-to-end on a real render: decoded PNG -> byte-exact PLY (CRC-verified) -> correctly detected as a Gaussian splat -> converted to `.splat` -> rendered with correct structure in 3DGenStudio's Splat Viewer.
* **Rule**: any workflow whose real output isn't a native Graydient output type (image/video) needs Meshsmuggler-style PNG encoding to get anything back at all -- a job reporting `success` with no smuggling wired in will still return nothing usable.


### 🔁 RECURRING MISTAKE: inventing `imageN_url`/`<side>_image_url`-style field names for the numbered image slots

* **Pattern, seen 4+ times across sessions/workflows now** (hunyuanworld-mirror-v1 round 3
  below is one instance; recurred again 2026-09-02 in `gen_hy3d_mv_shape_v1.py` and
  `gen_hy3d21_mv_texture_v1.py`, where the extra view-image slots were written as
  `right_image_url`/`back_image_url`/`left_image_url`): a session invents a descriptive,
  URL-suffixed `local_field` name for one of Graydient's numbered image slots, reasoning by
  analogy from the `init_image_url`/`_filename`/`_bool` media-triplet pattern, or just because
  a descriptive name reads better in a field-mapping table. **Graydient does not accept it.**
  Only bare `image1`..`image9` (and `video1..9`, `audio1..9`) exist as real numbered slots.
* **Why it keeps recurring**: an older memory ("Graydient's `field_mapping` `local_field` is
  just a transport label, not a fixed vocabulary — any string name works") is true for the
  *node_input_name* side of the mapping but was over-generalized to *local_field* too, which
  it is not: the numbered image/video/audio slots ARE a fixed, closed vocabulary on
  Graydient's side, unlike `slot1`/`slot2` which really are arbitrary. A field name that
  merely *sounds* plausible (`right_image_url`) and lints clean (the JSON schema doesn't know
  Graydient's real slot vocabulary) gives false confidence.
* **The Fix**: for any 2nd/3rd/... image input beyond the first (which uses the real
  `init_image_url`/`init_image_filename`/`init_image_bool` triplet), map `local_field` to
  bare `image1`, `image2`, `image3`, ... in submission order — never invent a suffixed or
  side-descriptive name. Put the descriptive meaning in `help_text` instead (e.g.
  `local_field: "image1"`, `help_text: "right view URL"`), not in the field name itself.
* **Also remember**: per the round-4 entry below, these bare numbered slots can arrive as a
  Graydient-staged local filename rather than a raw URL — the consuming node needs the
  local-file fallback (`Hy3DLoadImageFromURL` in `UnlimitedEditing/ComfyUI-Hunyuan3D` already
  has this), not just a URL fetch.
* **Rule**: before naming a `local_field` for anything beyond the first image/video/audio
  input, check this entry first — do not re-derive by analogy from the `init_*` triplet
  pattern, which does not extend to the numbered slots.


### ⚠️ hunyuanworld-mirror-v1 image1..image9 field vocabulary correction, round 3 (confirmed live)
* **Platform Failure**: A same-session attempt to fix a different bug (see the round-4 filename-fallback entry below) briefly renamed the numbered slots to `image1_url`..`image9_url`, reasoning from `GRAYDIENT-COMPLETE-REFERENCE.md`'s documented "media triplet" pattern (`init_image_bool`/`_filename`/`_url`) applying equally to the numbered slots. **The user corrected this directly**: `imageN_url` is not a field Graydient accepts at all -- only bare `imageN`. That doc's own table already flagged itself as unconfirmed on this exact point ("not yet job-confirmed which of a media triplet's fields actually gets populated for a given submission path").
* **The Fix**: reverted to bare `image1`..`image9` (this workflow's original, correct field names all along). The actual bug this session was chasing (see next entry) was never in the field name -- it was that Graydient's behavior for the bare numbered slots is unlike `init_image_url`'s real-URL passthrough, and needed a node-level fix instead.
* **Rule**: when a doc explicitly flags a specific detail as unconfirmed, do not silently treat an inference built on that detail as settled -- and a direct user correction from live platform experience outranks a documented-as-uncertain reference every time.


### ⚠️ hunyuanworld-mirror-v1 image1..image9 arrive as staged filenames, not URLs (confirmed live)
* **Platform Failure**: Unlike `init_image_url` (confirmed real URL passthrough), Graydient's numbered `image1`..`image9` slots do NOT pass the submitted URL through to the mapped node. Confirmed via a real job traceback: submitting a real URL to `image6` produced `Invalid URL 'image6__4aa48107e2f2a30c7ace932d0988c895.png': No scheme supplied` inside `Hy3DLoadImageFromURL` -- Graydient downloaded the URL server-side itself and handed the node a generated filename already staged into ComfyUI's `input/` directory instead.
* **The Fix, confirmed working live**: added a local-file fallback to `Hy3DLoadImageFromURL` (`UnlimitedEditing/ComfyUI-Hunyuan3D`) -- if the incoming value isn't an `http(s)://` URL, read it from `folder_paths.get_input_directory()` instead of attempting to fetch it. Confirmed live: a subsequent job with 8 numbered-slot images progressed past every image-loading node with no error (next failure was the unrelated mismatched-resolution bug in `Hy3DBatchImagesSkippingBlanks`, a real step further into the graph).
* **Rule**: don't assume every Graydient media field_mapping slot behaves like `init_image_url`. The numbered `imageN`/`videoN`/`audioN` slots may resolve to a Graydient-staged local filename rather than a raw URL passthrough -- any node consuming one of these needs to handle both forms, the same defensive pattern `graydient-cli`'s own `SourceMedia` type already uses for the `init_*` triplet.


### ⚠️ hunyuanworld-mirror-v1 scalar-first/scalar-last quaternion mismatch -- the actual root cause of "wildly inaccurate, even on a single image" (confirmed live, 2026-09-02)
* **Platform Failure**: every one of the fixes above (model repo id, blank-frame filtering, PLY encoding, gsplat import, Meshsmuggler export, image-slot field handling) still left reconstructions looking like an amorphous streaky blob -- no coherent geometry at all, on either multi-image or single-image input, with real (non-synthetic) photos. The user pushed back hard on the working theory ("sample quality") after comparing directly against Tencent's own official demo (huggingface.co/spaces/tencent/HunyuanWorld-Mirror) and judging our output "wildly inaccurate... even on a single image" compared to it.
* **Root cause, found by diffing the vendored model source against the official Space file-by-file**: `cedarconnor/ComfyUI-HunyuanWorld-Mirror`'s `src/models/utils/rotation.py` is a from-scratch reimplementation of `quat_to_rotmat`/`rotmat_to_quat` using **scalar-first (w,x,y,z)** quaternion component order. Tencent's actual official demo's `src/models/utils/rotation.py` (fetched directly via `curl` from the HF Space, not assumed) explicitly documents **scalar-last (x,y,z,w)** in its own docstring ("Quaternion Order: XYZW or say ijkr, scalar-last") -- confirmed identical to the file's real content, not a paraphrase. `camera_utils.py`, which calls these two functions, is byte-identical between our fork and official (confirmed via `diff -w`) -- so it was written assuming the OFFICIAL (scalar-last) convention, but our fork's `rotation.py` silently gave it the opposite one.
* **Why this corrupts everything, not just multi-view**: `worldmirror.py`'s `forward()` calls `self.cam_head(token_list)` -> `transform_camera_vector()` -> `vector_to_camera_matrices()` -> `quat_to_rotmat()` in the **default, no-prior inference path** (lines ~176-181) -- this runs on every single job, single image included, since the model always predicts+decodes its own camera pose even for one frame. The pretrained `cam_head` weights were trained to output quaternion components in the official scalar-last order; our fork's matrix-conversion formula read every channel's meaning backwards, producing a wrong rotation matrix for every predicted camera pose, on every job, always. Camera pose is what places every point/Gaussian into world space -- get it wrong and you get exactly the kind of streaky, exploded, non-coherent geometry seen throughout this whole workflow's history, independent of image count, camera motion, or precision.
* **The Fix, confirmed working live**: replaced `quat_to_rotmat`/`rotmat_to_quat` in `rotation.py` with Tencent's official implementation verbatim (same function names/signatures -- `camera_utils.py` and every other call site needed zero changes). Verified three ways: (1) numerically against `scipy.spatial.transform.Rotation` as an independent reference implementation (5/5 random rotations matched exactly, both directions); (2) a raw `matplotlib` scatter plot of a real render's PLY vertex data, colored from the file's own RGB fields, with zero dependency on this project's own viewer/conversion code -- went from an unrecognizable streaky blob to a coherent solid object with legible panel edges and readable label text, using the exact same 4 real input photos before/after; (3) confirmed again on a real Graydient job with real photos, both multi-image (still-image set) and single-image (the hardest case -- zero parallax), both producing coherent recognizable geometry where before there was only noise.
* **Rule**: when forking/reimplementing a pretrained model's supporting math (rotation/quaternion conversions, coordinate frame transforms, normalization constants) rather than vendoring it byte-for-byte, the network's own learned weights encode a SPECIFIC convention that must match exactly -- a self-consistent-looking reimplementation (round-trips correctly through its own encode/decode pair) can still be completely wrong relative to what the pretrained weights actually expect, and nothing about local round-trip correctness will reveal the mismatch. When a wrapper's output is inexplicably degraded even in the simplest case (single image, no multi-view compounding) despite every export/preprocessing-level fix checking out, diff the wrapper's vendored model source against the actual upstream official repo file-by-file (not just the demo glue code) before concluding the input data or model itself is the limiting factor.


### ⚠️ hunyuanimage3-lowvram-t2i
* **Platform Failure**: 80B MoE model, HunyuanImage-3.0-NF4-v2 via EricRollei/Comfy_HunyuanImage3, HunyuanUnifiedV2 node. Confirmed non-viable on 24GB (RTX 4090) tier: with correct block-swap loading (loads to CPU first via CleanModelLoader, not the broken README-recommended NF4-LowVRAM+/LowVRAMBudget pair which forces full-GPU load), only 1 of 32 transformer blocks fits resident on GPU regardless of tuning (15GB non-block + 13GB inference + 2GB reserve leaves ~0GB of the 22.6GB free for blocks). Per-step cost of streaming ~31 blocks over PCIe measured at 25-100s/step, far exceeding Graydient's job budget even at 10 steps (recorded here as ~380-400s; the real limit is ~180 s of ComfyUI run time, see KI-005). guidance_scale cannot be lowered to reduce cost: prepare_model_inputs hardcodes cfg_factor=2 for gen_image mode regardless of guidance_scale, so text-context/KV-cache is always batch=2 -- guidance_scale=1.0 only crashes (scatter_ batch mismatch), no compute saving exists. Also hit and fixed three unrelated platform-level pip bugs along the way (all now documented in gen_hunyuanimage3_lowvram_t2i.py): (1) Graydient concatenates requirements.pip entries into an UNQUOTED shell command, so any '>' or '<' in a version constraint (e.g. 'transformers>=4.47.0,<5.0') gets parsed as shell redirection instead of a pip constraint and silently no-ops -- use exact '==' pins only; (2) transformers==4.57.3 pin then conflicts with a later unpinned huggingface_hub install pulling 1.x (transformers 4.x needs <1.0) -- pin huggingface_hub explicitly and install it LAST; (3) unpinned diffusers resolves to a version needing huggingface_hub>=1.23.0, conflicting again -- diffusers must be pinned <=0.39.0 to stay in the compatible window. Would need either a 48GB+ card (fits enough blocks to avoid per-step PCIe streaming) or an upstream fix to the model's own vendored gen_image cfg_factor hardcoding. Revisit if a Graydient machine class with more VRAM becomes available, or if EricRollei's repo ships a real low-VRAM-without-full-swap path.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ krea2-360-sampler-test
* **Platform Failure**: Tested dpmpp_2m/karras and uni_pc/normal against euler/simple baseline to fix residual grain/noise in flat regions of krea2_turbo (CFG-distilled) equirectangular panorama outpaint, 8 steps, cfg=1, same seed/LoRA(0.3)/1536x768 otherwise. Result: euler/simple (baseline) stayed cleanest and most faithful to source composition. dpmpp_2m/karras made the grain dramatically worse (heavy moire noise). uni_pc/normal produced blocky pixelation AND broke spatial composition (a stray disconnected 'inset' sub-scene appeared, unrelated to walking-around-the-scene continuity). Conclusion: higher-order multistep samplers and non-simple schedulers do not converge cleaner than euler/simple on this CFG-distilled turbo model at 8 steps -- likely a mismatch with the model's distillation trajectory. Do not retry sampler-swap as a grain fix on krea2_turbo. Remaining grain issue needs a different lever: post-process denoise/upscale-downscale pass, or a light low-denoise refiner pass, not sampler/scheduler choice.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ h3-skillsmith-voice-v1
* **Platform Failure**: SaveText output never delivered (job showed 'Prompt executed' + empty node_errors, then outer harness timed_out at 305.87s with no output collected). Root cause per catalog's own Meshsmuggler rule: only image/video are native Graydient output types -- SaveText/.txt/.md is not, regardless of file extension (tried .md then .txt, neither helped, as expected once the rule is applied). Fix: route output through the response_card/lyrics_card monospace text-card IMAGE output (already exposed by HFTextGenerate/TranscribeAudioFromURL) via SaveImage instead of SaveText -- native output type, same pattern as the original h3-voice-prompt-v1's fallback card, which this workflow had dropped. Combined with splitting generation into 3 shorter LLM calls (Purpose / Archetypes+Phrasebank+Craftrules / Examples) so each resulting card stays legible instead of one long unreadable text wall.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ zoomout-krea2 (R19832964)
* **Platform Failure**: Not a workflow bug -- all 4 model assets resolved fine (3 exists, AnyPaint LoRA fetched correctly). Job hung 1933s (this was the ~1800s install-stuck limit in the uncounted startup phase, not the ~180 s run-time budget) with WorkflowInstallStuckException: 'stuck in download_comfyui > 1800s' on machine tls-pro-ny4-g3 -- Graydient's own base-ComfyUI install phase, not our custom-node repos. Orchestrator recursed find_project/start_project ~100x against the same stuck state instead of failing fast or rerouting. Fix: resubmit, should land on a healthy machine.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ edit-krea2-chain empty/non-matching mask prompt
* **Platform Failure**: Krea2AnyPaintPrepare (alexw5702-afk/krea2-anypaint, anypaint_helpers.py:99) hard-raises ValueError('the generated mask has no white pixels') on ANY all-zero generated_mask -- confirmed live, job R19833174, comfy execution error. This breaks the 'leave a stage's mask prompt empty to skip it' design in gen_krea2_anypaint_textmask_chain3.py: an empty or non-matching SAM3 mask prompt crashes the whole job rather than no-op passing the image through. Also affects any Krea2AnyPaintPrepare use where generated_mask could end up all-zero (e.g. zero padding + no mask + no border). Fix: never leave a running stage's mask prompt empty; it must describe something SAM3 can actually find in the CURRENT (possibly already-edited) image. No supported 'skip stage' mechanism exists yet -- use gen_krea2_anypaint_textmask_outpaint.py for single-edit jobs instead.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ auk-tts-v1-node-path
* **Platform Failure**: Confirmed live (R19915983): cloning github.com/Tencent-Hunyuan/AuK to custom_nodes/AuK/ fails to import -- FileNotFoundError, no __init__.py at repo root. Real node pack is nested at comfyui/ComfyUI-AuK/. requirements.github must point at a mirror/fork of just that subtree, not the upstream repo URL.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ auk-tts-v2-pep508-pip-syntax
* **Platform Failure**: Confirmed live (R19920674): requirements.pip entry 'auk @ git+https://.../AuK.git --no-deps' produced ModuleNotFoundError: No module named 'auk' -- node-path fix from the prior bury worked (mirror imported), but the pip install itself silently failed. Root cause, reproduced locally: Graydient concatenates each requirements.pip entry unquoted into 'pip install <entry>'; PEP 508's 'name @ url' direct-reference syntax needs the whole spec as ONE shell token (normally via quoting) -- unquoted, the shell splits it into 'auk', '@', 'git+URL' as three argv args, and pip errors on the bare '@' ('Invalid requirement: @: Expected package name...'). Fix: drop the 'name @ ' prefix and use the bare git+URL form instead (pip installs it under the package's own declared name from pyproject.toml/setup.py automatically) -- confirmed working via 'pip install git+URL --no-deps --dry-run' locally (Would install auk-0.1.0). General rule: never use PEP 508 'name @ url' syntax in a Graydient requirements.pip entry -- use bare 'git+URL' (optionally with trailing flags like --no-deps, which ARE safe since pip already expects those as separate space-separated argv tokens).
* **Rule**: Avoid this pattern in future builds.


### ⚠️ auk-tts-v3-load-audio-any-required
* **Platform Failure**: Confirmed live (R19923543): with the node-path and pip-syntax fixes applied, gen_auk_tts.py's instruct-TTS path (init_audio deliberately left empty) failed at 'Load Reference Audio' -- LoadAudioAny (unlimitededting-comfy-audio-utils) always raises RuntimeError when all three audio_source*/filename inputs are empty, by design. Correct for every other caller in this project where reference audio is genuinely required (gen_ltx2.5_i2v.py, gen_auk_edit.py), wrong for a workflow whose downstream node has a real optional AUDIO input (AuKGenerateEdit.input_audio, which explicitly handles None). Fix: added a purely additive LoadAudioAnyOptional node class / 'Load Audio Any Optional' registration in the same repo (does not modify LoadAudioAny itself, so no other deployed workflow is affected) that returns (None,) instead of raising on all-empty. Rule: when wiring 'Load Audio Any' upstream of a genuinely-optional AUDIO input, use 'Load Audio Any Optional' instead -- the strict version will hard-fail any request that omits the reference/source clip, even when the downstream node is designed to accept that.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ auk-help-text-brace-placeholders
* **Platform Failure**: Confirmed live (user report, tts-auk job): field_mapping help_text used {voice description}/{text} bracket notation to mean 'replace this whole span', but a real submitted prompt kept the literal curly braces around the filled-in content (e.g. description: "{a deep grumbly voice...}"). AuK has no brace-stripping/templating step -- it reads the braces as literal characters in the instruction sentence, producing garbled output (voice description spoken aloud, bad grammar, wrong fit) rather than erroring, so the failure mode is silent quality degradation, not a crash. Fixed in gen_auk_tts.py/gen_auk_edit.py: field_mapping help_text and description strings now give only concrete filled worked examples (real words, no { } or < > anywhere) instead of bracket/placeholder notation, with an explicit 'do not type brackets' warning. General rule: never use {}/<> placeholder notation in any Graydient field_mapping help_text meant to guide a free-text prompt field for a model with no templating layer of its own -- give a complete worked example instead, since users copy help text structure literally and the model has no way to know a bracket was meant to be replaced rather than spoken/rendered.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ Qwen Image 2.1 VAE decodes RGBA -> TextGenerate/Qwen3.5 vision crash
* **Platform Failure**: The Qwen Image 2.1 VAE (qwen_image_2.1_vae_bf16) decodes to 4-channel RGBA images (comfy/sd.py: 'Qwen Image 2.1 VAE ... RGBA'). Feeding a decoded image into TextGenerate with a Qwen3.5 VL model (e.g. Qwen-Image-2.1 PE-I2I) crashes in the vision patch embed: "shape '[-1, 3, 2, 16, 16]' is invalid for input of size N" (N divisible by 4*2*16*16). Fix: flatten first with SplitImageWithAlpha -> MaskToImage/InvertMask -> ImageCompositeMasked onto white (all core). TextEncodeQwenImage21 itself accepts RGBA refs fine. Hit in gen_pixel_turnaround_qwen21 v6 'fix' branch, fixed in v7.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ VHS pip deps downgrade numpy -> ComfyUI startup crash
* **Platform Failure**: sprite-pixart v13 (2026-09-23): adding requirements.pip [opencv-python, imageio-ffmpeg] + github Kosinkadink/ComfyUI-VideoHelperSuite to a workflow left numpy 1.26.4 in the venv under a SciPy that needs numpy>=2. ComfyUI died at import before any node ran: comfy/audio.py -> scipy.signal -> scipy.sparse -> AttributeError: module 'numpy' has no attribute 'long'. Older VHS workflows listed the same pip deps, so treat VHS + those pip entries as unsafe on the current Graydient image. For GIF/animated output, use a Pillow-only writer (UnlimitedEditing/ComfyUI-SpriteSheetPack SpritePackSaveGIF, reports under ui 'gifs' like VHS) and flag supports_img2vid + supports_img2img. Fixed in v14 with pip: [].
* **Rule**: Avoid this pattern in future builds.


### ⚠️ Custom save nodes: Graydient collects no files, job hangs to timeout
* **Platform Failure**: sprite-pixart v14/v15 (2026-09-23): outputs went through custom output nodes (SpritePackSaveImage writing PNGs with a standard ui images entry; SpritePackSaveGIF with a VHS-style ui gifs entry). ComfyUI logged 'Prompt executed in 100.81 seconds', but Graydient's result had files=[] and the job sat until timed_out (332 s). Graydient's collector evidently recognises outputs only from known stock save node types (SaveImage, VHS_VideoCombine, SaveVideo, SaveAnimatedWEBP...). Always end outputs in a stock save node. To switch an output off from a slot, gate its INPUT (e.g. SpritePackGate -> empty batch -> stock SaveImage saves nothing) rather than using a custom save node.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ CORRECTION: custom save nodes ARE collected; hang was likely img2vid + .gif
* **Platform Failure**: Supersedes the entry 'Custom save nodes: Graydient collects no files'. scene-3d v15 (working) returns PNGs from a CUSTOM output node (Meshsmuggler SmuggleMeshAsImage, ui images entries identical to SpritePackSaveImage) plus VHS mp4 videos, with supports_img2vid=false and no stock SaveImage. sprite-pixart v14/v15 hung (prompt executed, files=[], timed out) with supports_img2vid=TRUE and the only animated output a .gif under ui 'gifs' from a custom node. Best-supported explanation: with img2vid on, Graydient waits for a real video file (.mp4) and a .gif does not satisfy it. Rule: if a workflow sets supports_img2vid, make sure it emits an actual .mp4 (core CreateVideo -> SaveVideo, or VHS video/h264-mp4); custom image save nodes are fine.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ Platform: WorkflowInstallStuckException stuck in download_comfyui
* **Platform Failure**: Not a workflow bug. sprite-pixart (Graydient project 3768-18, 2026-09-23, machine tls-pro-ny4-g0): Graydient's launcher (/datapool/stablebot/utils_comfyui.py find_project/start_project loop) raised WorkflowInstallStuckException 'stuck in download_comfyui > 1800s'. ComfyUI never started, logs weren't collected, peak VRAM 0, and all concept_mapping assets showed 'exists'. Same class of Graydient infra fault as the earlier localhost:33666 launcher errors: retry, and report to Graydient support if it repeats.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ ltx25-upscale-ref-v1
* **Platform Failure**: First Graydient run (tls-pro-ny4-g0) never reached inference -- stuck 1800s in download_comfyui install phase (WorkflowInstallStuckException), all model/lora assets already staged fine (exists/mirror-fetched) before the hang. Looks like an infra-level stall (repo clone or pip install hang), not a workflow-graph problem -- github requirements are identical to the already-working gen_ltx25_upscale.py. Retry before assuming the graph itself is broken.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ joyaiecho-ltx25-v1
* **Platform Failure**: R20103368 on tls-pro-ny4-g2 (RTX 4090 24GB, not a 5090): job failed at prompt VALIDATION, before any inference -- LoadImage node 1 got image='' (empty string), ComfyUI's own image-exists check ('Invalid image file: ') rejected it. Everything upstream (ComfyUI 0.38.0 startup, pip installs, custom node loads -- ComfyUI-LTXVideo, unlimitededting-comfy-audio-utils, comfy-audio-duration -- all loaded clean, comfy-kitchen/aimdo DynamicVRAM detected fine) succeeded. Root cause looks like the test submission simply didn't include an image1 value, not a workflow-graph bug -- field_mapping for image1 (node 1, input 'image', index 0) matches the already-proven gen_ltx2.5_i2v.py pattern exactly. Retry with a real image1 URL/filename before assuming the graph itself is broken. Also note for future budget checks: this project's ny4-g pool can hand out RTX 4090 24GB instances, not only 5090s -- the int8 UNET tier (21.5GB, card-recommended for 32GB+ per the JoyAI-Echo model card) relies on comfy-aimdo DynamicVRAM RAM-overflow (confirmed enabled in this job's logs) to fit on a 24GB card; never independently verified whether it actually completes inference at that VRAM level since the job never got past validation.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ pinkcherry-ltx25: silent no-start = submit-time HTTP 500 (not a graph/repo problem)
* **Platform Failure**: Confirmed live 2026-10-02 via graydient-cli (D:/ForgeExpress/cli, 'q' and 'workflows show'): Telegram shows NOTHING when Graydient answers the render submit with HTTP 500 'Interal Server Error', which happens before any repo clone/pip/startup. A working sibling (redgraft-ltx25) queued fine through the same CLI; all four github requirements were reachable (HTTP 200), so repos were not it. The pinkcherry-ltx25 config 500'd until regenerated with: filled type:url concept field_mapping ('<id>-<default node title>.<idx>-<input>', e.g. '439-Load Diffusion Model.0-unet_name'), default loader node titles, field-mapping default/min/max stored as strings (98% of live workflows), ASCII-only description/help (an em-dash description came back empty), split_prompt_pos_neg true, prompt_positive/prompt_negative local fields, and ComfyUI-LTXVideo dropped from requirements. Changed together, not individually isolated. Diagnose with: node dist/index.js q '/wf /run:<slug> test' --json --timeout 1 (500 JSON vs [render_queued]) and workflows show <slug> --json diffed against a live sibling.
* **Rule**: Avoid this pattern in future builds.


### ⚠️ restoring a workflow under an existing slug leaves a DUPLICATE; the slug resolves to the OLD one
* **Platform Failure**: Confirmed live 2026-10-02 (h3 t2i): 'workflows list' showed two workflows with slug image-h3 (ids 3670 old v5, 3837 new); '/run:image-h3' and 'workflows show image-h3' resolved to the OLD one (empty concept field_mapping, image1 field), so every submit returned HTTP 500 and the new restore was never reached. Renaming the new restore to images-h3 made it render immediately. Other duplicate slugs seen: animateturbo-h3 (3385/3414), audio-miso (3148/3150), paint-huny3d (3182/3184). Check for slug collisions FIRST when a freshly restored workflow 'does nothing'. (pinkcherry-ltx25 restored repeatedly without duplicating, version bumped to 7, so duplication depends on the restore path -- always re-list afterwards.)
* **Rule**: Avoid this pattern in future builds.

## 19. Some pip Entries Were Absent From the Job's COMMAND: `>=`, `[extras]`, `@commit` (observed 2026-10-04, R20163116)

* **Failure Mode**: `worldstereo-light-test` v1 listed `diffusers>=0.36.0`, `transformers>=5.2.0`, `optimum-quanto>=0.2.4`, `imageio[ffmpeg]` and `git+https://github.com/microsoft/MoGe.git@<sha>` in `requirements.pip`. The job's printed `COMMAND:` contained NONE of them -- only the bare-name entries survived as `pip install <name>;` lines. No error, no warning; if the package really isn't installed the failure shows up later as a missing-module error inside a node. **Cross-reference**: `GRAYDIENT-COMPLETE-REFERENCE.md` §6 ("pip requirements rules") already says Graydient *strips* `[]`, `>=`, `<=`, `~=` and to use plain package names — so this is a known platform behaviour, though the observed COMMAND omitted the whole entry rather than just the specifier. **Scope caveat**: 100+ older workflows in this project use `>=`, `[extras]` or `name @ url` entries and some ran fine, so this is one observed job, not a proven universal rule; the cause (drop vs. sanitise vs. something about this job) was not isolated.
* **The Rule**: for new builds prefer bare names, `==` pins, or a bare URL (these demonstrably survived). For a pinned git commit use GitHub's commit-zip URL (`https://github.com/<org>/<repo>/archive/<sha>.zip --no-deps`, confirmed installed live) rather than `git+...@sha`. Always read the job's `COMMAND:` block after the first run and diff it against `requirements.pip`. The linter emits an INFO (`PIP_SPEC_MAYBE_DROPPED`), not a warning, for that reason.

## 20. The Venv Ships a Broken `torchao`; Pinning `diffusers==0.36.0` Then Kills Every Node That Imports diffusers (confirmed 2026-10-04, R20163372)

* **Failure Mode**: the base venv has a `torchao` whose `.so` files don't load (`_C_mxfp8.cpython-310...so`, `_C_cutlass_90a.abi3.so`; harmless warnings on their own). Adding `diffusers==0.36.0` to pip made `diffusers.quantizers.torchao` raise on `NF4Tensor`, and 0.36.0's own error path then hit `NameError: name 'logger' is not defined`, so ALL of diffusers failed to import. `ComfyUI-TripoSG` imports diffusers at load time, so the whole pack (and `LoadImageFromURL` with it) vanished: "Node 'Load Image From URL' not found".
* **The Rule**: do not re-pin diffusers on Graydient; the venv's own diffusers imports fine (confirmed R20163429/R4y5zAD, full run). A pack-level IMPORT FAILED line in the log's "Import times" section is the tell. Don't add `torchao` either.

## 21. HY-World 2.0 WorldStereo Light on Graydient: works, ~110 s (confirmed live 2026-10-04)

* **Reference implementation**: `gen_worldstereo_light_test.py` -> `GraydientWorkflow-worldstereo-light-test-v1.json` (AHEKOT/ComfyUI_HYWorld2 + MIUProject/VNCCS_WorldStereoLight Memory DMD INT4). Chain: LoadImageFromURL -> VNCCS_LoadWorldStereoLightModel -> VNCCS_CameraTrajectoryBuilder -> VNCCS_WorldStereoGenerate -> CreateVideo -> SaveVideo. Single image in, 9 frames out.
* **Measured (RTX 5090, tls-pro-ny1-g0)**: pipeline load ~9s (int4 streams in ~2s), 4 DMD steps = 31s at 768x448 / 33 conditioning frames (first step 20.8s warmup, then ~3.5-4s), job total 109.8s. Weights pre-staged via concept_mapping (15.1GB; destinations in KI-008 §7); aux downloads (Wan2.1 aux 1.2GB, MoGe, config) took ~6-10s at runtime.
* **Stage 1 needs no compiled deps**: PyTorch3D is absent and unnecessary -- the node falls back to a torch point renderer and fallback camera presets (`circular` preset unavailable). gsplat is not needed for the WorldStereo stage. (**The WorldMirror V2 stage DOES need an importable gsplat just to load the model -- see section 22.**) (The runner image even ships the HYWorld gsplat fork, 1.5.3+hyworld.pt2110.cu128 on one machine class; on another it logs `module 'gsplat' has no attribute '__version__'` -- harmless here.)
* **Required pip, learned the hard way (R20163116 -> R20163429)**: `loguru`, `decord`, `matplotlib` are module-level imports in worldstereo/src/general_utils.py. MoGe must be the repo-pinned commit `0286b49...` AND utils3d commit `c5daf6f...` (that MoGe calls `utils3d.torch.*`; PyPI utils3d and a newer MoGe head call `utils3d.pt` -> "No module named 'utils3d.pt'"). Install both as commit-zip URLs `--no-deps` (see section 19).
* **Reconstruction stage CONFIRMED end to end (v1.2, `gen_worldstereo_recon.py` -> `GraydientWorkflow-worldstereo-recon-v1.json`, RTX 4090, tls-pro-ny3-g0)**: `Prompt executed in 143.61 seconds`, output delivered. Chain: WorldStereo Light (7 frames @576x320, 4 steps = 28s, first step 20.9s warm-up then ~2.5s each) -> `VNCCS_WorldMirrorV2_3D` (7 images @ 434px, depth_only) -> 901k raw dense splats -> capped to 250k -> `VNCCS_SavePLY` -> Meshsmuggler (17MB gzip PLY -> 1 PNG, 1406x1405). Started ComfyUI at 10:43:37 and finished ~160s later, ~20s inside the 180s limit.
* **v2 CONFIRMED live (2026-10-04, workflow3848 v5, `gen_worldstereo_recon_v2.py`)**: delivered 2 PNG chunks (8.4MB + 12.6MB) = a 61,282,560-byte PLY of **901,208 splats = 7 views x 266 x 484, no cap** (`splat_upsample_max_points=0`), named `..._gaussians_upright.ply` (the glue repo `UnlimitedEditing/ComfyUI-HYWorld2Glue` cloned and `HYW2FlipPLY` ran). It opens upright in 3DGenStudio and is dense and sharp. The stopwatch log lines have not been read yet (only the outputs were shared).
* **What the native PLY shows (measured offline)**: rows are in per-view raster order (7 x 266 x 484), scales are isotropic (exp(scale) 0.003-0.006), opacity 0.9, all points within 4.8 units. (a) ~1.2% of splats are mixed-depth 'flying pixels' (a 3D step to both neighbours >10x the local step); a quick offline filter removed them without a clearly visible change. (b) **Cross-view misalignment is real**: for adjacent views the median nearest-surface distance is 3.5-7.5 within-view pixel spacings (worst: view 0 -> 1 at 7.5), where coincident surfaces would be ~1 -- consistent with the 'layers don't align' observation. Likely cause (UNTESTED): the dense splats are backprojected from WorldStereo's COMMANDED poses (ICP-scaled) while the generated frames only roughly follow them; test `slot9 = predicted`. (c) Long thin streaks seen after orbiting are a viewer artifact (3DGenStudio's gaussian-splats-3d viewer, camera near splats), not data: they vanish when zoomed out and the file has no outliers/NaNs/oversized splats.
* **slot8 A/B live (2026-10-04, workflow3848 v7, `slot8 = 1` = predicted cameras; the PLY filename `..._scene_pred_...` proves the numeric slot -> lazy ComfySwitchNode branch selection WORKS on Graydient)**: predicted poses improve the *measured* cross-view agreement (adjacent-view nearest-surface mean 5.03 -> 3.48 pixel spacings, each scene normalised by its own spacing; scene scale differs ~0.6x) and stop the last views collapsing into a flat sheet (commanded view 6 spans only 0.22 in depth), BUT the face looks worse (doubled lips/teeth): the video model's frames disagree about the face and predicted poses keep every view at a sensible depth, so the disagreement shows. Pose source is not the main problem.
* **Offline prototype that works (UNBUILT as a node)**: "frame 0 priority" -- keep every splat of view 0 (the real photo) and keep a splat from view k>0 only if, projected into view 0 (pinhole fitted from view 0's own grid, camera 0 assumed at identity), it does NOT land on a pixel whose depth already matches (|dz| < 4%). On the commanded-poses scene this keeps 252,693 of 901,208 splats (28%) and visibly cleans the face/hair/shoulder (no doubled features, far fewer net artifacts); on the predicted scene it keeps 349,270 (39%) and helps less (view 0's pinhole fit is looser, residual 0.021 vs 0.012). Side effect: a ~72% smaller PLY (fewer PNG chunks, faster pack). The PLY's rows are per-view raster order (V x H x W) so it can be done at the file level. Pictures: worldstereo_recon_outputs/compare_poses_and_frame0_priority.png.
* **v2.2 CONFIRMED live (2026-10-04, workflow3848 v8, `HYW2Frame0Priority` in the glue repo)**: delivered ONE PNG chunk (9.4MB) = `worldstereo_scene_00001_gaussians_f0_upright.ply`, 27,843,220 bytes = 409,453 of 901,208 splats (45%) -- so the new chain (switch -> frame-0 priority -> flip) ran on Graydient. It kept more than the offline prototype's 28% because this run's depth scale/frames differ (see next).
* **Run-to-run scene scale is arbitrary**: the same photo and settings gave depth 1.0-4.4 (v2.0) and 1.4-9.3 (v2.2) (WorldMirror's ICP depth scale varies per run), while splat sigma stays ~0.004. Measured on the live v2.2 file: **45% of splats have sigma < 0.5 x nearest-neighbour spacing** (screen-door gaps in a true splat renderer), median ratio 0.63, and at depth > 3 the ratio is 0.35 (spacing 0.0146 vs sigma ~0.004); the v2.0 scene was gap-free near the camera (ratio 1.65 at depth < 1.8). Cause: `depth_adaptive` grows splat size only x1..x2 over the scene's depth range while the pixel footprint grows ~6x. Fix applied in v2.3 (UNTESTED): `splat_upsample_scale_mode = footprint_adaptive` (size = grid-neighbour spacing clamped to [base, 3 x base] = [0.003, 0.009]). Possible follow-up: normalise the scene scale per run (e.g. view-0 median depth -> a fixed value) so splat sigmas, viewer framing and clamps are stable across runs.
* **v2.3 CONFIRMED live (2026-10-04, workflow3848 v9, `footprint_adaptive` splat sizing)**: `..._gaussians_f0_upright.ply`, ONE 6.0MB PNG, 295,479 splats (32.8% of 901,208), PLY 20.1MB. Measured gap risk (splat sigma / nearest-neighbour distance; >=0.5 is gap-free): **45% of splats below 0.5 in v2.2 (`depth_adaptive`) -> 3% in v2.3**; far background (depth > 3) ratio 0.35 -> 0.83; overall median 1.07, p10 0.69. Splat sigma is now min 0.003 / median 0.009 / max 0.009 (most splats sit on the 3 x base clamp), so the scene is solid but a little softer than v2.0's crisp (but gappy) look. In 3DGenStudio the scene renders solid, orbits with real parallax, single clean mouth (no doubling). All three live fixes now work together: native splats, frame-0 priority, footprint sizing. Not yet read from a log: stopwatch lines, `[HYW2Frame0Priority]` output, `Prompt executed in`.
* **TIMING FINALLY MEASURED (2026-10-04, workflow3848 v9 log, RTX 4090 tls-pro-ny7-g0; HYW2 stopwatch marks = seconds since the ComfyUI PROCESS started, the 180s clock)**: A image loaded 11.7 (this IS the whole ComfyUI startup) | B WorldStereo model ready 28.5 (+16.8) | **C WorldStereoGenerate done 129.1 (+100.6)** | D V2 model ready 142.3 (+13.2) | E V2 inference + 901,208 splats 142.6 (**+0.3**) | F-G PLY saved, frame-0 priority (0.1s), flip (0.0s) 143.1 | H PNG packed 146.2 (+3.0). `Prompt executed in 135.07 seconds`, so **146.2s total, ~34s inside the 180s limit.** The long-unexplained ~85s is inside WorldStereoGenerate: only the 4 DMD steps (25s; step 1 = 18s of one-time warm-up, then ~3s each) are denoising, the other ~75s is MoGe depth + T5/CLIP/VAE conditioning encode of 25 frames ('full_vae / full / full' modes chosen by 'auto') + fallback point render + VAE decode. WorldMirror V2 and everything after it cost ~17s combined (13s of that is loading the 5GB model). The Wan aux pre-staging worked (log: `Wan2.1-I2V-14B-480P aux files cached`, no download); MoGe still fetches (4s).
* **Both V2 branches always run**: the slot8 `ComfySwitchNode` is lazy, but `VNCCS_SavePLY` is an OUTPUT_NODE, so the unselected branch's V2 inference + SavePLY still executes (log shows both `splat_camera_source=camera_inputs` and `predicted` runs). It costs only ~0.4s today because V2 is cheap; it would matter if the branch were expensive.
* **Untested experiment prepared**: `HYW2_VARIANT=fastcond python gen_worldstereo_recon_v2.py` writes `GraydientWorkflow-worldstereo-recon-v2-fastcond.json` with latent_condition_mode=first_frame_only, render_vae_mode=keyframes, conditioning_frame_mode=keyframes (the node's own 'auto' only picks these at high resolution) to attack the ~75s; effect on both time and quality unknown.
* **How v1.2 got under budget (from v1.1's N = 168.65s, which was flagged timed_out and delivered nothing)**: length 9->7, V2 target_size 518->434, voxel prune off, 576x320 frames, splat cap 250k. Measured effect: N 168.65 -> 143.61s (-25s). Still unexplained: ~85s of pre-denoise / decode / V2 / export work that the log has no timestamps for.
* **In-prompt downloads on a cold machine cost ~10s** (WorldStereo config + 1.2GB Wan aux files ~6s + MoGe ~3s all happened inside the prompt on this machine). `concept_mapping` for them would move that out of the budget; not done (14 small files, size-checked by the loader). Output quality of the scene itself: see the user's review, not established here.

## 22. WorldMirror V2 Needs an Importable `gsplat` Just to LOAD; Machine Classes Differ on Whether One Exists (confirmed 2026-10-04, R20164458)

* **Failure Mode**: `worldstereo-recon-v1` on tls-pro-ny1-g0 (RTX 5090) died in 0.02 s at `VNCCS_LoadWorldMirrorV2Model` with `No module named 'gsplat.rendering'`. Call chain: `hyworld2/worldrecon/hyworldmirror/models/models/worldmirror.py` -> `from .rasterization import GaussianSplatRenderer` -> `rasterization.py` line 8 `from gsplat.rendering import rasterization` (module scope, unguarded). The guarded `GSPLAT_AVAILABLE` flag in `nodes/world_mirror_v2.py` only controls whether native Gaussian heads *run*; it does not protect the model import. The startup log had already warned: `Error loading gsplat: module 'gsplat' has no attribute '__version__'`.
* **Why it half-worked before**: `ComfyUI_HYWorld2` has a root-level `gsplat/` folder holding only Windows `.whl` files and no `__init__.py`; the pack inserts its root at the front of `sys.path`, so with no real gsplat in site-packages `import gsplat` resolves to that folder as an EMPTY namespace package (importable, no `__version__`, no `rendering`). A regular package in site-packages beats a namespace folder, so machines that already ship the HYWorld fork (g2 RTX 4090 and g3 logged `gsplat 1.5.3+hyworld.pt2110.cu128`) loaded V2 fine (R20164194), while g0 had none. Whether a job passes depends on which machine class it lands on.
* **The Fix (CONFIRMED live, R...v9oKd0, 4090: `gsplat library detected: Version 1.6.0+pt211cu128`, V2 loaded, full job succeeded)**: pin our own prebuilt wheel in `requirements.pip`: `https://github.com/UnlimitedEditing/gsplat/releases/download/v1.6.0%2Bpt211cu128/gsplat-1.6.0%2Bpt211cu128-cp312-cp312-linux_x86_64.whl --no-deps` (cp312 / torch 2.11 / cu128, URL verified 302->200). This replaces the preinstalled fork on machines that have it, which is fine because the default V2 path never rasterizes.
* **The Rule**: this repeats the lesson in the earlier `hunyuanworld-mirror-v1 gsplat import-time dependency` entry -- "this function is never called" does not mean the dependency is skippable; check module-scope imports in the actual load path. Before declaring a dependency unnecessary, grep for `^from <pkg>` / `^import <pkg>` along the whole import chain of the node being loaded, and do not infer availability from one machine's log: a different machine class can lack it.

## 23. Graydient Has Slots 1-8 Only, and Slots 4-8 Accept Numbers Only (stated by Jacob 2026-10-04)

* **Failure Mode (caught before a run)**: `gen_worldstereo_recon_v2.py` mapped `slot9` to a STRING/COMBO widget (`splat_camera_source`: `camera_inputs` | `predicted`) and `slot3` to `offload_mode`. The reference doc claimed all nine slots take strings; Jacob corrected it: **only slot1-slot3 take strings, slot4-slot8 are numeric**, and a follow-up correction: **there is no slot9 at all, slots go 1-8** (a mapping to slot9 is silently dead). In `gen_worldstereo_recon_v2.py` this cost one control: the PLY-flip toggle was dropped (always on) so the camera-source selector could take slot8. This also explains the earlier pixel-turnaround observation that typed strings in slot4 were rejected. (A default string in the field mapping may still work, but a user can't type a different one.)
* **The Fix**: make slot4+ numeric and select behaviour in the graph (max slot8). `PrimitiveInt` (slot) -> `ComfyMathExpression` `round(a) == 1` (BOOL = output slot 2) -> lazy `ComfySwitchNode`. For the recon workflow that means two V2 branches (commanded vs predicted cameras) with the switch on the saved-PLY path (STRING, the type already proven for this switch), and slots 4-7 mapped to BOTH branches (one slot may feed several nodes).
* **The Rule**: never put a string/COMBO widget on slot4-slot8 and never map slot9 or above (the linter now warns `SLOT_DOES_NOT_EXIST`); the linter now emits an INFO (`SLOT4_9_NON_NUMERIC_DEFAULT`) for non-numeric slot4-9 defaults. Not yet confirmed live: the new switch graph in v2.1.

## 24. A Node Title With "." (and "-") in a concept_mapping field_mapping String Kills the Job at Preparation; the CLI Never Reports It (confirmed 2026-10-07, ripple-ltx25)

* **Failure Mode**: `ripple-ltx25` v2 (`gen_ltx25_ripple.py`, workflow WFEmgY97) failed in the same minute it was submitted (log row `failure`, elapsed `--`, **Error details = a bare `ValueError`**, no message or traceback). The concept_mapping strings are `"<node_id>-<node title>.<index>-<input name>"`; node 10 was titled `Load LTX-2.5 Transformer`, so its string was `10-Load LTX-2.5 Transformer.0-unet_name`. **Only that title was changed** (to `Load Diffusion Model`, the title `gen_pinkcherry_ltx25.py` uses) and the identical submission then succeeded (v3, render `39yNVD`: elapsed 232.191 s incl. first-run staging, `Prompt executed in 37.36 seconds`).
* **What is and is not confirmed**: confirmed = the combination `-` + `.` in a title fails and a plain title works (single-variable before/after). NOT confirmed = which character is responsible. The `.` is the prime suspect (it is the string's own delimiter); `Load JoyAI-Echo DiT Model` (hyphen only) in `joyaiecho-t2voice-v1/v2` was never confirmed live either way. 156 titles across the existing `GraydientWorkflow-*.json` had neither character.
* **The Rule**: titles of any node referenced from a concept_mapping `field_mapping` / `weight_field_mapping` must not contain `.`; avoid `-` too. The linter now errors on a dot (`CONCEPT_MAPPING_TITLE_HAS_DOT`) and warns on a hyphen (`CONCEPT_MAPPING_TITLE_HAS_HYPHEN`). Node titles in the *field_mapping* list (`node_name`) are a different path and were fine (`Load Source Video (URL)` etc.).
* **Diagnosing it (no ComfyUI log exists for such a failure)**: (a) `graydient render` printed only `render_queued` + `rendering_started`, then **waited the full `--timeout 45` and exited `Error: This operation was aborted`** with no hash and no mp4 -- the CLI does NOT surface a platform-side failure, so do not wait on it; (b) the workflow's **Logs tab** (`graydient archive dump <id> --tab Logs`) shows the truth: status `failure`, `Error details`. Those `<details>` panels are collapsed in the dump text; open them with the `ArchiveSession` class (`page.getByText('Error details').click()`) or read the raw `<details><pre>` HTML. (c) **The "ComfyUI log" panel can belong to a different workflow**: it showed an `omni-eros-h3` MiniMax-H3 run on another machine, because no ComfyUI was ever started for the failed job. Check the machine/workflow name and the timestamps in the log before trusting it. On the *successful* run the same panel did show the real log (`ripple-ltx25-3864-3`, `got prompt` ... `Prompt executed in 37.36 seconds`).
* **Related confirmed facts from the same build**: `extract-frames` (`/run:extract-frames /slot1:0 --init-video <public https URL>`) returns frame 0 as a PNG with no local download; `--init-image <https URL>` of a previous render's S3 URL works where the CLI's temp-upload host is dead; a second media type goes via `/image1:URL1 --placeholder URL1=<url>` while the video uses `--init-video-url` (the `init_video_url` field) -- both arrived correctly.
* **Reference implementation**: `gen_ltx25_ripple.py` -> `GraydientWorkflow-ripple-ltx25-v1.json` (LTX Ripple FFAF IC-LoRA, WepeNerd). Edited-frame + source-video frames -> `ImageBatch` -> one `LTXAddVideoICLoRAGuide` (frame_idx 0, latent_downscale_factor literal 1.0) -> distilled 22B int8, 8 steps euler CFG 1 (`BasicScheduler simple`) with `LoraLoaderModelOnly` strength 1.35 -> `LTXVCropGuides` -> `VAEDecodeTiled` + `LTXVAudioVAEDecode` -> `CreateVideo` -> `SaveVideo`. **Measured (job 39yNVD)**: 768x448, 97 frames @ 24 fps (4.04 s), h264 + AAC, `Prompt executed in 37.36 seconds` -- far under the ~120 s planning target, so the default size and length have lots of headroom (the author runs 1152x768 / 129; untested here). Visual check by Claude of frames 0/48/96: the snow edit persisted through the clip with the source's camera push-in; Jacob has not yet judged motion fidelity. The ComfyUI-TripoSG `trimesh`/`cv2` import warnings in the log are harmless here (video loader stays active).

