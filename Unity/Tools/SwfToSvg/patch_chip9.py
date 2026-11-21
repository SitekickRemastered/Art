#!/usr/bin/env python3
"""Author chip 9's scripted poses into the movie, the way its ActionScript sets them.

Chip 9 is the hole-punch chip.  Almost every clip it shows is moved by a frame
script, never by the timeline, and the whole effect is a small state machine:

    root 2    trim.gotoAndPlay(2)                  trim shadow, stops on 5
    root 8    stop(); side.gotoAndPlay(2)          hole opens (side frame 2..19)
    side 9    effect.gotoAndPlay("hover")          root leaves its stop at 8
    side 12   effect.arm.gotoAndPlay(2)             the arm starts
    arm 10    effect.rightSide.gotoAndPlay(2)      the right side starts
    side 19   stop()                               hole parked open
    root 33   stop(); arm.gotoAndPlay("retract2")  the arm retracts
    arm 59    effect.side.gotoAndPlay("retract")    side 16..19, hole closes
    root 42   arm.gotoAndPlay("prepare")
    root 53   arm.gotoAndPlay("downHole")          arm 78..80, stops on 80
    root 102  arm.gotoAndStop("pointUp")           - already on 80
    root 112  arm.gotoAndPlay("relax")             arm 90..110, stops on 110
    arm 110   effect.side.gotoAndPlay("retract")

The arm, side, rightSide, trim and hole clips all end their first frame in
`stop()`, so on the timeline they hold that frame until one of those calls moves
them.  FFDec runs no script: it advances every clip one frame per root frame,
straight through the stops and loops.  The exported frames therefore show the
arm swinging out at root frames where the real chip has it inside the hole, the
right side playing its whole 44-frame timeline instead of sitting on frame 4,
and the two-frame `hole` clip alternating open/closed on every frame.

This pass bakes in what the scripts do, in the same way as patch_chip7.py and
patch_chip8_tools.py: each scripted clip is re-emitted with one frame per root
frame showing the frame the script would have left it on, and every root
placement of it is pointed at that copy (its ratio dropped, so the copy's first
frame is the one shown at the frame that places it).  Each of those frames is
the clip's own tag stream up to that frame, merged into one frame: the arm
places its hole twice, and a flattened display list keeps only the second
placement, which renders nothing -- the hole vanished for root frames 33-41.

The hole is folded in as well: arm frame 53 calls `hole.gotoAndStop(2)` on the
root frame (33) that also jumps the arm past the hole's first placement, so the
open frame is the only state the authored arm can show; the clip itself is
rewritten to it.

Everything else is left to `patch_stopped_clips.py`, which freezes the stopped
clips no script reaches (the right side's 55-frame shadow, character 29), and is
run over the same tree here first so the copies embed the frozen ids.

Usage:  patch_chip9.py <in.swf> <out.swf> [--xml cache.xml]
"""

import argparse
import copy
import os
import subprocess
import sys

from lxml import etree

import patch_chip7 as patch7
import patch_chip8_tools as tools8
import patch_stopped_clips as stop_clips

SHOW = "ShowFrameTag"
FFDEC = stop_clips.FFDEC

# the root frame whose script first moves each clip, and the pose it sets; the
# numbers below are the frames the scripts name (labels or explicit frames)
HOVER = 18          # side 12 plays the arm from frame 2
RETRACT2 = 33       # root 33: arm 53
PREPARE = 42        # root 42: arm 69
DOWN_HOLE = 53      # root 53: arm 78, then stops on 80
POINT_UP = 102      # root 102: arm pointUp (already showing 80)
RELAX = 112         # root 112: arm 90
STOP_71 = 45        # arm 69,70,71 then its own stop on 71
STOP_80 = 55        # arm 78,79,80 then its own stop on 80
STOP_110 = 132      # arm 90..110 then its own stop on 110
HOLE_OPEN = 33      # arm 53 calls hole.gotoAndStop(2)

TRIM, RIGHT, ARM = 12, 39, 66
SIDE, SIDE2, HOLE = 90, 102, 63

