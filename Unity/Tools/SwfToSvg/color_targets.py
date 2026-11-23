#!/usr/bin/env python3
"""Which pieces of a chip effect the user's Sitekick colour recolours.

corus.effects.base.BaseEffect extends BasePaint, and BasePaint paints every
display object whose instance name matches /fill/i (case-insensitive) with
`new ColorTransform(0,0,0,1,r,g,b,0)` -- a flat silhouette in the chosen colour
that keeps the clip's alpha.  Every effect class extends BaseEffect, so the rule
for a chip is simply: every placement named *fill* anywhere under the effect
symbol, at any depth, including the ones added later by timeline frames.

One pass over the library XML (8 s) instead of one `extract_effect.py` per chip
(about a minute each):

    python3 Tools/SwfToSvg/color_targets.py            # every chip, text report
    python3 Tools/SwfToSvg/color_targets.py --json ...  # machine readable

Each target also gets the exported-SVG group it lands in.  FFDec writes a
chip's art as a flat list of `<g id="xN_shapeK">` / `<g id="xN_spriteK">`
groups in draw order, one group per *occurrence*, counting shapes and sprites
separately in that same order -- so walking the display list depth-first gives
the group for any placement.
"""
import json
import os
import re
import subprocess
import sys

from lxml import etree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LIBRARY = os.path.join(ROOT, "..", "Source", "Effect Libraries", "effectlibrary1_250.swf")
XML = os.path.join(ROOT, "Temp", "color", "lib.xml")
FILL = re.compile("fill", re.I)


def library_xml():
    if not os.path.exists(XML):
        os.makedirs(os.path.dirname(XML), exist_ok=True)
        subprocess.run(["flatpak", "run", "--command=ffdec.sh",
                        "com.jpexs.decompiler.flash", "-swf2xml",
                        LIBRARY, XML], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return etree.parse(XML).getroot()


def places(sub):
    if sub is None:
        return []
    return [t for t in sub if (t.get("type") or "").startswith("PlaceObject")]


def index(root):
    """spriteId -> child tags, class name -> character id."""
    sprites = {}
    classes = {}
    for tag in root.iter("item"):
        kind = tag.get("type") or ""
        if kind == "DefineSpriteTag":
            sprites[int(tag.get("spriteId"))] = tag.find("subTags")
        elif kind == "SymbolClassTag":
            # FFDec splits the tag into parallel <tags> (character ids) and
            # <names> (class names) lists
            ids = [int(i.text) for i in tag.findall("tags/item")]
            names = [i.text for i in tag.findall("names/item")]
            classes.update(dict(zip(names, ids)))
    return sprites, classes


def walk(sprites, character, depth=0, path=()):
    """Pre-order over a sprite's children, depth order, one entry per occurrence."""
    for tag in places(sprites.get(character)):
        child = tag.get("characterId")
        if child is None:
            continue
        child = int(child)
        here = path + (child,)
        yield {
            "char": child,
            "name": tag.get("name") or "",
            "depth": int(tag.get("depth") or 0),   # the SWF's own depth
            "nest": depth + 1,                     # nesting under the effect
            "sprite": child in sprites,
            "path": here,
        }
        if child in sprites:
            yield from walk(sprites, child, depth + 1, here)


def targets(root, sprites, classes, chip):
    symbol = classes.get("corus.effects.effect_%06d" % chip)
    if symbol is None:
        return None
    found = []
    nodes = []
    shapes = sprites_seen = 0
    for node in walk(sprites, symbol):
        # the exported SVG numbers occurrences in this same order, with the
        # effect symbol itself left out of the count
        if node["sprite"]:
            group = "%s%d" % ("sprite", sprites_seen)
            sprites_seen += 1
        else:
            group = "%s%d" % ("shape", shapes)
            shapes += 1
        node["group"] = group
        nodes.append(node)
        if FILL.search(node["name"]):
            found.append(node)
    return {"chip": chip, "symbol": symbol, "nodes": nodes,
            "targets": found, "occurrences": shapes + sprites_seen}


def main(argv):
    root = library_xml()
    sprites, classes = index(root)
    chips = [int(a) for a in argv if a.isdigit()] or list(range(1, 101))
    report = []
    for chip in chips:
        result = targets(root, sprites, classes, chip)
        if result is None:
            print("chip %3d  no class" % chip)
            continue
        report.append(result)
        print("chip %3d  symbol %-5d fills %d" %
              (chip, result["symbol"], len(result["targets"])))
        for node in result["targets"]:
            print("    %-16s char %-5d %-6s depth %-3d group %-9s path %s"
                  % (node["name"], node["char"],
                     "sprite" if node["sprite"] else "shape",
                     node["depth"], node["group"],
                     "/".join(str(p) for p in node["path"])))
    if "--json" in argv:
        out = os.path.join(ROOT, "Logs", "color-targets.json")
        with open(out, "w") as handle:
            json.dump(report, handle, indent=1)
        print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1:])
