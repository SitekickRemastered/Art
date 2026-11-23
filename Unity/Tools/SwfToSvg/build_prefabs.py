#!/usr/bin/env python3
"""Build one Unity prefab per chip from the exported SVG art + effect JSON.

Composition follows the project convention (see Chip_0099_Effect.prefab):
  Chip_XXXX_Effect            Transform + SortingGroup + ChipEffect (+ Animator later)
  +- chip_XXXX_base           SpriteRenderer of the static effect art
  +- chip_XXXX_part_<depth>   Transform carrying the SWF matrix of that display-list depth
     +- sprite                SpriteRenderer of the moving part, offset to its own pivot

Coordinates: effect JSON matrices are in SWF units (y down).  Unity world units
are SWF units * 6.94 (export scale) / 400 (sprite pixels-per-unit).  Sprites are
centred on the geometry bounding box that the Unity SVG importer uses, so each
renderer is offset by its bbox centre to keep the SWF registration point intact.

Blank effects (chiplibrary has no effect symbol) produce an empty prefab, which
is the project's "no visual effect" state.

Usage:  python3 Tools/SwfToSvg/build_prefabs.py [--write] [--limit N] [--ids 1-1375]
"""

import argparse
import glob
import hashlib
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import normalize  # noqa: E402
from svg_bbox import bbox as svg_bbox  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
CHIPS = os.path.join(ROOT, "Assets", "Chips")
SCALE = 6.94          # exported pixels per SWF unit
PPU = 400             # sprite pixels per unit, matches ChipSpriteImporter
U = SCALE / PPU       # Unity units per SWF unit

# Where a chip effect's own stage centre belongs on the Sitekick.  sitekick.swf
# creates `effectHolder` on its root timeline (`_global.skMain = this`) and loads
# the chip's effect.swf into it at (0, 0), so the effect's 375x300 stage lands
# 1:1 on the Sitekick's stage.  The body's registration (sprite 214, placed at
# (3758, 2784) twips by the root's `sitekick` object) is therefore at stage
# (187.9, 139.2), and the stage centre -- where every chip effect is drawn -- is
# (-0.4, +10.8) px from it.  Effect art anchored on the registration point sits
# 10.8 px too high on the face.
STAGE_OFFSET = (-0.4, 10.8)
SPRITE_LOCAL_ID = 3286163911610860551  # constant local id of an SVGImporter sprite
CHIP_EFFECT_SCRIPT = "e058694190c354a4ab26742ffed98388"
PREFAB_SUFFIX = "_Effect.prefab"
# SWF stage in SWF units, from the libraries' displayRect (11000x8000 twips)
STAGE = (550.0, 400.0)
# spawned particles: how many copies and how long each takes to cross the stage
# (the SWF spawns up to 9 a second, each falling for 3-8 seconds)
PARTICLES = 4
PARTICLE_SECONDS = (3.5, 4.5, 5.5, 6.5)
BACK_ORDER = -1000
FRONT_ORDER = 1000

META_TEMPLATE = """fileFormatVersion: 2
guid: {guid}
ScriptedImporter:
  internalIDToNameTable: []
  externalObjects: {{}}
  serializedVersion: 2
  userData: 
  assetBundleName: 
  assetBundleVariant: 
  script: {{fileID: 12408, guid: 0000000000000000e000000000000000, type: 0}}
  svgType: 1
  texturedSpriteMeshType: 0
  svgPixelsPerUnit: {ppu}
  gradientResolution: 64
  alignment: 0
  customPivot: {{x: 0, y: 0}}
  generatePhysicsShape: 0
  viewportOptions: 0
  preserveViewport: 0
  advancedMode: 0
  tessellationMode: 1
  predefinedResolutionIndex: 1
  targetResolution: 1080
  resolutionMultiplier: 1
  stepDistance: 10
  samplingStepDistance: 100
  maxCordDeviationEnabled: 0
  maxCordDeviation: 1
  maxTangentAngleEnabled: 0
  maxTangentAngle: 5
  keepTextureAspectRatio: 1
  textureSize: {tex}
  textureWidth: {tex}
  textureHeight: {tex}
  wrapMode: 0
  filterMode: 1
  sampleCount: 4
  preserveSVGImageAspect: 0
  useSVGPixelsPerUnit: 0
  spriteData:
    TessellationDetail: 0
    SpriteName: 
    SpritePivot: {{x: 0, y: 0}}
    SpriteAlignment: 0
    SpriteBorder: {{x: 0, y: 0, z: 0, w: 0}}
    SpriteRect:
      serializedVersion: 2
      x: 0
      y: 0
      width: 0
      height: 0
    SpriteID: sprite
    PhysicsOutlines: []
"""

