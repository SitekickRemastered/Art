#!/usr/bin/env python3
"""Author chip 14's display state into the export: the spider parked at 21.

Chip 14 is the spider chip.  Its root has two labels:

    hover   = 3
    display = 33

and the site loads the effect, then calls `effectHolder.gotoAndPlay("display")`.
Root 33 runs

    spider.gotoAndStop("display");   // sprite 64 frame 21
    gotoAndStop("hover");            // root 3
    play();

so the visible movie is root 3..29 with the spider parked on its own `display`
label (sprite 64 frame 21); root 30's `gotoAndStop("hover"); play()` is what
keeps it there.  Root 1..2 (the loader stop and `spider.gotoAndPlay(2)`) and
root 30..55 are not on that path, and the spider's frames 22..29 are its
`retract` half, ending with the effect removing itself.

FFDec runs no script: it starts the spider at frame 1 and advances it one frame
per root frame, so the exported root 3 shows the curled intro, root 8 the
walk-in and root 29 the retract ball, while the site shows the hanging spider
the whole time.  The only two sound cues are inside the spider at frames 2 and
14; parked at 21 it plays neither, so the export drops both.

The park itself is `cooked_sprite.park()`: the shared stopped-clip freeze first
(sprite 26 -> 65; sprite 64 is named `spider`, so that pass leaves it alone),
then sprite 64 re-emitted as one frame -- the cooked display list of its frame
21, actions and sounds dropped.  Root frames 1..29 are kept and the export loops
3..29.

Usage:  patch_chip14.py <in.swf> <out.swf> [--xml source.xml]
"""

import argparse
import os
import sys

import cooked_sprite
import patch_stopped_clips as stop_clips

# Park the clip on its own label?  Off: the animation is the display state the
# chip should play, and a parked pose is a single still frame.
PARK = False

SPIDER = 64         # sprite 64, placed on the root as `spider`
DISPLAY_AT = 21     # sprite 64's `display` label, where root 33 parks it
HOVER = 3           # root's `hover` label, the first frame of the idle
LAST = 29           # root 30 jumps back to hover, so the export ends here


def patched(swf, workdir, xml=None):
    if not PARK:
        # the clip's own animation is what the chip should show: parking it
        # bakes a single still pose, which reads as no animation at all
        return stop_clips.patched(swf, workdir, verbose=False)
    return cooked_sprite.park(swf, workdir, SPIDER, DISPLAY_AT, xml)


def loop():
    """The idle range to repeat: the `hover` block through root 29."""
    return (HOVER, LAST)


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
