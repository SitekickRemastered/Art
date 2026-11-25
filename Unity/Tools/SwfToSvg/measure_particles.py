#!/usr/bin/env python3
"""Body-relative measurement of a spawned particle effect.

    python3 Tools/SwfToSvg/measure_particles.py IMAGE [IMAGE ...]
    python3 Tools/SwfToSvg/measure_particles.py --stream --stage 375x300 \
        --margin 1.1 Logs/chip_0151_play_live/stage.png

The body is the Sitekick shell (`measure_placement.masks`: the white/bone shell
in Unity, the flat black disc Ruffle draws on its olive stage).  Particles are
the light blobs clear of the body's columns -- the flake and bubble art is
white -- and are reported three ways, because a spawned effect has no single
placement to compare:

  * the group's centre against the body's centre and bottom edge, normalised by
    body height so captures at any zoom compare (this is the number the chip 151
    offset fix was judged on: -0.053 body heights at the pivot, +0.140 at the
    stage centre);
  * the count and the mean blob height in SWF px, which is what a real stream
    has and the baked four-copy stand-in did not;
  * the x spread of the blobs, as a fraction of the effect's own stage (and by
    body width).  `FlakeMC.init` puts x at `Math.random() * stageWidth`, i.e.
    uniform across the whole stage, so a stream's blobs run from the left edge
    to the right one; four fixed columns sit at four x values and read 0.
    Neither the stage nor the capture's framing margin is assumed here: a
    `stage.png` is `ChipPlayCheck --stage`'s capture, so the stage (SWF px) and
    the margin it framed with are passed in (`--stage WxH --margin M` on the
    command line), and the stage fraction is reported only when they are.

Blob scale is reported as height only: the SWF randomises `scaleX = scaleY`, so
height and width agree, and height survives a blob clipped at the stage edge.

This is the tracked version of the `Logs/skcomp/measure_flakes.py` scratch the
chip 151 check was built with; `Logs/` is gitignored, so the convention lives
here.
"""

import sys

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, 'Tools/SwfToSvg')
from measure_placement import masks, biggest, bbox  # noqa: E402

# 1 SWF px, in the units the effect json uses (build_prefabs.U)
U = 0.01735


def measure(path, light_threshold=170, min_blob=8, max_blob=2000):
    im, bg, pink, rain, shell, black, ink = masks(path)
    # the browser panel paints a Freebuff badge in the corner; it is not art
    im = im.copy()
    im[0:36, 0:76] = im[200, 200]
    body = biggest(ink)
    bb = bbox(body)
    if bb is None:
        print(f'{path}: no body blob')
        return None
    bx0, by0, bx1, by1 = [int(v) for v in bb]
    height, width = by1 - by0, bx1 - bx0
    bcx, bcy = (bx0 + bx1) / 2.0, (by0 + by1) / 2.0

    # the particle art is white; its edges blend into the olive stage, so take
    # anything clearly lighter than the background rather than pure white only
    light = (im > light_threshold).all(axis=2) & ~ndimage.binary_dilation(body, iterations=3)
    lab, n = ndimage.label(light)
    sizes = ndimage.sum(light, lab, range(1, n + 1))
    keep = [i + 1 for i, s in enumerate(sizes) if min_blob <= s <= max_blob]

    blobs = []
    for k in keep:
        ys, xs = np.nonzero(lab == k)
        if xs.min() >= bx0 - 8 and xs.max() <= bx1 + 8:
            continue           # inside the body's columns: the Sitekick's own highlights
        blobs.append((xs.min(), ys.min(), xs.max(), ys.max()))

    print(f'{path}  {im.shape[1]}x{im.shape[0]}')
    print(f'  body bbox ({bx0},{by0})-({bx1},{by1})  size {width}x{height}'
          f'  centre ({bcx:.1f},{bcy:.1f})')
    if not blobs:
        print('  no particle blobs outside the body')
        return dict(path=path, body=bb, height=height, blobs=[])

    fx0 = min(b[0] for b in blobs)
    fy0 = min(b[1] for b in blobs)
    fx1 = max(b[2] for b in blobs)
    fy1 = max(b[3] for b in blobs)
    fy = (fy0 + fy1) / 2.0
    heights = [b[3] - b[1] for b in blobs]
    centres = [(b[0] + b[2]) / 2.0 for b in blobs]
    px_per_swf = height / 58.0          # body height is 58 SWF px on the rule sheet
    print(f'  particles bbox ({fx0},{fy0})-({fx1},{fy1})  {len(blobs)} blob(s)'
          f'  mean height {np.mean(heights):.1f} px'
          f' ({np.mean(heights) / px_per_swf:.1f} SWF px)')
    print(f'  group centre - body centre  {fy-bcy:+.1f}px  normalised {(fy-bcy)/height:+.4f}')
    print(f'  group centre - body bottom  {fy-by1:+.1f}px  normalised {(fy-by1)/height:+.4f}')
    print(f'  x spread {fx1-fx0}px = {(fx1-fx0)/width:.3f} body widths'
          f'  mean x {(np.mean(centres)-bcx)/width:+.3f} body widths')
    if len(blobs) > 1:
        print(f'  x stdev {np.std(centres)/width:.3f} body widths')
    return dict(path=path, body=bb, height=height, blobs=blobs,
                dy_centre=fy - bcy, dy_bottom=fy - by1,
                count=len(blobs), spread_px=fx1 - fx0,
                spread=(fx1 - fx0) / width, mean_x=(np.mean(centres) - bcx) / width)


