#!/usr/bin/env python3
"""Prove chip 8's arm timing from the SWF, not from how a frame happens to look.

Ruffle renders the *state a clip is in*, so a pixel diff between a frame and a
render can only ever say "these two pictures agree".  That is not the same as
"the export shows the arm state the script puts there on this frame", and the
frozen-frame harness in `ruffle_frames.py` cannot tell them apart: it freezes
every clip at the root frame (FFDec's lockstep advance) and drops the root's
frame actions, so for a SWF whose arm state is not baked in it reproduces the
export's own assumption by construction.  Measured on frames 45-61, the arms
region reads 5.48/255 against the current export and 5.04/255 against HEAD's
lockstep export -- indistinguishable, while a repeat capture of the same page
differs by 0.00.

What can decide it is the data the exporter itself obeys:

  1. the root's frame actions, read out of the pristine SWF's action bytes
     (frame 40 names "hover", frame 53 names "retract");
  2. the labels those names resolve to (tools: hover 16, retract 46;
     tools2: hover 13, retract 40);
  3. the arm sprites the export actually draws (7301, 8201): each of the 71
     root frames must carry exactly the source clip frame that (1)+(2) select
     for it -- tag for tag, matrices included, with only the hand/toolset
     re-pointing this patch does allowed to differ.

If (3) holds for every root frame, then `frame_NNN.svg` shows the arm state the
script asks for on frame NNN, and the retract edge sits on root frame 53
because that is where the action that names "retract" runs -- not because two
pictures looked alike.

Usage:  verify_arm_timing.py [--src lib.src.xml] [--patched chip_0008_tools.xml]
"""

import argparse
import os
import sys

from lxml import etree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import patch_chip8_tools as P            # noqa: E402  (same directory)

TOOLS, TOOLS2 = 73, 82                   # the two arm clips
SHIPPED = {TOOLS: 7301, TOOLS2: 8201}    # their authored replacements

# the identities the patch re-points: hands to their per-hand copies, tool 5
# and the antenna to single-frame/held copies.  Anything else must match.
REMAP = {}
for _k in P.TOOLS:
    REMAP[(P.HANDS[_k], P.HAND_IDS[_k])] = True
REMAP[(44, 4401)] = True                 # tool 5, single-frame copy
REMAP[(71, 7101)] = True                 # antenna, held extended


def tags_of(path):
    return etree.parse(path).getroot().find("tags")


def actions_on_frame(tags, frame):
    """The DoAction tags that run on root frame `frame` (1-based)."""
    seen, out = 0, []
    for sub in tags:
        if sub.get("type") == "ShowFrameTag":
            seen += 1
            continue
        if sub.get("type") == "DoActionTag" and seen + 1 == frame:
            out.append(sub.get("actionBytes") or "")
    return out


def strings_in(hex_bytes):
    """Printable ASCII runs in an ActionScript byte string."""
    raw = bytes(int(hex_bytes[i:i + 2], 16) for i in range(0, len(hex_bytes), 2))
    runs, cur = [], b""
    for b in raw:
        if 32 <= b < 127:
            cur += bytes([b])
        else:
            if len(cur) >= 3:
                runs.append(cur.decode())
            cur = b""
    if len(cur) >= 3:
        runs.append(cur.decode())
    return runs


def items(tag, ratio=True):
    """A tag's canonical text with the character identity factored out.

    The patch re-points hands at per-hand copies, so the identity is compared
    separately (against REMAP) and everything else must be identical.  A
    re-pointed placement also loses its `ratio` (the patch seats the copy
    itself), so that attribute is dropped from those comparisons too.
    """
    item = etree.fromstring(etree.tostring(tag))
    item.attrib.pop("characterId", None)
    if not ratio:
        item.attrib.pop("ratio", None)
        item.attrib.pop("placeFlagHasRatio", None)
    return etree.tostring(item, method="c14n")


