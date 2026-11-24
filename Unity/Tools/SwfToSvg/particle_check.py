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
* **field** -- with `--live` the spawner's own `LiveCount` has to reach a third
  of the rule's expected concurrency (`mean burst x mean lifetime / interval`),
  and the capture has to corroborate it: blobs at least the held pose's and an
  x spread at least half the stage.  A baked effect reads 4 blobs and a spread
  of 0; a prefab with no field block has no `LiveCount` at all.
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
import statistics
import subprocess
import sys
import time

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


def run_unity(cid, live, seed=None, live_seconds=None):
    """Run the play-mode check with the right flags for a particle chip."""
    lock = os.path.join(ROOT, "Unity", "Temp", "UnityLockfile")
    if os.path.exists(lock):
        os.unlink(lock)
    args = [UNITY, "-batchmode", "-projectpath", os.path.join(ROOT, "Unity"),
            "-executeMethod", "Sitekick.ChipPlayCheck.RunFromCommandLine",
            "--chip", str(cid), "--stage"]
    if not live:
        args.append("--hold")
    if seed is not None:
        # batchmode seeds UnityEngine.Random the same way on every launch, so a
        # second run without this measures the first one's sample again
        args += ["--seed", str(seed)]
    if live_seconds is not None:
        args += ["--live-seconds", "%.1f" % live_seconds]
    log = os.path.join(ROOT, "Unity", "Logs", "p%04d_%s.log" % (cid, "live" if live else "hold"))
    print("running Unity: %s" % " ".join(args))
    started = time.time()
    subprocess.run(args + ["-logFile", log], check=False)
    out = os.path.join(ROOT, "Unity", "Logs", "chip_%04d_play" % cid)
    report = os.path.join(out, "report.txt")
    if not os.path.exists(report) or os.path.getmtime(report) < started:
        # a launch that died leaves the previous run's report behind; grading it
        # would print numbers that were not measured this time (this happened:
        # `--live` without `--unity` re-measured one capture five times)
        raise SystemExit("FAIL: Unity wrote no new report; see %s"
                         % os.path.relpath(log, ROOT))
    if live:
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


def live_window(rule):
    """How long the stream is given before the capture.

    With a 1 s spawn tick and whole-second lifetimes, `maxLifetime + 2` is where
    every age class that can still be alive is represented, i.e. the count the
    rule's `mean burst x mean lifetime` describes.  The old fixed 4.5 s window
    sampled 786 two to three lifetimes short of that and undercounted 1109 by
    about 30%.
    """
    life = rule.get("lifetime", [3, 8])
    return max(4.5, float(life[1]) + 2.0)


def hold_baseline(cid):
    """Blobs the chip's own authored pose puts on the stage.

    The live floor has to clear this or a prefab whose particle field was
    dropped would still pass: chip 786's four baked coins read 7 blobs under the
    stream mask, more than a third of its rule.  The hold capture is kept beside
    the live one and re-taken when the prefab changes.
    """
    here = os.path.join(ROOT, "Unity", "Logs", "chip_%04d_play_hold" % cid)
    report = os.path.join(here, "report.txt")
    prefabs = glob.glob(os.path.join(chip_dir(cid) or "", "*.prefab"))
    stale = (not os.path.exists(report)) or (
        prefabs and os.path.getmtime(prefabs[0]) > os.path.getmtime(report))
    if stale:
        out = run_unity(cid, False, None)
        import shutil
        shutil.rmtree(here, ignore_errors=True)
        shutil.copytree(out, here)
    stage = os.path.join(here, "stage.png")
    m = measure_capture(stage, stream=True) if os.path.exists(stage) else None
    return (m or {}).get("count", 0)


def backdrop_of(report):
    """The non-particle sprite a prefab also draws (153 and 1133 carry a `back` clip)."""
    try:
        text = open(report, encoding="utf-8").read()
    except OSError:
        return None
    m = re.search(r"^drawn (.*)$", text, re.M)
    if not m:
        return None
    for name in m.group(1).split(","):
        name = name.strip()
        if name and "particle" not in name:
            return name
    return None


