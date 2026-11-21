#!/usr/bin/env python3
"""Build the frozen per-frame SWFs for a chip's Ruffle review.

This is the "review every chip in Ruffle" driver: for each chip it regenerates
the SWF the export was made from (chip 8's hand-authored patch, every other
chip's stopped-clip freeze), writes one frozen SWF per frame, and prints the
grid page that renders them plus the diff command.

    ruffle_review.py --ids 7-16 --out ../.tmp-review
    # open the printed ruffle_frames.html?base=... pages, screenshot each,
    # then:  ruffle_frames.py --diff <page>.png --first-frame 1 --cols 8
"""

import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ruffle_frames
import patch_chip8_tools as patch8
import patch_stopped_clips as patch_stop

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TMP = os.path.join(os.environ["HOME"], "sitekick-movies")


def source_xml(chip, work):
    """The XML the exported frames were rendered from."""
    if chip == 8:
        swf = patch8.patched(os.path.join(ROOT, "SWF", "chip_%04d.swf" % chip), work)
        return swf.replace(".swf", ".xml")
    swf = patch_stop.patched(os.path.join(ROOT, "SWF", "chip_%04d.swf" % chip), work,
                             verbose=False)
    frozen = swf.replace(".swf", ".xml")
    if os.path.exists(frozen):
        return frozen
    plain = os.path.join(work, "xml", "lib.src.xml")
    return plain if os.path.exists(plain) else os.path.join(work, "xml", "lib.xml")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="7-16")
    ap.add_argument("--out", default=os.path.join(ROOT, "..", ".tmp-review"))
    ap.add_argument("--stage", default="375x300")
    ap.add_argument("--cols", type=int, default=8)
    args = ap.parse_args()

    lo, hi = (int(v) for v in args.ids.split("-"))
    out_root = os.path.abspath(args.out)
    for chip in range(lo, hi + 1):
        movie = glob.glob(os.path.join(ROOT, "Assets", "Chips", "*", "Chip_%04d" % chip,
                                      "Movie", "frame_*.svg"))
        if not movie:
            continue
        frames = len(movie)
        work = os.path.join(TMP, "%04d" % chip)
        xml = source_xml(chip, work)
        out = os.path.join(out_root, "c%04d" % chip)
        os.makedirs(out, exist_ok=True)
        for frame in range(1, frames + 1):
            ruffle_frames.build(xml, os.path.join(out, "f%03d.swf" % frame), frame, out)
        base = "/.tmp-review/c%04d/f" % chip
        print("chip %d: %d frames  ->  ../Unity/Tools/SwfToSvg/ruffle_frames.html"
              "?base=%s&from=1&count=%d&cols=%d" % (chip, frames, base, frames, args.cols),
              flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