TRIM_ID = 1201
ARM_IDS = (6601, 6602, 6603)
SIDE_ID, SIDE2_ID = 9001, 10201
RIGHT_IDS = (3901, 3902, 3903)


def arm_playhead(n):
    """The arm's own frame on root frame `n`, following the script's jumps."""
    if n < HOVER:                       # parked on 1 by its own stop()
        return 1
    if n < RETRACT2:                    # side 12 played it from 2
        return 2 + (n - HOVER)
    if n < PREPARE:                     # root 33 -> retract2 (53)
        return 53 + (n - RETRACT2)
    if n < STOP_71:                     # root 42 -> prepare (69)
        return 69 + (n - PREPARE)
    if n < DOWN_HOLE:                   # 69, 70, 71 and its stop on 71
        return 71
    if n < STOP_80:                     # root 53 -> downHole (78)
        return 78 + (n - DOWN_HOLE)
    if n < RELAX:                       # 78, 79, 80 and its stop on 80
        return 80
    if n < STOP_110:                    # root 112 -> relax (90)
        return 90 + (n - RELAX)
    return 110                          # 90..110 and its stop on 110


def side_playhead(n):
    """The hole side's own frame on root frame `n`."""
    if n < 8:                           # parked on 1 by its own stop()
        return 1
    if n < 25:                          # root 8 -> gotoAndPlay(2)
        return 2 + (n - 8)
    if n < 39:                          # 2..19, then parked open
        return 19
    if n < 42:                          # arm 59 -> retract (16), hole closes
        return 16 + (n - 39)
    return 19


def right_playhead(n):
    """The right side's own frame on root frame `n` (it stops on 4 by itself)."""
    if n < 26:                          # parked on 1
        return 1
    if n < 28:                          # arm 10 -> gotoAndPlay(2)
        return 2 + (n - 26)
    return 4


def trim_playhead(n):
    """The trim's own frame: root 2 plays it from 2, it stops on 5."""
    return min(n, 5)


def places(tags, char):
    """Every root placement of one character, with the root frame it is on."""
    out, frame = [], 1
    for tag in tags:
        if tag.get("type") == SHOW:
            frame += 1
            continue
        if (tag.get("type", "").startswith("PlaceObject")
                and tag.get("characterId") == str(char)):
            out.append((frame, tag))
    return out


def retarget(tag, new_id):
    """Point a placement at another character, starting it at its frame 1.

    The originals carry a ratio that makes the clip's own frame equal the root
    frame; the authored copy already has one frame per root frame, so the ratio
    would skip into it.  Dropping it is what patch_stopped_clips.repoint does
    for the same reason.
    """
    tag.set("characterId", str(new_id))
    if tag.get("placeFlagHasRatio") == "true":
        tag.set("placeFlagHasRatio", "false")
    tag.attrib.pop("ratio", None)


def merged(tags, sid, ph):
    """One frame holding the clip's tags up to `ph`, in order, without actions.

    A sprite's timeline is incremental: frame `ph` only carries what changed,
    and the timeline as a whole builds the display list.  Replaying tags 1..ph
    without the ShowFrames between them is exactly what the clip shows on
    `ph` -- and, unlike a flattened display list, it keeps the tags FFDec keys
    on, such as the arm placing its hole twice (the second placement is the one
    that shows, and dropping it lost the hole entirely).
    """
    frames = tools8.without_actions(tools8.raw_frames(tools8.sprite(sid, tags)))
    out = []
    for frame in frames[:ph]:
        out.extend(copy.deepcopy(frame))
    return out


def author(tags, char, ids, playhead, last_frame):
    """One copy per placement: a frame per root frame, at `playhead(root)`."""
    hits = places(tags, char)
    assert hits, "root never places %d" % char
    assert len(hits) == len(ids), "expected %d placements of %d, got %d" % (
        len(ids), char, len(hits))
    for (start, tag), new_id in zip(hits, ids):
        frames = []
        for n in range(start, last_frame + 1):
            frames.append(merged(tags, char, playhead(n)))
        tools8.define(tags, new_id, frames)
        retarget(tag, new_id)
    return hits