SPRITE_RENDERER = """--- !u!212 &{rid}
SpriteRenderer:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: {go}}}
  m_Enabled: {enabled}
  m_CastShadows: 0
  m_ReceiveShadows: 0
  m_DynamicOccludee: 1
  m_StaticShadowCaster: 0
  m_MotionVectors: 1
  m_LightProbeUsage: 1
  m_ReflectionProbeUsage: 1
  m_RayTracingMode: 0
  m_RayTraceProcedural: 0
  m_RenderingLayerMask: 1
  m_RendererPriority: 0
  m_Materials:
  - {{fileID: 10754, guid: 0000000000000000f000000000000000, type: 0}}
  m_StaticBatchInfo:
    firstSubMesh: 0
    subMeshCount: 0
  m_StaticBatchRoot: {{fileID: 0}}
  m_ProbeAnchor: {{fileID: 0}}
  m_LightProbeVolumeOverride: {{fileID: 0}}
  m_ScaleInLightmap: 1
  m_ReceiveGI: 1
  m_PreserveUVs: 0
  m_IgnoreNormalsForChartDetection: 0
  m_ImportantGI: 0
  m_StitchLightmapSeams: 1
  m_SelectedEditorRenderState: 0
  m_MinimumChartSize: 4
  m_AutoUVMaxDistance: 0.5
  m_AutoUVMaxAngle: 89
  m_LightmapParameters: {{fileID: 0}}
  m_SortingLayerID: 0
  m_SortingLayer: 0
  m_SortingOrder: {order}
  m_Sprite: {{fileID: {sprite_id}, guid: {sprite_guid}, type: 3}}
  m_Color: {{r: 1, g: 1, b: 1, a: {alpha}}}
  m_FlipX: 0
  m_FlipY: 0
  m_DrawMode: 0
  m_Size: {{x: 1, y: 1}}
  m_AdaptiveModeThreshold: 0.5
  m_SpriteTileMode: 0
  m_WasSpriteAssigned: 1
  m_MaskInteraction: 0
  m_SpriteSortPoint: 0
"""


def stable_guid(text):
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def fnum(v):
    """Compact float formatting Unity accepts."""
    if v == 0:
        return "0"
    s = "%.9g" % v
    if s in ("-0", "-0.0"):
        return "0"
    return s


class Ids:
    def __init__(self):
        self.n = 100000

    def next(self):
        self.n += 1
        return self.n


def go_block(gid, name, components):
    comps = "\n".join("  - component: {fileID: %d}" % c for c in components)
    return """--- !u!1 &%d
GameObject:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  serializedVersion: 6
  m_Component:
%s
  m_Layer: 0
  m_Name: %s
  m_TagString: Untagged
  m_Icon: {fileID: 0}
  m_NavMeshLayer: 0
  m_StaticEditorFlags: 0
  m_IsActive: 1
""" % (gid, comps, name)


def transform_block(tid, gid, pos, rot, scale, children, father):
    kids = ""
    if children:
        kids = "\n  m_Children:\n" + "\n".join("  - {fileID: %d}" % c for c in children)
    else:
        kids = "\n  m_Children: []"
    qz = rot[2]
    qw = rot[3]
    return """--- !u!4 &%d
Transform:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  m_GameObject: {fileID: %d}
  serializedVersion: 2
  m_LocalRotation: {x: 0, y: 0, z: %s, w: %s}
  m_LocalPosition: {x: %s, y: %s, z: 0}
  m_LocalScale: {x: %s, y: %s, z: 1}
  m_ConstrainProportionsScale: 0%s
  m_Father: {fileID: %d}
  m_LocalEulerAnglesHint: {x: 0, y: 0, z: %s}
""" % (tid, gid, fnum(qz), fnum(qw), fnum(pos[0]), fnum(pos[1]),
       fnum(scale[0]), fnum(scale[1]), kids, father,
       fnum(math.degrees(2 * math.atan2(qz, qw))))


