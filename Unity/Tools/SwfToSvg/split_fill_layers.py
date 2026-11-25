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


def grey_stroke(element, low=30, high=225):
    """A stroke drawn in grey: the crease and edge lines the effect tints too.

    These lines are inside the fill clip in the SWF -- `paint()` multiplies
    them, which is why Ruffle shows them as a darker shade of the colour and
    not as a grey line over it.  FFDec exports them flat, with no clip around
    them, so without this they sit on the colour untouched (chip 72's sleeve
    band, 73's forearm creases, 74's shin seams).  Black outlines are not grey
    and stay black; so do the opaque grey *fills* that are really art outside
    the clip (74's boots).
    """
    stroke = element.get("stroke")
    if not stroke or stroke in ("none", "#000000"):
        return False
    match = re.match(r"#([0-9a-fA-F]{2})([0-9a-fA-F]{2})([0-9a-fA-F]{2})$", stroke)
    if not match:
        return False
    r, g, b = (int(v, 16) for v in match.groups())
    return r == g == b and low <= r <= high


def shading(element, strokes=False):
    """True for a piece the colour darkens: a fill at less than full opacity.

    Opaque art outside a fill clip is *not* painted by the effect -- chip 74's
    feet, chip 73's shoulder knob -- so it must keep its own greys instead of
    being tinted.  A translucent piece is a shade drawn over the fill, and
    tinting it is what turns it into a darker shade of the colour.

    `strokes` also counts a grey stroke, for the chips whose outlines FFDec
    exported without the clip they are drawn inside (see `grey_stroke`).
    """
    tag = etree.QName(element).localname
    if tag != "path":
        return None
    if strokes and grey_stroke(element):
        return True
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


def classify(node, strokes=False):
    """True/False when every piece under `node` agrees, None when mixed."""
    found = set()
    for element in node.iter():
        value = shading(element, strokes)
        if value is not None:
            found.add(value)
    if not found:
        return False
    return found.pop() if len(found) == 1 else None


def runs(node, ids, inside, strokes=False):
    """[(tinted, [elements])] for the drawing `node`, in draw order.

    `tinted` is True for a piece the colour reaches and False for art the
    colour never touches.  A fill clip takes its whole subtree with it (Flash
    paints it flat); anything else is cut by whether its pieces are shading, and
    each piece keeps the groups above it.  The hand cut is the caller's job: it
    copies a whole tinted run, so the pieces of one run stay together.
    """
    out = []
    for child in node:
        if is_group(child):
            if inside or short(child) in ids:
                out.append((True, [copy.deepcopy(child)]))
                continue
            kind = classify(child, strokes)
            if kind is None:
                for k, elements in runs(child, ids, False, strokes):
                    out.append((k, [prune(child, elements)]))
            else:
                out.append((kind, [copy.deepcopy(child)]))
        elif etree.QName(child).localname in DEFINITIONS:
            continue
        else:
            # a path (or anything else this group draws itself) sits in the run
            # at the point it is written
            out.append((bool(inside or shading(child, strokes)), [copy.deepcopy(child)]))
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


