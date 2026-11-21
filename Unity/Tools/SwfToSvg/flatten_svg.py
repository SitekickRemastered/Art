#!/usr/bin/env python3
"""Flatten an SVG's curves into line segments.

Unity's SVG importer tessellates a curve into whatever it thinks the drawing is
worth, and on these frames that is a straight edge every 13 px at the size the
movies are now drawn -- a circle comes out as a polygon. Its tessellation
settings turned out not to move that at all, so the curves are cut here instead:
what the importer receives is already polygonal, and it has nothing left to
approximate.

The tolerance is given in stage pixels (the viewBox units of the frames, i.e.
1/375 of the movie's width).  The frames keep their art inside scaled groups --
a shape's own coordinates are anywhere from a tenth of a stage pixel to several
stage pixels each -- so the tolerance for a path is converted to its own units
through the cumulative transform of the groups it sits in.  Without that, a path
drawn at 1/7 scale is flattened seven times coarser than asked and a path drawn
at 7x is flattened seven times finer, which is what the first attempt did.

Usage as a script:  flatten_svg.py <file.svg> ...   (rewrites in place)
"""

import math
import re
import sys

NUM = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
CMD = re.compile(r"[MmZzLlHhVvCcSsQqTtAa]")
# a tag that changes the transform stack, or a path whose `d` may need work
TAG = re.compile(r"</g\s*>|<(?:g|path)\b[^>]*?/?>")
CURVE = re.compile(r"[CcSsQqTtAa]")

IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _numbers(chunk):
    return [float(n) for n in NUM.findall(chunk)]


def _quad(p0, p1, p2, tol):
    """Points along a quadratic bezier, excluding p0."""
    dev = max(abs(p0[0] - 2 * p1[0] + p2[0]), abs(p0[1] - 2 * p1[1] + p2[1]))
    n = max(1, min(256, int(math.ceil(math.sqrt(dev / (8.0 * tol))))))
    out = []
    for i in range(1, n + 1):
        t = i / float(n)
        u = 1 - t
        out.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                    u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
    return out


def _cubic(p0, p1, p2, p3, tol):
    dev = max(abs(p0[0] - 2 * p1[0] + p2[0]), abs(p0[1] - 2 * p1[1] + p2[1]),
              abs(p1[0] - 2 * p2[0] + p3[0]), abs(p1[1] - 2 * p2[1] + p3[1]))
    n = max(1, min(256, int(math.ceil(math.sqrt(6 * dev / (8.0 * tol))))))
    out = []
    for i in range(1, n + 1):
        t = i / float(n)
        u = 1 - t
        out.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return out


def _starts_number(text, i):
    """True if another coordinate group follows at i (not a new command)."""
    return re.match(r"\s*,?\s*[-+]?(?:\d*\.\d+|\d+\.?)", text[i:]) is not None


def flatten_path(d, tol):
    """Rewrite one path's `d` with its curves replaced by line segments."""
    out = []
    i, cur, start, prev_ctrl = 0, (0.0, 0.0), (0.0, 0.0), None
    n = len(d)

    def read(count):
        nonlocal i
        vals = []
        for _ in range(count):
            mm = NUM.search(d, i)
            if not mm:
                return None
            vals.append(float(mm.group(0)))
            i = mm.end()
        return vals

    while True:
        m = CMD.search(d, i)
        if not m:
            break
        cmd = m.group(0)
        i = m.end()
        rel = cmd.islower()
        c = cmd.upper()

        if c == "Z":
            out.append("Z")
            cur = start
            prev_ctrl = None
            continue

        groups = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2}
        if c not in groups:
            raise ValueError("unsupported path command %r" % cmd)
        size = groups[c]

        # one command letter can be followed by several coordinate groups; a
        # new letter ends them, and a group only continues while a number is
        # actually next (the old code read the next command's numbers as
        # coordinates, which turned every curve into one straight line)
        while _starts_number(d, i):
            vals = read(size)
            if vals is None:
                break

            if c == "M":
                x, y = vals
                if rel:
                    x, y = cur[0] + x, cur[1] + y
                cur = (x, y)
                start = cur
                out.append("M%g %g" % (x, y))
                prev_ctrl = None
                # subsequent pairs are implicit lineto
                c, size = "L", 2
                continue

            if c in ("L", "H", "V"):
                if c == "L":
                    x, y = vals
                    if rel:
                        x, y = cur[0] + x, cur[1] + y
                elif c == "H":
                    x = cur[0] + vals[0] if rel else vals[0]
                    y = cur[1]
                else:
                    x = cur[0]
                    y = cur[1] + vals[0] if rel else vals[0]
                cur = (x, y)
                out.append("L%g %g" % (x, y))
                prev_ctrl = None
            elif c == "Q":
                x1, y1, x, y = vals
                if rel:
                    x1, y1 = cur[0] + x1, cur[1] + y1
                    x, y = cur[0] + x, cur[1] + y
                for px, py in _quad(cur, (x1, y1), (x, y), tol):
                    out.append("L%g %g" % (px, py))
                prev_ctrl = (x1, y1)
                cur = (x, y)
            elif c == "T":
                if prev_ctrl is not None:
                    x1 = 2 * cur[0] - prev_ctrl[0]
                    y1 = 2 * cur[1] - prev_ctrl[1]
                else:
                    x1, y1 = cur
                x, y = vals
                if rel:
                    x, y = cur[0] + x, cur[1] + y
                for px, py in _quad(cur, (x1, y1), (x, y), tol):
                    out.append("L%g %g" % (px, py))
                prev_ctrl = (x1, y1)
                cur = (x, y)
            elif c == "C":
                x1, y1, x2, y2, x, y = vals
                if rel:
                    x1, y1 = cur[0] + x1, cur[1] + y1
                    x2, y2 = cur[0] + x2, cur[1] + y2
                    x, y = cur[0] + x, cur[1] + y
                for px, py in _cubic(cur, (x1, y1), (x2, y2), (x, y), tol):
                    out.append("L%g %g" % (px, py))
                prev_ctrl = (x2, y2)
                cur = (x, y)
            elif c == "S":
                if prev_ctrl is not None:
                    x1 = 2 * cur[0] - prev_ctrl[0]
                    y1 = 2 * cur[1] - prev_ctrl[1]
                else:
                    x1, y1 = cur
                x2, y2, x, y = vals
                if rel:
                    x2, y2 = cur[0] + x2, cur[1] + y2
                    x, y = cur[0] + x, cur[1] + y
                for px, py in _cubic(cur, (x1, y1), (x2, y2), (x, y), tol):
                    out.append("L%g %g" % (px, py))
                prev_ctrl = (x2, y2)
                cur = (x, y)

    return "".join(out)


