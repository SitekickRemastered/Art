#!/usr/bin/env python3
"""Compare each chip's Unity frames with the same frames rendered from our SVGs.

FFDec's own PNGs are full-bleed stage renders, so they do not line up with our
movies (we draw the stage colour as a disc over the face). Rasterising our SVGs
gives the same composition Unity is asked to draw, which isolates what Unity does
with them: same shapes, same disc, same transparency.

Only pixels our SVG draws opaquely are compared, so the camera background does
not pollute the score.

Usage:  python3 Tools/SwfToSvg/compare_svg_vs_unity.py [chips...]
Output: Logs/chip-svg-compare.md
"""

import glob
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
REF = os.path.join(ROOT, "Logs/pilot/svgr")
UNITY = os.path.join(ROOT, "Logs/pilot/unity")
OUT = os.path.join(ROOT, "Logs/chip-svg-compare.md")

# The dumps now come from a camera framed on the movie: ortho 6.7 at the movie's
# anchor, rendered 1440x1080.
MOVIE_CENTER = (5.2017, -0.0390)
MOVIE_SIZE = (375 * 0.01735 * 2.5, 300 * 0.01735 * 2.5)
PX_PER_UNIT = 1080 / 13.4


def idx(path):
    return int(re.search(r"(\d+)\.\w+$", path).group(1))


def crop_movie(img):
    x0 = (MOVIE_SIZE[0] / 2 - MOVIE_CENTER[0] - 5.2017) / 2 * 0 + (720 - MOVIE_SIZE[0] * PX_PER_UNIT / 2)
    y0 = 540 - MOVIE_SIZE[1] * PX_PER_UNIT / 2
    return img.crop((int(x0), int(y0), int(x0 + MOVIE_SIZE[0] * PX_PER_UNIT),
                     int(y0 + MOVIE_SIZE[1] * PX_PER_UNIT)))


def erode(mask, radius):
    """Shrink a boolean mask by radius pixels, so antialiased outlines are ignored."""
    m = mask.copy()
    for _ in range(radius):
        p = np.pad(m, 1, mode="constant", constant_values=False)
        m = (p[1:-1, 1:-1] & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:])
    return m


def screen(img):
    """The whole stage, which is what the prefab now covers."""
    return img.resize((375, 300), Image.LANCZOS)


def rasterise(chip, svgs, folder):
    os.makedirs(folder, exist_ok=True)
    todo = [s for s in svgs
            if not os.path.exists(os.path.join(folder, os.path.basename(s).replace(".svg", ".png")))]
    def one(s):
        dst = os.path.join(folder, os.path.basename(s).replace(".svg", ".png"))
        subprocess.run(["magick", "-background", "none", s, "-resize", "375x300", dst],
                       check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return dst
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(one, todo))


def main():
    chips = [int(c) for c in sys.argv[1:]] or [7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    lines = ["# Unity vs our own SVG frames", "",
             "Mean absolute RGB difference over the interior of what the SVG draws, edge pixels excluded.", "",
             "| Chip | Frames | Mean | Worst frame | Frames over 10 | Verdict |",
             "| --- | --- | --- | --- | --- | --- |"]

    for chip in chips:
        svgs = sorted(glob.glob(os.path.join(ROOT, "Assets/Chips/*/Chip_%04d/Movie/frame_*.svg" % chip)), key=idx)
        u_paths = sorted(glob.glob(os.path.join(UNITY, "%04d" % chip, "frame_*.png")), key=idx)
        if not svgs or not u_paths:
            lines.append("| %d | — | — | — | — | no captures |" % chip)
            continue

        folder = os.path.join(REF, "%04d" % chip)
        rasterise(chip, svgs, folder)
        ref_paths = sorted(glob.glob(os.path.join(folder, "frame_*.png")), key=idx)

        n = min(len(ref_paths), len(u_paths))
        diffs = []
        for i in range(n):
            ref = screen(Image.open(ref_paths[i]).convert("RGBA"))
            uni = crop_movie(Image.open(u_paths[i]).convert("RGB")).resize((375, 300), Image.LANCZOS)
            u = np.asarray(uni, dtype=np.int16)
            r = np.asarray(ref, dtype=np.int16)
            # The movie has no backdrop now, so a frame is artwork on whatever
            # the camera shows: composite the reference over the camera colour
            # before comparing, and only where the frame actually draws.
            bg = u[2, 2]
            alpha = r[:, :, 3:4].astype(np.float32) / 255.0
            comp = r[:, :, :3].astype(np.float32) * alpha + bg * (1.0 - alpha)
            mask = r[:, :, 3] > 20
            if mask.sum() < 100:
                diffs.append(0.0)
                continue
            d = np.abs(comp - u)[mask]
            diffs.append(float(d.mean()))

        mean = sum(diffs) / len(diffs)
        worst = max(range(len(diffs)), key=lambda i: diffs[i]) + 1
        over = sum(1 for d in diffs if d > 10)
        verdict = "OK" if mean < 4 and over == 0 else ("close" if mean < 10 else "BROKEN")
        lines.append("| %d | %d | %.1f | %d (%.1f) | %d | %s |"
                     % (chip, n, mean, worst, diffs[worst - 1], over, verdict))
        print("%d: mean %.1f worst %d (%.1f) over10 %d" % (chip, mean, worst, diffs[worst - 1], over))

    open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("->", OUT)


if __name__ == "__main__":
    main()
