#!/usr/bin/env python3
"""Export the sounds embedded in the Sitekick SWFs and write the audio map.

Sources, in the order they matter:

  SWF/chip_0007..0016.swf   the ten standalone chip movies; their clips are
                            already inside each chip's Movie/ folder
  Source/Misc. SWF/sfx.swf  the shared effect-sound library (57 clips)
  SWF/*library*.swf         symbol libraries; the scan finds no sound tags in them

sfx.swf lives outside the Unity project (the assets repo keeps it under Source/),
and no SWF here imports from it, so its clips are copied into Assets/Audio/Sfx as
a standalone library rather than being referenced by a chip.

Usage:  python3 Tools/SwfToSvg/export_sfx.py [--sfx PATH]
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

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
FFDEC = ["flatpak", "run", "--command=ffdec.sh", "com.jpexs.decompiler.flash"]
# scratch inside the project: Temp/ is gitignored, so a run leaves nothing
# behind outside the Unity folder
TMP = os.path.join(ROOT, "Temp", "swftosvg", "sfx")
DEST = os.path.join(ROOT, "Assets/Audio/Sfx")
MAP_MD = os.path.join(ROOT, "Logs/audio-map.md")
MAP_JSON = os.path.join(ROOT, "Logs/audio-map.json")
DEFAULT_SFX = "/var/home/nicholas/Documents/GitHub/Art/Source/Misc. SWF/sfx.swf"

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


def read_meta(path):
    """guid of an existing asset, so re-exporting does not orphan references."""
    if not os.path.exists(path + ".meta"):
        return uuid.uuid4().hex
    m = re.search(r"^guid: (\w+)$", open(path + ".meta", encoding="utf-8").read(), re.M)
    return m.group(1) if m else uuid.uuid4().hex


def export_sfx(sfx):
    shutil.rmtree(TMP, ignore_errors=True)
    os.makedirs(TMP, exist_ok=True)
    subprocess.run(FFDEC + ["-format", "sound:wav", "-export", "sound", TMP, sfx],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    os.makedirs(DEST, exist_ok=True)
    clips = {}
    for src in sorted(glob.glob(os.path.join(TMP, "*"))):
        name = os.path.basename(src)
        sid = re.match(r"(-?\d+)", name)
        if not sid or int(sid.group(1)) < 0:
            continue
        dst = os.path.join(DEST, name)
        shutil.copyfile(src, dst)
        open(dst + ".meta", "w", encoding="utf-8").write(
            SOUND_META.format(guid=read_meta(dst)))
        clips[int(sid.group(1))] = name
    return clips


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sfx", default=DEFAULT_SFX)
    args = ap.parse_args()

    scan = {os.path.basename(r["path"]): r for r in json.load(open(os.path.join(ROOT, "Logs/swf-audio.json")))}
    sfx_scan = json.load(open(os.path.join(ROOT, "Logs/sfx-audio.json")))[0]
    clips = export_sfx(args.sfx) if os.path.exists(args.sfx) else {}

    lines = ["# Sitekick audio map", "",
             "Which SWFs carry sounds, and where each sound starts.", "",
             "## Summary", ""]
    # a SoundStreamHead with no samples is an empty stub, which most of these are
    def heard(rows):
        heads = [s for r in rows for s in r["streams"]]
        return sum(1 for s in heads if s["samples"] > 0)

    lines.append("| Source | Clips (DefineSound) | StartSound events | Streams with audio |")
    lines.append("| --- | --- | --- | --- |")

    chips = sorted(n for n in scan if n.startswith("chip_"))
    libs = [n for n in scan if "library" in n]
    lines.append("| chip_0007..0016.swf | %d | %d | %d |"
                 % (sum(len(scan[n]["defines"]) for n in chips),
                    sum(len(scan[n]["starts"]) for n in chips),
                    heard(scan[n] for n in chips)))
    lines.append("| chipslibrary*/effectlibrary* | %d | %d | %d |"
                 % (sum(len(scan[n]["defines"]) for n in libs),
                    sum(len(scan[n]["starts"]) for n in libs),
                    heard(scan[n] for n in libs)))
    lines.append("| sitekick.swf | %d | %d | %d |"
                 % (len(scan["sitekick.swf"]["defines"]), len(scan["sitekick.swf"]["starts"]),
                    heard([scan["sitekick.swf"]])))
    lines.append("| sfx.swf | %d | %d | %d |"
                 % (len(sfx_scan["defines"]), len(sfx_scan["starts"]), heard([sfx_scan])))
    lines.append("")
    lines.append("A clip is a DefineSound; an event is a StartSound placing one on a frame.")
    lines.append("The chip movies are the only sources whose sounds are actually played here")
    lines.append("(`SoundStreamHead` tags elsewhere are the empty stubs Flash leaves behind).")
    lines.append("")

    lines.append("## Chips with audio")
    lines.append("")
    lines.append("Only chips 7-16 exist as individual SWFs here; the symbol libraries hold no")
    lines.append("sound tags, so no other chip's audio can come out of this repo.")
    lines.append("")
    lines.append("| Chip | Frames | Clips | Events | Where each sound starts |")
    lines.append("| --- | --- | --- | --- | --- |")
    per_chip = {}
    for name in chips:
        chip = int(re.search(r"(\d+)", name).group(1))
        r = scan[name]
        # what the rebuilt movie already knows: its length, and the root frame each
        # clip was resolved to when the prefab was built
        folders = glob.glob(os.path.join(ROOT, "Assets/Chips/*/Chip_%04d" % chip))
        manifest = os.path.join(folders[0], "Movie/movie.json") if folders else None
        frames, root_of = None, {}
        if manifest and os.path.exists(manifest):
            data = json.load(open(manifest))
            frames = len(data["frames"])
            for cue in data.get("sounds", []):
                root_of[cue["clip"].rsplit(".", 1)[0]] = cue["frame"]

        events = []
        for s in r["starts"]:
            where = ("root frame %d" % s["frame"] if s["owner"] == "root"
                     else "sprite %s frame %d" % (s["owner"].split()[-1], s["frame"]))
            resolved = root_of.get("sound_%d" % s["sound"])
            if resolved is not None:
                where += " → root %d" % resolved
            events.append(where)

        per_chip[chip] = {"clips": len(r["defines"]), "events": events,
                          "defines": r["defines"], "frames": frames}
        lines.append("| %d | %s | %d | %d | %s |" % (
            chip, frames if frames else "—", len(r["defines"]), len(r["starts"]),
            "<br>".join(events) if events else "— silent —"))
    lines.append("")

    lines.append("## sfx.swf")
    lines.append("")
    lines.append("Exported to `Assets/Audio/Sfx/` (%d clips). Its own timeline walks them one" % len(clips))
    lines.append("sound every few frames, which is what the StartSound events below are.")
    lines.append("")
    lines.append("Its ids 1-19 are library entries the timeline never starts; the rest have a")
    lines.append("frame on that timeline.")
    lines.append("")
    lines.append("| Id | Clip | Format | Seconds | Starts at frame |")
    lines.append("| --- | --- | --- | --- | --- |")
    starts = {}
    for s in sfx_scan["starts"]:
        starts.setdefault(s["sound"], []).append(s["frame"])
    for key in sorted(sfx_scan["defines"], key=int):
        sid = int(key)
        info = sfx_scan["defines"][key]
        frames = ", ".join(str(f) for f in starts.get(sid, [])) or "—"
        lines.append("| %d | `%s` | %s | %s | %s |" % (
            sid, clips.get(sid, "?"), info["format"], info["seconds"], frames))
    lines.append("")

    open(MAP_MD, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    json.dump({"chips": per_chip, "sfx": {"defines": sfx_scan["defines"],
                                          "starts": sfx_scan["starts"], "clips": clips}},
              open(MAP_JSON, "w"), indent=1)

    print("sfx clips exported: %d -> %s" % (len(clips), DEST))
    for chip in sorted(per_chip):
        print("chip %2d: %d clips, %d events" % (chip, per_chip[chip]["clips"],
                                                 len(per_chip[chip]["events"])))
    print("map ->", MAP_MD)


if __name__ == "__main__":
    main()
