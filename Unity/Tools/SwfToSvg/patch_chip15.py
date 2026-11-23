#!/usr/bin/env python3
"""Author chip 15's display state into the export: the soundwave parked transformed.

Chip 15 is the readings chip: the Sitekick puts on a pair of headphones and the
movie idles while a message is read out.  Its root has three labels:

    display = 3
    hover   = 4
    retract = 29

and the site loads the effect, waits for it to finish loading, then calls
`effectHolder.gotoAndPlay("display")`.  So the visible movie starts on root 3:

    root 2              play(); soundwaveSK.gotoAndPlay(2);
    root 3 (display)    if (soundwaveSK._currentframe == 1)
                            soundwaveSK.gotoAndStop("transformed");
    root 4 (hover)      play();
    root 23             gotoAndStop("hover"); play();

Root 2 is not on that path.  Entered at 3, the clip is still sitting on its own
frame-1 `stop()`, so root 3's test passes and parks it on `transformed` --
sprite 33 frame 17 -- where it stops again.  Root 4..22 is the idle and root 23
loops it; root 1..2 (the loader and the wave's play) and 24..55 (the retract,
which ends with root 40 removing the effect) are never shown.

FFDec runs no script: it starts sprite 33 at frame 1 and advances it one frame
per root frame, so the exported frames grow the headphones in over 1..16 and
then keep going through 17..22, while the site shows them already on.  Both
sounds are unreachable as well: sound 10 is placed inside sprite 33 on its
frame 2, which the park skips, and sound 35 is on root 32, inside the retract.
The export therefore has no cues.

The park itself is `cooked_sprite.park()`: the shared stopped-clip freeze first
(nothing is frozen here: sprites 16 and 33 are placed as `cup` and
`soundwaveSK`, so that pass leaves them alone), then sprite 33 re-emitted as one
frame -- the cooked display list of its frame 17, actions dropped.  Root frames
1..22 are kept and the export loops 4..22.

Usage:  patch_chip15.py <in.swf> <out.swf> [--xml source.xml]
"""

import argparse
import os
import sys

import cooked_sprite
import patch_stopped_clips as stop_clips

# Park the clip on its own label?  Off: the animation is the display state the
# chip should play, and a parked pose is a single still frame.
PARK = False

WAVE = 33           # sprite 33, placed on the root as `soundwaveSK`
TRANSFORMED = 17    # sprite 33's `transformed` label, where root 3 parks it
HOVER = 4           # root's `hover` label, the first frame of the idle
LAST = 22           # root 23 jumps back to hover, so the export ends here


def patched(swf, workdir, xml=None):
    if not PARK:
        # the clip's own animation is what the chip should show: parking it
        # bakes a single still pose, which reads as no animation at all
        return stop_clips.patched(swf, workdir, verbose=False)
    return cooked_sprite.park(swf, workdir, WAVE, TRANSFORMED, xml)


def loop():
    """The idle range to repeat: the `hover` block through root 22."""
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
