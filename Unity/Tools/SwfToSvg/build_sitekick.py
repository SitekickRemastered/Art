#!/usr/bin/env python3
"""Build Assets/Sitekick/EditorSitekick.prefab from sitekick.swf.

The Sitekick is sprite 214 (`skMain`), the body clip, at frame 1.  Its frame-1
display list places one symbol per body piece and names it:

    depth 1  behind     (empty clip)   effects drawn behind the body
    depth 3  antenna    sprite 14      aerial stick
    depth 5  pulse      sprite 17      glow around the aerial knob
    depth 7  knob       sprite 20      aerial knob
    depth 9  washer     sprite 22      ring where the aerial meets the head
    depth 11 head       sprite 29      head + face plates
    depth 20 eye1       sprite 31
    depth 22 eye2       sprite 31      scaled 0.74
    depth 24 inFront    (empty clip)   effects drawn in front of the body
    depth 26 (button)   button 33      knob hit area, no art

The prefab keeps those pieces as separate objects, at the SWF matrices and
under the SWF instance names, so body/eyes/antenna can be addressed
individually.  The four effect layers carry the project's EffectLayer component,
so chip effects still land behind or in front of the body.

Art is rasterised from the FFDec sprite export of each symbol in the same units
as the chip pipeline (SCALE pixels per SWF pixel at PPU 400), so the Sitekick
and the chips share one scale.  It is drawn at twice that resolution (PPU 800)
to keep the edges clean.

Usage:  python3 Tools/SwfToSvg/build_sitekick.py [--write]
"""

import argparse
import hashlib
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_prefabs as bp  # noqa: E402

ROOT = bp.ROOT
OUT = os.path.join(ROOT, "Tools", "out", "sitekick")
LIB_XML = os.path.join(OUT, "lib.xml")
ART_DIR = os.path.join(ROOT, "Assets", "Sitekick", "Sprites")
PREFAB = os.path.join(ROOT, "Assets", "Sitekick", "EditorSitekick.prefab")

BODY_SPRITE = 214
PPU = bp.PPU * 2          # rasterise at twice the chip resolution
U = bp.U                  # Unity units per SWF pixel
TWIP = 20.0               # twips per SWF pixel
ZOOM = 2.0 * bp.SCALE     # rasterised pixels per SWF pixel

EDITOR_SITEKICK_SCRIPT = "cb707e0445e2c3f41820bf43d1665600"
EFFECT_LAYER_SCRIPT = "3caf9a3b18604de4aaaf61312ce3faa6"

BACKGROUND_ORDER = -3000
BEHIND_ORDER = -2000
INFRONT_ORDER = 1000
FOREGROUND_ORDER = 2000

PULSE_ORDER = -70
STICK_ORDER = -60
KNOB_ORDER = -50
WASHER_ORDER = -40
BODY_ORDER = -20
EYE_L_ORDER = -10
EYE_R_ORDER = -9

# SWF instance name -> (prefab object, art file stem, character, order)
# the stick is SWF "antenna"; "head" is the Sitekick's body shell
PIECES = {
    "antenna": ("Stick", "antenna", 14, STICK_ORDER),
    "pulse": ("Pulse", "pulse", 17, PULSE_ORDER),
    "knob": ("Knob", "knob", 20, KNOB_ORDER),
    "washer": ("Washer", "washer", 22, WASHER_ORDER),
    "head": ("Body", "body", 29, BODY_ORDER),
    "eye1": ("Eye L", "eye", 31, EYE_L_ORDER),
    "eye2": ("Eye R", "eye", 31, EYE_R_ORDER),
}

LAYERS = (
    ("Background", 2, BACKGROUND_ORDER),
    ("Behind", 1, BEHIND_ORDER),
    ("InFront", 0, INFRONT_ORDER),
    ("Foreground", 3, FOREGROUND_ORDER),
)

