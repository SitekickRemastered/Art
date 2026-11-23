#!/usr/bin/env python3
"""Pull one effect out of an Effect Library SWF as a standalone movie.

The libraries under `Source/Effect Libraries/` are the site's AS3 asset bundle:
one `SymbolClass` entry per effect (`corus.effects.effect_000037` ->
`symbol1274`), with the animation living on that symbol's own timeline and the
behaviour in the class (`mouseClickEffect`, label jumps, onEnter listeners).
Chips 37 and 53 have no standalone SWF anywhere in the repo, so their movies
are authored from the symbol itself.

The standalone movie keeps every character definition the effect sprite can
reach -- following placements, fonts, bitmaps and sounds alike, so nothing the
symbol depends on goes missing -- and replaces the library's root timeline --
four empty frames -- with one placement of the effect sprite, held for as many
frames as the sprite is long.  Played
without the class, that is exactly the timeline, which is what the SVG export
and the Ruffle reference read.

Usage:  extract_effect.py <library.swf> <effect> <out.swf>
            [--stage 375x300] [--offset X,Y] [--frames N]

`--stage` rewrites the stage rectangle (the library's own is 550x400, which is
just its canvas); `--offset` translates the sprite by that many stage pixels, to
put the art where the 375x300 effect holder expects it.
"""

import os
import shutil
import subprocess
import sys

from lxml import etree

FFDEC = ("flatpak", "run", "--command=ffdec.sh", "com.jpexs.decompiler.flash")
HOME = os.environ["HOME"]
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
# scratch stays inside the project: Temp/ is gitignored, and a normal run then
# leaves nothing to clean up outside the Unity folder
CACHE = os.path.join(ROOT, "Temp", "swftosvg", "lib")
# the flatpak only mounts $HOME; only a checkout that lives outside it needs this
STAGE = os.path.join(HOME, ".cache", "swftosvg")

# tags that define something a placement can point at, plus the ones that carry
# global settings; everything else in the library's tag list is root timeline
KEEP_ALWAYS = {"FileAttributesTag", "MetadataTag", "SetBackgroundColorTag",
               "ProtectTag", "JPEGTablesTag", "DoABC2Tag", "DoABCTag",
               "SymbolClassTag", "ExportAssetsTag", "ImportAssetsTag",
               "ScriptLimitsTag", "EnableDebuggerTag", "EnableDebugger2Tag"}

# every attribute that carries a character id, whether it is a tag's own id
# (a shape's `shapeId`, a font's `fontId`) or a reference to another character
# (a placement's `characterId`, a text record's `fontId`, a bitmap fill's
# `bitmapId`, a button's `soundId`, ...).  The reachability walk below follows
# all of them: `characterId` alone is only what placements use.  FFDec spells
# some of these with a capitalised suffix (`DefineEditTextTag`'s `characterID`,
# `DefineFontNameTag`'s `fontID`), so both spellings are listed.
ID_ATTRS = ("characterId", "characterID", "spriteId", "spriteID",
            "shapeId", "shapeID", "soundId", "soundID", "fontId", "fontID",
            "buttonId", "buttonID", "bitmapId", "bitmapID", "textId",
            "textID", "imageId", "imageID", "videoId", "videoID")


def run(*args):
    subprocess.run(list(args), check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)


def flatpak_path(path, into=False):
    """A path FFDec can reach; its sandbox only mounts $HOME.

    Inside $HOME (where the checkout normally is) this is the path itself, so
    nothing is staged.  A checkout elsewhere gets a copy in `$HOME/.cache`:
    `into` for an input that has to be copied there first, plain for an output
    the caller then copies back.
    """
    if os.path.abspath(path).startswith(HOME + os.sep):
        return path
    os.makedirs(STAGE, exist_ok=True)
    local = os.path.join(STAGE, os.path.basename(path))
    if into:
        shutil.copyfile(path, local)
    return local


def library_xml(swf):
    """swf2xml of the library, cached: it is the slow part of the pull."""
    os.makedirs(CACHE, exist_ok=True)
    name = os.path.splitext(os.path.basename(swf))[0]
    path = os.path.join(CACHE, name + ".xml")
    if not os.path.exists(path):
        out = flatpak_path(path)
        run(*FFDEC, "-swf2xml", flatpak_path(swf, into=True), out)
        if out != path:
            shutil.copyfile(out, path)
            os.unlink(out)
    return path


