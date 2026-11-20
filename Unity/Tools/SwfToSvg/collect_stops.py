#!/usr/bin/env python3
"""Map every stop() in the decompiled chip scripts to its chip, owner and frame.

The chip SWFs hand out their pauses in two places: the main timeline calls
stop() to hold the movie for the game, and sub-sprites call stop() on their own
timelines (a held flap, a held pose).  This walks both and, for a sprite, also
works out when the sprite is on screen, so a sprite's pause can be read as the
root frame a viewer would see it on.

Output: Logs/chip-stops.md plus a per-chip summary on stdout.

Usage:  python3 Tools/SwfToSvg/collect_stops.py
"""

import glob
import os
import re
import sys

from lxml import etree

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
OUT = os.path.join(ROOT, "Logs", "chip-stops.md")
BASES = [os.path.join(os.environ["HOME"], "sitekick-movies")]

STOP = re.compile(r"\bstop\s*\(\s*\)\s*;")


def chips():
    found = []
    for base in BASES:
        for scripts in sorted(glob.glob(os.path.join(base, "*", "scr", "scripts"))):
            chip_dir = os.path.dirname(os.path.dirname(scripts))   # <chip>/scr/scripts -> <chip>
            chip = int(os.path.basename(chip_dir))
            found.append((chip, scripts, os.path.join(chip_dir, "xml", "lib.xml")))
    return found


def sprite_frames(tags):
    """spriteId -> frame count, from the SWF's own tags."""
    out = {}
    for item in tags:
        if item.get("type") != "DefineSpriteTag":
            continue
        frames = sum(1 for sub in item.findall("subTags/item") if sub.get("type") == "ShowFrameTag")
        out[int(item.get("spriteId"))] = frames
    return out


def placement(tags):
    """Who places what, and on which frame; plus the root frame each one starts on."""
    owner = {}
    for item in tags:
        if item.get("type") == "DefineSpriteTag":
            sid = int(item.get("spriteId"))
            for n, frame in enumerate(frames_of(item)):
                for sub in frame:
                    if sub.get("type") == "PlaceObject2Tag" and sub.get("characterId"):
                        owner.setdefault(int(sub.get("characterId")), (sid, n + 1))
    placed_at, frame = {}, 1
    for item in tags:
        if item.get("type") == "ShowFrameTag":
            frame += 1
        elif item.get("type") == "PlaceObject2Tag" and item.get("characterId"):
            placed_at.setdefault(int(item.get("characterId")), frame)
    return owner, placed_at


def frames_of(sprite_item):
    frames, current = [], []
    for sub in sprite_item.findall("subTags/item"):
        if sub.get("type") == "ShowFrameTag":
            frames.append(current)
            current = []
        else:
            current.append(sub)
    frames.append(current)
    return frames


def root_frame_of(sid, owner, placed_at):
    """Root frame on which a sprite starts playing, following its placement chain."""
    offset, node, seen = 0, sid, set()
    while node in owner and node not in seen:
        seen.add(node)
        parent, at = owner[node]
        offset += at - 1
        if parent is None:
            break
        node = parent
    start = placed_at.get(node)
    return None if start is None else start + offset


def waits_for(body):
    """What the script does while it is stopped, as far as the movie's own code says."""
    if "sendAndLoad" in body or "LoadVars" in body:
        return "server data"
    if "onRelease" in body or "onPress" in body:
        return "a click"
    if "_global.effect =" in body or "_global.fixit =" in body:
        return "the game to start it"
    if "onEnterFrame" in body:
        return "a value it polls"
    if "removeMovieClip" in body:
        return "nothing (teardown)"
    if "gotoAndPlay" in body:
        return "a part plays on"
    if "play()" in body:
        return "itself, next frame"
    return "nothing (plain hold)"


def stops_in(path):
    """(line number, line text, conditional) for every stop() in a script."""
    hits = []
    text = open(path, encoding="utf-8", errors="ignore").read()
    lines = text.splitlines()
    guard = None
    for n, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("if") or stripped.startswith("} else"):
            guard = n
        if stripped.startswith("}"):
            guard = None
        for _ in STOP.finditer(line):
            after = ""
            for follow in lines[n:]:
                if follow.strip():
                    after = follow.strip()
                    break
            hits.append((n, stripped, guard is not None, after))
    return hits


