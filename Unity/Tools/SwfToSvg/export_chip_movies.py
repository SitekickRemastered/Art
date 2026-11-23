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

The export ends at the root's idle loop rather than at the end of the timeline:
every chip but 9, 11, 12, 13 and 16 jumps back to a labelled block from its
display section, and the frames after that jump are the retract, which nothing
in the game reaches (see `hover_loop.py`).  Chip 12 resets with a literal jump;
chip 13's root stops on `display` while its fish keeps swimming, so
`patch_chip13.py` holds the root for one fish cycle and those frames loop.  The
loop range goes into `movie.json` for the player to repeat.  9 and 11 play their
sequence once and hold the last frame; chip 16 does the same, because the
snowman's hat only arrives on the last frames (see `patch_chip16.py`).

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
# scratch stays inside the project (Temp/ is gitignored), so a run leaves
# nothing behind outside it
TMP = os.path.join(ROOT, "Temp", "swftosvg")
FFDEC = ["flatpak", "run", "--command=ffdec.sh", "com.jpexs.decompiler.flash"]

sys.path.insert(0, HERE)
import flatten_svg as flatten
import normalize as N
import patch_chip7 as patch7
import patch_chip8_tools as patch8
import patch_chip9 as patch9
import patch_chip10 as patch10
import patch_chip11 as patch11
import patch_chip13 as patch13
import patch_chip14 as patch14
import patch_chip15 as patch15
import patch_chip16 as patch16
import patch_stopped_clips as patch_stop
import hover_loop

TEMPLATE_SVG_META = os.path.join(
    ROOT, "Assets/Chips/0101-0200/Chip_0177/Sprites/chip_0177_back.svg.meta")

# The stage is the Sitekick's face: 1.100 prefab units across 375 stage px.
STAGE_UNITS_PER_PX = 0.0029333

# Root frames the movie never shows.  Chip 8's root timeline runs ten frames
# past the end of the effect: the script on 61 calls `sk.gotoAndPlay("fromEffect")`
# and `skMain.effectHolder.removeMovieClip()`, so 62-71 are a collapsed dot the
# player removes before it can draw.  Only the timeline play (which no script
# stops) keeps them, so the export ends where the effect does.
LAST_VISIBLE_FRAME = {8: 61,
                      # the hole has closed by 132 and 132..152 are one pose
                      9: 132,
                      11: 35}   # the monster is fully open on 34-35; 36+ is its retract

