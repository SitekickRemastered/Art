#!/usr/bin/env python3
"""Turn the effect JSON frame tracks into an animation plan for the Unity builder.

The SWF display list moves one *instance* between depths, so a depth is not an
identity.  Each prefab part (named chip_XXXX_part_<depth> from the fullest frame)
finds its instance in the neighbouring frames by same character id + nearest
registration point, walking outwards from that reference frame.  The result is
one key per exported frame per part: position, rotation and scale of the SWF
matrix, plus the alpha of the instance (0 when it is not on the display list).

Output is a line bundle that Assets/Scripts/Editor/ChipAnimBuilder.cs reads:

  CHIP <id> <fps> <frames>
  PART <transform path>
  K <t> <px> <py> <rotZ deg> <scaleX> <scaleY> <alpha>
  END

Usage:  python3 Tools/SwfToSvg/build_anim_plan.py [--out FILE] [--ids 1-1375]
"""

import argparse
import glob
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_prefabs as bp  # noqa: E402


def best_frame_index(tracks):
    """Index of the frame that shows the most instances (fades start empty)."""
    best, bi = -1, 0
    for i, track in enumerate(tracks):
        visible = [e for e in track["moving"] if "character_id" in e and not e.get("absent")]
        if len(visible) > best:
            best, bi = len(visible), i
    return bi


def entry_visible(e):
    return "character_id" in e and not e.get("absent") and "matrix" in e


def nearest_instance(entries, cid, matrix):
    """Closest instance of the same character in another frame (SWF units)."""
    best, best_d = None, float("inf")
    for e in entries:
        if not entry_visible(e) or e["character_id"] != cid:
            continue
        dx = e["matrix"][4] - matrix[4]
        dy = e["matrix"][5] - matrix[5]
        d = dx * dx + dy * dy
        if d < best_d:
            best, best_d = e, d
    return best


def track_instance(tracks, ref_index, ref_entry):
    """Follow one instance from the reference frame to every other frame."""
    cid = ref_entry["character_id"]
    out = [None] * len(tracks)
    out[ref_index] = ref_entry

    cur = ref_entry
    for i in range(ref_index - 1, -1, -1):
        nxt = nearest_instance(tracks[i]["moving"], cid, cur["matrix"])
        if nxt is None:
            break
        out[i] = nxt
        cur = nxt

    cur = ref_entry
    for i in range(ref_index + 1, len(tracks)):
        nxt = nearest_instance(tracks[i]["moving"], cid, cur["matrix"])
        if nxt is None:
            break
        out[i] = nxt
        cur = nxt
    return out


def alpha_of(entry):
    col = entry.get("color") if entry else None
    if not col:
        return 1.0
    term = col.get("alphaMultTerm")
    if term is None:
        return 1.0
    try:
        return max(0.0, min(1.0, float(term) / 256.0))
    except (TypeError, ValueError):
        return 1.0


def asset_path(cdir, name):
    rel = os.path.relpath(os.path.join(cdir, "Sprites", name), bp.ROOT)
    return rel.replace(os.sep, "/")


def aux_lines(data, cdir, fps):
    """Clips that are not part of the effect timeline.

    A background/foreground clip plays its own frames, so it needs a sprite-swap
    track; spawned particles are not on a timeline at all - the SWF makes a random
    handful a second and tweens each across the stage, which becomes a stream of
    copies looping from one edge to the other.
    """
    clips = data.get("clips") or {}
    out = []
    swaps, longest = [], 0.0
    for kind in ("back", "front"):
        entry = clips.get(kind)
        if not entry:
            continue
        names = entry["art"] if isinstance(entry["art"], list) else [entry["art"]]
        usable = [asset_path(cdir, n) for n in names
                  if bp.art_usable(os.path.join(cdir, "Sprites", n))]
        if len(usable) < 2:
            continue
        swaps.append("%s/sprite %s" % (kind, " ".join(usable)))
        longest = max(longest, len(usable) / float(fps))
    if swaps:
        out.append("AUX extras %s" % bp.fnum(longest))
        out.extend("SWAP " + s for s in swaps)
        out.append("END")

    height = bp.STAGE[1] * bp.U
    for particle in clips.get("particles") or []:
        seconds = float(particle.get("seconds") or 5.0)
        up = particle.get("dir") == "up"
        y0, y1 = (-height / 2.0, height / 2.0) if up else (height / 2.0, -height / 2.0)
        fade = 0.08 * seconds
        out.append("AUX %s %s" % (particle["name"], bp.fnum(seconds)))
        for t, y, a in ((0.0, y0, 0.0),
                        (fade, y0 + (y1 - y0) * 0.08, 1.0),
                        (seconds - fade, y0 + (y1 - y0) * 0.92, 1.0),
                        (seconds, y1, 0.0)):
            out.append("M %s %s %s" % (bp.fnum(t), bp.fnum(y), bp.fnum(a)))
        out.append("END")
    return out


