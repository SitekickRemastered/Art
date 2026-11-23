#!/usr/bin/env python3
"""Render a chip movie frame-by-frame in Ruffle and diff it against the export.

The reference for a chip's animation is Ruffle, not FFDec (see AGENTS.md), but
Ruffle's web player has no frame-stepping API, so a recording only samples the
loop.  This script instead freezes the movie: for each frame N it writes a copy
of the patched SWF

  * whose root timeline keeps frames 1..N and stops there, and
  * whose every child clip is cut to the state it is showing at root frame N
    and stops there.

That is exactly the playstate FFDec exports for frame N (same lockstep
advance, same looping of short clips), so a Ruffle render of that copy can be
compared with the exported `frame_NNN.svg` pixel for pixel.  Root and clip
frame scripts are dropped: their art effects are authored into the SWF by
`patch_chip8_tools.py`, and dropping them keeps Ruffle from pausing on frame 1
or hiding the movie.

    # build, capture and diff in one go
    ruffle_frames.py Temp/swftosvg/0008/chip_0008_tools.xml \
        --out Temp/swftosvg/review/c0008 --frames 45-61 --capture --cols 5

    # or do the two halves by hand
    ruffle_frames.py <patched.xml> --out /tmp/chip8-frames --frames 1-71
    # then open Tools/SwfToSvg/ruffle_frames.html?base=/frames/f&from=1&count=24
    ruffle_frames.py --diff Logs/ruffle-frames-1.png --first-frame 1

`--capture` drives the grid itself: it serves the SWF folder and the page on a
loopback port, runs a headless Chromium-family browser with `--screenshot`, and
diffs the saved grids.  That is the path to trust when the Freebuff window is
minimised: the page's own `post` composite grabs whatever each player happened
to have painted, so an undrawn window returns duplicate tiles (a 16-tile page
came back as 9 identical tiles and 7 identical ones), which reads as a clean
frame.  Headless drawing does not depend on anything being on screen.

The browser needs two flags that are easy to lose: `--autoplay-policy=
no-user-gesture-required` (headless Chromium blocks playback that produces
audio, and these movies carry sound cues, so Ruffle never leaves its
click-to-play overlay: the screenshot is a grid of play buttons) and
`--mute-audio` (the same sound cues at full volume).  `--force-device-scale-
factor=1` keeps a tile exactly 375x300 so the pixel maths below holds.

Screenshots are tiles of 375x300 laid out in a row-major grid of `--cols`
columns (default 5).  The exported SVG is drawn at one SVG unit per SWF pixel
and pasted at its own viewBox origin, so the comparison is in stage pixels.
Ruffle does not render a player that is outside the viewport, so `--rows`
decides how many 300 px rows fit in the window; longer ranges are captured in
several pages.
"""

import argparse
import copy
import os
import shutil
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from lxml import etree

SHOW = "ShowFrameTag"
STOP = "0700"          # ActionStop, end-of-actions
FFDEC = ("flatpak", "run", "--command=ffdec.sh", "com.jpexs.decompiler.flash")

# tag types that belong to the file rather than to a timeline frame
FILE_TAGS = ("SetBackgroundColorTag", "ProtectTag", "SoundStreamHead2Tag",
             "SoundStreamHeadTag", "FileAttributesTag", "MetadataTag",
             "ExportAssetsTag", "ScriptLimitsTag", "EnableDebugger2Tag",
             "EnableDebuggerTag", "DefineSceneAndFrameLabelDataTag")


def is_file_tag(tag):
    t = tag.get("type", "")
    return t.startswith("Define") or t in FILE_TAGS


def frames_of(item):
    """The sprite's frames, each a list of its tags without the ShowFrameTag."""
    frames, current = [], []
    for sub in item.find("subTags"):
        if sub.get("type") == SHOW:
            frames.append(current)
            current = []
        else:
            current.append(sub)
    if current:
        frames.append(current)
    return frames


def stop_tag():
    return etree.Element("item", type="DoActionTag", actionBytes=STOP,
                         forceWriteAsLong="false")


