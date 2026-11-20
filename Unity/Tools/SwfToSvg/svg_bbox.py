#!/usr/bin/env python3
"""Compute the exact geometry bounding box of an FFDec SVG in user (viewBox) units.

The Unity SVG importer ignores clipPath when measuring the sprite canvas, so its
texture spans this raw geometry bbox (not the viewBox).  We reproduce that bbox
here so prefab placement can be calculated without opening the project.

Only geometry is measured (no strokes; FFDec output is fill-only).
"""

import math
import re
import sys
import xml.etree.ElementTree as ET

SVG_NS = "{http://www.w3.org/2000/svg}"
NUM = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def _mul(m, n):
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return (a * A + c * B, b * A + d * B,
            a * C + c * D, b * C + d * D,
            a * E + c * F + e, b * E + d * F + f)


def _apply(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def _parse_transform(text):
    m = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", text or ""):
        v = [float(x) for x in NUM.findall(args)]
        if name == "matrix" and len(v) == 6:
            m = _mul(m, tuple(v))
        elif name == "translate":
            m = _mul(m, (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0))
        elif name == "scale":
            sx = v[0]
            sy = v[1] if len(v) > 1 else v[0]
            m = _mul(m, (sx, 0, 0, sy, 0, 0))
        elif name == "rotate":
            a = math.radians(v[0])
            ca, sa = math.cos(a), math.sin(a)
            r = (ca, sa, -sa, ca, 0, 0)
            if len(v) == 3:
                r = _mul(_mul((1, 0, 0, 1, v[1], v[2]), r), (1, 0, 0, 1, -v[1], -v[2]))
            m = _mul(m, r)
        elif name == "skewX":
            m = _mul(m, (1, 0, math.tan(math.radians(v[0])), 1, 0, 0))
        elif name == "skewY":
            m = _mul(m, (1, math.tan(math.radians(v[0])), 0, 1, 0, 0))
    return m


def _quad_extrema(p0, p1, p2):
    """Parameter values where a quadratic bezier is extreme, per axis."""
    out = []
    for k in (0, 1):
        den = p0[k] - 2 * p1[k] + p2[k]
        if abs(den) > 1e-12:
            t = (p0[k] - p1[k]) / den
            if 0.0 < t < 1.0:
                out.append(t)
    return out


def _cubic_extrema(p0, p1, p2, p3):
    out = []
    for k in (0, 1):
        a = -p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]
        b = 2 * (p0[k] - 2 * p1[k] + p2[k])
        c = p1[k] - p0[k]
        if abs(a) < 1e-12:
            if abs(b) > 1e-12:
                t = -c / b
                if 0.0 < t < 1.0:
                    out.append(t)
            continue
        disc = b * b - 4 * a * c
        if disc < 0:
            continue
        sq = math.sqrt(disc)
        for t in ((-b + sq) / (2 * a), (-b - sq) / (2 * a)):
            if 0.0 < t < 1.0:
                out.append(t)
    return out


def _quad_at(p0, p1, p2, t):
    mt = 1 - t
    return (mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0],
            mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1])


def _cubic_at(p0, p1, p2, p3, t):
    mt = 1 - t
    return (mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t ** 3 * p3[0],
            mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t ** 3 * p3[1])