def sorting_group_block(sid, gid):
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
  m_SortingOrder: 0
  m_SortAtRoot: 0
""" % (sid, gid)


def animator_block(aid, gid, controller_guid):
    return """--- !u!95 &%d
Animator:
  serializedVersion: 5
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  m_GameObject: {fileID: %d}
  m_Enabled: 1
  m_Avatar: {fileID: 0}
  m_Controller: {fileID: 9100000, guid: %s, type: 2}
  m_CullingMode: 0
  m_UpdateMode: 0
  m_ApplyRootMotion: 0
  m_LinearVelocityBlending: 0
  m_StabilizeFeet: 0
  m_WarningMessage: 
  m_HasTransformHierarchy: 1
""" % (aid, gid, controller_guid)


def chip_effect_block(mid, gid):
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
  coloredRenderers: []
""" % (mid, gid, CHIP_EFFECT_SCRIPT)


def matrix_trs(m):
    a, b, c, d = m[0], m[1], m[2], m[3]
    sx = math.hypot(a, b)
    sy = math.hypot(c, d)
    det = a * d - b * c
    if det < 0:
        sy = -sy
    angle = math.atan2(-b, a)
    return (0.0, 0.0, math.sin(angle / 2.0), math.cos(angle / 2.0)), (sx, sy)


_ART_USABLE = {}


def art_usable(path):
    """False when a sprite built from this file would be empty.

    Unity turns such a document into a sprite with no geometry, whose NaN
    renderer bounds poison the bounds of the whole prefab.
    """
    if path in _ART_USABLE:
        return _ART_USABLE[path]
    ok = os.path.exists(path) and svg_bbox(path) is not None
    if ok:
        with open(path, encoding="utf-8", errors="ignore") as f:
            text = f.read()
        # a clip path can hide the entire content
        if "clipPath" in text:
            ok = not normalize.renders_empty(path)
    _ART_USABLE[path] = ok
    return ok


MAX_TEXTURE = 4096


def sprite_info(svg_path):
    """bbox centre in SWF units and the texture long edge in pixels."""
    b = svg_bbox(svg_path)
    if b is None:
        return (0.0, 0.0), 256
    cx = (b[0] + b[2]) / 2.0
    cy = (b[1] + b[3]) / 2.0
    tex = max(8, min(MAX_TEXTURE, int(round(max(b[2] - b[0], b[3] - b[1]) * SCALE))))
    return (cx, cy), tex


