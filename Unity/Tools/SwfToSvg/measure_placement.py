"""Measure where a chip effect's art sits relative to the Sitekick, in SWF px.

The Ruffle capture of the composite is 1:1 (1 image px = 1 SWF px); the Unity
gallery capture is auto-framed at an unknown zoom, so both are reduced to the
same body-relative measure:

    body   = the Sitekick shell (largest blob of shell ink)
    cloud  = the effect's mid-pink (the largest pink blob)

and the result is the cloud centre relative to the body's bottom edge, divided
by the body's height so the capture's zoom cancels out.

    python3 Tools/SwfToSvg/measure_placement.py IMAGE [IMAGE ...]
"""

import sys

import numpy as np
from PIL import Image
from scipy import ndimage

PINK = (212, 130, 185)
RAIN = (0, 37, 88)


def masks(path):
    im = np.asarray(Image.open(path).convert("RGB")).astype(np.int16)
    colours, counts = np.unique(im.reshape(-1, 3), axis=0, return_counts=True)
    bg = colours[counts.argmax()]

    def near(c, t):
        return (np.abs(im - np.array(c, dtype=np.int16)) <= t).all(axis=2)

    pink = near(PINK, (26, 26, 22))
    rain = near(RAIN, (18, 18, 18))
    # shell ink: the Sitekick's white shell and its bone shadow (the unpainted
    # Ruffle body is flat black, so black is shell ink there too)
    shell = (near((255, 255, 255), (12, 12, 12)) | near((178, 147, 147), (18, 18, 18))
             | near((213, 193, 193), (18, 18, 18)))
    black = near((0, 0, 0), (40, 40, 40))
    return im, bg, pink, rain, shell, black, body_ink(bg, shell, black)


def body_ink(bg, shell, black):
    """The Sitekick body: its white shell in Unity, the flat black disc that

    Ruffle draws when the host's paint() is missing (the olive stage)."""
    olive = bg[2] < 40 and bg[0] > 100  # bright and blue-free: the stage colour
    return black if olive else shell


def biggest(mask):
    lab, n = ndimage.label(mask)
    if not n:
        return None
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    keep = int(sizes.argmax()) + 1
    return lab == keep


def bbox(mask):
    if mask is None:
        return None
    ys, xs = np.nonzero(mask)
    if not len(ys):
        return None
    return xs.min(), ys.min(), xs.max(), ys.max()


def report(path):
    im, bg, pink, rain, shell, black, ink = masks(path)
    body = biggest(ink)
    body_bb = bbox(body)
    cloud = biggest(pink)
    cloud_bb = bbox(cloud)
    if body_bb is None or cloud_bb is None:
        print(f"{path}: body={body_bb} cloud={cloud_bb}")
        return None
    bx0, by0, bx1, by1 = body_bb
    cx0, cy0, cx1, cy1 = cloud_bb
    height = by1 - by0
    cloud_c = ((cx0 + cx1) / 2.0, (cy0 + cy1) / 2.0)
    body_c = ((bx0 + bx1) / 2.0, (by0 + by1) / 2.0)
    rain_bb = bbox(rain)
    print(f"{path}  {im.shape[1]}x{im.shape[0]}  bg={tuple(int(v) for v in bg)}")
    print(f"  body bbox {body_bb}  size {bx1-bx0}x{height}  centre {body_c}")
    if rain_bb:
        print(f"  rain height {rain_bb[3]-rain_bb[1]}px")
    print(f"  cloud bbox {cloud_bb}  size {cx1-cx0}x{cy1-cy0}  centre {cloud_c}")
    if rain_bb:
        print(f"  rain bbox {rain_bb}")
    print(f"  cloud centre - body bottom   dx {cloud_c[0]-body_c[0]:+.1f}px  "
          f"dy {cloud_c[1]-(by0+height):+.1f}px   (body height {height}px)")
    print(f"  normalised  dx {((cloud_c[0]-body_c[0])/height):+.4f}  "
          f"dy {((cloud_c[1]-(by0+height))/height):+.4f}   (body height in {path.split('/')[-1]})")
    return dict(path=path, height=height, dx=cloud_c[0] - body_c[0],
                dy=cloud_c[1] - (by0 + height),
                cloud_h=cy1 - cy0, cloud_w=cx1 - cx0)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        report(p)
        print()
