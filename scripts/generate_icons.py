"""Generate StarPulse favicon and PWA PNG icons from a simple drawn mark."""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "frontend" / "public"
ICONS = PUBLIC / "icons"


def _png(width: int, height: int, rgba_rows: list[bytes]) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + row for row in rgba_rows)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", ihdr),
            chunk(b"IDAT", zlib.compress(raw, 9)),
            chunk(b"IEND", b""),
        ]
    )


def _blend(dst: tuple[int, int, int, int], src: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    sr, sg, sb, sa = src
    dr, dg, db, da = dst
    a = sa / 255.0
    inv = 1.0 - a
    return (
        int(sr * a + dr * inv),
        int(sg * a + dg * inv),
        int(sb * a + db * inv),
        min(255, int(sa + da * inv)),
    )


def _set_pixel(buf: list[list[list[int]]], x: int, y: int, color: tuple[int, int, int, int]) -> None:
    h = len(buf)
    w = len(buf[0])
    if 0 <= x < w and 0 <= y < h:
        r, g, b, a = _blend(tuple(buf[y][x]), color)  # type: ignore[arg-type]
        buf[y][x] = [r, g, b, a]


def _fill_circle(buf: list[list[list[int]]], cx: float, cy: float, r: float, color: tuple[int, int, int, int]) -> None:
    rr = int(r) + 1
    for y in range(int(cy) - rr, int(cy) + rr + 1):
        for x in range(int(cx) - rr, int(cx) + rr + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                _set_pixel(buf, x, y, color)


def _stroke_circle(
    buf: list[list[list[int]]], cx: float, cy: float, r: float, width: float, color: tuple[int, int, int, int]
) -> None:
    outer = r + width / 2
    inner = max(0.0, r - width / 2)
    rr = int(outer) + 1
    for y in range(int(cy) - rr, int(cy) + rr + 1):
        for x in range(int(cx) - rr, int(cx) + rr + 1):
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            if inner * inner <= d2 <= outer * outer:
                _set_pixel(buf, x, y, color)


def _fill_rounded_rect(buf: list[list[list[int]]], size: int, radius: float, color: tuple[int, int, int, int]) -> None:
    for y in range(size):
        for x in range(size):
            dx = min(x, size - 1 - x)
            dy = min(y, size - 1 - y)
            if dx < radius and dy < radius:
                if (radius - dx) ** 2 + (radius - dy) ** 2 > radius * radius:
                    continue
            _set_pixel(buf, x, y, color)


def _fill_star(buf: list[list[list[int]]], cx: float, cy: float, outer: float, inner: float, color: tuple[int, int, int, int]) -> None:
    points: list[tuple[float, float]] = []
    for i in range(8):
        ang = -math.pi / 2 + i * math.pi / 4
        r = outer if i % 2 == 0 else inner
        points.append((cx + math.cos(ang) * r, cy + math.sin(ang) * r))

    min_x = int(min(p[0] for p in points)) - 1
    max_x = int(max(p[0] for p in points)) + 1
    min_y = int(min(p[1] for p in points)) - 1
    max_y = int(max(p[1] for p in points)) + 1

    def inside(x: float, y: float) -> bool:
        # Ray casting
        hit = False
        n = len(points)
        j = n - 1
        for i in range(n):
            xi, yi = points[i]
            xj, yj = points[j]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi):
                hit = not hit
            j = i
        return hit

    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            if inside(x + 0.5, y + 0.5):
                _set_pixel(buf, x, y, color)


def render_icon(size: int, *, maskable: bool = False) -> bytes:
    buf = [[[0, 0, 0, 0] for _ in range(size)] for _ in range(size)]
    pad = size * 0.12 if maskable else 0.0
    content = size - 2 * pad
    scale = content / 128.0
    ox = pad
    oy = pad

    def m(v: float) -> float:
        return ox + v * scale

    bg = (11, 15, 20, 255)
    ring = (59, 157, 255, 255)
    star = (231, 237, 243, 255)
    pulse = (52, 211, 153, 255)

    _fill_rounded_rect(buf, size, size * 0.22, bg)
    _stroke_circle(buf, m(64), m(64), 42 * scale, max(2.0, 6 * scale), ring)
    _stroke_circle(buf, m(64), m(64), 28 * scale, max(1.0, 3 * scale), (59, 157, 255, 90))
    _fill_star(buf, m(64), m(64), 36 * scale, 14 * scale, star)
    _fill_circle(buf, m(64), m(64), max(2.0, 8 * scale), pulse)

    rows = [bytes(px for pixel in row for px in pixel) for row in buf]
    return _png(size, size, rows)


def _ico(png_bytes: bytes) -> bytes:
    # Single-image PNG-in-ICO
    count = 1
    header = struct.pack("<HHH", 0, 1, count)
    # width/height 0 means 256
    entry = struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png_bytes), 22)
    return header + entry + png_bytes


def main() -> None:
    ICONS.mkdir(parents=True, exist_ok=True)
    (PUBLIC / "logo-192.png").write_bytes(render_icon(192))
    (ICONS / "icon-192.png").write_bytes(render_icon(192))
    (ICONS / "icon-512.png").write_bytes(render_icon(512))
    (ICONS / "icon-maskable-512.png").write_bytes(render_icon(512, maskable=True))
    favicon_png = render_icon(64)
    (PUBLIC / "favicon.png").write_bytes(favicon_png)
    (PUBLIC / "favicon.ico").write_bytes(_ico(favicon_png))
    print("Wrote logo and icon assets under frontend/public/")


if __name__ == "__main__":
    main()
