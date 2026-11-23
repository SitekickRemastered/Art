# SWF → SVG chip pipeline

Lossless vector export via JPEXS FFDec (Ruffle has no vector export).
Libraries: chips 1–500, 501–1000, 1001–1375; effects 1–250 … 1251–1375.

```bash
# one-off: fetch the decompiler (release zip contains ffdec.jar)
curl -sL -o /tmp/ffdec.zip \
  https://github.com/jindrapetrik/jpexs-decompiler/releases/latest/download/ffdec_26.5.0.zip
unzip -o /tmp/ffdec.zip -d Tools/ffdec

# for each SWF: export sprite frames, shapes, morph shapes and the timeline XML
#   Tools/out/chips_<range>/sprites|shapes + lib.xml
#   Tools/out/effects_<range>/sprites|shapes|morphshapes + lib.xml
# (FFDec only finds the input file by absolute path for the morphshape export)
java -jar Tools/ffdec/ffdec.jar -format sprite:svg     -export sprite     <dir>/sprites     <lib>.swf
java -jar Tools/ffdec/ffdec.jar -format shape:svg      -export shape      <dir>/shapes      <lib>.swf
java -jar Tools/ffdec/ffdec.jar -format morphshape:svg -export morphshape <dir>/morphshapes <abs>/<lib>.swf
java -jar Tools/ffdec/ffdec.jar -swf2xml <lib>.swf <dir>/lib.xml

# build (add --delete-pngs to remove superseded bitmaps)
python3 Tools/SwfToSvg/build_chips.py --ids 1-1375 --write

# prefabs + SVG import settings (svgType 1 = Sprite, 400 px/unit)
python3 Tools/SwfToSvg/build_prefabs.py --ids 1-1375 --write

# animation plan for the animated chips (frame tracks -> per-part keys)
python3 Tools/SwfToSvg/build_anim_plan.py
```

Animation assets are authored inside Unity, which owns the clip/controller
serialisation (`m_ClipBindingConstant` and friends are not hand-writable):

```bash
# clips + controllers (Animations/Chip_XXXX.anim, Animations/chip_XXXX.controller)
Unity -batchmode -quit -projectpath . -executeMethod ChipAnimBuilder.Run
# wiring the Animator onto the prefab roots (uses the controller guid in its .meta)
python3 Tools/SwfToSvg/build_prefabs.py --ids 1-1375 --write
```

Output per chip: `Assets/Chips/<range>/Chip_XXXX/`
- `Chip_XXXX.asset` — ChipData ScriptableObject
- `Sprites/chip_XXXX.svg` — inventory icon
- `Sprites/chip_XXXX_effect.svg` — static effect or blank placeholder
- `Sprites/chip_XXXX_base.svg` + `chip_XXXX_part_<id>.svg` + `chip_XXXX_effect.json`
  — animated effects, split by display-list depth. `base` is the fullest frame with
  the moving instances removed, i.e. the same effect as a still; the prefab only
  falls back to it when nothing in the chip can animate, so an effect is never
  drawn twice (once as a still, once as the animation)
- `Chip_XXXX_Effect.prefab` — SortingGroup + ChipEffect root, one SpriteRenderer per
  animated part; blank effects get an empty prefab, static effects one renderer

## Frame-exact Ruffle check

The movies are judged in Ruffle, not in the decompiler's frames (see `AGENTS.md`).
`ruffle_frames.py` freezes the patched movie one frame at a time, plays the copies in
`ruffle_frames.html` and diffs every tile against `Movie/frame_NNN.svg` in stage
pixels.  `--capture` runs the whole thing headlessly and prints one line per frame:

```bash
python3 Tools/SwfToSvg/ruffle_frames.py Temp/swftosvg/0008/chip_0008_tools.xml \
    --out Temp/swftosvg/review/c0008 --frames 45-61 --capture --cols 5
```

Scratch lives under `Temp/swftosvg/` inside the project (gitignored): the export
tools' work dirs are `<chip>/`, `extract_effect.py` caches its library XML in
`lib/`, and `ruffle_review.py` writes its frozen SWFs and grid pages to
`review/c<chip>/`.  Nothing is written outside the project.

