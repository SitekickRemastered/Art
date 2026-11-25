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
  and the x values it reports have to span the stage: the floor is the 0.1%
  quantile of the span of `n` uniform draws (`spread_floor`), so it rises with
  the count instead of failing legitimate quiet draws.  The capture corroborates
  with blobs at least the held pose's.  A baked effect reads 4 blobs and has no
  x values at all; a prefab with no field block has no `LiveCount` either.
* **rule** -- the spread is one third of the rule, so the spawner also reports
  every live particle (`live particle  x .. y .. age .. life .. from .. to ..
  scale .. frame n of m`) and the constants it runs (`field rule`).  Each one
  has to start `margin` px past the stage edge, end at the other side, cross
  linearly over its own lifetime, draw at `Math.random()` scale and show the
  frame its age puts it at in a symbol playing at the movie's frame rate.  A
  fixed y, a half-speed fall and every particle at scale 1 all passed the
  spread check; each fails here.
* **distribution** -- `--repeat` compares the batch's mean live count and mean
  spread with `particle_baseline.json`, where the per-chip numbers live instead
  of in the docs, and warns when the mean falls two stored standard deviations
  below.  A warning, not a gate: one run is one draw of a 0..N burst, so a
  legitimate quiet batch is possible even when every rep clears its floor.
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
BASELINE = os.path.join(HERE, "particle_baseline.json")
CHIPS = os.path.join(ROOT, "Unity", "Assets", "Chips")
UNITY = os.environ.get("UNITY", os.path.expanduser(
    "~/Unity/Hub/Editor/6000.3.24f1/Editor/Unity"))

SCALE = 6.94
U = SCALE / 400.0
# ChipGallery draws the effect layers at 2.5x, so a report's world numbers are
# 2.5 times the prefab's (the chip 145 sweep moves by exactly the offset x 2.5)
PREVIEW = 2.5
# A fixed spread floor cannot judge a small sample: half the stage fails about a
# third of legitimate 4-particle draws on a uniform field (P(span < 0.5) = 4 *
# 0.5**3 - 3 * 0.5**4 = 0.31), and 786's honest 7-live draw read 0.59 against it.
# The floor is therefore the 0.1% quantile of the span of `n` uniform draws,
# computed per run (see `spread_floor`), in stage fractions rather than body
# widths -- the four authored columns span 7.2 body widths (206.25 px either
# side of the centre, outside the stage), so a body-width fraction cannot fail.
SPREAD_CONFIDENCE = 0.001


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


def run_unity(cid, live, seed=None, live_seconds=None, hide_back=False):
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
    if hide_back:
        args.append("--hide-back")
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


def spawn_x(report):
    """The spawner's own x for every live particle, in SWF px from the stage centre.

    ChipParticleField writes them (`live x ...`) because the capture cannot be
    trusted for this: blobs merge where `FlakeMC` art overlaps and a missed one
    at the edge moves the extremes -- 153's 36 live particles read as 29 blobs.
    """
    try:
        text = open(report, encoding="utf-8").read()
    except OSError:
        return None
    m = re.search(r"^live x ?(.*)$", text, re.M)
    if not m:
        return None
    return [float(v) for v in m.group(1).split(",") if v.strip()]


def spawn_stage(report):
    """The spawn domain and capture framing the run used, in SWF px.

    `ChipParticleField` reads both from the prefab (`stageWidth`/`stageHeight`)
    and `ChipPlayCheck` writes them beside the `live x` values, so the spread is
    divided by the stage the rule actually drew in.  Nothing defaults to 375:
    a chip whose stage is wider would be silently scaled against a constant, and
    the capture's margin is what turns `stage.png` pixels into SWF px.
    """
    try:
        text = open(report, encoding="utf-8").read()
    except OSError:
        return None
    m = re.search(r"^field stage ([\d.]+) x ([\d.]+) px\s+capture margin ([\d.]+)",
                  text, re.M)
    if not m:
        return None
    return {"width": float(m.group(1)), "height": float(m.group(2)),
            "margin": float(m.group(3))}


def spread_of(xs, stage):
    """Spawn spread and stdev as fractions of the stage the rule drew in."""
    if not xs or not stage:
        return None
    return {"n": len(xs), "spread": (max(xs) - min(xs)) / float(stage),
            "stdev": statistics.pstdev(xs) / float(stage)}


