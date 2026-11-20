#!/usr/bin/env python3
"""Flatten an SVG's curves into line segments.

Unity's SVG importer tessellates a curve into whatever it thinks the drawing is
worth, and on these frames that is a straight edge every 13 px at the size the
movies are now drawn — a circle comes out as a polygon. Its tessellation settings
turned out not to move that at all, so the curves are cut here instead: what the
importer receives is already polygonal, and it has nothing left to approximate.

The frames keep their art inside a scaled group, so path coordinates are around
+-55 units for a 375 unit wide stage: one path unit is a few stage pixels. The
tolerance is therefore given in stage pixels and converted per file, and the
frames are drawn about 1.3 stage px per screen px at their current size.
"""

import math
import re

NUM = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
CMD = re.compile(r"[MmZzLlHhVvCcSsQqTtAa]")


def _numbers(chunk):
    return [float(n) for n in NUM.findall(chunk)]


def _quad(p0, p1, p2, tol):
    """Points along a quadratic bezier, excluding p0."""
    dev = max(abs(p0[0] - 2 * p1[0] + p2[0]), abs(p0[1] - 2 * p1[1] + p2[1]))
    n = max(1, min(48, int(math.ceil(math.sqrt(dev / (8.0 * tol))))))
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
    n = max(1, min(64, int(math.ceil(math.sqrt(6 * dev / (8.0 * tol))))))
    out = []
    for i in range(1, n + 1):
        t = i / float(n)
        u = 1 - t
        out.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return out


def flatten_path(d, tol):
    """Rewrite one path's `d` with its curves replaced by line segments."""
    out = []
    i, cur, start, last_cmd = 0, (0.0, 0.0), (0.0, 0.0), None
    prev_ctrl = None
    n = len(d)

    def read(count):
        nonlocal i
        chunk = d[i:]
        m = re.match(r"\s*,?\s*", chunk)
        vals = NUM.findall(chunk)
        if len(vals) < count:
            return None
        # advance i past the matched numbers
        consumed = 0
        for _ in range(count):
            mm = NUM.search(d, i)
            if not mm:
                return None
            i = mm.end()
            consumed += 1
        return [float(v) for v in vals[:count]]

    while i < n:
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

        first = True
        while True:
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
                first = False
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

            first = False
            # another coordinate group follows only if another number is next
            if not re.match(r"\s*,?\s*[-+]?(?:\d*\.\d+|\d+\.?)", d[i:]):
                break

    return "".join(out)


def flatten(text, tol=0.2):
    def repl(match):
        return ' d="%s"' % flatten_path(match.group(1), tol)
    # the leading whitespace keeps ids such as id="x1_shape0" out of the match
    return re.sub(r'\sd="([^"]*)"', repl, text)


def _units_per_stage_px(text):
    """How many path units one stage pixel covers, from art width vs viewBox."""
    view = re.search(r'viewBox="([^"]*)"', text)
    xs = []
    for d in re.findall(r'\sd="([^"]*)"', text):
        nums = [float(n) for n in NUM.findall(d)]
        xs.extend(nums[0::2])
    if not view or not xs:
        return 1.0
    vb = [float(v) for v in view.group(1).replace(",", " ").split()]
    if len(vb) < 3 or vb[2] <= 0:
        return 1.0
    art = max(xs) - min(xs)
    if art <= 0:
        return 1.0
    return vb[2] / art


def flatten_file(path, tol_px=0.2):
    """tol_px is in stage pixels; see the module docstring."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    tol = tol_px / _units_per_stage_px(text)
    with open(path, "w", encoding="utf-8") as f:
        f.write(flatten(text, tol))
