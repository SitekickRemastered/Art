#!/usr/bin/env python3
"""Build Assets/Chips/<range>/Chip_XXXX from the SWF libraries.

Art comes from FFDec's shape/sprite SVG exports. Animation structure comes from
FFDec's -swf2xml dump (depth, character id and matrix per frame), which is
authoritative and avoids guessing from the SVG output.
"""
import argparse
import glob
import json
import os
import re
from collections import Counter

import normalize as N
from lxml import etree

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS = os.path.join(ROOT, "Assets")
SCALE = N.SCALE
SVG = "{%s}" % N.SVG
FF = "{%s}" % N.FF
IDENT = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

CHIP_LIB_RANGES = [(1, 500), (501, 1000), (1001, 1500)]
EFFECT_LIB_RANGES = [(1, 250), (251, 500), (501, 750), (751, 1000),
                     (1001, 1250), (1251, 1500)]


# ---------------------------------------------------------------- timelines
def matrix_from_item(el):
    m = el.find("matrix")
    if m is None:
        return IDENT
    f = lambda k, d=0.0: float(m.get(k, d))
    return (f("scaleX", 1.0), f("rotateSkew0"), f("rotateSkew1"),
            f("scaleY", 1.0), f("translateX") / 20.0, f("translateY") / 20.0)


def color_from_item(el):
    c = el.find("colorTransform")
    if c is None:
        return None
    return {k: c.get(k) for k in ("alphaMultTerm", "alphaAddTerm", "redMultTerm",
                                  "greenMultTerm", "blueMultTerm") if c.get(k) is not None}


def load_timelines(path, wanted=None):
    """Parse one library: (frames for `wanted` sprite ids, frameCount for all)."""
    tree = etree.parse(path)
    sprites = {}
    counts = {}
    for item in tree.iter("item"):
        if item.get("type") != "DefineSpriteTag":
            continue
        sid = int(item.get("spriteId"))
        counts[sid] = int(item.get("frameCount", "0"))
        if wanted is not None and sid not in wanted:
            continue
        state = {}
        frames = []
        sub = item.find("subTags")
        if sub is None:
            sprites[sid] = {"frames": counts[sid], "frame_list": []}
            continue
        for tag in sub:
            t = tag.get("type")
            if t == "ShowFrameTag":
                frames.append({d: dict(v) for d, v in state.items()})
            elif t in ("PlaceObject2Tag", "PlaceObject3Tag", "PlaceObjectTag"):
                depth = int(tag.get("depth", "0"))
                has_char = tag.get("placeFlagHasCharacter", "true") != "false"
                cid = tag.get("characterId")
                if has_char and cid:
                    state[depth] = {"char": int(cid), "matrix": matrix_from_item(tag),
                                    "color": color_from_item(tag), "name": tag.get("name"),
                                    "clip": tag.get("clipDepth")}
                elif depth in state:
                    if tag.find("matrix") is not None:
                        state[depth]["matrix"] = matrix_from_item(tag)
                    if tag.find("colorTransform") is not None:
                        state[depth]["color"] = color_from_item(tag)
            elif t in ("RemoveObject2Tag", "RemoveObjectTag"):
                state.pop(int(tag.get("depth", "0")), None)
        sprites[sid] = {"frames": counts[sid], "frame_list": frames}
    return {"sprites": sprites, "counts": counts}


# ---------------------------------------------------------------- libraries
def range_tag(ranges, i):
    for a, b in ranges:
        if a <= i <= b:
            return "%d_%d" % (a, b)
    return None


def index_libraries():
    chips = {}
    for d in glob.glob(os.path.join(ROOT, "Tools/out/chips_*/sprites/DefineSprite_*")):
        m = re.search(r"_chip_(\d{6})$", os.path.basename(d))
        if m:
            chips.setdefault(range_tag(CHIP_LIB_RANGES, int(m.group(1))), {})[int(m.group(1))] = d

    effects = {}
    for tag in ("%d_%d" % r for r in EFFECT_LIB_RANGES):
        base = os.path.join(ROOT, "Tools/out/effects_%s" % tag)
        sprites, shapes, eff = {}, {}, {}
        for d in glob.glob(os.path.join(base, "sprites", "DefineSprite_*")):
            sid = re.match(r"DefineSprite_(\d+)", os.path.basename(d))
            if not sid:
                continue
            # every sprite is a potential part symbol; only the ones FFDec also
            # names `effect_XXXXXX` are effect entry points for a chip
            sprites[int(sid.group(1))] = d
            m = re.search(r"effect_(\d{6})$", os.path.basename(d))
            if m:
                eff[int(m.group(1))] = (d, int(sid.group(1)))
        for f in glob.glob(os.path.join(base, "shapes", "*.svg")):
            b = os.path.basename(f)[:-4]
            if b.isdigit():
                shapes[int(b)] = f
        morphs = {}
        for f in glob.glob(os.path.join(base, "morphshapes", "*.svg")):
            b = os.path.basename(f)[:-4]
            if b.isdigit():
                morphs[int(b)] = f
        effects[tag] = {"sprites": sprites, "shapes": shapes, "morphs": morphs,
                        "effects": eff,
                        "xml": os.path.join(base, "lib.xml")}
    return chips, effects


