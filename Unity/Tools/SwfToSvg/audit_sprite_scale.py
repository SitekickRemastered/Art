#!/usr/bin/env python3
"""Check that a spawned particle's sprite renders at the size its SWF art has.

A particle sprite is the one place in an effect where nothing compensates for a
wrong import scale: the prefab node sits at scale 1, so the only thing that sets
the world size is the sprite's own `svgPixelsPerUnit`.  Every other renderer in
the project can be off and still look right because its node carries a matching
scale, which is why this audit looks at particles only.

The intended size comes from the export, not from a constant: `size_px` in
`Sprites/chip_XXXX_effect.json` is the art's own SWF size in exported pixels
(`SCALE` exported px per SWF px), and one SWF px is `U` world units.  The
rendered size is the SVG viewBox divided by the sprite's pixels-per-unit times
the node scale.  They agree when

    ppu = viewBoxWidth * PPU / size_px

which for an untouched export (size_px == viewBox * SCALE) is PPU / SCALE, the
project's 57.6361.  Chip 151 shipped its flakes at 171.7241 (0.336x, 5.1 px
instead of 15.2) and its three other particle sprites at 173.2/174.7; the same
mismatch is in every other particle chip.

    python3 Tools/SwfToSvg/audit_sprite_scale.py            # report
    python3 Tools/SwfToSvg/audit_sprite_scale.py --write    # set ppu

Only the ppu line of a `.meta` changes.  The sprite child's offset is
`bboxCentre * U`, which is independent of ppu, so the art stays centred on its
node -- see AGENTS.md, "a spawned particle renders at the size of the art it
was drawn from".
"""

import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CHIPS = os.path.join(ROOT, "Assets", "Chips")

SCALE = 6.94          # exported pixels per SWF px (normalize.SCALE)
PPU = 400             # sprite pixels per unit (build_prefabs.PPU)
U = SCALE / PPU       # world units per SWF px
IDEAL = PPU / SCALE   # 57.6361: the ppu of a sprite drawn at its SWF size


def viewbox(svg_path):
    text = open(svg_path, encoding="utf-8", errors="ignore").read(4000)
    m = re.search(r'viewBox="([^"]+)"', text)
    if not m:
        return None
    return [float(v) for v in re.split(r"[ ,]+", m.group(1).strip()) if v][:4]


def ppu_of(meta_path):
    text = open(meta_path, encoding="utf-8").read()
    m = re.search(r"svgPixelsPerUnit: ([\d.]+)", text)
    return float(m.group(1)) if m else None


def set_ppu(meta_path, ppu):
    text = open(meta_path, encoding="utf-8").read()
    new = re.sub(r"svgPixelsPerUnit: [\d.]+", "svgPixelsPerUnit: %.4f" % ppu, text)
    if new != text:
        open(meta_path, "w", encoding="utf-8").write(new)
    return new != text


def symbol_frames(entry, cdir):
    """every exported frame of a particle symbol, as meta paths"""
    art = entry.get("art")
    names = art if isinstance(art, list) else [art]
    return [os.path.join(cdir, "Sprites", n) + ".meta" for n in names if n]


def particle_nodes(prefab_path):
    """chip_XXXX_particle_n node -> its uniform scale, read from the prefab.

    The particle node is the one named `particle_<n>`; the sprite child under it
    carries the renderer.  Only the node's own scale matters: build_prefabs never
    scales it, so a value other than 1 means someone compensated by hand and the
    audit must not overwrite that.
    """
    if not os.path.exists(prefab_path):
        return {}
    text = open(prefab_path, encoding="utf-8").read()
    out = {}
    # each GameObject block is followed by its Transform; walk name -> scale
    for m in re.finditer(r"m_Name: (particle_\d+)\n(.*?)(?=\n--- )", text, re.S):
        name, body = m.group(1), m.group(2)
        t = re.search(r"m_LocalScale: \{x: ([\d.eE+-]+), y: ([\d.eE+-]+)", text[m.end():m.end() + 2000])
        out[name] = float(t.group(1)) if t else 1.0
    return out


