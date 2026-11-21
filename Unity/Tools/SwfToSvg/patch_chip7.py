#!/usr/bin/env python3
"""Author chip 7's scripted poses into the movie, the way its ActionScript sets them.

Chip 7 is the butterfly chip.  The clips it shows are put where they belong by
frame scripts, never by the timeline:

    root 13   bfly["wing" + getWingNum(i)]["btn" + i].wing.rings
                  .gotoAndStop(bestScore % 11 + 1)
              bfly["wing" + getWingNum(i)]["btn" + i].wing
                  .gotoAndStop(Math.ceil(bestScore / 10))
    root 44   antenna1.gotoAndStop("extended")
              antenna2.gotoAndStop("extended")

The rings (`rings`, 38/55/74/90) and the little score wings (`wing`, 50/67/86/102)
each stop on their own first frame, and with the server's default record (no stored
score, so `bestScore` is 0) the script leaves them there for the whole movie:
`0 % 11 + 1` is 1, and `ceil(0 / 10)` is 0, which is not a frame, so the clip stays
where its own `stop()` left it.  FFDec runs no script, so it advances those eight
clips one frame per root frame instead: the rings light up in a sequence and the
wings flap through a cycle the chip never plays.

`antenna1`/`antenna2` are one clip (119, 35 frames, "extended" on frame 14).  It
parks on frame 1 (`stop()`), and the only thing that ever moves it is the root 44
jump to "extended".  The real antenna is therefore folded for root frames 14-43 and
extended from 44 on, while FFDec plays the whole extend/retract animation in the
gap and reaches the extended pose at 44 by coincidence.

This pass authors both:

  * a single-frame copy per ring/wing clip (3801, 5001, 5501, 6701, 7401, 8601,
    9001, 10201) repointed at every placement -- they are placed inside the
    butterfly's buttons, under names the script builds on the fly;
  * a copy of the antenna (11901) holding frame 1 for root frames 14-43 and the
    "extended" frame from root 44, so a lockstep export shows what the script
    does.

Everything else is left to `patch_stopped_clips.py`, which freezes the stopped
clips no script reaches (`faceLines`, `knob`) and is run over the same tree here.

Usage:  patch_chip7.py <in.swf> <out.swf> [--xml cache.xml]
"""

import argparse
import copy
import os
import subprocess
import sys

from lxml import etree

import patch_stopped_clips as stop_clips

SHOW = "ShowFrameTag"
FFDEC = stop_clips.FFDEC

# every one of these parks on frame 1 with its own stop(), and the scripts
# only ever jump them to a score-dependent frame: rings -> 1, wing -> 0 (not a
# frame, so the stop stays), buttons -> untouched until a click
RINGS = (38, 55, 74, 90)          # placed as "rings", "special" on frame 12
WINGS = (48, 65, 84, 100)         # placed as "wing", 10 frames
BUTTONS = (50, 67, 86, 102)       # placed as btn1..btn4, succeed/fail labels
HOLD = RINGS + WINGS + BUTTONS
ANTENNA = 119                     # antenna1 and antenna2, "extended" on frame 14
ANTENNA_ID = 11901
EXTENDED_AT = 44                  # root frame whose script sets the antenna extended
ANTENNA_LABEL = "extended"


def sprite(tags, sid):
    for item in tags:
        if item.get("type") == "DefineSpriteTag" and int(item.get("spriteId")) == sid:
            return item
    raise AssertionError("no sprite %d" % sid)


def raw_frames(item):
    """The sprite's frames as raw tag lists: the timeline is incremental."""
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


def art_frames(item):
    """The sprite's frames with their actions dropped: what the art shows."""
    return [[t for t in frame if t.get("type") != "DoActionTag"]
            for frame in raw_frames(item)]


def labels_of(item):
    out = {}
    for n, frame in enumerate(raw_frames(item), 1):
        for tag in frame:
            if tag.get("type") == "FrameLabelTag":
                out[tag.get("name")] = n
    return out


def define(tags, sprite_id, frames):
    item = etree.SubElement(tags, "item", type="DefineSpriteTag", spriteId=str(sprite_id))
    sub = etree.SubElement(item, "subTags")
    for frame in frames:
        for tag in frame:
            sub.append(copy.deepcopy(tag))
        sub.append(etree.Element("item", type=SHOW, forceWriteAsLong="false"))
    return item


def repoint(tags, old, new):
    """Point every placement of one character at another, keeping its ratio.

    The rings are placed with a ratio (it spins the ring); the authored copy has
    to keep it or the ring would sit where the ratio says frame 0 does.
    """
    hits = 0
    for tag in stop_clips.placements(tags):
        if tag.get("characterId") == str(old):
            tag.set("characterId", str(new))
            hits += 1
    return hits


def root_frames(tags):
    return sum(1 for sub in tags if sub.get("type") == SHOW)


