#!/usr/bin/env python3
"""Scan the Sitekick SWFs for embedded sounds, without decompiling them.

Reads the SWF container directly (FWS/CWS, tags at the root and inside every
DefineSprite) so a thousand files can be surveyed in seconds:

  * DefineSound (tag 14)     - the clip: format, rate, sample count
  * StartSound (tag 15)      - a bite of that clip, on a timeline frame
  * SoundStreamHead (18/45)  - a streamed soundtrack, which is not a clip
  * ImportAssets (57/71)     - sound symbols pulled from another SWF (sfx.swf)

A StartSound sits on a timeline, so its position is the frame of the timeline
that owns it: the root timeline for a chip's own sound, or a sprite's frame for
an inner one.  Those are the two numbers the report gives.

Usage:  python3 Tools/SwfToSvg/scan_swf_audio.py [--json out.json] path...
"""

import argparse
import json
import os
import struct
import sys
import zlib
from collections import OrderedDict

DEFINE_SOUND = 14
START_SOUND = 15
SOUND_STREAM_HEAD = (18, 45)
SOUND_STREAM_BLOCK = 19
DEFINE_SPRITE = 39
IMPORT_ASSETS = (57, 71)

FORMATS = {0: "pcm-be", 1: "adpcm", 2: "mp3", 3: "pcm-le", 4: "nellymoser16",
           5: "nellymoser8", 6: "nellymoser", 11: "speex"}
RATES = {0: 5512, 1: 11025, 2: 22050, 3: 44100}


class Reader:
    def __init__(self, data):
        self.d = data
        self.i = 0

    def byte(self):
        v = self.d[self.i]
        self.i += 1
        return v

    def u16(self):
        v = struct.unpack_from("<H", self.d, self.i)[0]
        self.i += 2
        return v

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.i)[0]
        self.i += 4
        return v

    def string(self):
        end = self.d.index(b"\0", self.i)
        v = self.d[self.i:end].decode("utf-8", "replace")
        self.i = end + 1
        return v


def swf_body(path):
    raw = open(path, "rb").read()
    if raw[:3] == b"CWS":
        data = raw[:8] + zlib.decompress(raw[8:])
    elif raw[:3] == b"FWS":
        data = raw
    else:
        raise ValueError("not a plain SWF: " + path)

    nbits = data[8] >> 3                       # RECT is bit packed
    rect_bytes = (5 + 4 * nbits + 7) // 8
    start = 8 + rect_bytes + 4                 # magic, version, length, RECT, fps, frames
    return data, start


def tags(data, start, end):
    """(code, payload, payload offset) for each tag between `start` and `end`."""
    i = start
    while i < min(end, len(data)) - 1:
        header = struct.unpack_from("<H", data, i)[0]
        i += 2
        code, length = header >> 6, header & 0x3F
        if length == 0x3F:
            length = struct.unpack_from("<I", data, i)[0]
            i += 4
        if code == 0:
            break
        yield code, data[i:i + length], i
        i += length


def read_define_sound(payload):
    r = Reader(payload)
    sid = r.u16()
    fmt = r.byte() >> 4
    rate = (payload[2] >> 2) & 3
    size = (payload[2] >> 1) & 1
    kind = payload[2] & 1
    samples = r.u32()
    return sid, {
        "format": FORMATS.get(fmt, "fmt-%d" % fmt),
        "rate": RATES.get(rate, rate),
        "bits": 16 if size else 8,
        "stereo": bool(kind),
        "samples": samples,
        "seconds": round(samples / float(RATES.get(rate, 5512)), 3),
    }


def read_start_sound(payload):
    r = Reader(payload)
    return r.u16()


def read_imports(payload, code):
    """Sound symbols pulled from another SWF (ImportAssets 57 / ImportAssets2 71)."""
    r = Reader(payload)
    url = r.string()
    if code == 71:
        r.byte()                               # reserved
        r.byte()                               # reserved
    count = struct.unpack_from("<H", payload, r.i)[0]
    r.i += 2
    names = []
    for _ in range(count):
        tag = struct.unpack_from("<H", payload, r.i)[0]
        r.i += 2
        names.append([tag, r.string()])
    return url, names


def scan(path):
    data, start = swf_body(path)
    defines, starts, streams, imports = {}, [], [], []

    def walk(body_start, body_end, owner, depth):
        frame = 1
        for code, payload, off in tags(data, body_start, body_end):
            if code == 1:                                    # ShowFrame
                frame += 1
            elif code == DEFINE_SOUND:
                sid, info = read_define_sound(payload)
                defines.setdefault(sid, info)
            elif code == START_SOUND:
                starts.append({"owner": owner, "frame": frame,
                               "sound": read_start_sound(payload)})
            elif code in SOUND_STREAM_HEAD:
                fmt = payload[1] >> 4 if len(payload) > 1 else -1
                samples = struct.unpack_from("<I", payload, len(payload) - 4)[0] \
                    if len(payload) >= 8 else 0
                streams.append({"owner": owner, "frame": frame,
                                "format": FORMATS.get(fmt, str(fmt)), "samples": samples})
            elif code == DEFINE_SPRITE and depth < 8:
                r = Reader(payload)
                sid = r.u16()
                r.u16()                                      # declared frame count
                walk(off + 4, off + len(payload), "sprite %d" % sid, depth + 1)
            elif code in IMPORT_ASSETS:
                try:
                    url, names = read_imports(payload, code)
                    imports.append({"url": url, "symbols": names})
                except Exception as exc:
                    imports.append({"url": "?", "symbols": [], "error": str(exc)})

    walk(start, len(data), "root", 0)
    return {
        "path": path,
        "defines": defines,
        "starts": starts,
        "streams": streams,
        "imports": imports,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--json")
    args = ap.parse_args()

    files = []
    for p in args.paths:
        if os.path.isdir(p):
            for dirpath, _, names in os.walk(p):
                files.extend(os.path.join(dirpath, n) for n in names if n.lower().endswith(".swf"))
        else:
            files.append(p)

    results = []
    for path in sorted(files):
        try:
            r = scan(path)
        except Exception as exc:                      # a broken file must not stop the survey
            results.append({"path": path, "error": str(exc)})
            continue
        results.append(r)

    if args.json:
        json.dump(results, open(args.json, "w"), indent=1)

    noisy = [r for r in results if r.get("starts")]
    print("%d SWFs, %d with StartSound, %d DefineSound total, %d streamed"
          % (len(results), len(noisy),
             sum(len(r.get("defines", {})) for r in results),
             sum(1 for r in results if r.get("streams"))))
    if args.json:
        print("wrote", args.json)


if __name__ == "__main__":
    main()
