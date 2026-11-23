#!/usr/bin/env python3
"""Chip 16's pass: play the whole root, so the export ends on the finished hat.

Chip 16 is the snowman chip.  Its root has one label:

    hover = 3

and its whole visible movie is one clip, `body` (sprite 64, 101 frames):

    root 1              stop(); _global.effect = this;
    root 2              body.gotoAndPlay(2);
    root 3 (hover)      ...
    root 21             gotoAndStop("hover"); play();

    body 1              stop();
                        if (effect.display == "true") gotoAndStop("display");
    body 39 (display)   ...   the finished snowman: head, face, stick arms, hat
    body 40 (still)     stop(); hat.gotoAndPlay(2); nose.onRelease = ... "wave"
    body 44 (wave)      the nose-click reaction, ending on body 72, which
                        removes the effect from effectHolder

The site loads the chip as `effect.swf?...&display=true` and then calls
`effectHolder.gotoAndPlay("display")` (sitekick.swf, `funcLoadDisplay`).  Chip
16's root has no `display` label, so that call does nothing and the root stays
on frame 1 -- frame 2's `body.gotoAndPlay(2)` never runs.  The `display=true`
query variable does land on the loaded movie, so `body` frame 1's test passes
and the clip parks on its own `display` label, frame 39.  Measured live against
the shipping `SWF/chip_0016.swf` with a dock shim that reproduces that load
(`Logs/chip_0016_live.txt`): 34 samples over 8.5 s read `root=1/39` and
`body=39/101` every time.

FFDec runs no script, so it starts `body` at frame 1 and advances it one frame
per root frame.  That lockstep walk is how the display pose is built by hand:
one ball first, then head, body, face and both stick arms, and the hat -- sprite
40, a five-frame clip placed on `body` 36 -- growing in over the last frames.
`body` reaches `display` (39) on root 39, which is the pose Flash parks on, so
there is nothing to author here: this pass only runs the stopped-clip freeze
(`patch_stopped_clips.patched`) and the export plays the whole root.

The 3..20 hover loop that `hover_loop.py` finds at root 21 is real, but it is
the host's other path (`effectHolder.play()`, used when the effect returns from
a game), and it starts long before the hat is placed, so cutting to it exports a
snowman that never gets its hat.  Chip 16 therefore takes no cut and no loop
(`loop = None` in `export_chip_movies.py`): frames 1..39 are played once and the
player holds the last one, the finished snowman.  The nose-click `wave` (body
44, with the 47 and 60 sound cues) stays out of the export for the same reason,
as do its mp3s: the gallery cannot click an SVG nose.

Usage:  patch_chip16.py <in.swf> <out.swf> [--work dir]
"""

import argparse
import os
import sys

import patch_stopped_clips as stop_clips


def patched(swf, workdir):
    """The SWF to render frames from: only the stopped clips frozen.

    Nothing is baked: the whole root timeline is the export, which is why
    `export_chip_movies.py` gives chip 16 `loop = None`.
    """
    return stop_clips.patched(swf, workdir, verbose=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("swf")
    ap.add_argument("out")
    ap.add_argument("--work", default=None)
    args = ap.parse_args()
    work = args.work or os.path.dirname(os.path.abspath(args.out))
    out = patched(args.swf, work)
    if os.path.abspath(out) != os.path.abspath(args.out):
        os.replace(out, args.out)
    print(args.out)


if __name__ == "__main__":
    sys.exit(main())