def symbol_for(root, effect):
    """The character id the effect's SymbolClass entry points at."""
    class_name = "corus.effects.effect_%06d" % effect
    for tag in root.find("tags"):
        if tag.get("type") != "SymbolClassTag":
            continue
        ids = [i.get("tag") or i.text for i in tag.find("tags")]
        names = [i.get("name") or i.text for i in tag.find("names")]
        for cid, name in zip(ids, names):
            if name == class_name:
                return int(cid)
    raise SystemExit("no SymbolClass entry for %s" % class_name)


def sprite(tags, sid):
    for item in tags:
        if item.get("type") == "DefineSpriteTag" and int(item.get("spriteId")) == sid:
            return item
    raise SystemExit("character %d is not a sprite" % sid)


def frame_count(item):
    return sum(1 for sub in item.find("subTags") if sub.get("type") == "ShowFrameTag")


def labels(item):
    out, n = {}, 1
    for sub in item.find("subTags"):
        if sub.get("type") == "FrameLabelTag":
            out[sub.get("name")] = n
        elif sub.get("type") == "ShowFrameTag":
            n += 1
    return out


def rect(width, height):
    return {"type": "RECT", "Xmin": "0", "Ymin": "0",
            "Xmax": str(int(width * 20)), "Ymax": str(int(height * 20)),
            "nbits": "15"}


# Define tags that decorate another character instead of defining one: they
# carry the id of the character they belong to (a sprite's scaling grid, a
# font's hinting zones / info / name), so they are kept with that character and
# never shadow its own definition.  `lxml` element identity is not stable, so
# nothing below keys on element objects -- only on the character ids themselves.
DECORATES = {"DefineScalingGridTag": "characterId",
             "DefineFontAlignZonesTag": "fontId",
             "DefineFontInfoTag": "fontId",
             "DefineFontInfo2Tag": "fontId",
             "DefineFontNameTag": "fontId"}


def character_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def own_id(item):
    """The id a definition is filed under, i.e. its own and not a reference.

    `ID_ATTRS` is ordered so a tag's identity comes before the characters it
    points at (`DefineEditTextTag` has both `characterID` and `fontId`).
    """
    for attr in ID_ATTRS:
        cid = character_id(item.get(attr))
        if cid is not None:
            return cid
    return None


def definitions(tags):
    """Every character definition in the tag list, keyed by its own id.

    Returns `id -> (tag, identity attribute)`; decoration tags are skipped so
    a `DefineScalingGridTag` cannot replace the sprite whose id it carries.
    """
    defs = {}
    for item in tags:
        kind = str(item.get("type", ""))
        if not kind.startswith("Define") or kind == "DefineSceneAndFrameLabelDataTag" \
                or kind in DECORATES:
            continue
        for attr in ID_ATTRS:
            cid = character_id(item.get(attr))
            if cid is not None:
                defs[cid] = (item, attr)
                break
    return defs


def references(item, own):
    """Every character id this tag points at, by any id-bearing name.

    A placement reaches its character with `characterId`, but that is not the
    only way one definition reaches another: a text record carries its font as
    `fontId`, a shape's bitmap fill carries `bitmapId`, a button its `soundId`,
    a `DefineFontInfo`/`DefineFontAlignZones` its `fontId`.  Following only
    `characterId` silently drops that art, so every `ID_ATTRS` attribute is
    followed -- as an attribute, and as a child element for the tags FFDec
    writes that way (`<bitmapId>20</bitmapId>`).  `own` is the attribute holding
    this tag's own id, which is not a reference to itself and is skipped.
    """
    found = set()
    for index, sub in enumerate(item.iter()):
        if index and sub.tag in ID_ATTRS:
            cid = character_id(sub.text)
            if cid is not None:
                found.add(cid)
        for attr, value in sub.attrib.items():
            if attr not in ID_ATTRS or (index == 0 and attr == own):
                continue
            cid = character_id(value)
            if cid is not None:
                found.add(cid)
    return found