def hand_parts(root, spec):
    """The shapes that make up the hand side of a cut, from a `hand` spec.

    A spec is one or more shapes separated by `;`, each one either

      * `outline shape2/7/3` -- the drawing's *own* subpath: group `shape2`,
        its 8th path, that path's 4th subpath (0-based).  Auto-closed, so an
        open outline becomes the region it encloses.  This is the precise way
        to cut a hand off: the seam is the black boundary the art already
        draws, so no straight line can slice the mass beside it;
      * `rect x,y,w,h` -- user units, for a plain slab;
      * `poly x,y x,y ...` -- a closed polygon, for a seam no path follows;
      * `x>87` / `y<40` / `slope m,b` -- the old axis and line cuts (hand on
        the right/below the line), kept for a quick cut.

    Several shapes are unioned.  Their outer extent does not matter: the hand
    copy is only drawn where the run has art, so a shape may overshoot the
    drawing freely -- it just must not reach into the mass.
    """
    shapes = []
    for part in (p.strip() for p in spec.split(";")):
        if not part:
            continue
        kind, _, rest = part.partition(" ")
        if kind == "outline":
            group, path, sub = rest.split("/")
            shapes.append(("path", outline_path(root, group, int(path), int(sub))))
        elif kind == "rect":
            x, y, w, h = (float(v) for v in rest.split(","))
            shapes.append(("rect", (x, y, w, h)))
        elif kind == "poly":
            points = [tuple(float(v) for v in pair.split(",")) for pair in rest.split()]
            shapes.append(("path", "M" + " L".join("%.4f %.4f" % p for p in points) + " Z"))
        elif kind == "slope" or kind[0] in "xy":
            shapes.extend(line_cut(part))
        else:
            raise SystemExit("unknown hand shape " + part)
    return shapes


def outline_path(root, group, path_index, sub_index):
    """The `d` of one subpath of one path of one exported group, closed."""
    for node in root.iter(G):
        if short(node) != group:
            continue
        paths = [c for c in node if etree.QName(c).localname == "path"]
        subpaths = [s for s in re.split(r"(?=M)", paths[path_index].get("d") or "")
                    if s.strip()]
        d = subpaths[sub_index].strip()
        return d if d.rstrip().upper().endswith("Z") else d + " Z"
    raise SystemExit("no group %s" % group)


def line_cut(spec):
    """The old straight cuts, as shapes: hand is right of `x>` / below `y>`.

    Kept for a quick cut on art with no boundary to follow.  `slope m,b` puts
    the hand below the line y = m*x + b.
    """
    # a half-plane is written as a huge rectangle, in the art's own units
    far = 10000.0
    if spec.startswith("slope"):
        m, b = (float(v) for v in spec.split()[1].split(","))
        points = [(-far, m * -far + b), (far, m * far + b), (far, far), (-far, far)]
        return [("path", "M" + " L".join("%.2f %.2f" % p for p in points) + " Z")]
    axis, value = spec[0], float(spec[2:])
    if "<" in spec:
        # hand is left of / above the line
        return [("rect", (-far, -far, value + far, 2 * far)) if axis == "x"
                else ("rect", (-far, -far, 2 * far, value + far))]
    return [("rect", (value, -far, far, 2 * far)) if axis == "x"
            else ("rect", (-far, value, 2 * far, far))]


def clip_box(parent, shapes, name, evenodd=False):
    """defs > clipPath > shape(s), on `parent`, and the url to reference it.

    `evenodd` turns the union into "the first shape minus the rest", which is
    how the mass is clipped out of the drawing: the bbox rect with the hand
    shapes knocked out of it.
    """
    defs = etree.SubElement(parent, W + "defs")
    clip = etree.SubElement(defs, W + "clipPath")
    clip.set("id", name)
    if evenodd:
        clip.set("clip-rule", "evenodd")
    for kind, value in shapes:
        if kind == "rect":
            shape = etree.SubElement(clip, W + "rect")
            for key, number in zip(("x", "y", "width", "height"), value):
                shape.set(key, "%.4f" % number)
        else:
            shape = etree.SubElement(clip, W + "path")
            shape.set("d", value)
        if evenodd:
            shape.set("clip-rule", "evenodd")
    return "url(#%s)" % name


def grey_out(elements, grey):
    """A hand copy drawn in `grey` instead of the white the fill clip uses.

    The hand is kept as drawn, and the drawing's own white is what the fill
    clip paints: 73's fist sits under a coloured sleeve as a white blob, which
    is much brighter than the rest of the chip (`HAND_FILL` in
    `apply_color_layers`).  Only the hand copy is touched; its shade and crease
    strokes stay what the art draws, so a 50 % grey over this lands on 179 and
    the creases on 102, which is the grey the SWF itself shows there.
    """
    for element in elements:
        for node in element.iter():
            if etree.QName(node).localname not in ("path", "g", "rect"):
                continue
            if (node.get("fill") or "").lower() == "#ffffff":
                node.set("fill", grey)
            style = node.get("style")
            if style and "#ffffff" in style.lower():
                node.set("style", re.sub(r"#ffffff", grey, style, flags=re.I))