`--out` gets `fNNN.swf` per frame plus `shots/frames-NNN-NNN.png` per page
(`--shot-dir` moves those).  The browser is Brave (flatpak) when it is installed,
else the first Chromium on `PATH`; `--browser '<command>'` overrides the choice.

Three flags in that launch are not optional:

- `--autoplay-policy=no-user-gesture-required` — a headless Chromium blocks
  playback that would produce audio, and every chip movie carries sound cues.  With
  the policy in force Ruffle never leaves its click-to-play overlay, so the capture
  is a grid of play buttons (or a blank page) and diffs as a clean frame.
- `--mute-audio` — the same cues, at full volume.
- `--force-device-scale-factor=1` — a HiDPI scale turns a tile into 470x375 instead
  of 375x300 and the diff then compares the wrong pixels.

The window is sized to the grid because Ruffle does not render a player outside the
viewport, so a page taller than the window leaves blank tiles; `--rows` (default 3)
sets how many 300 px rows fit and longer ranges are captured one page at a time.

The page's own `&post=NAME` composite still exists for driving the grid by hand in
the Freebuff browser, but it grabs whatever each player happened to have painted:
when the window is not being drawn it returns duplicate tiles, which read as an
agreeing frame.  Use `--capture` whenever the result matters.

### What a pixel diff can and cannot decide

`--playhead SPRITE=LABEL@FRAME` (repeatable) freezes a clip where the root script
jumps it; a `!` after the target makes it a `gotoAndStop` (`83=2!@40`), and a bare
number is a frame for clips the script jumps by number.  `--region X,Y,W,H`
restricts the diff to one rectangle, and `--cross A B` compares two captures
instead of a capture against the export.

A clip the script jumps is frozen by merging its frames up to the playhead into
one, so a playhead may name a pose past the root frame (chip 9's arm is on 53
while the root is on 33).  A clip no script jumps is cut to the frames it has
played since it was placed and stopped there, because the placement offset is
part of the state: chip 7's butterfly clip (104), placed on root 13, is 18
frames old on root 30 and shows its 18th frame, not its 30th.  Re-measured after
this, chip 7's reference is pixel-identical to the earlier run (mean 1.06 over
all 53 frames) and chip 8's lockstep capture reads 5.69 whole-frame against
5.70 before.

The frozen build has to decide where each clip's playhead is, and the plain build
uses FFDec's lockstep advance — the export's own assumption.  A pristine SWF
therefore reads at the floor against an export made that way, which is agreement
by construction, not evidence.  Chip 8, frames 45-61, over the arms region (26.8%
of the stage: the pixels where the arm clips draw):

| comparison | arms region (mean /255) |
| --- | --- |
| current export vs Ruffle of the shipped SWF | 5.48 |
| HEAD export vs the lockstep build | 5.04 |
| repeat capture of the same page twice | 0.00 |
| the same export vs its Ruffle, arms parked (57-61) | 1.2-2.4 |
| the same export vs its Ruffle, arms moving (45-56) | 6.8-9.9 |

Two different arm states differ by ~13/255 in that region while rendering the same
state two ways costs up to ~10, and the whole-frame means that used to be quoted
(~2.2) are a mixture of quiet background and busy arm pixels.  So this harness can
show an export is faithful to the SWF it was made from; it cannot show *when* a
clip moves.  Timing comes from the SWF: `verify_arm_timing.py` reads the root's
frame actions, resolves the labels they name, and checks tag-for-tag that the arm
sprites the export draws carry exactly that source clip frame on every root frame.

## Prefab placement

`build_prefabs.py` places each piece using the SWF matrix of the fullest animation
frame (the SWF moves one instance between display-list depths, so a depth is not an
instance identity). Positions come from `svg_bbox.py`, which reproduces the bbox the
Unity SVG importer uses for a sprite canvas — the importer ignores `clipPath` when
measuring, so it does not match the rendered alpha bounds. Every moving part gets a
parent transform at its SWF registration point with the sprite offset underneath, so
a later Animator can rotate it about the right pivot.

## Backgrounds, foregrounds and particles

An effect class is not the whole effect. `build_effect_clips.py` reads the actionscript
exported with the libraries (`Tools/out/effects_*/scripts`) and records what else a
chip draws:

