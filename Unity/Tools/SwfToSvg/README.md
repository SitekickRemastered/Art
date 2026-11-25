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

### Effects that spawn their art

A chip whose parts are created by ActionScript has no frames to freeze: chip 151's
flakes are `new FlakeMC()`s added by a timer, so `ruffle_frames.py` has nothing to
cut, and in the gallery the Animators are somewhere mid-fall.  For those the
reference is a body-relative composite, `sitekick_particles.html`: Ruffle plays
`sitekick.swf` at 1:1 and the page drops copies of the chip's particle SVG at SWF
stage coordinates, one SVG unit per SWF pixel with the origin at the stage centre
— the chip 145 static composite's 375x300 setup with the particle art in place of
the effect SVG.

```bash
python3 -m http.server 8137            # repo root
# http://127.0.0.1:8137/Unity/Tools/SwfToSvg/sitekick_particles.html
#   ?art=/Unity/Assets/Chips/0101-0200/Chip_0151/Sprites/chip_0151_particle_0_f001.svg
#   &at=-206.25,0;-68.75,0;68.75,0;206.25,0
```

`at` takes `x,y` pairs in SWF px relative to the stage centre (`0` is the centre,
`206.25` a column 19 px off the right edge) and `scale` multiplies the art.  The
gallery side is `ChipPlayCheck --hold`, which disables the spawned effect's
Animators before their first update so the capture is the prefab's authored pose —
the only state a still composite can match, since chip 151's flakes tween ±3.47
units about their node.  `Tools/SwfToSvg/measure_particles.py` reads both: body = largest
ink blob, flakes = light blobs clear of the body's columns, every figure divided by
body height so the gallery's zoom cancels.  Chip 151 measures -0.053 body heights
at the pivot and +0.140 at the stage centre in the composite, -0.032 and +0.164 in
the captures, so the stage offset is carried and the ~0.02 body heights left over
is the body mask (Ruffle's black silhouette against Unity's white shell).  A pre-fix capture means writing `git show HEAD:…Chip_0151_Effect.prefab` over the
working copy and restoring it afterwards.

`?pad=N` widens the capture by N empty pixels on every side, for a particle the
SWF would clip above its 300 px stage (`FlakeMC` starts at -25).  `ChipPlayCheck
--stage` is the Unity side of the same idea: it writes `stage.png`, the effect's
whole 375x300 stage scaled by the layer's 2.5x, beside `resting.png`, and it
reports the field's symbol count and live total.

**The stream itself is the effect.**  The baked four columns are only the
authored pose; the prefabs carry `ChipParticleField`, which spawns from the rule
in the chip's ActionScript -- `Timer(1000)` firing `int(Math.random() * 10)`
particles, each with a random x across the stage, `scale = Math.random()`, a
start 25 px past the stage edge and a `3 + int(Math.random() * 6)` s linear
tween -- and plays each symbol's frames at 31 fps on its own playhead.
`build_particle_fields.py` writes that data into the eight particle prefabs
(`--write`, idempotent) from `Sprites/chip_XXXX_effect.json`:

```bash
python3 Tools/SwfToSvg/build_particle_fields.py            # report
python3 Tools/SwfToSvg/build_particle_fields.py --write    # patch prefabs
```

`audit_particle_fields.py` is the no-Unity guard for that block: a prefab
rebuild that drops it, or a re-export that renumbers the symbol frames,
otherwise only shows up in a live Unity run.  It reads the eight prefabs and
each chip's export and fails when the field is gone, when the root no longer
lists its component, when `stageWidth`/`stageHeight` are missing, zero or not
the 375x300 the effects are drawn on, when a symbol has no frames, a frame count
the export did not write, or a frame guid that is not its sprite's meta guid:

```bash
python3 Tools/SwfToSvg/audit_particle_fields.py            # 8 chips in 0.27 s
python3 Tools/SwfToSvg/audit_particle_fields.py --chip 151
```

On the current tree that is 151/152/153/322/452/786 one symbol each (128, 160,
160, 40, 50 and 8 frames), 1133 two (400) and 1109 four (800), all at stage
375x300, 31 fps and capacity 96.

A particle's node is at scale 1, so the sprite's `svgPixelsPerUnit` *is* its
size.  `audit_sprite_scale.py` compares the rendered size with the art's own
`size_px` and rewrites the whole symbol when they differ (the class shipped
1.5-2.5x too small; the value is 57.6361 = 1 / 0.01735):

