#!/usr/bin/env python3
"""Freeze clips that stop themselves and are never restarted by a script.

Every chip movie in 7-16 is built the same way: parts sit on a clip whose first
frame ends in `stop()`, and the timeline after that frame is only reachable
because ActionScript jumps the clip there (`antenna1.gotoAndStop("extended")`).
FFDec never runs a script, so it plays those clips straight through and then
loops them: art that should be parked appears, animates and repeats, and a
two-frame clip like chip 8's `bottom` alternates every frame.

This pass finds the stopped clips and freezes the ones no script can reach:

  * the clip is defined, has at least two frames and stops on frame k,
  * frames after k draw something, *or* k is the last frame -- a stop before the
    end leaves art FFDec plays on into, and a stop on the end leaves none but
    still loops back to frame 1, because dropping the action is exactly what the
    freeze does,
  * the clip is actually placed on the timeline, and
  * no script mentions any instance name that clip is placed under.  A name that
    appears anywhere in the ActionScript is left alone: that clip is script-
    driven and needs its jumps authored by hand (as chip 8's bottom, antenna and
    tool are in patch_chip8_tools.py), not frozen.

A frozen clip is repointed at every placement and renders its parked state for
the whole movie.  A stop before the end keeps frames 1..k (their actions
dropped); a stop on the last frame has nothing to cut to -- k frames with the
action gone would just loop 1..k again -- so its frames are merged into the one
pose at k, which is what Ruffle holds.  That is chip 11's fringe (sprite 36),
five frames of moves ending on the spiky outline, which used to cycle and read
as a smooth cap.

Usage:  patch_stopped_clips.py <in.swf> <out.swf>
"""

import argparse
import copy
import glob
import os
import re
import shutil
import subprocess
import sys

from lxml import etree

SHOW = "ShowFrameTag"
FFDEC = ("flatpak", "run", "--command=ffdec.sh", "com.jpexs.decompiler.flash")


def frames_of(item):
    frames, current = [], []
    for sub in item.find("subTags"):
        if sub.get("type") == SHOW:
            frames.append(current)
            current = []
        else:
            current.append(sub)
    if current:
        frames.append(current)
    return frames


def is_art(tag):
    return not tag.get("type", "").startswith("DoAction")


def stop_frame(frames):
    """1-based index of the frame whose actions stop the clip, else None."""
    for i, frame in enumerate(frames):
        for tag in frame:
            if tag.get("type") == "DoActionTag":
                if b"\x07" in bytes.fromhex(tag.get("actionBytes") or ""):
                    return i + 1
    return None


def held_frames(frames, k):
    """The single frame a frozen clip shows.

    Cutting at a stop before the end keeps frames 1..k, which for the parks
    these chips use is one frame anyway.  A stop *on* the last frame cannot be
    cut that way -- writing all k frames without their action loops them again
    -- so they are merged: a sprite timeline is incremental, so replaying every
    frame's tags in order without the ShowFrames between them is exactly the
    display list of frame k.
    """
    if k < len(frames):
        return frames[:k]
    return [[tag for frame in frames for tag in frame if is_art(tag)]]


def jumps_later(frames, k):
    """True if the clip moves itself after the stop: it would loop on its own."""
    for frame in frames[k:]:
        for tag in frame:
            if tag.get("type") == "DoActionTag":
                raw = bytes.fromhex(tag.get("actionBytes") or "").lower()
                if b"gotoandplay" in raw or b"gotoandstop" in raw:
                    return True
    return False


def placements(tags):
    """Every PlaceObject in the file, root and sprites alike."""
    for tag in tags:
        if tag.get("type", "").startswith("PlaceObject"):
            yield tag
        elif tag.get("type") == "DefineSpriteTag":
            for sub in tag.find("subTags"):
                if sub.get("type", "").startswith("PlaceObject"):
                    yield sub


def script_text(script_dir):
    text = []
    for path in glob.glob(os.path.join(script_dir, "**", "*.as"), recursive=True):
        text.append(open(path, encoding="latin1", errors="ignore").read())
    return "\n".join(text)


def dynamic_prefixes(text):
    """Instance-name stems the scripts build on the fly.

    Chip 7 addresses its buttons as `bfly["btn" + i]`, so no script ever spells
    out `btn1`: a clip named btn1 is still script-driven.  Collect the stems used
    next to a goto call and match clip names against them.
    """
    stems = set()
    for m in re.finditer(r"gotoAnd(?:Play|Stop)\s*\(", text):
        window = text[max(0, m.start() - 240):m.start()]
        stems.update(re.findall(r'"(\w+)"\s*\+', window))
    return stems


