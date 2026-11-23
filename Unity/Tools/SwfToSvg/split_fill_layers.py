#!/usr/bin/env python3
"""Split a chip's exported art into the layers the Sitekick colour needs.

Flash paints every clip whose instance name matches /fill/ with a flat colour
(`new ColorTransform(0,0,0,1,r,g,b,0)`), so those pieces cannot share a sprite
with the rest of the drawing: they get their own renderer, which is the one
Unity tints.

FFDec writes a chip's drawing as nested `<g id="xN_shapeK">` / `<g id="xN_spriteK">`
groups in draw order, one per occurrence, so a fill clip is an element of that
tree.  `color_targets.py` walks the same display list and names them.

The split has to keep Flash's draw order exactly -- a fill can sit between two
other pieces (chip 45's guitar) -- so this cuts the drawing into *runs*: every
maximal stretch of the drawing that is either all fill or all not-fill becomes
one layer, in the original order.  A layer is a pruned copy of the tree with the
same width, height, viewBox and `<defs>`, keeping the ancestor groups (and their
transforms) around each piece, so every layer imports at the same size and lands
in exactly the same place.

    python3 Tools/SwfToSvg/split_fill_layers.py 45
    python3 Tools/SwfToSvg/split_fill_layers.py 45 --svg frame_001.svg --fills sprite1 --out ...

Each run is written as `<prefix>_L<n>.svg`, and `<prefix>.layers.json` lists the
runs in draw order with whether each one is a fill and whether it is tinted.

Two things every layer has to carry, because Unity's SVG importer measures the
sprite from the layer's *own* geometry (clipPath and the viewBox are ignored;
see `svg_bbox.py`):

* an invisible anchor rect over the source drawing's geometry bbox, so every
  layer imports to the same rect and the same pivot and therefore lands where
  the original renderer is -- without it each layer is centred on its own ink
  and the pieces drift apart;
* the site's shade math, baked in.  Flash's `paint(clip)` turns a clip into a
    flat colour, but a *shaded* piece is a grey or half-transparent overlay, and
  tinting is a multiply: grey * colour is a darker shade of the colour, which is
  what the site does with `paint(clip,"shadow")` (`rvalue - 20` on the
  multiplier) instead of washing the piece towards grey.  So a layer that holds
  nothing but greys -- shading, and the black outlines that the multiply leaves
  black -- is tinted as well, which is what lets chip 73's shadow follow the
  colour; at the default white the multiply is the identity.
"""
import argparse
import copy
import json
import os
import re
import sys

from lxml import etree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import svg_bbox as bbox

W = "{http://www.w3.org/2000/svg}"
G = "{http://www.w3.org/2000/svg}g"
# drawings only: clip paths, gradients and the like are definitions, and every
# layer gets its own copy of them in `split` below
DEFINITIONS = {"defs", "clipPath", "mask", "linearGradient", "radialGradient",
               "pattern", "style", "symbol", "marker", "filter"}


def short(element):
    """x4_sprite1 -> sprite1: the export's serial prefix is not interesting."""
    return (element.get("id") or "").split("_", 1)[-1]


def is_group(element):
    return element.tag == G


def prune(node, keep):
    """A copy of `node` holding only the children `keep` (in that order)."""
    clone = copy.deepcopy(node)
    for child in list(clone):
        clone.remove(child)
    for child in keep:
        clone.append(child)
    return clone


def shading(element):
    """True for a piece the colour darkens: a fill at less than full opacity.

    Opaque art outside a fill clip is *not* painted by the effect -- chip 74's
    feet, chip 73's shoulder knob -- so it must keep its own greys instead of
    being tinted.  A translucent piece is a shade drawn over the fill, and
    tinting it is what turns it into a darker shade of the colour.
    """
    tag = etree.QName(element).localname
    if tag != "path":
        return None
    fill = element.get("fill")
    opacity = element.get("fill-opacity")
    for decl in (element.get("style") or "").split(";"):
        key, _, value = decl.partition(":")
        if key.strip() == "fill":
            fill = value.strip()
        elif key.strip() == "fill-opacity":
            opacity = value.strip()
    if fill in (None, "none"):
        return False
    return float(opacity) < 0.999 if opacity else False