def prune(tags, keep_ids):
    """Drop the definitions the effect cannot reach.

    The library is one big asset bundle; carrying all of it makes the standalone
    a copy of the library (and its XML 36 MB, which is too slow to build a
    frame-exact Ruffle reference from).  Walk every character the kept tags
    point at -- by every id-bearing attribute, not just `characterId` (see
    `references`), so a kept text record does not lose its font and a
    bitmap-filled shape does not lose its bitmap -- and keep only that.
    """
    defs = definitions(tags)

    keep, pending = set(), [i for i in keep_ids]
    while pending:
        cid = pending.pop()
        if cid in keep or cid not in defs:
            continue
        keep.add(cid)
        item, own = defs[cid]
        pending.extend(references(item, own) - keep)

    unreached = set(defs) - keep
    for item in list(tags):
        kind = str(item.get("type", ""))
        if kind == "SymbolClassTag":
            ids = item.find("tags")
            names = item.find("names")
            pairs = list(zip(list(ids), list(names)))
            for a, b in pairs:
                ids.remove(a)
                names.remove(b)
            for a, b in pairs:
                if int(a.get("tag") or a.text) in keep:
                    ids.append(a)
                    names.append(b)
        elif kind in DECORATES:
            if character_id(item.get(DECORATES[kind])) not in keep:
                tags.remove(item)
        elif kind.startswith("Define") and kind != "DefineSceneAndFrameLabelDataTag":
            if own_id(item) in unreached:
                tags.remove(item)
    return len(keep)


def standalone(xml, effect, out_swf, stage=None, offset=(0, 0), frames=None):
    tree = etree.parse(xml)
    root = tree.getroot()
    tags = root.find("tags")
    sid = symbol_for(root, effect)
    effect_sprite = sprite(tags, sid)
    total = frame_count(effect_sprite)

    kept = [t for t in tags
            if str(t.get("type", "")).startswith("Define") or t.get("type") in KEEP_ALWAYS
            if t.get("type") != "DefineSceneAndFrameLabelDataTag"]
    # the effect's own sprite is the root's only starting point; everything it
    # does not place is another chip's art and does not belong in this movie
    for t in list(tags):
        tags.remove(t)
    for t in kept:
        tags.append(t)
    prune(tags, [sid])

    place = etree.SubElement(tags, "item", type="PlaceObject2Tag", forceWriteAsLong="false",
                             characterId=str(sid), depth="1",
                             placeFlagHasCharacter="true", placeFlagHasClipActions="false",
                             placeFlagHasClipDepth="false", placeFlagHasColorTransform="false",
                             placeFlagHasMatrix="true", placeFlagHasName="false",
                             placeFlagHasRatio="false", placeFlagMove="false")
    etree.SubElement(place, "matrix", type="MATRIX", hasRotate="false", hasScale="false",
                     nRotateBits="0", nScaleBits="0", nTranslateBits="15",
                     translateX=str(int(offset[0] * 20)),
                     translateY=str(int(offset[1] * 20)))
    for _ in range(frames or total):
        etree.SubElement(tags, "item", type="ShowFrameTag", forceWriteAsLong="false")

    root.set("frameCount", str(frames or total))
    if stage:
        old = root.find("displayRect")
        new = etree.Element("displayRect", **rect(*stage))
        root.replace(old, new)

    out_xml = os.path.splitext(out_swf)[0] + ".src.xml"
    tree.write(out_xml, encoding="UTF-8", xml_declaration=True)
    run(*FFDEC, "-xml2swf", out_xml, out_swf)
    return sid, total, labels(effect_sprite)


def main():
    args = sys.argv[1:]
    if len(args) < 3:
        raise SystemExit(__doc__)
    lib, effect, out = args[0], int(args[1]), args[2]
    stage = offset = None
    frames = None
    i = 3
    while i < len(args):
        if args[i] == "--stage":
            w, h = args[i + 1].lower().split("x")
            stage = (float(w), float(h))
            i += 2
        elif args[i] == "--offset":
            x, y = args[i + 1].split(",")
            offset = (float(x), float(y))
            i += 2
        elif args[i] == "--frames":
            frames = int(args[i + 1])
            i += 2
        else:
            raise SystemExit("unknown option " + args[i])

    sid, total, labs = standalone(library_xml(lib), effect, out, stage, offset or (0, 0), frames)
    print("%s -> %s: sprite %d, %d frames%s"
          % (os.path.basename(lib), out, sid, total,
             (", labels " + repr(labs)) if labs else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
