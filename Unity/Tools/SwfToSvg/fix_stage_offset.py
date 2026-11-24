#!/usr/bin/env python3
"""Add the missing STAGE_OFFSET to non-static chip effect prefabs from 138 up.

Static single-renderer prefabs were corrected in place long ago; the extras and
part-animated ones built before STAGE_OFFSET existed still sit 10.8 px high.

Two shapes, and they need different edits:

  extras    `chip_XXXX_extras` node at (0, 0) -> (OX, OY).  Particles are its
            children, so their local x is the authored `x_swf * U` (not shifted
            again); the animation clip drives their localPosition, so the x has
            to be baked into the clip's position keys as well.

  parts     every part/base node is at the SWF track translation (or the base
            art bbox centre) with no offset.  The Animator's position curves key
            the node absolutely every frame, so both the node and every position
            key in Animations/*.anim get (OX, OY).

The "already offset" and "neither shape" cases are reported instead of touched.
Run with --write to apply; the default is a dry run.
"""

import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svg_bbox import bbox as svg_bbox

U = 6.94 / 400.0
OX, OY = -0.4 * U, -10.8 * U          # STAGE_OFFSET in prefab units
TOL = 2e-3                            # 0.115 SWF px; rounding noise is < 1e-5
CHIPS = "Assets/Chips"
SKIP = {161, 177, 286}                # hand-measured front/back pairs (AGENTS.md)

TRANSFORM = re.compile(
    r"--- !u!4 &(-?\d+)\nTransform:(.*?)(?=\n--- |\Z)", re.S)
GAMEOBJECT = re.compile(
    r"--- !u!1 &(-?\d+)\nGameObject:(.*?)(?=\n--- |\Z)", re.S)
POS = re.compile(r"m_LocalPosition: \{x: ([-0-9.eE+]+), y: ([-0-9.eE+]+), z: ([-0-9.eE+]+)\}")
VALUE = re.compile(r"value: \{x: (-?[\d.eE+]+), y: (-?[\d.eE+]+), z: (-?[\d.eE+]+)\}")


def fmt(v):
    # seven decimals, trailing zeros trimmed: %g alone keeps only 6 significant
    # digits, which is ~5e-6 units of error on positions near 1
    s = "%.7f" % v
    s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def chip_dirs():
    out = {}
    for d in glob.glob(os.path.join(CHIPS, "*", "Chip_[0-9][0-9][0-9][0-9]")):
        out[int(os.path.basename(d).split("_")[1])] = d
    return out


def prefab_nodes(txt):
    """GameObject name -> (transform id, x, y) for every transform in the file."""
    go = {}
    for m in GAMEOBJECT.finditer(txt):
        nm = re.search(r"m_Name: ([^\n]*)", m.group(2))
        comps = re.findall(r"component: \{fileID: (-?\d+)\}", m.group(2))
        if nm:
            go[m.group(1)] = (nm.group(1), comps)
    nodes = {}
    tr = {}
    for m in TRANSFORM.finditer(txt):
        p = POS.search(m.group(2))
        owner = re.search(r"m_GameObject: \{fileID: (-?\d+)\}", m.group(2))
        if p and owner:
            tr[m.group(1)] = (float(p.group(1)), float(p.group(2)), owner.group(1))
    for gid, (name, comps) in go.items():
        for c in comps:
            if c in tr:
                x, y, owner = tr[c]
                if owner == gid:
                    nodes[name] = (c, x, y)
                    break
    return nodes, tr


def expected_parts(meta, chip):
    """name -> (x, y) exactly as build_prefabs.py would place it, no offset."""
    want = {}
    tracks = meta.get("tracks") or []
    if tracks:
        best = tracks[0].get("moving") or []
        score = -1
        for track in tracks:
            vis = [e for e in track.get("moving") or []
                   if "character_id" in e and not e.get("absent")]
            if len(vis) > score:
                score, best = len(vis), track.get("moving") or []
        for m in sorted(best, key=lambda e: e["depth"]):
            if "character_id" not in m or m.get("absent") or "matrix" not in m:
                continue
            mx = m["matrix"]
            want["chip_%04d_part_%d" % (chip, m["depth"])] = (mx[4] * U, -mx[5] * U)
    if not want and meta.get("base"):
        art = os.path.join("Assets/Chips", "*", "Chip_%04d" % chip,
                           "Sprites", meta["base"])
        found = glob.glob(art)
        if found:
            b = svg_bbox(found[0])
            if b:
                want[os.path.splitext(meta["base"])[0]] = (
                    (b[0] + b[2]) / 2.0, -(b[1] + b[3]) / 2.0)
    return want


def set_node_position(txt, tid, x, y):
    m = None
    for cand in TRANSFORM.finditer(txt):
        if cand.group(1) == tid:
            m = cand
            break
    if m is None:
        raise RuntimeError("transform %s not found" % tid)
    p = POS.search(m.group(2))
    old = p.group(0)
    new = "m_LocalPosition: {x: %s, y: %s, z: %s}" % (fmt(x), fmt(y), p.group(3))
    start = m.start(2) + p.start()
    end = m.start(2) + p.end()
    return txt[:start] + new + txt[end:]