PNG_META = """fileFormatVersion: 2
guid: {guid}
TextureImporter:
  internalIDToNameTable: []
  externalObjects: {{}}
  serializedVersion: 12
  mipmaps:
    mipMapMode: 0
    enableMipMap: 0
    sRGBTexture: 1
    linearTexture: 0
    fadeOut: 0
    borderMipMap: 0
    mipMapsPreserveCoverage: 0
    alphaTestReferenceValue: 0.5
    mipMapFadeDistanceStart: 1
    mipMapFadeDistanceEnd: 3
  bumpmap:
    convertToNormalMap: 0
    externalNormalMap: 0
    heightScale: 0.25
    normalMapFilter: 0
    flipGreenChannel: 0
  isReadable: 0
  streamingMipmaps: 0
  streamingMipmapsPriority: 0
  vTOnly: 0
  ignoreMipmapLimit: 0
  grayScaleToAlpha: 0
  generateCubemap: 6
  cubemapConvolution: 0
  seamlessCubemap: 0
  textureFormat: 1
  maxTextureSize: 2048
  textureSettings:
    serializedVersion: 2
    filterMode: 1
    aniso: 1
    mipBias: 0
    wrapU: 1
    wrapV: 1
    wrapW: 1
  nPOTScale: 0
  lightmap: 0
  compressionQuality: 50
  spriteMode: 1
  spriteExtrude: 1
  spriteMeshType: 1
  alignment: 0
  spritePivot: {{x: 0.5, y: 0.5}}
  spritePixelsToUnits: {ppu}
  spriteBorder: {{x: 0, y: 0, z: 0, w: 0}}
  spriteGenerateFallbackPhysicsShape: 1
  alphaUsage: 1
  alphaIsTransparency: 1
  spriteTessellationDetail: -1
  textureType: 8
  textureShape: 1
  singleChannelComponent: 0
  flipbookRows: 1
  flipbookColumns: 1
  maxTextureSizeSet: 0
  compressionQualitySet: 0
  textureFormatSet: 0
  ignorePngGamma: 0
  applyGammaDecoding: 0
  swizzle: 50462976
  cookieLightType: 1
  platformSettings:
  - serializedVersion: 3
    buildTarget: DefaultTexturePlatform
    maxTextureSize: 2048
    resizeAlgorithm: 0
    textureFormat: -1
    textureCompression: 1
    compressionQuality: 50
    crunchedCompression: 0
    allowsAlphaSplitting: 0
    overridden: 0
    ignorePlatformSupport: 0
    androidETC2FallbackOverride: 0
    forceMaximumCompressionQuality_BC6H_BC7: 0
  spriteSheet:
    serializedVersion: 2
    sprites: []
    outline: []
    physicsShape: []
    bones: []
    spriteID: 5e97eb03825dee720800000000000000
    internalID: 0
    vertices: []
    indices: 
    edges: []
    weights: []
    secondaryTextures: []
    nameFileIdTable: {{}}
  mipmapLimitGroupName: 
  pSDRemoveMatte: 0
  userData: 
  assetBundleName: 
  assetBundleVariant: 
"""


