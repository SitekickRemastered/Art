#!/usr/bin/env python3
"""Render the static chip icons in Ruffle, straight out of the library SWFs.

A static chip is not a movie: it is a `chip_NNNNNN` sprite inside
chipslibrary{1_500,501_1000,1001_1500}.swf, placed and drawn by sitekick.swf.
There is no per-chip SWF to play, so this builds one: each page is a one-frame
SWF on a big white stage that places a batch of those sprites side by side,
trimmed to just the definitions they reach.  Ruffle then draws the page and
`static_diff.py` compares every cell with the exported Sprites/chip_XXXX.svg.

The sprite's own bounding box comes from the shipped chip SVG: its viewBox is
the art in the sprite's local coordinates, so moving that box to a cell is all
the placement has to do.

    python3 static_review.py --ids 1-1375            # build the page SWFs
    python3 static_review.py --ids 1-12 --out /tmp/x # quick probe

Playing a page needs Ruffle; `static_review.html` does that, and with
`&renderer=canvas&raf=timer&post=pNNNN` it draws into a readable canvas and
POSTs the pixels to `shot_server.py`, so pages can be captured while the
browser window is minimised (a screenshot cannot).
"""
import argparse
import copy
import glob
import json
import os
import re
import subprocess
from lxml import etree

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FFDEC = ("flatpak", "run", "--command=ffdec.sh", "com.jpexs.decompiler.flash")
CHIP_LIB_RANGES = [(1, 500), (501, 1000), (1001, 1500)]
STAGE = (1600, 1200)          # stage in SWF units (1:1 with pixels)
MARGIN, GAP = 8, 8
TOP = 64                      # the app's badge sits over the page's top-left
ID_ATTRS = ("characterId", "characterID", "shapeId", "spriteId", "morphShapeId",
            "fontId", "fontID", "bitmapId")
KEEP = ("FileAttributesTag", "MetadataTag", "SetBackgroundColorTag")


def range_tag(ranges, i):
    for a, b in ranges:
        if a <= i <= b:
            return "%d_%d" % (a, b)
    return None


def view_box(svg_path):
    head = open(svg_path, encoding="utf-8", errors="ignore").read(1200)
    m = re.search(r'viewBox="([-\d. ]+)"', head)
    if not m:
        return None
    a = [float(v) for v in m.group(1).split()]
    return a if len(a) == 4 and a[2] > 0 and a[3] > 0 else None


def exported_icon(chip):
    hits = glob.glob(os.path.join(
        ROOT, "Assets/Chips/*/Chip_%04d/Sprites/chip_%04d.svg" % (chip, chip)))
    return hits[0] if hits else None


def index_chips(lo, hi):
    """chip id -> (library tag, sprite id, sprite dir, local viewBox)."""
    out = {}
    for d in glob.glob(os.path.join(ROOT, "Tools/out/chips_*/sprites/DefineSprite_*")):
        m = re.match(r"DefineSprite_(\d+)_chip_(\d{6})$", os.path.basename(d))
        if not m:
            continue
        chip, sid = int(m.group(2)), int(m.group(1))
        if not lo <= chip <= hi:
            continue
        icon = exported_icon(chip)
        vb = view_box(icon) if icon else None
        if not vb:
            vb = view_box(os.path.join(d, "1.svg"))
        if not vb:
            print(" no box for chip", chip)
            continue
        out[chip] = (range_tag(CHIP_LIB_RANGES, chip), sid, d, vb)
    return out


class Library:
    def __init__(self, tag):
        self.tag = tag
        self.path = os.path.join(ROOT, "Tools/out/chips_%s/lib.xml" % tag)
        self.root = etree.parse(self.path).getroot()
        self.template = None
        for item in self.root.iter("item"):
            if (item.get("type") or "").startswith("PlaceObject"):
                self.template = item
                break
        if self.template is None:
            raise SystemExit("no PlaceObject template in %s" % self.path)

    def page_tree(self, sids):
        """A copy of the library holding only what `sids` reach, one frame."""
        root = copy.deepcopy(self.root)
        tags = root.find("tags")
        defs = {}
        for item in list(tags):
            t = item.get("type") or ""
            if t not in KEEP and not t.startswith("Define"):
                tags.remove(item)
                continue
            if not t.startswith("Define"):
                continue
            for a in ID_ATTRS:
                v = item.get(a)
                if v is not None and v.lstrip("-").isdigit():
                    defs.setdefault(int(v), item)
                    break
        need, todo = set(), list(sids)
        while todo:
            item = defs.get(todo.pop())
            if item is None or id(item) in need:
                continue
            need.add(id(item))
            # every id-bearing attribute is a dependency, not just characterId:
            # a bitmap fill is `FILLSTYLE bitmapId`, so following only
            # characterId strips the image and Ruffle draws the shape without
            # it (chip 1211's disc lost its photo and read as a bare ring)
            for el in item.iter():
                for a in ID_ATTRS:
                    v = el.get(a)
                    if v is not None and v.lstrip("-").isdigit():
                        todo.append(int(v))
        for item in list(tags):
            if item.get("type", "").startswith("Define") and id(item) not in need:
                tags.remove(item)
        rect = root.find("displayRect")
        rect.set("Xmax", str(STAGE[0] * 20))
        rect.set("Ymax", str(STAGE[1] * 20))
        root.set("frameCount", "1")
        for item in tags:
            if item.get("type") == "SetBackgroundColorTag":
                bg = item.find("backgroundColor")
                if bg is not None:
                    bg.set("red", "255")
                    bg.set("green", "255")
                    bg.set("blue", "255")
        return root, tags


