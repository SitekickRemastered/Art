#!/usr/bin/env python3
"""Author chip 8's hands with one tool each, as its ActionScript assigns them.

Chip 8 is the fix-it chip: six hands unfold and each holds a tool.  The tools
are not on the timeline -- the root script reads them from the server and hands
them out per hand:

    fixit.funcEnableTools = function()
    {
       var _loc3_ = 2;
       while(_loc3_ <= 6)
       {
          _loc2_ = fixit.bottom.tools["hand" + _loc3_];
          _loc2_.myNumber = fixit["tool" + _loc3_];
          _loc2_.toolset.gotoAndStop(fixit["tool" + _loc3_]);
          ...
       }
       fixit.bottom.tools2.hand1.myNumber = fixit.tool1;
       ...
    };

and when the server has nothing stored it writes the identity as the default:

    i = 0;
    while(i < 6)
    {
       _global.fixit["tool" + (i + 1)] = i + 1;   // tool1..tool6 = 1..6
       i++;
    }
    _global.infoSwap.chipData = "1~2~3~4~5~6";

So hand1 holds tool 1, hand2 tool 2, ... hand6 tool 6.  The art for those six
tools lives in the `toolset` sprite (character 51, duplicated as 84), whose six
frames each place a different tool sprite:

    frame 1 -> character 17     frame 4 -> character 38
    frame 2 -> character 25     frame 5 -> character 44
    frame 3 -> character 31     frame 6 -> character 50

Every hand is an instance of the same hand sprite (54 for hands 2-3, 59 for
hands 4-6 and hand1), and the hand sprite just places that one clip.  Nothing
ever tells FFDec's renderer to jump the clip to frame n, so every frame it
exports has all six hands on frame 1: six hammers.  This script rewrites the
authoring so the assignment is baked in:

  * six single-frame toolset sprites (5101..5106), one per tool;
  * one hand sprite per hand (5402, 5403, 5904, 5905, 5906 and 5901) that
    places its own toolset instead of the shared one;
  * the `hand1..hand6` placements in the tools timelines point at those.

Several clips are also steered by frame scripts, which FFDec never runs -- it
keeps their playheads moving instead, and that is what made the chip flicker:

  * `bottom` (83) is a two-frame clip whose frame 1 stops; the display frame
    calls bottom.gotoAndStop(2), which adds `tools2` and the seventh hand.  FFDec
    alternates the two frames, so the seventh arm blinked in and out.  Frame 1
    is authored as a single-frame sprite (8301); author_arms folds the seventh
    hand in from the display frame on.
  * `antenna` (71) extends over five frames and stops; FFDec ran on into the
    retract half and looped, waving the antenna for the whole movie.  It is
    authored as the settled frame 5 alone (7101), flattened into a one-frame
    clip: frames 1..5 as the clip's opening frames replayed the drop on every
    pass of the 16..35 loop, which starts two frames into the extend.
  * tool 5 is `tool` (44), a two-frame clip that also stops on frame 1; it is
    replaced by a single-frame copy (4401).

The arms are then steered by three `gotoAndPlay` calls on the root timeline,
which FFDec likewise never runs, so the exported frames keep the arms on their
straight playhead while Ruffle jumps:

    root frame 14   bottom.tools.gotoAndPlay(2)                 -> frame 2 of 73
                    bottom.gotoAndStop(2)                 (adds `tools2`)
    root frame 40   fixit.bottom.tools.gotoAndPlay("hover")     -> frame 16 of 73
                    fixit.bottom.tools2.gotoAndPlay("hover")    -> frame 13 of 82
    root frame 53   bottom.tools.gotoAndPlay("retract")      -> frame 46 of 73
                    bottom.tools2.gotoAndPlay("retract")     -> frame 40 of 82

FFDec advances every clip in lockstep with the root, so the playhead a jump
selects has to become the clip's own frame on that root frame: `tools` and
`tools2` are re-emitted with one frame per root frame showing the playhead the
script would have left them on (7301, 8201) -- each frame carrying the delta
from the one before, since the timeline is incremental -- and `bottom` (8300)
places both from its first frame, tools2 with nothing on screen before the
loop (root 16) -- it is the seventh hand, and the loop frames must show it even
though the file's own timeline only adds it on the display frame.
Without that the arms stay in the hover pose for the rest of the movie -- 19
frames of mismatch from root frame 40 on.

The matrix on each toolset placement (scale and rotation that seat the tool in
the hand) is carried over untouched, and the hand's own art, masks and animation
keys are the ones already in the file.

Usage:  patch_chip8_tools.py <in.swf> <out.swf> [--xml cache.xml]
"""