def freeze_sprite(item, playhead, placed_on=1, merge=False):
    """Cut one sprite to the drawing it shows at `playhead`, and hold it there.

    A clip no script jumps is kept as a timeline cut to the frames it has
    played since it was placed, stopped on the last one: `playhead` is the
    root frame it is being built for, and a copy placed on root 13 is 18
    frames old on root 30.  Ruffle then advances the copy from the frame it is
    placed on, exactly as FFDec does, so cutting it to the root frame number
    instead would let a clip that loops inside itself carry on to a pose the
    movie never shows.

    A clip a script jumps (`merge`) is the opposite: the jump selects an
    absolute pose -- `gotoAndPlay("retract2")` is frame 53 whether or not the
    root has played that far -- so the frames up to the playhead are merged
    into one (a sprite's timeline is incremental: later frames only carry the
    tags that changed, so replaying them in order without the ShowFrames
    between them is exactly the display list of frame `playhead`).  One frame
    also means the hold does not depend on when the clip was placed or on its
    placement ratio, so a frozen arm can show its frame 53 on root frame 33.
    """
    frames = frames_of(item)
    if not frames:
        return
    sub = item.find("subTags")
    for child in list(sub):
        sub.remove(child)

    def art(frame):
        return [tag for tag in frame if tag.get("type") != "DoActionTag"]

    show = etree.Element("item", type=SHOW, forceWriteAsLong="false")
    if merge:
        keep = (playhead - 1) % len(frames) + 1
        for frame in frames[:keep]:
            for tag in art(frame):
                sub.append(copy.deepcopy(tag))
        sub.append(show)
        return
    keep = max(1, min(playhead - placed_on + 1, len(frames)))
    for n, frame in enumerate(frames[:keep], 1):
        for tag in art(frame):
            sub.append(copy.deepcopy(tag))
        if n == keep:
            sub.append(stop_tag())
        sub.append(copy.deepcopy(show))


def freeze_root(root, frame):
    tags = root.find("tags")
    out, seen = [], 0
    for child in list(tags):
        if is_file_tag(child):
            out.append(child)
            continue
        if child.get("type") == SHOW:
            seen += 1
            if seen <= frame:
                if seen == frame:
                    out.append(stop_tag())
                out.append(child)
            continue
        if seen + 1 > frame:
            continue
        if child.get("type") == "DoActionTag":
            continue
        out.append(child)
    for child in list(tags):
        tags.remove(child)
    for child in out:
        tags.append(child)
    root.set("frameCount", str(frame))


def sprite_by_id(tags, sid):
    for item in tags:
        if item.get("type") == "DefineSpriteTag" and int(item.get("spriteId")) == sid:
            return item
    raise SystemExit("no sprite %d in the XML" % sid)


def sprite_labels(item):
    """frame label -> frame number, for one sprite."""
    out = {}
    for n, frame in enumerate(frames_of(item), 1):
        for tag in frame:
            if tag.get("type") == "FrameLabelTag":
                out[tag.get("name")] = n
    return out


def parse_playheads(xml_path, specs):
    """`SPRITE=LABEL@ROOT,...` -> {sprite: [(root frame, label frame), ...]}."""
    tree = etree.parse(xml_path)
    tags = tree.getroot().find("tags")
    out = {}
    for spec in specs:
        sid, sep, rest = spec.partition("=")
        if not sep:
            raise SystemExit("--playhead wants SPRITE=LABEL@FRAME,...: %r" % spec)
        table = sprite_labels(sprite_by_id(tags, int(sid)))
        events = []
        for part in rest.split(","):
            label, sep, at = part.partition("@")
            if not sep:
                raise SystemExit("--playhead event wants LABEL@FRAME[!]: %r" % part)
            label = label.strip()
            hold = label.endswith("!")        # gotoAndStop instead of gotoAndPlay
            label = label.rstrip("!").strip()
            if label.isdigit():
                # a bare number is a frame, for clips the script jumps by
                # number (bottom.gotoAndStop(2)) rather than by label
                events.append((int(at), int(label), hold))
                continue
            if label not in table:
                raise SystemExit("sprite %s has no label %r (has %s)"
                                 % (sid, label, ", ".join(sorted(table))))
            events.append((int(at), table[label], hold))
        out[int(sid)] = sorted(events)
    return out