def classify(node):
    """True/False when every piece under `node` agrees, None when mixed."""
    found = set()
    for element in node.iter():
        value = shading(element)
        if value is not None:
            found.add(value)
    if not found:
        return False
    return found.pop() if len(found) == 1 else None


def runs(node, ids, inside, hand=None):
    """[(cls, [elements])] for the drawing `node`, in draw order.

    `cls` is True for a piece the colour reaches, "hand" for the copy of one
    that keeps its own art inside the hand cut, and False for art the colour
    never touches.  A fill clip takes its whole subtree with it (Flash paints it
    flat); anything else is cut by whether its pieces are shading, and each
    piece keeps the groups above it.

    The hand copy is emitted *in place*, right after the piece it copies: a
    separate layer at the end would draw the hand's white fill over the black
    outlines that belong above it.
    """
    out = []
    for child in node:
        if is_group(child):
            if inside or short(child) in ids:
                out.append((True, [copy.deepcopy(child)]))
                if hand:
                    out.append(("hand", [copy.deepcopy(child)]))
                continue
            kind = classify(child)
            if kind is True:
                out.append((True, [copy.deepcopy(child)]))
                if hand:
                    out.append(("hand", [copy.deepcopy(child)]))
            elif kind is False:
                out.append((False, [copy.deepcopy(child)]))
            else:
                for k, elements in runs(child, ids, False, hand):
                    out.append((k, [prune(child, elements)]))
        elif etree.QName(child).localname in DEFINITIONS:
            continue
        else:
            # a path (or anything else this group draws itself) sits in the run
            # at the point it is written
            tinted = bool(inside or shading(child))
            out.append((tinted, [copy.deepcopy(child)]))
            if tinted and hand:
                out.append(("hand", [copy.deepcopy(child)]))
    return out


def merge(chunks):
    """Fold neighbouring runs of the same kind into one layer."""
    merged = []
    for kind, elements in chunks:
        if merged and merged[-1][0] == kind:
            merged[-1][1].extend(elements)
        else:
            merged.append((kind, list(elements)))
    return merged


def anchor(root, box):
    """An invisible rect over the source bbox, so the import rect is the same."""
    x0, y0, x1, y1 = box
    rect = etree.Element(W + "rect")
    rect.set("x", "%.6f" % x0)
    rect.set("y", "%.3f" % y0)
    rect.set("width", "%.6f" % (x1 - x0))
    rect.set("height", "%.6f" % (y1 - y0))
    rect.set("fill", "#000000")
    rect.set("fill-opacity", "0.001")
    return rect


def cut_polygons(box, spec):
    """(hand, rest) polygons for a cut spec, in user units.

    `spec` is "x>87" / "y>57" for an axis-aligned cut, or "slope m,b" for the
    line y = m*x + b with the hand on the lower side -- chip 73's wrist runs
    diagonally, and a straight horizontal cut there swallows half the forearm.
    Both polygons are clipped to the drawing's geometry bbox, so they tile it.
    """
    x0, y0, x1, y1 = box
    if spec.startswith("slope"):
        m, b = (float(v) for v in spec.split()[1].split(","))
        # the line where it crosses the left and right edges of the box
        yl, yr = m * x0 + b, m * x1 + b
        hand = [(x0, yl), (x1, yr), (x1, y1), (x0, y1)]
        rest = [(x0, yl), (x1, yr), (x1, y0), (x0, y0)]
        return [hand], [rest]
    axis, value = spec[0], float(spec[2:])
    if axis == "x":
        hand, rest = ((value, y0, x1 - value, y1 - y0), (x0, y0, value - x0, y1 - y0))
    else:
        hand, rest = ((x0, value, x1 - x0, y1 - value), (x0, y0, x1 - x0, value - y0))
    if "<" in spec:
        hand, rest = rest, hand
    return [hand], [rest]


def polygon_rects(shapes):
    """[(x, y, w, h)] when every shape is an axis-aligned rect, else None."""
    if not all(len(shape) == 4 and not isinstance(shape[0], tuple) for shape in shapes):
        return None
    for x, y, w, h in shapes:
        if w <= 0 or h <= 0:
            return None
    return shapes


def polygon_points(polygons):
    return [[(x, y) for x, y in shape] for shape in polygons]


