#!/usr/bin/env python3
"""make_apk_icon.py: draw the launcher icon apk/res/drawable/icon.png from code (no third-party artwork).

The icon is an original, abstract motif: two forward chevrons on the launcher's dark background, in the
launcher's own colours (apk/res/values/colors.xml: lg_bg, lg_surface, lg_primary). No logo, character,
trademark or texture from any game. Pure Python (zlib + struct), deterministic: running it twice gives the
same bytes. Run from the repository root:

    python3 tools/make_apk_icon.py            # writes apk/res/drawable/icon.png
    python3 tools/make_apk_icon.py --check    # exit 1 if the committed icon differs from this drawing
"""
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'apk/res/drawable/icon.png'
SIZE = 256
SAMPLES = 4  # 4x4 supersampling per pixel (anti-aliasing)

BG_TOP = (0x1C, 0x1F, 0x27)     # lg_surface
BG_BOTTOM = (0x14, 0x16, 0x1C)  # lg_bg
BACK = (0x8A, 0x5E, 0x2E)       # lg_primary, darkened
FRONT = (0xE8, 0xA9, 0x5B)      # lg_primary
STROKE = 24.0                   # chevron line width, round caps and joint


def chevron(x0, apex):
    """A right-pointing chevron as two segments, centred on the icon's vertical axis."""
    top, mid, bottom = (x0, 76.0), (apex, 128.0), (x0, 180.0)
    return ((top, mid), (mid, bottom))


SHAPES = ((chevron(132.0, 180.0), FRONT), (chevron(80.0, 128.0), BACK))


def dist2_segment(px, py, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = min(1.0, max(0.0, t))
    ex, ey = ax + t * dx - px, ay + t * dy - py
    return ex * ex + ey * ey


def colour_at(x, y):
    for segments, colour in SHAPES:
        if min(dist2_segment(x, y, a, b) for a, b in segments) <= (STROKE / 2) ** 2:
            return colour
    t = y / SIZE
    return tuple(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t for i in range(3))


def render():
    rows = bytearray()
    step = 1.0 / SAMPLES
    for py in range(SIZE):
        rows.append(0)  # PNG filter type 0 (none)
        for px in range(SIZE):
            acc = [0.0, 0.0, 0.0]
            for sy in range(SAMPLES):
                for sx in range(SAMPLES):
                    c = colour_at(px + (sx + 0.5) * step, py + (sy + 0.5) * step)
                    for i in range(3):
                        acc[i] += c[i]
            rows.extend(int(round(v / (SAMPLES * SAMPLES))) for v in acc)
    return bytes(rows)


def png(raw):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    ihdr = struct.pack('>IIBBBBB', SIZE, SIZE, 8, 2, 0, 0, 0)  # 8-bit RGB, like the icon it replaces
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')


def main(argv):
    data = png(render())
    if '--check' in argv:
        if not OUT.is_file() or OUT.read_bytes() != data:
            print(f'ICON_DRIFT: {OUT.relative_to(ROOT)} is not the output of tools/make_apk_icon.py', file=sys.stderr)
            return 1
        print('ICON_OK')
        return 0
    OUT.write_bytes(data)
    print(f'wrote {OUT.relative_to(ROOT)} ({len(data)} bytes)')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