def first_placement(tags, char):
    """The root frame that first places `char`, from the incremental stream."""
    state, pending = {}, []
    for tag in tags:
        if tag.get("type") == SHOW:
            pending.append(dict(state))
            continue
        if tag.get("type", "").startswith("PlaceObject") and tag.get("characterId"):
            state[tag.get("depth")] = int(tag.get("characterId"))
        elif tag.get("type", "").startswith("RemoveObject"):
            state.pop(tag.get("depth"), None)
    for n, frame in enumerate(pending, 1):
        if char in frame.values():
            return n
    raise AssertionError("root never places %d" % char)


def actions_on(tags, frame):
    """The action bytes that run on root frame `frame` (1-based)."""
    seen, out = 0, []
    for tag in tags:
        if tag.get("type") == SHOW:
            seen += 1
            continue
        if tag.get("type") == "DoActionTag" and seen + 1 == frame:
            out.append(tag.get("actionBytes") or "")
    return out


def ascii_in(hex_bytes):
    raw = bytes(int(hex_bytes[i:i + 2], 16) for i in range(0, len(hex_bytes), 2))
    return raw.decode("latin1")


def author_bands(tags):
    """Hold every ring, wing and button on the frame the script leaves it on."""
    authored = []
    for sid in HOLD:
        first = art_frames(sprite(tags, sid))[0]
        new = sid * 100 + 1
        define(tags, new, [first])
        hits = repoint(tags, sid, new)
        assert hits >= 1, "nothing places %d" % sid
        authored.append((sid, new, hits))
    return authored


def author_antenna(tags):
    """Folded until root 44, extended from then on, one frame per root frame."""
    placed = first_placement(tags, ANTENNA)
    frames = art_frames(sprite(tags, ANTENNA))
    extended = labels_of(sprite(tags, ANTENNA))[ANTENNA_LABEL]
    out = []
    for root in range(placed, root_frames(tags) + 1):
        out.append(copy.deepcopy(frames[0] if root < EXTENDED_AT else frames[extended - 1]))
    define(tags, ANTENNA_ID, out)
    hits = repoint(tags, ANTENNA, ANTENNA_ID)
    assert hits == 2, "expected antenna1 and antenna2, repointed %d" % hits
    return placed, extended, len(out)


def patched(swf, workdir, verbose=True):
    """The SWF to render frames from: this chip's, with its scripted poses authored in."""
    src_xml, scripts = stop_clips.ensure(swf, workdir)
    text = stop_clips.script_text(scripts)
    tree = etree.parse(src_xml)
    tags = tree.getroot().find("tags")

    # guard: this authoring only makes sense for this movie
    frame13 = "".join(ascii_in(a) for a in actions_on(tags, 13))
    frame44 = "".join(ascii_in(a) for a in actions_on(tags, 44))
    assert "gotoAndStop" in frame13 and "rings" in frame13, "frame 13 is not the ring jump"
    assert "extended" in frame44 and "antenna" in frame44, "frame 44 is not the antenna jump"

    bands = author_bands(tags)
    placed, extended, length = author_antenna(tags)
    if verbose:
        for sid, new, hits in bands:
            print("    hold #%d at frame 1 -> #%d (%d placement%s)"
                  % (sid, new, hits, "" if hits == 1 else "s"))
        print("    antenna #%d placed on root %d: folded 1..%d, %s (frame %d) from %d"
              % (ANTENNA, placed, EXTENDED_AT - 1, ANTENNA_LABEL, extended, EXTENDED_AT))

    # whatever else stops itself and no script reaches (faceLines, knob)
    frozen, skipped = stop_clips.freeze(tags, text, stop_clips.dynamic_prefixes(text))
    if verbose:
        for old, new, frames, k in frozen:
            print("    freeze #%d (%df, stop@%d) -> #%d" % (old, frames, k, new))
        for sid, why in skipped:
            print("    keep #%d: %s" % (sid, why))

    out = os.path.join(workdir, os.path.basename(swf).replace(".swf", "_tools.swf"))
    out_xml = out.replace(".swf", ".xml")
    tree.write(out_xml, encoding="UTF-8", xml_declaration=True)
    subprocess.run(FFDEC + ("-xml2swf", out_xml, out), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("swf")
    ap.add_argument("out")
    ap.add_argument("--xml", default=None, help="swf2xml cache to reuse")
    ap.add_argument("--work", default=None)
    args = ap.parse_args()

    work = args.work or os.path.dirname(os.path.abspath(args.out)) or "."
    swf = patched(args.swf, work)
    if os.path.abspath(swf) != os.path.abspath(args.out):
        with open(swf, "rb") as src, open(args.out, "wb") as dst:
            dst.write(src.read())
    print(args.out)


if __name__ == "__main__":
    sys.exit(main())
