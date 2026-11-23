#!/usr/bin/env python3
"""Find the root's idle loop: the backward jump that keeps a chip hovering.

The chip movies are stage movies with three sections: an intro, an idle section
the root loops, and a retract half.  The idle section is a labelled block --
`hover` on chips 8-11 and 14-16, `float` on chip 7 -- that a root frame script
jumps back to with `gotoAndPlay(label)`, so in Flash the movie plays the intro
once and then loops that block for as long as the chip is on the Sitekick.  Chip
12 has no such label: it waits on its closed frame until the nose is clicked
(`nose.onRelease` -> `gotoAndStop("open"); play()`) and root 25 resets it with a
literal `gotoAndStop(1)`, so its idle is the 24-frame click cycle.  The
frames after the jump (chip 10's antenna going down, chip 11's monster walking
back, chip 9's whole arm pull-out) are only reached when something outside the
movie sends it to `retract`, which the site did when the visitor left the effect.

Nothing in the game does that: `ChipGallery` keeps an effect until its chip is
clicked again, so the retract half is never shown.  A linear export that runs the
whole root timeline plays it anyway, once, at the end of the hover pass.

This module reads the jump off the root timeline.  A chip with a loop is exported
only up to the frame before the jump, and `movie.json` carries the loop range for
`ChipMoviePlayer` to repeat instead of finishing.

Usage:  hover_loop.py <source.xml> [<source.xml> ...]
"""

import glob
import os
import re
import sys

from lxml import etree

import patch_chip7 as patch7

GOTO_LABEL = "\x8c"     # ActionGotoLabel, followed by a length-prefixed name


def frame_labels(tags):
    """frame label -> frame number, for the root timeline."""
    out, n = {}, 0
    for tag in tags:
        if tag.get("type") == "ShowFrameTag":
            n += 1
        elif tag.get("type") == "FrameLabelTag":
            out[tag.get("name")] = n + 1
    return out


def label_jumps(text):
    """Every label an action block jumps to, in order."""
    out, i = [], text.find(GOTO_LABEL)
    while i >= 0:
        length = ord(text[i + 1]) + 256 * ord(text[i + 2])
        out.append(text[i + 3:i + 3 + length].split("\x00")[0])
        i = text.find(GOTO_LABEL, i + 1)
    return out


def literal_jumps(script_dir, total):
    """(frame, target) for root frame scripts that jump to a frame number.

    Only an unwrapped `gotoAndStop(1)` counts: `fixit.bottom.gotoAndStop(2)` on
    chip 8's root 40 moves a clip, not the root, and the dot tells them apart.
    """
    jumps = []
    for path in glob.glob(os.path.join(script_dir, "frame_*", "DoAction*.as")):
        found = re.search(r"frame_(\d+)", os.path.dirname(path))
        if not found:
            continue
        frame = int(found.group(1))
        text = open(path, encoding="latin1", errors="ignore").read()
        for hit in re.finditer(r"(?<![\w.])gotoAnd(?:Play|Stop)\s*\(\s*(\d+)\s*\)", text):
            target = int(hit.group(1))
            if 1 <= target < frame <= total:
                jumps.append((frame, target))
    return jumps


def find(tags, script_dir=None):
    """(first, last) of the idle loop, or None when the root has none.

    The first backward jump closes the display section: from that frame on the
    root only replays the block, so every frame after it belongs to the retract.
    Later backward jumps (chip 8 at 40, chip 14 at 33) sit in the retract path
    and are never reached while the movie idles, so only the first one sets the
    end.  `script_dir` adds jumps to a literal frame number, which is how chip
    12 resets without a label.
    """
    total = patch7.root_frames(tags)
    labels = frame_labels(tags)
    jumps = []
    for frame in range(1, total + 1):
        for action in patch7.actions_on(tags, frame):
            for name in label_jumps(patch7.ascii_in(action)):
                target = labels.get(name)
                if target is not None and target < frame:
                    jumps.append((frame, target))
    if script_dir:
        jumps += literal_jumps(script_dir, total)
    if not jumps:
        return None
    frame, target = min(jumps)
    return target, frame - 1


def main():
    for path in sys.argv[1:]:
        tags = etree.parse(path).getroot().find("tags")
        loop = find(tags)
        print("%s: %d frames, %s" % (
            os.path.basename(os.path.dirname(os.path.dirname(path))) or path,
            patch7.root_frames(tags),
            "idle %d..%d, export %d frames" % (loop[0], loop[1], loop[1])
            if loop else "no idle loop"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
