#!/usr/bin/env python3
"""Check that every spawned-particle prefab still carries its runtime field.

`build_particle_fields.py` writes the `ChipParticleField` block into a chip's
effect prefab from its export.  `build_prefabs.py --write` rewrites the whole
file from the export and drops it, and so does any hand-splice; what is left is
a chip that draws the baked four columns and never spawns a stream.  The live
check catches that (`particle_check.py --chip N --unity --live` reports no field
line and `LiveCount` 0), but it costs a Unity launch.  This audit reads the
prefabs and the export's json and answers in a second.

For every chip whose effect json has `clips.particles` it checks

* the prefab exists and carries a MonoBehaviour with the component's script guid,
  and the root GameObject still references it -- a block the root no longer
  lists never runs;
* `stageWidth`/`stageHeight` are present and positive: that is the domain the
  spawn rule draws x in, and the one thing `particle_check` divides the spread
  by, so a zero or dropped value there makes the live check wrong as well;
* the symbol list matches the export: one entry per distinct symbol, in order,
  with the export's name and `rising` flag, a non-empty frame list whose count
  is the number of frames the export wrote for that symbol, and frame guids that
  are the `.meta` guids of the sprites the json names (a re-export renumbers
  them, so a stale list plays the previous art or nothing at all);
* `frameRate` is the chip's exported fps and `capacity`/`margin` are present.

    python3 Tools/SwfToSvg/audit_particle_fields.py            # report + FAIL
    python3 Tools/SwfToSvg/audit_particle_fields.py --chip 151 # one chip

Read-only, and exit 1 on any failure.  There is no `--write`: the fix for a
dropped block is the builder, and for a stale one a re-export plus the builder.
"""

import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CHIPS = os.path.join(ROOT, "Assets", "Chips")

SCRIPT_GUID = "3f7c1a5e9b2d4c8ea1f6d0b7c93e2a48"   # Assets/Scripts/ChipParticleField.cs
# The effect stage every chip in the library is exported on (`STAGE_SWF` in
# build_prefabs.py, and what build_particle_fields.py pins).  A field that
# reports another stage is either a broken block or a new stage class: both
# deserve a look, and the live check divides by whatever the prefab says.
STAGE = (375.0, 300.0)


def chips():
    """(chip id, chip dir, effect json) for every chip that spawns particles."""
    for range_dir in sorted(glob.glob(os.path.join(CHIPS, "*"))):
        if not os.path.isdir(range_dir):
            continue
        for name in sorted(os.listdir(range_dir)):
            m = re.match(r"Chip_(\d{4})$", name)
            if not m:
                continue
            cdir = os.path.join(range_dir, name)
            js = glob.glob(os.path.join(cdir, "Sprites", "*_effect.json"))
            if not js:
                continue
            data = json.load(open(js[0], encoding="utf-8"))
            if ((data.get("clips") or {}).get("particles")):
                yield int(m.group(1)), cdir, data


def meta_guid(svg_path):
    try:
        text = open(svg_path + ".meta", encoding="utf-8").read()
    except OSError:
        return None
    m = re.search(r"^guid: (\w+)", text, re.M)
    return m.group(1) if m else None


def expected(cid, cdir, data):
    """What the prefab's block should say, rebuilt the way the builder builds it."""
    seen, rows = set(), []
    for p in data["clips"]["particles"]:
        symbol = p.get("symbol")
        if symbol in seen:
            continue
        seen.add(symbol)
        art = p.get("art")
        names = art if isinstance(art, list) else [art]
        rows.append({"name": p.get("name", "particle_0"),
                     "rising": p.get("dir") == "up",
                     "frames": [meta_guid(os.path.join(cdir, "Sprites", n))
                                for n in names if n]})
    return rows


def blocks(text):
    """The prefab split into its `--- !u!` documents."""
    return [b for b in re.split(r"(?m)^(?=--- !u!)", text) if b.startswith("--- !u!")]


def find_field(text):
    """(block id, block text) for the ChipParticleField MonoBehaviour, or None."""
    for block in blocks(text):
        if block.startswith("--- !u!114 ") and SCRIPT_GUID in block:
            m = re.match(r"--- !u!114 &(-?\d+)", block)
            return (m.group(1) if m else "?", block)
    return None


def find_root(text, cid):
    """(game object id, block text) for the prefab's root `Chip_XXXX_Effect`."""
    for block in blocks(text):
        if not block.startswith("--- !u!1 "):
            continue
        if re.search(r"^  m_Name: Chip_%04d_Effect$" % cid, block, re.M):
            m = re.match(r"--- !u!1 &(-?\d+)", block)
            return (m.group(1) if m else "?", block)
    return None