def prefab_yaml(chip, dump, controller_guid=None, extras_guids=None):
    extras_guids = extras_guids or {}
    ids = Ids()
    root_go = ids.next()
    root_tr = ids.next()
    root_sort = ids.next()
    root_mono = ids.next()
    root_anim = ids.next() if controller_guid else None

    children = []
    blocks = []

    base = dump.get("base_renderer")
    if base:
        go = ids.next()
        tr = ids.next()
        sr = ids.next()
        centre, _ = base["centre"], None
        blocks.append(go_block(go, base["name"], [tr, sr]))
        blocks.append(transform_block(tr, go,
                                      ((centre[0] + STAGE_OFFSET[0]) * U,
                                       -(centre[1] + STAGE_OFFSET[1]) * U),
                                      (0, 0, 0, 1), (1, 1), [], root_tr))
        blocks.append(SPRITE_RENDERER.format(
            rid=sr, go=go, enabled=1, order=base["order"],
            sprite_id=SPRITE_LOCAL_ID, sprite_guid=base["guid"],
            alpha=fnum(base["alpha"])))
        children.append(tr)

    extras = dump.get("extras") or {}
    if extras:
        # backdrop, foreground and spawned particles live under one child so a
        # single Animator can frame-swap the clips without touching the parts
        ex_go = ids.next()
        ex_tr = ids.next()
        ex_anim = ids.next() if extras_guids.get("extras") else None
        ex_children = []
        ex_blocks = []

        def layer(item, parent, anim_guid=None, pos=(0, 0)):
            go = ids.next()
            tr = ids.next()
            sgo = ids.next()
            str_ = ids.next()
            sr = ids.next()
            anim = ids.next() if anim_guid else None
            ex_blocks.append(go_block(go, item["name"], [tr] + ([anim] if anim else [])))
            ex_blocks.append(transform_block(tr, go, pos, (0, 0, 0, 1), (1, 1),
                                             [str_], parent))
            ex_blocks.append(go_block(sgo, "sprite", [str_, sr]))
            ex_blocks.append(transform_block(str_, sgo,
                                             (item["centre"][0] * U, -item["centre"][1] * U),
                                             (0, 0, 0, 1), (1, 1), [], tr))
            ex_blocks.append(SPRITE_RENDERER.format(
                rid=sr, go=sgo, enabled=1, order=item["order"],
                sprite_id=SPRITE_LOCAL_ID, sprite_guid=item["guid"], alpha=fnum(1.0)))
            if anim:
                ex_blocks.append(animator_block(anim, go, anim_guid))
            return tr

        if extras.get("back"):
            ex_children.append(layer(extras["back"], ex_tr))
        for particle in extras.get("particles", []):
            # each particle sits at its own x and animates its own transform
            ex_children.append(layer(particle, ex_tr, extras_guids.get(particle["name"]),
                                     (particle.get("x_swf", 0.0) * U, 0.0)))
        if extras.get("front"):
            ex_children.append(layer(extras["front"], ex_tr))

        blocks.append(go_block(ex_go, "chip_%04d_extras" % chip,
                               [ex_tr] + ([ex_anim] if ex_anim else [])))
        blocks.append(transform_block(ex_tr, ex_go,
                                      (STAGE_OFFSET[0] * U, -STAGE_OFFSET[1] * U),
                                      (0, 0, 0, 1), (1, 1), ex_children, root_tr))
        if ex_anim:
            blocks.append(animator_block(ex_anim, ex_go, extras_guids["extras"]))
        blocks.extend(ex_blocks)
        children.append(ex_tr)

    for part in dump.get("parts", []):
        go = ids.next()
        tr = ids.next()
        sgo = ids.next()
        str_ = ids.next()
        sr = ids.next()
        pos, rot, scale = part["pos"], part["rot"], part["scale"]
        centre = part["centre"]
        blocks.append(go_block(go, part["name"], [tr]))
        blocks.append(transform_block(tr, go,
                                      (pos[0] + STAGE_OFFSET[0] * U,
                                       pos[1] - STAGE_OFFSET[1] * U),
                                      rot, scale, [str_], root_tr))
        blocks.append(go_block(sgo, "sprite", [str_, sr]))
        blocks.append(transform_block(str_, sgo, (centre[0] * U, -centre[1] * U),
                                      (0, 0, 0, 1), (1, 1), [], tr))
        blocks.append(SPRITE_RENDERER.format(
            rid=sr, go=sgo, enabled=part["enabled"], order=part["order"],
            sprite_id=SPRITE_LOCAL_ID, sprite_guid=part["guid"],
            alpha=fnum(part["alpha"])))
        children.append(tr)

    root_comps = [root_tr, root_sort, root_mono]
    if root_anim:
        root_comps.append(root_anim)

    out = ["%YAML 1.1", "%TAG !u! tag:unity3d.com,2011:"]
    out.append(go_block(root_go, "Chip_%04d_Effect" % chip, root_comps).rstrip("\n"))
    out.append(transform_block(root_tr, root_go, (0, 0), (0, 0, 0, 1), (1, 1), children, 0).rstrip("\n"))
    out.append(sorting_group_block(root_sort, root_go).rstrip("\n"))
    out.append(chip_effect_block(root_mono, root_go).rstrip("\n"))
    if root_anim:
        out.append(animator_block(root_anim, root_go, controller_guid).rstrip("\n"))
    for b in blocks:
        out.append(b.rstrip("\n"))
    return "\n".join(out) + "\n"