def _parse_transform(value):
    if not value or value.strip() in ("", "none"):
        return IDENTITY
    v = value.strip()
    m = re.match(r"matrix\(\s*([-+\d.eE]+)[,\s]+([-+\d.eE]+)[,\s]+([-+\d.eE]+)[,\s]+"
                 r"([-+\d.eE]+)[,\s]+([-+\d.eE]+)[,\s]+([-+\d.eE]+)\s*\)", v)
    if m:
        return tuple(float(x) for x in m.groups())
    m = re.match(r"translate\(\s*([-+\d.eE]+)(?:[,\s]+([-+\d.eE]+))?\s*\)", v)
    if m:
        return (1.0, 0.0, 0.0, 1.0, float(m.group(1)), float(m.group(2) or 0))
    m = re.match(r"scale\(\s*([-+\d.eE]+)(?:[,\s]+([-+\d.eE]+))?\s*\)", v)
    if m:
        sx = float(m.group(1))
        return (sx, 0.0, 0.0, float(m.group(2) or sx), 0.0, 0.0)
    m = re.match(r"rotate\(\s*([-+\d.eE]+)\s*\)", v)
    if m:
        a = math.radians(float(m.group(1)))
        return (math.cos(a), math.sin(a), -math.sin(a), math.cos(a), 0.0, 0.0)
    return IDENTITY


def _mul(p, c):
    """parent * child, both (a,b,c,d,e,f)."""
    a, b, cc, d, e, f = p
    ca, cb, ccc, cd, ce, cf = c
    return (a * ca + cc * cb, b * ca + d * cb,
            a * ccc + cc * cd, b * ccc + d * cd,
            a * ce + cc * cf + e, b * ce + d * cf + f)


def _tag_transform(tag):
    m = re.search(r'\stransform="([^"]*)"', tag)
    return _parse_transform(m.group(1) if m else None)


def _scale_of(m):
    det = abs(m[0] * m[3] - m[1] * m[2])
    return math.sqrt(det) if det > 1e-12 else 1.0


def flatten(text, tol_px=0.1):
    """Replace every curve in `text` with segments no longer than tol_px."""
    stack = []
    edits = []
    for m in TAG.finditer(text):
        tag = m.group(0)
        if tag.startswith("</"):
            if stack:
                stack.pop()
            continue
        if tag.startswith("<g"):
            stack.append(_tag_transform(tag))
            continue
        parent = IDENTITY
        for t in stack:
            parent = _mul(parent, t)
        tol = tol_px / _scale_of(_mul(parent, _tag_transform(tag)))
        for dm in re.finditer(r'\sd="([^"]*)"', tag):
            d = dm.group(1)
            if not CURVE.search(d):
                continue
            at = m.start() + dm.start(1)
            edits.append((at, at + len(d), flatten_path(d, tol)))

    for at, end, repl in reversed(edits):
        text = text[:at] + repl + text[end:]
    return text


def flatten_file(path, tol_px=0.1):
    """tol_px is in stage pixels, see the module docstring."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    with open(path, "w", encoding="utf-8") as f:
        f.write(flatten(text, tol_px))


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        flatten_file(arg)