# Chips with no movie in `SWF/`: those are the site's effect movies, and these
# only exist in the extracted chip library.
LIBRARY_SWF = {36: os.path.join("..", "Source", "Chip Libraries", "Old Chips",
                                "Effects", "chip_0036.swf")}

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
        if not os.path.exists(swf) and chip in LIBRARY_SWF:
            swf = os.path.join(ROOT, LIBRARY_SWF[chip])
        if not os.path.exists(swf):
            print(chip, "MISSING", swf)
            continue

        work = os.path.join(TMP, "%04d" % chip)
        shutil.rmtree(work, ignore_errors=True)
        for sub in ("svg", "png", "snd", "scr", "xml"):
            os.makedirs(os.path.join(work, sub), exist_ok=True)

        # sound cues are read from the movie as it ships on the site: the patch
        # passes prune characters nothing reaches, and the walk that turns a
        # sound's placement chain into a root frame needs the original graph
        source_xml = os.path.join(work, "xml", "source.xml")
        if not os.path.exists(source_xml):
            run(*FFDEC, "-swf2xml", swf, source_xml)

        if chip == 8:
            # chip 8's hands take one tool each from the server record, which
            # only the ActionScript ever applies; the timeline has all six on
            # the clip's first frame, so the assignment is authored in first
            swf = patch8.patched(swf, work)
        elif chip == 7:
            # chip 7's rings, score wings and antenna are placed by frame
            # scripts too; that pass also runs the stopped-clip freeze
            swf = patch7.patched(swf, work)
        elif chip == 9:
            # chip 9's arm, hole side, right side, trim and hole are all parked
            # or jumped by frame scripts; that pass runs the freeze as well
            swf = patch9.patched(swf, work)
        elif chip == 10:
            # chip 10's bubble is parked on the effect's first frame and squints
            # at root 9; that pass runs the freeze as well
            swf = patch10.patched(swf, work)
        elif chip == 11:
            # chip 11's monster is parked on its first frame until root 14 sends
            # it through the transformation, then holds its own stop; that pass
            # runs the freeze as well
            swf = patch11.patched(swf, work)
        elif chip == 13:
            # chip 13's root stops on 11 while the fish keeps swimming; that pass
            # holds the root for one fish cycle so those frames can loop
            swf = patch13.patched(swf, work, source_xml)
        elif chip == 14:
            # the site starts at display (33), parks the spider at 21 and jumps
            # the root to hover (3); that pass bakes the parked pose
            swf = patch14.patched(swf, work, source_xml)
        elif chip == 15:
            # the site starts at display (3), parks soundwaveSK on transformed
            # (17) and jumps the root to hover (4); that pass bakes the pose
            swf = patch15.patched(swf, work, source_xml)
        elif chip == 16:
            # the site's display call has no root label here, so Flash leaves the
            # root on 1 and `body` parks on display (39); FFDec walking `body`
            # from 1 in lockstep reaches that same pose on the last root frame,
            # so nothing is baked -- the pass only freezes the stopped clips and
            # the export plays the whole 1..39 timeline
            swf = patch16.patched(swf, work)
        else:
            # clips that stop themselves and no script restarts are frozen at
            # their parked frame instead of playing out and looping
            swf = patch_stop.patched(swf, work)

        run(*FFDEC, "-format", "frame:svg", "-export", "frame", os.path.join(work, "svg"), swf)
        run(*FFDEC, "-format", "frame:png", "-export", "frame", os.path.join(work, "png"), swf)
        run(*FFDEC, "-export", "sound", os.path.join(work, "snd"), swf)
        run(*FFDEC, "-export", "script", os.path.join(work, "scr"), swf)
        run(*FFDEC, "-swf2xml", swf, os.path.join(work, "xml", "lib.xml"))

        sounds, _, frames = timeline(source_xml)
        # The idle section is a label the root jumps back to; everything after
        # that jump is the retract, which only an outside caller can reach (see
        # hover_loop.py).  The export ends at the loop and the player repeats it.
        # 14 and 15 used to drop their cues because the parked pose skipped them;
        # with the park off the clips play, so both cues fire again
        drop_sounds = False
        if chip == 13:
            # the stop is authored as the held root, not a backward jump
            loop = patch13.loop()
            cue_limit = patch13.HOLD_AT
        elif chip == 14:
            # the display path parks the spider before its two internal cues
            loop = patch14.loop()
            cue_limit = None
        elif chip == 15:
            # both cues sit behind the park (sprite 33 frame 2, root 32)
            loop = patch15.loop()
            cue_limit = None
        elif chip == 16:
            # no cut here, and no loop: the hat growing in IS the chip's
            # animation and the finished snowman is the last frame.  The root's
            # `gotoAndStop("hover")` on 21 marks a hover block that starts
            # before the hat is placed (body places it on 36), so looping it
            # replays a hatless snowman for ever and the export never reaches
            # the pose the chip is for.  Play 1..39 once and hold the last
            # frame, which the player does when `loop` is absent.
            loop = None
            cue_limit = None
        elif chip in (37, 53):
            # both are pulled out of the effect library by extract_effect.py: an
            # AS3 class whose animation is the symbol's own timeline, with the
            # behaviour (click, hover) in the class, which a movie cannot run.
            # Chip 53's class loops `start`..`endStart` while it is worn, so that
            # block is its movie.  Chip 37 has no idle motion at all -- the jar
            # fills (2..31) and empties (33..75) only when clicked -- so it plays
            # the whole cycle and loops where root 75 returns to `start`.
            loop = (1, 54) if chip == 53 else (1, 75)
            cue_limit = None
        elif chip == 36:
            # the movie waits on frame 1 for a click on its mask, and its swords
            # then start `flipRight`/`sliceLeft`, each jumping back to `drawn`
            # (14), with the mask sheathing them back to 1.  Nothing in the
            # gallery can hit those buttons, and every clip is a single frame,
            # so the only motion in the whole movie is that root sequence: the
            # export plays all of it -- draw, both attacks, sheath -- and loops
            # on the sheathed pose at 1, where root 52 jumps
            loop = (1, 51)
            cue_limit = None
        elif chip == 9:
            # the punch sequence is played once, all the way through: the hole
            # opens, the hand and the antenna come out, both go away and the
            # hole closes; the player holds the last frame instead of looping
            loop = None
            cue_limit = None
        elif chip == 11:
            # plays once and ends with the monster fully open, which it holds
            loop = None
            cue_limit = None
        else:
            loop = hover_loop.find(root_tags(source_xml), os.path.join(work, "scr", "scripts"))
            cue_limit = None
        pauses = pause_frames(os.path.join(work, "scr", "scripts"))
        if chip == 36:
            # its stop()s wait for the player to click the mask or a sword; the
            # export plays the whole cycle by itself, so a pause would hold it
            # on the drawn pose for good
            pauses = []

        chip_dir = glob.glob(os.path.join(ROOT, "Assets/Chips", "*", "Chip_%04d" % chip))
        if not chip_dir:
            print(chip, "no chip folder"); continue
        out = os.path.join(chip_dir[0], "Movie")
        # every frame keeps its guid across a re-export: the chip prefabs point
        # at them, so read the old metas before the folder is cleared
        old_guids = {}
        for path in glob.glob(os.path.join(out, "frame_*.svg.meta")):
            found = re.search(r"^guid: (.*)$", open(path, encoding="utf-8").read(), re.M)
            if found:
                old_guids[os.path.basename(path)] = found.group(1)
        # the manifest's importer settings are Unity's, not ours: the folder is
        # cleared for the re-export, so carry them across like the frame guids
        manifest_meta = None
        manifest_meta_path = os.path.join(out, "movie.json.meta")
        if os.path.exists(manifest_meta_path):
            manifest_meta = open(manifest_meta_path, encoding="utf-8").read()
        shutil.rmtree(out, ignore_errors=True)
        os.makedirs(out, exist_ok=True)

        # frames: normalise each stage render, keep the canvas numbers
        frame_files = sorted(glob.glob(os.path.join(work, "svg", "*.svg")),
                             key=lambda p: int(re.search(r"(\d+)\.svg$", p).group(1)))
        keep = LAST_VISIBLE_FRAME.get(chip)
        if keep:
            frame_files = frame_files[:keep]
        if loop:
            frame_files = frame_files[:loop[1]]
        # cues and pauses past the cut belong to the retract the movie never plays
        # (chip 13's loop frames hold the root, so nothing new fires in them)
        last = len(frame_files)
        keep = min(last, cue_limit) if cue_limit else last
        sounds = [s for s in sounds if s["frame"] <= keep]
        if drop_sounds:
            # both cues live in the spider's skipped intro (frames 2 and 14)
            sounds = []
        pauses = [p for p in pauses if p <= keep]
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
            # read the old guid before opening the meta for writing: opening it
            # truncates the file, and svg_meta would then hand back a new guid,
            # which orphans every prefab that points at this frame
            meta_text = svg_meta(name + "Sprite", meta_path=dst + ".meta")
            keep = old_guids.get(name + ".svg.meta")
            if keep:
                meta_text = re.sub(r"^guid: .*$", "guid: " + keep, meta_text,
                                   count=1, flags=re.M)
            open(dst + ".meta", "w", encoding="utf-8").write(meta_text)
            names.append(name + ".svg")
            if stage is None:
                stage = [meta["w_swf"], meta["h_swf"]]

        # sounds: one clip per sound tag, in the chip's own SFX folder. The SWF
        # knows them only by number, so the file name says which chip it belongs
        # to and the frame it fires on, which is how it is found in the timeline.
        sfx = os.path.join(chip_dir[0], "SFX")
        # keyed by sound id, not file name: the name carries the frame the clip
        # fires on, which a re-export can shift
        sfx_guids = {}
        for path in glob.glob(os.path.join(sfx, "*.meta")):
            found = re.search(r"^guid: (.*)$", open(path, encoding="utf-8").read(), re.M)
            sid = re.search(r"_sfx_(-?\d+)_", os.path.basename(path))
            key = sid.group(1) if sid else os.path.basename(path)[:-5]
            if found:
                sfx_guids[key] = found.group(1)
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
                SOUND_META.format(guid=sfx_guids.get(sid.group(1), uuid.uuid4().hex)))
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
            "source": os.path.relpath(swf, ROOT).replace(os.sep, "/"),
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
        if loop:
            # 1-based, inclusive: the player replays these instead of finishing
            manifest["loop"] = list(loop)
        with open(os.path.join(out, "movie.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=1)
            f.write("\n")
        if manifest_meta:
            with open(manifest_meta_path, "w", encoding="utf-8") as f:
                f.write(manifest_meta)

        print("%d: %d frames  %d sounds (%d cues)  pauses %s  loop %s"
              % (chip, len(names), len(clips), len(cues), pauses,
                 ("%d..%d" % tuple(loop)) if loop else "-"))


if __name__ == "__main__":
    main()
