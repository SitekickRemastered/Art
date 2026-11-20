#!/usr/bin/env python3
"""Score every rebuilt chip's Unity frames against FFDec's own frame renders.

FFDec's PNG export of a chip SWF is the reference: for chip 12 it matches Ruffle
on all 66 frames (mean diff 0.2/255), so anything Unity adds or loses shows up
here as a difference from the truth.

Usage:  python3 Tools/SwfToSvg/compare_chips.py [chips...]
Output: Logs/chip-movie-compare.md
"""

import glob
import os
import re
import sys

import numpy as np
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
UNITY = os.path.join(ROOT, "Logs/pilot/unity")
TRUTH = os.path.join(os.environ["HOME"], "sitekick-movies")
OUT = os.path.join(ROOT, "Logs/chip-movie-compare.md")

# the movie rectangle in the gallery camera, from ChipMovieBuilder's registration
MOVIE_CENTER = (5.2043, -0.0976)
MOVIE_SIZE = (2.575, 2.372)
PX_PER_UNIT = 1440 / 14.6667


def idx(path):
    return int(re.search(r"(\d+)\.\w+$", path).group(1))


def crop_movie(img):
    x0 = (MOVIE_CENTER[0] - MOVIE_SIZE[0] / 2 + 14.6667 / 2) * PX_PER_UNIT
    y0 = (5.5 - (MOVIE_CENTER[1] + MOVIE_SIZE[1] / 2)) * PX_PER_UNIT
    return img.crop((int(x0), int(y0), int(x0 + MOVIE_SIZE[0] * PX_PER_UNIT),
                     int(y0 + MOVIE_SIZE[1] * PX_PER_UNIT)))


def main():
    chips = [int(c) for c in sys.argv[1:]] or [7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    lines = ["# Chip movie comparison (Unity vs FFDec's frame renders)", "",
             "Mean absolute RGB difference over the movie rectangle, 0-255.", "",
             "| Chip | Frames | Mean | Worst frame | Frames over 20 | Verdict |",
             "| --- | --- | --- | --- | --- | --- |"]

    for chip in chips:
        u_paths = sorted(glob.glob(os.path.join(UNITY, "%04d" % chip, "frame_*.png")), key=idx)
        t_paths = sorted(glob.glob(os.path.join(TRUTH, "%04d" % chip, "png", "*.png")), key=idx)
        if not u_paths or not t_paths:
            lines.append("| %d | — | — | — | — | no captures |" % chip)
            continue

        n = min(len(u_paths), len(t_paths))
        diffs = []
        for i in range(n):
            u = crop_movie(Image.open(u_paths[i]).convert("RGB")).resize((375, 300), Image.LANCZOS)
            t = Image.open(t_paths[i]).convert("RGB").resize((375, 300), Image.LANCZOS)
            diffs.append(float(np.abs(np.asarray(u, dtype=np.int16) - np.asarray(t, dtype=np.int16)).mean()))

        mean = sum(diffs) / len(diffs)
        worst = max(range(len(diffs)), key=lambda i: diffs[i]) + 1
        over = sum(1 for d in diffs if d > 20)
        verdict = "OK" if mean < 8 and over == 0 else ("close" if mean < 20 else "BROKEN")
        lines.append("| %d | %d | %.1f | %d (%.1f) | %d | %s |"
                     % (chip, n, mean, worst, diffs[worst - 1], over, verdict))

    open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