def clip_box(parent, shapes, name):
    """defs > clipPath > shape(s), on `parent`, and the url to reference it."""
    defs = etree.SubElement(parent, W + "defs")
    clip = etree.SubElement(defs, W + "clipPath")
    clip.set("id", name)
    rects = polygon_rects(shapes)
    if rects is not None:
        for rect in rects:
            shape = etree.SubElement(clip, W + "rect")
            for key, value in zip(("x", "y", "width", "height"), rect):
                shape.set(key, "%.4f" % value)
        return "url(#%s)" % name
    for points in polygon_points(shapes):
        shape = etree.SubElement(clip, W + "path")
        shape.set("d", "M" + " L".join("%.4f %.4f" % p for p in points) + " Z")
    return "url(#%s)" % name


def split(svg_path, fills, out_prefix, manifest_dir=None, hand=None):
    root = etree.parse(svg_path).getroot()
    box = bbox.bbox(svg_path)
    ids = set(fills)
    present = {short(g) for g in root.iter(G) if g.get("id")}
    missing = [i for i in ids if i not in present]
    if missing:
        raise SystemExit("%s: no group for %s" % (svg_path, ", ".join(sorted(missing))))

    hand_shapes, rest = cut_polygons(box, hand) if hand else (None, None)
    chunks = merge(runs(root, ids, False, hand))
    layers = []
    for index, (kind, elements) in enumerate(chunks):
        out = etree.Element(root.tag, nsmap=root.nsmap)
        for key, value in root.attrib.items():
            out.set(key, value)
        for child in root:
            if not is_group(child):
                out.append(copy.deepcopy(child))    # defs, gradients, ...
        if box:
            out.append(anchor(root, box))
        if hand and kind is True:
            # this piece takes the colour: everything but the hand
            group = etree.SubElement(out, G)
            group.set("clip-path", clip_box(out, rest, "rest"))
            for child in elements:
                group.append(child)
        elif kind == "hand":
            # the hand's own copy of it, drawn as the art has it
            group = etree.SubElement(out, G)
            group.set("clip-path", clip_box(out, hand_shapes, "hand"))
            for child in elements:
                group.append(child)
        else:
            for child in elements:
                out.append(child)
        # Flash flattens a painted clip, so a fill run is recoloured whatever
        # is in it; a run of shading follows the colour by darkening it (the
        # tint is a multiply, so grey * colour is a darker colour).  Opaque art
        # outside a fill clip is not painted at all and keeps its own greys.
        tint = kind is True
        path = "%s_L%d.svg" % (out_prefix, index)
        etree.ElementTree(out).write(path, xml_declaration=True, encoding="UTF-8")
        layers.append({"layer": "L%d" % index, "fill": kind is True,
                       "tint": bool(tint), "hand": kind == "hand", "path": path})

    manifest_dir = manifest_dir or os.path.dirname(out_prefix)
    os.makedirs(manifest_dir, exist_ok=True)
    manifest = os.path.join(manifest_dir,
                            os.path.basename(out_prefix) + ".layers.json")
    with open(manifest, "w") as handle:
        json.dump(layers, handle, indent=1)
    return layers, manifest


def default_svg(chip):
    return os.path.join(ROOT, "Assets", "Chips", "0001-0100",
                        "Chip_%04d" % chip, "Sprites", "chip_%04d_effect.svg" % chip)


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("chip", nargs="?", type=int)
    parser.add_argument("--svg")
    parser.add_argument("--fills", help="comma separated group names, e.g. sprite1")
    parser.add_argument("--out")
    parser.add_argument("--json", default=os.path.join(ROOT, "Logs", "color-targets.json"))
    parser.add_argument("--hand", help="keep this side as drawn, e.g. x>87 or y>57")
    args = parser.parse_args(argv)

    targets = json.load(open(args.json))
    chip = [t for t in targets if t["chip"] == args.chip][0]
    fills = args.fills.split(",") if args.fills else [t["group"] for t in chip["targets"]]
    svg = args.svg or default_svg(args.chip)
    out = args.out or os.path.splitext(svg)[0]
    layers, manifest = split(svg, fills, out, hand=args.hand)
    for entry in layers:
        print("wrote", entry["path"], "fill" if entry["fill"] else ("tint" if entry["tint"] else ""))
    print("wrote", manifest)


if __name__ == "__main__":
    main(sys.argv[1:])
