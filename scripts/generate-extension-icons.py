#!/usr/bin/env python3
"""Generate Personal Layer extension icons."""
try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Install Pillow: pip install Pillow")
    exit(1)

import os

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "extension", "icons")
os.makedirs(OUTPUT_DIR, exist_ok=True)

COLORS = {
    "bg": (30, 30, 50),
    "circle": (100, 150, 255),
    "accent": (255, 200, 100)
}

def generate(size):
    img = Image.new("RGBA", (size, size), COLORS["bg"])
    draw = ImageDraw.Draw(img)
    padding = size // 6
    draw.ellipse([padding, padding, size - padding, size - padding], fill=COLORS["circle"])
    inner = size // 4
    draw.ellipse([inner, inner, size - inner, size - inner], fill=COLORS["accent"])
    return img

for sz in [16, 48, 128]:
    img = generate(sz)
    img.save(os.path.join(OUTPUT_DIR, f"icon{sz}.png"))
    print(f"Generated icon{sz}.png")