def art_by_char(sprites_dir, data):
    """character_id -> exported art file.  Older exports omit "art", so fall back
    to the naming convention used by the exporter (with an optional subframe index)."""
    by_char = {}
    for p in data["parts"]:
        name = p.get("art")
        if isinstance(name, list):
            # multi-frame part symbol: one renderer, so take its first frame that
            # draws something (symbols often start with empty frames)
            name = next((n for n in name if art_usable(os.path.join(sprites_dir, n))), None)
        if not name:
            stem = "chip_%04d_part_%d" % (data["chip"], p["character_id"])
            for candidate in (stem + ".svg", stem + "_f001.svg"):
                if os.path.exists(os.path.join(sprites_dir, candidate)):
                    name = candidate
                    break
        if name and art_usable(os.path.join(sprites_dir, name)):
            by_char[p["character_id"]] = name
    return by_char


def clip_art(sprites_dir, entry, name, order):
    """One backdrop/foreground/particle renderer from an exported clip."""
    frames = entry["art"] if isinstance(entry["art"], list) else [entry["art"]]
    paths = [os.path.join(sprites_dir, f) for f in frames]
    usable = [p for p in paths if art_usable(p)]
    if not usable:
        return None
    centre, _ = sprite_info(usable[0])
    return {"name": name, "order": order, "frames": frames,
            "centre": centre, "guid": meta_guid(usable[0]),
            "art": paths}


def collect(sprites_dir, data):
    """Turn an effect json into renderer descriptions."""
    dump = {}

    def extras_of(data):
        """backdrop, foreground and spawned particles the effect class draws."""
        clips = data.get("clips") or {}
        out = {}
        if clips.get("back"):
            r = clip_art(sprites_dir, clips["back"], "back", BACK_ORDER)
            if r:
                out["back"] = r
        if clips.get("front"):
            r = clip_art(sprites_dir, clips["front"], "front", FRONT_ORDER)
            if r:
                out["front"] = r
        particles = []
        for n, p in enumerate(clips.get("particles") or []):
            r = clip_art(sprites_dir, p, "particle_%d" % n, 0)
            if r:
                r["dir"] = p.get("dir", "down")
                particles.append(r)
        if particles:
            out["particles"] = particles
        return out

    def add_extras():
        ex = extras_of(data)
        if ex:
            dump["extras"] = ex

    def art(name):
        path = os.path.join(sprites_dir, name)
        if not os.path.exists(path):
            return None
        if not art_usable(path):
            # frame draws nothing: Unity imports it as an empty sprite, whose
            # renderer bounds are NaN and poison the whole prefab
            return None
        centre, tex = sprite_info(path)
        guid = meta_guid(path)
        return {"centre": centre, "tex": tex, "guid": guid, "path": path}

    if data["mode"] == "static":
        a = art(data["art"])
        if a:
            dump["base_renderer"] = {
                "name": os.path.splitext(os.path.basename(data["art"]))[0],
                "order": 0 if data.get("effectLayer", 0) in (0, 1) else 0,
                "alpha": 1.0,
                **{k: a[k] for k in ("centre", "guid")},
            }
        add_extras()
        return dump

    if data["mode"] != "animated":
        # nothing of its own to animate (a background chip's symbol is empty);
        # the backdrop and particles still have to be drawn
        add_extras()
        return dump

    by_char = art_by_char(sprites_dir, data)

    # The SWF moves one instance between display-list depths, so a depth is not
    # an instance identity.  A prefab needs one concrete pose: use the frame that
    # shows the most parts (most effects fade in from an empty first frame).
    best = data["tracks"][0]["moving"] if data["tracks"] else []
    best_score = -1
    for track in data["tracks"]:
        visible = [e for e in track["moving"] if "character_id" in e and not e.get("absent")]
        score = len(visible)
        if score > best_score:
            best_score = score
            best = track["moving"]

    parts = []
    for m in sorted(best, key=lambda e: e["depth"]):
        depth = m["depth"]
        if "character_id" not in m or m.get("absent"):
            continue
        pick = m
        cid = pick.get("character_id")
        name = by_char.get(cid)
        if not name:
            continue
        a = art(name)
        if a is None:
            continue
        rot, scale = matrix_trs(pick["matrix"])
        alpha = 1.0
        col = pick.get("color")
        if col and col.get("alphaMultTerm"):
            try:
                alpha = max(0.0, min(1.0, float(col["alphaMultTerm"]) / 256.0))
            except ValueError:
                alpha = 1.0
        parts.append({
            "name": "chip_%04d_part_%d" % (data["chip"], depth),
            "pos": (pick["matrix"][4] * U, -pick["matrix"][5] * U),
            "rot": rot,
            "scale": scale,
            "centre": a["centre"],
            "guid": a["guid"],
            "order": depth,
            "alpha": alpha,
            "enabled": 1,
        })
    dump["parts"] = parts

    # The base is the fullest frame with the moving instances removed, i.e. a
    # still of the same effect: drawing it behind the animated parts shows the
    # effect twice, so it is only used when nothing can animate.
    if not parts:
        base = art(data["base"])
        if base:
            dump["base_renderer"] = {
                "name": os.path.splitext(os.path.basename(data["base"]))[0],
                "order": 0,
                "alpha": 1.0,
                "centre": base["centre"],
                "guid": base["guid"],
            }
    add_extras()
    return dump


