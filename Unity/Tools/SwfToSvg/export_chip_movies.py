#!/usr/bin/env python3
"""Re-export chips 7-16 from the individual chip SWFs in Unity/SWF.

Those files are standalone stage movies (375x300, 12 fps, 39-152 frames): the
whole effect as Flash plays it, which is a better copy than what the effect
library produced.  This script turns each one into Unity-ready pieces:

  Assets/Chips/<range>/Chip_XXXX/Movie/frame_NNN.svg   one normalised SVG per frame
  Assets/Chips/<range>/Chip_XXXX/Movie/sound_<id>.mp3  the SoundStream/StartSound clips
  Assets/Chips/<range>/Chip_XXXX/Movie/movie.json      fps, frames, sounds, pause points

Registration: the movies are drawn on the 375x300 stage centred on (187.5, 150).
The Sitekick's own eye is 0.221 prefab units across; the eyeball chip 7 opens
with is 64 stage pixels, which fixes the stage scale (see STAGE_UNITS_PER_PX).
The builder places the stage centre on the Sitekick's eye centre.

Pause points are read from the decompiled root timeline: a frame whose DoAction
calls stop() halts the movie in Flash, and the player stops there too.

Usage:  python3 Tools/SwfToSvg/export_chip_movies.py [--ids 7-16]
"""

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import uuid

import numpy as np
from lxml import etree
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TMP = os.path.join(os.environ["HOME"], "sitekick-movies")
FFDEC = ["flatpak", "run", "--command=ffdec.sh", "com.jpexs.decompiler.flash"]

sys.path.insert(0, HERE)
import flatten_svg as flatten
import normalize as N

TEMPLATE_SVG_META = os.path.join(
    ROOT, "Assets/Chips/0101-0200/Chip_0177/Sprites/chip_0177_back.svg.meta")

# The stage is the Sitekick's face: 1.100 prefab units across 375 stage px.
STAGE_UNITS_PER_PX = 0.0029333

SOUND_META = """fileFormatVersion: 2
guid: {guid}
AudioImporter:
  externalObjects: {{}}
  serializedVersion: 7
  defaultSettings:
    loadType: 0
    sampleRateSetting: 0
    sampleRateOverride: 44100
    compressionFormat: 1
    quality: 1
    conversionMode: 0
    preloadAudioData: 1
  platformSettingOverrides: {{}}
  forceToMono: 0
  normalize: 1
  loadInBackground: 0
  ambisonic: 0
"""


