#!/usr/bin/env python3
"""Build a standalone sitekick.swf that colours itself, for the Flash reference.

sitekick.swf has no colour code of its own: its 48 painted clips call
`paint(this[, tone])`, and `paint` is defined by the movie that loads it
(Tuesday.swf) as

    ra/ga/ba = rvalue/gvalue/bvalue          (0..100, a pure multiply)
    "shadow" -20, "shadow2" -30, "shadow3" -40

`Color.setTransform` REPLACES the colour transform the parent placed the clip
with, which is why the 50 %/70 % greys FFDec bakes into the head's shadow fills
disappear at runtime.

This script rewrites every `paint(this, ...)` call with the transform it would
have applied, so Ruffle can render the body at a known colour and the Unity
build can be diffed against it:

    Tools/SwfToSvg/make_sitekick_probe.py ffcc00
    # then serve the project root and open
    #   Tools/SwfToSvg/sitekick_probe.html?swf=/Temp/skpatch/sitekick_probe.swf

    # a bigger render to sample colours from
    #   ...?swf=/Temp/skpatch/sitekick_probe.swf&w=1125&h=900

The reference values at ffcc00 (matching the sitekick's own palette) are
#FFCC00 base, #CC7A00 shadow (tone 20) and #B26600 shadow2 (tone 30).
"""

import glob
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SWF = os.path.join(ROOT, "SWF", "sitekick.swf")
TMP = os.path.join(ROOT, "Temp", "skpatch")
FFDEC = ["flatpak", "run", "--command=ffdec.sh", "com.jpexs.decompiler.flash",
         "-onerror", "ignore"]

TONES = {"shadow": 20, "shadow2": 30, "shadow3": 40}


def main(hex_colour):
    rgb = [int(hex_colour[i:i + 2], 16) for i in (0, 2, 4)]
    # 0..255 -> the 0..100 multipliers the SWF uses
    mul = [round(c * 100.0 / 255.0) for c in rgb]

    shutil.rmtree(TMP, ignore_errors=True)
    os.makedirs(TMP)
    # FFDec creates the `scripts` tree inside the folder it is given, and
    # -importScript wants that same parent folder back
    subprocess.run(FFDEC + ["-export", "script", TMP, SWF],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    scripts = os.path.join(TMP, "scripts")

    patched = 0
    for path in glob.glob(os.path.join(scripts, "*", "frame_1", "DoAction.as")):
        text = open(path, encoding="utf-8", errors="replace").read()
        m = re.search(r'paint\(this(?:,\s*"(\w+)")?\)\s*;', text)
        if not m:
            continue
        drop = TONES.get(m.group(1) or "", 0)
        code = ("_c=new Color(this);_c.setTransform({ra:%d,ga:%d,ba:%d,aa:100,"
                "rb:0,gb:0,bb:0,ab:0});" % (mul[0] - drop, mul[1] - drop, mul[2] - drop))
        with open(path, "w", encoding="utf-8") as f:
            f.write(code + "\r\n")
        patched += 1

    probe = os.path.join(TMP, "sitekick_probe.swf")
    subprocess.run(FFDEC + ["-importScript", SWF, probe, TMP],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("patched %d painted clips to %s, wrote %s" % (patched, hex_colour, probe))


if __name__ == "__main__":
    main((sys.argv[1] if len(sys.argv) > 1 else "ffcc00").lstrip("#").lower())