PARTICLE = re.compile(
    r"^live particle\s+x (-?[\d.]+)\s+y (-?[\d.]+)\s+age ([\d.]+)\s+life ([\d.]+)"
    r"\s+from (-?[\d.]+)\s+to (-?[\d.]+)\s+scale ([\d.]+)\s+frame (\d+) of (\d+)\s*$",
    re.M)

FIELD_RULE = re.compile(
    r"^field rule\s+particle margin ([\d.]+) px\s+symbol ([\d.]+) fps"
    r"\s+lifetime ([\d.]+)\.\.([\d.]+) s\s+burst 0\.\.(\d+) every ([\d.]+) s",
    re.M)


def live_particles(report):
    """Every live particle's rule state, in the order the spawner listed it."""
    try:
        text = open(report, encoding="utf-8").read()
    except OSError:
        return []
    return [{"x": float(m.group(1)), "y": float(m.group(2)), "age": float(m.group(3)),
             "life": float(m.group(4)), "from": float(m.group(5)),
             "to": float(m.group(6)), "scale": float(m.group(7)),
             "frame": int(m.group(8)), "frames": int(m.group(9))}
            for m in PARTICLE.finditer(text)]


def field_rule(report):
    """The spawn constants the field reports: margin, symbol rate, lifetime, burst."""
    try:
        text = open(report, encoding="utf-8").read()
    except OSError:
        return None
    m = FIELD_RULE.search(text)
    if not m:
        return None
    return {"margin": float(m.group(1)), "fps": float(m.group(2)),
            "life": (float(m.group(3)), float(m.group(4))),
            "burst": int(m.group(5)), "interval": float(m.group(6))}


def capture_args(st):
    """(stage tuple, margin) for measuring a capture, from a report's line."""
    if not st:
        return None, None
    return (st["width"], st["height"]), st["margin"]


def spread_floor(n, confidence=SPREAD_CONFIDENCE):
    """Smallest stage fraction the x span must reach for `n` live particles.

    The rule draws every particle's x uniformly over the stage, so the span of n
    of them has `P(span <= r) = n*r**(n-1) - (n-1)*r**n`.  Solving that at 0.1%
    gives a floor that scales with the count instead of a fixed half: 0.06 at 4
    live, 0.24 at 7 (786's 0.59 draw passes), 0.45 at 12 and 0.78 at 38, so a
    full stream still has to cover most of the stage while a quiet draw is only
    failed for being improbable rather than merely narrow.
    """
    if n < 2:
        return None
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if n * mid ** (n - 1) - (n - 1) * mid ** n < confidence:
            lo = mid
        else:
            hi = mid
    return lo


