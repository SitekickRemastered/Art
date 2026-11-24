#!/usr/bin/env python3
"""Give every spawned-particle prefab the runtime field its SWF effect has.

`build_chips.py` can only bake four particle copies on fixed columns, because a
prefab needs concrete transforms.  The spawn rule itself lives in ActionScript
(`FlakeMC.init`, `BubbleMC.init`, `effect_NNNNN.onTimer`) and the particle's own
symbol plays 8..200 frames that the bake shows one of.  `ChipParticleField` runs
the rule instead; this script writes its data into the prefab:

  * one entry per distinct particle *symbol* (chips 151 and 152 use one, 1109
    uses four, 1133 two), with every exported frame in order and the direction
    `build_effect_clips.py` read from the class;
  * the spawn rate and lifetime from the same AS3 (`maxPerSecond`,
    `minLifetime`, `maxLifetime`);
  * the stage and frame rate from the chip's effect json.

The component is added to the prefab root, so the field sits where the effect's
stage sits; it places particles under `chip_XXXX_extras`, which already carries
STAGE_OFFSET.

    python3 Tools/SwfToSvg/build_particle_fields.py            # report
    python3 Tools/SwfToSvg/build_particle_fields.py --write     # patch prefabs

Idempotent: the block is rebuilt from the json each run and the file is only
written when the text differs.  Nothing else in the prefab is touched -- the
baked copies stay, and the field hides them on its first update, so a held
capture (`ChipPlayCheck --hold`) still measures the authored pose.
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
SPRITE_LOCAL_ID = 3286163911610860551

# `corus.effects.FlakeMC` / `BubbleMC`, and what `effect_NNNNN.onTimer` adds.
# build_effect_clips.py records these in effect_clips.json; the defaults below
# are the shared rule (Math.random() * 10 a second, 3 + random * 5 s) and every
# particle chip in the library uses it.
DEFAULT_TICK = (1.0, 10, (3.0, 8.0))


def spawn_rule(cid):
    """The rule `build_effect_clips.py` read out of the chip's effect class.

    Returns (interval seconds, burst size, lifetime range).  FlakeMC's init is
    `Timer(1000)` + `Math.random() * 10` added per tick, and its tween length is
    `3 + int(Math.random() * 6)`; both are read from the AS3 when the export has
    it, and the fallbacks are those same numbers.
    """
    path = os.path.join(HERE, "effect_clips.json")
    try:
        clips = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError):
        return DEFAULT_TICK
    rule = (clips.get(str(cid)) or {}).get("spawn") or {}
    return (float(rule.get("intervalSeconds", DEFAULT_TICK[0])),
            int(rule.get("burst", DEFAULT_TICK[1])),
            tuple(rule.get("lifetime", DEFAULT_TICK[2])))


def meta_guid(svg_path):
    meta = svg_path + ".meta"
    if not os.path.exists(meta):
        return None
    m = re.search(r"^guid: ([0-9a-f]{32})", open(meta, encoding="utf-8").read(), re.M)
    return m.group(1) if m else None


def prefab_block(comp_id, go_id, entries, interval, burst, lifetime, fps):
    lines = ["--- !u!114 &%d" % comp_id,
             "MonoBehaviour:",
             "  m_ObjectHideFlags: 0",
             "  m_CorrespondingSourceObject: {fileID: 0}",
             "  m_PrefabInstance: {fileID: 0}",
             "  m_PrefabAsset: {fileID: 0}",
             "  m_GameObject: {fileID: %d}" % go_id,
             "  m_Enabled: 1",
             "  m_EditorHideFlags: 0",
             "  m_Script: {fileID: 11500000, guid: %s, type: 3}" % SCRIPT_GUID,
             "  m_Name: ",
             "  m_EditorClassIdentifier: ",
             "  art:"]
    for e in entries:
        lines.append("  - name: %s" % e["name"])
        lines.append("    rising: %d" % (1 if e["rising"] else 0))
        lines.append("    frames:")
        for guid in e["guids"]:
            lines.append("    - {fileID: %d, guid: %s, type: 3}" % (SPRITE_LOCAL_ID, guid))
    lines += ["  spawnInterval: %s" % fmt(interval),
              "  spawnBurst: %s" % fmt(burst),
              "  minLifetime: %s" % fmt(lifetime[0]),
              "  maxLifetime: %s" % fmt(lifetime[1]),
              "  stageWidth: 375",
              "  stageHeight: 300",
              "  margin: 25",
              "  frameRate: %s" % fmt(fps),
              "  capacity: 96"]
    return "\n".join(lines) + "\n"


def fmt(v):
    return ("%g" % v) if v != int(v) else str(int(v))


def chips():
    for range_dir in sorted(glob.glob(os.path.join(CHIPS, "*"))):
        if not os.path.isdir(range_dir):
            continue
        for name in sorted(os.listdir(range_dir)):
            m = re.match(r"Chip_(\d{4})$", name)
            if not m:
                continue
            cdir = os.path.join(range_dir, name)
            js = glob.glob(os.path.join(cdir, "Sprites", "*_effect.json"))
            if js:
                yield int(m.group(1)), cdir, json.load(open(js[0], encoding="utf-8"))


def build(cid, cdir, data):
    particles = ((data.get("clips") or {}).get("particles")) or []
    if not particles:
        return None
    seen, entries = set(), []
    for p in particles:
        symbol = p.get("symbol")
        if symbol in seen:
            continue
        seen.add(symbol)
        art = p.get("art")
        names = art if isinstance(art, list) else [art]
        guids = [meta_guid(os.path.join(cdir, "Sprites", n)) for n in names if n]
        guids = [g for g in guids if g]
        if not guids:
            continue
        entries.append({"name": p.get("name", "particle_0"),
                        "rising": p.get("dir") == "up", "guids": guids})
    if not entries:
        return None
    return entries


def patch(cid, cdir, data, write):
    entries = build(cid, cdir, data)
    if not entries:
        return None
    prefab = os.path.join(cdir, "Chip_%04d_Effect.prefab" % cid)
    if not os.path.exists(prefab):
        return None
    text = open(prefab, encoding="utf-8").read()

    # the root GameObject is the one named Chip_XXXX_Effect
    m = re.search(r"--- !u!1 &(\d+)\nGameObject:\n(.*?)(?=\n--- )", text, re.S)
    if not m:
        return None
    go_id = int(m.group(1))

    # Drop a previous copy of this component block, and its component reference.
    # Split on the block markers first: a regex that tries to find the m_Script
    # line inside a block will happily run from the *first* MonoBehaviour in the
    # file to ours at the end, which deletes everything in between.
    parts = re.split(r"(?m)^(?=--- !u!)", text)
    kept, stale = [], []
    for part in parts:
        if part.startswith("--- !u!114 ") and SCRIPT_GUID in part:
            m = re.match(r"--- !u!114 &(\d+)", part)
            if m:
                stale.append(m.group(1))
            continue
        kept.append(part)
    text = "".join(kept)
    for old_id in stale:
        text = re.sub(r"^  - component: \{fileID: %s\}\n" % old_id, "",
                      text, count=1, flags=re.M)

    used = set(int(x) for x in re.findall(r"^--- !u!\d+ &(\d+)", text, re.M))
    comp_id = max(used) + 1 if used else 100001
    interval, burst, lifetime = spawn_rule(cid)
    block = prefab_block(comp_id, go_id, entries, interval, burst, lifetime,
                         data.get("fps", 31))

    # add the component to the root's list, after its last component line
    root = re.search(r"(--- !u!1 &%d\nGameObject:\n)(.*?)(?=\n--- )" % go_id, text, re.S)
    body = root.group(2)
    last = list(re.finditer(r"^  - component: \{fileID: \d+\}$", body, re.M))
    if not last:
        return None
    insert_at = root.start(2) + last[-1].end()
    text = text[:insert_at] + "\n  - component: {fileID: %d}" % comp_id + text[insert_at:]
    text = text.rstrip("\n") + "\n" + block

    old = open(prefab, encoding="utf-8").read()
    if write and text != old:
        open(prefab, "w", encoding="utf-8").write(text)
    return len(entries), text != old


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--ids")
    args = ap.parse_args()

    want = None
    if args.ids:
        want = set()
        for chunk in args.ids.split(","):
            chunk = chunk.strip()
            if "-" in chunk:
                a, b = chunk.split("-")
                want.update(range(int(a), int(b) + 1))
            elif chunk:
                want.add(int(chunk))

    total = changed = 0
    for cid, cdir, data in chips():
        if want and cid not in want:
            continue
        got = patch(cid, cdir, data, args.write)
        if not got:
            continue
        entries, differs = got
        total += 1
        changed += 1 if differs else 0
        interval, burst, lifetime = spawn_rule(cid)
        print("%-6d %d symbol(s) %s %.0f-%.0f per %.0f s, life %.0f-%.0f s%s"
              % (cid, entries, "changed" if differs else "already", 0, burst - 1,
                 interval, lifetime[0], lifetime[1],
                 "" if args.write else "  (dry run)"))
    print("\n%d particle prefabs, %d would change%s"
          % (total, changed, "" if args.write else "; pass --write to apply"))


if __name__ == "__main__":
    main()