_META_GUIDS = {}


def meta_guid(asset_path):
    key = asset_path
    if key in _META_GUIDS:
        return _META_GUIDS[key]
    meta = asset_path + ".meta"
    if os.path.exists(meta):
        m = re.search(r"^guid: ([0-9a-f]{32})", open(meta, encoding="utf-8").read(), re.M)
        if m:
            _META_GUIDS[key] = m.group(1)
            return m.group(1)
    guid = stable_guid(os.path.relpath(asset_path, ROOT))
    _META_GUIDS[key] = guid
    return guid


def write_meta(svg_path, tex, write, coarse=False):
    """Keep the import settings in sync without discarding what Unity writes back.

    After an import the SVG importer stores its computed sprite data (SpriteName,
    SpritePivot, SpriteRect, SpriteID) in the .meta.  Rewriting the whole file from
    the template would drop that and force a reimport on every run, so only the
    three settings this pipeline owns are patched in place.
    """
    meta = svg_path + ".meta"
    if not os.path.exists(meta):
        if write:
            with open(meta, "w", encoding="utf-8") as f:
                f.write(META_TEMPLATE.format(guid=meta_guid(svg_path), ppu=PPU, tex=tex))
        return True

    # a full-screen backdrop can ask for more than the importer will allocate
    # (over 4096 fails with "invalid parameters")
    tex = min(tex, 4096)
    text = open(meta, encoding="utf-8").read()
    m = re.search(r"textureSize: (\d+)", text)
    sized = (m and int(m.group(1)) == tex
             and "textureWidth: %d" % tex in text
             and "textureHeight: %d" % tex in text)
    if coarse and "stepDistance: 40" not in text:
        sized = False
    if "svgType: 1" in text and "svgPixelsPerUnit: %d" % PPU in text and sized:
        return False

    new = re.sub(r"svgType: \d+", "svgType: 1", text)
    new = re.sub(r"svgPixelsPerUnit: [\d.]+", "svgPixelsPerUnit: %d" % PPU, new)
    new = re.sub(r"textureSize: \d+", "textureSize: %d" % tex, new)
    # the importer builds the texture from width/height, not from textureSize
    new = re.sub(r"textureWidth: \d+", "textureWidth: %d" % tex, new)
    new = re.sub(r"textureHeight: \d+", "textureHeight: %d" % tex, new)
    if coarse:
        # a full-screen backdrop is far too dense for the 65535-vertex sprite
        # limit, and nobody sees its detail: flatten the curves harder
        new = re.sub(r"stepDistance: [\d.]+", "stepDistance: 40", new)
        new = re.sub(r"samplingStepDistance: [\d.]+", "samplingStepDistance: 400", new)
        new = re.sub(r"maxCordDeviationEnabled: \d", "maxCordDeviationEnabled: 1", new)
        new = re.sub(r"maxCordDeviation: [\d.]+", "maxCordDeviation: 4", new)
    if new != text and write:
        with open(meta, "w", encoding="utf-8") as f:
            f.write(new)
    return new != text


def chip_dirs(ids):
    out = []
    for range_dir in sorted(glob.glob(os.path.join(CHIPS, "*"))):
        if not os.path.isdir(range_dir):
            continue
        for name in sorted(os.listdir(range_dir)):
            m = re.match(r"Chip_(\d{4})$", name)
            if not m:
                continue
            cid = int(m.group(1))
            if ids and cid not in ids:
                continue
            out.append((cid, os.path.join(range_dir, name)))
    return out