def rule_problems(report, stage, export):
    """What the spread gate cannot see: the start, the travel, the scale, the playhead.

    The x spread says the spawn rule covers the stage.  It says nothing about
    whether a particle starts 25 px past the edge, crosses the stage linearly
    over its own lifetime, draws at `Math.random()` scale, or plays its symbol
    at the movie's frame rate -- a field with a fixed y, a half-speed traverse
    or every particle at scale 1 passed every earlier check.  Each of these is
    read from the spawner's own `live particle` lines.  Returns a list of
    sentences, empty when the rule holds.
    """
    parts = live_particles(report)
    rule = field_rule(report)
    if rule is None:
        return ["the report has no `field rule` line, so the particle margin, "
                "symbol rate and lifetime the field runs are unknown"]
    if stage is None:
        return []      # the unknown-stage failure is already reported once
    if not parts:
        return ["the report lists no live particles to audit"]

    out = []
    reach = stage["height"] / 2.0 + rule["margin"]
    start = [p for p in parts if abs(abs(p["from"]) - reach) > 0.5]
    if start:
        out.append("%d of %d particles start %.2f px from the stage centre, not "
                   "stage/2 + %.2f = %.2f"
                   % (len(start), len(parts), start[0]["from"], rule["margin"], reach))
    ends = [p for p in parts if abs(p["to"] + p["from"]) > 0.5]
    if ends:
        out.append("%d of %d particles end at %.2f after starting at %.2f, not the "
                   "other side of the stage"
                   % (len(ends), len(parts), ends[0]["to"], ends[0]["from"]))

    lo, hi = rule["life"]
    wrong_life = [p for p in parts if not lo - 0.01 <= p["life"] <= hi + 0.01]
    if wrong_life:
        out.append("%d of %d particles live %.2f s, outside the rule's %g..%g s"
                   % (len(wrong_life), len(parts), wrong_life[0]["life"], lo, hi))

    # a linear tween over the particle's own lifetime: the residual is what a
    # constant y, a half-speed traverse or an eased tween shows up as
    travel = 2.0 * reach
    tol = max(1.0, 0.02 * travel)
    rows = []
    for p in parts:
        t = min(1.0, p["age"] / p["life"]) if p["life"] > 0 else 1.0
        rows.append((abs(p["y"] - (p["from"] + (p["to"] - p["from"]) * t)), p,
                     p["from"] + (p["to"] - p["from"]) * t))
    bad = [r for r in rows if r[0] > tol]
    if bad:
        r = max(bad, key=lambda x: x[0])
        out.append("%d of %d particles are off a linear traverse (worst %.1f px: y %.1f "
                   "where the tween puts it at %.1f, tolerance %.1f)"
                   % (len(bad), len(parts), r[0], r[1]["y"], r[2], tol))

    scales = [p["scale"] for p in parts]
    outside = [s for s in scales if s < 0.0 or s > 1.001]
    if outside:
        out.append("%d of %d particles draw at scale %.3f, outside the rule's 0..1"
                   % (len(outside), len(parts), outside[0]))
    floor = spread_floor(len(scales))
    if floor is not None and max(scales) - min(scales) < floor:
        out.append("every particle draws at scale %.2f-%.2f (range %.3f, floor %.3f "
                   "for %d): the rule draws Math.random() per spawn"
                   % (min(scales), max(scales), max(scales) - min(scales), floor,
                      len(scales)))

    fps = export.get("fps")
    if fps and abs(rule["fps"] - fps) > 0.01:
        out.append("the report's symbol rate is %g fps, the chip's export says %g"
                   % (rule["fps"], fps))
    lengths = sorted(set(export.get("frames") or []))
    wrong = [p for p in parts if lengths and p["frames"] not in lengths]
    if wrong:
        out.append("%d of %d particles play %d frame(s); the export has %s"
                   % (len(wrong), len(parts), wrong[0]["frames"],
                      "/".join(str(n) for n in lengths)))
    still = [p for p in parts if p["frames"] < 2]
    if still:
        out.append("%d of %d particles have a single-frame symbol, so nothing animates"
                   % (len(still), len(parts)))
    late = []
    for p in parts:
        if p["frames"] < 2:
            continue
        want = int(p["age"] * rule["fps"]) % p["frames"]
        d = abs(p["frame"] - want)
        d = min(d, p["frames"] - d)
        late.append((d, p, want))
    bad = [r for r in late if r[0] > 1]
    if bad:
        d, p, want = max(bad, key=lambda x: x[0])
        out.append("%d of %d particles are off the playhead (age %.2f s at %g fps is "
                   "frame %d, the symbol shows %d)"
                   % (len(bad), len(parts), p["age"], rule["fps"], want, p["frame"]))
    return out


def print_rule(report, stage, export):
    """One line describing the rule the spawner actually ran."""
    parts = live_particles(report)
    rule = field_rule(report)
    if not (parts and rule and stage):
        return
    ages = [p["age"] for p in parts]
    scales = [p["scale"] for p in parts]
    lives = [p["life"] for p in parts]
    reach = stage["height"] / 2.0 + rule["margin"]
    print("rule: %d track(s), start %.0f px from the centre (stage/2 + %g), ages "
          "%.1f-%.1f s, life %g-%g s, scale %.2f-%.2f (floor %.2f), symbols %d-frame "
          "at %g fps"
          % (len(parts), reach, rule["margin"], min(ages), max(ages), min(lives),
             max(lives), min(scales), max(scales), spread_floor(len(scales)) or 0.0,
             parts[0]["frames"], rule["fps"]))


