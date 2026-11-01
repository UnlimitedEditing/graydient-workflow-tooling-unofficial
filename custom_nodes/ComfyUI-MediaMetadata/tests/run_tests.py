#!/usr/bin/env python3
"""
Local test harness for ComfyUI-MediaMetadata.

Builds real sample media (video + audio + image with EXIF), runs the node's
synchronous core against them, and checks that the report actually surfaces
the metadata the utility promises: resolution, duration, frame rate, total
frames, bit rate, codec, creation time, file size, EXIF.

Run:  python tests/run_tests.py
Needs: pillow, numpy, av, imageio-ffmpeg (dev-only; the node itself needs
       pillow + ffprobe/ffmpeg on the runner).
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIXTURES = os.path.join(HERE, "fixtures")
BIN = os.path.join(HERE, "bin")

sys.path.insert(0, ROOT)


def load_package():
    """Import the pack as a package (its directory name has dashes, so it
    cannot be imported by name directly)."""
    try:
        import torch  # noqa: F401
    except Exception:
        sys.path.insert(0, HERE)
        import torch_stub
        sys.modules["torch"] = torch_stub
        print("[test] using torch stub (real torch is not importable here)")

    spec = importlib.util.spec_from_file_location(
        "mediametadata", os.path.join(ROOT, "__init__.py"), submodule_search_locations=[ROOT]
    )
    package = importlib.util.module_from_spec(spec)
    sys.modules["mediametadata"] = package
    spec.loader.exec_module(package)
    return package


def build_fixtures():
    os.makedirs(FIXTURES, exist_ok=True)
    os.makedirs(BIN, exist_ok=True)

    # ffprobe test double on PATH (wrapper so it runs under THIS interpreter)
    fake = os.path.join(BIN, "ffprobe")
    with open(fake, "w", encoding="utf-8") as fh:
        fh.write(f'#!/bin/sh\nexec "{sys.executable}" "{os.path.join(HERE, "fake_ffprobe.py")}" "$@"\n')
    os.chmod(fake, 0o755)

    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg = shutil.which("ffmpeg")
    shutil.copyfile(ffmpeg, os.path.join(BIN, "ffmpeg"))
    os.chmod(os.path.join(BIN, "ffmpeg"), 0o755)
    os.environ["PATH"] = BIN + os.pathsep + os.environ.get("PATH", "")

    video = os.path.join(FIXTURES, "sample_clip.mp4")
    audio = os.path.join(FIXTURES, "sample_tone.m4a")
    if not os.path.isfile(video):
        subprocess.run([
            os.path.join(BIN, "ffmpeg"), "-y", "-v", "error",
            "-f", "lavfi", "-i", "testsrc=size=768x448:rate=30:duration=4.166667",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=4.2",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-metadata", "creation_time=2026-10-09T12:33:01.000000Z",
            "-metadata", "encoder=Lavf60.16.100",
            "-c:a", "aac", "-b:a", "128k", "-shortest", video,
        ], check=True)
    if not os.path.isfile(audio):
        subprocess.run([
            os.path.join(BIN, "ffmpeg"), "-y", "-v", "error",
            "-f", "lavfi", "-i", "sine=frequency=330:duration=3.0",
            "-c:a", "aac", "-b:a", "96k", audio,
        ], check=True)

    from PIL import Image
    jpeg = os.path.join(FIXTURES, "sample_photo.jpg")
    if not os.path.isfile(jpeg):
        img = Image.new("RGB", (1920, 1080), (24, 26, 32))
        exif = img.getexif()
        exif[271] = "Graydient Test Cam"      # Make
        exif[272] = "Model X1"                # Model
        exif[306] = "2026:10:09 12:33:01"     # DateTime
        exif[36867] = "2026:10:09 12:33:01"  # DateTimeOriginal
        exif[305] = "MediaMetadataProbe tests"
        img.save(jpeg, "JPEG", quality=92, exif=exif.tobytes())
    png = os.path.join(FIXTURES, "sample_frame.png")
    if not os.path.isfile(png):
        Image.new("RGB", (640, 360), (10, 120, 200)).save(png)
    return video, audio, jpeg, png


def run_node(video, audio, jpeg):
    load_package()
    from mediametadata import media_metadata as nodes_mod

    node = nodes_mod.MediaMetadataProbe()
    out_dir = os.path.join(FIXTURES, "out")
    os.makedirs(out_dir, exist_ok=True)

    cases = [
        ("video", dict(video_filename=video)),
        ("audio", dict(audio_filename=audio)),
        ("image", dict(image_filename=jpeg)),
        ("none", dict()),
    ]
    results = {}
    for name, kwargs in cases:
        body, report_json, tensor = node._run_sync(
            video_url=kwargs.get("video_url", ""),
            video_filename=kwargs.get("video_filename", ""),
            image_url=kwargs.get("image_url", ""),
            image_filename=kwargs.get("image_filename", ""),
            audio_url=kwargs.get("audio_url", ""),
            audio_filename=kwargs.get("audio_filename", ""),
            caption="local test run",
            card_width=1600,
            card_height=1000,
            include_thumbnail=True,
        )
        results[name] = (body, report_json, tensor)
        print(f"\n{'=' * 78}\nCASE: {name}\n{'=' * 78}")
        print(body)
        from PIL import Image
        arr = tensor[0].numpy()
        Image.fromarray((arr * 255).astype("uint8")).save(os.path.join(out_dir, f"card_{name}.png"))
        with open(os.path.join(out_dir, f"report_{name}.json"), "w", encoding="utf-8") as fh:
            fh.write(report_json)
    return results


def check(results):
    failures = []
    video_body = results["video"][0]
    for needle in ("768 x 448", "30.000 fps", "Total frames", "Bit rate", "h264",
                   "Duration", "CONTAINER", "creation_time", "Codec"):
        if needle not in video_body:
            failures.append(f"video report missing {needle!r}")
    audio_body = results["audio"][0]
    for needle in ("Sample rate", "Channels", "aac", "Bit rate"):
        if needle not in audio_body:
            failures.append(f"audio report missing {needle!r}")
    image_body = results["image"][0]
    for needle in ("1920 x 1080", "EXIF", "JPEG"):
        if needle not in image_body:
            failures.append(f"image report missing {needle!r}")
    none_body = results["none"][0]
    if "no media was supplied" not in none_body:
        failures.append("empty case did not report 'no media was supplied'")

    vjson = json.loads(results["video"][1])
    if not vjson.get("video_streams"):
        failures.append("video JSON has no video streams")
    else:
        vs = vjson["video_streams"][0]
        if vs.get("width") != 768 or vs.get("height") != 448:
            failures.append(f"video JSON resolution wrong: {vs.get('width')}x{vs.get('height')}")
        if not vs.get("fps"):
            failures.append("video JSON has no fps")
        if not vs.get("total_frames"):
            failures.append("video JSON has no total_frames")
    print("\n" + "=" * 78)
    if failures:
        print("FAILURES:")
        for f in failures:
            print("  -", f)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    video, audio, jpeg, png = build_fixtures()
    results = run_node(video, audio, jpeg)
    sys.exit(check(results))
