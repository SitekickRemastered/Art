#!/usr/bin/env python3
"""Write a copy of a SWF with the root timeline's DoAction tags removed.

The chip movies are built to stop on frame 1 and wait for the game to call
play(), so a plain player (Ruffle included) shows frame 1 and nothing else. To
watch the animation the way the game plays it, this drops the root timeline's
actions and leaves everything else — sprites, sounds, art — untouched. It writes
FWS (uncompressed) and is only meant for side-by-side rendering tests.

Usage:  python3 Tools/SwfToSvg/strip_actions.py in.swf out.swf
"""

import struct
import sys
import zlib

DO_ACTION = 12
END = 0


def body(path):
    raw = open(path, "rb").read()
    if raw[:3] == b"CWS":
        return raw[:8] + zlib.decompress(raw[8:])
    if raw[:3] == b"FWS":
        return raw
    raise SystemExit("uncompressed or zlib SWF expected: " + path)


def header_end(data):
    nbits = data[8] >> 3
    return 8 + (5 + 4 * nbits + 7) // 8 + 4


def rewrite(data):
    """Root tags, minus DoAction, plus an End tag."""
    start = header_end(data)
    out = bytearray()
    i = start
    removed = 0
    while i < len(data) - 1:
        at = i
        h = struct.unpack_from("<H", data, i)[0]
        i += 2
        code, length = h >> 6, h & 0x3F
        if length == 0x3F:
            length = struct.unpack_from("<I", data, i)[0]
            i += 4
        if code == END:
            break
        if code == DO_ACTION:
            removed += 1
        else:
            out += data[at:i + length]
        i += length
    return out, removed


def main():
    src, dst = sys.argv[1], sys.argv[2]
    data = body(src)
    tags, removed = rewrite(data)
    start = header_end(data)
    head = bytearray(data[:start])
    payload = bytes(tags) + b"\x00\x00"
    head[0:8] = b"FWS" + head[3:4] + struct.pack("<I", start + len(payload))
    open(dst, "wb").write(bytes(head) + payload)
    print("%s -> %s, removed %d root DoAction tags" % (src, dst, removed))


if __name__ == "__main__":
    main()