def parse_ids(text):
    out = set()
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            a, b = chunk.split("-")
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(chunk))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--ids")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    ids = parse_ids(args.ids) if args.ids else None
    targets = chip_dirs(ids)
    if args.limit:
        targets = targets[:args.limit]

    stats = {"chips": 0, "metas": 0, "prefabs": 0, "blank": 0, "static": 0,
             "animated": 0, "parts": 0, "no_prefab": 0, "extras": 0}
    missing_art = []

    for cid, cdir in targets:
        sdir = os.path.join(cdir, "Sprites")
        jsons = glob.glob(os.path.join(sdir, "*_effect.json"))
        stats["chips"] += 1

        data = None
        if jsons:
            data = json.load(open(jsons[0], encoding="utf-8"))

        # 1. import settings for every svg in this chip
        for svg in sorted(glob.glob(os.path.join(sdir, "*.svg"))):
            _, tex = sprite_info(svg)
            base = os.path.basename(svg)
            coarse = "_back" in base or "_front" in base
            if coarse:
                # a full screen backdrop does not need more, and the biggest
                # ones cannot be rasterised at all above this
                tex = min(tex, 2048)
            if write_meta(svg, tex, args.write, coarse):
                stats["metas"] += 1
            if not os.path.exists(svg + ".meta") and args.write:
                with open(svg + ".meta", "w", encoding="utf-8") as f:
                    f.write(META_TEMPLATE.format(guid=stable_guid(os.path.relpath(svg, ROOT)),
                                                 ppu=PPU, tex=tex))

        # 2. prefab
        if data is None:
            dump = {}
            stats["blank"] += 1
        else:
            dump = collect(sdir, data)
            stats["static" if data["mode"] == "static" else "animated"] += 1
            stats["parts"] += len(dump.get("parts", []))

        prefab_path = os.path.join(cdir, "Chip_%04d%s" % (cid, PREFAB_SUFFIX))
        meta_path = prefab_path + ".meta"
        if os.path.exists(meta_path):
            guid = meta_guid(prefab_path)
        else:
            guid = stable_guid(os.path.relpath(prefab_path, ROOT))

        anim_dir = os.path.join(cdir, "Animations")

        def ctrl_guid(name):
            path = os.path.join(anim_dir, name + ".controller.meta")
            if not os.path.exists(path):
                return None
            m = re.search(r"^guid: ([0-9a-f]{32})", open(path, encoding="utf-8").read(), re.M)
            return m.group(1) if m else None

        controller_guid = ctrl_guid("chip_%04d" % cid) if dump.get("parts") else None
        extras_guids = {}
        extras = dump.get("extras") or {}
        if extras:
            g = ctrl_guid("chip_%04d_extras" % cid)
            if g:
                extras_guids["extras"] = g
            for particle in extras.get("particles", []):
                pg = ctrl_guid("chip_%04d_%s" % (cid, particle["name"]))
                if pg:
                    extras_guids[particle["name"]] = pg
            stats["extras"] += 1

        yaml = prefab_yaml(cid, dump, controller_guid, extras_guids)
        old = open(prefab_path, encoding="utf-8").read() if os.path.exists(prefab_path) else None
        if old != yaml:
            if args.write:
                with open(prefab_path, "w", encoding="utf-8") as f:
                    f.write(yaml)
            stats["prefabs"] += 1

        if args.write and not os.path.exists(meta_path):
            with open(meta_path, "w", encoding="utf-8") as f:
                f.write("fileFormatVersion: 2\nguid: %s\nPrefabImporter:\n  externalObjects: {}\n"
                        "  userData: \n  assetBundleName: \n  assetBundleVariant: \n" % guid)

        if data and not dump and data["mode"] != "static":
            missing_art.append(cid)

    print(json.dumps(stats, indent=1, sort_keys=True))
    if missing_art:
        print("chips whose effect data produced no renderers:", missing_art[:20],
              "(%d total)" % len(missing_art))
    if not args.write:
        print("(dry run: pass --write to apply)")


if __name__ == "__main__":
    main()