def define(tags, sprite_id, frames):
    item = etree.SubElement(tags, "item", type="DefineSpriteTag", spriteId=str(sprite_id))
    sub = etree.SubElement(item, "subTags")
    for frame in frames:
        for tag in frame:
            if tag.get("type") != "DoActionTag":
                sub.append(copy.deepcopy(tag))
        sub.append(etree.Element("item", type=SHOW, forceWriteAsLong="false"))
    return item


def repoint(tags, old, new):
    hits = 0
    for tag in placements(tags):
        if tag.get("characterId") == str(old):
            tag.set("characterId", str(new))
            if tag.get("placeFlagHasRatio") == "true":
                tag.set("placeFlagHasRatio", "false")
                tag.attrib.pop("ratio", None)
            hits += 1
    return hits


def freeze(tags, text, stems=()):
    """Freeze every stopped clip no script can reach; return what was frozen."""
    names_by_char = {}
    for tag in placements(tags):
        name = tag.get("name")
        if name and tag.get("characterId"):
            names_by_char.setdefault(int(tag.get("characterId")), set()).add(name)
    placed = {int(t.get("characterId")) for t in placements(tags) if t.get("characterId")}

    sprites = [t for t in tags if t.get("type") == "DefineSpriteTag"]
    # ids are unique across every character type, not just sprites: chip 7 has a
    # DefineShape2Tag 120, so a new sprite must not be called 120
    taken = [int(t.get("shapeId") or t.get("spriteId") or t.get("characterId") or 0)
             for t in tags if t.get("type", "").startswith("Define")]
    next_id = max(taken + [0]) + 1

    frozen, skipped = [], []
    for item in sprites:
        sid = int(item.get("spriteId"))
        frames = frames_of(item)
        k = stop_frame(frames)
        if k is None or len(frames) < 2:
            continue
        # a stop before the end is only visible if something is drawn after it
        if k != len(frames) and not any(any(is_art(t) for t in f) for f in frames[k:]):
            continue
        if sid not in placed:
            continue
        if jumps_later(frames, k):
            skipped.append((sid, "moves itself"))
            continue
        names = sorted(names_by_char.get(sid, ()))
        touched = [n for n in names
                   if n in text or any(n.startswith(s) and n[len(s):].isdigit()
                                       for s in stems)]
        if touched:
            skipped.append((sid, "script: " + ", ".join(touched)))
            continue
        repoint(tags, sid, next_id)
        define(tags, next_id, held_frames(frames, k))
        frozen.append((sid, next_id, len(frames), k))
        next_id += 1
    return frozen, skipped


def ensure(src, workdir):
    """The chip's XML and exported scripts, which the decision needs."""
    xml_dir = os.path.join(workdir, "xml")
    os.makedirs(xml_dir, exist_ok=True)
    src_xml = os.path.join(xml_dir, "lib.src.xml")
    if not os.path.exists(src_xml):
        subprocess.run(FFDEC + ("-swf2xml", src, src_xml), check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    scripts = os.path.join(workdir, "scr")
    if not glob.glob(os.path.join(scripts, "**", "*.as"), recursive=True):
        subprocess.run(FFDEC + ("-export", "script", scripts, src), check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return src_xml, os.path.join(scripts, "scripts")


def patched(swf, workdir, verbose=True):
    src_xml, scripts = ensure(swf, workdir)
    text = script_text(scripts)
    tree = etree.parse(src_xml)
    tags = tree.getroot().find("tags")
    frozen, skipped = freeze(tags, text, dynamic_prefixes(text))
    if verbose:
        for old, new, frames, k in frozen:
            print("    freeze #%d (%df, stop@%d) -> #%d" % (old, frames, k, new))
        for sid, why in skipped:
            print("    keep #%d: %s" % (sid, why))
    if not frozen:
        return swf
    # written next to the chip's work files, never into the SWF folder
    out = os.path.join(workdir, os.path.basename(swf).replace(".swf", "_frozen.swf"))
    out_xml = out.replace(".swf", ".xml")
    tree.write(out_xml, encoding="UTF-8", xml_declaration=True)
    subprocess.run(FFDEC + ("-xml2swf", out_xml, out), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("swf")
    ap.add_argument("out")
    ap.add_argument("--work", default=None)
    args = ap.parse_args()
    work = args.work or os.path.dirname(os.path.abspath(args.out))
    out = patched(args.swf, work)
    if os.path.abspath(out) != os.path.abspath(args.out):
        shutil.copyfile(out, args.out)
    print(args.out)


if __name__ == "__main__":
    sys.exit(main())