def stable_guid(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def meta_guid(path):
    meta = path + ".meta"
    if os.path.exists(meta):
        m = re.search(r"^guid: ([0-9a-f]{32})", open(meta, encoding="utf-8").read(), re.M)
        if m:
            return m.group(1)
    return stable_guid(os.path.relpath(path, ROOT))


def frame_one(sprite_id):
    """(depth, character id, instance name, matrix) placed on frame 1."""
    root = ET.parse(LIB_XML).getroot()
    sprite = None
    for item in root.iter("item"):
        if item.get("type") == "DefineSpriteTag" and item.get("spriteId") == str(sprite_id):
            sprite = item
            break
    if sprite is None:
        raise SystemExit("sprite %d not in %s" % (sprite_id, LIB_XML))

    out = []
    for sub in sprite.find("subTags"):
        kind = sub.get("type")
        if kind == "ShowFrameTag":
            break
        if kind != "PlaceObject2Tag" or sub.get("placeFlagMove") == "true":
            continue
        if not sub.get("characterId"):
            continue
        matrix = sub.find("matrix")
        m = matrix.attrib if matrix is not None else {}
        out.append({
            "depth": int(sub.get("depth")),
            "char": int(sub.get("characterId")),
            "name": sub.get("name"),
            "tx": float(m.get("translateX", 0)),
            "ty": float(m.get("translateY", 0)),
            "sx": float(m.get("scaleX", 1)),
            "sy": float(m.get("scaleY", 1)),
        })
    return out


def art_source(char):
    """The FFDec SVG for a character: a sprite's frame 1, or a shape."""
    sprite = os.path.join(OUT, "sprites", "DefineSprite_%d" % char, "1.svg")
    if os.path.exists(sprite):
        return sprite
    shape = os.path.join(OUT, "shapes", "%d.svg" % char)
    if os.path.exists(shape):
        return shape
    raise SystemExit("character %d has no exported art" % char)


def art(stem, char):
    """Rasterise one piece; the FFDec viewport is centred on the symbol's
    registration point, which is what the sprite pivot (centre) uses.

    A piece that draws nothing on frame 1 (the aerial's pulse glow is blank
    until it animates) would still add an invisible sprite, and a transparent
    renderer's bounds would stretch the Sitekick's bounds, so it is dropped.
    """
    png = os.path.join(ART_DIR, "sitekick_%s.png" % stem)
    os.makedirs(ART_DIR, exist_ok=True)
    subprocess.run(["rsvg-convert", "-z", str(ZOOM), "-o", png, art_source(char)],
                   check=True)

    coverage = float(subprocess.check_output(
        ["magick", "identify", "-format", "%[fx:mean.a]", png]).decode())
    if coverage < 0.002:
        for path in (png, png + ".meta"):
            if os.path.exists(path):
                os.remove(path)
        return None, coverage

    text = PNG_META.format(guid=meta_guid(png), ppu=PPU)
    with open(png + ".meta", "w", encoding="utf-8") as f:
        f.write(text)

    return (png, meta_guid(png)), coverage


def sorting_group(sid, go, order):
    return """--- !u!210 &%d
SortingGroup:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  m_GameObject: {fileID: %d}
  m_Enabled: 1
  m_SortingLayerID: 0
  m_SortingLayer: 0
  m_SortingOrder: %d
  m_SortAtRoot: 0
""" % (sid, go, order)


def effect_layer(mid, go, layer):
    return """--- !u!114 &%d
MonoBehaviour:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  m_GameObject: {fileID: %d}
  m_Enabled: 1
  m_EditorHideFlags: 0
  m_Script: {fileID: 11500000, guid: %s, type: 3}
  m_Name: 
  m_EditorClassIdentifier: 
  layer: %d
""" % (mid, go, EFFECT_LAYER_SCRIPT, layer)


def editor_sitekick(mid, go, body, eyes, antenna, colored):
    colors = "\n".join("  - {fileID: %d}" % c for c in colored)
    return """--- !u!114 &%d
MonoBehaviour:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  m_GameObject: {fileID: %d}
  m_Enabled: 1
  m_EditorHideFlags: 0
  m_Script: {fileID: 11500000, guid: %s, type: 3}
  m_Name: 
  m_EditorClassIdentifier: 
  bodyObj: {fileID: %d}
  eyesObj: {fileID: %d}
  antennaObj: {fileID: %d}
  coloredRenderers:
%s
""" % (mid, go, EDITOR_SITEKICK_SCRIPT, body, eyes, antenna, colors)


class Node:
    def __init__(self, name):
        self.name = name
        self.go = None
        self.tr = None
        self.sr = None
        self.sort = None
        self.layer = None
        self.children = []


def prefab_yaml(frame):
    ids = bp.Ids()

    def node(name):
        n = Node(name)
        n.go = ids.next()
        n.tr = ids.next()
        return n

    def piece_node(name, entry):
        n = node(name)
        n.sr = ids.next()
        n.piece = entry
        return n

    root = node("EditorSitekick")
    root.sort = ids.next()
    root.mono = ids.next()

    layers = {}
    for name, _, _ in LAYERS:
        n = node(name)
        n.sort = ids.next()
        n.layer = ids.next()
        layers[name] = n

    antenna = node("Antenna")
    eyes = node("Eyes")

    by_name = {}
    for entry in frame:
        if entry["name"] in PIECES:
            by_name[entry["name"]] = entry

    missing = sorted(set(PIECES) - set(by_name))
    if missing:
        raise SystemExit("frame 1 of sprite %d is missing %s" % (BODY_SPRITE, missing))

    pieces = []
    skipped = []
    for swf_name in ("pulse", "antenna", "knob", "washer", "head", "eye1", "eye2"):
        entry = by_name[swf_name]
        name, stem, char, order = PIECES[swf_name]
        (n, coverage) = (piece_node(name, entry), None)
        a, coverage = art(stem, char)
        if a is None:
            skipped.append((name, coverage))
            continue

        n.art, n.guid = a
        n.order = order
        n.parent = eyes if swf_name in ("eye1", "eye2") else (
            antenna if name in ("Pulse", "Stick", "Knob", "Washer") else root)
        n.parent.children.append(n)
        pieces.append(n)

    for name, coverage in skipped:
        print("  %s draws nothing on frame 1 (alpha %.4f), left out" % (name, coverage))

    body = next(p for p in pieces if p.name == "Body")

    root.children = [layers["Background"], layers["Behind"], antenna, body, eyes,
                     layers["InFront"], layers["Foreground"]]

    out = ["%YAML 1.1", "%TAG !u! tag:unity3d.com,2011:"]

    out.append(bp.go_block(root.go, root.name, [root.tr, root.sort, root.mono]).rstrip("\n"))
    out.append(bp.transform_block(root.tr, root.go, (0, 0), (0, 0, 0, 1), (1, 1),
                                  [c.tr for c in root.children], 0).rstrip("\n"))
    out.append(sorting_group(root.sort, root.go, 0).rstrip("\n"))

    for name, enum, order in LAYERS:
        n = layers[name]
        out.append(bp.go_block(n.go, name, [n.tr, n.sort, n.layer]).rstrip("\n"))
        out.append(bp.transform_block(n.tr, n.go, (0, 0), (0, 0, 0, 1), (1, 1), [], root.tr).rstrip("\n"))
        out.append(sorting_group(n.sort, n.go, order).rstrip("\n"))
        out.append(effect_layer(n.layer, n.go, enum).rstrip("\n"))

    for n in (antenna, eyes):
        out.append(bp.go_block(n.go, n.name, [n.tr]).rstrip("\n"))
        out.append(bp.transform_block(n.tr, n.go, (0, 0), (0, 0, 0, 1), (1, 1),
                                      [c.tr for c in n.children], root.tr).rstrip("\n"))

    for n in pieces:
        entry = n.piece
        pos = (entry["tx"] / TWIP * U, -entry["ty"] / TWIP * U)
        scale = (entry["sx"], entry["sy"])
        out.append(bp.go_block(n.go, n.name, [n.tr, n.sr]).rstrip("\n"))
        out.append(bp.transform_block(n.tr, n.go, pos, (0, 0, 0, 1), scale,
                                      [], n.parent.tr).rstrip("\n"))
        out.append(bp.SPRITE_RENDERER.format(
            rid=n.sr, go=n.go, enabled=1, order=n.order,
            sprite_id=21300000, sprite_guid=n.guid, alpha="1").rstrip("\n"))

    out.append(editor_sitekick(root.mono, root.go, body.go, eyes.go, antenna.go,
                               [body.sr]).rstrip("\n"))
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    frame = frame_one(BODY_SPRITE)
    print("frame 1 of sprite %d:" % BODY_SPRITE)
    for e in frame:
        print("  depth %-3d char %-4d %-8s at (%g, %g) scale %g" % (
            e["depth"], e["char"], e["name"], e["tx"] / TWIP, e["ty"] / TWIP, e["sx"]))

    yaml = prefab_yaml(frame)
    if args.write:
        with open(PREFAB, "w", encoding="utf-8") as f:
            f.write(yaml)
        print("wrote %s (%d lines)" % (os.path.relpath(PREFAB, ROOT), len(yaml.splitlines())))
    else:
        print("(dry run: pass --write to apply)")


if __name__ == "__main__":
    main()
