"""Generate StarPulse branding PNGs for GitHub and the app favicon set.

Requires Pillow (dev/tooling only — not a runtime dependency).
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BRANDING = ROOT / "docs" / "branding"
PUBLIC = ROOT / "frontend" / "public"
ICONS = PUBLIC / "icons"

BG = (11, 15, 20, 255)
SURFACE = (18, 24, 32, 255)
RING = (59, 157, 255, 255)
RING_SOFT = (59, 157, 255, 90)
STAR = (231, 237, 243, 255)
PULSE = (52, 211, 153, 255)
TEXT = (231, 237, 243, 255)
MUTED = (139, 152, 168, 255)
ACCENT = (94, 179, 255, 255)


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _fill_rounded_rect(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _draw_mark(draw: ImageDraw.ImageDraw, cx: float, cy: float, scale: float) -> None:
    """Draw the StarPulse icon mark centered at (cx, cy). Scale 1.0 ~= 128px mark."""
    s = scale
    outer = 42 * s
    inner = 28 * s
    # Outer ring
    draw.ellipse((cx - outer, cy - outer, cx + outer, cy + outer), outline=RING, width=max(2, int(6 * s)))
    # Soft inner ring
    draw.ellipse((cx - inner, cy - inner, cx + inner, cy + inner), outline=RING_SOFT, width=max(1, int(3 * s)))
    # 4-point star
    points: list[tuple[float, float]] = []
    for i in range(8):
        ang = -math.pi / 2 + i * math.pi / 4
        r = (36 if i % 2 == 0 else 14) * s
        points.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))
    draw.polygon(points, fill=STAR)
    # Pulse core + side ticks
    core = max(2, 8 * s)
    draw.ellipse((cx - core, cy - core, cx + core, cy + core), fill=PULSE)
    tick_w = max(2, int(4 * s))
    draw.line((cx - 46 * s, cy, cx - 30 * s, cy), fill=PULSE, width=tick_w)
    draw.line((cx + 30 * s, cy, cx + 46 * s, cy), fill=PULSE, width=tick_w)


def _draw_icon_tile(size: int, *, maskable: bool = False) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = int(size * 0.12) if maskable else 0
    content = size - 2 * pad
    radius = int(content * 0.22)
    _fill_rounded_rect(draw, (pad, pad, size - pad - 1, size - pad - 1), radius, BG)
    cx = cy = size / 2
    scale = content / 128.0
    _draw_mark(draw, cx, cy, scale)
    return img


def _ico_from_png(png_bytes: bytes) -> bytes:
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png_bytes), 22)
    return header + entry + png_bytes


def make_logo_png(path: Path) -> None:
    """Horizontal logo: icon + StarPulse wordmark on a dark plate (README-safe).

    Renders the lockup, then sizes the plate to the visible ink with equal
    padding so the wordmark reads centered (a fixed wide canvas looks left-heavy).
    """
    mark_scale = 2.5
    gap = 56
    font = _font(128, bold=True)
    text = "StarPulse"
    pad_x, pad_y = 72, 56

    # Draw lockup on a generous transparent canvas
    canvas = 1600
    layer = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    tb = ld.textbbox((0, 0), text, font=font)

    mark_cx = 280.0
    mark_cy = canvas / 2
    _draw_mark(ld, mark_cx, mark_cy, mark_scale)

    text_x = mark_cx + 46 * mark_scale + gap
    text_y = mark_cy - (tb[1] + tb[3]) / 2
    ld.text((text_x, text_y), text, font=font, fill=TEXT)

    ink = layer.getbbox()
    if ink is None:
        raise RuntimeError("logo lockup produced no visible pixels")
    lockup = layer.crop(ink)
    lw, lh = lockup.size

    w = lw + 2 * pad_x
    h = lh + 2 * pad_y
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = max(24, min(w, h) // 6)
    _fill_rounded_rect(draw, (0, 0, w - 1, h - 1), radius, BG)
    img.alpha_composite(lockup, (pad_x, pad_y))
    img.save(path, "PNG")


def make_social_preview(path: Path) -> None:
    """GitHub social preview banner (1280×640)."""
    w, h = 1280, 640
    img = Image.new("RGBA", (w, h), BG)
    draw = ImageDraw.Draw(img)

    # Soft radial-ish accents via translucent ellipses
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.ellipse((-200, -280, 700, 420), fill=(59, 157, 255, 28))
    od.ellipse((750, 250, 1500, 900), fill=(52, 211, 153, 22))
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    # Top bar accent
    draw.rectangle((0, 0, w, 4), fill=RING)

    icon = _draw_icon_tile(160)
    icon_x, icon_y = 80, 120
    img.alpha_composite(icon, (icon_x, icon_y))
    icon_cy = icon_y + 160 / 2

    title_font = _font(92, bold=True)
    subtitle_font = _font(36, bold=False)
    features_font = _font(28, bold=False)
    creator_font = _font(24, bold=False)

    title = "StarPulse"
    title_tb = draw.textbbox((0, 0), title, font=title_font)
    title_x = icon_x + 160 + 40
    title_y = icon_cy - (title_tb[1] + title_tb[3]) / 2
    draw.text((title_x, title_y), title, font=title_font, fill=TEXT)
    draw.text((280, 240), "Self-hosted Starlink Monitoring", font=subtitle_font, fill=ACCENT)
    draw.text((280, 310), "Telemetry  •  Weather  •  Alerts  •  Outage Tracking", font=features_font, fill=MUTED)

    # Divider
    draw.line((80, 420, w - 80, 420), fill=(42, 52, 66, 255), width=2)

    draw.text((80, 460), "Created by mistercyber", font=creator_font, fill=MUTED)
    draw.text((80, 510), "FastAPI  ·  React  ·  SQLite  ·  Docker", font=creator_font, fill=(100, 114, 130, 255))

    # Right-side decorative pulse line
    pulse_y = 540
    draw.line((780, pulse_y, 860, pulse_y), fill=PULSE, width=4)
    draw.ellipse((870, pulse_y - 8, 886, pulse_y + 8), fill=PULSE)
    draw.line((896, pulse_y, 1180, pulse_y), fill=RING, width=3)

    img.convert("RGB").save(path, "PNG", optimize=True)


def main() -> None:
    BRANDING.mkdir(parents=True, exist_ok=True)
    ICONS.mkdir(parents=True, exist_ok=True)

    logo_path = BRANDING / "logo.png"
    social_path = BRANDING / "github-social-preview.png"
    make_logo_png(logo_path)
    make_social_preview(social_path)

    # App favicon / PWA set (same mark as branding icon)
    for size, name in [(192, "icon-192.png"), (512, "icon-512.png")]:
        _draw_icon_tile(size).save(ICONS / name, "PNG")
    _draw_icon_tile(512, maskable=True).save(ICONS / "icon-maskable-512.png", "PNG")

    fav64 = _draw_icon_tile(64)
    fav64.save(PUBLIC / "favicon.png", "PNG")
    # PNG-in-ICO
    import io

    buf = io.BytesIO()
    fav64.save(buf, "PNG")
    (PUBLIC / "favicon.ico").write_bytes(_ico_from_png(buf.getvalue()))

    # Keep frontend header logo SVG in sync with branding icon
    icon_svg = (BRANDING / "icon.svg").read_text(encoding="utf-8")
    (PUBLIC / "logo.svg").write_text(icon_svg, encoding="utf-8", newline="\n")
    _draw_icon_tile(192).save(PUBLIC / "logo-192.png", "PNG")

    # Also expose square icon under branding/
    _draw_icon_tile(512).save(BRANDING / "icon-512.png", "PNG")

    print(f"Wrote {logo_path}")
    print(f"Wrote {social_path}")
    print("Updated frontend favicon / PWA icons")


if __name__ == "__main__":
    main()
