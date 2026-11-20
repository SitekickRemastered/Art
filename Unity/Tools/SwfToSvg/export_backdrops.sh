#!/usr/bin/env bash
# Export the art the background chips draw *besides* their own effect symbol.
#
# A background chip's effect class is a shell:
#
#     var _loc1_:Class = getDefinitionByName("Back_161") as Class;
#     backClip = new _loc1_();
#
# and the weekday mini-game chips (1-6, `extends GameEffect`) have no library
# art at all -- their effect is a standalone movie, `Old Chips/Effects/chip_0001.swf`,
# a 375x300 stage that plays a 51-frame boot screen at 12 fps.
#
# The earlier pipeline only followed `backClip = new X()` written literally, so
# chip 161 (which assigns through `_loc1_`) and chips 1-6 (GameEffect) ended up
# with empty prefabs.  This script exports what those chips need:
#
#   Assets/Chips/Backdrops/Boot/chip_boot_fNN.svg   the shared 1-6 movie, 51 frames
#   Assets/Chips/0101-0200/Chip_0161/Sprites/chip_0161_back.svg / _front.svg
#
# Usage: bash Tools/SwfToSvg/export_backdrops.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
SRC="$ROOT/../Source/Chip Libraries/Old Chips/Effects"
FFDEC=(flatpak run --command=ffdec.sh com.jpexs.decompiler.flash)
# keep the scratch dir inside the project: the FFDec flatpak has its own /tmp
TMP="$ROOT/Temp/backdrops"

rm -rf "$TMP"
mkdir -p "$TMP/boot" "$TMP/s161"

echo "exporting the 1-6 boot movie"
"${FFDEC[@]}" -format frame:svg -export frame "$TMP/boot" "$SRC/chip_0001.swf" >/dev/null

echo "exporting Back_161 / Front_161"
"${FFDEC[@]}" -selectid 753,707 -format sprite:svg -export sprite "$TMP/s161" \
	"$ROOT/SWF/effectlibrary1_250.swf" >/dev/null

mkdir -p "$ROOT/Assets/Chips/Backdrops/Boot" "$ROOT/Assets/Chips/0101-0200/Chip_0161/Sprites"
rm -f "$ROOT/Assets/Chips/Backdrops/Boot"/chip_boot_f*.svg*
rm -f "$ROOT/Assets/Chips/0101-0200/Chip_0161/Sprites/chip_0161_back.svg"* \
	"$ROOT/Assets/Chips/0101-0200/Chip_0161/Sprites/chip_0161_front.svg"*

python3 - "$ROOT" "$TMP" <<'PY'
import glob, os, re, subprocess, sys, uuid

root, tmp = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(root, "Tools", "SwfToSvg"))
import normalize as N

TEMPLATE = os.path.join(root, "Assets/Chips/0101-0200/Chip_0177/Sprites/chip_0177_back.svg.meta")


def meta(name, ppu):
    """A vector-sprite importer .meta with a fresh guid."""
    txt = open(TEMPLATE, encoding="utf-8").read()
    txt = re.sub(r"^guid: .*$", "guid: " + uuid.uuid4().hex, txt, count=1, flags=re.M)
    txt = re.sub(r"^  spriteData:\n(?:    .*\n)*",
                 "  spriteData:\n    TessellationDetail: 0\n"
                 "    SpriteName: %s\n    SpritePivot: {x: 0.5, y: 0.5}\n" % name,
                 txt, count=1, flags=re.M)
    txt = re.sub(r"^  svgPixelsPerUnit: .*$", "  svgPixelsPerUnit: %s" % ppu, txt, count=1, flags=re.M)
    return txt


