#!/usr/bin/env python3
"""Read the effect ActionScript and record the art each chip draws *besides*
its own effect symbol.

An effect class is not the whole effect.  A background chip's class is just a
shell that does

    var c:Class = getDefinitionByName("Back_543") as Class;
    backClip = new c();

and plenty of effects never use a timeline at all - chip 151 starts a timer that
spawns `FlakeMC` instances onto the stage forever, chip 152 does the same with
`BubbleMC`.  The symbol a clip or particle uses, and that symbol's frame count,
is what this script records, so the exporters can pull the art:

    Tools/out/effects_<tag>/scripts/   AS3 sources      (ffdec -export script)
    Tools/out/effects_<tag>/symbols/   SymbolClass CSV  (ffdec -export symbolClass)

Output: effect_clips.json

    { "543": { "lib": "501_750",
               "back":  { "cls": "Back_543", "symbol": 1931, "frames": 1 },
               "front": null,
               "particles": [] },
      "151": { "lib": "1_250", ..., "particles": [ { "cls": "FlakeMC",
                 "symbol": 643, "frames": 3, "dir": "up"|"down" } ] } }

Usage:  python3 Tools/SwfToSvg/build_effect_clips.py [--out FILE]
"""

import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "Tools", "out")


def symbol_maps():
    """per library: class name -> symbol id, and symbol id -> frame count."""
    maps = {}
    for lib_dir in sorted(glob.glob(os.path.join(OUT, "effects_*"))):
        tag = os.path.basename(lib_dir).replace("effects_", "")
        names = {}
        for f in glob.glob(os.path.join(lib_dir, "symbols", "*.csv")):
            for line in open(f, encoding="utf-8", errors="ignore"):
                parts = line.strip().split(";")
                if len(parts) >= 2 and parts[0].strip().isdigit():
                    names[parts[1].strip().strip('"')] = int(parts[0])
        frames = {}
        for d in glob.glob(os.path.join(lib_dir, "sprites", "DefineSprite_*")):
            m = re.match(r"DefineSprite_(\d+)", os.path.basename(d))
            if m and os.path.isdir(d):
                frames[int(m.group(1))] = len([f for f in os.listdir(d) if f.endswith(".svg")])
        scripts = os.path.join(lib_dir, "scripts")
        if os.path.isdir(os.path.join(scripts, "scripts")):
            scripts = os.path.join(scripts, "scripts")  # ffdec nests the export
        maps[tag] = {"names": names, "frames": frames, "dir": lib_dir, "scripts": scripts}
    return maps


def stage_direction(txt):
    """Falling or rising, from where init() puts the particle.

    FlakeMC starts at y = -25 (above the stage) and tweens down; BubbleMC starts
    at y = stageHeight + 25 (below it) and tweens up.
    """
    m = re.search(r"this\.y\s*=\s*([^;]+);", txt)
    if m and "stageHeight" in m.group(1):
        return "up"
    return "down"


def class_source(lib, cls):
    for rel in (("corus", "effects"), ()):
        path = os.path.join(lib["scripts"], *rel, cls + ".as")
        if os.path.exists(path):
            return open(path, encoding="utf-8", errors="ignore").read()
    return None


def spawn_rule(txt, lib, wrappers):
    """The stream a spawned-particle effect starts, read from its own AS3.

    `effect_NNNNN.onStaged` starts `new Timer(1000)` and `onTimer` adds
    `int(Math.random() * 10)` particles per tick; each particle class tweens
    itself over `3 + int(Math.random() * 6)` seconds.  Both numbers are Flash's
    rule, not the export's, so the runtime spawner reads them from here rather
    than hard-coding them (`build_particle_fields.py` writes them into the
    prefab).
    """
    m = re.search(r"new Timer\((\d+)\)", txt)
    interval = int(m.group(1)) / 1000.0 if m else 1.0

    burst = None
    timer = re.search(r"function onTimer\([^)]*\)[^{]*\{(.*?)\n\s*\}", txt, re.S)
    if timer:
        b = re.search(r"Math\.random\(\)\s*\*\s*(\d+)", timer.group(1))
        if b:
            burst = int(b.group(1))

    lifetime = None
    for cls in wrappers:
        body = class_source(lib, cls)
        if not body:
            continue
        # LeafMC has two random ints (a frame pick and the fall length), so the
        # duration variable has to come from the Tween call itself rather than
        # from the first Math.random() in init().
        t = re.search(r"new Tween\([^;]*?,(?:(\d+) \+ )?(\w+),\s*true\)", body)
        if not t:
            continue
        base, var = int(t.group(1) or 0), t.group(2)
        # FlakeMC/BubbleMC: `3 + _loc1_` seconds.  CoinMC is the bare variable,
        # i.e. a 0..n-1 s fall, which is why this reads the expression instead
        # of assuming the shared formula.
        n = re.search(r"var %s:int = Math\.random\(\)\s*\*\s*(\d+)" % var, body)
        if n:
            spread = int(n.group(1))
            lifetime = [base, base + spread - 1]
            break

    rule = {"intervalSeconds": interval}
    if burst is not None:
        rule["burst"] = burst
    if lifetime:
        rule["lifetime"] = lifetime
    return rule


