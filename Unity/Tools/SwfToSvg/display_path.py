#!/usr/bin/env python3
"""Derive a chip's display path from its ActionScript.

The site never plays a chip movie from its first frame.  `sitekick.swf`'s
`funcLoadDisplay` loads `effect.swf?...&display=true` offscreen and, once the
movie is fully loaded, calls

    this.effectHolder.gotoAndPlay("display");

so a chip either has a `display` label and starts there, or the call does
nothing and the root stays wherever it stopped.  From that frame on the movie
plays, parks the clips its scripts name, and repeats one block for as long as the
chip is worn.  Reading that off a new chip by hand is what AGENTS.md records one
chip at a time; this derives it from the movie's own ActionScript:

  entry   the label the host asks for, whether the root has it, the frame it
          lands on, and the frame the root rejoins when the display frame is a
          setup frame (chip 14's root 33 parks the spider and goes to `hover`,
          chip 8's root 40 waits for its tool info and then goes to `hover`)
  parks   clips a script sends to a fixed label, resolved to the sprite and the
          frame it lands on (`spider.gotoAndStop("display")` -> #64 frame 21),
          with the `if` it sits inside when the park is conditional (chip 7's
          rings only go to `special` when the score tops out, so with the
          server's default record they stay on their own frame 1), including
          the self-park a clip does when the display flag is set: chip 16's
          `body` frame 1 tests `effect.display` and parks itself on `display`,
          which is the whole display state because that root has no `display`
          label to jump to
  cut     the block the root repeats -- the first backward jump (`hover_loop`),
          the held frame a `stop()` leaves instead (chip 13), the click cycle of
          a root that waits for a button (chip 12), or no motion at all when the
          root stops on frame 1 and the host's call misses (chip 16)
  cues    every sound start resolved to its root frame and the clips it plays
          inside, marked dead when the movie's last frame is past it or when the
          clip it sits in is parked as one static frame

`--check` re-derives chips 7-16 and compares the answer with the constants the
hand-authored patches encode (`patch_chip13/14/15/16.py`) and the loop ranges
AGENTS.md records, so a change to these rules is caught before they are trusted
on a new chip.

The scripts are the ones FFDec exports from the *original* SWF (never the patched
copy a previous export left in the work dir), so the derivation always describes
what Flash runs, not what was authored.

What it does not resolve: a target computed at run time (chip 7's
`gotoAndStop(bestScore % 11 + 1)`), a clip reached by navigating named parents
without the leaf being placed under that name (chip 8's
`fixit.bottom.tools.antenna`), and clips parked only by their own `stop()` --
that last one is `patch_stopped_clips.py`'s freeze, which runs on every export.

Usage:  display_path.py <chip 7-16 | .swf path> [--work DIR] [--json] [--check]
"""

import argparse
import json
import os
import re
import subprocess
import sys

from lxml import etree

import hover_loop
import patch_chip7 as patch7
import patch_stopped_clips as stop_clips

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
# scratch inside the project: Temp/ is gitignored
TMP = os.path.join(ROOT, "Temp", "swftosvg")
FFDEC = stop_clips.FFDEC

HOST_LABEL = "display"      # funcLoadDisplay: effectHolder.gotoAndPlay("display")

CLIP_GOTO = re.compile(r"([\w.]+)\s*\.\s*(gotoAnd(?:Stop|Play))\s*\(\s*\"([^\"]+)\"\s*\)")
LABEL_JUMP = re.compile(r'(?:([\w.\[\]"+]+)\s*\.\s*)?gotoAnd(?:Play|Stop)\s*\(\s*"([^"]+)"\s*\)')
STOP = re.compile(r"(?m)^\s*stop\s*\(\s*\)\s*;")
DISPLAY_FLAG = re.compile(r"effect\s*\.\s*display|\bdisplay\s*==")


# --------------------------------------------------------------------------
# the movie as Flash runs it


def swf_path(chip):
    return os.path.join(ROOT, "SWF", "chip_%04d.swf" % chip)


def work_dir(chip):
    return os.path.join(TMP, "%04d" % chip, "path")