- `backClip = new c()` / `frontClip = new c()` — a backdrop or overlay that is a
  *separate* symbol (often `Back_<chip>`), drawn behind or in front of the effect.
  138 chips have one, 53 also have a front. The backdrop art is exported next to the
  effect art (`chip_XXXX_back.svg`, `chip_XXXX_front.svg`, `chip_XXXX_particle_N.svg`)
  and the prefab gets a `chip_XXXX_extras` child with sorting order -1000/+1000.
- A clip with more than one frame is animated by a sprite-swap track in an aux clip
  (`Chip_XXXX_extras.anim`), so an animated background actually plays its frames.
- Spawned particles (`new FlakeMC()`, `BubbleMC`, `LeafMC`, ...) are not on a timeline
  at all: the effect starts a timer that adds a random handful to the stage every
  second and tweens each across the screen. Those become `PARTICLES` copies, each on
  its own animator/clip so they do not run in step, moving from one edge to the other
  and fading in and out — an endless rise or fall (chips 151/152, 153, 322, 452, 786,
  1109, 1133).

Output: `Tools/SwfToSvg/effect_clips.json` (regenerate after re-exporting the
libraries; it is committed so the chip build does not need the actionscript).

## Sitekick

`Assets/Sitekick/EditorSitekick.prefab` is sprite 214 (`skMain`) of
`SWF/sitekick.swf` at frame 1. Its frame-1 display list is the body itself:

```
depth 1  behind    empty clip   effects behind the body
depth 3  antenna   sprite 14    aerial stick
depth 5  pulse     sprite 17    glow at the knob (blank at frame 1)
depth 7  knob      sprite 20    aerial knob
depth 9  washer    sprite 22    ring where the aerial meets the head
depth 11 head      sprite 29    body shell and face plates
depth 20 eye1      sprite 31
depth 22 eye2      sprite 31    scaled 0.74
depth 24 inFront   empty clip   effects in front of the body
depth 26 -         button 33    knob hit area, no art
```

```bash
python3 Tools/SwfToSvg/build_sitekick.py --write
```

The `pulse` symbol is blank on frame 1 (it only draws while the aerial
animates), so it is left out rather than added as an invisible sprite: a fully
transparent renderer would still stretch the Sitekick's bounds.

Each piece is rasterised from its own exported symbol at twice the chip
resolution (PPU 800, same units per SWF pixel), so the Sitekick and the chip
effects share one scale: an effect prefab placed under the Sitekick at scale 1
is exactly the size it had in Flash.  The prefab keeps the SWF instance names
(`Antenna` holding `Pulse`/`Stick`/`Knob`/`Washer`, `Body`, `Eyes` holding
`Eye L`/`Eye R`) and the four `EffectLayer` children, so `EditorSitekick` can
still hide body/eyes/antenna and tint the body.  The prefab keeps its .meta guid
(`921ac30d…`): `ChipPrefabStage` loads it by that guid.

## Animation

`build_anim_plan.py` follows each prefab part's instance through the frames (same
character id, nearest registration point, walking out from the fullest frame) and
emits one key per frame: position, rotation (unwrapped, so no 360° flips), scale and
the instance alpha. Instances that leave the display list keep their last pose and
fade to alpha 0, which reproduces the SWF's fade-in/fade-out instead of popping.
`ChipAnimBuilder` turns that into a looping clip at the SWF frame rate plus a
controller with a single default state, and the prefab generator adds the Animator
to the root (Transform + SortingGroup + ChipEffect + Animator, as `Chip_0099` had).

A moving depth's symbol is looked up among the library's sprites, shapes and morph
shapes, so all 262 animated effects have part art. Symbol ids are only unique
within one SWF, which is why nothing is looked up across libraries. A symbol a
timeline places but the SWF never defines (chip 158 has 52 of them, chip 529 has
4) is a dangling reference that Flash draws as nothing, so those parts are skipped.

Part symbols that are themselves multi-frame sprites are exported frame by frame
and the renderer uses their first frame: the clips animate transform and alpha,
not sprite swaps, so the extra frames are only there for future frame swapping.
Empty frames are skipped (a symbol often starts blank); a frame that draws
nothing at all - including one whose clip path hides every path - would import as
an empty sprite whose NaN bounds poison the whole prefab.
