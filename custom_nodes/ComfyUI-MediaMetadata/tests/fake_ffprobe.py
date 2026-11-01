#!/usr/bin/env python3
"""
Test double for ffprobe.

The sandbox cannot download a real ffprobe binary (GitHub release assets are
blocked), so this script emits the SAME JSON shape that
`ffprobe -v error -print_format json -show_format -show_streams` produces,
using PyAV to read the real container facts. It exists so the parsing and
report-rendering paths can be exercised against realistic data locally.

Usage: fake_ffprobe.py <file>
"""
import json
import sys

import av

CODEC_LONG = {
    "h264": "H.264 / AVC / MPEG-4 AVC",
    "aac": "AAC (Advanced Audio Coding)",
    "mjpeg": "Motion JPEG",
    "png": "PNG (Portable Network Graphics) image",
    "mp3": "MP3 (MPEG audio layer 3)",
    "pcm_s16le": "PCM signed 16-bit little-endian",
    "vp9": "Google VP9",
    "hevc": "H.265 / HEVC",
}


def rate(r):
    if r is None:
        return "0/0"
    return f"{int(r.numerator)}/{int(r.denominator)}" if hasattr(r, "numerator") else str(r)


def attr(obj, name, default=None):
    try:
        value = getattr(obj, name, default)
    except Exception:
        return default
    return default if value is None else value


def main():
    path = sys.argv[-1]
    out = {"streams": [], "format": {}}
    with av.open(path) as container:
        fmt = container.format
        out["format"] = {
            "filename": path,
            "nb_streams": len(container.streams),
            "nb_programs": 0,
            "format_name": attr(fmt, "name", "unknown"),
            "format_long_name": attr(fmt, "long_name", attr(fmt, "name", "unknown")),
            "start_time": float(attr(container, "start", 0) or 0),
            "duration": float(attr(fmt, "duration", 0) or 0),
            "size": int(attr(fmt, "size", 0) or 0),
            "bit_rate": int(attr(fmt, "bit_rate", 0) or 0),
            "probe_score": 100,
            "tags": {str(k): str(v) for k, v in (attr(fmt, "metadata", {}) or {}).items()},
        }
        for i, stream in enumerate(container.streams):
            cc = stream.codec_context
            duration = float(stream.duration * stream.time_base) if attr(stream, "duration") else None
            common = {
                "index": i,
                "codec_name": attr(cc, "name", "unknown"),
                "codec_long_name": CODEC_LONG.get(attr(cc, "name", ""), attr(cc, "name", "unknown")),
                "codec_type": attr(stream, "type", "unknown"),
                "time_base": str(attr(stream, "time_base", "0/1")),
                "start_time": float(attr(stream, "start", 0) or 0),
                "duration": duration,
                "bit_rate": int(attr(cc, "bit_rate", 0) or 0),
                "tags": {str(k): str(v) for k, v in (attr(stream, "metadata", {}) or {}).items()},
                "disposition": {"default": 0, "dub": 0, "orig": 0, "copy": 0, "comment": 0,
                                "lyrics": 0, "karaoke": 0, "forced": 0, "hearing_impaired": 0,
                                "visual_impaired": 0, "clean_effects": 0, "attached_pic": 0,
                                "timed_thumbnails": 0, "captions": 0, "descriptions": 0,
                                "dependent": 0, "metadata": 0},
            }
            if stream.type == "video":
                common.update({
                    "profile": str(attr(cc, "profile", "") or "") or None,
                    "width": attr(cc, "width"),
                    "height": attr(cc, "height"),
                    "coded_width": attr(cc, "width"),
                    "coded_height": attr(cc, "height"),
                    "pix_fmt": attr(cc, "pix_fmt"),
                    "level": -99,
                    "color_range": "tv",
                    "color_space": "bt709",
                    "color_primaries": "bt709",
                    "color_transfer": "bt709",
                    "chroma_location": "left",
                    "field_order": "progressive",
                    "sample_aspect_ratio": "1:1",
                    "display_aspect_ratio": f"{attr(cc, 'width', 0)}:{attr(cc, 'height', 0)}",
                    "avg_frame_rate": rate(attr(stream, "average_rate")),
                    "r_frame_rate": rate(attr(stream, "average_rate")),
                    "nb_frames": int(attr(stream, "frames", 0) or 0) or None,
                    "bits_per_raw_sample": "8",
                })
            elif stream.type == "audio":
                channels = attr(cc, "channels")
                common.update({
                    "sample_fmt": attr(attr(cc, "format", None), "name", None),
                    "sample_rate": attr(cc, "sample_rate"),
                    "channels": channels,
                    "channel_layout": {1: "mono", 2: "stereo"}.get(channels, f"{channels} channels"),
                    "bits_per_sample": 16,
                    "nb_frames": int(attr(stream, "frames", 0) or 0) or None,
                })
            out["streams"].append(common)
    print(json.dumps(out, indent=4))


if __name__ == "__main__":
    main()