import argparse
import copy
import os
import subprocess
import sys

from lxml import etree

# toolset sprite -> the hand that places it, per hand number, and the tool each
# hand is assigned by the script (hand_k -> tool k, see module docstring)
TOOLS = {1: 17, 2: 25, 3: 31, 4: 38, 5: 44, 6: 50}
HANDS = {1: 59, 2: 54, 3: 54, 4: 59, 5: 59, 6: 59}
TOOLSET_IDS = {k: 5100 + k for k in TOOLS}
HAND_IDS = {k: (5400 if HANDS[k] == 54 else 5900) + k for k in TOOLS}


def run(*args):
    subprocess.run(list(args), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def swf2xml(swf, xml_path):
    run("flatpak", "run", "--command=ffdec.sh", "com.jpexs.decompiler.flash",
        "-swf2xml", swf, xml_path)
    return xml_path


def sprite(sid, tags):
    for item in tags:
        if item.get("type") == "DefineSpriteTag" and int(item.get("spriteId")) == sid:
            return item
    raise KeyError("no sprite %d" % sid)


def body(item):
    return item.find("subTags")


def show_frame():
    return etree.Element("item", type="ShowFrameTag", forceWriteAsLong="false")


def frames_of(item):
    """The sprite's frames, each a list of its tags without the ShowFrameTag."""
    frames, current = [], []
    for sub in body(item):
        if sub.get("type") == "ShowFrameTag":
            frames.append(current)
            current = []
        else:
            current.append(sub)
    if current:
        frames.append(current)
    return frames


def define(tags, sprite_id, frames):
    """A new sprite holding exactly these frames."""
    item = etree.SubElement(tags, "item", type="DefineSpriteTag", spriteId=str(sprite_id))
    sub = etree.SubElement(item, "subTags")
    for frame in frames:
        for tag in frame:
            sub.append(copy.deepcopy(tag))
        sub.append(show_frame())
    return item


def without_actions(frames):
    """Drop DoAction tags: they are what FFDec cannot honour (see module doc)."""
    return [[t for t in f if t.get("type") != "DoActionTag"] for f in frames]


def place_char(tags_or_frame, old, new, drop_ratio=True):
    """Repoint the placements of one character inside a frame/tag list."""
    hits = 0
    for tag in tags_or_frame:
        if tag.get("type", "").startswith("PlaceObject") and tag.get("characterId") == str(old):
            tag.set("characterId", str(new))
            hits += 1
            if drop_ratio and tag.get("placeFlagHasRatio") == "true":
                tag.set("placeFlagHasRatio", "false")
                tag.attrib.pop("ratio", None)
    return hits


def place_of(holdings, name):
    for sub in holdings:
        if sub.get("type", "").startswith("PlaceObject") and sub.get("name") == name:
            return sub
    return None


def patch(root):
    tags = root.find("tags")
    toolset = sprite(51, tags)
    frames = frames_of(toolset)
    assert len(frames) == 6, len(frames)

    # Tool 5 is character 44, a two-frame clip whose first frame stops: FFDec
    # advances it anyway, so the fifth hand's tool changes shape every frame.
    tool44 = frames_of(sprite(44, tags))
    define(tags, 4401, [without_actions(tool44)[0]])

    # one single-frame toolset per tool, so a hand can be authored to hold it
    for k in TOOLS:
        holds = frames[k - 1]
        placed = [s for s in holds if s.get("type", "").startswith("PlaceObject")]
        assert len(placed) == 1, (k, len(placed))
        assert int(placed[0].get("characterId")) == TOOLS[k], (k, placed[0].get("characterId"))
        tool = copy.deepcopy(placed[0])
        if int(tool.get("characterId")) == 44:
            tool.set("characterId", "4401")
        define(tags, TOOLSET_IDS[k], [[tool]])

    # one hand per hand number, holding its tool
    for k in TOOLS:
        src = sprite(HANDS[k], tags)
        item = copy.deepcopy(src)
        item.set("spriteId", str(HAND_IDS[k]))
        hold = place_of(body(item), "toolset")
        assert hold is not None
        hold.set("characterId", str(TOOLSET_IDS[k]))
        tags.append(item)

    # point the timelines at the per-hand sprites
    tools = sprite(73, tags)
    tools2 = sprite(82, tags)
    for item, names in ((tools, "hand2 hand3 hand4 hand5 hand6"), (tools2, "hand1")):
        for sub in body(item):
            if sub.get("type", "").startswith("PlaceObject") and sub.get("name") in names.split():
                n = int(sub.get("name")[4:])
                assert sub.get("name") == "hand%d" % n
                sub.set("characterId", str(HAND_IDS[n]))

    author_bottom(tags)
    author_antenna(tags)
    author_arms(tags)
    drop_dead_sprites(tags)
    return root


def own_placements(item, tags):
    """Characters placed by this timeline itself, not by its children."""
    container = tags if item is tags else (item.find("subTags") if item.get("type") == "DefineSpriteTag" else None)
    if container is None:
        return []
    return [int(sub.get("characterId")) for sub in container
            if sub.tag == "item" and sub.get("type", "").startswith("PlaceObject")
            and sub.get("characterId")]


def drop_dead_sprites(tags):
    """Delete sprites nothing on the timeline can reach.

    Once the hands hold their own single-frame toolsets and `bottom`/`antenna`
    are authored copies, the originals are unreachable: nothing places them, so
    they are dead weight in the SWF (and dead characters in every export).  The
    duplicate toolset (84) stays: the root still places it at depth 91.
    """
    sprites = {int(item.get("spriteId")): item for item in tags
               if item.get("type") == "DefineSpriteTag"}
    reached, pending = set(), list(own_placements(tags, tags))
    while pending:
        cid = pending.pop()
        if cid in reached:
            continue
        reached.add(cid)
        if cid in sprites:
            pending.extend(own_placements(sprites[cid], tags))
    dead = sorted(sid for sid in sprites if sid not in reached)
    assert 51 in dead, "the original toolset is still placed somewhere"
    for sid in dead:
        tags.remove(sprites[sid])
    return dead


def author_bottom(tags):
    """`bottom` (83) must not flip between its two frames every frame.

    Its frame 1 stops and the root script calls bottom.gotoAndStop(2) on the
    display frame (40), which adds `tools2` and so the seventh hand.  FFDec does
    not run the stop and advances the two-frame clip, so the seventh arm blinks
    in and out.  Frame 1 is authored as a single-frame sprite (8301) and taking
    on `tools2` is folded in by author_arms.
    """
    define(tags, 8301, [without_actions(frames_of(sprite(83, tags)))[0]])
    place = root_place(tags, 83)
    place.set("characterId", "8301")


def root_place(tags, char):
    """The root timeline's placement of one character."""
    for sub in tags:
        if (sub.get("type", "").startswith("PlaceObject")
                and sub.get("characterId") == str(char)):
            return sub
    raise AssertionError("root never places %d" % char)


def after_frame(tags, n):
    """Index just past the ShowFrame that ends frame n-1: where frame n starts."""
    if n <= 1:
        return 0
    seen = 0
    for i, sub in enumerate(tags):
        if sub.get("type") == "ShowFrameTag":
            seen += 1
            if seen == n - 1:
                return i + 1
    raise AssertionError("root has no frame %d" % n)


def raw_frames(item):
    """The sprite's raw tags per frame: the timeline is incremental, no ShowFrame."""
    frames, current = [], []
    for sub in body(item):
        if sub.get("type") == "ShowFrameTag":
            frames.append(current)
            current = []
        else:
            current.append(sub)
    if current:
        frames.append(current)
    return frames


def apply_delta(state, frame):
    """Fold one frame's PlaceObject/RemoveObject tags into depth -> placement."""
    for tag in frame:
        kind = tag.get("type", "")
        depth = tag.get("depth")
        if kind.startswith("PlaceObject"):
            has_char = tag.get("placeFlagHasCharacter", "true") != "false"
            if has_char and tag.get("characterId"):
                state[depth] = copy.deepcopy(tag)
            elif depth in state:
                # a move/transform update: the frame only carries what changed
                cur = state[depth]
                for name, flag in (("matrix", "placeFlagHasMatrix"),
                                   ("colorTransform", "placeFlagHasColorTransform")):
                    new = tag.find(name)
                    if new is None:
                        continue
                    old = cur.find(name)
                    if old is not None:
                        cur.remove(old)
                    cur.append(copy.deepcopy(new))
                    cur.set(flag, "true")
                if tag.get("name") is not None:
                    cur.set("placeFlagHasName", "true")
                    cur.set("name", tag.get("name"))
        elif kind.startswith("RemoveObject"):
            state.pop(depth, None)


def labels(item):
    """frame label -> frame number for one sprite."""
    out = {}
    for n, frame in enumerate(raw_frames(item), 1):
        for tag in frame:
            if tag.get("type") == "FrameLabelTag":
                out[tag.get("name")] = n
    return out


def states(sid, tags):
    """The display list of sprite `sid` at each of its frames."""
    state, out = {}, []
    for frame in raw_frames(sprite(sid, tags)):
        apply_delta(state, frame)
        out.append({depth: copy.deepcopy(po) for depth, po in state.items()})
    return out


def flattened(tags, sid, ph):
    """The whole display list of sprite `sid` at frame `ph`, as one frame."""
    per_frame = states(sid, tags)
    frame = [copy.deepcopy(per_frame[ph - 1][d])
             for d in sorted(per_frame[ph - 1], key=int)]
    for po in frame:
        po.set("placeFlagMove", "false")
        po.set("placeFlagHasCharacter", "true")
    return frame


def retimed(tags, sid, new_id, playheads, fresh_at=None):
    """Sprite `sid` re-emitted once per root frame, at `playheads[frame]`.

    FFDec's frame export advances every clip in lockstep with the root, so a
    clip placed later cannot start at its own frame 1: the playhead a script
    jump selects has to become the clip's own frame for that root frame.  The
    clip's own frame tags are replayed in that order, so moves, removes and the
    ratio-driven masks keep acting on the instances they act on in the file;
    `fresh_at` is the frame where the clip starts out of nothing (`None` before
    it), which needs the whole display list flattened.
    """
    raw = without_actions(raw_frames(sprite(sid, tags)))
    out = []
    for i, ph in enumerate(playheads):
        if ph is None:
            out.append([])
            continue
        idx = min(len(raw), max(1, ph)) - 1
        if fresh_at == i:
            out.append(flattened(tags, sid, idx + 1))
        else:
            out.append([copy.deepcopy(tag) for tag in raw[idx]])
    define(tags, new_id, out)
    return len(raw)


def arm_playheads(frames, hover, retract, display=40, release=53, loop_start=16):
    """What the two arm clips show on each root frame, following the script.

    root 40   tools/tools2 -> "hover"
    root 53   tools/tools2 -> "retract"

    The straight playhead already agrees up to the display frame, so only the
    two jumps reorder anything.

    `tools` (hand2..hand6) plays from the start.  `tools2` is the seventh hand
    and only exists once the script's `bottom.gotoAndStop(2)` on the display
    frame has run, so the intro does not show it -- but the movie loops back
    over 16..35 *after* that jump, and the seventh hand is the one holding the
    oil can.  Leaving it out of the loop is what made the export look armless
    beside Ruffle, which shows all six hands there.
    """
    tools, tools2 = [], []
    for n in range(1, frames + 1):
        if n < display:
            tools.append(n)
        elif n < release:
            tools.append(hover[0] + (n - display))
        else:
            tools.append(retract[0] + (n - release))
        if n < loop_start:
            tools2.append(None)
        elif n < display:
            tools2.append(hover[1] + (n - loop_start))
        elif n < release:
            tools2.append(hover[1] + (n - display))
        else:
            tools2.append(retract[1] + (n - release))
    return tools, tools2


def author_arms(tags):
    """Bake the root's arms jumps into the clips' own timelines.

    The script sends `tools`/`tools2` to their `hover` labels on the display
    frame and to `retract` eleven frames into the retract section.  Both clips
    are re-emitted with one frame per root frame showing the playhead the
    script would have left them on, and `bottom` places them from the first
    frame so the export's lockstep advance renders exactly that.
    """
    root_frames = sum(1 for s in tags if s.get("type") == "ShowFrameTag")
    hover = (labels(sprite(73, tags))["hover"], labels(sprite(82, tags))["hover"])
    retract = (labels(sprite(73, tags))["retract"], labels(sprite(82, tags))["retract"])
    tools, tools2 = arm_playheads(root_frames, hover, retract)
    retimed(tags, 73, 7301, tools)
    retimed(tags, 82, 8201, tools2, fresh_at=15)   # tools2 starts on the loop

    bottom = frames_of(sprite(83, tags))
    frame = copy.deepcopy(without_actions(bottom)[0])
    second = [t for t in bottom[1] if t.get("type", "").startswith("PlaceObject")]
    assert len(second) == 1, second
    frame += copy.deepcopy(second)
    assert place_char(frame, 73, 7301, drop_ratio=False) == 1, "tools placement"
    assert place_char(frame, 82, 8201, drop_ratio=False) == 1, "tools2 placement"
    # one frame only: re-placing them every frame would restart their instances
    define(tags, 8300, [frame])
    root_place(tags, 8301).set("characterId", "8300")


def author_antenna(tags):
    """`antenna` (71) extends over four frames, then stops on frame 5.

    FFDec rolls on into the retract half and loops, so the antenna waves up and
    down for the whole movie.  Hold the settled pose instead: frame 5 is the
    frame the sprite's own `stop` sits on, so one frame flattened from it cannot
    replay the drop.  Keeping frames 1..5 as the clip's opening frames replayed
    it on every pass of the 16..35 loop, because the loop starts two frames into
    the extend.
    """
    define(tags, 7101, [flattened(tags, 71, 5)])
    flat = [t for frame in frames_of(sprite(73, tags)) for t in frame]
    assert place_char(flat, 71, 7101) == 1, "antenna placement"


def patched(swf, workdir):
    """The SWF to render frames from: this chip's, with its tools authored in.

    The source XML is never written back: patching a patched file would add a
    second set of hand sprites on every run.
    """
    xml_dir = os.path.join(workdir, "xml")
    os.makedirs(xml_dir, exist_ok=True)
    # the cache must be the source file: `lib.xml` gets rewritten from the
    # patched SWF by the export, and patching that again finds no sprite 51
    src_xml = os.path.join(xml_dir, "lib.src.xml")
    if not os.path.exists(src_xml):
        swf2xml(swf, src_xml)
    out = os.path.join(workdir, os.path.basename(swf).replace(".swf", "_tools.swf"))
    out_xml = out.replace(".swf", ".xml")
    tree = etree.parse(src_xml)
    patch(tree.getroot())
    tree.write(out_xml, encoding="UTF-8", xml_declaration=True)
    run("flatpak", "run", "--command=ffdec.sh", "com.jpexs.decompiler.flash",
        "-xml2swf", out_xml, out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("swf")
    ap.add_argument("out")
    ap.add_argument("--xml", default=None, help="swf2xml cache to reuse")
    args = ap.parse_args()

    src_xml = args.xml or os.path.splitext(args.out)[0] + ".src.xml"
    if not os.path.exists(src_xml):
        swf2xml(args.swf, src_xml)
    out_xml = os.path.splitext(args.out)[0] + ".patched.xml"
    tree = etree.parse(src_xml)
    patch(tree.getroot())
    tree.write(out_xml, encoding="UTF-8", xml_declaration=True)
    run("flatpak", "run", "--command=ffdec.sh", "com.jpexs.decompiler.flash",
        "-xml2swf", out_xml, args.out)
    print(args.out)


if __name__ == "__main__":
    main()
