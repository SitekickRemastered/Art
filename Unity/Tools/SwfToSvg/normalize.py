#!/usr/bin/env python3
"""Turn FFDec SVGs into self-contained, Unity-friendly SVGs.

- expands every <use xlink:href="#"> (Unity's SVG importer does not support <use>)
- strips ffdec-specific attributes/namespaces
- re-centres the canvas on the sprite origin so Unity's centre pivot is the
  SWF pivot (needed for rotating parts)
- scales so 1 SWF pixel = 6.94 Unity pixels (calibrated against the existing
  chip/effect art: 73.85 swf px -> 512 px, 86.1 swf px -> 598 px)
"""
import copy
import math
import os
import re

from lxml import etree

SVG = "http://www.w3.org/2000/svg"
XLINK = "http://www.w3.org/1999/xlink"
FF = "https://www.free-decompiler.com/flash"
SCALE = 6.94


def px(v):
    if v is None:
        return None
    m = re.match(r"\s*(-?[\d.]+)", v)
    return float(m.group(1)) if m else None


def parse_transform(s):
    """Return (a,b,c,d,e,f) for matrix()/translate()/scale()/rotate()."""
    if not s or s.strip() in ("", "none"):
        return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    s = s.strip()
    m = re.match(r"matrix\(\s*([-\d.eE]+)[,\s]+([-\d.eE]+)[,\s]+([-\d.eE]+)[,\s]+"
                 r"([-\d.eE]+)[,\s]+([-\d.eE]+)[,\s]+([-\d.eE]+)\s*\)", s)
    if m:
        return tuple(float(x) for x in m.groups())
    m = re.match(r"translate\(\s*([-\d.eE]+)(?:[,\s]+([-\d.eE]+))?\s*\)", s)
    if m:
        return (1.0, 0.0, 0.0, 1.0, float(m.group(1)), float(m.group(2) or 0))
    m = re.match(r"scale\(\s*([-\d.eE]+)(?:[,\s]+([-\d.eE]+))?\s*\)", s)
    if m:
        sx = float(m.group(1))
        sy = float(m.group(2) or sx)
        return (sx, 0.0, 0.0, sy, 0.0, 0.0)
    m = re.match(r"rotate\(\s*([-\d.eE]+)\s*\)", s)
    if m:
        a = math.radians(float(m.group(1)))
        return (math.cos(a), math.sin(a), -math.sin(a), math.cos(a), 0.0, 0.0)
    return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def compose(p, c):
    a, b, cc, d, e, f = p
    ca, cb, ccc, cd, ce, cf = c
    return (a * ca + cc * cb, b * ca + d * cb,
            a * ccc + cc * cd, b * ccc + d * cd,
            a * ce + cc * cf + e, b * ce + d * cf + f)