def main():
    rows = []
    for chip, scripts, xml in chips():
        owner, placed_at, sprite_frames_map = {}, {}, {}
        if os.path.exists(xml):
            tags = list(etree.parse(xml).getroot().find("tags"))
            owner, placed_at = placement(tags)
            sprite_frames_map = sprite_frames(tags)

        for path in sorted(glob.glob(os.path.join(scripts, "**", "*.as"), recursive=True)):
            rel = os.path.relpath(path, scripts)
            parts = rel.split(os.sep)

            sprite, button = None, None
            for part in parts:
                if part.startswith("DefineSprite_"):
                    sprite = int(re.search(r"(\d+)", part).group(1))
                elif part.startswith("DefineButton2_"):
                    button = int(re.search(r"(\d+)", part).group(1))

            frames_in_path = [int(m.group(1)) for m in (re.search(r"frame_(\d+)", p) for p in parts) if m]
            frame = frames_in_path[-1] if frames_in_path else None

            if button is not None:
                at_root = hold_at = None          # a click, not a timeline frame
            elif sprite is None:
                at_root = hold_at = frame
            else:
                at_root = root_frame_of(sprite, owner, placed_at)
                hold_at = None if at_root is None or frame is None else at_root + frame - 1

            body = open(path, encoding="utf-8", errors="ignore").read()
            for line_no, line, conditional, after in stops_in(path):
                rows.append({
                    "waits": waits_for(body),
                    "after": after.replace("|", "\\|")[:60],
                    "chip": chip,
                    "sprite": sprite,
                    "button": button,
                    "frame": frame,
                    "root": at_root,
                    "hold": hold_at,
                    "frames": None if sprite is None else sprite_frames_map.get(sprite),
                    "placed": sprite is None or sprite in placed_at or sprite in owner,
                    "line": line,
                    "file": rel.replace(os.sep, "/"),
                    "conditional": conditional,
                })

    lines = ["# Chip stop() map", "",
             "Every `stop();` in the decompiled scripts of chips 7-16, with the frame it",
             "holds and — for a sub-sprite — the root frame it is visible on.", "",
             "`Waits for` reads the script around the stop: the chip movies are from the",
             "web game, so most root pauses are the chip asking the server for its saved",
             "score (or a mode flag) before playing on, and none of those have anything to",
             "wait for in Unity. Frame 1 is the movie's start pose, waiting for the game to",
             "call play(); a few later ones freeze the root while a limb plays on. The",
             "sprite stops are the inner poses staying put.", ""]

    by_chip = {}
    for r in rows:
        by_chip.setdefault(r["chip"], []).append(r)

    lines.append("| Chip | Root stops | Sprite stops | Sprites involved |")
    lines.append("| --- | --- | --- | --- |")
    for chip in sorted(by_chip):
        rs = by_chip[chip]
        root = [r for r in rs if r["sprite"] is None]
        spi = [r for r in rs if r["sprite"] is not None]
        sprites = sorted({r["sprite"] for r in spi})
        lines.append("| %d | %s | %d | %s |" % (
            chip,
            ", ".join(str(r["frame"]) for r in sorted(root, key=lambda r: r["frame"])) or "—",
            len(spi),
            ", ".join(str(s) for s in sprites[:8]) + (" …" if len(sprites) > 8 else "") or "—"))
    lines.append("")

    for chip in sorted(by_chip):
        rs = sorted(by_chip[chip], key=lambda r: (r["sprite"] is not None, r["sprite"] or 0, r["frame"] or 0))
        lines.append("## Chip %d" % chip)
        lines.append("")
        lines.append("| Owner | Frame | First shown on root | Holds at root frame | Waits for | Then | Sprite frames | Conditional | Script |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for r in rs:
            owner_name = ("root" if r["sprite"] is None and r["button"] is None
                          else "sprite %d" % r["sprite"] if r["sprite"] is not None
                          else "button %d" % r["button"])
            lines.append("| %s | %s | %s | %s | %s | `%s` | %s | %s | `%s` |" % (
                owner_name,
                r["frame"] if r["frame"] is not None else "—",
                r["root"] if r["root"] is not None else ("click" if r["button"] is not None else "not placed"),
                r["hold"] if r["hold"] is not None else ("click" if r["button"] is not None else "—"),
                r["waits"],
                r["after"] or "—",
                r["frames"] if r["frames"] is not None else "—",
                "yes" if r["conditional"] else "no",
                r["file"]))
        lines.append("")

    open(OUT, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    total = len(rows)
    for chip in sorted(by_chip):
        rs = by_chip[chip]
        root = sorted(r["frame"] or 0 for r in rs if r["sprite"] is None and r["button"] is None)
        sprites = sorted({r["sprite"] for r in rs if r["sprite"] is not None})
        print("%d: root %s  sprite stops %d across %d sprites"
              % (chip, root or "—", len(rs) - len(root), len(sprites)))
    print("total %d stops -> %s" % (total, OUT))


if __name__ == "__main__":
    main()
