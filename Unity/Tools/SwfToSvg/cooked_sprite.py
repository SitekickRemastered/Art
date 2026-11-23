#!/usr/bin/env python3
"""Cook a scripted sprite's parked frame into one static display list.

Chips 14 and 15 have the same shape, and so will 16: the root parks a *named*
sprite on one of the sprite's own labels, so the sprite holds a single pose for
as long as the chip is on the Sitekick.  FFDec starts every sprite at frame 1
and advances it one frame per root frame instead, so an untouched export plays
the intro that leads up to the park and then keeps going through frames only the
retract reaches.

`park()` re-emits the sprite as one frame holding the pose at frame k, on top of
the shared stopped-clip freeze: the clip is parked, not played, so the baked
frames' actions and sounds go with it.

Which sprite, which frame, and where the idle loops stay in the chip's own
patch file (`patch_chip14.py`, `patch_chip15.py`), which is where the timings
are documented.
"""

import copy
import os
import subprocess

from lxml import etree

import patch_stopped_clips as stop_clips


def _replace_child(tag, child):
    old = tag.find(child.tag)
    if old is not None:
        tag.replace(old, copy.deepcopy(child))
    else:
        tag.append(copy.deepcopy(child))


def cooked_frame(frames, k):
    """The display list of frame k as one fresh placement per depth.

    A sprite timeline is incremental: frame 1 places the characters, later
    frames mostly move them.  Ruffle replays those moves, but FFDec's SVG
    export takes a sprite's first placement at each depth, so a frame made by
    concatenating the timeline comes out at the frame-1 transforms.  Cook the
    timeline down instead: apply every place/move/remove in order and emit the
    final character, matrix and ratio once per depth.  No moves survive, so
    both renderers see the same frame.
    """
    state = {}
    for frame in frames[:k]:
        for tag in frame:
            kind = tag.get("type")
            if kind in ("PlaceObject2Tag", "PlaceObject3Tag"):
                depth = int(tag.get("depth"))
                if tag.get("placeFlagHasCharacter") == "true":
                    placed = copy.deepcopy(tag)
                    placed.set("placeFlagMove", "false")
                    state[depth] = placed
                    continue
                current = state.get(depth)
                if current is None:
                    continue
                if tag.get("placeFlagHasMatrix") == "true":
                    matrix = tag.find("matrix")
                    if matrix is not None:
                        _replace_child(current, matrix)
                        current.set("placeFlagHasMatrix", "true")
                if tag.get("placeFlagHasColorTransform") == "true":
                    color = tag.find("colorTransform")
                    if color is not None:
                        _replace_child(current, color)
                        current.set("placeFlagHasColorTransform", "true")
                for attr, flag in (("ratio", "placeFlagHasRatio"),
                                   ("name", "placeFlagHasName"),
                                   ("clipDepth", "placeFlagHasClipDepth")):
                    if tag.get(flag) == "true" and tag.get(attr) is not None:
                        current.set(attr, tag.get(attr))
                        current.set(flag, "true")
                if tag.get("placeFlagHasClipActions") == "true":
                    actions = tag.find("clipActions")
                    if actions is not None:
                        _replace_child(current, actions)
                        current.set("placeFlagHasClipActions", "true")
            elif kind == "RemoveObject2Tag":
                state.pop(int(tag.get("depth")), None)
    return [state[d] for d in sorted(state)]


def display_frame(tags, sprite_id, k):
    """Replace a clip with the one cooked frame holding its frame-k state.

    Actions and sounds are dropped: the clip is parked, not played.
    """
    item = next(t for t in tags
                if t.get("type") == "DefineSpriteTag"
                and t.get("spriteId") == str(sprite_id))
    frames = stop_clips.frames_of(item)
    cooked = cooked_frame(frames, k)
    item.set("frameCount", "1")
    sub = item.find("subTags")
    for child in list(sub):
        sub.remove(child)
    for tag in cooked:
        sub.append(copy.deepcopy(tag))
    sub.append(etree.Element("item", type=stop_clips.SHOW, forceWriteAsLong="false"))


def park(swf, workdir, sprite_id, k, xml=None):
    """Freeze the unreachable stops, then bake the sprite's frame-k pose.

    The intermediate XML/SWF are written into the workdir, never the SWF folder.
    """
    frozen = stop_clips.patched(swf, workdir, verbose=False)
    src_xml = os.path.splitext(frozen)[0] + ".xml"
    if not os.path.exists(src_xml):
        src_xml = xml or stop_clips.ensure(swf, workdir)[0]
    tree = etree.parse(src_xml)
    tags = tree.getroot().find("tags")

    display_frame(tags, sprite_id, k)

    os.makedirs(workdir, exist_ok=True)
    out_xml = os.path.join(workdir, "parked_%d.xml" % sprite_id)
    out_swf = os.path.join(workdir, "parked_%d.swf" % sprite_id)
    tree.write(out_xml, encoding="UTF-8", xml_declaration=True)
    subprocess.run(stop_clips.FFDEC + ("-xml2swf", out_xml, out_swf), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out_swf