# `stage.png` is the effect's own stage with `capture margin` around it
# (`ChipPlayCheck.Capture` frames `StageBounds * CaptureMargin` into 1440x1080),
# so the capture's height covers `stage height * margin` SWF px and one scale
# serves both axes.  Both numbers come from the chip -- the report line
# `field stage 375 x 300 px  capture margin 1.10` -- because a chip drawn on a
# wider stage would otherwise be scaled against a constant
# (`particle_check.spawn_stage`).


def measure_stream(path, stage=None, margin=1.1,
                   distance=12, min_blob=20, max_blob=40000):
    """Measure a live stream, whatever colour its art is.

    Snow is white and shows up in `measure`, but chip 152's bubbles are dark
    outlines with a grey fill, so a colour threshold cannot find them on the
    gallery's dark backdrop.  This masks anything that differs from the flat
    background, closes each outline into a solid blob, drops the Sitekick and
    reports the same shape of numbers.

    `stage` is the effect's (width, height) in SWF px and `margin` the factor
    the capture was framed with; the stage fraction needs both, so it is left
    out of the result (and the report) when they are not given.
    """
    im, bg, pink, rain, shell, black, ink = masks(path)
    im = im.copy()
    im[0:36, 0:76] = im[200, 200]
    arr = im.astype(np.int16)
    border = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]])
    back = np.median(border, axis=0)
    diff = np.abs(arr - back).max(axis=2)
    body = biggest(ink)
    keep_off = ndimage.binary_dilation(body, iterations=4)

    blob = (diff > distance) & ~keep_off
    blob = ndimage.binary_closing(blob, structure=np.ones((3, 3)), iterations=2)
    lab, n = ndimage.label(blob)
    sizes = ndimage.sum(blob, lab, range(1, n + 1))
    keep = [i + 1 for i, s in enumerate(sizes) if min_blob <= s <= max_blob]

    bb = bbox(body)
    bx0, by0, bx1, by1 = [int(v) for v in bb]
    height, width = by1 - by0, bx1 - bx0
    bcx = (bx0 + bx1) / 2.0
    blobs = []
    for k in keep:
        ys, xs = np.nonzero(lab == k)
        blobs.append((xs.min(), ys.min(), xs.max(), ys.max()))

    print(f'{path}  {im.shape[1]}x{im.shape[0]}  (stream)')
    print(f'  body bbox ({bx0},{by0})-({bx1},{by1})  size {width}x{height}')
    if not blobs:
        print('  no particles found')
        return dict(path=path, body=bb, height=height, blobs=[], count=0)
    fx0 = min(b[0] for b in blobs)
    fx1 = max(b[2] for b in blobs)
    centres = [(b[0] + b[2]) / 2.0 for b in blobs]
    heights = [b[3] - b[1] for b in blobs]
    print(f'  {len(blobs)} particle blob(s)  mean height {np.mean(heights):.1f} px'
          f'  sizes {min(heights)}..{max(heights)} px')
    back = (f'  ({(fx1-fx0)/width:.3f} body widths, mean x {(np.mean(centres)-bcx)/width:+.3f},'
            f' stdev {np.std(centres)/width:.3f})')
    frac = None
    if stage:
        if not margin:
            raise ValueError("measure_stream: `stage` needs the `margin` the capture "
                             "was framed with (ChipPlayCheck reports both)")
        px_per_swf = im.shape[0] / (float(stage[1]) * margin)
        frac = (fx1 - fx0) / (float(stage[0]) * px_per_swf)
        print(f'  x spread {fx1-fx0}px = {frac:.3f} of the {float(stage[0]):g} x'
              f' {float(stage[1]):g} SWF px stage' + back)
    else:
        print(f'  x spread {fx1-fx0}px  (no stage given: --stage WxH for the fraction)' + back)
    return dict(path=path, body=bb, height=height, blobs=blobs, count=len(blobs),
                stage=frac, spread=(fx1 - fx0) / width,
                mean_x=(np.mean(centres) - bcx) / width,
                stdev=np.std(centres) / width)


if __name__ == '__main__':
    stream = '--stream' in sys.argv
    stage, margin = None, 1.1
    args = sys.argv[1:]
    images = []
    for i, a in enumerate(args):
        if a == '--stage' and i + 1 < len(args):
            w, h = args[i + 1].lower().split('x')
            stage = (float(w), float(h))
        elif a == '--margin' and i + 1 < len(args):
            margin = float(args[i + 1])
        elif not a.startswith('--') and not (i and args[i - 1] in ('--stage', '--margin')):
            images.append(a)
    for p in images:
        if stream:
            measure_stream(p, stage=stage, margin=margin)
        else:
            measure(p)
        print()
