# ComfyUI-MediaMetadata

Graydient/ComfyUI node that reads the media attached to a job and reports what
that file actually is — as a picture.

Takes the media Graydient hands the workflow (`init_video` / `init_image` /
`init_audio`, in either the `_url` or the `_filename` flavour), resolves it to a
real file, and extracts file-level metadata with `ffprobe` (containers, video
and audio streams) and PIL/EXIF (stills). Returns the report three ways:

| output | type | what it is |
|---|---|---|
| `report` | STRING | the human-readable metadata report |
| `report_json` | STRING | the same data as JSON (machine-readable) |
| `card` | IMAGE | the report rendered as a single PNG-style image |

For a video the card carries the full set: container format, duration, bit
rate, codec and profile, resolution, display aspect ratio, frame rate (avg and
real), total frame count, pixel format, bit depth, colour space/primaries/
transfer, field order, rotation, time base, per-stream tags (including
`creation_time`), the audio stream's codec/sample rate/channels/bit rate, file
size and modification time.

For an image it carries format, resolution, colour mode, frame count (animated
stills), DPI and the EXIF block — including `DateTimeOriginal`, make, model and
GPS. For audio it carries codec, sample rate, channels, layout, duration and
bit rate.

## Node: `MediaMetadataProbe`

| input | type | meaning |
|---|---|---|
| `video_url`, `video_filename` | STRING | `init_video_url` / `init_video_filename` |
| `image_url`, `image_filename` | STRING | `init_image_url` / `init_image_filename` |
| `audio_url`, `audio_filename` | STRING | `init_audio_url` / `init_audio_filename` |
| `caption` | STRING | optional title line on the card (map `prompt_positive` here) |
| `card_width`, `card_height` | INT | card size in px (0 = 1600x1000). The card grows taller if the report needs it |
| `include_thumbnail` | BOOLEAN | draw the first frame / the still in the card header |

## Reference resolution

Graydient hands over the same media in more than one shape depending on the
submission path, so every one of the six inputs is tried, in a fixed order, and
the first one that resolves wins:

1. a real `http(s)://` URL → downloaded;
2. a mangled Telegram file reference (every `:`/`/` stripped, e.g.
   `init_audio__httpsapi.telegram.orgfilebot…voicefile….oga`) → reconstructed
   with the known Telegram Bot API URL shape, then downloaded;
3. a bare filename → looked up in ComfyUI's `input/` directory first (that is
   where the platform stages uploads), then as a literal path.

Video is preferred over image over audio, because a job carries exactly one
media type through the `init_<type>_*` triplet.

## It does not raise

A Graydient job that throws costs real quota and tells the user nothing, so
every failure is reported instead: an unreachable URL, a missing file, a file
`ffprobe` cannot read, no media supplied at all — each one produces a card that
says exactly what went wrong. The node only fails if ComfyUI itself is broken.

## Requirements

* `pillow` (already in ComfyUI's own requirements; listed here anyway).
* `ffprobe` and `ffmpeg` on the runner — present on Graydient instances (other
  node packs in this ecosystem shell out to both).

No model weights, no GPU, no network access beyond downloading the media the
user attached.

## Fonts

DejaVu (monospace + bold) is bundled in `fonts/` so the card renders the same
way everywhere. See `fonts/LICENSE_DEJAVU`.

## Tests

`tests/run_tests.py` builds real sample media (video, audio, EXIF JPEG) and
asserts that the report actually contains the promised metadata. It needs
`pillow`, `numpy`, `av` and `imageio-ffmpeg` (dev-only), and uses a PyAV-based
`ffprobe` test double when a real ffprobe binary is not on the machine.