def inverse(m):
    a, b, c, d, e, f = m
    det = a * d - b * c
    if abs(det) < 1e-12:
        return (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    ia, ib, ic, id_ = d / det, -b / det, -c / det, a / det
    return (ia, ib, ic, id_, -(ia * e + ic * f), -(ib * e + id_ * f))


def mstr(m):
    return "matrix(%s)" % ", ".join("%.6g" % v for v in m)


def apply(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def _renumber(subtree, prefix):
    ids = {}
    for el in subtree.iter():
        old = el.get("id")
        if old:
            ids[old] = prefix + old
            el.set("id", ids[old])
    if not ids:
        return
    for el in subtree.iter():
        for attr in ("fill", "stroke", "clip-path", "mask", "filter", "style"):
            v = el.get(attr)
            if v and "url(#" in v:
                for old, new in ids.items():
                    v = v.replace("url(#%s)" % old, "url(#%s)" % new)
                el.set(attr, v)


def _expand(use, defs, depth, counter):
    href = use.get("{%s}href" % XLINK)
    if not href or not href.startswith("#"):
        return None
    target = defs.get(href[1:])
    if target is None:
        return None
    counter[0] += 1
    clone = copy.deepcopy(target)
    _renumber(clone, "x%d_" % counter[0])
    # expand nested uses inside the clone
    for nested in list(clone.iter("{%s}use" % SVG)):
        rep = _expand(nested, defs, depth + 1, counter)
        parent = nested.getparent()
        idx = parent.index(nested)
        parent.remove(nested)
        if rep is not None:
            parent.insert(idx, rep)
    # use matrix then target matrix
    use_m = parse_transform(use.get("transform"))
    x = px(use.get("x")) or 0.0
    y = px(use.get("y")) or 0.0
    use_m = compose(use_m, (1.0, 0.0, 0.0, 1.0, x, y))
    target_m = parse_transform(clone.get("transform"))
    clone.set("transform", mstr(compose(use_m, target_m)))
    return clone


def flatten(content, defs):
    counter = [0]
    for use in list(content.iter("{%s}use" % SVG)):
        rep = _expand(use, defs, 0, counter)
        if rep is None:
            use.getparent().remove(use)
            continue
        parent = use.getparent()
        idx = parent.index(use)
        parent.remove(use)
        parent.insert(idx, rep)


def _strip_ffdec(root):
    for el in root.iter():
        for attr in list(el.attrib):
            if attr.startswith("{%s}" % FF) or attr.startswith("ffdec:"):
                del el.attrib[attr]


def load_frame(path):
    root = etree.parse(path, etree.XMLParser(recover=True, remove_blank_text=True)).getroot()
    w, h = px(root.get("width")), px(root.get("height"))
    g = root.find("{%s}g" % SVG)
    t = parse_transform(g.get("transform") if g is not None else None)
    defs = {}
    for el in root.iter("{%s}g" % SVG):
        i = el.get("id")
        if i:
            defs[i] = el
    content = etree.Element("{%s}g" % SVG)
    if g is not None:
        for ch in list(g):
            content.append(copy.deepcopy(ch))
    return root, w, h, t, content, defs


def convert(path, out_path, scale=SCALE, blank=False, radius_px=None, drop_uses=None,
            origin_centered=False):
    """Write a normalised SVG. Returns metadata about the local bounds."""
    if blank:
        r = radius_px or 9.72
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" '
               'viewBox="%s %s %s %s"/>\n' % (
                   fmt(r * 2 * scale), fmt(r * 2 * scale), fmt(-r), fmt(-r), fmt(r * 2), fmt(r * 2)))
        open(out_path, "w", encoding="utf-8").write(svg)
        return {"blank": True, "r": r}

    root, w, h, t, content, defs = load_frame(path)
    if drop_uses:
        for ch in list(content):
            if etree.QName(ch).localname != "use":
                continue
            cid = ch.get("{%s}characterId" % FF)
            tr = ch.get("transform") or "identity"
            if (cid, tr) in drop_uses:
                content.remove(ch)
    flatten(content, defs)

    # keep non-<g> defs children (gradients, clip paths, patterns)
    keep = []
    for d in root.findall("{%s}defs" % SVG):
        for ch in d:
            if etree.QName(ch).localname != "g":
                keep.append(copy.deepcopy(ch))
    # clipPaths defined directly in content stay in place

    # local bounds: invert the canvas transform and map the canvas corners
    inv = inverse(t)
    pts = [apply(inv, x, y) for x in (0.0, w) for y in (0.0, h)]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    r = max(abs(x0), abs(x1), abs(y0), abs(y1))

    if origin_centered:
        vx, vy, vw = -r, -r, r * 2
    else:
        vx, vy, vw = x0, y0, (x1 - x0)
    vh = vw if origin_centered else (y1 - y0)

    out = etree.Element("{%s}svg" % SVG, nsmap={None: SVG})
    out.set("width", fmt(vw * scale) + "px")
    out.set("height", fmt(vh * scale) + "px")
    out.set("viewBox", "%s %s %s %s" % (fmt(vx), fmt(vy), fmt(vw), fmt(vh)))
    if keep:
        d = etree.SubElement(out, "{%s}defs" % SVG)
        for k in keep:
            d.append(k)
    # content already holds local coordinates (its parent group transform was
    # only FFDec's canvas fit, which we drop by writing local bounds directly)
    for ch in list(content):
        out.append(ch)
    _strip_ffdec(out)
    etree.cleanup_namespaces(out)
    open(out_path, "wb").write(etree.tostring(out, xml_declaration=True, encoding="utf-8"))
    return {"w_swf": w, "h_swf": h, "local": (x0, y0, x1, y1),
            "size_px": (vw * scale, vh * scale),
            "origin_px": ((0 - vx) * scale, (0 - vy) * scale), "r": r}


def crop_to_content(path, scale=SCALE, margin=1.0):
    """Tighten an already-written SVG to its rendered content, keeping origin metadata."""
    import subprocess
    import tempfile
    from PIL import Image

    tree = etree.parse(path)
    root = tree.getroot()
    vx, vy, vw, vh = (float(v) for v in root.get("viewBox").split())
    img_w = max(8, int(round(vw)))
    img_h = max(8, int(round(vh)))
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        png = tmp.name
    try:
        subprocess.run(["rsvg-convert", "-w", str(img_w), "-h", str(img_h), path, "-o", png],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        alpha = Image.open(png).convert("RGBA").split()[3]
        box = alpha.getbbox()
    finally:
        try:
            os.unlink(png)
        except OSError:
            pass
    if not box:
        return None
    bx0, by0, bx1, by1 = box
    ux, uy = vw / img_w, vh / img_h
    nx0 = vx + bx0 * ux - margin
    ny0 = vy + by0 * uy - margin
    nw = (bx1 - bx0) * ux + margin * 2
    nh = (by1 - by0) * uy + margin * 2
    root.set("viewBox", "%s %s %s %s" % (fmt(nx0), fmt(ny0), fmt(nw), fmt(nh)))
    root.set("width", fmt(nw * scale) + "px")
    root.set("height", fmt(nh * scale) + "px")
    tree.write(path, xml_declaration=True, encoding="utf-8")
    return {"size_px": (nw * scale, nh * scale),
            "origin_px": ((0 - nx0) * scale, (0 - ny0) * scale)}


def renders_empty(path, width=200):
    """True when the document rasterises to no visible pixels.

    A sprite built from such a document has no geometry, so Unity reports NaN
    renderer bounds for it and that poisons the bounds of the whole prefab.
    """
    import subprocess
    import tempfile
    from PIL import Image

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        png = tmp.name
    try:
        subprocess.run(["rsvg-convert", "-w", str(width), path, "-o", png],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return Image.open(png).convert("RGBA").split()[3].getbbox() is None
    except Exception:
        return False
    finally:
        try:
            os.unlink(png)
        except OSError:
            pass


def fmt(v):
    s = ("%.3f" % v).rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"


if __name__ == "__main__":
    import sys
    m = convert(sys.argv[1], sys.argv[2])
    print(m)