def plan_for(cid, cdir):
    sdir = os.path.join(cdir, "Sprites")
    jsons = glob.glob(os.path.join(sdir, "*_effect.json"))
    if not jsons:
        return None
    data = json.load(open(jsons[0], encoding="utf-8"))
    tracks = data.get("tracks") or []
    fps = int(data.get("fps") or 31)
    animatable = data.get("mode") == "animated" and bool(tracks)

    # a background chip's own symbol is empty: it still needs its clips planned
    lines = ["CHIP %d %d %d" % (data["chip"], fps, len(tracks) or 1)]
    emitted = 0
    by_char = bp.art_by_char(sdir, data) if animatable else {}
    # a part symbol with more than one frame animates by swapping its sprite,
    # exactly like a backdrop clip does: emit the frame list for the clip builder
    frames_by_char = {}
    for p in (data.get("parts") or []):
        names = p.get("art")
        if not isinstance(names, list):
            continue
        usable = [n for n in names if bp.art_usable(os.path.join(sdir, n))]
        if len(usable) > 1:
            frames_by_char[p["character_id"]] = usable
    ref_index = best_frame_index(tracks) if animatable else 0

    for ref in (sorted(tracks[ref_index]["moving"], key=lambda e: e["depth"])
                if animatable else []):
        if not entry_visible(ref):
            continue
        cid_part = ref["character_id"]
        if cid_part not in by_char:
            continue
        path = "chip_%04d_part_%d" % (data["chip"], ref["depth"])
        per_frame = track_instance(tracks, ref_index, ref)

        lines.append("PART %s" % path)
        prev_angle = None
        last = None
        for i, entry in enumerate(per_frame):
            t = i / float(data.get("fps") or 31)
            if entry is None:
                # Not on the display list: keep the last pose, fade out.
                if last is None:
                    # Before the first appearance: sit at the reference pose.
                    ref_rot, ref_scale = bp.matrix_trs(ref["matrix"])
                    px = ref["matrix"][4] * bp.U
                    py = -ref["matrix"][5] * bp.U
                    rz = math.degrees(2 * math.atan2(ref_rot[2], ref_rot[3]))
                    sx, sy = ref_scale
                else:
                    px, py, rz, sx, sy = last
                a = 0.0
            else:
                rot, scale = bp.matrix_trs(entry["matrix"])
                px = entry["matrix"][4] * bp.U
                py = -entry["matrix"][5] * bp.U
                rz = math.degrees(2 * math.atan2(rot[2], rot[3]))
                sx, sy = scale
                a = alpha_of(entry)
                last = (px, py, rz, sx, sy)

            if prev_angle is not None:
                while rz - prev_angle > 180.0:
                    rz -= 360.0
                while rz - prev_angle < -180.0:
                    rz += 360.0
            prev_angle = rz

            lines.append("K %s %s %s %s %s %s %s" % (
                bp.fnum(t), bp.fnum(px), bp.fnum(py), bp.fnum(rz),
                bp.fnum(sx), bp.fnum(sy), bp.fnum(a)))
        swap = frames_by_char.get(cid_part)
        if swap:
            lines.append("SWAP %s/sprite %s" % (
                path, " ".join(asset_path(cdir, n) for n in swap)))
        emitted += 1

    aux = aux_lines(data, cdir, fps)
    lines.extend(aux)
    lines.append("END")
    if emitted == 0 and not aux:
        return None
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  "anim_plan.txt"))
    ap.add_argument("--ids")
    args = ap.parse_args()

    ids = bp.parse_ids(args.ids) if args.ids else None
    targets = bp.chip_dirs(ids)

    out_lines = []
    chips = 0
    parts = 0
    skipped = []
    for cid, cdir in targets:
        plan = plan_for(cid, cdir)
        if plan is None:
            data_js = glob.glob(os.path.join(cdir, "Sprites", "*_effect.json"))
            if data_js:
                import json as _json
                d = _json.load(open(data_js[0], encoding="utf-8"))
                if d.get("mode") == "animated":
                    skipped.append(cid)
            continue
        chips += 1
        parts += sum(1 for L in plan if L.startswith("PART "))
        out_lines.extend(plan)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")

    print(json.dumps({"chips": chips, "parts": parts, "out": args.out}, indent=1))
    if skipped:
        print("animated chips with no plannable part:", skipped[:20], "(%d total)" % len(skipped))


if __name__ == "__main__":
    main()