def scripted_playhead(events, frame):
    """Where `gotoAndPlay(label)` at root frame F leaves a clip.

    The script jumps to a label and the clip plays on from there, so on root
    frame N the clip shows `label_frame + (N - F)` for the last jump F <= N.
    Before the first jump the clip keeps its own straight playhead.
    """
    playhead = frame
    for at, label_frame, hold in events:
        if frame >= at:
            playhead = label_frame if hold else label_frame + (frame - at)
    return playhead


def placements(item_or_tags):
    """Characters this timeline places itself, in order."""
    return [sid for sid, _ in placements_with_frame(item_or_tags)]


def placements_with_frame(item_or_tags):
    """(character, frame) for every placement in one timeline, in order."""
    container = (item_or_tags.find("subTags")
                 if item_or_tags.get("type") == "DefineSpriteTag" else item_or_tags)
    out, n = [], 0
    for sub in container:
        if sub.tag != "item":
            continue
        if sub.get("type") == SHOW:
            n += 1
            continue
        if (sub.get("type", "").startswith("PlaceObject")
                and sub.get("characterId")):
            out.append((int(sub.get("characterId")), n + 1))
    return out


def freeze_tree(tags, frame, playheads):
    """Freeze every displayed clip at the playhead it is showing at `frame`.

    A clip advances in lockstep with its parent, so the playhead of a clip the
    script jumped is inherited by the clips inside it: when `tools` sits on its
    frame 25, the hands it holds are on theirs, not on the root's frame.  That
    only matters when --playhead moves something; for a plain lockstep build
    every playhead is the root frame anyway.
    """
    sprites = {int(item.get("spriteId")): item for item in tags
               if item.get("type") == "DefineSpriteTag"}

    def state(sid, inherited, placed_on):
        """(frame to show, frame it was placed on, whether a script picked it)."""
        events = (playheads or {}).get(sid)
        if events:
            return scripted_playhead(events, frame), 1, True
        # a clip inheriting the pose of a jumped parent sits where the jump put
        # it, not where its own timeline has played to
        return inherited, placed_on, inherited > frame

    pending = [(sid,) + state(sid, frame, on) for sid, on in placements_with_frame(tags)
               if sid in sprites]
    walked = set()
    while pending:
        sid, at, on, merge = pending.pop()
        item = sprites[sid]
        # a clip can be placed more than once; each placement freezes the
        # shared definition for its own age, and the last one visited holds
        freeze_sprite(item, at, on, merge)
        key = (sid, at, on)
        if key in walked:
            continue
        walked.add(key)
        pending.extend((child,) + state(child, at, on2)
                       for child, on2 in placements_with_frame(item)
                       if child in sprites)


