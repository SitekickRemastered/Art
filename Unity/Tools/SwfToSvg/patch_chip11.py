#!/usr/bin/env python3
"""Author chip 11's scripted pose into the movie, the way its ActionScript sets it.

Chip 11 is the "too cute" monster: a plain white chip sits in the middle of the
stage, flips onto its edge, and turns into a purple hairy version of itself with
the word "too" on it and little legs.  One clip carries all of that state:

    sprite 59 frame 1   stop()                          parked until root 14
    root 14             bottom.monster.gotoAndPlay(2)   -> sprite 59 plays from 2
    sprite 59 frame 16  sfx.gotoAndPlay("antennaUp")    sound only
    sprite 59 frame 22  stop() (label "display")        the monster rests here
    sprite 59 frame 29  play() (label "retract")        only entered by a jump
    sprite 59 frame 39  _parent._parent.gotoAndPlay("retract")  -> root 39

`monster` is sprite 59, placed once -- depth 1 of sprite 60 (`bottom`), which is
the chip itself: a one-frame container at root depth 12 that the root only ever
moves.  So the monster advances one frame per root frame, exactly like the root,
but it spends the first thirteen of them parked on its first frame: the chip sits
there until the root reaches 14 and sends it into the transformation.  It runs
2..22 over root 14..34 and then stays on 22, which is where its own `stop()` on
the `display` label leaves it for the rest of the movie.  Frames 23..50 (the
`retract` half, and the root jump its 39th frame asks for) are never reached
unless something outside the chip retracts it, and root 36 sends the root back to
its `hover` label anyway, so the chip never plays them.

FFDec runs no script.  It starts the clip at its frame 1 and advances it one
frame per root frame straight through both `stop()`s, so the exported movie
turns into the monster immediately -- frame 6 already has the purple hair on
it -- runs a full transformation ahead of the script for the whole movie (root
14 shows the monster's 14th frame where the chip shows its 2nd) and carries on
into the retract art on roots 23..50, which the chip never plays.

This pass bakes in what the script does, the same way `patch_chip7.py`,
`patch_chip8_tools.py`, `patch_chip9.py` and `patch_chip10.py` do: sprite 59 is
re-emitted as one frame per root frame -- the parked pose up to root 13, its own
frames 2..22 over roots 14..34, and then nothing, which on an incremental
timeline means the display list still stands, so it holds the `display` pose to
the end.  Only the parked frames and the hold are empty; the transformation is
the clip's own tag stream in its own order, so the clips it places keep their
timelines and the antenna keeps its own moving parts.

The monster is a named clip that a script moves, so `patch_stopped_clips.py`
leaves it alone (`keep #59: ...`); what it does freeze is the small clips inside
it that stop themselves and no script names, its fringe included.  Because that
pass runs first, the frames copied below already point at the frozen ids.

Its hair is the fringe, sprite 36: five frames of moves that end on the spiky
outline, with `stop()` on that fifth frame.  A stop on a clip's last frame still
loops under FFDec, so the fringe used to cycle 1..5 the whole movie and the
monster read as a smooth cap instead of a hairy one from root 30 on.  The shared
pass now freezes that case too (merging the frames into one pose), which is the
difference between mean 1.99 and 0.21 on root 32; this chip needs no extra work
for it.

Usage:  patch_chip11.py <in.swf> <out.swf> [--xml cache.xml]
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

FFDEC = stop_clips.FFDEC
SHOW = "ShowFrameTag"

MONSTER = 59        # sprite 59, placed as `monster` inside `bottom`
BOTTOM = 60         # sprite 60, the chip container at root depth 12
PLAY_AT = 14        # root 14: bottom.monster.gotoAndPlay(2)
PLAY_FROM = 2
HOLD_AT = 22        # sprite 59's own stop() on the "display" label
ROOT_FRAMES = 53


def rewrite(tags, sid, frames):
    """Replace a sprite's timeline in place, dropping the actions FFDec can't run.

    The definition keeps its id and its position in the tag stream: the
    placement that points at it lives in another sprite, and re-defining the id
    elsewhere would only move the character tag around it.
    """
    item = tools8.sprite(sid, tags)
    sub = item.find("subTags")
    for child in list(sub):
        sub.remove(child)
    for frame in frames:
        for tag in frame:
            if tag.get("type") == "DoActionTag":
                continue
            sub.append(copy.deepcopy(tag))
        sub.append(etree.Element("item", type=SHOW, forceWriteAsLong="false"))


def author_monster(tags, last_frame):
    """One frame per root frame: parked on 1, its own 2..22, then the hold.

    The parked frames and the tail are left empty rather than repeating the
    pose.  An empty frame adds nothing to the display list, which is what
    parking means; repeating the placements instead would re-place the clips
    inside the monster on every one of them and restart their timelines (the
    mistake that cost chip 10 its antenna).
    """
    frames = tools8.raw_frames(tools8.sprite(MONSTER, tags))
    assert len(frames) > HOLD_AT, len(frames)
    park = [[] for _ in range(PLAY_AT - 2)]
    play = frames[PLAY_FROM - 1:HOLD_AT]
    hold = [[] for _ in range(last_frame - (PLAY_AT - 1) - len(play))]
    assert len(play) == HOLD_AT - PLAY_FROM + 1, len(play)
    out = [frames[0]] + park + play + hold
    assert len(out) == last_frame, (len(out), last_frame)
    rewrite(tags, MONSTER, out)
    return out


def patched(swf, workdir, verbose=True):
    """The SWF to render frames from: this chip's, with its scripted pose in."""
    src_xml, scripts = stop_clips.ensure(swf, workdir)
    text = stop_clips.script_text(scripts)
    tree = etree.parse(src_xml)
    tags = tree.getroot().find("tags")
    last_frame = patch7.root_frames(tags)

    # guard: this authoring only makes sense for this movie
    def action(frame):
        return "".join(patch7.ascii_in(a) for a in patch7.actions_on(tags, frame))

    assert last_frame == ROOT_FRAMES, last_frame
    assert "monster" in action(PLAY_AT) and "gotoAndPlay" in action(PLAY_AT), \
        "root 14 is not the monster jump"
    # gotoAndStop("hover") compiles to ActionGotoLabel (0x8c) naming the label
    assert "hover" in action(36) and "\x8c" in action(36), \
        "root 36 is not the hover loop"
    assert MONSTER in [int(t.get("characterId")) for t in tools8.raw_frames(
        tools8.sprite(BOTTOM, tags))[0] if t.get("characterId")], \
        "the monster is not inside `bottom`"

    # clips that stop themselves and no script restarts
    frozen, skipped = stop_clips.freeze(tags, text, stop_clips.dynamic_prefixes(text))
    if verbose:
        for old, new, frames, k in frozen:
            print("    freeze #%d (%df, stop@%d) -> #%d" % (old, frames, k, new))
        for sid, why in skipped:
            print("    keep #%d: %s" % (sid, why))

    out = author_monster(tags, last_frame)
    if verbose:
        print("    monster #%d: %d frames, parked on 1 for roots 1-%d, its own %d..%d "
              "over roots %d-%d, held on %d after that (root 36 loops to `hover`)"
              % (MONSTER, len(out), PLAY_AT - 1, PLAY_FROM, HOLD_AT, PLAY_AT,
                 PLAY_AT + (HOLD_AT - PLAY_FROM), HOLD_AT))

    out_swf = os.path.join(workdir, os.path.basename(swf).replace(".swf", "_tools.swf"))
    out_xml = out_swf.replace(".swf", ".xml")
    tree.write(out_xml, encoding="UTF-8", xml_declaration=True)
    subprocess.run(FFDEC + ("-xml2swf", out_xml, out_swf), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out_swf


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