def split(svg_path, fills, out_prefix, manifest_dir=None, hand=None, tint_strokes=False,
          hand_fill=None):
    root = etree.parse(svg_path).getroot()
    box = bbox.bbox(svg_path)
    ids = set(fills)
    present = {short(g) for g in root.iter(G) if g.get("id")}
    missing = [i for i in ids if i not in present]
    if missing:
        raise SystemExit("%s: no group for %s" % (svg_path, ", ".join(sorted(missing))))

    hand_shapes = hand_parts(root, hand) if hand else None
    layers = []

    def write(kind, elements, clip, evenodd=False, name=None):
        if kind == "hand" and hand_fill:
            elements = copy.deepcopy(elements)
            grey_out(elements, hand_fill)
        out = etree.Element(root.tag, nsmap=root.nsmap)
        for key, value in root.attrib.items():
            out.set(key, value)
        for child in root:
            if not is_group(child):
                out.append(copy.deepcopy(child))    # defs, gradients, ...
        if box:
            out.append(anchor(root, box))
        if clip:
            group = etree.SubElement(out, G)
            group.set("clip-path", clip_box(out, clip, name or kind, evenodd))
            for child in elements:
                group.append(child)
        else:
            for child in elements:
                out.append(child)
        # Flash flattens a painted clip, so a fill run is recoloured whatever
        # is in it; a run of shading follows the colour by darkening it (the
        # tint is a multiply, so grey * colour is a darker colour).  Opaque art
        # outside a fill clip is not painted at all and keeps its own greys.
        name = "L%d" % len(layers)
        path = "%s_%s.svg" % (out_prefix, name)
        etree.ElementTree(out).write(path, xml_declaration=True, encoding="UTF-8")
        layers.append({"layer": name, "fill": kind is True,
                       "tint": kind is True, "hand": kind == "hand", "path": path})

    mass = [("rect", (box[0], box[1], box[2] - box[0], box[3] - box[1]))] if hand_shapes else None
    for kind, elements in merge(runs(root, ids, False, tint_strokes)):
        if kind is True and hand_shapes:
            # the hand takes its own copy of the run, untinted, and the tinted
            # copy is clipped to everything else.  The two have to be disjoint:
            # drawing the hand *over* the tint re-composites a translucent
            # shade (73's fist shading came out a grey step darker at white).
            write(kind, elements, mass + hand_shapes, evenodd=True, name="rest")
            write("hand", elements, hand_shapes, name="hand")
        else:
            write(kind, elements, None)

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
    parser.add_argument("--tint-strokes", action="store_true",
                        help="tint the grey crease/edge lines as well")
    parser.add_argument("--hand-fill", help="draw the hand copy in this grey, e.g. #cccccc")
    args = parser.parse_args(argv)

    targets = json.load(open(args.json))
    chip = [t for t in targets if t["chip"] == args.chip][0]
    fills = args.fills.split(",") if args.fills else [t["group"] for t in chip["targets"]]
    svg = args.svg or default_svg(args.chip)
    out = args.out or os.path.splitext(svg)[0]
    layers, manifest = split(svg, fills, out, hand=args.hand,
                             tint_strokes=args.tint_strokes, hand_fill=args.hand_fill)
    for entry in layers:
        print("wrote", entry["path"], "fill" if entry["fill"] else ("tint" if entry["tint"] else ""))
    print("wrote", manifest)


if __name__ == "__main__":
    main(sys.argv[1:])