```bash
python3 Tools/SwfToSvg/audit_sprite_scale.py           # table + FAIL
python3 Tools/SwfToSvg/audit_sprite_scale.py --write   # pin ppu
```

And the whole check is one command, which measures `report.txt` and `stage.png`
and can drive both sides itself:

```bash
python3 Tools/SwfToSvg/particle_check.py --chip 151               # measure what is there
python3 Tools/SwfToSvg/particle_check.py --chip 151 --unity       # + run ChipPlayCheck --hold --stage
python3 Tools/SwfToSvg/particle_check.py --chip 151 --live        # the spawner, not the pose
python3 Tools/SwfToSvg/particle_check.py --chip 151 --reference   # + the Ruffle composite
```

It checks the columns' spacing against `x_swf`, that a held capture spawned
nothing, that a live one holds at least a third of `mean burst x mean lifetime`
in the spawner's own `LiveCount` with an x spread over half the stage, and
prints the body-relative group centre `measure_particles.py` reads from the
capture.  A chip that also draws a back/front layer (153, 1133) is captured
with `--hide-back`: the play check turns those renderers off for `stage.png`
only -- the resting captures stay the chip as it ships -- and records `back
hidden <sprite>  (stage.png only)`.  The held baseline is taken the same way,
so the spread is measured on the particles rather than on that art.  That art
is far wider than the stage (2784 and 4364 library px on a 550 px canvas), so
re-enabling it moves the gallery captures by only a few pixels.

A live run waits `maxLifetime + 2` seconds so the stream reaches steady state,
keeps the chip's held capture beside it as the floor's baseline, and refuses to
grade a report older than its own Unity launch.  Repeats: `--seed N` reseeds the
editor (batchmode otherwise repeats one draw) and `--repeat 5 --seed 1` prints
the distribution.

The per-chip live-count and spread distributions are checked in at
`Tools/SwfToSvg/particle_baseline.json` -- one draw per seed with the window it
was taken over -- and `--repeat` prints a batch's mean against the stored one,
warning when it falls two stored sd below it rather than relying on a number
quoted here.  The floor itself is a third of `mean burst x mean lifetime`,
measured against a baked pose that alone puts 7 blobs under the stream mask --
which is why the gate is the component's `LiveCount` and the capture only has
to corroborate it.
With 786's field block deleted the run reports `no particle field` and 6 blobs,
and fails.  Counts quoted as typical earlier were one unseeded draw each at the
old 4.5 s window: reproducible, not representative.  151's 17 blobs, 152's `live
27 of 96`, 322's and 1133's samples sit inside their stored distributions; 153's
`live 16 of 96` is a low draw and 786's 4 is the same tail.  452's 14 was not
representative at all: 4.5 s is shorter than one
`LeafMC` lifetime (5-14 s), so the stream had not reached steady state, and the
same chip holds 26-55 over a 16 s window.  The 1133 seed-5 run's 12 is a tail
draw, not a chip fault: it failed a floor of half the rule (12.4) and clears the
third (8.2), which is why the floor is a third.  That does not weaken the
stripped-prefab check -- a prefab with no field block reports no field line and
`LiveCount` 0, and fails on that, not on the count.

The spread is measured from the spawner, not the capture.  `ChipParticleField`
reports each live particle's spawn x (report line `live x -154.90,...`) and
`--repeat`/`--live` compute the range and stdev from those as a fraction of the
effect's own stage, gated against the 0.1% quantile of the span of that many
uniform draws.  The stage comes from the chip, never a constant: `ChipPlayCheck`
writes `field stage 375 x 300 px  capture margin 1.10` beside the `live x`
values (`ChipParticleField.stageWidth`/`stageHeight`, which
`build_particle_fields.py` puts in the prefab), the spread is divided by that
width, and `measure_particles.measure_stream(stage=, margin=)` scales the capture
with it; a report without the line fails rather than assuming 375.  A live report with no `live x` line fails
outright rather than falling back to the blobs -- the capture is corroboration
only, and on the same draw it reads 0.481 where the spawner reads 0.95.  Blobs
are only corroboration: merging
loses particles (153's 36 live read as 29 blobs, 151's 14 as 9) and takes the
extremes with them.  151's seed-5 draw is the case in point -- 14 live span 0.95
of the stage from the spawner, 0.481 from 9 captured blobs, which failed the
floor on a uniform field.  The per-chip draws, their seeds and stdev are in
`particle_baseline.json`; at a full stream the capture reads slightly wider
(1.03 against 0.97) because a blob box includes the particle's own art width.

