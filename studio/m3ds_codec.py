"""
M3DS Container Codec & Multi-Modal Media Converter
Extracts and converts embedded payloads (GLB 3D meshes, Gaussian Splat PLY point clouds,
YuE2 song score JSON) from Graydient steganography PNG images.
"""

import os
import io
import struct
import zlib
from pathlib import Path
from PIL import Image
import numpy as np

MAGIC = b"M3DS"
HEADER_SIZE = 40
FLAG_GZIP = 0x01

def is_m3ds_image(image_bytes: bytes) -> bool:
    """Fast check if image bytes represent an M3DS steganography PNG."""
    if len(image_bytes) < HEADER_SIZE:
        return False
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        rgb = np.array(img, dtype=np.uint8).tobytes()
        return len(rgb) >= HEADER_SIZE and rgb[:4] == MAGIC
    except Exception:
        return False

def decode_m3ds_bytes(png_bytes: bytes) -> tuple[str, bytes]:
    """
    Decode raw PNG bytes into (filename, payload_bytes).
    Handles M3DS version 1 header, CRC32 verification, and optional gzip decompression.
    """
    img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    rgb = np.array(img, dtype=np.uint8).tobytes()

    if len(rgb) < HEADER_SIZE:
        raise ValueError("Image too small to contain an M3DS header")

    magic = rgb[:4]
    if magic != MAGIC:
        raise ValueError(f"Not an M3DS image (magic is {magic!r}, expected {MAGIC!r})")

    version = rgb[4]
    flags = rgb[5]
    if version != 1:
        raise ValueError(f"Unsupported M3DS container version: {version}")

    (
        chunk_idx,
        chunk_cnt,
        blob_total,
        pay_len,
        pay_crc,
        orig_len,
        orig_crc,
        fname_len,
    ) = struct.unpack(">HHQIIQIH", rgb[6:40])

    pos = HEADER_SIZE
    filename = rgb[pos : pos + fname_len].decode("utf-8", errors="ignore")
    pos += fname_len
    payload = rgb[pos : pos + pay_len]

    if len(payload) != pay_len:
        raise ValueError(f"Payload truncated ({len(payload)} of {pay_len} bytes)")

    if zlib.crc32(payload) != pay_crc:
        raise ValueError("M3DS chunk CRC mismatch - pixels may have been compressed or altered")

    if flags & FLAG_GZIP:
        raw = zlib.decompress(payload, 16 + zlib.MAX_WBITS)
    else:
        raw = payload

    if len(raw) != orig_len:
        raise ValueError(f"Decoded size mismatch: got {len(raw)}, expected {orig_len}")
    if zlib.crc32(raw) != orig_crc:
        raise ValueError("Final M3DS CRC mismatch - file corrupted in transit")

    return filename, raw

def decode_m3ds_file(file_path: str | Path) -> tuple[str, bytes]:
    """Decode an M3DS PNG file on disk into (filename, payload_bytes)."""
    with open(file_path, "rb") as f:
        data = f.read()
    return decode_m3ds_bytes(data)

def unpack_and_save(file_path: str | Path, output_dir: str | Path = None) -> dict:
    """
    Inspects a file. If it contains an M3DS payload, unpacks and writes it to disk.
    Returns rich metadata dict describing the media format.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "rb") as f:
        data = f.read()

    if not is_m3ds_image(data):
        # Normal image
        return {
            "is_m3ds": False,
            "filename": file_path.name,
            "path": str(file_path),
            "media_type": "image/png" if file_path.suffix.lower() == ".png" else "image/jpeg",
            "size_bytes": len(data)
        }

    fname, payload = decode_m3ds_bytes(data)
    out_dir = Path(output_dir) if output_dir else file_path.parent
    os.makedirs(out_dir, exist_ok=True)

    # Sanitize output filename
    base_stem = file_path.stem
    clean_fname = fname if fname else f"{base_stem}_extracted.bin"
    target_path = out_dir / clean_fname

    with open(target_path, "wb") as f:
        f.write(payload)

    # Detect media type
    media_type = "application/octet-stream"
    category = "binary"
    if clean_fname.endswith(".glb") or payload[:4] == b"glTF":
        media_type = "model/gltf-binary"
        category = "3d_mesh"
    elif clean_fname.endswith(".ply") or payload[:4] == b"ply\n":
        media_type = "model/ply"
        category = "3d_pointcloud"
    elif clean_fname.endswith(".json") or (payload.strip().startswith(b"{") and payload.strip().endswith(b"}")):
        media_type = "application/json"
        category = "score_json"

    return {
        "is_m3ds": True,
        "original_png": str(file_path),
        "extracted_filename": clean_fname,
        "extracted_path": str(target_path),
        "size_bytes": len(payload),
        "media_type": media_type,
        "category": category
    }
