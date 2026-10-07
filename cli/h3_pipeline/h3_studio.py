import argparse
import json
import os
import subprocess
import sys
from typing import List, Dict

def build_h3_prompt(args):
    """
    Builds a structured H3 timeline prompt based on the H3 Prompting Bible guidelines.
    """
    # Base command structure for Graydient
    # e.g. /workflow /run:sprite-actions-h3 /size:512x512 /length:240 /image1:img1 ...
    
    images_str = " ".join([f"/image{i+1}:{img}" for i, img in enumerate(args.images)])
    
    prompt_header = f"/workflow /run:sprite-actions-h3 /size:{args.size} /length:{args.length} {images_str} <motion-repairv2-h3:0.9> Create one continuous, coherent 2D game asset animation following the {len(args.images)} supplied guide images in strict chronological order.\n\n"
    prompt_header += "The guide images are fixed visual states on the timeline. Each guide establishes what the scene must look like at that point. Generate natural continuous motion BETWEEN these states rather than treating the images as independent shots.\n\n"
    prompt_header += "TIMELINE\n\n"
    
    # Simple timeline interpolation (evenly spaced for now, can be overridden with a JSON timeline)
    total_seconds = args.length / 24.0
    interval = total_seconds / max(1, (len(args.images) - 1)) if len(args.images) > 1 else total_seconds
    
    timeline_str = ""
    for i in range(len(args.images)):
        timestamp = i * interval
        timeline_str += f"{timestamp:.1f} — GUIDE {i+1}\n"
        timeline_str += f"Arrive naturally at the visual state established by Guide {i+1}.\n\n"
        
        if i < len(args.images) - 1:
            next_timestamp = (i + 1) * interval
            timeline_str += f"{timestamp:.1f}–{next_timestamp:.1f} — TRANSITION {i+1}\n"
            timeline_str += f"The character transitions smoothly towards the next guide state.\n\n"
    
    timeline_str += "IMPORTANT:\n"
    timeline_str += f"Guide {len(args.images)} is NOT the ending frame.\n"
    timeline_str += "Do not freeze. Do not hold as a still image.\n\n"
    
    timeline_str += "CONTINUITY\n"
    timeline_str += "Treat all guides as different moments within the SAME continuous scene.\n"
    timeline_str += "Maintain exact character identity, wardrobe, proportions, and environment. Do not reset characters between guides.\n\n"
    
    timeline_str += "CAMERA\n"
    timeline_str += "Locked tripod shot. Camera movement must remain physically continuous.\n"
    
    full_prompt = prompt_header + timeline_str
    
    print("=== GENERATED H3 PROMPT ===\n")
    print(full_prompt)
    print("\n===========================")
    
    if args.out:
        with open(args.out, 'w') as f:
            f.write(full_prompt)
        print(f"Prompt saved to {args.out}")

def extract_frames(args):
    """
    Extracts frames from an mp4 video using ffmpeg at the specified framerate.
    """
    if not os.path.exists(args.out_dir):
        os.makedirs(args.out_dir)
        
    out_pattern = os.path.join(args.out_dir, "frame_%04d.png")
    
    print(f"Extracting frames from {args.video} at {args.fps} fps...")
    cmd = [
        "ffmpeg", "-y",
        "-i", args.video,
        "-vf", f"fps={args.fps}",
        out_pattern
    ]
    
    subprocess.run(cmd, check=True)
    print(f"Frames extracted to {args.out_dir}")

def compile_strip(args):
    """
    Stitches extracted frames horizontally into a single sprite strip using Pillow.
    Optionally applies a basic chroma key.
    """
    try:
        from PIL import Image
    except ImportError:
        print("Error: Pillow is required for compile-strip. Run 'pip install Pillow'")
        sys.exit(1)
        
    frame_files = sorted([f for f in os.listdir(args.frame_dir) if f.endswith('.png')])
    if not frame_files:
        print(f"No PNG frames found in {args.frame_dir}")
        sys.exit(1)
        
    print(f"Found {len(frame_files)} frames. Compiling strip...")
    
    frames = []
    for f in frame_files:
        path = os.path.join(args.frame_dir, f)
        img = Image.open(path).convert("RGBA")
        
        # Very basic chroma keying (replacing pure white with transparent)
        if args.chroma_key:
            data = img.getdata()
            new_data = []
            for item in data:
                # If near white (adjust threshold as needed)
                if item[0] > 240 and item[1] > 240 and item[2] > 240:
                    new_data.append((255, 255, 255, 0))
                else:
                    new_data.append(item)
            img.putdata(new_data)
            
        frames.append(img)
        
    width = frames[0].width
    height = frames[0].height
    
    strip = Image.new("RGBA", (width * len(frames), height))
    
    for i, frame in enumerate(frames):
        strip.paste(frame, (i * width, 0))
        
    strip.save(args.out)
    print(f"Sprite strip saved to {args.out} ({strip.width}x{strip.height})")

def main():
    parser = argparse.ArgumentParser(description="H3 High-Fidelity Sprite Studio Pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Prompt Generator
    p_prompt = subparsers.add_parser("build-prompt", help="Build an H3 timeline prompt")
    p_prompt.add_argument("--images", nargs='+', required=True, help="List of guide image names (e.g. idle1 attack1)")
    p_prompt.add_argument("--size", default="512x512", help="Generation resolution")
    p_prompt.add_argument("--length", type=int, default=240, help="Total frames (e.g. 240 for 10s @ 24fps)")
    p_prompt.add_argument("--out", help="Save prompt to text file")
    
    # Extractor
    p_extract = subparsers.add_parser("extract-frames", help="Extract frames from H3 mp4 output")
    p_extract.add_argument("video", help="Input MP4 video file")
    p_extract.add_argument("--out-dir", default="./frames", help="Output directory for frames")
    p_extract.add_argument("--fps", type=int, default=24, help="Target extraction framerate")
    
    # Strip Compiler
    p_strip = subparsers.add_parser("compile-strip", help="Compile extracted frames into a sprite strip")
    p_strip.add_argument("frame_dir", help="Directory containing extracted PNG frames")
    p_strip.add_argument("--out", default="sprite_strip.png", help="Output strip file")
    p_strip.add_argument("--chroma-key", action="store_true", help="Apply basic white-to-transparent chroma key")
    
    args = parser.parse_args()
    
    if args.command == "build-prompt":
        build_h3_prompt(args)
    elif args.command == "extract-frames":
        extract_frames(args)
    elif args.command == "compile-strip":
        compile_strip(args)

if __name__ == "__main__":
    main()