def chips():
    for range_dir in sorted(glob.glob(os.path.join(CHIPS, "*"))):
        if not os.path.isdir(range_dir):
            continue
        for name in sorted(os.listdir(range_dir)):
            m = re.match(r"Chip_(\d{4})$", name)
            if not m:
                continue
            cdir = os.path.join(range_dir, name)
            js = glob.glob(os.path.join(cdir, "Sprites", "*_effect.json"))
            if not js:
                continue
            yield int(m.group(1)), cdir, json.load(open(js[0], encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="set the sprites' ppu")
    ap.add_argument("--ids", help="comma list / ranges of chip ids")
    args = ap.parse_args()

    want = None
    if args.ids:
        want = set()
        for chunk in args.ids.split(","):
            chunk = chunk.strip()
            if "-" in chunk:
                a, b = chunk.split("-")
                want.update(range(int(a), int(b) + 1))
            elif chunk:
                want.add(int(chunk))

    rows, fixed, skipped = [], 0, 0
    for cid, cdir, data in chips():
        if want and cid not in want:
            continue
        particles = ((data.get("clips") or {}).get("particles")) or []
        if not particles:
            continue
        scales = particle_nodes(os.path.join(cdir, "Chip_%04d_Effect.prefab" % cid))
        for p in particles:
            art = p.get("art")
            first = art[0] if isinstance(art, list) else art
            svg = os.path.join(cdir, "Sprites", first)
            meta = svg + ".meta"
            size = p.get("size_px")
            if not (os.path.exists(svg) and os.path.exists(meta) and size):
                skipped += 1
                continue
            vb = viewbox(svg)
            ppu = ppu_of(meta)
            if vb is None or ppu is None:
                skipped += 1
                continue
            node = scales.get(p.get("name"), 1.0)
            if abs(node - 1.0) > 1e-4:
                # a hand-scaled node already compensates: leave the meta alone
                rows.append((cid, p["name"], ppu, ppu * node, 0.0, "node scale %.3f" % node))
                skipped += 1
                continue
            want_ppu = vb[2] * PPU / size[0]
            ratio = want_ppu / ppu if ppu else 0.0
            rows.append((cid, p["name"], ppu, ppu, ratio, "%.1fx %.1f px" % (
                1.0 / ratio if ratio else 0.0, vb[2] / ppu / U if ppu else 0.0)))
            if args.write:
                # every frame of the symbol, not just the first: an animated
                # particle shows all of them, and a per-frame ppu would make it
                # pulse in size
                for frame_meta in symbol_frames(p, cdir):
                    if not os.path.exists(frame_meta):
                        continue
                    if abs((ppu_of(frame_meta) or 0.0) - want_ppu) > 0.004:
                        if set_ppu(frame_meta, round(want_ppu, 4)):
                            fixed += 1

    if args.write:
        # re-read so the report shows the result
        rows = []
        for cid, cdir, data in chips():
            if want and cid not in want:
                continue
            for p in ((data.get("clips") or {}).get("particles")) or []:
                art = p.get("art")
                first = art[0] if isinstance(art, list) else art
                svg = os.path.join(cdir, "Sprites", first)
                meta = svg + ".meta"
                if not (os.path.exists(svg) and os.path.exists(meta) and p.get("size_px")):
                    continue
                vb, ppu, size = viewbox(svg), ppu_of(meta), p["size_px"]
                if vb is None or ppu is None:
                    continue
                want_ppu = vb[2] * PPU / size[0]
                ratio = want_ppu / ppu
                rows.append((cid, p["name"], ppu, ppu, ratio,
                             "%.1fx %.1f px" % (1.0 / ratio, vb[2] / ppu / U)))

    print("%-6s %-10s %10s %10s %7s  %s" % ("chip", "particle", "ppu", "rendered",
                                            "ratio", "size"))
    for cid, name, ppu, rendered, ratio, note in rows:
        print("%-6d %-10s %10.4f %10.4f %7.3f  %s" % (cid, name, ppu, rendered, ratio, note))
    bad = [r for r in rows if r[4] and abs(r[4] - 1.0) > 0.004]
    print("\n%d particle renderers, %d off the art's size, %d skipped, %d ppu written"
          % (len(rows), len(bad), skipped, fixed))
    if bad and not args.write:
        print("run with --write to set ppu; expected ppu for an untouched export is %.4f"
              % IDEAL)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