def build(xml_path, out_swf, frame, workdir, playheads=None):
    tree = etree.parse(xml_path)
    root = tree.getroot()
    tags = root.find("tags")
    freeze_tree(tags, frame, playheads)
    freeze_root(root, frame)
    os.makedirs(workdir, exist_ok=True)
    xml_out = os.path.join(workdir, "f%03d.xml" % frame)
    tree.write(xml_out, encoding="UTF-8", xml_declaration=True)
    subprocess.run(FFDEC + ("-xml2swf", xml_out, out_swf), check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.unlink(xml_out)
    return out_swf


def parse_region(text):
    """`X,Y,W,H` -> (x, y, w, h), or None."""
    if not text:
        return None
    x, y, w, h = (int(v) for v in text.split(","))
    return x, y, w, h


def region_slices(region):
    x, y, w, h = region
    return slice(y, y + h), slice(x, x + w)


def parse_range(text):
    out = []
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out


def stage_of(svg_path):
    """(vx, vy, vw, vh, stage_w, stage_h) for an exported frame."""
    root = etree.parse(svg_path).getroot()
    vx, vy, vw, vh = (float(v) for v in root.get("viewBox").split())
    return vx, vy, vw, vh


def diff_page(page, first_frame, movie_dir, stage, cols, badge=(175, 48),
              count=None, verbose=True, region=None):
    """Compare one grid screenshot's tiles against the exported frames.

    `count` limits the comparison to the tiles a capture actually asked for:
    the last page of a range can be short, and a tile beyond it would be
    compared against a real exported frame and read as a huge error.
    """
    import numpy as np
    from PIL import Image

    sw, sh = stage
    worst = []
    shot = Image.open(page).convert("RGB")
    rows = shot.height // sh
    tiles = rows * cols if count is None else min(rows * cols, count)
    for n in range(tiles):
        frame = first_frame + n
        svg = os.path.join(movie_dir, "frame_%03d.svg" % frame)
        if not os.path.exists(svg):
            continue
        vx, vy, vw, vh = stage_of(svg)
        w, h = max(1, int(round(vw))), max(1, int(round(vh)))
        png = page.replace(".png", "-f%03d-svg.png" % frame)
        subprocess.run(["rsvg-convert", "-w", str(w), "-h", str(h), svg, "-o", png],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        art = Image.open(png).convert("RGBA")
        os.unlink(png)

        r = n // cols
        c = n % cols
        tile = shot.crop((c * sw, r * sh, c * sw + sw, r * sh + sh))
        arr = np.array(tile, dtype=np.int16)
        bg = arr[0, 0]
        paper = np.abs(arr - bg).max(axis=2) < 8

        # Ruffle paints the SWF's stage colour behind the art and the page has
        # a floating badge over the first tile: put both on white paper, like
        # the export (which has no background at all).
        arr[paper] = 255
        if n == 0:
            arr[:badge[1], :badge[0]] = 255

        canvas = Image.new("RGBA", (sw, sh), (255, 255, 255, 255))
        canvas.paste(art, (int(round(-vx)), int(round(-vy))), art)
        mine_g = np.asarray(canvas.convert("L"), dtype=np.int16)
        ink = np.asarray(canvas.split()[3], dtype=np.int16) > 0

        ruffle_g = np.asarray(Image.fromarray(arr.astype(np.uint8)).convert("L"),
                              dtype=np.int16)
        if region:
            ys, xs = region_slices(region)
            mine_g, ruffle_g, ink = mine_g[ys, xs], ruffle_g[ys, xs], ink[ys, xs]
        d = np.abs(mine_g - ruffle_g)
        mask = ink | (ruffle_g < 250)
        err = float(d[mask].mean()) if mask.any() else 0.0
        worst.append((err, frame, float(d[mask].max()) if mask.any() else 0.0))
    worst.sort(reverse=True)
    if verbose:
        for err, frame, top in worst[:10]:
            print("frame %3d  mean %6.2f/255  worst pixel %3.0f/255" % (frame, err, top))
        print("frames compared: %d  mean %.2f  worst %.2f" %
              (len(worst), sum(w[0] for w in worst) / max(1, len(worst)),
               worst[0][0] if worst else 0.0))
    return worst


# ---------------------------------------------------------------------------
# headless capture
# ---------------------------------------------------------------------------

# the Art tree holds the grid page; the frozen SWFs may live anywhere
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
GRID_PAGE = "/Unity/Tools/SwfToSvg/ruffle_frames.html"
FRAME_ROUTE = "/frames/"


def serve(frames_dir):
    """Serve the Art tree at `/` and `frames_dir` at `/frames/`, on a free port."""
    root = ROOT

    class Handler(SimpleHTTPRequestHandler):
        def translate_path(self, path):
            path = path.split("?", 1)[0].split("#", 1)[0]
            if path.startswith(FRAME_ROUTE):
                base, rel = frames_dir, path[len(FRAME_ROUTE):]
            else:
                base, rel = root, path.lstrip("/")
            parts = [p for p in rel.split("/") if p not in ("", ".", "..")]
            return os.path.join(base, *parts)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def browser_command(explicit=None):
    """The Chromium-family browser to drive, or a clear reason there is none."""
    if explicit:
        return explicit.split()
    if shutil.which("flatpak"):
        found = subprocess.run(["flatpak", "info", "com.brave.Browser"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if found.returncode == 0:
            return ["flatpak", "run", "com.brave.Browser"]
    for name in ("chromium", "chromium-browser", "google-chrome",
                 "google-chrome-stable", "brave-browser", "microsoft-edge"):
        path = shutil.which(name)
        if path:
            return [path]
    raise SystemExit("no Chromium-family browser found; pass --browser '<command>'")


def capture_page(browser, url, shot, width, height, budget):
    """Headless screenshot of the grid page, sized to the tiles it must show."""
    if os.path.exists(shot):
        os.unlink(shot)
    cmd = list(browser) + [
        "--headless=new", "--disable-gpu", "--no-sandbox",
        # these movies carry sound cues: without this the player never autoplays
        "--autoplay-policy=no-user-gesture-required",
        "--mute-audio",
        "--force-device-scale-factor=1", "--hide-scrollbars",
        "--window-size=%d,%d" % (width, height),
        "--virtual-time-budget=%d" % budget,
        "--screenshot=" + shot, url,
    ]
    run = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if not os.path.exists(shot):
        raise SystemExit("browser wrote no screenshot: %s" % (run.stderr or "").strip()[-400:])
    return shot


def cross_pages(page_a, page_b, first_frame, cols, count=None, region=None, verbose=True):
    """Compare two grid captures tile by tile: the harness floor, in-region.

    Same input twice gives the noise floor of the capture + diff pipeline;
    two different SWFs give the difference between them.
    """
    import numpy as np
    from PIL import Image

    a = Image.open(page_a).convert("RGB")
    b = Image.open(page_b).convert("RGB")
    rows = min(a.height, b.height) // 300
    tiles = rows * cols if count is None else min(rows * cols, count)
    ys, xs = region_slices(region) if region else (slice(None), slice(None))
    out = []
    for n in range(tiles):
        r, c = divmod(n, cols)
        box = (c * 375, r * 300, c * 375 + 375, r * 300 + 300)
        ga = np.asarray(a.crop(box).convert("L"), dtype=np.int16)
        gb = np.asarray(b.crop(box).convert("L"), dtype=np.int16)
        d = np.abs(ga - gb)
        out.append((float(d[ys, xs].mean()), first_frame + n, float(d.mean())))
        if verbose:
            print("frame %3d  whole %6.2f  region %6.2f"
                  % (first_frame + n, out[-1][2], out[-1][0]))
    if verbose:
        print("frames: %d  region mean %.2f  worst %.2f  whole mean %.2f"
              % (len(out), sum(o[0] for o in out) / max(1, len(out)),
                 max(o[0] for o in out), sum(o[2] for o in out) / max(1, len(out))))
    return out


def capture(xml, out, frames, cols, rows, shot_dir, budget, movie, browser=None,
            reuse=False, playheads=None, region=None):
    """Build the frozen SWFs, screenshot them in pages, and diff every frame."""
    from PIL import Image

    if frames != list(range(frames[0], frames[-1] + 1)):
        raise SystemExit("--capture needs one contiguous range, e.g. 45-71")
    os.makedirs(out, exist_ok=True)
    os.makedirs(shot_dir, exist_ok=True)
    for frame in frames:
        path = os.path.join(out, "f%03d.swf" % frame)
        if playheads or not (reuse and os.path.exists(path)):
            build(xml, path, frame, out, playheads)

    server, port = serve(out)
    worst_all = []
    try:
        per_page = cols * rows
        for start in range(0, len(frames), per_page):
            chunk = frames[start:start + per_page]
            first, count = chunk[0], len(chunk)
            shown_rows = (count + cols - 1) // cols
            width, height = cols * 375, shown_rows * 300
            url = ("http://127.0.0.1:%d%s?base=%sf&from=%d&count=%d&cols=%d"
                   "&renderer=canvas&raf=timer" % (port, GRID_PAGE, FRAME_ROUTE, first, count, cols))
            shot = os.path.join(shot_dir, "frames-%03d-%03d.png" % (first, chunk[-1]))
            capture_page(browser, url, shot, width, height, budget)
            # exactly the grid: a taller window would leave diff_page reading
            # rows the page never filled
            img = Image.open(shot)
            if img.size != (width, height):
                img.convert("RGB").crop((0, 0, width, height)).save(shot)
            print("captured %s  (%d frames, %d cols)" % (shot, count, cols))
            worst_all += diff_page(shot, first, movie, (375, 300), cols,
                                   count=count, verbose=False, region=region)
    finally:
        server.shutdown()

    print("\nper-frame diff against %s%s"
          % (movie, " in %s" % (region,) if region else ""))
    for err, frame, top in sorted(worst_all, key=lambda w: w[1]):
        print("frame %3d  mean %6.2f/255  worst pixel %3.0f/255" % (frame, err, top))
    worst = max(worst_all, default=(0.0, 0, 0.0))
    print("frames compared: %d  mean %.2f  worst %.2f (frame %d)" %
          (len(worst_all), sum(w[0] for w in worst_all) / max(1, len(worst_all)),
           worst[0], worst[1]))
    if len(worst_all) != len(frames):
        print("note: %d of %d frames have no exported frame_NNN.svg and were skipped"
              % (len(frames) - len(worst_all), len(frames)))
    return worst_all


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xml", nargs="?")
    ap.add_argument("--out", default="/tmp/chip8-frames")
    ap.add_argument("--frames", default="1-71")
    ap.add_argument("--diff", nargs="*", help="grid screenshots to compare")
    ap.add_argument("--first-frame", default="1",
                    help="frame of the first tile; comma separated per page")
    ap.add_argument("--movie", default="Assets/Chips/0001-0100/Chip_0008/Movie")
    ap.add_argument("--stage", default="375x300")
    ap.add_argument("--cols", type=int, default=5)
    ap.add_argument("--rows", type=int, default=3,
                    help="tile rows per screenshot; Ruffle skips off-screen players")
    ap.add_argument("--capture", action="store_true",
                    help="build, screenshot headlessly and diff in one run")
    ap.add_argument("--shot-dir", default=None, help="where the grid PNGs go (default <out>/shots)")
    ap.add_argument("--budget", type=int, default=20000,
                    help="headless virtual time budget in ms")
    ap.add_argument("--browser", default=None,
                    help="browser command, default: Brave (flatpak) or a Chromium on PATH")
    ap.add_argument("--reuse", action="store_true", help="keep the frozen SWFs already built")
    ap.add_argument("--playhead", action="append", default=[], metavar="SPRITE=LABEL@FRAME,...",
                    help="clips the root script jumps: gotoAndPlay(LABEL) at root FRAME")
    ap.add_argument("--region", default=None, metavar="X,Y,W,H",
                    help="restrict the diff to one rectangle of the stage")
    ap.add_argument("--cross", nargs=2, default=None, metavar=("A", "B"),
                    help="compare two grid captures instead of a capture against the export")
    args = ap.parse_args()

    region = parse_region(args.region)
    if args.cross:
        print("== %s vs %s" % tuple(args.cross))
        cross_pages(args.cross[0], args.cross[1], int(args.first_frame), args.cols,
                    count=len(parse_range(args.frames)), region=region)
        return 0

    if args.diff:
        sw, sh = (int(v) for v in args.stage.split("x"))
        firsts = [int(v) for v in str(args.first_frame).split(",")]
        while len(firsts) < len(args.diff):
            firsts.append(firsts[-1])
        for page, first in zip(args.diff, firsts):
            print("== %s (first frame %d)" % (page, first))
            diff_page(page, first, args.movie, (sw, sh), args.cols, region=region)
        return 0

    if not args.xml:
        ap.error("give the patched XML to build frames from")
    frames = parse_range(args.frames)
    if args.capture:
        playheads = parse_playheads(args.xml, args.playhead)
        capture(args.xml, args.out, frames, args.cols, args.rows,
                args.shot_dir or os.path.join(args.out, "shots"), args.budget,
                args.movie, browser_command(args.browser), args.reuse,
                playheads, region)
        return 0
    os.makedirs(args.out, exist_ok=True)
    for frame in frames:
        out = os.path.join(args.out, "f%03d.swf" % frame)
        build(args.xml, out, frame, args.out)
        print(out, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
