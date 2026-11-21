#!/usr/bin/env python3
"""Turn the flat cat avatar into two aligned ASCII layers in data/portrait.json.

Run this by hand only when the avatar changes; the daily Action reuses the saved
result. Needs Pillow and numpy:

    python scripts/make_portrait.py path/to/avatar.png
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
COLS = 120
ROWS = 64
BODY_RAMP = ".:-=+*#%@"


def main(source):
    image = Image.open(source).convert("RGB")
    pixels = np.asarray(image, dtype=np.float32)
    corners = np.array([pixels[4, 4], pixels[4, -5], pixels[-5, 4], pixels[-5, -5]])
    background = np.median(corners, axis=0)
    subject = np.linalg.norm(pixels - background, axis=2) > 45

    ys, xs = np.where(subject)
    side = max(xs.max() - xs.min(), ys.max() - ys.min()) + 12
    cx = (xs.min() + xs.max()) // 2
    left = max(0, min(cx - side // 2, image.width - side))
    top = max(0, min(ys.max() + 1, image.height) - side)
    crop = image.crop((left, top, left + side, top + side))

    small = np.asarray(crop.resize((COLS, ROWS), Image.BOX), dtype=np.float32)
    distance = np.linalg.norm(small - background, axis=2)
    mask = Image.fromarray(((distance > 45) * 255).astype(np.uint8))
    softened = np.asarray(mask.filter(ImageFilter.GaussianBlur(2.2)), dtype=np.float32) / 255

    green = (small[..., 1] > small[..., 0] + 25) & (small[..., 1] > small[..., 2] + 25)
    pupils = np.zeros((ROWS, COLS), dtype=bool)
    grid_y, grid_x = np.mgrid[0:ROWS, 0:COLS]
    for side_mask in (grid_x < COLS / 2, grid_x >= COLS / 2):
        eye = green & side_mask
        if eye.any():
            ex, ey = grid_x[eye] / COLS, grid_y[eye] / ROWS
            center_x, center_y = (ex.min() + ex.max()) / 2, (ey.min() + ey.max()) / 2
            radius = max(ex.max() - ex.min(), ey.max() - ey.min()) / 2
            pupils |= np.hypot(grid_x / COLS - center_x, grid_y / ROWS - center_y) < radius * 0.86

    ink_rows, accent_rows = [], []
    for y in range(ROWS):
        ink, accent = [], []
        for x in range(COLS):
            r, g, b = small[y, x]
            ink_char = accent_char = " "
            if distance[y, x] > 45:
                if g > r + 25 and g > b + 25:  # eye rings
                    accent_char = "@"
                elif min(r, g, b) > 130:  # crescent moon
                    accent_char = "#"
                elif b > g + 14 and b > 38:  # collar
                    ink_char = "="
                elif pupils[y, x]:
                    ink_char = "@"
                else:
                    rim = 1 - min(1, max(0, (softened[y, x] - 0.5) * 2))
                    light = 0.2 + 0.14 * (y / ROWS) + 0.66 * rim
                    ink_char = BODY_RAMP[min(len(BODY_RAMP) - 1, int(light * len(BODY_RAMP)))]
            ink.append(ink_char)
            accent.append(accent_char)
        ink_rows.append("".join(ink).rstrip())
        accent_rows.append("".join(accent).rstrip())

    out = ROOT / "data" / "portrait.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(
        json.dumps({"cols": COLS, "rows": ROWS, "ink": ink_rows, "accent": accent_rows}, indent=0) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {out} ({COLS}x{ROWS})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: make_portrait.py <image>")
    main(sys.argv[1])
