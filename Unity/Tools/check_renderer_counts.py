#!/usr/bin/env python3
"""Text-level renderer audit of the chip effect prefabs.

Chip 74 loaded one of its five renderers because stray `--- !u!114 &100020`
headers had no body.  This scan reports what each prefab declares, so the
Unity-side check (ChipRendererCountCheck) can be read against it:

  * SpriteRenderer (`!u!212`) blocks with a body  -> declared renderers
  * 212 blocks no component list points at         -> orphans (never attached)
  * headers with no body                           -> the chip 74 defect
  * duplicated object ids                          -> invalid YAML

Run from the Unity project root:  python3 Tools/check_renderer_counts.py
"""

import collections
import glob
import os
import re
import sys

HEADER = re.compile(r"^--- !u!(\d+) &(-?\d+)[^\n]*$", re.M)


def analyze(path):
    text = open(path, encoding="utf-8").read()
    matches = list(HEADER.finditer(text))
    docs = {}
    empty = []
    ids = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        oid, cls = m.group(2), int(m.group(1))
        ids.append(oid)
        if text[start:end].strip():
            docs[oid] = cls
        else:
            empty.append((cls, oid))

    renderers = [oid for oid, cls in docs.items() if cls == 212]
    orphans = [oid for oid in renderers
               if not re.search(r"fileID: %s\}" % re.escape(oid), text)]
    dupes = sorted(i for i, n in collections.Counter(ids).items() if n > 1)
    return len(renderers), len(renderers) - len(orphans), orphans, empty, dupes


def main():
    paths = sorted(glob.glob("Assets/Chips/**/Chip_*_Effect.prefab", recursive=True))
    if not paths:
        sys.exit("no chip effect prefabs under Assets/Chips")

    declared = loaded = empty_total = 0
    bad = []
    for path in paths:
        n, attached, orphans, empty, dupes = analyze(path)
        declared += n
        empty_total += len(empty)
        if orphans or empty or dupes:
            bad.append((path, n, attached, orphans, empty, dupes))

    lines = ["Chip effect prefabs: %d" % len(paths),
             "SpriteRenderer blocks declared: %d" % declared,
             "Orphan renderer blocks: %d" % sum(len(b[3]) for b in bad),
             "Empty block headers: %d" % empty_total,
             "Prefabs with defects: %d" % len(bad)]
    for path, n, attached, orphans, empty, dupes in bad:
        lines.append("  %s: declared %d attached %d" % (path, n, attached)
                     + ("  orphans " + ",".join(orphans) if orphans else "")
                     + ("  empty " + ",".join("!u!%d &%s" % e for e in empty) if empty else "")
                     + ("  duplicate ids " + ",".join(dupes) if dupes else ""))
    lines.append("RESULT: " + ("OK" if not bad else "%d prefabs need a look" % len(bad)))
    report = "\n".join(lines) + "\n"
    os.makedirs("Logs", exist_ok=True)
    open("Logs/chip-renderer-counts-py.txt", "w", encoding="utf-8").write(report)
    print(report, end="")
    sys.exit(0 if not bad else 1)


if __name__ == "__main__":
    main()