def shift_position_curves(path, dx, dy, x_override=None):
    """Shift the position keys of every curve in m_PositionCurves.

    The section ends at the next top-level `m_...:` key -- `m_ScaleCurves: []`
    does not end with a colon, so testing for one would run on into the scale
    keys and shift them too.  Each curve's `path` is checked as well: the part
    nodes are shifted, a `sprite` child is not.
    """
    txt = open(path).read()
    lines = txt.split("\n")
    try:
        start = next(i for i, l in enumerate(lines) if l.strip() == "m_PositionCurves:")
    except StopIteration:
        return 0
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if re.match(r"^  m_\w+:", lines[i]):
            end = i
            break
    # split the section into curve blocks so each can be checked by path
    bounds = [i for i in range(start + 1, end) if re.match(r"^  - curve:", lines[i])]
    if not bounds:
        return 0
    bounds.append(end)
    n = 0
    for a, b in zip(bounds, bounds[1:]):
        block = "\n".join(lines[a:b])
        pm = re.search(r"^    path: ?(.*)$", block, re.M)
        curve_path = pm.group(1).strip() if pm else ""
        if curve_path and not curve_path.startswith("chip_"):
            print("  WARN %s: skipping position curve for %r" % (os.path.basename(path), curve_path))
            continue
        for i in range(a, b):
            m = VALUE.search(lines[i])
            if not m:
                continue
            x, y, z = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
            nx = x_override if x_override is not None else x + dx
            ny = y + dy
            lines[i] = lines[i][:m.start()] + "value: {x: %s, y: %s, z: %s}" % (
                fmt(nx), fmt(ny), fmt(z)) + lines[i][m.end():]
            n += 1
    open(path, "w").write("\n".join(lines))
    return n


def main():
    write = "--write" in sys.argv
    only = None
    if "--only" in sys.argv:
        only = {int(v) for v in sys.argv[sys.argv.index("--only") + 1].split(",")}
    chips = chip_dirs()
    fixed, already, odd, nojson = [], [], [], []
    for chip in sorted(chips):
        if chip < 138 or chip in SKIP:
            continue
        if only is not None and chip not in only:
            continue
        d = chips[chip]
        pref_path = os.path.join(d, "Chip_%04d_Effect.prefab" % chip)
        if not os.path.exists(pref_path):
            continue
        js = glob.glob(os.path.join(d, "Sprites", "*effect.json"))
        if not js:
            nojson.append(chip)
            continue
        meta = json.load(open(js[0]))
        if meta.get("mode") == "static":
            continue
        txt = open(pref_path).read()
        nodes, _ = prefab_nodes(txt)
        extras = "chip_%04d_extras" % chip
        particles = {k: v for k, v in nodes.items() if k.startswith("particle_")}
        parts = {k: v for k, v in nodes.items() if k.startswith("chip_%04d_part_" % chip)}
        base = {k: v for k, v in nodes.items()
                if k.startswith("chip_%04d_base" % chip) or k.endswith("_base")}
        want = expected_parts(meta, chip)

        # classify every node we are responsible for
        targets = []   # (name, target_after, is_particle)
        unknown = []
        if extras in nodes:
            targets.append((extras, (OX, OY), False))
        for name, (tid, x, y) in parts.items():
            if name in want:
                wx, wy = want[name]
                targets.append((name, (wx + OX, wy + OY), False))
            else:
                unknown.append((name, "no track for part"))
        for name, (tid, x, y) in base.items():
            if name in want:
                wx, wy = want[name]
                targets.append((name, (wx + OX, wy + OY), False))
            else:
                unknown.append((name, "no bbox for base"))
        xs = {}
        if particles:
            plist = (meta.get("clips") or {}).get("particles") or []
            for i, p in enumerate(plist):
                xs["particle_%d" % i] = p.get("x_swf", 0.0) * U
        for name in particles:
            if name in xs:
                targets.append((name, (xs[name], 0.0), True))
            else:
                unknown.append((name, "no json particle"))

        if not targets:
            odd.append((chip, "no extras/part/base/particle node"))
            continue

        # is the file in the old (unshifted) state, the new state, or neither?
        state = set()
        for name, (tx, ty), is_particle in targets:
            cur = (nodes[name][1], nodes[name][2])
            if is_particle:
                old_ok = abs(cur[0]) < TOL and abs(cur[1]) < TOL
                new_ok = abs(cur[0] - tx) < TOL and abs(cur[1]) < TOL
            else:
                # old position is target minus offset
                oldx, oldy = tx - OX, ty - OY
                old_ok = abs(cur[0] - oldx) < TOL and abs(cur[1] - oldy) < TOL
                new_ok = abs(cur[0] - tx) < TOL and abs(cur[1] - ty) < TOL
            state.add("old" if old_ok else ("new" if new_ok else "other"))
        if state == {"new"}:
            already.append(chip)
            continue
        if state != {"old"} or unknown:
            odd.append((chip, "state %s; %s" % (sorted(state), unknown[:3])))
            continue

        fixed.append(chip)
        if not write:
            continue

        out = txt
        for name, (tx, ty), is_particle in targets:
            out = set_node_position(out, nodes[name][0], tx, ty)
        open(pref_path, "w").write(out)

        # clips: particle x comes from x_swf, everything else shifts uniformly
        for clip in sorted(glob.glob(os.path.join(d, "Animations", "*.anim"))):
            base_name = os.path.basename(clip)
            m = re.search(r"particle_(\d+)\.anim$", base_name)
            if m:
                key = "particle_%d" % int(m.group(1))
                if key not in xs:
                    print("  WARN %d: %s has no json particle" % (chip, base_name))
                    continue
                shift_position_curves(clip, 0.0, 0.0, x_override=xs[key])
            else:
                shift_position_curves(clip, OX, OY)

    print("chips fed to the fixer (write=%s): %d" % (write, len(fixed)))
    if write:
        print("  applied: %d" % len(fixed))
    print("already offset:", len(already), already[:20])
    print("no effect.json:", len(nojson), nojson[:20])
    print("DID NOT FIT EITHER SHAPE:", len(odd))
    for chip, why in odd:
        print("  chip %d: %s" % (chip, why))
    return 0 if not odd else 0


if __name__ == "__main__":
    raise SystemExit(main())