def author_hole(tags):
    """The hole is open for the whole time the arm shows it.

    Its frame 1 stops; arm frame 53 calls hole.gotoAndStop(2), which opens it.
    FFDec alternates the two frames on every root frame.  The arm only ever
    shows the hole from frame 41 -- which the script has already left behind by
    the time the arm is driven (it jumps to 53 on root 33) -- so the open frame
    is the only state the authored arm can show: rewrite the clip itself, which
    leaves every placement pointing at the same character.
    """
    frames = tools8.without_actions(tools8.frames_of(tools8.sprite(HOLE, tags)))
    assert len(frames) == 2, len(frames)
    opened = merged(tags, HOLE, 2)
    item = tools8.sprite(HOLE, tags)
    sub = item.find("subTags")
    for child in list(sub):
        sub.remove(child)
    for tag in opened:
        sub.append(tag)
    sub.append(etree.Element("item", type=SHOW, forceWriteAsLong="false"))
    item.set("frameCount", "1")


def author_trim(tags):
    """Root 2 plays the trim from 2; it stops on 5 and holds that pose."""
    frames = [merged(tags, TRIM, n) for n in range(1, 6)]
    tools8.define(tags, TRIM_ID, frames)
    for _, tag in places(tags, TRIM):
        retarget(tag, TRIM_ID)


def author_side2(tags):
    """The noHole side is placed on root 112 and stops on its (empty) frame 1."""
    tools8.define(tags, SIDE2_ID, [merged(tags, SIDE2, 1)])
    for _, tag in places(tags, SIDE2):
        retarget(tag, SIDE2_ID)


def patched(swf, workdir, verbose=True):
    """The SWF to render frames from: this chip's, with its scripted poses in."""
    src_xml, scripts = stop_clips.ensure(swf, workdir)
    text = stop_clips.script_text(scripts)
    tree = etree.parse(src_xml)
    tags = tree.getroot().find("tags")
    last_frame = patch7.root_frames(tags)

    # guard: this authoring only makes sense for this movie
    def action(frame):
        return "".join(patch7.ascii_in(a) for a in patch7.actions_on(tags, frame))

    assert last_frame == 152, last_frame
    assert "side" in action(8) and "gotoAndPlay" in action(8), "frame 8 is not the side start"
    assert "retract2" in action(33) and "arm" in action(33), "frame 33 is not retract2"
    assert "prepare" in action(42), "frame 42 is not prepare"
    assert "downHole" in action(53), "frame 53 is not downHole"
    assert "relax" in action(112), "frame 112 is not relax"

    # the shadow inside the right side stops itself and no script moves it
    frozen, skipped = stop_clips.freeze(tags, text, stop_clips.dynamic_prefixes(text))
    if verbose:
        for old, new, frames, k in frozen:
            print("    freeze #%d (%df, stop@%d) -> #%d" % (old, frames, k, new))
        for sid, why in skipped:
            print("    keep #%d: %s" % (sid, why))

    author_hole(tags)
    author_trim(tags)
    author_side2(tags)
    hero = author(tags, ARM, ARM_IDS, arm_playhead, last_frame)
    side = author(tags, SIDE, (SIDE_ID,), side_playhead, last_frame)
    right = author(tags, RIGHT, RIGHT_IDS, right_playhead, last_frame)
    if verbose:
        print("    arm #%d: %d placement%s, one frame per root frame, hole open"
              % (ARM, len(hero), "" if len(hero) == 1 else "s"))
        print("    side #%d: %d placement, retract on root 39" % (SIDE, len(side)))
        print("    rightSide #%d: %d placements, parked on 4 from root 28"
              % (RIGHT, len(right)))
        print("    trim #%d: 5 frames; hole #%d held open; noHole side #%d"
              % (TRIM_ID, HOLE, SIDE2_ID))

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
