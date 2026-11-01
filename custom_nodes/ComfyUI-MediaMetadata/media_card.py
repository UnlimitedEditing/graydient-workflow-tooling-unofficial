"""
Metadata card rendering (pure PIL).

Draws the probe report onto a single PNG-sized image: a header with the media
type and file name, the report body in monospace, an optional thumbnail of the
media itself, and a footer. No model, no GPU, no external font download --
the DejaVu fonts ship with this pack (see fonts/LICENSE_DEJAVU).
"""

import os

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except Exception as _pil_error:  # pragma: no cover - Pillow ships with ComfyUI
    Image = ImageDraw = ImageFont = None
    PIL_AVAILABLE = False
    PIL_IMPORT_ERROR = _pil_error

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

BG = (10, 10, 11)
HEADER_BG = (22, 22, 26)
FOOTER_BG = (16, 16, 19)
RULE = (42, 42, 48)
TEXT = (232, 232, 234)
DIM = (138, 143, 152)
FAINT = (82, 82, 90)

ACCENTS = {
    "video": (125, 211, 252),
    "image": (167, 243, 208),
    "audio": (253, 230, 138),
}
DEFAULT_ACCENT = (229, 229, 229)

MONO = os.path.join(FONT_DIR, "DejaVuSansMono.ttf")
MONO_BOLD = os.path.join(FONT_DIR, "DejaVuSansMono-Bold.ttf")
SANS_BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")

PAD = 26
HEADER_H = 86
FOOTER_H = 32
THUMB_W = 220


def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        try:
            return ImageFont.load_default(size=size)
        except Exception:
            return ImageFont.load_default()


def _text_width(draw, text, font):
    try:
        return draw.textlength(text, font=font)
    except Exception:
        return len(text) * 7


def _wrap_line(draw, text, font, max_w):
    """Break a single logical line so it fits max_w pixels (no word splitting
    except for tokens that are themselves too wide, e.g. a long URL)."""
    if _text_width(draw, text, font) <= max_w:
        return [text]
    out = []
    current = ""
    for word in text.split(" "):
        candidate = (current + " " + word).strip()
        if _text_width(draw, candidate, font) <= max_w or not current:
            if _text_width(draw, candidate, font) <= max_w:
                current = candidate
                continue
            # a single token wider than the line: hard-split it
            while _text_width(draw, candidate, font) > max_w and current:
                out.append(current)
                current = candidate[-max(1, len(candidate) // 2):]
                candidate = (current + " " + word).strip()
            current = candidate
        else:
            out.append(current)
            current = word
    if current:
        out.append(current)
    return out


def _fit_lines(draw, body, width, height):
    """
    Choose a font size, wrap the body to the card width, and return
    (font, line_height, wrapped_lines, needed_height).

    The card GROWS to fit the content rather than shrinking the text into
    illegibility: a metadata card that nobody can read is not a report. Only
    pathological input (thousands of lines) is clipped.
    """
    max_w = width - 2 * PAD
    longest = max((len(line) for line in body.split("\n")), default=0)
    size = 16 if longest <= 120 else (13 if longest <= 190 else 11)
    font = _font(MONO, size)
    line_h = int(size * 1.45)
    wrapped = []
    for raw in body.split("\n"):
        wrapped.extend(_wrap_line(draw, raw, font, max_w))

    needed = HEADER_H + PAD + len(wrapped) * line_h + PAD + FOOTER_H
    return font, line_h, wrapped, needed


def render_card(title, subtitle, body, thumbnail=None, media_type="unknown",
                width=1600, height=1000, footer="ComfyUI-MediaMetadata"):
    """Render the metadata card. Returns a PIL RGB image."""
    if not PIL_AVAILABLE:
        raise RuntimeError(f"Pillow is not available on this runner: {PIL_IMPORT_ERROR}")
    width = max(640, int(width))
    height = max(480, int(height))
    accent = ACCENTS.get(str(media_type).lower(), DEFAULT_ACCENT)

    # Measure first: the card grows to fit its content instead of shrinking
    # the text into illegibility.
    scratch = Image.new("RGB", (width, 10), BG)
    font, line_h, lines, needed = _fit_lines(ImageDraw.Draw(scratch), body, width, height)
    max_lines = 400
    if len(lines) > max_lines:
        dropped = len(lines) - max_lines
        lines = lines[: max_lines - 1] + [f"... {dropped} more line(s) -- the JSON report holds the full data"]
        needed = HEADER_H + PAD + len(lines) * line_h + PAD + FOOTER_H
    height = max(height, needed)

    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)

    # ── header band ──────────────────────────────────────────────────────────
    draw.rectangle([0, 0, width, HEADER_H], fill=HEADER_BG)
    draw.rectangle([0, HEADER_H - 3, width, HEADER_H], fill=accent)

    title_font = _font(SANS_BOLD, 30)
    sub_font = _font(MONO, 15)

    text_right = width - PAD
    if thumbnail is not None:
        try:
            tw, th = thumbnail.size
            scale = min((THUMB_W - 16) / max(tw, 1), (HEADER_H - 24) / max(th, 1))
            thumb = thumbnail.resize((max(1, int(tw * scale)), max(1, int(th * scale))), Image.LANCZOS)
            tx = width - PAD - thumb.size[0]
            ty = (HEADER_H - thumb.size[1]) // 2
            img.paste(thumb, (tx, ty))
            draw.rectangle([tx - 1, ty - 1, tx + thumb.size[0], ty + thumb.size[1]], outline=RULE, width=1)
            text_right = tx - 18
        except Exception:
            pass

    title = str(title or "MEDIA METADATA")
    while _text_width(draw, title, title_font) > max(120, text_right - PAD) and len(title) > 4:
        title = title[:-2]
        title += "…"
    draw.text((PAD, 16), title, font=title_font, fill=TEXT)

    sub = str(subtitle or "")
    while _text_width(draw, sub, sub_font) > max(120, text_right - PAD) and len(sub) > 4:
        sub = sub[:-2]
        sub += "…"
    draw.text((PAD, 54), sub, font=sub_font, fill=DIM)

    # ── body ─────────────────────────────────────────────────────────────────
    body_top = HEADER_H + PAD

    y = body_top
    for line in lines:
        stripped = line.strip()
        if stripped and set(stripped) == {"-"}:
            draw.line([(PAD, y + line_h // 2), (width - PAD, y + line_h // 2)], fill=RULE, width=1)
        else:
            # "Label : value" -- dim the label, brighten the value
            if ":" in line:
                label, _, value = line.partition(":")
                if label and not label.startswith(" ") and len(label) <= 24:
                    draw.text((PAD, y), label + ":", font=font, fill=DIM)
                    draw.text((PAD + _text_width(draw, label + ":", font), y), value, font=font, fill=TEXT)
                    y += line_h
                    continue
            draw.text((PAD, y), line, font=font, fill=TEXT)
        y += line_h

    # ── footer ───────────────────────────────────────────────────────────────
    draw.rectangle([0, height - FOOTER_H, width, height], fill=FOOTER_BG)
    draw.line([(0, height - FOOTER_H), (width, height - FOOTER_H)], fill=RULE, width=1)
    foot_font = _font(MONO, 12)
    draw.text((PAD, height - FOOTER_H + 9), footer, font=foot_font, fill=FAINT)

    return img