The same method measured the rest of the class, stored in that file.  786 is the
lowest, at 0.59 on a 7-live draw.  A fixed half-stage
floor would be wrong there: `P(span <= r) = n*r**(n-1) - (n-1)*r**n` for `n`
uniform points, so half the stage is missed by 31% of legitimate 4-live draws,
and 786's count floor (3.8) allows them.  The floor is the 0.1% quantile of that
span, per run: 0.06 at 4 live, 0.24 at 7, 0.38 at 10, 0.50 at 14, 0.55 at 16,
0.77 at 36, 0.84 at 55 -- tight for a full stream, forgiving of a quiet one.
Every stored draw clears it; an x cluster within +-5 px fails at 10 and at 36
live.  786's stored draws span 0.59-0.95 over seeds 3-9 and its lowest sits 0.35
above its floor.

The spread is one third of the rule, so the check reads the rest from the
spawner too.  `ChipParticleField.LiveTracks` reports every live particle and
`ChipPlayCheck` writes the constants plus one line each:

```
field rule  particle margin 25 px  symbol 31 fps  lifetime 3..8 s  burst 0..9 every 1 s
live particle  x 9.61  y 34.99  age 2.00  life 5.00  from 175.00  to -175.00  scale 0.643  frame 62 of 128
```

Each particle has to start `stageHeight/2 + margin` from the centre (175 px
here, 25 px past the stage), end at the other side, live inside the field's
lifetime range, and sit within 2% of the traverse of `from + (to - from) * age
/ life` -- the residual a fixed y or a half-speed fall shows up as.  Scales must
lie in 0..1 and span the same 0.1% floor as x (they come off the same uniform
stream); the reported rate must match the chip's export (31 fps), each symbol
must carry the export's frame count, and each particle's frame must be the one
its age gives, within a frame.  A report without `field rule` fails the way one
without `field stage` does, so older live captures are stale.

Seed 9, one draw each, all eight pass -- 151 34 particles, 152/153 36, 322 24,
452 58, 786 19, 1109 23, 1133 34, each starting at 175 px and ending at -175
(152/153 from -175), scales 0.07-0.97 on 151/152/153/1133, 0.07-0.99 on
322/1109, 0.01-0.99 on 452 and 0.18-0.93 on 786, against floors 0.61-0.85.
Manipulated copies of a real 151 report each fail (rc 1): all y held at the
start (30 of 34 off the traverse, worst 350 px), a half-speed fall (30 of 34,
175 px), every scale at 1.000 ("range 0.000, floor 0.759 for 34"), the symbol
at 15 fps ("the export says 31"), a start on the 150 px edge (34 of 34 wrong),
and one frame per symbol ("play 1 frame(s); the export has 128").

A baked pose is not rejected by extent -- it has `LiveCount` 0, so there are no
x values to read, and its four authored columns measure 1.134-1.169 of the stage
from the capture, wider than a field by construction.  `LiveCount` 0 and its
6-7 blobs are what fail it.


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
- The copies are a stand-in for a random field, not a port of it.  Chip 151's
  `FlakeMC.init` sets `x = Math.random() * stage.stageWidth` (0..375), `y = -25`
  (25 px above the stage), `scaleX = scaleY = Math.random()` and tweens `y` to
  `stageHeight + 25` over `3 + Math.random() * 5` s, and its `onTimer` adds
  `Math.random() * 10` flakes a second.  `build_chips.py` spreads `PARTICLES = 4`
  copies evenly over the *library's* 550x400 canvas instead
  (`x_swf = -275 + (n + 0.5) * 137.5`), so -206.25 and +206.25 fall outside the
  375 px stage the effect is drawn on, and gives them fixed 3.5/4.5/5.5/6.5 s falls
  of ±200 px rather than the SWF's +175 → -150 px, at scale 1 rather than 0..1.
  The group's origin is what a prefab can be judged against; the columns, the fall
  length and the scale are approximations (`AGENTS.md`, chip 151).

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
