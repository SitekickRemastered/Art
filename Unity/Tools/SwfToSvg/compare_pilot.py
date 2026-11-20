#!/usr/bin/env python3
"""Compare the pilot chip rendered by Ruffle with the same chip in Unity.

Ruffle gives the Flash-truth frames (Logs/pilot/ruffle/out/frame_NNN.png, the
375x300 stage at 2x). Unity gives what our clip actually draws
(Logs/pilot/unity/XXXX/frame_NNN.png, the whole 1440x1080 scene). The movie sits
in a known world rectangle, so the Unity capture is cropped to that rectangle and
scaled to the same size before the two are diffed.

Output: Logs/pilot/compare.txt (per frame metrics and best-match alignment) and
Logs/pilot/sheet.png (Ruffle over Unity for a few frames).

Usage:  python3 Tools/SwfToSvg/compare_pilot.py [chip]
"""

import glob
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PILOT = os.path.join(ROOT, "Logs/pilot")
OUT_TXT = os.path.join(PILOT, "compare.txt")
OUT_SHEET = os.path.join(PILOT, "sheet.png")

# the movie's rectangle in world space, and the scene's pixel projection
MOVIE_CENTER = (5.21, -0.10)
MOVIE_SIZE = (2.75, 2.20)
VIEW_W, VIEW_H = 14.6667, 11.0
SCENE_W, SCENE_H = 1440, 1080
PX_PER_UNIT = SCENE_W / VIEW_W


def unity_crop(img):
    x0 = (MOVIE_CENTER[0] - MOVIE_SIZE[0] / 2 + VIEW_W / 2) * PX_PER_UNIT
    y0 = (VIEW_H / 2 - (MOVIE_CENTER[1] + MOVIE_SIZE[1] / 2) + 5.5 - 5.5) * PX_PER_UNIT
    # camera is centred on the world origin with ortho size 5.5 (half height)
    y0 = (5.5 - (MOVIE_CENTER[1] + MOVIE_SIZE[1] / 2)) * PX_PER_UNIT
    w = MOVIE_SIZE[0] * PX_PER_UNIT
    h = MOVIE_SIZE[1] * PX_PER_UNIT
    return img.crop((int(round(x0)), int(round(y0)), int(round(x0 + w)), int(round(y0 + h))))


def load(source, size):
    im = source if isinstance(source, Image.Image) else Image.open(source)
    return im.convert("RGB").resize(size, Image.LANCZOS)


def main():
    chip = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    ruffle_dir = os.path.join(PILOT, "ruffle/out")
    unity_dir = os.path.join(PILOT, "unity", "%04d" % chip)
    ruffle_paths = sorted(glob.glob(os.path.join(ruffle_dir, "frame_*.png")))
    unity_paths = sorted(glob.glob(os.path.join(unity_dir, "frame_*.png")))
    if not ruffle_paths or not unity_paths:
        raise SystemExit("missing captures: %d ruffle, %d unity" % (len(ruffle_paths), len(unity_paths)))

    size = Image.open(ruffle_paths[0]).size
    ruffle = [load(p, size) for p in ruffle_paths]
    unity = [load(unity_crop(Image.open(p)), size) for p in unity_paths]
    n = min(len(ruffle), len(unity))

    ra = np.stack([np.asarray(im, dtype=np.int16) for im in ruffle[:n]])
    ua = np.stack([np.asarray(im, dtype=np.int16) for im in unity[:n]])

    lines = ["# Pilot comparison: chip %d" % chip, "",
             "Ruffle frames: %d, Unity frames: %d, compared: %d" % (len(ruffle), len(unity), n), "",
             "| Frame | Mean abs diff | Pixels > 24 | Best matching Ruffle frame |",
             "| --- | --- | --- | --- |"]

    worst = []
    for i in range(n):
        d = np.abs(ra[i] - ua[i])
        mad = float(d.mean())
        big = float((d.max(axis=2) > 24).mean() * 100.0)
        # which Ruffle frame looks most like this Unity frame?
        scores = np.abs(ra - ua[i]).mean(axis=(1, 2, 3))
        best = int(scores.argmin()) + 1
        lines.append("| %d | %.1f | %.0f%% | %d%s |"
                     % (i + 1, mad, big, best, "" if best == i + 1 else "  ←offset"))
        worst.append((mad, i + 1, big, best))

    lines.append("")
    lines.append("## Largest divergences")
    for mad, frame, big, best in sorted(worst, reverse=True)[:10]:
        lines.append("- frame %d: mean diff %.1f, %.0f%% of pixels differ, closest Ruffle frame %d"
                     % (frame, mad, big, best))

    # contact sheet of a handful of frames, Ruffle over Unity
    picks = [1, 10, 20, 30, 40, 50, n]
    cell = (360, 288)
    sheet = Image.new("RGB", (cell[0] * 2, cell[1] * len(picks) + 18 * len(picks)), (20, 20, 20))
    dr = ImageDraw.Draw(sheet)
    for row, f in enumerate(picks):
        y = row * (cell[1] + 18)
        dr.text((4, y + 2), "frame %d   left: Ruffle   right: Unity" % f, fill=(230, 230, 230))
        sheet.paste(ruffle[f - 1].resize(cell, Image.LANCZOS), (0, y + 16))
        sheet.paste(unity[f - 1].resize(cell, Image.LANCZOS), (cell[0], y + 16))

    sheet.save(OUT_SHEET)
    open(OUT_TXT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines[:8]))
    print("... %d frames compared -> %s" % (n, OUT_TXT))
    print("mean over all frames: %.1f" % float(np.abs(ra - ua).mean()))


if __name__ == "__main__":
    main()