def same_frame(want, got):
    """Do two frame tag lists draw the same thing?

    Returns (True, remapped) when they are identical apart from the hand /
    toolset / antenna re-pointing, (False, detail) otherwise.
    """
    if len(want) != len(got):
        return False, "%d tags vs %d" % (len(want), len(got))
    remapped = set()
    for a, b in zip(want, got):
        ca, cb = a.get("characterId"), b.get("characterId")
        ratio = True
        if ca != cb:
            if (int(ca), int(cb)) not in REMAP:
                return False, "character %s -> %s" % (ca, cb)
            remapped.add((ca, cb))
            ratio = False
        if items(a, ratio) != items(b, ratio):
            return False, "tag content differs at depth %s" % a.get("depth")
    return True, remapped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..",
        "Temp", "swftosvg", "0008", "xml", "lib.src.xml"),
        help="the pristine decompile the retainers are read from")
    ap.add_argument("--patched", default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..",
        "Temp", "swftosvg", "0008", "chip_0008_tools.xml"),
        help="the patched XML the export was made from")
    args = ap.parse_args()

    src, pat = tags_of(args.src), tags_of(args.patched)
    failures = 0

    print("1. root frame actions")
    for frame, expect in ((14, "gotoAndPlay"), (40, "hover"), (53, "retract")):
        found = [s for a in actions_on_frame(src, frame) for s in strings_in(a)]
        ok = expect in found
        failures += not ok
        print("   frame %2d: %s %s" % (frame, "names" if ok else "MISSING",
                                      ", ".join(sorted(set(found))[:8])))

    print("2. the labels those names resolve to")
    hover = (P.labels(P.sprite(TOOLS, src))["hover"], P.labels(P.sprite(TOOLS2, src))["hover"])
    retract = (P.labels(P.sprite(TOOLS, src))["retract"],
               P.labels(P.sprite(TOOLS2, src))["retract"])
    print("   tools %d: hover %d, retract %d | tools2 %d: hover %d, retract %d"
          % (TOOLS, hover[0], retract[0], TOOLS2, hover[1], retract[1]))

    root_frames = sum(1 for s in src if s.get("type") == "ShowFrameTag")
    playheads = P.arm_playheads(root_frames, hover, retract)

    print("3. the sprites the export draws, per root frame")
    all_remap = set()
    for clip, playhead_list in ((TOOLS, playheads[0]), (TOOLS2, playheads[1])):
        raw = P.without_actions(P.raw_frames(P.sprite(clip, src)))
        shipped = P.frames_of(P.sprite(SHIPPED[clip], pat))
        if len(shipped) != root_frames:
            print("   sprite %d has %d frames, root has %d"
                  % (SHIPPED[clip], len(shipped), root_frames))
            failures += 1
        for i, ph in enumerate(playhead_list):
            root = i + 1
            if ph is None:
                if shipped[i]:
                    failures += 1
                    print("   sprite %d root %2d: should be empty" % (SHIPPED[clip], root))
                continue
            want = P.flattened(src, clip, ph) if (clip == TOOLS2 and i == 39) else raw[ph - 1]
            ok, detail = same_frame(want, shipped[i])
            if not ok:
                failures += 1
                print("   sprite %d root %2d: %s (wanted clip frame %d)"
                      % (SHIPPED[clip], root, detail, ph))
            else:
                all_remap |= detail
    print("   frames checked: %d per clip, hand re-pointing: %s"
          % (root_frames, ", ".join("%s->%s" % r for r in sorted(all_remap)) or "none"))

    print("4. the timing edge")
    print("   root 40 -> tools clip frame %d, tools2 %d   (hover)"
          % (playheads[0][39], playheads[1][39]))
    print("   root 52 -> tools clip frame %d, tools2 %d"
          % (playheads[0][51], playheads[1][51]))
    print("   root 53 -> tools clip frame %d, tools2 %d   (retract, +%d frames)"
          % (playheads[0][52], playheads[1][52], playheads[0][52] - playheads[0][51]))
    print("   root 61 -> tools clip frame %d, tools2 %d"
          % (playheads[0][60], playheads[1][60]))

    print("result: %s" % ("timing verified" if not failures else "%d FAILURES" % failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
