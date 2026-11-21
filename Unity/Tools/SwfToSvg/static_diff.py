#!/usr/bin/env python3
"""Compare rendered static chip pages with the exported chip SVGs.

`static_review.py` builds page SWFs and Ruffle renders them; this reads the
captured page screenshots (Logs/static/pNNNN.png), rasterises each chip's
shipped Sprites/chip_XXXX.svg at the same size and compares them cell by cell.

Reported per chip:
  grey  mean |difference| over the union of both inks (0-255)
  iou   overlap / union of the two inks (1.0 = same silhouette)
  inkR  ink pixels Ruffle drew, inkE ink pixels the export has

A cell is flagged when the silhouette disagrees (iou < 0.9) or the two inks are
unrelated everywhere (grey high on a similar amount of ink).

    python3 static_diff.py --pages ../.tmp-static/pages.json --shots Logs/static
"""
import argparse
import glob
import json
import os
import subprocess
import tempfile

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RSVG = "rsvg-convert"


def rasterise(svg, w, h, out):
    subprocess.run([RSVG, "-w", str(max(1, w)), "-h", str(max(1, h)), "-o", out, svg],
                   check=True)
    return Image.open(out).convert("RGBA")


def exported_icon(chip):
    hits = glob.glob(os.path.join(
        ROOT, "Assets/Chips/*/Chip_%04d/Sprites/chip_%04d.svg" % (chip, chip)))
    return hits[0] if hits else None


def view_box(svg):
    head = open(svg, encoding="utf-8", errors="ignore").read(1200)
    import re
    m = re.search(r'viewBox="([-\d. ]+)"', head)
    a = [float(v) for v in m.group(1).split()]
    return a


def ink(rgb, tol=12):
    """Non-white pixels: the chip art on the page's white stage."""
    return (rgb.astype(np.int16).min(axis=2) < 255 - tol)


def grow(mask):
    """One pixel of slack in every direction, for antialiasing edges."""
    m = mask.copy()
    m[1:, :] |= mask[:-1, :]
    m[:-1, :] |= mask[1:, :]
    m[:, 1:] |= mask[:, :-1]
    m[:, :-1] |= mask[:, 1:]
    return m


def compare(shot, cell, export_path, tmpdir):
    """Agreement of the two silhouettes with 1px of slack.

    These icons are 15-40 px, so a half-pixel of antialiasing on each side
    moves a third of a stroke: an exact overlap test calls good art broken.
    Ink is therefore matched against the other side's dilated ink.
    """
    x0, y0 = int(round(cell["x"])), int(round(cell["y"]))
    w, h = max(1, int(round(cell["w"]))), max(1, int(round(cell["h"])))
    if x0 + w + 1 > shot.width or y0 + h + 1 > shot.height:
        return None
    crop = np.asarray(shot.crop((x0 - 1, y0 - 1, x0 + w + 1, y0 + h + 1)).convert("RGBA"))
    out = os.path.join(tmpdir, "e.png")
    svg = rasterise(export_path, w, h, out)
    exp_full = np.asarray(svg)
    # cells land on fractional coordinates, so the render can sit up to a pixel
    # off the box the export raster was made for: take the best of 9 offsets
    best = None
    for dy in (0, 1, 2):
        for dx in (0, 1, 2):
            r = _score(crop[dy:dy + h, dx:dx + w], exp_full)
            if best is None or r[0] > best[0]:
                best = r
    ncc, grey, agree, miss_r, miss_e, ink_r, ink_e, mass = best
    return {"grey": round(grey, 2), "agree": round(agree, 4), "ncc": round(ncc, 4),
            "mass": round(mass, 3), "missR": miss_r, "missE": miss_e,
            "inkR": ink_r, "inkE": ink_e}


def _score(crop, exp):
    a_r = ink(crop[:, :, :3]) & (crop[:, :, 3] > 8)
    a_e = exp[:, :, 3] > 8
    if not a_r.any() and not a_e.any():
        return {"grey": 0.0, "agree": 1.0, "inkR": 0, "inkE": 0}
    miss_r = int((a_r & ~grow(a_e)).sum())     # Ruffle ink the export lacks
    miss_e = int((a_e & ~grow(a_r)).sum())     # export ink Ruffle does not draw
    total = int(a_r.sum()) + int(a_e.sum())
    agree = 1.0 - (miss_r + miss_e) / float(total) if total else 1.0
    grey_r = (crop[:, :, :3].astype(np.float32) @ [0.299, 0.587, 0.114])
    grey_e = (exp[:, :, :3].astype(np.float32) @ [0.299, 0.587, 0.114])
    grey_r = np.where(a_r, grey_r, 255.0)
    grey_e = np.where(a_e, grey_e, 255.0)
    union = a_r | a_e
    grey = float(np.abs(grey_r - grey_e)[union].mean()) if union.any() else 0.0
    # Ruffle antialiases thin strokes much softer than rsvg does, so ink mass is
    # not comparable; the normalised correlation of the art intensities is.
    v_r = (255.0 - grey_r).ravel()
    v_e = (255.0 - grey_e).ravel()
    denom = float(np.linalg.norm(v_r) * np.linalg.norm(v_e))
    ncc = float(np.dot(v_r, v_e) / denom) if denom else 1.0
    mass = float(v_r.sum() / v_e.sum()) if v_e.sum() else 0.0
    return (ncc, grey, agree, miss_r, miss_e, int(a_r.sum()), int(a_e.sum()), mass)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", default=os.path.join(ROOT, "..", ".tmp-static/pages.json"))
    ap.add_argument("--shots", default=os.path.join(ROOT, "Logs/static"))
    ap.add_argument("--out", default=os.path.join(ROOT, "..", ".tmp-static/diff.json"))
    args = ap.parse_args()
    pages = json.load(open(args.pages))
    results, missing = [], []
    with tempfile.TemporaryDirectory() as tmpdir:
        for page in pages:
            shot_path = os.path.join(args.shots, page["page"] + ".png")
            if not os.path.exists(shot_path):
                missing.append(page["page"])
                continue
            shot = Image.open(shot_path)
            for cell in page["cells"]:
                svg = exported_icon(cell["chip"])
                if not svg:
                    continue
                m = compare(shot, cell, svg, tmpdir)
                if m is None:
                    results.append({"chip": cell["chip"], "error": "off-page"})
                    continue
                m["chip"] = cell["chip"]
                m["page"] = page["page"]
                results.append(m)
            print(" %s: %d cells" % (page["page"], len(page["cells"])))
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)
        f.write("\n")
    ok = [r for r in results if "ncc" in r]
    bad = sorted(ok, key=lambda r: r["ncc"])
    ncc = np.array([r["ncc"] for r in ok])
    print("compared:", len(ok), "missing pages:", missing)
    print("ncc median %.3f  p10 %.3f  below 0.9: %d  below 0.7: %d" % (
        float(np.median(ncc)), float(np.percentile(ncc, 10)),
        int((ncc < 0.9).sum()), int((ncc < 0.7).sum())))
    for r in bad[:30]:
        print("  chip %4d ncc %.3f agree %.3f mass %.2f grey %6.2f" % (
            r["chip"], r["ncc"], r["agree"], r["mass"], r["grey"]))


if __name__ == "__main__":
    main()
