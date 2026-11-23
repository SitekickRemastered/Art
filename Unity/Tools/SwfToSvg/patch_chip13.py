#!/usr/bin/env python3
"""Author chip 13's stopped root into the export, with its fish still swimming.

Chip 13 is the fishing chip: a small white chip drifts in, the Sitekick's face
turns into a green puffer fish, and the fish idles with a small bob while a
button on its body can be poked and a knob on its antenna can be pulled.

The root is a display/retract movie like the others, but its idle is not a
backward jump -- it is a *stop*:

    root 1              stop()                       the loader's parked frame
    root 11 (display)   stop() + button handlers     the idle frame
    root 14 (revert)    ...                          reached by the knob only
    root 26             sk.gotoAndPlay("fromEffect");
                        effectHolder.removeMovieClip()

The site loads the effect offscreen, then calls `effectHolder.gotoAndPlay(
"display")`, so the visible movie starts on root 11 and stops there.  The knob's
`onRelease` is what sends the root to `revert`, and the game removes the effect
at 26; `ChipGallery` has no knob, so like the hover tail on chips 7-12 that
retract section is never reached.

Stopping the root is not stopping the movie.  The fish is sprite 52, placed on
root 9, a 20-frame tween of its body (sprite 51); it has no stop, so Flash keeps
advancing it while the root sits on 11.  That is the idle: the fish swims its
20-frame cycle under a root that is frozen.  Two clips are interactive and stop
themselves on frame 1: the body (51, named `body`) is played by the body button
(31, named `btn`) on a click, and the button stops itself again when its poke
animation ends.  No script moves either timeline outside that click, so their
idle pose is frame 1.

FFDec runs no script: it exports root 12..79 linearly, so after 11 the movie
plays the knob's `revert` (14..26, with root 26's removal ignored) and then 52
frames of nothing.  It also advances the body and button through their poke
animations.  In Unity the stop is a `pauses` entry, so the player held the fish
for 0.75 s and then played the retract into an empty stage.

This pass bakes the idle state in: the body and button are re-emitted as their
frame-1 art, the root is cut at 11, its stop action is dropped, and 20 empty
frames are appended.  Those frames hold root 11's display list while sprite 52
advances one frame per root frame, which is precisely what Flash does.  The
20 appended frames are one fish cycle (52 is placed on root 9, so root 12 is its
frame 4), and `export_chip_movies.py` sets `loop` to 12..31; the 1..11 intro
plays once and the fish repeats.

Usage:  patch_chip13.py <in.swf> <out.swf> [--xml source.xml]
"""

import argparse
import copy
import os
import subprocess
import sys

from lxml import etree

import patch_stopped_clips as stop_clips

FFDEC = stop_clips.FFDEC
SHOW = "ShowFrameTag"

HOLD_AT = 11        # root 11: `display`, where the root stops and the fish idles
LOOP_FRAMES = 20    # sprite 52's tween cycle; root 12 is its frame 4
BODY = 51           # fish body, stop() on frame 1, played only by the button
BUTTON = 31         # poke button, stop() on frame 1


def freeze_first_frame(tags, sid):
    """Keep only a clip's frame-1 art, dropping its stop and later frames."""
    item = next(t for t in tags
                if t.get("type") == "DefineSpriteTag" and t.get("spriteId") == str(sid))
    frames = stop_clips.frames_of(item)
    sub = item.find("subTags")
    for child in list(sub):
        sub.remove(child)
    for tag in frames[0]:
        if tag.get("type") != "DoActionTag":
            sub.append(copy.deepcopy(tag))
    sub.append(etree.Element("item", type=SHOW, forceWriteAsLong="false"))


def held_tags(tags):
    """Root tags cut at HOLD_AT, its stop dropped, plus LOOP_FRAMES held frames."""
    segments, current = [], []
    for tag in tags:
        if tag.get("type") == SHOW:
            segments.append(current)
            current = []
            if len(segments) == HOLD_AT:
                break
        else:
            current.append(tag)
    if len(segments) != HOLD_AT:
        raise SystemExit("root has %d frames, want at least %d" % (len(segments), HOLD_AT))

    # the idle frame's stop is the state being authored; leaving it in would
    # also make pause_frames() stop the export there instead of looping
    segments[-1] = [t for t in segments[-1] if t.get("type") != "DoActionTag"]

    out = []
    for segment in segments:
        out.extend(segment)
        out.append(etree.Element("item", type=SHOW, forceWriteAsLong="false"))
    for _ in range(LOOP_FRAMES):
        out.append(etree.Element("item", type=SHOW, forceWriteAsLong="false"))
    return out


def patched(swf, workdir, xml=None):
    src_xml = xml or stop_clips.ensure(swf, workdir)[0]
    tree = etree.parse(src_xml)
    root = tree.getroot()
    tags = root.find("tags")

    freeze_first_frame(tags, BODY)
    freeze_first_frame(tags, BUTTON)

    out = held_tags(tags)
    for tag in list(tags):
        tags.remove(tag)
    for tag in out:
        tags.append(tag)
    root.set("frameCount", str(HOLD_AT + LOOP_FRAMES))

    os.makedirs(workdir, exist_ok=True)
    out_xml = os.path.join(workdir, "chip_0013_held.xml")
    out_swf = os.path.join(workdir, "chip_0013_held.swf")
    tree.write(out_xml, encoding="UTF-8", xml_declaration=True)
    subprocess.run(FFDEC + ("-xml2swf", out_xml, out_swf), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out_swf


def loop():
    """The idle range to repeat: the appended fish cycle."""
    return (HOLD_AT + 1, HOLD_AT + LOOP_FRAMES)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("swf")
    ap.add_argument("out")
    ap.add_argument("--xml", default=None)
    ap.add_argument("--work", default=None)
    args = ap.parse_args()
    work = args.work or os.path.dirname(os.path.abspath(args.out))
    out = patched(args.swf, work, args.xml)
    if os.path.abspath(out) != os.path.abspath(args.out):
        os.replace(out, args.out)
    print(args.out)


if __name__ == "__main__":
    sys.exit(main())
