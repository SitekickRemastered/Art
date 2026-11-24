#!/usr/bin/env python3
"""One command per spawned-particle chip: check it against the SWF rule.

Chip 151's check used to be a hand-built composite page, a Unity `--hold` run, a
throwaway measuring script in gitignored `Logs/` and two panel builders.  This
is the same check, driven from the chip's own data:

    python3 Tools/SwfToSvg/particle_check.py --chip 151              # measure
    python3 Tools/SwfToSvg/particle_check.py --chip 151 --unity      # + run Unity
    python3 Tools/SwfToSvg/particle_check.py --chip 152 --live       # spawner on
    python3 Tools/SwfToSvg/particle_check.py --chip 151 --reference  # + Ruffle page

What it asserts, and why each one is in here:

* **placement** -- every particle renderer sits at the x its effect json says
  (`x_swf`), inside 0.5 SWF px.  That is the STAGE_OFFSET fix and the four
  columns' spread, read from `report.txt`'s renderer table rather than an image.
* **size** -- each renderer's world size divided by `U` matches the art's own
  SWF size (`size_px / SCALE`), within 2%.  A sprite imported at the wrong ppu
  is exactly the bug chip 151 shipped (0.336x) and whose siblings still had.
* **field** -- with `--live` the capture must hold a stream, not four columns:
  the blob count has to be at least a third of the rule's expected concurrency
  (`mean burst x mean lifetime / interval`) and the x spread at least half the
  stage.  A baked effect reads 4 and a spread of 0.
* **pose** -- with `--hold` the authored pose is what is measured, so the group
  centre against the body can be compared with the composite reference; the
  number it prints is the body-height offset the chip 151 work used.

`--reference` captures `sitekick_particles.html` headless and measures it the
same way, for a visual side-by-side; it needs a Chromium-family browser (the
same one `ruffle_frames.py --capture` uses).
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
CHIPS = os.path.join(ROOT, "Unity", "Assets", "Chips")
UNITY = os.environ.get("UNITY", os.path.expanduser(
    "~/Unity/Hub/Editor/6000.3.24f1/Editor/Unity"))

SCALE = 6.94
U = SCALE / 400.0
# ChipGallery draws the effect layers at 2.5x, so a report's world numbers are
# 2.5 times the prefab's (the chip 145 sweep moves by exactly the offset x 2.5)
PREVIEW = 2.5


def chip_dir(cid):
    hits = glob.glob(os.path.join(CHIPS, "*", "Chip_%04d" % cid))
    return hits[0] if hits else None


def effect_json(cdir):
    js = glob.glob(os.path.join(cdir, "Sprites", "*_effect.json"))
    return json.load(open(js[0], encoding="utf-8")) if js else {}


def spawn_rule(cid):
    try:
        clips = json.load(open(os.path.join(HERE, "effect_clips.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return (clips.get(str(cid)) or {}).get("spawn") or {}


def report_path(cid, live):
    # ChipPlayCheck always writes chip_XXXX_play; a live run is copied aside so
    # the held capture (the authored pose the composite is matched against)
    # survives the next run
    return os.path.join(ROOT, "Unity", "Logs", "chip_%04d_play%s" % (
        cid, "_live" if live else ""), "report.txt")


def run_unity(cid, live):
    """Run the play-mode check with the right flags for a particle chip."""
    lock = os.path.join(ROOT, "Unity", "Temp", "UnityLockfile")
    if os.path.exists(lock):
        os.unlink(lock)
    args = [UNITY, "-batchmode", "-projectpath", os.path.join(ROOT, "Unity"),
            "-executeMethod", "Sitekick.ChipPlayCheck.RunFromCommandLine",
            "--chip", str(cid), "--stage"]
    if not live:
        args.append("--hold")
    log = os.path.join(ROOT, "Unity", "Logs", "p%04d_%s.log" % (cid, "live" if live else "hold"))
    print("running Unity: %s" % " ".join(args))
    subprocess.run(args + ["-logFile", log], check=False)
    out = os.path.join(ROOT, "Unity", "Logs", "chip_%04d_play" % cid)
    if live and os.path.isdir(out):
        import shutil
        dst = out + "_live"
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(out, dst)
        return dst
    return out


def renderers(report):
    """The `  renderer ... centre (...) size WxH` lines of a static report."""
    rows = []
    for line in open(report, encoding="utf-8").read().splitlines():
        m = re.search(r"renderer \S+\s+sprite (\S+).*centre \(([-\d.]+), ([-\d.]+),", line)
        s = re.search(r"size ([\d.]+)x([\d.]+)", line)
        # 153 and 1133 also draw a backdrop clip from the same prefab; it is not
        # a particle column, so it must not be counted as one
        if m and s and "particle" not in m.group(1):
            continue
        if m and s:
            rows.append({"sprite": m.group(1), "x": float(m.group(2)),
                         "y": float(m.group(3)), "w": float(s.group(1)),
                         "h": float(s.group(2))})
    return rows


def field_line(report):
    m = re.search(r"particle field (\d+) symbol\(s\)\s+live (\d+) of (\d+)(\s+held)?",
                  open(report, encoding="utf-8").read())
    if not m:
        return None
    return {"symbols": int(m.group(1)), "live": int(m.group(2)),
            "capacity": int(m.group(3)), "held": bool(m.group(4))}


def expected_columns(data):
    """The x the prefab should place its columns at, in SWF px from the stage."""
    return [p.get("x_swf") for p in ((data.get("clips") or {}).get("particles") or [])]


def measure_capture(path, stream=False):
    from measure_particles import measure, measure_stream
    return measure_stream(path) if stream else measure(path)


def reference(cid, cdir, data, browser=None):
    """Capture the 1:1 composite: sitekick.swf with the chip's particle columns.

    The page places copies of one exported frame at SWF stage coordinates, so a
    screenshot is the Flash-side placement for the same columns the prefab
    bakes.  `--hold` leaves the particle nodes at their own positions (the
    animator is what would move them), i.e. on the stage's centre row, so `at`
    puts the copies on y 0 and the two captures measure the same thing.
    """
    import ruffle_frames as rf
    parts = data["clips"]["particles"]
    art = os.path.join(cdir, "Sprites", parts[0]["art"][0])
    xs = [p.get("x_swf", 0.0) for p in parts]
    at = ";".join("%.2f,0" % x for x in xs)
    rel = "/" + os.path.relpath(art, ROOT)
    server, port = rf.serve(os.path.join(ROOT, "Unity", "Temp"))
    url = ("http://127.0.0.1:%d/Unity/Tools/SwfToSvg/sitekick_particles.html"
           "?art=%s&at=%s&scale=1" % (port, rel, at))
    shot = os.path.join(ROOT, "Unity", "Logs", "p%04d_reference.png" % cid)
    rf.capture_page(rf.browser_command(browser), url, shot, 375, 300, 15000)
    server.shutdown()
    return shot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chip", type=int, required=True)
    ap.add_argument("--unity", action="store_true", help="run the play-mode check first")
    ap.add_argument("--live", action="store_true", help="measure the spawner, not the held pose")
    ap.add_argument("--reference", action="store_true", help="also capture the Ruffle composite")
    ap.add_argument("--browser", help="Chromium-family command for --reference")
    args = ap.parse_args()

    cdir = chip_dir(args.chip)
    if not cdir:
        raise SystemExit("no chip_%04d" % args.chip)
    data = effect_json(cdir)
    if not ((data.get("clips") or {}).get("particles")):
        raise SystemExit("chip %d has no spawned particles" % args.chip)

    if args.unity:
        run_unity(args.chip, args.live)

    report = report_path(args.chip, args.live)
    if not os.path.exists(report):
        raise SystemExit("no %s; run with --unity (or pass the flags to ChipPlayCheck)"
                         % os.path.relpath(report, ROOT))
    text = open(report, encoding="utf-8").read()
    print(text.strip().splitlines()[0])
    for line in text.splitlines():
        if line.startswith("RESULT"):
            print(line)

    ok = True
    cols = [c for c in expected_columns(data) if c is not None]
    rows = renderers(report)
    # a held capture is the authored pose: one renderer per column, at its x
    if not args.live:
        if len(rows) != len(cols):
            print("FAIL placement: %d renderers for %d columns" % (len(rows), len(cols)))
            ok = False
        # The group's absolute x is the gallery's, not the chip's, so the check
        # is the columns' spacing: the prefab must put them `x_swf` apart, which
        # is what the four-column spread was rebuilt to.  A stacked set reads a
        # spacing of 0 (the pre-STAGE_OFFSET chrome).
        got = [x / PREVIEW for x in sorted(r["x"] for r in rows)]
        want = sorted(c * U for c in cols)
        if len(got) == len(want) and len(got) > 1:
            for a, b, wa, wb in zip(got, got[1:], want, want[1:]):
                # 2% of the gap, not 0.01 units: a chip with several particle
                # symbols (1109 has four) has a different bbox centre per
                # symbol, and the renderer sits at node + that offset.  A
                # collapsed set still reads a gap of 0, which this catches.
                if abs((b - a) - (wb - wa)) > max(0.02 * abs(wb - wa), 0.01):
                    print("FAIL placement: columns %.3f units apart, expected %.3f"
                          % (b - a, wb - wa))
                    ok = False
            print("placement: columns span %.2f units (expected %.2f)"
                  % (got[-1] - got[0], want[-1] - want[0]))
        elif cols:
            print("FAIL placement: %d renderers for %d columns" % (len(got), len(cols)))
            ok = False
        # size is the sprite's import scale, which audit_sprite_scale.py owns;
        # here it is reported so a run says what the renderers measure
        w, h = rows[0]["w"] / PREVIEW, rows[0]["h"] / PREVIEW
        print("size: renderer %.3fx%.3f units = %.1fx%.1f SWF px"
              % (w, h, w / U, h / U))

    field = field_line(report)
    rule = spawn_rule(args.chip)
    burst = rule.get("burst", 10)
    life = rule.get("lifetime", [3, 8])
    expected_live = (burst - 1) / 2.0 * (sum(life) / 2.0) / rule.get("intervalSeconds", 1.0)
    if field:
        print("field: %d symbol(s), %d live of %d%s"
              % (field["symbols"], field["live"], field["capacity"],
                 "  (held)" if field["held"] else ""))
        if not args.live and not field["held"]:
            # the directory holds a live capture: its numbers are a stream, not
            # the authored pose, so comparing them would be meaningless
            print("FAIL the report is a live capture, not a held one; re-run with --unity")
            return 1
        if not args.live and field["live"] != 0:
            print("FAIL held capture spawned particles: %d live" % field["live"])
            ok = False

    # a chip that also draws a backdrop (153, 1133) has that art in the same
    # capture, so measuring "particles" there would count the backdrop instead
    drawn = re.search(r"^drawn (.*)$", text, re.M)
    backdrop = None
    if drawn:
        for name in drawn.group(1).split(","):
            if name and "particle" not in name:
                backdrop = name
                break

    stage = os.path.join(os.path.dirname(report), "stage.png")
    if backdrop:
        print("capture: skipped, the prefab also draws %s" % backdrop)
    elif os.path.exists(stage):
        # a live stream's art may be outlined rather than white (152's bubbles),
        # so the stream measurement masks anything off the backdrop
        m = measure_capture(stage, stream=args.live)
        if m and m.get("count"):
            centre = ("" if "dy_centre" not in m else
                      ", group centre %+.3f body heights" % (m["dy_centre"] / m["height"]))
            print("capture: %d blob(s), x spread %.2f body widths%s"
                  % (m["count"], m["spread"], centre))
            if args.live:
                if m["count"] < expected_live / 3.0:
                    print("FAIL field: %d blobs on stage, the rule expects about %.0f"
                          % (m["count"], expected_live))
                    ok = False
                if m["spread"] < 0.5:
                    print("FAIL field: x spread %.2f body widths, the rule is uniform over the stage"
                          % m["spread"])
                    ok = False
        else:
            print("capture: no blobs found outside the body")

    if args.reference:
        shot = reference(args.chip, cdir, data, args.browser)
        print("reference: %s" % os.path.relpath(shot, ROOT))
        measure_capture(shot)

    print("RESULT: %s" % ("OK" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