def place(template, depth, char, x, y):
    # built from scratch: cloning a library placement drags along clipDepth and
    # name/ratio leftovers, which clip the cells that follow it
    el = etree.Element("item", {
        "type": "PlaceObject2Tag", "forceWriteAsLong": "false",
        "depth": str(depth), "characterId": str(char),
        "placeFlagHasCharacter": "true", "placeFlagHasMatrix": "true",
        "placeFlagHasColorTransform": "false", "placeFlagHasClipDepth": "false",
        "placeFlagHasName": "false", "placeFlagHasRatio": "false",
        "placeFlagHasClipActions": "false", "placeFlagMove": "false"})
    # FFDec writes twips as plain integers plus the bit width the encoder needs
    tx, ty = int(round(x * 20.0)), int(round(y * 20.0))
    bits = max(1, max(abs(tx), abs(ty)).bit_length() + 1)
    etree.SubElement(el, "matrix", {
        "type": "MATRIX", "hasRotate": "false", "hasScale": "false",
        "nRotateBits": "0", "nScaleBits": "0", "nTranslateBits": str(bits),
        "translateX": str(tx), "translateY": str(ty)})
    return el


def layout_page(items):
    """Shelf-pack [(chip, sprite id, viewBox)] on the stage, or None."""
    x, y, row_h = MARGIN, TOP, 0.0
    cells = []
    for chip, sid, vb in items:
        vx, vy, vw, vh = vb
        if x + vw + MARGIN > STAGE[0]:
            x, y, row_h = MARGIN, y + row_h + GAP, 0.0
        if y + vh + MARGIN > STAGE[1]:
            return None
        cells.append({"chip": chip, "sprite": sid, "x": round(x, 2),
                      "y": round(y, 2), "w": round(vw, 2), "h": round(vh, 2)})
        x += vw + GAP
        row_h = max(row_h, vh)
    return cells


def write_page(lib, items, cells, path_base):
    root, tags = lib.page_tree([sid for _, sid, _ in items])
    for depth, ((chip, sid, vb), cell) in enumerate(zip(items, cells), start=1):
        tags.append(place(lib.template, depth, sid,
                          cell["x"] - vb[0], cell["y"] - vb[1]))
    etree.SubElement(tags, "item", type="ShowFrameTag", forceWriteAsLong="false")
    xml_path = path_base + ".xml"
    with open(xml_path, "wb") as f:
        f.write(etree.tostring(root, xml_declaration=True, encoding="UTF-8"))
    subprocess.run(FFDEC + ("-xml2swf", xml_path, path_base + ".swf"), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with open(path_base + ".json", "w", encoding="utf-8") as f:
        json.dump({"library": lib.tag, "stage": list(STAGE), "cells": cells}, f,
                  indent=1)
        f.write("\n")
    os.remove(xml_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="1-1500")
    ap.add_argument("--out", default=os.path.join(ROOT, "..", ".tmp-static"))
    args = ap.parse_args()
    lo, hi = (int(v) for v in args.ids.split("-"))
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)

    chips = index_chips(lo, hi)
    print("chips with a library sprite:", len(chips))
    pages = []
    for tag in ["%d_%d" % r for r in CHIP_LIB_RANGES]:
        todo = [c for c in sorted(chips) if chips[c][0] == tag]
        if not todo:
            continue
        lib = Library(tag)
        i = 0
        while i < len(todo):
            batch = [(c, chips[c][1], chips[c][3]) for c in todo[i:]]
            if layout_page(batch[:1]) is None:
                raise SystemExit("chip %d is bigger than the stage" % batch[0][0])
            lo_n, hi_n = 1, len(batch)
            while lo_n < hi_n:                    # largest prefix that fits
                mid = (lo_n + hi_n + 1) // 2
                if layout_page(batch[:mid]) is not None:
                    lo_n = mid
                else:
                    hi_n = mid - 1
            n = lo_n
            name = "p%04d" % (len(pages) + 1)
            cells = layout_page(batch[:n])
            write_page(lib, batch[:n], cells, os.path.join(out, name))
            print(" %s: lib %s chips %d-%d (%d per page)" % (
                name, tag, batch[0][0], batch[n - 1][0], len(cells)))
            pages.append({"page": name, "library": tag, "cells": cells})
            i += n
    with open(os.path.join(out, "pages.json"), "w", encoding="utf-8") as f:
        json.dump(pages, f, indent=1)
        f.write("\n")
    print("pages:", len(pages), "chips:", sum(len(p["cells"]) for p in pages), "->", out)


if __name__ == "__main__":
    main()