def sources(swf, work):
    """The original movie's XML and decompiled scripts, exported once per chip.

    A previous export leaves its own `xml/` and `scr/` behind, taken from the
    patched movie; those must not be read here, or the tool would describe the
    authored state instead of the ActionScript.
    """
    work = work or os.path.join(TMP, os.path.basename(swf)[:-4], "path")
    os.makedirs(work, exist_ok=True)
    xml = os.path.join(work, "source.xml")
    scripts = os.path.join(work, "scripts", "scripts")
    if not os.path.exists(xml):
        subprocess.run(FFDEC + ("-swf2xml", swf, xml), check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not os.path.isdir(scripts):
        subprocess.run(FFDEC + ("-export", "script", os.path.join(work, "scripts"), swf),
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return xml, scripts


def read_scripts(path):
    """Every .as file directly in a script directory, in name order."""
    if not os.path.isdir(path):
        return ""
    return "\n".join(open(os.path.join(path, name), encoding="latin1", errors="ignore").read()
                     for name in sorted(os.listdir(path)) if name.endswith(".as"))


def frame_scripts(path):
    """frame number -> that frame's ActionScript."""
    if not os.path.isdir(path):
        return {}
    out = {}
    for name in os.listdir(path):
        found = re.match(r"frame_(\d+)$", name)
        if found:
            out[int(found.group(1))] = read_scripts(os.path.join(path, name))
    return out


def sprites(tags):
    return {int(item.get("spriteId")): item for item in tags
            if item.get("type") == "DefineSpriteTag"}


def labels(item):
    """A clip's frame labels -> frame number."""
    return patch7.labels_of(item)


def placed_names(tags):
    """instance name -> character id, from every placement in the file."""
    out = {}
    for tag in stop_clips.placements(tags):
        if tag.get("name") and tag.get("characterId"):
            out.setdefault(tag.get("name"), int(tag.get("characterId")))
    return out


def instance_of(tags, cid):
    for tag in stop_clips.placements(tags):
        if tag.get("characterId") == str(cid) and tag.get("name"):
            return tag.get("name")
    return "#%d" % cid


def root_placed_at(tags):
    """character id -> the root frame it is first placed on."""
    out, frame = {}, 1
    for tag in tags:
        if tag.get("type") == stop_clips.SHOW:
            frame += 1
        elif tag.get("type", "").startswith("PlaceObject") and tag.get("characterId"):
            out.setdefault(int(tag.get("characterId")), frame)
    return out


# --------------------------------------------------------------------------
# the four things the patches encode


def entry(tags, lab, by_frame):
    """Where the host puts the root, and where that frame sends it."""
    if HOST_LABEL not in lab:
        text = by_frame.get(1, "")
        stops = bool(STOP.search(text))
        return {"label": None, "frame": 1, "rejoin": None, "stop": stops,
                "why": "the root has no `display` label, so the host's "
                       "gotoAndPlay(\"display\") does nothing and the root "
                       + ("stops on 1" if stops else "plays from 1")}

    frame = lab[HOST_LABEL]
    back = []
    for expr, name in LABEL_JUMP.findall(by_frame.get(frame, "")):
        target = lab.get(name)
        if target is not None and target < frame:
            back.append((name, target))
    return {"label": HOST_LABEL, "frame": frame, "stop": bool(STOP.search(by_frame.get(frame, ""))),
            "rejoin": back[-1] if back else None,
            "why": "the host calls effectHolder.gotoAndPlay(\"display\")"}


def enclosing_ifs(text, pos):
    """The `if (...)` blocks open at `pos`, innermost last.

    FFDec puts the `{` on its own line, so the header is the last line that is
    neither a brace nor blank.
    """
    stack, header = [], ""
    for line in text[:pos].split("\n"):
        stripped = line.strip()
        if stripped and stripped not in ("{", "}"):
            header = stripped
        for ch in line:
            if ch == "{":
                stack.append(header if header.startswith(("if", "while", "for", "function")) else "")
            elif ch == "}" and stack:
                stack.pop()
    return [s for s in stack if s.startswith("if")]


def parks(tags, spr, by_frame, frames, names):
    """Clips a script parks on a fixed label while the movie plays."""
    found = {}
    for frame in frames:
        text = by_frame.get(frame, "")
        for match in CLIP_GOTO.finditer(text):
            expr, call, label = match.group(1), match.group(2), match.group(3)
            if call != "gotoAndStop":
                continue
            name = expr.split(".")[-1]
            cid = names.get(name)
            if cid is None or cid not in spr:
                continue
            target = labels(spr[cid])
            if label not in target:
                continue
            park = {"at": frame, "clip": name, "sprite": cid, "label": label,
                    "frame": target[label],
                    "when": enclosing_ifs(text, match.start())[-1:],
                    "how": "%s.gotoAndStop(\"%s\") on root %d" % (name, label, frame)}
            # the same clip is often set again later (chip 7 extends its antenna on
            # the display frame as well): the last call is the state that lasts
            old = found.get((cid, label))
            if old is None or park["at"] > old["at"]:
                found[(cid, label)] = park
    return sorted(found.values(), key=lambda p: p["at"])


def self_parks(tags, spr, spots, by_sprite):
    """Clips that park themselves when the host's `display=true` is set."""
    out = []
    for cid, item in spr.items():
        if cid not in spots:
            continue
        text = by_sprite.get(cid, {}).get(1, "")
        if not DISPLAY_FLAG.search(text):
            continue
        target = labels(item)
        found = [m.group(1) for m in re.finditer(r"gotoAndStop\s*\(\s*\"([^\"]+)\"\s*\)", text)
                 if m.group(1) in target]
        if not found:
            continue
        out.append({"at": 1, "clip": instance_of(tags, cid), "sprite": cid,
                    "label": found[0], "frame": target[found[0]],
                    "when": [],
                    "how": "clip #%d frame 1 tests `effect.display` and parks itself "
                           "on \"%s\"" % (cid, found[0])})
    return out


def cut(tags, by_frame, loop):
    """How the root stays in its idle block."""
    at = loop[1] + 1
    lab = hover_loop.frame_labels(tags)
    for _, name in LABEL_JUMP.findall(by_frame.get(at, "")):
        if lab.get(name) == loop[0]:
            return {"kind": "jump", "at": at,
                    "how": "root %d: gotoAndStop(\"%s\")" % (at, name)}
    return {"kind": "jump", "at": at,
            "how": "root %d jumps back to %d" % (at, loop[0])}


def stop_hold(tags, verbatim, by_sprite, ent):
    """The held root a `stop()` leaves, and the clip that keeps it alive."""
    if not ent["stop"]:
        return None
    hold = ent["frame"]
    spots = root_placed_at(tags)
    playing = []
    for cid, item in sprites(tags).items():
        where = spots.get(cid)
        if where is None or where > hold:
            continue
        length = len(stop_clips.frames_of(item))
        if length < 2:
            continue
        if any(STOP.search(text) for text in by_sprite.get(cid, {}).values()):
            continue
        playing.append((cid, length, where))
    if not playing:
        return {"hold": hold, "cycle": 0, "sprite": None, "loop": (hold, hold),
                "how": "root %d stops and nothing keeps playing" % hold}
    cid, length, where = max(playing, key=lambda p: (p[1], -p[2]))
    return {"hold": hold, "cycle": length, "sprite": cid, "loop": (hold + 1, hold + length),
            "how": "root %d stops; clip #%d (placed on root %d) keeps playing its "
                   "%d-frame cycle, so the export holds %d for one cycle"
                   % (hold, cid, where, length, hold)}


def cues(tags, last, parked):
    """Every sound start, with the clips it plays inside, and whether it can fire."""
    spr = sprites(tags)
    frames = {cid: stop_clips.frames_of(item) for cid, item in spr.items()}

    owner = {}
    for tag in tags:
        if tag.get("type", "").startswith("PlaceObject") and tag.get("characterId"):
            owner.setdefault(int(tag.get("characterId")), (None, 0))
    for cid, fs in frames.items():
        for n, frame in enumerate(fs):
            for tag in frame:
                if tag.get("type", "").startswith("PlaceObject") and tag.get("characterId"):
                    owner[int(tag.get("characterId"))] = (cid, n)
    spots = root_placed_at(tags)

    found = []
    for cid, fs in frames.items():
        starts = [(n, int(tag.get("soundId"))) for n, frame in enumerate(fs)
                  for tag in frame if tag.get("type") == "StartSoundTag"]
        if not starts:
            continue
        chain, offset, node, seen = [cid], 0, cid, set()
        while node in owner and node not in seen:
            seen.add(node)
            parent, at = owner[node]
            offset += at
            if parent is None:
                break
            chain.append(parent)
            node = parent
        start = spots.get(node, 1) + offset
        for n, sound in starts:
            found.append({"frame": max(1, start + n), "sound": sound, "clips": chain})

    frame = 1
    for tag in tags:
        if tag.get("type") == "StartSoundTag":
            found.append({"frame": frame, "sound": int(tag.get("soundId")), "clips": []})
        elif tag.get("type") == stop_clips.SHOW:
            frame += 1

    found.sort(key=lambda c: (c["frame"], c["sound"]))
    out = []
    for cue in found:
        hit = [c for c in cue["clips"] if c in parked]
        if hit:
            why = "inside clip #%d, which is parked as one frame" % hit[0]
        elif cue["frame"] > last:
            why = "root frame %d is past the movie's last frame (%d)" % (cue["frame"], last)
        else:
            why = None
        out.append({"frame": cue["frame"], "sound": cue["sound"],
                    "clips": cue["clips"], "dead": why})
    return out


def derive(swf, work=None):
    """Everything the export has to author for this chip."""
    xml, scripts = sources(swf, work)
    tags = etree.parse(xml).getroot().find("tags")
    total = patch7.root_frames(tags)
    lab = hover_loop.frame_labels(tags)
    by_frame = frame_scripts(scripts)
    spr = sprites(tags)
    by_sprite = {cid: frame_scripts(os.path.join(scripts, "DefineSprite_%d" % cid))
                 for cid in spr}
    names = placed_names(tags)

    ent = entry(tags, lab, by_frame)
    loop = hover_loop.find(tags, scripts)
    held = stop_hold(tags, None, by_sprite, ent)

    if ent["label"] is None and ent["stop"] and "onRelease" not in by_frame.get(1, ""):
        # the host's call misses, the root stops, nothing in the movie plays it
        kind, loop = "static", (1, 1)
        stable = {"kind": "static", "at": 1, "how": "root 1 stops and nothing plays it"}
    elif ent["label"] is None and loop is not None:
        kind = "click"
        stable = {"kind": "click", "at": loop[1] + 1,
                  "how": "root 1 waits for a click; root %d resets it" % (loop[1] + 1)}
    elif loop is None and held is not None:
        kind, loop = "stop", held["loop"]
        stable = {"kind": "stop", "at": held["hold"], "how": held["how"]}
    elif loop is not None:
        kind = "jump"
        stable = cut(tags, by_frame, loop)
    else:
        kind, loop = "static", (ent["frame"], ent["frame"])
        stable = {"kind": "static", "at": ent["frame"],
                  "how": "root stops on the entry frame with nothing after it"}

    last = loop[1]
    # the entry frame runs even when it sits past the loop (a setup frame that
    # rejoins the block), so its parks belong to the display state too
    played = sorted(set(range(1, last + 1)) | {ent["frame"]})
    found_parks = parks(tags, spr, by_frame, [f for f in played if f <= total], names)
    found_parks += self_parks(tags, spr, root_placed_at(tags), by_sprite)
    for park in found_parks:
        park["applies"] = park["at"] <= last or park["at"] == ent["frame"]
    parked = {p["sprite"] for p in found_parks if p["applies"]}

    cue_list = cues(tags, last, parked)

    notes = []
    if ent["label"] is None:
        notes.append("the host's gotoAndPlay(\"display\") misses this root")
    elif ent["frame"] > last:
        notes.append("the entry frame %d is past the loop %d..%d: it is a setup frame "
                     "that rejoins the block" % (ent["frame"], loop[0], loop[1]))
    elif ent["frame"] > 1:
        notes.append("Flash starts at %d; the export also ships 1..%d as an intro"
                     % (ent["frame"], ent["frame"] - 1))
    if kind == "static":
        notes.append("the whole display state is root frame %d, so the export is one frame"
                     % loop[0])

    return {"swf": swf, "root_frames": total, "labels": lab, "entry": ent,
            "kind": kind, "loop": list(loop), "cut": stable,
            "hold": held["hold"] if kind == "stop" else None,
            "cycle": held["cycle"] if kind == "stop" else None,
            "parks": found_parks, "cues": cue_list, "notes": notes}


# --------------------------------------------------------------------------
# reporting


def show(path):
    print(os.path.relpath(path["swf"], ROOT))
    print("  root   %d frames, labels %s" % (
        path["root_frames"],
        ", ".join("%s %d" % (n, f) for n, f in
                  sorted(path["labels"].items(), key=lambda p: p[1])) or "none"))
    ent = path["entry"]
    print("  entry  %s" % (
        "label `%s` at root %d" % (ent["label"], ent["frame"]) if ent["label"]
        else "root %d (no `display` label)" % ent["frame"]))
    print("         %s" % ent["why"])
    if ent["rejoin"]:
        print("         root %d rejoins %d (`%s`)" % (ent["frame"], ent["rejoin"][1],
                                                      ent["rejoin"][0]))

    loop = path["loop"]
    if path["kind"] == "static":
        print("  idle   none: %s, so the display state is frame %d"
              % (path["cut"]["how"], loop[0]))
    else:
        print("  idle   %d..%d (%s), %s" % (loop[0], loop[1], path["kind"], path["cut"]["how"]))
    if path["hold"]:
        print("  hold   root %d stops; an %d-frame clip keeps it alive (loop %d..%d)"
              % (path["hold"], path["cycle"], loop[0], loop[1]))

    for park in path["parks"]:
        print("  park   %s #%d at its `%s` label, frame %d -- %s%s"
              % (park["clip"], park["sprite"], park["label"], park["frame"], park["how"],
                 "" if park["applies"] else "  (outside the played frames: unused)"))
        if park["when"]:
            guard = park["when"][-1]
            print("         %s: %s" % (("guarded by the display flag" if "display" in guard
                                        else "only inside"), guard))
    if not path["parks"]:
        print("  park   none a script names (clips that stop themselves are frozen "
              "by patch_stopped_clips.py)")

    dead = [c for c in path["cues"] if c["dead"]]
    print("  cues   %d, %d dead" % (len(path["cues"]), len(dead)))
    for cue in path["cues"]:
        print("         sound %-3d root %-3d %s" % (cue["sound"], cue["frame"],
                                                   cue["dead"] or "fires"))
    for note in path["notes"]:
        print("  note   %s" % note)


def check():
    """Re-derive chips 7-16 and compare with the hand-authored constants."""
    import patch_chip13 as patch13
    import patch_chip14 as patch14
    import patch_chip15 as patch15

    documented = {7: (15, 34), 8: (16, 35), 9: (10, 27), 10: (17, 36),
                  11: (16, 35), 12: (1, 24)}
    want_parks = {14: [(patch14.SPIDER, patch14.DISPLAY_AT)],
                  15: [(patch15.WAVE, patch15.TRANSFORMED)]}
    want_entry = {13: "display", 14: "display", 15: "display", 16: None}

    bad = 0
    for chip in range(7, 17):
        path = derive(swf_path(chip), work_dir(chip))
        loop = tuple(path["loop"])
        expected = []
        if chip in documented:
            expected.append(("loop", loop, documented[chip], "AGENTS.md ranges"))
        if chip == 13:
            expected += [("loop", loop, tuple(patch13.loop()), "patch_chip13.loop()"),
                         ("hold", path["hold"], patch13.HOLD_AT, "patch_chip13.HOLD_AT"),
                         ("cycle", path["cycle"], patch13.LOOP_FRAMES,
                          "patch_chip13.LOOP_FRAMES")]
        if chip == 14:
            expected.append(("loop", loop, tuple(patch14.loop()), "patch_chip14.loop()"))
        if chip == 15:
            expected.append(("loop", loop, tuple(patch15.loop()), "patch_chip15.loop()"))
        # chip 16's patch authors nothing and the export overrides the derived
        # range: it plays the whole root once with no loop (patch_chip16.py), so
        # there is no hand-authored range here to compare against
        if chip in want_parks:
            got = [(p["sprite"], p["frame"]) for p in path["parks"] if p["applies"]]
            expected.append(("parks", got, want_parks[chip], "the patch's sprite/frame"))
        if chip in want_entry:
            expected.append(("entry", path["entry"]["label"], want_entry[chip],
                             "host gotoAndPlay(\"display\")"))

        for what, got, want, source in expected:
            ok = got == want
            bad += 0 if ok else 1
            print("%2d  %-5s %-34s %s" % (
                chip, what,
                str(got) if ok else "%s   want %s" % (got, want),
                "ok   (%s)" % source if ok else "FAIL (%s)" % source))

    print("%d check(s) failed" % bad)
    return bad == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chip", nargs="?", default=None, help="chip number 7-16, or a .swf path")
    ap.add_argument("--swf", default=None)
    ap.add_argument("--work", default=None, help="where to cache the SWF export")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="re-derive chips 7-16 and compare with the patches")
    args = ap.parse_args()

    if args.check:
        return 0 if check() else 1
    target = args.swf or args.chip
    if not target:
        ap.error("give a chip number (7-16), a .swf path, or --check")
    if os.path.exists(target):
        swf, work = os.path.abspath(target), args.work
    else:
        chip = int(target)
        swf, work = swf_path(chip), args.work or work_dir(chip)
        if not os.path.exists(swf):
            ap.error("no SWF at %s" % swf)

    path = derive(swf, work)
    if args.json:
        print(json.dumps(path, indent=2, sort_keys=True))
    else:
        show(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