_TL_CACHE = {}


def timelines(tag, effects):
    if tag in _TL_CACHE:
        return _TL_CACHE[tag]
    lib = effects[tag]
    wanted = {sid for _, sid in lib["effects"].values()}
    data = load_timelines(lib["xml"], wanted)
    _TL_CACHE.clear()          # only one library's timelines are needed at a time
    _TL_CACHE[tag] = data
    return data


# ---------------------------------------------------------------- helpers
def chip_dir(i):
    start = ((i - 1) // 100) * 100 + 1
    return os.path.join(ASSETS, "Chips", "%04d-%04d" % (start, start + 99), "Chip_%04d" % i)


def frame_files(d):
    fs = [f for f in glob.glob(os.path.join(d, "*.svg")) if os.path.basename(f)[:-4].isdigit()]
    return sorted(fs, key=lambda p: int(os.path.basename(p)[:-4]))


def counts_by_depth(frames):
    """depth -> list of (char, matrix) across frames (None when the depth is empty)."""
    depths = set()
    for fr in frames:
        depths.update(fr)
    out = {}
    for d in sorted(depths):
        seq = []
        for fr in frames:
            p = fr.get(d)
            seq.append((p["char"], tuple(round(v, 4) for v in p["matrix"])) if p else None)
        out[d] = seq
    return out


def moving_depths(frames, counts):
    """Depths that move, appear/disappear, or reference a multi-frame sprite.

    Depth slots with a clipDepth are masks (FFDec already bakes the clip into
    the SVG), so they stay with the base art.
    """
    masks = {d for fr in frames for d, p in fr.items() if p.get("clip")}
    moves = set()
    for d, seq in counts_by_depth(frames).items():
        if d in masks:
            continue
        if any(s is None or s != seq[0] for s in seq):
            moves.add(d)
            continue
        cid = seq[0][0]
        if counts.get(cid, 1) > 1:
            moves.add(d)
    return moves


def remove_uses(top_g, wanted):
    """Remove <use> elements matching (characterId, matrix) counts in `wanted`."""
    left = Counter(wanted)
    for use in list(top_g.iter(SVG + "use")):
        cid = use.get(FF + "characterId")
        if not cid:
            continue
        tr = tuple(round(v, 3) for v in N.parse_transform(use.get("transform")))
        for key, n in list(left.items()):
            if n <= 0 or key[0] != cid:
                continue
            if all(abs(a - b) < 0.002 for a, b in zip(key[1], tr)):
                left[key] -= 1
                parent = use.getparent()
                if parent is not None:
                    parent.remove(use)
                break
    return left


CLIPS = {}

# SWF stage (lib.xml displayRect 11000x8000 twips) and the particle field the
# prefab needs: the SWF spawns up to 9 particles a second for 3-8 seconds, so a
# fixed set of copies on separate animators stands in for that stream
STAGE_SWF = (550.0, 400.0)
PARTICLES = 4
PARTICLE_SECONDS = (3.5, 4.5, 5.5, 6.5)


def load_clip_map():
    """chip id -> the extra symbols its effect class draws (Tools/SwfToSvg/effect_clips.json)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "effect_clips.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def clips_field(res):
    return {"clips": res["clips"]} if res.get("clips") else {}


def export_symbol(lib, sprites_dir, write, sid, prefix, res):
    """Convert every frame of a clip symbol; returns (names, meta) or None."""
    src = lib["sprites"].get(sid)
    if not src:
        return None
    frames = frame_files(src)
    if not frames:
        return None
    names, meta = [], None
    for n, f in enumerate(frames, 1):
        name = ("%s.svg" % prefix if len(frames) == 1 else "%s_f%03d.svg" % (prefix, n))
        meta = N.convert(f, os.path.join(sprites_dir, name) if write else "/tmp/_probe.svg",
                         scale=SCALE)
        names.append(name)
        res["files"].append("Sprites/" + name)
    return names, meta


def add_clips(i, lib, sprites_dir, write, res):
    """Export the art a background/foreground chip draws besides its own symbol.

    A background effect's class is often just a shell that instantiates a
    separate `Back_<chip>` clip (`backClip`), a foreground adds a `frontClip`, and
    some effects spawn particles instead of using a timeline at all.
    """
    clip = CLIPS.get(str(i))
    if not clip:
        return
    out = {}
    for kind in ("back", "front"):
        info = clip.get(kind)
        if not info:
            continue
        got = export_symbol(lib, sprites_dir, write, info["symbol"],
                            "chip_%04d_%s" % (i, kind), res)
        if not got:
            continue
        names, meta = got
        out[kind] = {"art": names[0] if len(names) == 1 else names, "frames": len(names),
                     "symbol": info["symbol"],
                     "size_px": [round(v, 2) for v in meta["size_px"]],
                     "origin_px": [round(v, 2) for v in meta["origin_px"]]}

    particles = []
    for n, p in enumerate(clip.get("particles") or []):
        got = export_symbol(lib, sprites_dir, write, p["symbol"],
                            "chip_%04d_particle_%d" % (i, n), res)
        if not got:
            continue
        names, meta = got
        particles.append({"art": names[0] if len(names) == 1 else names, "frames": len(names),
                          "dir": p.get("dir", "down"), "symbol": p["symbol"],
                          "size_px": [round(v, 2) for v in meta["size_px"]],
                          "origin_px": [round(v, 2) for v in meta["origin_px"]]})
    if particles:
        copies = []
        for n in range(PARTICLES):
            v = dict(particles[n % len(particles)])
            v["name"] = "particle_%d" % n
            v["seconds"] = PARTICLE_SECONDS[n % len(PARTICLE_SECONDS)]
            v["x_swf"] = round(-STAGE_SWF[0] / 2.0 + (n + 0.5) * STAGE_SWF[0] / PARTICLES, 2)
            copies.append(v)
        out["particles"] = copies
    if out:
        res["clips"] = out


def part_source(lib, cid):
    if cid in lib["sprites"]:
        return "sprite", lib["sprites"][cid]
    if cid in lib["shapes"]:
        return "shape", lib["shapes"][cid]
    if cid in lib.get("morphs", {}):
        # a morph shape has no single pose; its start outline is the still art,
        # the transform track still moves it
        return "shape", lib["morphs"][cid]
    return None, None


def load_chipdata_index():
    idx = {}
    for base in ("Assets/Chips", "Assets/NewChips"):
        for a in glob.glob(os.path.join(ROOT, base, "**", "*.asset"), recursive=True):
            txt = open(a, encoding="utf-8", errors="ignore").read()
            m = re.search(r"^\s*id:\s*(-?\d+)\s*$", txt, re.M)
            if not m:
                continue
            idx[int(m.group(1))] = {
                "effectType": int(re.search(r"effectType:\s*(-?\d+)", txt).group(1)),
                "effectLayer": int(re.search(r"effectLayer:\s*(-?\d+)", txt).group(1)),
                "effectFlags": int(re.search(r"effectFlags:\s*(-?\d+)", txt).group(1)),
            }
    return idx


CHIPDATA_TEMPLATE = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!114 &11400000
MonoBehaviour:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  m_GameObject: {fileID: 0}
  m_Enabled: 1
  m_EditorHideFlags: 0
  m_Script: {fileID: 11500000, guid: c0aab5fa3ce84a64a88001011186524e, type: 3}
  m_Name: Chip___ID4__
  m_EditorClassIdentifier: 
  id: __ID__
  effectType: __TYPE__
  effectLayer: __LAYER__
  effectFlags: __FLAGS__
"""


def chipdata_text(i, data):
    return (CHIPDATA_TEMPLATE.replace("__ID4__", "%04d" % i)
            .replace("__ID__", str(i))
            .replace("__TYPE__", str(data["effectType"]))
            .replace("__LAYER__", str(data["effectLayer"]))
            .replace("__FLAGS__", str(data["effectFlags"])))


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def build_chip(i, write, chipdata, chip_icons, effects):
    d = chip_dir(i)
    sprites_dir = os.path.join(d, "Sprites")
    res = {"chip": i, "mode": "none", "files": [], "parts": [], "dynamic": []}
    if write:
        os.makedirs(sprites_dir, exist_ok=True)

    icon_dir = chip_icons.get(range_tag(CHIP_LIB_RANGES, i), {}).get(i)
    icon = os.path.join(icon_dir, "1.svg") if icon_dir else None
    if icon and not os.path.exists(icon):
        icon = None
    res["icon"] = bool(icon)
    if icon:
        out = os.path.join(sprites_dir, "chip_%04d.svg" % i)
        meta = N.convert(icon, out if write else "/tmp/_probe.svg", scale=SCALE)
        res["files"].append("Sprites/chip_%04d.svg" % i)
        res["icon_size"] = [round(v, 2) for v in meta["size_px"]]

    data = chipdata.get(i) or {"effectType": 0, "effectLayer": 0, "effectFlags": 0}
    res["data"] = data
    asset = os.path.join(d, "Chip_%04d.asset" % i)
    if write and (not os.path.exists(asset) or os.path.getsize(asset) < 100):
        open(asset, "w", encoding="utf-8").write(chipdata_text(i, data))

    etag = range_tag(EFFECT_LIB_RANGES, i)
    lib = effects.get(etag)
    eff = lib["effects"].get(i) if lib else None
    if lib:
        add_clips(i, lib, sprites_dir, write, res)
    if not eff:
        return blank_effect(res, sprites_dir, i, write)
    eff_dir, sid = eff
    tl = timelines(etag, effects)
    sp = tl["sprites"].get(sid)
    if not sp or not sp["frame_list"] or not any(sp["frame_list"]):
        return blank_effect(res, sprites_dir, i, write)

    frames = sp["frame_list"]
    files = frame_files(eff_dir)
    moves = moving_depths(frames, tl["counts"])
    res["dynamic"] = sorted({p["char"] for fr in frames for d, p in fr.items() if d in moves})
    source = "effectlibrary%s.swf" % etag

    # first frame that actually draws something
    first_idx = next((n for n, fr in enumerate(frames) if fr), 0)
    first_file = files[min(first_idx, len(files) - 1)]
    # prefer a frame that still has static content once moving instances go
    for n, fr in enumerate(frames):
        if fr and any(d not in moves for d in fr):
            first_idx = n
            first_file = files[min(n, len(files) - 1)]
            break

    if not moves:
        out_name = "chip_%04d_effect.svg" % i
        out_path = os.path.join(sprites_dir, out_name)
        meta = N.convert(first_file, out_path if write else "/tmp/_probe.svg", scale=SCALE)
        if write:
            meta.update(N.crop_to_content(out_path) or {})
        res["mode"] = "static"
        res["files"].append("Sprites/" + out_name)
        if write:
            write_json(os.path.join(sprites_dir, "chip_%04d_effect.json" % i), {
                "chip": i, "source": source, "scale": SCALE,
                "fps": 31, "frames": len(frames), "mode": "static",
                "art": out_name,
                "art_size_px": [round(v, 2) for v in meta["size_px"]],
                "origin_px": [round(v, 2) for v in meta["origin_px"]],
                "effectType": data["effectType"], "effectLayer": data["effectLayer"],
                **clips_field(res),
            })
        return res

    # ---- animated: base (static instances on the first drawing frame)
    res["mode"] = "animated"
    wanted = Counter()
    for depth in moves:
        p = frames[first_idx].get(depth)
        if p:
            wanted[(str(p["char"]), tuple(round(v, 3) for v in p["matrix"]))] += 1

    base_name = "chip_%04d_base.svg" % i
    base_path = os.path.join(sprites_dir, base_name)
    if wanted:
        base_meta = N.convert(first_file, base_path if write else "/tmp/_probe.svg",
                              scale=SCALE, drop_uses=set(wanted))
    else:
        base_meta = N.convert(first_file, base_path if write else "/tmp/_probe.svg", scale=SCALE)
    if write:
        base_meta.update(N.crop_to_content(base_path) or {})
    res["files"].append("Sprites/" + base_name)

    parts = []
    for cid in res["dynamic"]:
        kind, src = part_source(lib, cid)
        entry = {"character_id": cid, "kind": kind, "subframes": 1}
        if not src:
            entry["missing"] = True
            parts.append(entry)
            continue
        if kind == "shape":
            name = "chip_%04d_part_%s.svg" % (i, cid)
            meta = N.convert(src, os.path.join(sprites_dir, name) if write else "/tmp/_probe.svg",
                             scale=SCALE)
            entry.update(art=name, size_px=[round(v, 2) for v in meta["size_px"]],
                         origin_px=[round(v, 2) for v in meta["origin_px"]])
            res["files"].append("Sprites/" + name)
        else:
            sub = frame_files(src)
            entry["subframes"] = len(sub) or 1
            names = []
            for n, f in enumerate(sub, 1):
                name = ("chip_%04d_part_%s.svg" % (i, cid) if len(sub) == 1 else
                        "chip_%04d_part_%s_f%03d.svg" % (i, cid, n))
                meta = N.convert(f, os.path.join(sprites_dir, name) if write else "/tmp/_probe.svg",
                                 scale=SCALE)
                entry.update(size_px=[round(v, 2) for v in meta["size_px"]],
                             origin_px=[round(v, 2) for v in meta["origin_px"]])
                res["files"].append("Sprites/" + name)
                names.append(name)
            entry["art"] = names[0] if len(names) == 1 else names
        parts.append(entry)
    res["parts"] = parts

    tracks = []
    for n, fr in enumerate(frames, 1):
        moving = []
        for depth in sorted(moves):
            p = fr.get(depth)
            if not p:
                moving.append({"depth": depth, "absent": True})
                continue
            moving.append({"depth": depth, "character_id": p["char"],
                           "matrix": [round(v, 5) for v in p["matrix"]],
                           **({"color": p["color"]} if p.get("color") else {})})
        tracks.append({"frame": n, "moving": moving})

    if write:
        write_json(os.path.join(sprites_dir, "chip_%04d_effect.json" % i), {
            "chip": i, "source": source, "scale": SCALE,
            "fps": 31, "frames": len(frames), "mode": "animated",
            "canvas_size_px": [round(v, 2) for v in base_meta["size_px"]],
            "canvas_origin_px": [round(v, 2) for v in base_meta["origin_px"]],
            "base": base_name, "parts": parts, "tracks": tracks,
            "effectType": data["effectType"], "effectLayer": data["effectLayer"],
            **clips_field(res),
        })
    return res


def blank_effect(res, sprites_dir, i, write):
    res["mode"] = "blank"
    name = "chip_%04d_effect.svg" % i
    if write:
        N.convert(None, os.path.join(sprites_dir, name), blank=True)
        res["files"].append("Sprites/" + name)
        if res.get("clips"):
            # a background chip's own symbol is empty; the backdrop is the effect
            write_json(os.path.join(sprites_dir, "chip_%04d_effect.json" % i), {
                "chip": i, "source": None, "scale": SCALE,
                "fps": 31, "frames": 0, "mode": "blank", "art": None,
                **clips_field(res),
            })
    return res


def delete_pngs(a, b, write):
    removed = []
    for i in range(a, b + 1):
        dirs = [chip_dir(i)] + glob.glob(os.path.join(ASSETS, "NewChips", "*", "Chip_%04d" % i))
        for base in dirs:
            for p in (glob.glob(os.path.join(base, "Sprites", "*.png")) +
                      glob.glob(os.path.join(base, "Sprites", "*.png.meta")) +
                      glob.glob(os.path.join(base, "Masks", "*.png")) +
                      glob.glob(os.path.join(base, "Masks", "*.png.meta"))):
                removed.append(os.path.relpath(p, ROOT))
                if write:
                    os.remove(p)
    return removed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--ids", default="1-1500")
    ap.add_argument("--delete-pngs", action="store_true")
    args = ap.parse_args()
    a, b = (int(x) for x in args.ids.split("-"))
    chipdata = load_chipdata_index()
    CLIPS.update(load_clip_map())
    print("clip map:", len(CLIPS), "chips")
    print("indexing libraries...")
    chip_icons, effects = index_libraries()
    print("chip icons:", sum(len(v) for v in chip_icons.values()),
          "effect symbols:", {k: len(v["effects"]) for k, v in effects.items()})
    results = [build_chip(i, args.write, chipdata, chip_icons, effects) for i in range(a, b + 1)]
    modes = Counter(r["mode"] for r in results)
    print("built", len(results), dict(modes))
    print("missing icons:", [r["chip"] for r in results if not r["icon"]][:40],
          "count", sum(1 for r in results if not r["icon"]))
    print("animated:", [(r["chip"], r["dynamic"]) for r in results if r["mode"] == "animated"])
    print("blank count:", sum(1 for r in results if r["mode"] == "blank"))
    print("blank:", [r["chip"] for r in results if r["mode"] == "blank"])
    print("files:", sum(len(r["files"]) for r in results))
    if args.delete_pngs:
        gone = delete_pngs(a, b, args.write)
        print("pngs %s: %d" % ("deleted" if args.write else "to delete", len(gone)))


if __name__ == "__main__":
    main()