def place(src, dst, name, ppu):
    """Normalise then install: FFDec output uses <use>, which Unity's SVG
    importer ignores, so it has to go through the same converter as the rest
    of the chip art. A pattern/bitmap fill (chip 286's overlay) additionally
    has to be rasterised -- the importer draws those as black."""
    N.convert(src, dst, scale=N.SCALE)
    open(dst + ".meta", "w", encoding="utf-8").write(meta(name, ppu))
    body = open(dst, encoding="utf-8").read()
    if "<pattern" in body or "<image" in body:
        png = os.path.splitext(dst)[0] + ".png"
        subprocess.run(["rsvg-convert", "-w", "1600", dst, "-o", png], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        open(png + ".meta", "w", encoding="utf-8").write(png_meta(name))
        print("rasterised", os.path.basename(png))


def png_meta(name):
    """A plain 2D sprite importer .meta for a rasterised piece."""
    return """fileFormatVersion: 2
guid: {guid}
TextureImporter:
  internalIDToNameTable: []
  serializedVersion: 13
  mipmaps:
    mipMapMode: 0
    enableMipMap: 0
  isReadable: 0
  sRGBTexture: 1
  alphaTestReferenceValue: 0.5
  alphaIsTransparency: 1
  spriteMode: 1
  spriteExtrude: 1
  spritePixelsToUnits: 100
  spritePivot: {{x: 0.5, y: 0.5}}
  spriteMeshType: 0
  textureType: 8
  textureShape: 1
  maxTextureSize: 2048
  textureCompression: 1
  compressionQuality: 50
  mipmapFilter: 0
  userData: 
  assetBundleName: 
  assetBundleVariant: 
""".format(guid=uuid.uuid4().hex)


frames = sorted(glob.glob(os.path.join(tmp, "boot", "*.svg")),
                key=lambda p: int(re.search(r"(\d+)\.svg$", p).group(1)))
print("boot frames:", len(frames))
for n, src in enumerate(frames, 1):
    name = "chip_boot_f%02d" % n
    place(src, os.path.join(root, "Assets/Chips/Backdrops/Boot", name + ".svg"), name + "Sprite", 100)

sprites = os.path.join(root, "Assets/Chips/0101-0200/Chip_0161/Sprites")
back = glob.glob(os.path.join(tmp, "s161", "*Back_161", "1.svg"))[0]
front = glob.glob(os.path.join(tmp, "s161", "*Front_161", "1.svg"))[0]
place(back, os.path.join(sprites, "chip_0161_back.svg"), "chip_0161_backSprite", 100)
place(front, os.path.join(sprites, "chip_0161_front.svg"), "chip_0161_frontSprite", 100)
print("161 back/front written")

# Any backdrop piece that uses a fill Unity's SVG importer cannot draw (chip
# 286's overlay is a <pattern> over an embedded PNG) ships rasterised as well;
# the SVG stays next to it so the builder can read its canvas.
BACKGROUNDS = ("0001", "0002", "0003", "0004", "0005", "0006", "0161", "0177", "0286")
FORCE_RASTER = ("chip_0161_", "chip_0177_", "chip_0286_")
for svg in sorted(s for i in BACKGROUNDS
                  for kind in ("back", "front")
                  for s in glob.glob(os.path.join(root,
                          "Assets/Chips/*/Chip_%s/Sprites/chip_%s_%s.svg" % (i, i, kind)))):
    body = open(svg, encoding="utf-8").read()
    # Static full-frame backdrops (161/177/286) are rasterised too: they are
    # shown 1:1 and the vector path renders their gradient fills too dark, which
    # rsvg-convert reproduces exactly.
    forced = any(i in os.path.basename(svg) for i in FORCE_RASTER)
    if not forced and "<pattern" not in body and "<image" not in body:
        continue
    png = os.path.splitext(svg)[0] + ".png"
    name = os.path.splitext(os.path.basename(svg))[0] + "Sprite"
    subprocess.run(["rsvg-convert", "-w", "1600", svg, "-o", png], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    open(png + ".meta", "w", encoding="utf-8").write(png_meta(name))
    print("rasterised", os.path.basename(png))
PY

echo "done"
