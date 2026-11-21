#!/usr/bin/env python3
"""Author chip 10's scripted poses into the movie, the way its ActionScript sets them.

Chip 10 is the squinting bubble: a face in a glass ball that pops in, squints at
the camera and pops out again.  Two clips carry the state, and both are parked
by their own `stop()` until a frame script moves one of them:

    sprite 20 frame 1   stop()                  parked until root 9
    root 9              effectSK.gotoAndStop("squint")   -> sprite 20 frame 25
    sprite 20 frame 5   stop() (label "ready")  never reached while parked
    sprite 20 frame 17  effect.gotoAndPlay("retract")   never reached either
    sprite 5  frame 1   stop()                  the face lines, parked on "out"

`effectSK` is placed three times -- once at depth 1 on root 1, and twice more at
depths 22 and 43 on root 9 with ratio 8 -- all of them the same character, and
none of them moved again after the root 9 jump.  The two clones are what makes
the ball look like glass: three copies of the same drawing are stacked so the
face sits between the front and back shells, so a squint is a squint of all
three.

FFDec runs no script.  It starts the clip at frame 1 and advances it one frame
per root frame straight through its `stop()`s, so the exported movie shows the
bubble with its eyes open all the way through -- the pose at root 9 is the
clip's ninth frame, not the squint the script selects -- and carries on into the
retract animation the movie never plays.  `sprite 5`s face lines advance the
same way, from "out" into "over".

This pass bakes in what the script does, in the same way as `patch_chip7.py`,
`patch_chip8_tools.py` and `patch_chip9.py`: each placement of the effect gets a
copy with one frame per root frame showing the frame the script would have left
it on (frame 1 up to root 8, the squint from root 9), its ratio dropped so the
copy's first frame is the one shown on the frame that places it.  Frames are the
clip's own tag stream merged up to that frame, not a flattened display list, for
the reason spelled out in `patch_chip9.py`.

The face lines need no authoring of their own: `patch_stopped_clips.py`, run over
the same tree first, freezes sprite 5 to the single frame its `stop()` parks it on
(it skips the effect clip, which is the one clip here that a script moves).
Because that pass runs first, the copies built below already point at the frozen
ids.

Usage:  patch_chip10.py <in.swf> <out.swf> [--xml cache.xml]
"""

import argparse
import os
import subprocess
import sys

from lxml import etree

import patch_chip7 as patch7
import patch_chip8_tools as tools8
import patch_chip9 as patch9
import patch_stopped_clips as stop_clips

FFDEC = stop_clips.FFDEC

SQUINT_AT = 9       # root 9: effectSK.gotoAndStop("squint")
SQUINT = 25         # sprite 20's "squint" label
EFFECT = 20
EFFECT_IDS = (2001, 2002, 2003)   # depth 1 on root 1, depths 22 and 43 on root 9
ROOT_FRAMES = 59


def playhead(n):
    """The effect's own frame on root frame `n`: parked, then the squint."""
    return SQUINT if n >= SQUINT_AT else 1


def changed_since(before, after):
    """Only the tags `after` adds to a display list `before` already builds.

    A sprite timeline is incremental.  The squint pose is the parked pose plus
    whatever the clip adds by its 25th frame, so the copy's switch frame has to
    carry only that addition: repeating the parked placements would re-place
    every child and restart its own timeline, which is what left the antenna
    without its knob and sliding out of the ball.
    """
    seen = {str(tag.get("characterId")) for tag in before
            if tag.get("type", "").startswith("PlaceObject") and tag.get("characterId")}
    return [tag for tag in after
            if not (tag.get("type", "").startswith("PlaceObject")
                    and tag.get("characterId") in seen)]


def author_effect(tags, last_frame):
    """One copy per placement: a timeline holding the pose the script leaves.

    Each copy starts on the frame that places it, carries the pose in that
    frame, and adds the next pose on the root frame the script jumps to.  Every
    other frame is empty, which on an incremental timeline means \"the display
    list above still stands\" -- so the clips inside keep advancing exactly as
    they do in the movie instead of being reset by a repeated placement.
    """
    hits = patch9.places(tags, EFFECT)
    assert hits, "root never places the effect"
    assert len(hits) == len(EFFECT_IDS), "expected %d placements of #%d, got %d" % (
        len(EFFECT_IDS), EFFECT, len(hits))
    bodies = {1: patch9.merged(tags, EFFECT, 1),
              SQUINT: patch9.merged(tags, EFFECT, SQUINT)}
    for (start, tag), new_id in zip(hits, EFFECT_IDS):
        frames, pose = [], None
        for n in range(start, last_frame + 1):
            want = playhead(n)
            if want == pose:
                frames.append([])
                continue
            body = bodies[want]
            if pose is not None:
                body = changed_since(bodies[pose], body)
            frames.append(body)
            pose = want
        tools8.define(tags, new_id, frames)
        patch9.retarget(tag, new_id)
    return hits


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

    assert last_frame == ROOT_FRAMES, last_frame
    assert "squint" in action(SQUINT_AT) and "gotoAndStop" in action(SQUINT_AT), \
        "root 9 is not the squint jump"

    # clips that stop themselves and no script restarts
    frozen, skipped = stop_clips.freeze(tags, text, stop_clips.dynamic_prefixes(text))
    if verbose:
        for old, new, frames, k in frozen:
            print("    freeze #%d (%df, stop@%d) -> #%d" % (old, frames, k, new))
        for sid, why in skipped:
            print("    keep #%d: %s" % (sid, why))

    hero = author_effect(tags, last_frame)
    if verbose:
        print("    effect #%d: %d placements, parked on 1 to root %d, squint (%d) from %d"
              % (EFFECT, len(hero), SQUINT_AT - 1, SQUINT, SQUINT_AT))

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