def art_entries(block):
    """The block's `art:` list: name, rising and the frame guids of each symbol."""
    rows, cur, in_frames = [], None, False
    for line in block.splitlines():
        if re.match(r"^  art:\s*$", line):
            continue
        m = re.match(r"^  - name: ?(.*)$", line)
        if m:
            cur = {"name": m.group(1).strip(), "rising": False, "frames": []}
            rows.append(cur)
            in_frames = False
            continue
        if cur is None:
            continue
        m = re.match(r"^    rising: (\d+)", line)
        if m:
            cur["rising"] = m.group(1) != "0"
            in_frames = False
            continue
        if re.match(r"^    frames:\s*$", line):
            in_frames = True
            continue
        m = re.match(r"^    - \{fileID: \d+, guid: (\w+), type: 3\}$", line)
        if m and in_frames:
            cur["frames"].append(m.group(1))
            continue
        if line.strip() and not line.startswith("      "):
            in_frames = False
    return rows


def number(block, key):
    m = re.search(r"^  %s: (-?[\d.]+)\s*$" % key, block, re.M)
    return float(m.group(1)) if m else None


def audit_chip(cid, cdir, data, prefab_path=None):
    """Return (problems, summary) for one chip's prefab."""
    prefab = prefab_path or os.path.join(cdir, "Chip_%04d_Effect.prefab" % cid)
    rel = os.path.relpath(prefab, ROOT)
    if not os.path.exists(prefab):
        return ["no %s: the chip has no effect prefab to carry the field" % rel], None
    text = open(prefab, encoding="utf-8").read()

    found = find_field(text)
    if not found:
        return ["%s has no ChipParticleField block: the prefab draws the baked "
                "columns and never spawns (build_particle_fields.py --write)" % rel], None
    comp_id, block = found

    root = find_root(text, cid)
    if not root:
        return ["%s has no root GameObject named Chip_%04d_Effect" % (rel, cid)], None
    if not re.search(r"^  - component: \{fileID: %s\}$" % re.escape(comp_id), root[1], re.M):
        return ["%s: the root does not list the field's component (%s), so it never "
                "runs" % (rel, comp_id)], None

    problems = []
    width, height = number(block, "stageWidth"), number(block, "stageHeight")
    if width is None or height is None:
        problems.append("%s: the field has no stageWidth/stageHeight, so the live "
                        "check cannot scale its spread" % rel)
    elif width <= 0 or height <= 0:
        problems.append("%s: the field's stage is %g x %g px" % (rel, width, height))
    elif (width, height) != STAGE:
        problems.append("%s: the field draws x in %g x %g px, not the %g x %g the "
                        "effect export uses (update this audit if a chip's stage "
                        "really changed)" % (rel, width, height, STAGE[0], STAGE[1]))

    fps = number(block, "frameRate")
    if fps is None:
        problems.append("%s: the field has no frameRate" % rel)
    elif data.get("fps") and abs(fps - float(data["fps"])) > 0.01:
        problems.append("%s: the field plays symbols at %g fps, the export says %g"
                        % (rel, fps, data["fps"]))
    for key in ("margin", "capacity", "spawnInterval", "spawnBurst"):
        if number(block, key) is None:
            problems.append("%s: the field has no %s" % (rel, key))

    want = expected(cid, cdir, data)
    got = art_entries(block)
    if len(got) != len(want):
        problems.append("%s: the field lists %d symbol(s), the export has %d"
                        % (rel, len(got), len(want)))
    for i, (w, g) in enumerate(zip(want, got)):
        where = "%s: symbol %d (%s)" % (rel, i + 1, w["name"])
        if g["name"] != w["name"]:
            problems.append("%s is named %s in the prefab" % (where, g["name"]))
        if g["rising"] != w["rising"]:
            problems.append("%s rises=%s in the prefab, %s in the export"
                            % (where, g["rising"], w["rising"]))
        if not g["frames"]:
            problems.append("%s has no frames: the symbol cannot play" % where)
        elif len(g["frames"]) != len(w["frames"]):
            problems.append("%s has %d frame(s), the export wrote %d"
                            % (where, len(g["frames"]), len(w["frames"])))
        else:
            for n, (a, b) in enumerate(zip(g["frames"], w["frames"])):
                if b is None:
                    break
                if a != b:
                    problems.append("%s frame %d points at guid %s, the sprite's "
                                    "meta says %s" % (where, n + 1, a, b))
                    break

    symbols = len(got)
    total = sum(len(g["frames"]) for g in got)
    summary = "%d symbol(s)  stage %g x %g px  symbol %g fps  capacity %g  %d frame(s)" % (
        symbols, width or 0, height or 0, fps or 0, number(block, "capacity") or 0, total)
    return problems, summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chip", type=int, help="audit one chip")
    args = ap.parse_args()

    rows = [r for r in chips() if args.chip is None or r[0] == args.chip]
    if not rows:
        raise SystemExit("no particle chip%s" % ("" if args.chip is None else " %d" % args.chip))
    failed = 0
    for cid, cdir, data in rows:
        problems, summary = audit_chip(cid, cdir, data)
        if problems:
            failed += 1
            print("chip %d  FAIL" % cid)
            for p in problems:
                print("  " + p)
        else:
            print("chip %d  %s  ok" % (cid, summary))
    print("")
    print("%d chip(s), %d failed" % (len(rows), failed))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