def particle_symbol(lib, cls):
    """Symbol class + direction of a spawned particle.

    Some spawns are wrapper clips that instantiate a symbol (`FlakeMC` ->
    `Flake_MC`), others are the symbol class itself (`new Star_MC()`).
    """
    txt = class_source(lib, cls)
    if txt is None:
        return None, "down"
    m = re.search(r'getDefinitionByName\("([^"]+)"\)', txt)
    if m:
        return m.group(1), stage_direction(txt)
    if cls in lib["names"]:
        return cls, stage_direction(txt)
    return None, "down"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "effect_clips.json"))
    args = ap.parse_args()

    maps = symbol_maps()
    if not maps:
        sys.exit("no exports found in %s (run Tools/SwfToSvg/export_libs.sh)" % OUT)

    out = {}
    for tag, lib in maps.items():
        for path in glob.glob(os.path.join(lib["scripts"], "corus", "effects", "effect_*.as")):
            chip = int(re.search(r"effect_(\d+)\.as", path).group(1))
            txt = open(path, encoding="utf-8", errors="ignore").read()

            entry = {"lib": tag, "back": None, "front": None, "particles": []}
            defs = re.findall(r'getDefinitionByName\("([^"]+)"\)', txt)
            newed = re.findall(r"new\s+(\w+)\s*\(\s*\)", txt)
            # assign the definition names in order to backClip/frontClip
            order = re.findall(r"(\w+)\s*=\s*new\s+(\w+)", txt)
            for i, (var, cls) in enumerate(order):
                if var not in ("backClip", "frontClip"):
                    continue
                name = defs[i] if i < len(defs) else None
                if not name:
                    continue
                sym = lib["names"].get(name)
                if sym is None:
                    continue
                entry["back" if var == "backClip" else "front"] = {
                    "cls": name, "symbol": sym, "frames": lib["frames"].get(sym, 1)}

            for cls in newed:
                if not cls.endswith("MC") or cls in ("MovieClip",):
                    continue
                name, direction = particle_symbol(lib, cls)
                if not name:
                    continue
                sym = lib["names"].get(name)
                if sym is None:
                    continue
                entry["particles"].append({
                    "cls": name, "wrapper": cls, "symbol": sym,
                    "frames": lib["frames"].get(sym, 1), "dir": direction})

            if entry["particles"]:
                entry["spawn"] = spawn_rule(txt, lib,
                                            [p["wrapper"] for p in entry["particles"]])

            if entry["back"] or entry["front"] or entry["particles"]:
                prev = out.get(str(chip))
                if prev:  # an id can only live in one library, but keep the richer entry
                    for k in ("back", "front"):
                        if not entry[k]:
                            entry[k] = prev.get(k)
                    entry["particles"] = entry["particles"] or prev.get("particles", [])
                out[str(chip)] = entry

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write("\n")

    backs = sum(1 for v in out.values() if v["back"])
    fronts = sum(1 for v in out.values() if v["front"])
    parts = sum(1 for v in out.values() if v["particles"])
    animated = sum(1 for v in out.values()
                   if (v["back"] and v["back"]["frames"] > 1) or (v["front"] and v["front"]["frames"] > 1))
    print(json.dumps({"chips": len(out), "with back": backs, "with front": fronts,
                      "with particles": parts, "animated clips": animated,
                      "out": args.out}, indent=1))


if __name__ == "__main__":
    main()