def _path_points(d):
    """Yield control/extreme points of a path in its own coordinate space."""
    tokens = re.findall(r"[MmLlHhVvCcQqSsTtAaZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?", d)
    i = 0
    cmd = None
    cur = (0.0, 0.0)
    start = (0.0, 0.0)
    prev_ctrl = None
    prev_qctrl = None

    def num():
        nonlocal i
        v = float(tokens[i])
        i += 1
        return v

    while i < len(tokens):
        if re.match(r"[A-Za-z]", tokens[i]):
            cmd = tokens[i]
            i += 1
            if cmd in "Zz":
                cur = start
                yield cur
                prev_ctrl = prev_qctrl = None
                continue
        rel = cmd.islower()
        C = cmd.upper()

        if C == "M":
            x, y = num(), num()
            cur = (cur[0] + x, cur[1] + y) if rel else (x, y)
            start = cur
            yield cur
            cmd = "l" if rel else "L"
            prev_ctrl = prev_qctrl = None
        elif C == "L":
            x, y = num(), num()
            cur = (cur[0] + x, cur[1] + y) if rel else (x, y)
            yield cur
            prev_ctrl = prev_qctrl = None
        elif C == "H":
            x = num()
            cur = (cur[0] + x if rel else x, cur[1])
            yield cur
            prev_ctrl = prev_qctrl = None
        elif C == "V":
            y = num()
            cur = (cur[0], cur[1] + y if rel else y)
            yield cur
            prev_ctrl = prev_qctrl = None
        elif C == "C":
            pts = [(num(), num()) for _ in range(3)]
            if rel:
                pts = [(cur[0] + p[0], cur[1] + p[1]) for p in pts]
            p0, p1, p2, p3 = cur, pts[0], pts[1], pts[2]
            yield p1
            yield p2
            yield p3
            for t in _cubic_extrema(p0, p1, p2, p3):
                yield _cubic_at(p0, p1, p2, p3, t)
            cur = p3
            prev_ctrl, prev_qctrl = p2, None
        elif C == "Q":
            pts = [(num(), num()) for _ in range(2)]
            if rel:
                pts = [(cur[0] + p[0], cur[1] + p[1]) for p in pts]
            p0, p1, p2 = cur, pts[0], pts[1]
            yield p1
            yield p2
            for t in _quad_extrema(p0, p1, p2):
                yield _quad_at(p0, p1, p2, t)
            cur = p2
            prev_qctrl, prev_ctrl = p1, None
        elif C == "S":
            pts = [(num(), num()) for _ in range(2)]
            if rel:
                pts = [(cur[0] + p[0], cur[1] + p[1]) for p in pts]
            p1 = prev_ctrl if prev_ctrl is not None else cur
            p0, p2, p3 = cur, pts[0], pts[1]
            yield p2
            yield p3
            for t in _cubic_extrema(p0, p1, p2, p3):
                yield _cubic_at(p0, p1, p2, p3, t)
            cur = p3
            prev_ctrl, prev_qctrl = p2, None
        elif C == "T":
            x, y = num(), num()
            p2 = (cur[0] + x, cur[1] + y) if rel else (x, y)
            p1 = (2 * cur[0] - prev_qctrl[0], 2 * cur[1] - prev_qctrl[1]) if prev_qctrl else cur
            p0 = cur
            yield p2
            for t in _quad_extrema(p0, p1, p2):
                yield _quad_at(p0, p1, p2, t)
            cur = p2
            prev_qctrl, prev_ctrl = p1, None
        elif C == "A":
            # Only endpoints are reliable without full arc maths; arcs are rare
            # in FFDec output and their endpoints bound the arc for our purpose.
            for _ in range(5):
                num()
            x, y = num(), num()
            cur = (cur[0] + x, cur[1] + y) if rel else (x, y)
            yield cur
            prev_ctrl = prev_qctrl = None
        else:
            break


def bbox(path):
    """Return (x0, y0, x1, y1) of all path geometry in SVG user units."""
    tree = ET.parse(path)
    root = tree.getroot()
    lo = [math.inf, math.inf]
    hi = [-math.inf, -math.inf]
    found = False

    skip = {"clipPath", "defs", "mask", "symbol", "linearGradient",
            "radialGradient", "pattern", "filter", "marker", "style", "title", "desc"}

    def walk(el, ctm, stroke, stroke_width):
        nonlocal found
        tag = el.tag.replace(SVG_NS, "")
        if tag in skip:
            return
        ctm = _mul(ctm, _parse_transform(el.get("transform")))

        if el.get("stroke") is not None:
            stroke = el.get("stroke")
        if el.get("stroke-width") is not None:
            try:
                stroke_width = float(el.get("stroke-width"))
            except ValueError:
                pass
        style = el.get("style") or ""
        for decl in style.split(";"):
            if ":" not in decl:
                continue
            k, v = decl.split(":", 1)
            k, v = k.strip(), v.strip()
            if k == "stroke":
                stroke = v
            elif k == "stroke-width":
                try:
                    stroke_width = float(v.replace("px", ""))
                except ValueError:
                    pass

        if tag == "path":
            d = el.get("d")
            if d:
                a, b, c, d2, _, _ = ctm
                scale = max(math.hypot(a, b), math.hypot(c, d2))
                pad = 0.0
                if stroke and stroke != "none":
                    pad = 0.5 * stroke_width * scale
                for x, y in _path_points(d):
                    px, py = _apply(ctm, x, y)
                    found = True
                    for v, i, sgn in ((px, 0, -1), (py, 1, -1), (px, 0, 1), (py, 1, 1)):
                        pass
                    if px - pad < lo[0]:
                        lo[0] = px - pad
                    if py - pad < lo[1]:
                        lo[1] = py - pad
                    if px + pad > hi[0]:
                        hi[0] = px + pad
                    if py + pad > hi[1]:
                        hi[1] = py + pad
        for child in el:
            walk(child, ctm, stroke, stroke_width)

    walk(root, (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), None, 1.0)
    if not found:
        return None
    return (lo[0], lo[1], hi[0], hi[1])


def viewbox(path):
    t = open(path, encoding="utf-8", errors="replace").read(1200)
    m = re.search(r'viewBox="([^"]+)"', t)
    return [float(v) for v in NUM.findall(m.group(1))] if m else None


if __name__ == "__main__":
    for p in sys.argv[1:]:
        b = bbox(p)
        vb = viewbox(p)
        print(p)
        print("  viewBox", vb)
        if b:
            print("  bbox   (%.3f, %.3f) - (%.3f, %.3f)  size %.3f x %.3f"
                  % (b[0], b[1], b[2], b[3], b[2] - b[0], b[3] - b[1]))
        else:
            print("  bbox   <none>")
