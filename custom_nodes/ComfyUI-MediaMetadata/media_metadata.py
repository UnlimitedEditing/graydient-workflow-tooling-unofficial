"""
Media file resolution + metadata extraction for Graydient jobs.

Takes the media reference Graydient handed the workflow (a URL, a mangled
Telegram file reference, or a filename the platform pre-staged into ComfyUI's
input/ directory), resolves it to a real file on disk, and extracts
container-level metadata from it:

  * video  -> ffprobe (container, video streams, audio streams, tags)
  * audio  -> ffprobe (codec, sample rate, channels, bit rate, duration)
  * image  -> PIL (size, format, mode, EXIF incl. DateTimeOriginal/GPS) with
              ffprobe as a complement (it knows pixel format, colour space)

Everything in this module is defensive on purpose. A Graydient job that raises
costs real quota and tells the user nothing, so every failure path returns a
report that SAYS what went wrong instead of raising. The only exception is
programmer error inside the node itself.
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
from datetime import datetime, timezone

import numpy as np
import torch

from . import media_card as _card

# ── reference shapes ──────────────────────────────────────────────────────────

# Graydient sometimes hands back a Telegram attachment reference with every
# ':' and '/' delimiter stripped, e.g.
#   init_audio__httpsapi.telegram.orgfilebot5714594430AAFo...voicefile2033054.oga
# That shape is recoverable with a narrow, known-format regex (NOT a general
# "guess any mangled URL" heuristic -- mangling is lossy for arbitrary URLs).
# Same pattern as UnlimitedEditing/unlimitededting-comfy-audio-utils.
TELEGRAM_FILE_RE = re.compile(
    r'^(?:[a-z_]+__)?(https?)api\.telegram\.orgfilebot(\d+)([A-Za-z0-9_-]+?)'
    r'(voice|photo|video_note|video|audio|document|animation|sticker)file(\d+)\.([a-z0-9]+)$',
    re.IGNORECASE,
)

# Media kinds, in the order the probe prefers them when more than one field
# arrives. Graydient delivers exactly ONE media type per job through the
# init_<type>_* triplet (the Telegram "reply to one attachment" transport),
# so this order only matters for the odd job that populates more than one.
MEDIA_KINDS = ("video", "image", "audio")

# PIL format names that count as "an image" rather than a container we probe.
IMAGE_FORMATS = {
    "PNG", "JPEG", "GIF", "WEBP", "BMP", "TIFF", "ICO", "AVIF", "HEIF", "MPO", "PSD", "JPEG2000",
}

# EXIF tags worth surfacing by name, in the order they are printed.
EXIF_INTERESTING = (
    "DateTime", "DateTimeOriginal", "DateTimeDigitized", "OffsetTime", "OffsetTimeOriginal",
    "Make", "Model", "Software", "LensModel", "Artist", "Copyright", "HostComputer",
    "ExposureTime", "FNumber", "ISOSpeedRatings", "FocalLength", "ExposureProgram",
    "WhiteBalance", "MeteringMode", "Flash", "Orientation", "ColorSpace",
)


# ── small formatting helpers ──────────────────────────────────────────────────

def human_size(num_bytes):
    if num_bytes is None:
        return "n/a"
    n = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0 or unit == "TB":
            return f"{n:.2f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024.0
    return f"{n:.2f} TB"


def human_duration(seconds):
    if seconds is None:
        return "n/a"
    try:
        s = float(seconds)
    except (TypeError, ValueError):
        return "n/a"
    if s < 0:
        return "n/a"
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    if h:
        return f"{h:d}:{m:02d}:{sec:06.3f} ({s:.3f} s)"
    return f"{m:02d}:{sec:06.3f} ({s:.3f} s)"


def human_bitrate(bits_per_second):
    if bits_per_second is None:
        return "n/a"
    try:
        b = float(bits_per_second)
    except (TypeError, ValueError):
        return "n/a"
    if b <= 0:
        return "n/a"
    if b >= 1_000_000:
        return f"{b / 1_000_000:.2f} Mbps ({int(round(b)):,} bits/s)"
    if b >= 1000:
        return f"{b / 1000:.1f} kbps ({int(round(b)):,} bits/s)"
    return f"{b:.0f} bits/s"


def parse_rate(value):
    """'30000/1001' -> 29.97002997...  (ffprobe's rational frame rate)."""
    if value is None:
        return None
    try:
        if isinstance(value, str) and "/" in value:
            num, den = value.split("/", 1)
            den_f = float(den)
            return float(num) / den_f if den_f else None
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def parse_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_int(value):
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _iso(epoch):
    try:
        return datetime.fromtimestamp(float(epoch), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except (TypeError, ValueError, OSError, OverflowError):
        return "n/a"


# ── resolution: reference -> file on disk ─────────────────────────────────────

def _download(url, dest, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as fh:
        shutil.copyfileobj(resp, fh, length=1 << 20)


def _input_dir():
    try:
        import folder_paths
        return folder_paths.get_input_directory()
    except Exception:
        return ""


def _local_candidates(value, input_dir):
    """Every local path a bare filename could plausibly mean."""
    out = []
    if not value:
        return out
    value = value.strip()
    if input_dir:
        out.append(os.path.join(input_dir, value))
        out.append(os.path.join(input_dir, os.path.basename(value)))
    out.append(value)
    return out


def resolve_reference(value, workdir, input_dir=None):
    """
    Turn one media reference into a local file.

    Resolution order (first hit wins), matching the pattern proven by
    UnlimitedEditing/unlimitededting-comfy-audio-utils:
      1. real http(s):// URL              -> download
      2. mangled Telegram file reference  -> reconstruct, then download
      3. bare filename                    -> ComfyUI input/ dir, then literal path

    Returns (path_or_None, origin_label, note).
    """
    value = (value or "").strip()
    if not value:
        return None, None, "empty"

    if value.startswith("http://") or value.startswith("https://"):
        suffix = os.path.splitext(value.split("?")[0])[1] or ".bin"
        if len(suffix) > 8:
            suffix = ".bin"
        dest = os.path.join(workdir, "download" + suffix)
        try:
            _download(value, dest)
        except Exception as exc:  # noqa: BLE001 - reported, never raised
            return None, "url", f"download failed: {exc}"
        return dest, "url", f"downloaded {human_size(os.path.getsize(dest))}"

    rebuilt = TELEGRAM_FILE_RE.match(value)
    if rebuilt:
        scheme, bot_id, bot_secret, media_kind, file_id, ext = rebuilt.groups()
        url = f"{scheme}://api.telegram.org/file/bot{bot_id}:{bot_secret}/{media_kind}/file_{file_id}.{ext}"
        dest = os.path.join(workdir, "telegram" + "." + ext)
        try:
            _download(url, dest)
        except Exception as exc:  # noqa: BLE001
            return None, "telegram", f"reconstructed Telegram URL but download failed: {exc}"
        return dest, "telegram", "reconstructed mangled Telegram file reference and downloaded it"

    if input_dir is None:
        input_dir = _input_dir()
    for candidate in _local_candidates(value, input_dir):
        if os.path.isfile(candidate):
            return candidate, "local", f"found local file ({os.path.basename(candidate)})"

    return None, "local", "no local file matched (checked ComfyUI input/ and the literal path)"


def select_media(values, workdir, input_dir=None):
    """
    Pick the media to probe out of the {kind: {url, filename}} reference map.

    Returns (selection_dict, fields_received_dict). selection_dict is None when
    nothing resolved.
    """
    fields_received = {}
    for kind in MEDIA_KINDS:
        for slot in ("url", "filename"):
            raw = (values.get(f"{kind}_{slot}") or "").strip()
            if raw:
                fields_received[f"init_{kind}_{slot}"] = raw[:160]

    errors = []
    for kind in MEDIA_KINDS:
        for slot in ("url", "filename"):
            raw = (values.get(f"{kind}_{slot}") or "").strip()
            if not raw:
                continue
            path, origin, note = resolve_reference(raw, workdir, input_dir)
            if path:
                return {
                    "kind": kind,
                    "field": f"init_{kind}_{slot}",
                    "value": raw,
                    "path": path,
                    "resolved_via": origin,
                    "resolution_note": note,
                }, fields_received
            errors.append(f"init_{kind}_{slot}: {note}")
    return {"kind": None, "errors": errors}, fields_received


# ── probing ───────────────────────────────────────────────────────────────────

def ffprobe(path, timeout=90):
    """Run ffprobe and return its JSON (streams + format). Raises on failure."""
    exe = shutil.which("ffprobe") or "ffprobe"
    cmd = [exe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffprobe exited {proc.returncode}: "
            f"{proc.stderr.decode('utf-8', 'replace').strip()[:400]}"
        )
    raw = proc.stdout.decode("utf-8", "replace").strip()
    if not raw:
        raise RuntimeError("ffprobe returned no output")
    return json.loads(raw)


def _rotation_of(stream):
    rot = (stream.get("tags") or {}).get("rotate")
    for sd in stream.get("side_data_list") or []:
        if "rotation" in sd:
            rot = sd["rotation"]
    try:
        return int(round(float(rot))) % 360
    except (TypeError, ValueError):
        return 0


def _describe_video_stream(stream, index):
    fps = parse_rate(stream.get("avg_frame_rate")) or parse_rate(stream.get("r_frame_rate"))
    r_fps = parse_rate(stream.get("r_frame_rate"))
    duration = parse_float(stream.get("duration"))
    nb_frames = parse_int(stream.get("nb_frames"))
    total_frames = nb_frames
    if total_frames is None and duration and fps:
        total_frames = int(round(duration * fps))
    return {
        "index": stream.get("index", index),
        "codec": stream.get("codec_name"),
        "codec_long_name": stream.get("codec_long_name"),
        "profile": stream.get("profile"),
        "level": stream.get("level"),
        "codec_tag_string": stream.get("codec_tag_string"),
        "width": parse_int(stream.get("width")),
        "height": parse_int(stream.get("height")),
        "coded_width": parse_int(stream.get("coded_width")),
        "coded_height": parse_int(stream.get("coded_height")),
        "display_aspect_ratio": stream.get("display_aspect_ratio"),
        "sample_aspect_ratio": stream.get("sample_aspect_ratio"),
        "pix_fmt": stream.get("pix_fmt"),
        "field_order": stream.get("field_order"),
        "color_range": stream.get("color_range"),
        "color_space": stream.get("color_space"),
        "color_primaries": stream.get("color_primaries"),
        "color_transfer": stream.get("color_transfer"),
        "chroma_location": stream.get("chroma_location"),
        "bits_per_raw_sample": stream.get("bits_per_raw_sample"),
        "avg_frame_rate": stream.get("avg_frame_rate"),
        "r_frame_rate": stream.get("r_frame_rate"),
        "fps": fps,
        "r_fps": r_fps,
        "duration": duration,
        "nb_frames": nb_frames,
        "total_frames": total_frames,
        "bit_rate": parse_int(stream.get("bit_rate")),
        "time_base": stream.get("time_base"),
        "start_time": parse_float(stream.get("start_time")),
        "rotation": _rotation_of(stream),
        "tags": stream.get("tags") or {},
        "disposition": stream.get("disposition") or {},
    }


def _describe_audio_stream(stream, index):
    return {
        "index": stream.get("index", index),
        "codec": stream.get("codec_name"),
        "codec_long_name": stream.get("codec_long_name"),
        "profile": stream.get("profile"),
        "sample_fmt": stream.get("sample_fmt"),
        "sample_rate": parse_int(stream.get("sample_rate")),
        "channels": parse_int(stream.get("channels")),
        "channel_layout": stream.get("channel_layout"),
        "bits_per_sample": parse_int(stream.get("bits_per_sample")),
        "duration": parse_float(stream.get("duration")),
        "bit_rate": parse_int(stream.get("bit_rate")),
        "start_time": parse_float(stream.get("start_time")),
        "nb_frames": parse_int(stream.get("nb_frames")),
        "time_base": stream.get("time_base"),
        "tags": stream.get("tags") or {},
        "disposition": stream.get("disposition") or {},
    }


def _describe_other_stream(stream, index):
    return {
        "index": stream.get("index", index),
        "type": stream.get("codec_type"),
        "codec": stream.get("codec_name"),
        "codec_long_name": stream.get("codec_long_name"),
        "duration": parse_float(stream.get("duration")),
        "bit_rate": parse_int(stream.get("bit_rate")),
        "tags": stream.get("tags") or {},
    }


def probe_image(path):
    """PIL-side image facts: size, format, mode, EXIF, DPI, frame count."""
    from PIL import ExifTags, Image

    out = {
        "format": None, "mode": None, "width": None, "height": None,
        "frames": 1, "animated": False, "dpi": None, "exif": {}, "info": {},
    }
    with Image.open(path) as im:
        out["format"] = im.format
        out["mode"] = im.mode
        out["width"], out["height"] = im.width, im.height
        out["frames"] = int(getattr(im, "n_frames", 1) or 1)
        out["animated"] = bool(getattr(im, "is_animated", False))
        dpi = im.info.get("dpi")
        if isinstance(dpi, (tuple, list)) and dpi:
            out["dpi"] = f"{dpi[0]:.0f} x {dpi[1]:.0f} dpi"
        for key, value in im.info.items():
            if isinstance(value, (str, int, float, bool)) and len(str(value)) < 120:
                out["info"][key] = value
        try:
            exif = im.getexif()
            tag_names = {v: k for k, v in ExifTags.TAGS.items()}
            for tid, value in exif.items():
                name = tag_names.get(tid, ExifTags.TAGS.get(tid))
                if not name:
                    continue
                if isinstance(value, bytes):
                    value = f"<{len(value)} bytes>"
                out["exif"][name] = str(value)[:120]
            for ifd_name, ifd in (("Exif", getattr(exif, "get_ifd", lambda _k: None)(0x8769)),
                                  ("GPS", getattr(exif, "get_ifd", lambda _k: None)(0x8825))):
                if not ifd:
                    continue
                ifd_names = {v: k for k, v in getattr(ExifTags, f"{ifd_name.upper()}_TAGS", {}).items()}
                for tid, value in ifd.items():
                    name = ifd_names.get(tid, tid)
                    if isinstance(value, bytes):
                        value = f"<{len(value)} bytes>"
                    out["exif"][f"{ifd_name}:{name}"] = str(value)[:120]
        except Exception as exc:  # noqa: BLE001 - EXIF is a bonus, never fatal
            out["exif_error"] = str(exc)
    return out


def probe_media(path):
    """
    Probe one media file. Returns a dict with whatever could be determined;
    never raises for a readable-but-odd file.
    """
    result = {
        "detected_type": None,
        "file": {},
        "container": {},
        "video_streams": [],
        "audio_streams": [],
        "other_streams": [],
        "image": None,
        "tags": {},
        "creation_time": None,
        "errors": [],
    }

    try:
        stat = os.stat(path)
        result["file"] = {
            "name": os.path.basename(path),
            "path": path,
            "size_bytes": stat.st_size,
            "size_human": human_size(stat.st_size),
            "mtime_utc": _iso(stat.st_mtime),
        }
    except OSError as exc:
        result["errors"].append(f"stat failed: {exc}")
        return result

    # 1. PIL first: it identifies images unambiguously and never mis-reports them.
    try:
        image_info = probe_image(path)
    except Exception:
        image_info = None
    if image_info and image_info.get("format") in IMAGE_FORMATS:
        result["image"] = image_info
        result["detected_type"] = "image"

    # 2. ffprobe for containers (and as a complement for images).
    probe = None
    try:
        probe = ffprobe(path)
    except FileNotFoundError:
        result["errors"].append("ffprobe is not installed on this runner (no container metadata)")
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"ffprobe failed: {exc}")

    if probe:
        fmt = probe.get("format") or {}
        result["container"] = {
            "format_name": fmt.get("format_name"),
            "format_long_name": fmt.get("format_long_name"),
            "nb_streams": parse_int(fmt.get("nb_streams")),
            "nb_programs": parse_int(fmt.get("nb_programs")),
            "start_time": parse_float(fmt.get("start_time")),
            "duration": parse_float(fmt.get("duration")),
            "size_bytes": parse_int(fmt.get("size")),
            "bit_rate": parse_int(fmt.get("bit_rate")),
            "probe_score": parse_int(fmt.get("probe_score")),
        }
        result["tags"] = {k: str(v)[:200] for k, v in (fmt.get("tags") or {}).items()}
        for stream in probe.get("streams") or []:
            ctype = stream.get("codec_type")
            if ctype == "video":
                result["video_streams"].append(_describe_video_stream(stream, len(result["video_streams"])))
            elif ctype == "audio":
                result["audio_streams"].append(_describe_audio_stream(stream, len(result["audio_streams"])))
            else:
                result["other_streams"].append(_describe_other_stream(stream, len(result["other_streams"])))

        if result["video_streams"] and result["detected_type"] is None:
            result["detected_type"] = "video"
        elif result["audio_streams"] and result["detected_type"] is None:
            result["detected_type"] = "audio"

        creation = result["tags"].get("creation_time")
        if not creation:
            for stream in result["video_streams"] + result["audio_streams"]:
                stags = stream.get("tags") or {}
                if stags.get("creation_time"):
                    creation = stags["creation_time"]
                    break
        if creation:
            result["creation_time"] = creation
        elif result["image"]:
            exif = result["image"].get("exif") or {}
            for key in ("DateTimeOriginal", "DateTime", "DateTimeDigitized"):
                if exif.get(key):
                    result["creation_time"] = exif[key]
                    break

    # Some containers only report duration/bitrate on the streams, not on the
    # format. Fill the gaps so the card never shows a bare "0.000 s".
    stream_durations = [s.get("duration") for s in result["video_streams"] + result["audio_streams"]
                        if s.get("duration")]
    container = result["container"]
    if not container.get("duration") and stream_durations:
        container["duration"] = max(stream_durations)
        container["duration_source"] = "longest stream (container did not report one)"
    if not container.get("bit_rate"):
        size = (result.get("file") or {}).get("size_bytes")
        duration = container.get("duration")
        if size and duration:
            container["bit_rate"] = int(round(size * 8 / duration))
            container["bit_rate_source"] = "computed from file size / duration"
    if not result["creation_time"] and result["image"]:
        exif = result["image"].get("exif") or {}
        for key in ("DateTimeOriginal", "DateTime", "DateTimeDigitized"):
            if exif.get(key):
                result["creation_time"] = exif[key]
                break

    if result["detected_type"] is None:
        result["detected_type"] = "unknown"

    return result


# ── report rendering (text) ───────────────────────────────────────────────────

def _kv(lines, label, value, width=17):
    if value is None or value == "":
        return
    lines.append(f"{label.ljust(width)} {value}")


def build_report_text(selection, fields_received, probed, caption=""):
    """Human-readable report body (no header/footer -- the card adds those)."""
    lines = []
    lines.append("SOURCE")
    lines.append("-" * 60)
    if selection.get("kind") is None:
        _kv(lines, "Status", "no media was supplied with this job")
        for err in selection.get("errors") or []:
            _kv(lines, "Tried", err, 17)
    else:
        _kv(lines, "Declared", f"{selection['kind'].upper()} (via {selection['field']})")
        _kv(lines, "Resolved via", selection.get("resolved_via"))
        _kv(lines, "Note", selection.get("resolution_note"))
        _kv(lines, "Detected type", str(probed.get("detected_type", "unknown")).upper())
    _kv(lines, "File", (probed.get("file") or {}).get("name"))
    _kv(lines, "Size", (probed.get("file") or {}).get("size_human"))
    _kv(lines, "File modified", (probed.get("file") or {}).get("mtime_utc"))
    _kv(lines, "Created", probed.get("creation_time"))

    container = probed.get("container") or {}
    still = str(probed.get("detected_type", "")).lower() == "image"
    if container:
        lines.append("")
        lines.append("CONTAINER")
        lines.append("-" * 60)
        _kv(lines, "Format", container.get("format_name"))
        _kv(lines, "Format name", container.get("format_long_name"))
        _kv(lines, "Duration", human_duration(container.get("duration")))
        _kv(lines, "Bit rate", human_bitrate(container.get("bit_rate")))
        _kv(lines, "Streams", container.get("nb_streams"))
        _kv(lines, "Start time", container.get("start_time"))
        _kv(lines, "Probe score", container.get("probe_score"))
        if container.get("duration_source"):
            _kv(lines, "Duration from", container.get("duration_source"))
        if container.get("bit_rate_source"):
            _kv(lines, "Bit rate from", container.get("bit_rate_source"))

    # A still image is reported by ffprobe as a one-frame "video" stream
    # (mjpeg/png). That is decoder noise, not media metadata -- the IMAGE
    # section below is the meaningful one -- so it is only shown for real
    # moving media.
    for stream in (probed.get("video_streams") or []) if not still else []:
        lines.append("")
        lines.append(f"VIDEO STREAM #{stream.get('index')}")
        lines.append("-" * 60)
        _kv(lines, "Codec", f"{stream.get('codec')} ({stream.get('codec_long_name')})")
        _kv(lines, "Profile", stream.get("profile"))
        _kv(lines, "Level", stream.get("level"))
        res = f"{stream.get('width')} x {stream.get('height')}"
        if stream.get("coded_width") and stream.get("coded_width") != stream.get("width"):
            res += f" (coded {stream.get('coded_width')} x {stream.get('coded_height')})"
        _kv(lines, "Resolution", res)
        _kv(lines, "Aspect ratio", stream.get("display_aspect_ratio"))
        _kv(lines, "Sample aspect", stream.get("sample_aspect_ratio"))
        fps = stream.get("fps")
        _kv(lines, "Frame rate", f"{fps:.3f} fps (avg {stream.get('avg_frame_rate')}, r {stream.get('r_frame_rate')})" if fps else None)
        _kv(lines, "Total frames", stream.get("total_frames"))
        _kv(lines, "Duration", human_duration(stream.get("duration")))
        _kv(lines, "Bit rate", human_bitrate(stream.get("bit_rate")))
        _kv(lines, "Pixel format", stream.get("pix_fmt"))
        _kv(lines, "Bit depth", stream.get("bits_per_raw_sample"))
        colour = " / ".join(str(x) for x in (stream.get("color_space"), stream.get("color_primaries"), stream.get("color_transfer")) if x)
        _kv(lines, "Colour", colour)
        _kv(lines, "Chroma loc.", stream.get("chroma_location"))
        _kv(lines, "Field order", stream.get("field_order"))
        _kv(lines, "Rotation", stream.get("rotation"))
        _kv(lines, "Time base", stream.get("time_base"))
        _kv(lines, "Codec tag", stream.get("codec_tag_string"))
        for key, value in (stream.get("tags") or {}).items():
            _kv(lines, f"Tag: {key}", value)

    for stream in probed.get("audio_streams") or []:
        lines.append("")
        lines.append(f"AUDIO STREAM #{stream.get('index')}")
        lines.append("-" * 60)
        _kv(lines, "Codec", f"{stream.get('codec')} ({stream.get('codec_long_name')})")
        _kv(lines, "Profile", stream.get("profile"))
        _kv(lines, "Sample rate", f"{stream.get('sample_rate')} Hz" if stream.get("sample_rate") else None)
        _kv(lines, "Channels", f"{stream.get('channels')} ({stream.get('channel_layout')})" if stream.get("channels") else None)
        _kv(lines, "Duration", human_duration(stream.get("duration")))
        _kv(lines, "Bit rate", human_bitrate(stream.get("bit_rate")))
        _kv(lines, "Sample format", stream.get("sample_fmt"))
        _kv(lines, "Bit depth", stream.get("bits_per_sample"))
        _kv(lines, "Time base", stream.get("time_base"))
        for key, value in (stream.get("tags") or {}).items():
            _kv(lines, f"Tag: {key}", value)

    for stream in probed.get("other_streams") or []:
        lines.append("")
        lines.append(f"{str(stream.get('type') or 'other').upper()} STREAM #{stream.get('index')}")
        lines.append("-" * 60)
        _kv(lines, "Codec", f"{stream.get('codec')} ({stream.get('codec_long_name')})")
        _kv(lines, "Duration", human_duration(stream.get("duration")))
        _kv(lines, "Bit rate", human_bitrate(stream.get("bit_rate")))

    image = probed.get("image")
    if image:
        lines.append("")
        lines.append("IMAGE")
        lines.append("-" * 60)
        _kv(lines, "Format", image.get("format"))
        _kv(lines, "Resolution", f"{image.get('width')} x {image.get('height')}")
        _kv(lines, "Colour mode", image.get("mode"))
        _kv(lines, "Frames", image.get("frames"))
        _kv(lines, "Animated", image.get("animated"))
        _kv(lines, "Resolution (dpi)", image.get("dpi"))
        for key, value in (image.get("exif") or {}).items():
            if key in EXIF_INTERESTING or key.startswith(("GPS:", "Exif:")):
                _kv(lines, f"EXIF {key}", value)

    tags = probed.get("tags") or {}
    if tags:
        lines.append("")
        lines.append("CONTAINER TAGS")
        lines.append("-" * 60)
        for key, value in tags.items():
            _kv(lines, key, value)

    if fields_received:
        lines.append("")
        lines.append("PLATFORM FIELDS RECEIVED")
        lines.append("-" * 60)
        for key, value in fields_received.items():
            _kv(lines, key, value)

    errors = probed.get("errors") or []
    if errors:
        lines.append("")
        lines.append("NOTES")
        lines.append("-" * 60)
        for err in errors:
            lines.append(f"* {err}")

    return "\n".join(lines)


def build_report_json(selection, fields_received, probed, caption=""):
    """Machine-readable twin of the text report."""
    return {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "caption": caption or "",
        "selected": {
            "declared_kind": selection.get("kind"),
            "field": selection.get("field"),
            "value": selection.get("value"),
            "resolved_via": selection.get("resolved_via"),
            "resolution_note": selection.get("resolution_note"),
            "errors": selection.get("errors") or [],
        },
        "platform_fields_received": fields_received,
        "detected_type": probed.get("detected_type"),
        "file": probed.get("file"),
        "container": probed.get("container"),
        "video_streams": probed.get("video_streams"),
        "audio_streams": probed.get("audio_streams"),
        "other_streams": probed.get("other_streams"),
        "image": probed.get("image"),
        "tags": probed.get("tags"),
        "creation_time": probed.get("creation_time"),
        "errors": probed.get("errors"),
    }


# ── thumbnail ─────────────────────────────────────────────────────────────────

def first_frame_thumbnail(path, detected_type, max_side=320):
    """
    Best-effort thumbnail: first video frame, or the image itself.
    Returns a PIL Image or None. Never raises.
    """
    try:
        if detected_type == "image":
            from PIL import Image
            with Image.open(path) as im:
                im = im.convert("RGB")
                im.thumbnail((max_side, max_side))
                return im.copy()
        if detected_type == "video":
            from PIL import Image
            exe = shutil.which("ffmpeg") or "ffmpeg"
            with tempfile.TemporaryDirectory(prefix="mediameta_thumb_") as tmp:
                out = os.path.join(tmp, "thumb.png")
                proc = subprocess.run(
                    [exe, "-y", "-v", "error", "-i", path, "-frames:v", "1",
                     "-vf", f"scale='min({max_side},iw)':-2", out],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90,
                )
                if proc.returncode == 0 and os.path.isfile(out):
                    with Image.open(out) as im:
                        im = im.convert("RGB")
                        im.thumbnail((max_side, max_side))
                        return im.copy()
    except Exception:
        return None
    return None


# ── the ComfyUI node ───────────────────────────────────────────────────────────

def _to_tensor(image):
    """PIL RGB image -> ComfyUI IMAGE tensor [B,H,W,C] float32 in [0,1]."""
    arr = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(arr).unsqueeze(0)


class MediaMetadataProbe:
    """
    Probe an attached media file and render its metadata as an image.

    The six media inputs are the Graydient init_<type>_* triplet, in both its
    _url and its _filename flavour, because which of them a given submission
    path populates is architecturally unpredictable (KI-007 section 7).
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_url": ("STRING", {"default": "", "multiline": False}),
                "video_filename": ("STRING", {"default": "", "multiline": False}),
                "image_url": ("STRING", {"default": "", "multiline": False}),
                "image_filename": ("STRING", {"default": "", "multiline": False}),
                "audio_url": ("STRING", {"default": "", "multiline": False}),
                "audio_filename": ("STRING", {"default": "", "multiline": False}),
                "caption": ("STRING", {"default": "", "multiline": True}),
                "card_width": ("INT", {"default": 1600, "min": 0, "max": 4096, "step": 16}),
                "card_height": ("INT", {"default": 1000, "min": 0, "max": 4096, "step": 16}),
                "include_thumbnail": ("BOOLEAN", {"default": True}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "IMAGE")
    RETURN_NAMES = ("report", "report_json", "card")
    FUNCTION = "run"
    CATEGORY = "media/metadata"

    async def run(self, video_url="", video_filename="", image_url="", image_filename="",
                  audio_url="", audio_filename="", caption="", card_width=1600,
                  card_height=1000, include_thumbnail=True):
        # Blocking work (download + ffprobe + PIL) stays off the event loop:
        # a blocked loop can make a finished job report timed_out.
        return await asyncio.to_thread(
            self._run_sync, video_url, video_filename, image_url, image_filename,
            audio_url, audio_filename, caption, card_width, card_height, include_thumbnail,
        )

    def _run_sync(self, video_url, video_filename, image_url, image_filename,
                  audio_url, audio_filename, caption, card_width, card_height,
                  include_thumbnail):
        workdir = tempfile.mkdtemp(prefix="mediametadata_")
        try:
            values = {
                "video_url": video_url,
                "video_filename": video_filename,
                "image_url": image_url,
                "image_filename": image_filename,
                "audio_url": audio_url,
                "audio_filename": audio_filename,
            }
            selection, fields_received = select_media(values, workdir)

            if selection.get("kind") is None:
                probed = {
                    "detected_type": "none", "file": {}, "container": {},
                    "video_streams": [], "audio_streams": [], "other_streams": [],
                    "image": None, "tags": {}, "creation_time": None,
                    "errors": list(selection.get("errors") or []),
                }
            else:
                probed = probe_media(selection["path"])

            body = build_report_text(selection, fields_received, probed, caption)
            report_json = build_report_json(selection, fields_received, probed, caption)

            media_type = probed.get("detected_type") or "none"
            file_info = probed.get("file") or {}
            title = f"MEDIA METADATA - {str(media_type).upper()}"
            subtitle = file_info.get("name") or "no media supplied"
            if file_info.get("size_human"):
                subtitle += f"   -   {file_info['size_human']}"
            if caption:
                caption_line = " ".join(str(caption).split())
                if len(caption_line) > 120:
                    caption_line = caption_line[:120] + "..."
                subtitle += f"   -   {caption_line}"

            thumbnail = None
            if include_thumbnail and selection.get("kind") is not None:
                thumbnail = first_frame_thumbnail(selection["path"], media_type)

            width = int(card_width or 0)
            height = int(card_height or 0)
            # A platform-injected default size (Telegram sends one when the user
            # gives no /size) can be small; keep the card legible regardless.
            width = max(width, 900) if width else 1600
            height = max(height, 600) if height else 1000

            try:
                card = _card.render_card(
                    title=title,
                    subtitle=subtitle,
                    body=body,
                    thumbnail=thumbnail,
                    media_type=media_type,
                    width=width,
                    height=height,
                )
                card_tensor = _to_tensor(card)
            except Exception as exc:  # noqa: BLE001 - the report must still ship
                body += f"\n\nNOTES\n{'-' * 60}\n* card rendering failed: {exc}"
                report_json.setdefault("errors", []).append(f"card rendering failed: {exc}")
                card_tensor = torch.zeros((1, 64, 64, 3), dtype=torch.float32)

            return (body, json.dumps(report_json, indent=2), card_tensor)
        finally:
            shutil.rmtree(workdir, ignore_errors=True)


NODE_CLASS_MAPPINGS = {
    "MediaMetadataProbe": MediaMetadataProbe,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MediaMetadataProbe": "Media - Metadata Probe (file -> metadata card)",
}