def repeat_live(cid, reps, seed0):
    """Run the editor N times with different seeds and report the distribution.

    One live capture is a single sample of `Math.random`, so whether a chip holds
    a stream cannot be judged from it: the spread of the counts can.
    """
    rule = spawn_rule(cid)
    burst = rule.get("burst", 10)
    life = rule.get("lifetime", [3, 8])
    rule_mean = (burst - 1) / 2.0 * (sum(life) / 2.0) / rule.get("intervalSeconds", 1.0)
    window = live_window(rule)
    held = hold_baseline(cid)
    spawner_floor = max(rule_mean / 3.0, 3.0)
    paint_floor = max(held, 4.0)
    print("window %.1f s   held baseline %d blob(s)   floors spawner %.1f live, capture %.0f blob(s)"
          % (window, held, spawner_floor, paint_floor))
    rows = []
    for i in range(reps):
        seed = seed0 + i
        out = run_unity(cid, True, seed, window)
        report = os.path.join(out, "report.txt")
        field = field_line(report)
        stage = os.path.join(out, "stage.png")
        m = measure_capture(stage, stream=True) if os.path.exists(stage) else None
        backdrop = backdrop_of(report)
        row = {"seed": seed,
               "live": field["live"] if field else -1,
               "blobs": (m or {}).get("count", 0),
               "spread": (m or {}).get("spread", 0.0)}
        rows.append(row)
        # with a backdrop in the same capture the blob numbers measure that art,
        # so only the spawner's own count can be judged
        ok = row["live"] >= spawner_floor
        if not backdrop:
            ok = ok and row["blobs"] >= paint_floor and row["spread"] >= 0.5
        print("rep %d  seed %-6d live %-3d  blobs %-3d  spread %.2f  %s"
              % (i + 1, seed, row["live"], row["blobs"], row["spread"],
                 "ok" if ok else "BELOW the floor"))
    blobs = [r["blobs"] for r in rows]
    lives = [r["live"] for r in rows]
    backdrop = backdrop_of(report)
    if backdrop:
        print("capture: skipped, the prefab also draws %s" % backdrop)
    passed = sum(1 for r in rows if (r["live"] >= spawner_floor
                                     and (backdrop is not None
                                          or (r["blobs"] >= paint_floor and r["spread"] >= 0.5))))
    print("")
    print("blobs  n %d  mean %.1f  sd %.1f  min %d  max %d   (floor %.0f, held pose %d)"
          % (len(blobs), statistics.mean(blobs), statistics.pstdev(blobs), min(blobs), max(blobs),
             paint_floor, held))
    print("live   n %d  mean %.1f  sd %.1f  min %d  max %d"
          % (len(lives), statistics.mean(lives), statistics.pstdev(lives), min(lives), max(lives)))
    print("RESULT: %s  %d of %d reps over the floor"
          % ("OK" if passed == len(rows) else "FAIL", passed, len(rows)))
    return 0 if passed == len(rows) else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chip", type=int, required=True)
    ap.add_argument("--unity", action="store_true", help="run the play-mode check first")
    ap.add_argument("--live", action="store_true", help="measure the spawner, not the held pose")
    ap.add_argument("--seed", type=int, help="reseed UnityEngine.Random before the effect spawns")
    ap.add_argument("--repeat", type=int, help="run --unity --live N times and report the distribution")
    ap.add_argument("--reference", action="store_true", help="also capture the Ruffle composite")
    ap.add_argument("--browser", help="Chromium-family command for --reference")
    args = ap.parse_args()

    cdir = chip_dir(args.chip)
    if not cdir:
        raise SystemExit("no chip_%04d" % args.chip)
    data = effect_json(cdir)
    if not ((data.get("clips") or {}).get("particles")):
        raise SystemExit("chip %d has no spawned particles" % args.chip)

    if args.repeat:
        if not (args.live and args.unity):
            raise SystemExit("--repeat needs --unity --live")
        return repeat_live(args.chip, args.repeat, args.seed if args.seed is not None else 1)

    rule = spawn_rule(args.chip)
    window = live_window(rule) if args.live else None
    # measured before the live run so the baseline is the prefab as it is now
    held = hold_baseline(args.chip) if args.live else 0

    if args.unity:
        run_unity(args.chip, args.live, args.seed, window)

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
    burst = rule.get("burst", 10)
    life = rule.get("lifetime", [3, 8])
    expected_live = (burst - 1) / 2.0 * (sum(life) / 2.0) / rule.get("intervalSeconds", 1.0)
    # The spawner's own counter is the exact measure of the stream: the held pose
    # reads 7 blobs under the stream mask, so no blob floor separates the baked
    # coins from a stream (10 coins merge into 8 blobs), while `LiveCount` is 0
    # for anything that is not spawning.  The capture is the corroboration that
    # the copies are drawn, not the gate.
    # The floor is a third of the rule, not half: one run is one draw of a burst
    # that ranges 0..N, so a legitimate low tail has to stay over it (1133's
    # seed 5 read 12 against 12.4 and failed), and the guard against a dropped
    # field no longer rests on the count -- that prefab reports no field line and
    # `LiveCount` 0.  A third still catches a spawner that runs but far too quiet.
    spawner_floor = max(expected_live / 3.0, 3.0)
    paint_floor = max(held, 4.0)
    if args.live:
        print("rule: window %.1f s, about %.0f live, held pose %d blob(s); "
              "floors spawner %.1f live, capture %.0f blob(s)"
              % (window, expected_live, held, spawner_floor, paint_floor))
    if args.live and not field:
        # a prefab whose particle field was dropped still draws the baked columns
        print("FAIL the report has no particle field: the prefab has no spawner")
        ok = False
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
        if args.live and field["live"] < spawner_floor:
            print("FAIL spawner: %d live, floor %.1f (about %.0f by this window)"
                  % (field["live"], spawner_floor, expected_live))
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
                if m["count"] < paint_floor:
                    print("FAIL capture: %d blobs on stage, the held pose alone draws %d"
                          % (m["count"], held))
                    ok = False
                if m["spread"] < 0.5:
                    print("FAIL field: x spread %.2f body widths, the rule is uniform over the stage"
                          % m["spread"])
                    ok = False
        else:
            print("capture: no blobs found outside the body")
            if args.live:
                print("FAIL field: nothing spawned on stage")
                ok = False

    if args.reference:
        shot = reference(args.chip, cdir, data, args.browser)
        print("reference: %s" % os.path.relpath(shot, ROOT))
        measure_capture(shot)

    print("RESULT: %s" % ("OK" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