def run(*args):
    subprocess.run(list(args), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def svg_meta(name, ppu=100, meta_path=None):
    txt = open(TEMPLATE_SVG_META, encoding="utf-8").read()
    # a frame keeps its guid across exports, so anything already pointing at the
    # sprite (prefabs, the movie's own references) survives a re-export
    guid = uuid.uuid4().hex
    if meta_path and os.path.exists(meta_path):
        old = re.search(r"^guid: (.*)$", open(meta_path, encoding="utf-8").read(), re.M)
        if old:
            guid = old.group(1)
    txt = re.sub(r"^guid: .*$", "guid: " + guid, txt, count=1, flags=re.M)
    txt = re.sub(r"^  spriteData:\n(?:    .*\n)*",
                 "  spriteData:\n    TessellationDetail: 0\n"
                 "    SpriteName: %s\n    SpritePivot: {x: 0.5, y: 0.5}\n" % name,
                 txt, count=1, flags=re.M)
    txt = re.sub(r"^  svgPixelsPerUnit: .*$", "  svgPixelsPerUnit: %s" % ppu, txt, count=1, flags=re.M)
    # A movie needs every frame on the same rect: keep the SVG viewport instead of
    # letting the importer crop to each frame's own drawing.
    txt = re.sub(r"^  preserveViewport: .*$", "  preserveViewport: 1", txt, count=1, flags=re.M)
    return txt


def fix_stage(path, w, h):
    """Drop the stage's backdrop, then hold the full canvas open.

    The backdrop is the movie's own screen fill, not artwork.  The effect is
    laid over the Sitekick's face, which is already the screen, so painting that
    fill would just put a coloured disc on the Sitekick: only the drawing stays.

    The near-invisible canvas rect matters more than it looks: Unity sizes a
    sprite from its drawing, so without it every frame would be trimmed to its
    own content and the movie would jitter and scale per frame.
    """
    text = open(path, encoding="utf-8").read()

    # FFDec writes the stage colour as one full-canvas rect before the drawing.
    text = re.sub(r'<rect fill="#[0-9a-fA-F]{6}" height="[\d.]+px" width="[\d.]+px"/>',
                  "", text, count=1)

    canvas = '<rect fill="#000000" fill-opacity="0.004" width="%g" height="%g"/>' % (w, h)
    text = re.sub(r'(<svg[^>]*>)', r'\1' + canvas, text, count=1)

    open(path, "w", encoding="utf-8").write(text)


def root_tags(xml_path):
    """Only the timeline's own tags, not the contents of each sprite."""
    tree = etree.parse(xml_path)
    root = tree.getroot()
    tags = root.find("tags")
    return list(tags) if tags is not None else []


def sprite_timelines(tags):
    """characterId -> the sprite's own frame-by-frame tags."""
    out = {}
    for item in tags:
        if item.get("type") != "DefineSpriteTag":
            continue
        frames, current = [], []
        for sub in item.findall("subTags/item"):
            if sub.get("type") == "ShowFrameTag":
                frames.append(current)
                current = []
            else:
                current.append(sub)
        frames.append(current)
        out[int(item.get("spriteId"))] = frames
    return out


def owner_map(tags, sprites):
    """characterId -> (owner sprite id or None for root, frame it is placed on)."""
    owner = {}
    for item in tags:
        if item.get("type") == "PlaceObject2Tag" and item.get("characterId"):
            owner.setdefault(int(item.get("characterId")), (None, 0))
    for sid, frames in sprites.items():
        for n, frame in enumerate(frames):
            for sub in frame:
                if sub.get("type") == "PlaceObject2Tag" and sub.get("characterId"):
                    owner[int(sub.get("characterId"))] = (sid, n)
    return owner


def timeline(xml_path):
    """Frame index of every sound start, followed through the sprite it plays in.

    These movies start their clips from inside sub-sprites, not on the root
    timeline, so each sound walks up its placement chain to the root frame at
    which the chain begins.
    """
    tags = root_tags(xml_path)
    sprites = sprite_timelines(tags)
    owner = owner_map(tags, sprites)

    starts = {}   # sprite id -> (internal frame, sound id)
    for sid, frames in sprites.items():
        for n, frame in enumerate(frames):
            for sub in frame:
                if sub.get("type") == "StartSoundTag":
                    starts.setdefault(sid, []).append((n, int(sub.get("soundId"))))

    # Half of these chips also start clips on their own timeline, which the
    # sprite walk above never sees.
    root_starts = []
    root_frame = 1
    for item in tags:
        if item.get("type") == "StartSoundTag":
            root_starts.append({"frame": root_frame, "sound": int(item.get("soundId"))})
        elif item.get("type") == "ShowFrameTag":
            root_frame += 1

    # root frame where each root-placed character first appears
    placed_at, frame = {}, 1
    for item in tags:
        if item.get("type") == "ShowFrameTag":
            frame += 1
        elif item.get("type") == "PlaceObject2Tag" and item.get("characterId"):
            placed_at.setdefault(int(item.get("characterId")), frame)

    sounds = []
    for sid, entries in starts.items():
        offset, node = 0, sid
        seen = set()
        while node in owner and node not in seen:
            seen.add(node)
            parent, at = owner[node]
            offset += at          # sprite placed on its parent's frame `at`
            if parent is None:
                break
            node = parent
        start = placed_at.get(node, 1) + offset
        for internal, sound in entries:
            sounds.append({"frame": max(1, start + internal), "sound": sound})

    sounds.extend(root_starts)
    sounds.sort(key=lambda s: s["frame"])

    total = sum(1 for item in tags if item.get("type") == "ShowFrameTag")
    return sounds, [], total


def pause_frames(script_dir):
    frames = []
    for path in glob.glob(os.path.join(script_dir, "frame_*", "DoAction.as")):
        m = re.search(r"frame_(\d+)", path)
        body = open(path, encoding="utf-8", errors="ignore").read()
        if m and re.search(r"(?m)^\s*stop\(\s*\)\s*;", body):
            frames.append(int(m.group(1)))
    return sorted(frames)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="7-16")
    args = ap.parse_args()

    lo, hi = (int(x) for x in args.ids.split("-"))
    os.makedirs(TMP, exist_ok=True)

    for chip in range(lo, hi + 1):
        swf = os.path.join(ROOT, "SWF", "chip_%04d.swf" % chip)
        if not os.path.exists(swf):
            print(chip, "MISSING", swf)
            continue

        work = os.path.join(TMP, "%04d" % chip)
        shutil.rmtree(work, ignore_errors=True)
        for sub in ("svg", "png", "snd", "scr", "xml"):
            os.makedirs(os.path.join(work, sub), exist_ok=True)

        run(*FFDEC, "-format", "frame:svg", "-export", "frame", os.path.join(work, "svg"), swf)
        run(*FFDEC, "-format", "frame:png", "-export", "frame", os.path.join(work, "png"), swf)
        run(*FFDEC, "-export", "sound", os.path.join(work, "snd"), swf)
        run(*FFDEC, "-export", "script", os.path.join(work, "scr"), swf)
        run(*FFDEC, "-swf2xml", swf, os.path.join(work, "xml", "lib.xml"))

        sounds, _, frames = timeline(os.path.join(work, "xml", "lib.xml"))
        pauses = pause_frames(os.path.join(work, "scr", "scripts"))

        chip_dir = glob.glob(os.path.join(ROOT, "Assets/Chips", "*", "Chip_%04d" % chip))
        if not chip_dir:
            print(chip, "no chip folder"); continue
        out = os.path.join(chip_dir[0], "Movie")
        shutil.rmtree(out, ignore_errors=True)
        os.makedirs(out, exist_ok=True)

        # frames: normalise each stage render, keep the canvas numbers
        frame_files = sorted(glob.glob(os.path.join(work, "svg", "*.svg")),
                             key=lambda p: int(re.search(r"(\d+)\.svg$", p).group(1)))
        names = []
        stage = None
        for n, src in enumerate(frame_files, 1):
            name = "frame_%03d" % n
            dst = os.path.join(out, name + ".svg")
            meta = N.convert(src, dst, scale=N.SCALE)
            fix_stage(dst, meta["w_swf"], meta["h_swf"])
            # Unity's import tessellates a curve to a chord every ~60 px at the
            # size these play, so the curves are cut to sub-pixel segments here
            flatten.flatten_file(dst)
            open(dst + ".meta", "w", encoding="utf-8").write(svg_meta(name + "Sprite", meta_path=dst + ".meta"))
            names.append(name + ".svg")
            if stage is None:
                stage = [meta["w_swf"], meta["h_swf"]]

        # sounds: one clip per sound tag, in the chip's own SFX folder. The SWF
        # knows them only by number, so the file name says which chip it belongs
        # to and the frame it fires on, which is how it is found in the timeline.
        sfx = os.path.join(chip_dir[0], "SFX")
        shutil.rmtree(sfx, ignore_errors=True)
        os.makedirs(sfx, exist_ok=True)

        fires = {}
        for s in sounds:
            fires.setdefault(s["sound"], []).append(s["frame"])

        clips = {}
        for path in sorted(glob.glob(os.path.join(work, "snd", "*"))):
            sid = re.match(r"(-?\d+)", os.path.basename(path))
            if not sid or int(sid.group(1)) < 0:
                continue
            ext = os.path.splitext(path)[1].lower()
            if ext not in (".mp3", ".wav"):
                continue
            sound_id = int(sid.group(1))
            when = fires.get(sound_id)
            name = "chip_%04d_sfx_%s_%s%s" % (
                chip, sid.group(1), ("frame_%03d" % when[0]) if when else "unused", ext)
            shutil.copyfile(path, os.path.join(sfx, name))
            open(os.path.join(sfx, name + ".meta"), "w", encoding="utf-8").write(
                SOUND_META.format(guid=uuid.uuid4().hex))
            clips[sound_id] = "SFX/" + name

        # Several sprites can start a clip on the same frame: they are the movie's
        # alternatives for one event (chip 7 swaps four), so only one is played.
        cues, seen = [], set()
        for s in sounds:
            if s["sound"] not in clips or s["frame"] in seen:
                continue
            seen.add(s["frame"])
            cues.append({"frame": s["frame"], "clip": clips[s["sound"]]})
        skipped = [s["sound"] for s in sounds if s["sound"] not in clips]
        if skipped:
            print("   sounds with no exported clip:", sorted(set(skipped)))

        # The SWFs also carry alternates for the same event and clips the
        # timeline never starts; only the ones a cue plays belong in the folder.
        used = {os.path.basename( c["clip"] ) for c in cues}
        for path in glob.glob( os.path.join( sfx, "*" ) ):
            if os.path.basename( path ).replace( ".meta", "" ) not in used:
                os.remove( path )

        manifest = {
            "chip": chip,
            "source": "SWF/chip_%04d.swf" % chip,
            "fps": 12.0,
            "frames": names,
            "stage_px": stage,
            # sprite units of the full canvas: the frame SVGs are written at
            # N.SCALE and imported at 100 px per unit, and some frames draw
            # beyond the canvas, so the sprite's own bounds are not the stage
            "canvas_units": [stage[0] * N.SCALE / 100.0, stage[1] * N.SCALE / 100.0],
            "units_per_px": STAGE_UNITS_PER_PX,
            "sounds": cues,
            "pauses": pauses,
        }
        with open(os.path.join(out, "movie.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=1)
            f.write("\n")

        print("%d: %d frames  %d sounds (%d cues)  pauses %s"
              % (chip, len(names), len(clips), len(cues), pauses))


if __name__ == "__main__":
    main()