def baseline_of(cid):
    """The stored distribution for a chip, or None."""
    try:
        data = json.load(open(BASELINE, encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return (data.get("chips") or {}).get(str(cid))


def baseline_stats(entry, key):
    """mean/sd/n of one stored distribution, or None when it is too short to judge."""
    rows = (entry or {}).get(key) or {}
    vals = [float(v) for v in rows.get("values") or []]
    if len(vals) < 2:
        return None
    return {"n": len(vals), "mean": statistics.mean(vals),
            "sd": statistics.pstdev(vals), "min": min(vals), "max": max(vals),
            "seeds": rows.get("seeds") or []}


def baseline_note(cid, batch, key, label):
    """Compare a batch's mean with the stored distribution; warn below mean - 2 sd.

    The per-chip numbers live in `particle_baseline.json` instead of the prose,
    so a batch that has drifted -- a rebuilt prefab with a narrower spawn, a
    window that no longer reaches steady state -- says so when it is measured
    instead of being compared by eye with a figure quoted in AGENTS.md.
    """
    entry = baseline_of(cid)
    st = baseline_stats(entry, key) if entry else None
    if not st:
        print("baseline: no stored %s distribution for %d to compare" % (label, cid))
        return
    if len(batch) < 2:
        print("baseline: %s stored %.2f sd %.2f (n %d); this batch is %d draw(s), "
              "too few to compare"
              % (label, st["mean"], st["sd"], st["n"], len(batch)))
        return
    mean = statistics.mean(batch)
    low = st["mean"] - 2.0 * st["sd"]
    if mean < low:
        # a stored sd of a hundredth is common with four draws, and "72 sd" says
        # less than the numbers do: name the distance only when it is meaningful
        z = (st["mean"] - mean) / st["sd"] if st["sd"] >= 0.01 else None
        where = ("%.1f sd below the stored" % z) if z else "below the stored"
        print("baseline: %s mean %.2f over %d draw(s) is %s %.2f (sd %.2f over %d), "
              "under %.2f -- WARN"
              % (label, mean, len(batch), where, st["mean"], st["sd"], st["n"], low))
    else:
        print("baseline: %s mean %.2f over %d draw(s) against the stored %.2f (sd %.2f "
              "over %d), low %.2f"
              % (label, mean, len(batch), st["mean"], st["sd"], st["n"], low))


def expected_columns(data):
    """The x the prefab should place its columns at, in SWF px from the stage."""
    return [p.get("x_swf") for p in ((data.get("clips") or {}).get("particles") or [])]


def measure_capture(path, stream=False, stage=None, margin=None):
    from measure_particles import measure, measure_stream
    return measure_stream(path, stage=stage, margin=margin) if stream else measure(path)


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


def hold_baseline(cid, hide_back=False):
    """Blobs the chip's own authored pose puts on the stage.

    The live floor has to clear this or a prefab whose particle field was
    dropped would still pass: chip 786's four baked coins read 7 blobs under the
    stream mask, more than a third of its rule.  The hold capture is kept beside
    the live one and re-taken when the prefab changes.
    """
    tag = "_hidden" if hide_back else ""
    here = os.path.join(ROOT, "Unity", "Logs", "chip_%04d_play_hold%s" % (cid, tag))
    report = os.path.join(here, "report.txt")
    prefabs = glob.glob(os.path.join(chip_dir(cid) or "", "*.prefab"))
    # a report without the stage line predates the field reporting it, so its
    # capture cannot be scaled against the chip's own stage
    stale = ((not os.path.exists(report)) or spawn_stage(report) is None or (
        prefabs and os.path.getmtime(prefabs[0]) > os.path.getmtime(report)))
    if stale:
        out = run_unity(cid, False, None, hide_back=hide_back)
        import shutil
        shutil.rmtree(here, ignore_errors=True)
        shutil.copytree(out, here)
    stage = os.path.join(here, "stage.png")
    shape, margin = capture_args(spawn_stage(report))
    m = (measure_capture(stage, stream=True, stage=shape, margin=margin)
         if os.path.exists(stage) else None)
    return (m or {}).get("count", 0)


def has_backdrop(data):
    """Whether the chip draws a back or front layer beside its particles."""
    clips = data.get("clips") or {}
    return any(clips.get(k) for k in ("back", "front"))


def backdrop_of(report):
    """The non-particle sprite a prefab also draws (153 and 1133 carry one)."""
    try:
        text = open(report, encoding="utf-8").read()
    except OSError:
        return None
    if re.search(r"^back hidden ", text, re.M):
        return None          # turned off for this capture, so it cannot be measured
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
    data = effect_json(chip_dir(cid))
    hide = has_backdrop(data)
    symbols = (data.get("clips") or {}).get("particles") or []
    export = {"fps": data.get("fps"),
              "frames": [len(p.get("art") or []) for p in symbols if p.get("art")]}
    held = hold_baseline(cid, hide)
    spawner_floor = max(rule_mean / 3.0, 3.0)
    paint_floor = max(held, 4.0)
    print("window %.1f s   held baseline %d blob(s)   floors spawner %.1f live, capture %.0f blob(s)"
          % (window, held, spawner_floor, paint_floor))
    rows = []
    for i in range(reps):
        seed = seed0 + i
        out = run_unity(cid, True, seed, window, hide)
        report = os.path.join(out, "report.txt")
        field = field_line(report)
        st = spawn_stage(report)
        xs = spawn_x(report)
        shape, margin = capture_args(st)
        stage = os.path.join(out, "stage.png")
        m = (measure_capture(stage, stream=True, stage=shape, margin=margin)
             if os.path.exists(stage) else None)
        backdrop = backdrop_of(report)
        # the spawner's own x values, not the captured blobs: merging loses
        # particles and a missed one at the edge sets the whole span; the divisor
        # is the stage the field reported, never a constant
        sp = spread_of(xs, (st or {}).get("width"))
        row = {"seed": seed,
               "live": field["live"] if field else -1,
               "blobs": (m or {}).get("count", 0),
               "stage": sp["spread"] if sp else 0.0,
               "stdev": sp["stdev"] if sp else 0.0,
               "known": sp is not None,
               "width": (st or {}).get("width"),
               "blob_stage": (m or {}).get("stage") or 0.0}
        rows.append(row)
        # with a backdrop in the same capture the blob numbers measure that art,
        # so only the spawner's own count can be judged
        # no `live x` means the spawner's spread is unknown, and the captured
        # blobs are not a substitute: they understate it (151 reads 0.481 from 9
        # of 14 particles against 0.95 from the spawner's own x values)
        row["floor"] = spread_floor(sp["n"]) if sp else None
        # the parts of the rule the spread cannot see: start, travel, scale, playhead
        row["rule"] = rule_problems(report, st, export)
        ok = row["live"] >= spawner_floor and row["known"] and not row["rule"]
        if not backdrop:
            ok = (ok and row["blobs"] >= paint_floor and row["floor"] is not None
                  and row["stage"] >= row["floor"])
        why = "ok"
        if not ok:
            why = ("RULE " + row["rule"][0][:60] if row["rule"] else
                   "NO live x line" if xs is None else
                   "NO field stage line" if row["width"] is None else
                   "BELOW the floor")
        stamp = ("%.2f sd %.2f floor %.2f" % (row["stage"], row["stdev"], row["floor"])
                 if row["known"] else "unknown")
        print("rep %d  seed %-6d live %-3d  blobs %-3d  spawner %-24s  blobs %.2f  %s"
              % (i + 1, seed, row["live"], row["blobs"], stamp, row["blob_stage"], why))
    blobs = [r["blobs"] for r in rows]
    lives = [r["live"] for r in rows]
    backdrop = backdrop_of(report)
    if backdrop:
        print("capture: skipped, the prefab also draws %s" % backdrop)
    passed = sum(1 for r in rows if (r["live"] >= spawner_floor and r["known"]
                                     and not r["rule"]
                                     and (backdrop is not None
                                          or (r["blobs"] >= paint_floor
                                              and r["floor"] is not None
                                              and r["stage"] >= r["floor"]))))
    print("")
    print("blobs  n %d  mean %.1f  sd %.1f  min %d  max %d   (floor %.0f, held pose %d)"
          % (len(blobs), statistics.mean(blobs), statistics.pstdev(blobs), min(blobs), max(blobs),
             paint_floor, held))
    print("live   n %d  mean %.1f  sd %.1f  min %d  max %d"
          % (len(lives), statistics.mean(lives), statistics.pstdev(lives), min(lives), max(lives)))
    stages = [r["stage"] for r in rows if r["known"]]
    if len(stages) != len(rows):
        print("spread: %d of %d reps had no `live x` line, so their spread is unknown"
              % (len(rows) - len(stages), len(rows)))
    if stages:
        widths = sorted(set(r["width"] for r in rows if r["width"]))
        label = ("%g" % widths[0]) if len(widths) == 1 else \
            "/".join("%g" % w for w in widths)
        print("spread n %d  mean %.2f  sd %.2f  min %.2f  max %.2f   "
              "(of the %s px stage the field reports, from the spawner; floor per rep "
              "from its live count)"
              % (len(stages), statistics.mean(stages), statistics.pstdev(stages),
                 min(stages), max(stages), label))
    # the stored per-chip distributions are the reference, not prose: a batch
    # that has drifted says so here (a warning, not a gate -- a draw is a draw)
    baseline_note(cid, stages, "spread", "spread")
    baseline_note(cid, lives, "live", "live count")

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
    # a back/front layer would be measured as if it were the stream, so both the
    # baseline and the live capture are taken with it off
    hide_back = has_backdrop(data)
    # measured before the live run so the baseline is the prefab as it is now
    held = hold_baseline(args.chip, hide_back) if args.live else 0

    if args.unity:
        run_unity(args.chip, args.live, args.seed, window, hide_back)

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
    st = spawn_stage(report)
    xs = spawn_x(report)
    sp = spread_of(xs, (st or {}).get("width"))
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
        if args.live and sp:
            print("spawn x: %d particle(s), spread %.2f of the %g px stage, stdev %.2f, "
                  "floor %.2f for that count"
                  % (sp["n"], sp["spread"], st["width"], sp["stdev"],
                     spread_floor(sp["n"])))
        if args.live and field["live"] < spawner_floor:
            print("FAIL spawner: %d live, floor %.1f (about %.0f by this window)"
                  % (field["live"], spawner_floor, expected_live))
            ok = False

    # the stream's spread is a property of the spawner's own x values, so it is
    # judged whether or not the capture can be measured -- and a run that did not
    # report them fails: the captured blobs understate the field (151: 0.481 from
    # 9 of 14 against 0.95 from the spawner), so they are never the substitute
    if args.live and xs is None:
        print("FAIL field: the report has no `live x` line, so the spawner's spread is "
              "unknown; the capture is corroboration and cannot stand in for it")
        ok = False
    if args.live and xs is not None and st is None:
        # the divisor is the field's own stage: a constant here would scale a chip
        # drawn on a wider stage without saying so
        print("FAIL field: the report has no `field stage` line, so the width the "
              "spawn rule drew x in is unknown; 375 px is not assumed")
        ok = False
    if args.live and sp:
        floor = spread_floor(sp["n"])
        if floor is not None and sp["spread"] < floor:
            print("FAIL field: spawner x spread %.2f of the %g px stage with %d live "
                  "(floor %.2f), the rule is uniform over it"
                  % (sp["spread"], st["width"], sp["n"], floor))
            ok = False

    # the spread is one third of the rule: a particle also has to start past the
    # stage, cross it linearly for its own lifetime, draw at a random scale and
    # play its symbol at the movie's frame rate, and none of that is in the x
    if args.live and field:
        symbols = (data.get("clips") or {}).get("particles") or []
        export = {"fps": data.get("fps"),
                  "frames": [len(p.get("art") or []) for p in symbols if p.get("art")]}
        if st is not None:
            print_rule(report, st, export)
        for why in rule_problems(report, st, export):
            print("FAIL rule: " + why)
            ok = False

    # a chip that also draws a backdrop (153, 1133) has that art in the same
    # capture, so measuring "particles" there would count the backdrop instead --
    # unless the run hid it, which `backdrop_of` knows from the report
    backdrop = backdrop_of(report)

    stage = os.path.join(os.path.dirname(report), "stage.png")
    if backdrop:
        print("capture: skipped, the prefab also draws %s" % backdrop)
    elif os.path.exists(stage):
        # a live stream's art may be outlined rather than white (152's bubbles),
        # so the stream measurement masks anything off the backdrop; the capture's
        # pixels scale with the stage and margin the run reported
        shape, margin = capture_args(st)
        m = measure_capture(stage, stream=args.live, stage=shape, margin=margin)
        if m and m.get("count"):
            centre = ("" if "dy_centre" not in m else
                      ", group centre %+.3f body heights" % (m["dy_centre"] / m["height"]))
            # a held capture is measured as a drawing (`measure`), which has no
            # stage fraction; only the stream path scales it against the stage
            frac = ("%.2f of the stage" % m["stage"]) if m.get("stage") is not None \
                else "not scaled (a held drawing)"
            print("capture: %d blob(s), x spread %s%s" % (m["count"], frac, centre))
            if args.live:
                if m["count"] < paint_floor:
                    print("FAIL capture: %d blobs on stage, the held pose alone draws %d"
                          % (m["count"], held))
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
