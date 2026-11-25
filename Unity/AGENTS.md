# Project instructions

## Chip movie exports (Tools/SwfToSvg)

- **The decompiler (JPEXS/FFDec) is only a source of SVG geometry.** Use it to
  export frame/sprite SVGs, shapes, XML and ActionScript. Never treat its
  rendered frames as the truth about what an animation looks like: it does not
  run ActionScript, and its handling of `clipDepth` masks, `ratio`-placed
  art and multi-frame placements is wrong often enough that frames alternate
  content (art appears and disappears every other frame) while looking
  plausible one frame at a time.
- **Always check visual accuracy against Ruffle.** Ruffle plays the SWF with a
  real ActionScript VM and is the reference for what the chip actually looks
  like. Compare the exported frames against Ruffle before calling an export
  done; a frame-by-frame FFDec render matching the SWF geometry is not evidence
  that the animation is right.
- Practical consequence: when a movie's art depends on script state (per-hand
  tools, visibility toggles, `gotoAndStop` in clips), author that state into the
  SWF (see `Tools/SwfToSvg/patch_chip8_tools.py`) or into the export, then
  verify the result in Ruffle.
- Chip 8 is authored in `Tools/SwfToSvg/patch_chip8_tools.py`, and two of its
  pieces only exist on the *loop*, not in the display section the file's own
  timeline shows first.  `tools2` (sprite 82) carries the seventh hand -- the
  one holding the oil can -- and the script adds it with
  `bottom.gotoAndStop(2)` on the display frame; because the movie then loops
  back over 16..35, the loop frames must show it, so `arm_playheads` starts it
  on root 16 (`fresh_at=15`) rather than on 40.  Starting it at 40 left the
  export with five hands where Ruffle shows six: the missing one is the only
  hand the game could never show.  The antenna (71) extends over four frames,
  stops on its frame 5 and retracts from 6; holding frames 1..5 as the clip's
  opening frames replayed the drop on every pass of the loop, because the loop
  starts two frames into the extend, so `author_antenna` emits frame 5
  flattened as a one-frame sprite (a one-frame clip has no playhead to replay).
  Both are visible against the live dock, which is where they were caught:
  frame 20 against Ruffle goes from mean 3.90/255 over the loop to 2.93, and the
  oil-can region from 993 to 145 hot pixels.
- Chip 7 is authored the same way in `Tools/SwfToSvg/patch_chip7.py`. Its rings,
  score wings and buttons all park on their own frame 1 and the scripts only ever
  jump them to a score-dependent frame (`0 % 11 + 1` is 1, `ceil(0 / 10)` is not
  a frame), so FFDec's advance lit them up and tinted the butterfly through a
  pastel cycle it never plays; the antenna is folded on frame 1 and only the root
  44 jump extends it, so the pass holds frame 1 there and `extended` from 44.
  Holding those twelve clips is safe because their frames are one pose each; the
  rewrite is in the export, not in the SWF folder.
- Chip 9 is authored in `Tools/SwfToSvg/patch_chip9.py`. Its clips are a state
  machine on the root timeline: root 2 plays the trim from 2, root 8 plays the
  hole side from 2, side 12 plays the arm from 2, arm 10 plays the right side
  from 2, root 33 stops and sends the arm to `retract2` (53) while arm 53 opens
  the hole, root 42 sends the arm to `prepare` (69), 53 to `downHole` (78),
  112 to `relax` (90), and arm 59 sends the side back to its `retract` (16).
  FFDec advanced all of them in lockstep instead: the arm swung out where the
  chip has it inside the hole, the right side played its whole 44 frames, and
  the two-frame hole alternated open/closed every frame.  Each scripted clip is
  re-emitted with one frame per root frame, holding the tag stream up to the
  frame the script leaves it on.  That stream has to be merged rather than
  flattened into a display list: the arm places its hole twice (frame 41 and 47)
  and only the merged order renders it, so flattening hid the hole for root
  frames 33-41.  Against the scripted Ruffle reference the export goes from
  mean 3.59/255 (worst 7.49) to 1.36 (worst 1.81).
- Chip 10 is authored in `Tools/SwfToSvg/patch_chip10.py`.  Its bubble (sprite
  20) is placed three times -- depth 1 on root 1, depths 22 and 43 on root 9
  with ratio 8, all named `effectSK` -- and stops on its first frame; the only
  thing that moves it is root 9's `effectSK.gotoAndStop("squint")` (label
  `squint`, frame 25).  Its face lines (sprite 5) stop on frame 1 ("out") and no
  script touches them, so `patch_stopped_clips.py` freezes that one itself.
  FFDec advanced the bubble from frame 1 instead: open eyes for the whole movie,
  running on into a retract the chip never plays.  Each placement gets a copy
  that carries the parked pose in its first frame and adds the squint on root 9
  as a *delta* -- the squint body is the parked body plus what the clip adds by
  frame 25 -- because repeating the parked placements on the switch frame
  re-places the clips inside it and restarts their timelines, which stripped
  the antenna's knob and slid it off the ball.  Against the scripted Ruffle
  reference the face region (130,45,115,125) goes from mean 5.77/255 (worst
  14.60) to 4.02 (worst 10.10); root 9-16 now differ by a hairline at the mouth
  and a broad shading offset, not by the pose.
- Chip 11 is authored in `Tools/SwfToSvg/patch_chip11.py`.  The chip (`bottom`,
  sprite 60) is a one-frame container at root depth 12 that the root only moves,
  and the whole animation hangs off one clip inside it: `monster` (sprite 59),
  which stops on its frame 1, is sent to frame 2 by root 14's
  `bottom.monster.gotoAndPlay(2)`, and stops itself again on frame 22 (label
  `display`).  So it runs 2..22 over root 14..34 and holds that pose for the rest
  of the movie -- root 36 sends the root back to `hover` anyway, and the
  `retract` half of the clip (frames 23..50, and the root jump its 39th frame
  asks for) is only reached when something outside the chip retracts it.  FFDec
  advanced it from frame 1, i.e. the chip turned into a purple monster while it
  should still have been a white ball.  The clip is re-emitted as one frame per
  root frame: its frame 1 for roots 1-13, its own 2..22 over roots 14..34, then
  empty frames, which on an incremental timeline hold the display list.
- A stop on a clip's *last* frame loops under FFDec like any other stop FFDec
  never runs, and the shared pass now freezes that case too.  It has to be
  merged rather than cut: writing frames 1..k with the action dropped would just
  loop them again, so `held_frames()` replays them as one frame, the pose at k.
  Chip 11's fringe (sprite 36) is five frames of moves ending on the spiky
  outline, stopped there; it went round 1..5 the whole movie and the monster
  read as a smooth cap from root 30 on, and holding it is the difference between
  mean 1.99 and 0.21 on root 32.  Widening the rule changed nothing else:
  sprite 36 is the only last-frame stop in chips 7-11, so all 167 exported
  frames are byte-identical before and after and the numbers below stand.
  Whole-frame means on the shipped ranges, before = after: 7 1.05, 8 2.58,
  9 1.28, 10 1.98, 11 1.43 (worst 1.07 / 3.20 / 1.53 / 4.25 / 1.96).  Chip 8's
  5.69 was measured over all 71 root frames; the 36 the hover cut drops carried
  most of the tool-loading difference.
- Chip 12 needs no clip authoring, only the cut.  Root 1 stops and arms
  `nose.onRelease` (`busy = true; gotoAndStop("open"); play();`); the `open`
  label is frame 2, and root 25 runs `busy = false; gotoAndStop(1)` with nothing
  after it -- frames 26-66 carry no tags at all.  So the movie is a 24-frame
  cycle: closed, nose out with the flag on 8-21, closed again by 24, then back to
  1 to wait for the next click.  FFDec played 1..66 linearly: frames 1-24 were
  already right (mean 1.38/255, worst 1.60 against Ruffle) and the export then
  held the last pose for 42 frames the movie never shows.  `hover_loop.py` now
  also reads literal `gotoAndStop(n)` from the root's frame scripts -- only
  unwrapped calls, since chip 8's `fixit.bottom.gotoAndStop(2)` moves a clip --
  so the export is 24 frames and the player loops 1..24: mean 1.39, worst 1.60,
  with all 24 frames byte-identical to the old export.  Its one-frame sprites
  3/5/9/11 call `paint(this)`, which the site's host supplies: `sitekick.swf`
  defines it as `new Color(clip).setTransform(...)` and nothing else, so it can
  only tint, never draw.  Checked against the shipping `SWF/chip_0012.swf`
  loaded in Ruffle with a `dock` shim (the movie hides and opens
  `ytv.com/flash404.asp` without one, and its guard also needs `_url` to contain
  `ytv.com`) and the host's `paint` copied in: paint undefined and paint at
  100/100/100 give byte-identical frames, and a 40/70/100 tint recolours only the
  nose/tip pieces (463 px) with the silhouette unchanged (2,167 px) -- so
  standalone the movie draws the whole effect, nose, tip, pole and flag, and
  that is the art both the export and the harness see, not a missing body.  At
  frame 16 the real SWF and `frame_016.svg` agree to mean 1.43/255 over the
  stage background (`Logs/chip_0012_paint_check.png`).
- Chip 13 is authored in `Tools/SwfToSvg/patch_chip13.py`.  Root 1 stops and the
  site starts the movie at the `display` label on 11
  (`effectHolder.gotoAndPlay("display")`), where it stops again and arms the
  body button and the antenna knob.  The knob sends the root to `revert` (14)
  and root 26 removes the effect, so 14-26 are a retract nothing in
  `ChipGallery` can reach.  The idle is not frozen art: the fish is sprite 52,
  placed on root 9, a 20-frame tween of its body (51), and it has no stop, so it
  keeps advancing while the root sits on 11.  The body (51) and its button (31)
  do stop on their frame 1 and are only played by the button's click, so the
  idle body is frame 1.  FFDec played the root linearly (12-26 retract, 27-79
  empty) and advanced the body through its poke animation; in Unity that was a
  0.75 s pause on 11 and then the retract into an empty stage.  The patch
  freezes 51/31 on frame 1, cuts the root at 11, drops its stop and appends 20
  empty frames: those hold root 11's display list while 52 advances one frame
  per root frame, which is what Flash does.  The export is 31 frames, loop
  12..31, with cues on 5 and 10 (the frame-14 cue belonged to the revert and is
  gone).  Against the same Ruffle reference (run `ruffle_frames.py` on a held
  copy with `--playhead 52=1@9`; the merge path wraps the fish each 20 frames)
  the whole 1..31 export goes from mean 3.42/255 (worst 8.27) to 1.69 (worst
  8.27) on the harness's white-paper metric, with frames 11-31 at 1.22-1.25
  where 15-31 used to be the revert and the empty tail.  The 6-9 blip is not an
  export error and not clipDepth/mask handling: chip 0013's SWF has no clipDepth
  tags and its 31 SVGs no masks; the art is a white radial-gradient glow, and
  `diff_page`'s white-paper/grayscale composite loses it.  Composited over the
  stage blue, frames 5-10 are 0.68-0.76 and the whole 1..31 range is 0.75 mean
  (worst per-frame 0.76, worst pixel 87); the 8.27 is the glow artifact
  (`Logs/chip_0013_absorb_check.txt`).  Checked live against the shipping
  `SWF/chip_0013.swf` with a dock shim: the shim must set `_global.dock`, not
  just `_root.dock`, or the loaded movie's unqualified `dock` misses it and the
  guard sends the page to `ytv.com/flash404.asp`; serve it under a path
  containing `ytv.com` so `_url` passes too.  With that, 26 `fscommand` samples
  over 10.8 s put root at 11 every time while sprite 52 runs 1..20 (body stays
  1, root visible), and the live fish=7 frame matches the frozen root-15 tile
  to 1.10/255 (`Logs/chip_0013_live_dock.*`).
- Chip 14 is authored in `Tools/SwfToSvg/patch_chip14.py`.  Its root labels are
  `hover` 3 and `display` 33; the site starts at `display`, whose script parks
  the spider (sprite 64) on its own `display` label, frame 21, then sends the
  root to `hover` (3) and plays.  Root 30 jumps back to 3, so the visible movie
  is 3..29; 1..2 and 30..55 (the spider's retract from 22) are never reached.
  FFDec started the spider at 1 and advanced it: root 3 showed the curled intro,
  root 8 the walk-in and root 29 the retract ball.  The pass runs the shared
  stopped-clip freeze (26 -> 65), then cooks sprite 64's frame-21 display list
  into one frame -- one fresh placement per depth, no moves, `frameCount` 1 --
  because FFDec ignores the move-only tags and otherwise exports the frame-1
  transforms (a lower, grey spider).  Both sound cues are inside the spider at
  frames 2 and 14, so the parked pose plays neither and the export has no cues.
  The export is 29 frames, loop 3..29, pause [1].  Against the scripted Ruffle
  reference: before mean 2.56/255 (worst 4.02, frame 2), after 1.61 (worst 1.62)
  on the harness's white-paper metric; composited over the stage blue, 1.68
  (worst 3.35) -> 0.45 (worst 0.46, worst pixel 111, the 0.004 stage veil), and
  frame 21 is byte-identical to the old correct render.  Live dock: 12 samples
  over 5 s put the root at 3..29 while `spider` stayed 21/33 and visible
  (`Logs/chip_0014_live.txt`).  Prefab rebuilt to 29 refs with `sounds: []`,
    `loopFrom` 3, `loopTo` 29, frame guids preserved.
- Chip 15 is authored in `Tools/SwfToSvg/patch_chip15.py`.  Its root labels are
  `display` 3, `hover` 4 and `retract` 29; the site jumps to `display` once the
  effect has loaded, whose script parks `soundwaveSK` (sprite 33) on its own
  `transformed` label, frame 17, and then root 4 plays.  Root 2 is the frame
  that starts the wave (`soundwaveSK.gotoAndPlay(2)`) and it is not on that
  path: entered at 3 the clip is still sitting on its own frame-1 stop, so root
  3's `_currentframe == 1` test passes and the clip never runs.  Root 23 jumps
  back to 4, so the visible movie is 3..22; 1..2 and 24..55 (root 40 removes
  the effect) are never reached.  FFDec started sprite 33 at 1 and advanced it
  one frame per root frame, so the export grew the headphones in over 1..16 --
  frames 1..8 showed a bare white Sitekick -- and kept going to 22.  The pass
  runs the shared stopped-clip freeze (a no-op here: 16 is `cup` and 33
  `soundwaveSK`, so both are named in scripts) and then cooks sprite 33's
  frame-17 display list into one frame, `frameCount` 1.  Both sounds are
  unreachable as well: sound 10 is placed inside sprite 33 on its frame 2,
  which the park skips, and sound 35 is on root 32.  The export is 22 frames,
  loop 4..22, pause [1], no cues.  Against the scripted Ruffle reference: before
  mean 2.11/255 (worst 3.71, frame 2), after 1.49 (worst 1.60) on the harness's
  white-paper metric; over the stage blue in the chip's own box, 4.95 -> 1.27
  mean (frame 2 10.06 -> 2.19), the residual being antialiasing on the outline
  (`Logs/chip_0015_measure.txt`).  Live dock: the root cycled 5..22 then 4 for
  6.5 s while `soundwaveSK` stayed 17/27 and visible (`Logs/chip_0015_live.txt`).
  Prefab rebuilt to 22 refs with `sounds: []`, `loopFrom` 4, `loopTo` 22,
  frame guids preserved.
- Chip 16 is authored in `Tools/SwfToSvg/patch_chip16.py`.  Its root has one
  label, `hover` 3, and the whole movie is `body` (sprite 64, 101 frames) with
  its own labels `display` 39, `still` 40 and `wave` 44.  The site loads it as
  `effect.swf?...&display=true` and then calls
  `effectHolder.gotoAndPlay("display")`; the root has no `display` label, so
  that call does nothing and the root stays on frame 1 -- root 2's
  `body.gotoAndPlay(2)` never runs -- while the query variable does land on the
  loaded movie and `body` frame 1's `if (effect.display == "true")` parks the
  clip on its own `display` label.  Measured live against the shipping SWF with
  a dock shim that reproduces that load (`Logs/chip_0016_live.txt`): 28 samples
  over 6.9 s read `root=1/39 body=39/101` every time.  The chip is therefore
  one static pose -- head, mouth, stick arms, tilted top hat -- and the 3..20
  hover loop the generic cut found is only reachable through the host's other
  path (`effectHolder.play()`, used when the effect returns from a game), where
  `body` restarts at 2 and grows the hat in over 2..40 before stopping at
  `still`; the nose-click `wave` is likewise unreachable from the gallery.
  FFDec played `body` from frame 1 in lockstep with the root, so the export
  builds the chip from one ball: head and body by 20, face and both stick arms
  by 36, then the hat -- sprite 40, a five-frame clip placed on `body` 36 -- in
  the last frames.  That is exactly where the export has to end, and the cut was
  wrong: the root's `gotoAndStop("hover")` on 21 names a block that starts long
  before the hat exists, so routing chip 16 through `hover_loop` exported frames
  3..20 and looped them -- a hatless snowman for ever, which never reaches the
  pose the chip is for.  Chip 16 therefore takes no cut and no loop
  (`loop = None` in `export_chip_movies.py`).  The export is the whole root
  timeline: 39 frames, `pauses [1]`, cues on 3, 9, 18, 28 and 32 (the 47 and 60
  cues sit in `body`'s nose-click `wave`, which the gallery cannot reach, so the
  export drops them and their mp3s); the movie plays once and the player holds
  the last frame, which is the finished snowman -- head, face, both arms, body
  and the tilted top hat.  The 39 exported SVGs are byte-identical to the set
  already shipped, so the measurement of that art stands: the parked pose (root
  1, body at 39) reads 0.09 stage / 0.86 chip mean against the scripted Ruffle
  reference, worst pixel 57 (`Logs/chip_0016_measure.txt`,
  `Logs/chip_0016_before_after.png`).  Frame 39 is that pose in lockstep, with
  the hat three frames into its own five-frame settle (sprite 40 stops on its
  frame 5), so it differs from the parked tile by a hat scale of a few pixels,
  not by the pose.  Prefab: 39 frame refs
  in movie order, `sounds` at 3/9/18/28/32, no `loopFrom`/`loopTo`, so nothing
  wraps.  Gallery play-mode check (`Logs/chip_0016_play/report.txt`): `frames 39
  fps 12  loop 0..0  pauses [1]  pauseSeconds 0.75  sounds 5`, trace `1..15
  restart 1..39`, `samples 54  distinct 39  wraps 0  stopped at -`, `rest done
  on frame 39 (frame_039Sprite)`, `cues 3,9,18,28,32  fired 7x  prefab
  3,9,18,28,32` (the two extra fires are the check's own warm-up restart
  replaying 1..15).  So it plays the 39 frames once in order, never wraps,
  never holds at a stop, and rests on the finished snowman -- two balls, face
  with eyes/nose/smile, both stick arms and the tilted top hat
  (`Logs/chip_0016_play/resting-close.png`; the pale patch beside the hat there
  is the art's 30%-white highlight, invisible on the paper the frames are
  measured on).
- Chip 36 is authored by the export itself, from the library movie
  (`Source/Chip Libraries/Old Chips/Effects/chip_0036.swf`, via `LIBRARY_SWF`
  in `export_chip_movies.py`: there is no `SWF/` copy).  It has no `display`
  label, so the host's `gotoAndPlay("display")` misses and the root stops on
  frame 1, where it arms `mask.onRelease` to draw the swords and `sword1`/
  `sword2`/`mask` to `sliceLeft` (26), `flipRight` (17) and `sheath` (41, back to
  1).  Every clip in the movie is a single frame, so with the root stopped
  *nothing* moves: the whole animation is that root sequence and only a click
  starts it.  Nothing in the gallery can hit an SVG button, so the export plays
  the cycle itself -- `loop = (1, 51)`, where root 52 jumps back to the sheathed
  pose (frame 51 is byte-identical to frame 1) -- and `pauses = []`, because the
  stop() on 14 (`drawn`) would otherwise hold the movie on that pose for good.
  51 frames, 38 distinct, 8 cues; against Ruffle the whole range reads mean
  1.16/255 (worst 1.40 on frame 6), and the live dock -- which stays on root 1,
  as the script does -- matches export frame 1 to 1.29.  Both swords and the
  mask between them are in every drawn frame, not only the stops.  Play-mode
  check: `frames 51 loop 1..51`, trace `1 .. 51 | 1 .. 51 | 1 .. 16`, 2 wraps,
  never held   (`Logs/chip_0036_play/report.txt`); `ChipPlayCheck` now takes
  `--chip` like the builder, and its window grew to two of the movie's own
  cycles, since 51 frames at 12 fps outlast the old fixed 7 s.  It also listens
  to the player's `CueFired` event and checks the frames it fired against the
  prefab's cue list, and it treats `loop 0..0` as a one-pass movie: every frame
  once, `IsDone`, resting on the last, which is what chips 9, 11 and 16 do.  A
  chip with no `ChipMoviePlayer` -- most of the library -- is reported as a
  static effect instead: the renderers and sprite it spawned, their bounds, and
  a capture, which is all such a chip can be checked for.
- Chips 37 and 53 have no standalone SWF anywhere in the repo (37's only file
  is the one-frame chip icon), so `Tools/SwfToSvg/extract_effect.py` pulls them
  out of `Source/Effect Libraries/effectlibrary1_250.swf` and writes
  `SWF/chip_0037.swf` / `SWF/chip_0053.swf`, which is where the exporter looks.
  The libraries are one AS3 asset bundle: the `SymbolClass` table maps each
  `corus.effects.effect_NNNNNN` to a symbol (`000037` -> 1274, `000053` ->
  1155) and that symbol's own timeline is the animation.  The standalone keeps
  only the characters the effect reaches (the library is 796 KB and its XML
  36 MB, which makes a frame-exact Ruffle reference take forever; pruned they
  are 273 KB / 12 MB) and replaces the library's four empty root frames with
  one placement of the effect sprite.  The art is drawn *around the origin*,
  not on the library's 550x400 canvas, so the stage is rewritten to 375x300
  with the sprite at (187.5,150) -- without that the movie is a clipped corner
  sliver.
- What each one plays comes from its class.  Chip 53's `onStaged` starts at
  `start` and its ENTER_FRAME listener loops `start`..`endStart` (1..54) for as
  long as it is worn, so that block is its movie.  Chip 37 has no idle motion at
  all: it stops on frame 1 and its clicks run `fill` (2..31) and `empty`
  (33..75), so the export plays the whole cycle and loops where 75 returns to 1.
  Both are AS3, so there are no frame scripts to freeze or park: `pauses` is
  empty by construction and `export_chip_movies.py` gets an explicit branch for
  them (`elif chip in (37, 53)`).
- Against Ruffle per frame, chip 53 reads **mean 0.74/255 (worst 3.16, frame
  3)** over its 54 frames.  The earlier 1.70 (worst 4.03 on frame 9) was a
  frozen-reference artifact: chip 53 is AVM2 like 37, so the same recipe
  applies -- strip `DoABC2Tag`/`SymbolClassTag`/`ProtectTag`, cut 1155 to its
  Nth `ShowFrame` and flatten it to one frame (replay frames 1..N, one
  `ShowFrame`, actions dropped), one pose per page.  Its 126 frames hold one
  multi-frame child, clip 1139 (122 frames), placed on 1155's frame 1 and itself
  holding the single-frame pieces, so the flatten has to recurse: 1139 is cut to
  age N and every other clip is single-frame, which leaves nothing on a
  frame-action stop.  No shift helps (ruffle N-2..N+2 read 0.74-0.76).  Frame 3
  is the export's own outlier, not a state error: `frame_003.svg` draws the bow
  tie edge-on, as the strip seen side-on (its five `x5_shape1` paths are the
  turned set, six in every other frame) for that one frame, while frames 2 and 4
  and all 54 Ruffle states show it face-on; without frame 3 the mean is 0.69.
  The 54 frames hold seven distinct drawings (the bow tie steps through its
  poses rather than tweening), which is what the SWF's ratio-driven placements
  do.  Reference builds and the metric are in `Logs/chip_0053/ref/`
  (`measure.txt`).
- Chip 37's water is filled, and the earlier "Ruffle draws the jar's fill as an
  outline only" note was wrong: it was a frozen first frame, not a renderer
  difference.  The water is two `DefineMorphShape`s (1252 fills, 1263 empties),
  each one solid `#cccc00` at alpha 127 with a zero-width, zero-alpha stroke --
  the same kind of morph the library uses elsewhere (effect 16's 1364, effect
  135's 848/850/852/853), and Ruffle draws both at every ratio.  What hid it is
  the effect's own ActionScript: `InteractionEffect`'s constructor runs
  `gotoAndStop(1)`, and `effect_000037.onStaged` then calls `setClickResponder`,
  which needs the Sitekick (`Sprite(_sk)`) that a standalone SWF does not have.
  Ruffle logs the throw (`TypeError #1009 at setClickResponder`), the playhead
  never leaves frame 1, and frame 1 is an empty jar -- the water is not placed
  until frame 18, and the fill/empty labels only run on a click.  Everything
  below was measured that way, so a Ruffle reference for these AS3 effects has
  to drop `DoABC2Tag`/`SymbolClassTag` (and `ProtectTag`) from the extracted
  XML before `-xml2swf`, which lets the timeline play on its own:
  * with the script stripped the jar fills and drains exactly like the export
    (`Logs/chip_0037/probe/noas3*.png`, `liquid-compare.png`);
  * a per-frame reference cannot be built by stopping the movie.  1274 is AVM2,
    and in an AVM2 file the `DoAction` stop `ruffle_frames.py` appends is AVM1
    bytecode that never runs, so every "frozen" SWF loops and the screenshot
    samples a random pose -- which is why single matched pairs (state 45 against
    `frame_042.svg`, state 56 against the half-filled drawing) looked right
    while no range did.  Cutting 1274 to its Nth `ShowFrame` *and* flattening it
    to a one-frame movie (replay the tags of frames 1..N in order, one
    `ShowFrame`, drop the actions) holds the pose instead; every clip inside
    1274 is single-frame, so that state is deterministic.  Capture one pose per
    page: a 15-tile grid of these high-layer movies still returned stale first
    frames even in headless capture;
  * the morph alone, played at ratios 0 / 21845 / 43691 / 65535 on a plain
    stage, is filled in all four (`Logs/chip_0037/probe/probe4.png`), so the
    fill is neither alpha-, mask- nor ratio-dependent: neither 255 alpha, nor
    removing the `clipDepth` masks, nor moving the water to the top depth
    changes the frozen frame, because none of them move the playhead.
  The export therefore stays as FFDec draws it.  Measured per frame over all 75
  frames, scripts stripped and index aligned, the export reads **mean 2.66/255
  (worst 3.58, frame 57)** on the same whole-stage metric as chips 7-16 -- not
  the 3.95 a single frozen frame 1 suggested, and no frame stands out.  The two
  sides follow the same timeline, which is what fixes the alignment: empty to 11,
  the drops (1243-1248) land 12-17, the water body is placed on 18 and the jar is
  full by 21, holds to 55, drains 56-66, empty again from 66 -- so the fill and
  drain in these 75 frames are the timeline's ratio tween, not the AS3 click
  (`fill` 2..31 / `empty` 33..75), which needs the script back.  A shifted
  comparison is no better (ruffle N-1..N+1 all read 33.4-33.6 on the art-only
  metric against 33.0 for N).  Over art pixels only the two differ by ~35 levels
  per channel, uniformly, export darker: that is the glass composite, not a
  state error -- the water path carries `fill-opacity="0.49803922"` as the morph
  does -- and it is the same order as the in-chip residuals the white-paper
  metric gives elsewhere (chip 16: 32.88), so nothing was rebuilt.
- Play-mode, both in the gallery: chip 37 `frames 75 loop 1..75`, chip 53
  `frames 54 loop 1..54`, two wraps each and never held
  (`Logs/chip_0037_play/report.txt`, `Logs/chip_0053_play/report.txt`).
- `Tools/SwfToSvg/display_path.py` derives the four things those patches were
  written by hand from a movie's own ActionScript: the `display` entry (or the
  frame the root stays on when the host's `gotoAndPlay("display")` misses it),
  the clips a script parks and the frame each lands on, the idle block the root
  repeats, and the sound starts that can never fire because the movie ends
  before them or the clip they sit in is parked.  It shows the `if` a park sits
  inside (chip 7's rings only go to `special` when the score tops out; chip 9's
  `side` is guarded by the display flag), and it exports the scripts from the
  *original* SWF into its own `<TMP>/<chip>/path/` dir so a previous export's
  patched sources are never read.  `--check` re-derives chips 7-16 and compares
  them with the constants in `patch_chip13/14/15/16.py` and the ranges above:
  every one matches except chip 13's cycle.  Sprite 52 is 19 frames and is
  placed on root 9, so root 12 shows its 4th frame and the loop is 12..30;
  `patch_chip13.py` appends 20 frames and loops 12..31, whose last frame repeats
  the first (`Chip_0013/Movie/frame_031.svg` is byte-identical to
  `frame_012.svg`), i.e. one duplicated frame per cycle.  It does not resolve a
  target computed at run time (chip 7's `bestScore % 11 + 1`), a clip reached
  through named parents (chip 8's `fixit.bottom.tools.antenna`), or clips parked
  only by their own `stop()` -- that case is `patch_stopped_clips.py`'s freeze.

- Chip 11 against its scripted Ruffle reference: mean 4.75/255 (worst frame 38,
  9.95) before the patch, 1.36 (worst 1.96) after; root 1-20 goes 5.91 -> 1.24
  and 21-40 6.03 -> 1.71, with the empty tail at 1.00 throughout.  After the
  hover-loop cut (below) it is 1.43 over the 35 frames it still exports.
- **The idle section is a loop, not a timeline.**  Every chip but 13 ends its
  display section with a frame script that jumps back: `gotoAndStop("hover");
  play();` on 8-11 and 14-16, `gotoAndStop("float"); play();` on 7, and a
  literal `gotoAndStop(1)` at root 25 on 12, whose idle is a click cycle rather
  than a labelled block.  Chip 16 has that jump too (root 21 -> `hover`), but
  it is unreachable: its root never leaves frame 1 on the display path.  Chip 13's idle is a stop instead: root 11 (`display`)
  stops while the fish (sprite 52) keeps playing its 20-frame tween, so
  `patch_chip13.py` holds the root for one fish cycle and the export loops
  12..31.  Flash therefore plays the intro once and loops that block for
  as long as the chip is on the Sitekick; the frames after the jump (chip 10's
  antenna going down, chip 11's monster walking back, chip 9's arm pull-out)
  are the retract, and only an outside caller can reach them.  Nothing in the
  game does: `ChipGallery` keeps an effect until its chip is clicked again, so a
  linear export used to play the retract once, after the hover pass, and freeze
  on it -- chip 9 shipped 152 frames against the 27 the chip shows.  The export
  now ends one frame before the jump and `movie.json` carries `"loop": [first,
  last]` (1-based, inclusive), which `ChipMoviePlayer` repeats instead of
  finishing.  `Tools/SwfToSvg/hover_loop.py` finds the jump (the *first*
  backward jump, label or literal frame; chip 8 has a second at 40 inside the
  retract path); sound cues and pauses past the cut go with it.  Ranges: 7
  15..34, 8 16..35, 9 10..27, 10 17..36, 11 16..35, 12 1..24, 13 12..31 (the
  held-root fish cycle), 14 3..29, 15 4..22, and no loop for 9, 11 and 16.  Chip
  16's patch authors nothing, so its export is the whole root timeline (39
  frames) played once, ending on the finished snowman.  Chip 15's frame-32
  retract cue, chip 9's sound cues and several retract SFX files no longer ship
  because nothing can reach them.  Effect prefabs carry `loopFrom`/`loopTo`
  (from `ChipMovieBuilder`), so a re-export needs a prefab rebuild for the new
  frame count to take effect.
- **The parked pose is off for 14 and 15** (`PARK = False` in each patch):
  parking the spider or the headphones baked one still frame, and a chip whose
  clip holds one pose reads in the game as no animation at all.  With the park
  off both export their clips' own timelines (29 and 22 frames, all distinct)
  and keep looping (`patch14.loop()` 3..29, `patch15.loop()` 4..22).  Chip 16 has
  no park left at all -- its patch only runs the stopped-clip freeze -- and its
  39 frames play once, holding the finished snowman: the hat only arrives on the
  last frames, so the hover block it used to loop (3..20) never showed it.  Their
  cues come back with them: `export_chip_movies.py` used to force `sounds = []`
  for 14 and 15 because the park skipped both, which is now a no-op.
- Chips 9 and 11 **do not loop**: both play their sequence once and hold the last
  frame (`loopFrom`/`loopTo` 0, 0).  Chip 9 exports its whole state machine --
  132 frames, cut where `frame_132` onward are one pose and the hole has closed
  -- instead of the 27-frame hover block, and chip 11 stops at 35, with the
  monster fully open, rather than replaying it.
- `--playhead` is only for clips whose state is *not* baked yet.  Once a patch
  authors the clip's timeline (chips 9, 10, 11), run `ruffle_frames.py` without
  it: the authored clip already advances one frame per root frame, and a
  playhead merges its frames from the start, which reads as the clip running a
  dozen frames late.  Chip 11 measures 5.03 that way and 1.43 with no playhead
  on the same export.  Chip 13's fish is the other case: it is not authored, but
  it keeps advancing under a stopped root, so its reference is built with
  `--playhead 52=1@9`; the merge path wraps it every 20 frames instead of
  holding its last frame.
- Tool scratch stays inside the project: every script's default work dir is
  `Temp/swftosvg/` (gitignored, like `Logs/`), one `<chip>/` per movie holding
  `svg/`, `png/`, `scr/`, `xml/` and `snd/`, with `lib/` for `extract_effect.py`'s
  cached library XML, `review/c<chip>/` for `ruffle_review.py`'s frozen SWFs and
  `sfx/` for `export_sfx.py`'s decompiled sounds.
  A normal run therefore writes nothing outside the Unity folder.  FFDec's
  flatpak mounts `$HOME`, which covers a checkout under it; `extract_effect.py`
  stages the library through `$HOME/.cache/swftosvg/` only when the checkout
  lives outside `$HOME`, and copies the result back.
- `Tools/SwfToSvg/patch_stopped_clips.py` runs on every chip during export. It
  freezes the stops no script can reach (a clip that stops itself, either with
  art after the stop or on its last frame, and is placed under a name the
  ActionScript never mentions and never builds on the fly) so the clip holds its
  parked frame instead of playing out and looping. Clips whose names the scripts do jump are left alone: those
  need their jumps authored by hand, as chip 8's `bottom`, `antenna`, `tool` and
  `tools` are.  FFDec never runs a frame script, so any clip
  whose `stop()` matters keeps advancing and alternates its art every frame:
  that reads as flicker in Unity and is invisible when inspecting single frames.

### Ruffle reference

- `Tools/SwfToSvg/ruffle_preview.html` plays a SWF with Ruffle.  Serve the repo
  root and open it with the movie as a query parameter:
  `python3 -m http.server 8137` then
  `http://127.0.0.1:8137/Unity/Tools/SwfToSvg/ruffle_preview.html?swf=/Unity/SWF/chip_0008.swf`.
  The stage is 375x300, so a screenshot is directly comparable with an exported
  frame rendered at the same size.
- These chip SWFs are interactive: they hide themselves and open
  `ytv.com/flash404.asp` unless they think they are on the site, and they stop
  until a chip-data record arrives.  For a linear reference, build a copy with
  the root frame scripts removed (as `patch_chip8_tools.py` does for the export)
  and, if the script's data load is involved, serve
  `undefinedcommon/inc/sitekick/getChipData.asp` with `chipData=nodata` next to
  the movie so the default `1~2~3~4~5~6` assignment is used.
- Ruffle has no frame-stepping API, so a recording only samples the loop.
  For a frame-exact check use `Tools/SwfToSvg/ruffle_frames.py`: it writes one
  SWF per frame (root trimmed to that frame and stopped, every child clip cut
  to the frame it shows there and stopped), `ruffle_frames.html` loads them in a
  grid at 375x300, and the script diffs each tile against `frame_NNN.svg` in
  stage pixels.  Worst-frame lists out of that are the frames to look at; a
  handful of pixels of error is antialiasing, tens of grey levels is a real
  difference (a clip at the wrong playhead, art missing, or a bad transform).
  Run it with `--capture`: that drives a headless browser itself and saves the
  grid screenshots, so the check no longer depends on the Freebuff window being
  drawn or on the page's `post` composite (which returns duplicate tiles when
  nothing is on screen).  Its launch flags are in `Tools/SwfToSvg/README.md`.
- A frame diff proves an export is faithful to the SWF it was made from; it does
  not prove *timing*.  The frozen build advances every clip in lockstep unless
  `--playhead` says where the script jumps it, so a SWF whose state is not baked
  in reproduces the export's own assumption and agrees by construction: on chip
  0008 the arms region reads 5.48/255 for the current export and 5.04 for the
  lockstep one, while a repeat capture differs by 0.00.  Judge timing from the
  SWF data instead: `Tools/SwfToSvg/verify_arm_timing.py` checks the root frame
  actions, the labels they name and the frames the exported clips actually
  carry, tag for tag.
- A frozen clip is cut one of two ways, and they are not interchangeable.  A
  clip the root script jumps (`--playhead`) keeps the pose the jump names: its
  frames up to the playhead are merged into one, so chip 9's arm shows its frame
  53 while the root is on 33.  A clip no script jumps keeps its timeline cut to
  the frames it has played since the frame it was placed on, stopped on the last
  one, because the placement offset is part of the state: chip 7's butterfly
  clip (104) is placed on root 13 and is 18 frames old on root 30, so it shows
  its 18th frame, not its 30th.  Merging the second case instead is invisible on
  a clip placed on frame 1 and moves the references by whole grey levels (chip 7
  1.06 -> 2.03).  Both were re-measured after this: chip 7 is pixel-identical to
  the run that read 1.06, chip 8's lockstep build reads 5.69 whole-frame against
  5.70 before (nine frames differ by up to 1.2 because the four short clips
  placed more than once, 51/71/82/84, are cut from a different instance), and
  chip 9's frames 33-46 are unchanged at 1.53 mean, worst 1.81 on frame 35.
- When a browser is driven headless for Ruffle (e.g. `flatpak run
  com.brave.Browser --headless=new … --screenshot=…`), launch it muted with
  `--mute-audio`: the chip movies carry sound cues, so an unmuted headless
  player plays them at full volume.  Ruffle also needs
  `--autoplay-policy=no-user-gesture-required`, otherwise it only shows its play
  button.

## Chips and the gallery

- Chip art lives under `Assets/Chips/<range>/Chip_XXXX/`: `Sprites/` (static
  icon, one SVG per chip), `Movie/` (baked animation frames), `SFX/`.
- **Every chip sprite is an SVG; no PNG copy belongs next to it.**  Chips 161,
  177 and 286 carried `chip_XXXX_front.png` / `_back.png` beside the SVGs they
  were rasterised from -- 1600 px at 400 ppu, 4 units wide, byte-identical to a
  fresh `rsvg-convert` of the SVG (mean |diff| 0.00, ink IoU 1.000) -- and three
  effect prefabs pointed at the PNG.  The SVGs are now the sprites.  Two things
  to know when doing that on another chip:
  * a gradient SVG sprite needs `Assets/Materials/ChipMovie-Vector.mat`
    (`Unlit/VectorGradient`, fileID 2100000, guid `31d1e238...`) on the
    renderer: under the built-in sprite material 161's dungeon came out black --
    the same trap chips 20 and 42 hit from the other direction;
  * the SVG importer crops the sprite to the drawing's geometry bbox, not the
    viewBox, so a heading with empty margin shifts when it stops being a PNG.
    Set `svgPixelsPerUnit` to `viewBox width / 4` (the PNG's 4-unit width) and
    move the child by `(bboxCentre - viewBoxCentre) * 4 / viewBoxWidth *` its
    own local scale, y negated (SVG is y-down).  Of the six, only 161's and
    177's front needed it (`f = 1.41` and `1.29`); 286's back took 0.004 and
    the three `back`/`front` pairs whose bbox already equals the viewBox none.
- **Where an effect sits on the Sitekick.**  `sitekick.swf` creates
  `effectHolder` on its own root (`_global.skMain = this`, frame 1) and loads the
  chip's `effect.swf` into it at (0, 0) (`funcLoadDisplay` sets only
  `effectHolder._x = 0`), so the effect's 375x300 stage lands 1:1 on the
  Sitekick's stage.  The body's registration point is at stage (187.9, 139.2)
  (the root's `sitekick` object is placed at 3758,2784 twips and puts sprite 214
  at 0,0), so the stage centre -- where every chip effect is drawn -- is
  (-0.4, +10.8) px from the body pivot.  `build_prefabs.py` carries that as
  `STAGE_OFFSET`; anchoring effect art on the registration point instead puts it
  10.8 px too high.  Chip 17 was the first to show it: its grin's top lip sat
  across the Sitekick's eyes, and at the stage-centre offset it sits under them
  (`Logs/chip_0017_play/reference.png` is a Ruffle render of `sitekick.swf` with
  the effect at the stage centre, `compare.png` is that against the gallery
  capture).  Both use 0.01735 units per SWF pixel, so the offset is the only
  difference -- the size was never wrong.
- **Every static effect sprite is placed from its art bbox with that offset**,
  and 805 prefabs written before `STAGE_OFFSET` existed were not: they sat
  exactly `(0.4, 10.8)` px high, which is `dy = +0.18738`, `dx = +0.00694` in
  prefab units (`U = 6.94/400`).  The rule that holds for a single-renderer
  static effect is
  `local = ((bboxCx - 0.4) * U, -(bboxCy + 10.8) * U)` on the art child, and it
  is the rule the Ruffle-checked chips 17-35 reproduce to 0.00000 (17, 18, 20,
  22-30, 35 all match exactly), so it is the convention, not a coincidence.
  Chips 101 upward matched the same formula *without* the offset, i.e. 10.8 px
  high on the face, from 101 to 1375 -- 805 prefabs.  They were corrected in
  place (only the art child's `m_LocalPosition` line changes; a scan of all 828
  single-renderer static prefabs now reads 0 off the convention).  Two traps:
  * don't reach for `build_prefabs.py --write` to do it.  Its rewrite also
    changes the sprite's `.meta` (`svgPixelsPerUnit` to 400, `svgType` 0 -> 1,
    sprite rect in px) and always writes the built-in sprite material, so it
    would undo chips 161/177/286's PNG->SVG repoint and any vector material;
  * the formula only applies where the renderer's sprite *is* the chip's
    `_effect.svg`.  Chips 161, 177 and 286 draw `_back.svg`/`_front.svg` from a
    hand-measured `front`/`back` pair with its own bbox compensation
    (`(bboxCentre - viewBoxCentre) * 4 / viewBoxWidth * localScale`, y negated);
    rebuilding those from the effect canonical svg moves them a whole body
    height, so they are excluded.
- **The same omission is still in every non-static prefab built before
  `STAGE_OFFSET`** -- the single-renderer pass above never touched them.
  Counted from chip 138 up: 143 extras-style prefabs (`chip_XXXX_extras` at
  (0, 0) instead of (-0.00694, -0.18738)) and 222 part-animated ones (part node
  at the track translation with no offset).  Two shapes, and the fix differs:
  * `chip_XXXX_extras` carries back/front/particle layers; shifting the node is
    enough for back/front, but particles also need their authored
    `x_swf * U` (the builder writes it, the old prefabs have every particle at
    x = 0 -- chip 151's four snow columns all fell down the centre line);
  * a part-animated chip's `Animations/Chip_XXXX.anim` bakes the track position
    into the `m_PositionCurves` keys, and an Animator overrides the node's
    static `m_LocalPosition` every frame, so shifting the prefab node alone
    changes nothing.  Add the offset to every position key too (x - 0.00694,
    y - 0.18738); 36 keys for chip 145, one per frame.
  Chip 145 was fixed first (prefab node + all 36 keys; the gallery capture moves
  by exactly (-0.017, -0.469) world units, i.e. the offset times the preview's
  2.5 scale, and `ChipPlayCheck --chip 145` still reads `renderers 1 sprites 1`).
  Chip 151 was fixed as well (extras node + the four particle nodes and their
  clip keys; the four columns now sit at -206.25/-68.75/+68.75/+206.25 SWF px,
  17.9 units of preview width where they used to be stacked).  Its check is the
  particle composite in the Ruffle-reference section (it reads the group 10.8 px
  high at the pivot and on the stage centre after the fix), and its flake sprite
  also needed the import scale corrected (171.7241 -> 57.6361, 0.336x -> 1.0x,
  15x16.7 px): the prefab's 128 px compensation is bbox-centre based, so the
  node centres stayed at -3.737/2.227/8.191/14.155, -0.484.
  The rest of the class (380 prefabs) was then swept with
  `Tools/SwfToSvg/fix_stage_offset.py`: it rebuilds each chip's expected
  un-offset node positions from the effect json (track matrix for a part, the
  base SVG's bbox centre for a base, `(0, 0)` for extras/particles), classifies
  a file as old / already fixed / neither, and only rewrites the position
  lines and position keys.  It is idempotent (`--write`, then a dry run reports
  every chip as already offset).  Dry run before writing: 0 chips that fit
  neither shape.  Excluded and left alone: 75 chips with no `effect.json` and
  no renderer -- 139, 223-296 and a few later ones (1228, 1245, 1301) whose
  `chip_XXXX_effect.svg` is an empty viewBox -- and the 161/177/286 hand-built
  back/front pairs.  Chip 213's `Orange`/`Purple`/`Yellow` clips name nodes
  (`chip_0213_orange`, `*_ring`) that do not exist in its prefab; those curves
  were deliberately left untouched as inert, while its live `Chip_0213.anim`
  (part_1/5/9) was shifted.
  Verification: 28,072 position keys across 270 clips differ from HEAD by
  exactly the offset (particle clips: x set to `x_swf * U`, y untouched), with
  the Euler/scale/float sections byte-identical; 2,218 `m_LocalPosition` lines
  changed across 382 prefabs and no other line type; `ChipArtValidate` loads
  all 1375 prefabs / 2144 renderers; `ChipPlayCheck --chip 152` shows its four
  particle columns spread over 18.49 preview units, and `--chip 146` still
  renders one sprite.  The first batch wrote positions with `%g` (6
  significant digits, <= 5e-6 units of error); `fmt()` now keeps 7 decimals.
  The validator's one remaining problem is unrelated and pre-dates this pass:
  `Chip_1236/Sprites/chip_1236_back.svg` does not import as a Sprite, so that
  prefab's single renderer has no sprite.
- **A spawned-particle effect has no timeline, so it is checked with a
  body-relative composite rather than a frame diff.**  Chip 151's flakes are
  `new FlakeMC()`s added by `effect_000151.onTimer`; the effect SWF draws
  nothing on its own and `ruffle_frames.py` has no frame to freeze.
  `Tools/SwfToSvg/sitekick_particles.html` is its reference: it plays
  `sitekick.swf` in Ruffle at 1:1 and drops copies of the chip's particle SVG at
  SWF stage coordinates -- one SVG unit per SWF px, origin at the stage centre,
  `?art=<svg>&at=x,y;x,y&scale=` -- which is the chip 145 static composite's
  375x300 setup with the flake art in place of the effect SVG.
  `ChipPlayCheck --hold` is the capture side: it disables the spawned effect's
  Animators before their first update, so the prefab is measured at its authored
  pose, the only state a still composite can match, since the flakes tween
  ±3.47 units about their node.  With the prefab's own placement put into the
  page and `Tools/SwfToSvg/measure_particles.py` reading both (body = largest ink
  blob, flakes = light blobs clear of the body's columns, every figure divided
  by body height so the two zooms cancel): the group's centre against the body's
  centre is -0.053 body heights at the pivot (pre-fix) and +0.140 at the stage
  centre (post-fix), 11 px on a 57 px body, against -0.032 and +0.164 in the
  `--hold` captures.  So the 10.8 px / 0.469 preview-unit fix is carried into the
  gallery, and the leftover 0.02 body heights (~1.2 px) is the body mask --
  Ruffle's black silhouette including its outline against Unity's white shell --
  which cancels in the before/after difference (`Logs/skcomp/c151_compare.png`,
  `c151_ppu.png`).  A pre-fix capture needs the old prefab: write
  `git show HEAD:./Assets/Chips/0101-0200/Chip_0151/Chip_0151_Effect.prefab`
  over the working copy, run, then put the working copy back (verify it, the
  file is the fix).
- **Those four columns are a spread over the library canvas, not the SWF's spawn
  rule.**  `corus/effects/FlakeMC.init` sets
  `x = Math.random() * stage.stageWidth` (0..375), `y = -25` (25 px above the
  stage), `scaleX = scaleY = Math.random()` and tweens `y` to `stageHeight + 25`
  (300) over `3 + Math.random() * 5` s, linear, while `effect_000151.onTimer`
  adds `Math.random() * 10` flakes a second.  `build_chips.py` cannot port a
  random field, so it spreads `PARTICLES = 4` copies evenly over the *library's*
  550x400 canvas (`x_swf = -STAGE_SWF[0]/2 + (n + 0.5) * STAGE_SWF[0]/PARTICLES`,
  i.e. -206.25/-68.75/+68.75/+206.25), and the outer two are outside the 375 px
  stage the effect is drawn on -- the composite shows two flakes where the
  prefab has four.  The fall is ±200 px over 3.5/4.5/5.5/6.5 s against the SWF's
  +175 -> -150 px, and every copy draws at scale 1 where the SWF randomises 0..1.
  The group's *origin* is therefore what the offset fix can be judged against;
  the columns, the fall length and the scale are stand-ins (chips 152, 153, 322,
  452, 786, 1109 and 1133 share the builder's spread).
- **A spawned particle is a stream, and `ChipParticleField` runs the SWF's rule.**
  The four columns are now the authored pose only: the prefabs carry a runtime
  field (`Assets/Scripts/ChipParticleField.cs`, guid `3f7c1a5e...`) written by
  `Tools/SwfToSvg/build_particle_fields.py` from each chip's
  `Sprites/chip_XXXX_effect.json` and `effect_clips.json`.  It spawns a random x
  across the 375 px stage, `scale = Math.random()` (0..1), 25 px past the stage
  edge, tweens linearly to the other side and plays the symbol's frames at the
  movie's 31 fps on each particle's own playhead -- the clip keeps running while
  it falls, which the bake never did (only frame 1 of each symbol was
  referenced and no particle `.anim` carries an `m_Sprite` track, so all eight
  chips drew a still flake/bubble).  Data per chip: one
  entry per *distinct* symbol (151/152/153/322/452/786 one, 1133 two, 1109
  four), each with every exported frame; `rising` from the class (`BubbleMC`
  starts at `stageHeight + 25`, `FlakeMC` at `-25`); and the burst read out of
  the effect class rather than assumed -- `onStaged` starts `new Timer(1000)` and
  `onTimer` adds `int(Math.random() * 10)`, i.e. 0..9 a second, mean 4.5, while
  the tween length is `3 + int(Math.random() * 6)` = 3..8 *whole* seconds.  The
  chips differ: 322 and 1109 burst 0..5, 452's `LeafMC` falls 5..14 s and 786's
  `CoinMC` 0..5 s (a coin can be gone the tick it spawned).  The field hides the
  baked `particle_0..3` nodes on its **first update**, not in `Awake`, because
  `ChipPlayCheck --hold` disables the component in the frame the effect is
  instantiated: the authored pose stays the state a held capture measures.
  Spawn density follows: `mean burst x mean lifetime` is about 25 live flakes
  for 151 where the bake held four, and peaks near 70 at 9/s over 8 s, which is
  why the pool is 96.  `Tools/SwfToSvg/audit_particle_fields.py` is the
  no-Unity guard on that block (0.27 s for all eight): a prefab rebuild that
  drops it, or a re-export that renumbers its frames, used to show up only in a
  live run.  It fails when the block is gone, when the root no longer lists its
  component (an unreferenced block never runs), when `stageWidth`/`stageHeight`
  are missing, zero or not the 375x300 the effects are drawn on, when a symbol
  has no frames, a frame count other than the export's, or a frame guid that is
  not that sprite's meta guid.  Current tree: 151/152/153/322/452/786 one
  symbol (128/160/160/40/50/8 frames), 1133 two (400) and 1109 four (800).
- **A particle renders at the size of the art it was drawn from.**  Its prefab
  node sits at scale 1, so the only size control is the sprite's
  `svgPixelsPerUnit`, which must be `PPU / SCALE` = **57.6361** (= 1 / 0.01735,
  one SWF px in world units).  Chip 151 shipped 171.7241 (0.336x, a 5.1 px flake
  instead of 15) and the same export rule left most of the class wrong:
  `audit_sprite_scale.py` read 24 of the 32 particle renderers at 0.40-0.67x --
  152 0.49 (2.0x small), 153 0.40 (2.5x), 322 0.67, 452 0.59, 1109 0.44-0.50,
  1133 0.40-0.44; only 786 was already right at 1.003.  The tool takes the
  intended size from `size_px` in the effect json and the rendered size from the
  viewBox and ppu, prints the ratio, and `--write` pins **every frame of the
  symbol**, not just frame 1: a per-frame ppu made the 128 flake frames differ
  (171.7241 / 173.2174 / 174.7368 over one identical viewBox) and an animated
  particle would have pulsed in size.  1,746 metas now read 57.636x and all 32
  renderers report 1.000x.  The sprite child's offset is `bboxCentre * U` and
  does not depend on ppu, so only the meta line moves; the node centres stay at
  -3.737/2.227/8.191/14.155, -0.484.
- **A spawned effect is framed by its stage, and one command checks it.**
  Particles start 25 px outside the 375x300 stage and land anywhere across it,
  so a capture framed on the renderers in the prefab -- or on the one column the
  gallery camera keeps in view when the sitekick sits 5.2 units off centre --
  cannot show the stream.  `ChipPlayCheck --stage` writes `stage.png`: the
  effect's own 375x300 SWF px centred on the stage (`STAGE_OFFSET` from the
  instance origin) and scaled by the layer's `lossyScale`, since the gallery
  draws effects at 2.5x.  `sitekick_particles.html?pad=` does the same on the
  Ruffle side by widening the canvas.
  `Tools/SwfToSvg/particle_check.py --chip 151 [--unity] [--live]
  [--reference]` is the whole check now, and replaces the hand-built composite
  page plus the throwaway `Logs/skcomp` scripts: it asserts the four columns sit
  `x_swf` apart (2.386 units = 137.5 SWF px, a span of 17.89 units) within 0.01
  units, prints each renderer's size in SWF px (0.651 units / 2.5 = 15.0 x 16.7),
  fails a held capture that spawned anything, and with `--live` requires the
  spawner's own `LiveCount` to reach a third of the rule's expected concurrency
  plus an x spread of half the stage.  That count has to come from the component, not the
  capture: chip 786's four baked coins measure 7 blobs under the stream mask (10
  real coins merge into 8), so no blob floor separates them, while `LiveCount` is
  0 for anything that is not spawning and a prefab with the field block deleted
  fails outright.  The window is `maxLifetime + 2` s rather than a fixed 4.5:
  with a 1 s tick and whole-second lifetimes that is where every age class that
  can still be alive is represented, so the count matches the rule, where 4.5 s
  undercounted 1109 by about 30% and sampled 786 anywhere from 4 to 19.  Every
  chip now has a distribution, and they are checked in at
  `Tools/SwfToSvg/particle_baseline.json` (one draw per seed: live count,
  spawner spread and the window it was taken over), read against a floor of a
  third of `mean burst x mean lifetime`.  `--repeat` prints the batch's mean
  against the stored one and warns when it falls two stored standard deviations
  below, so the numbers are measured against a file rather than quoted here.
  With 786's field block removed the run reports `no particle field` and 6 blobs
  against the held pose's 7, and fails.  Batchmode seeds `UnityEngine.Random` identically on every
  launch, so a repeat without `--seed` measures one draw however many times it is
  run, and `run_unity` now refuses a report older than its own launch because
  `--live` without `--unity` used to grade the previous capture.  `--reference` drives `sitekick_particles.html` headless
  through `ruffle_frames.py`'s `serve`/`browser_command`/`capture_page`.
  Particle-for-particle comparison is impossible by construction -- Ruffle's
  `Math.random` is unseeded, so no two runs (and no capture against the export)
  put the flakes in the same places -- which is why a live check asserts the
  *distribution* (count against `mean burst x mean lifetime`, x spread and
  stdev against the stage width) and the held check asserts the authored
  columns in `report.txt`.  The counts this file quoted for chips 151, 152 and
  153 -- `live 27 of 96` on 152, `live 16 of 96` on 153, 17 blobs with a 6.34
  spread on 151 -- are one draw each, taken at the old fixed 4.5 s window with
  the unseeded batchmode default.  Re-running them reproduces those exact
  numbers instead of varying, which is the signature of a single sample: 151's,
  152's, 322's and 1133's sit inside the stored distributions, but 153's 16 is a
  low draw and 452's 14 is not representative at all -- its 4.5 s window was
  shorter than one `LeafMC` lifetime (5-14 s), so the stream had not reached the
  steady state it was being asked to show, and the same chip holds 26-55 over a
  16 s window.  786's single 4 is the other kind of tail, a quiet draw rather
  than a dead spawner.
  The floor is a third of the rule rather than half because one run is one draw
  of a 0..N burst, so a legitimate tail has to clear it: at half, 1133's seed-5
  run read 12 against 12.4 and failed, and at a third (8.2) the same draw
  passes.  The guard against a dropped field does not depend on the margin --
  that run reports no field line and `LiveCount` 0, whatever the floor -- so a
  third costs nothing and still catches a spawner that runs but far too quiet.  Both chips that draw a layer of their own -- 153's `front` heart pile, 1133's
  `back` -- used to make the live capture unreadable, because the blob count and
  spread measured that art, so the capture was skipped and those two had no
  spread assertion at all.  `ChipPlayCheck --hide-back` marks every renderer
  whose sprite is not a particle, turns them off for `stage.png` only and
  records `back hidden <sprite>  (stage.png only)` -- `resting.png`,
  `resting-art.png` and `resting-close.png` stay the chip as it ships.
  `particle_check` passes the flag whenever the chip's effect json has a
  `back`/`front` clip and takes the held baseline the same way
  (`Logs/chip_XXXX_play_hold_hidden`), so the capture floor and the spread apply
  again.  Those layers sit almost entirely off the 375 px stage -- their art is
  2784 and 4364 library px wide against a 550 px canvas -- so re-enabling them
  moves the gallery captures by 2-5 px on 153/1133; the tight stage framing is
  the only capture that counts them.
  **The spread is read from the spawner, not the capture.**
  `ChipParticleField.LiveX` returns each live particle's spawn x in SWF px from
  the stage centre and `ChipPlayCheck` writes them as a `live x -154.90,...`
  line; `particle_check` computes the range and stdev from those values as a
  fraction of the effect's stage and gates on a floor that scales with the
  count (below).  The stage is not assumed: `ChipParticleField` reads
  `stageWidth`/`stageHeight` from the prefab (`build_particle_fields.py` writes
  them), `ChipPlayCheck` reports them beside the x values as
  `field stage 375 x 300 px  capture margin 1.10`, and the check divides by that
  width and scales `stage.png` pixels with that margin (`STAGE_PX` and the old
  `1.1` constant are gone).  A live report without the line fails with `the
  width the spawn rule drew x in is unknown; 375 px is not assumed`, exactly as
  one without `live x` does, and `StageBounds` frames the capture from the same
  numbers, so an effect drawn on a wider stage is neither mis-framed nor
  mis-scaled.
  **The spread is a third of the rule.**  The x spread only says where the
  spawn rule draws; it cannot see that a particle starts 25 px past the edge,
  crosses the stage linearly over its own lifetime, draws at `Math.random()`
  scale or plays its symbol while it travels.  So `ChipParticleField.LiveTracks`
  hands the check every live particle and `ChipPlayCheck` writes the constants
  and one line per particle:

  ```
  field rule  particle margin 25 px  symbol 31 fps  lifetime 3..8 s  burst 0..9 every 1 s
  live particle  x 9.61  y 34.99  age 2.00  life 5.00  from 175.00  to -175.00  scale 0.643  frame 62 of 128
  ```

  `particle_check` requires, per particle, `|from| = stageHeight/2 + margin`
  (175 px on this stage, i.e. 25 px past the 150 px half-height, not the
  stage's own edge), `to = -from`, a lifetime inside the field's `lifetime`
  range, and `y` within 2% of the traverse (7 px here) of `from + (to - from)
  * age / life` -- the residual a fixed y or a half-speed fall shows.  Scales
  must lie in 0..1 and span the same 0.1% quantile floor as x, because they
  come off the same uniform stream; the reported symbol rate must match the
  chip's export (31 fps), each symbol must carry the export's frame count, and
  each particle's frame must be the one its age puts it at, within a frame of
  rounding.  A report without `field rule` fails as one without `field stage`
  does, so a live capture taken before these lines is stale evidence.
  Seed 9, one draw each, all eight pass: 151 34 particles, 152/153 36, 322 24,
  452 58, 786 19, 1109 23, 1133 34, every one starting at 175 px and ending at
  -175 (152/153 the other way, `from -175`), lifetimes inside each rule (786's
  0..5 s, 452's 5..14 s) and scales 0.07-0.97 (151/152/153/1133), 0.07-0.99
  (322/1109), 0.01-0.99 (452) and 0.18-0.93 (786) against floors 0.61-0.85.
  The frame relation is what catches a still symbol: 152's sample reads frame 61
  of 160 at age 2.00 s and 31 fps, one behind the 62 the age gives, which is why
  the tolerance is a frame rather than exact.
  Rewritten out of a real 151 report, each defect fails the run (rc 1): every
  particle held at its start y -- 30 of 34 off the traverse, worst 350 px; a
  half-speed fall -- 30 of 34, worst 175 px; every scale at 1.000 -- "range
  0.000, floor 0.759 for 34"; the symbol at 15 fps -- "the report's symbol rate
  is 15 fps, the chip's export says 31"; a start on the stage edge (150 px) --
  34 of 34 wrong and 29 of 34 then off the traverse; one frame per symbol -- 34
  of 34 "play 1 frame(s); the export has 128".  Deleting the `field rule` line
  fails with "the particle margin, symbol rate and lifetime the field runs are
  unknown".  `--repeat` applies the same gate per rep, so a batch cannot print a
  distribution over a field that is traversing wrongly.
  A live report with no `live x` line fails outright (single run and `--repeat`
  alike): the capture is never the substitute, because on this same draw it
  reads 0.481 where the spawner reads 0.95.
  The capture cannot be trusted for it: blob detection merges particles where
  the art overlaps (153's 36 live read as 29 blobs; 151's 14 as 9), and the two
  extremes are usually the particles it loses.  Measured from the spawner; the
  per-chip draws, seeds and stdev are in `particle_baseline.json`.  151's
  seed-5 draw is the clearest case: 14 live span **0.95** of the stage (stdev
  0.25), while its capture read
  **0.481** from 9 blobs -- the blob figure was half the field and failed the
  floor on a uniform draw.  The capture still prints its own `x spread ... of
  the 375 SWF px stage` as corroboration, and at a full stream it reads slightly
  *wider* than the spawner (153 1.032 against 0.97) because a blob box carries
  the particle's own art width, ~10 px per side.
  The same method measured the rest of the class, stored in that file.  786 is
  the tightest by far -- its lowest draw is 0.59 at 7 live, and 322/1109 reach
  0.68 at 14-16 live.  A fixed half-stage floor is wrong for that tail: with `n`
  points uniform on the stage the span has `P(<= r) = n*r**(n-1) -
  (n-1)*r**n`, so 0.5 is missed by 31% of legitimate 4-live draws and 19% of
  5-live ones, and 786's count floor (a third of 11.25 = 3.8) admits both.  The
  gate is therefore the 0.1% quantile of that span distribution, computed per
  run from its own count: 0.06 at 4 live, 0.24 at 7, 0.38 at 10, 0.50 at 14,
  0.55 at 16, 0.77 at 36 and 0.84 at 55, so a full stream still has to cross
  most of the stage while a quiet draw is failed only for being improbable.
  Every stored draw clears it (786's 0.59 against 0.24 at 7; 1109's 0.68
  against 0.55 at 16), and an x cluster inside +-5 px fails at both 10 live
  (0.03 against 0.38) and 36 live (0.03 against 0.77).  786's stored draws span
  0.59-0.95 over seeds 3-9, and its low tail sits 0.35 over its floor, so the
  count-scaled gate is not the binding
  one on this chip after all.  Its 16-live capture read 0.59 while the spawner
  read 0.95, the same 9-of-16 shortfall the blob measurement shows everywhere.
  Extent alone does not reject a baked pose: with `LiveCount` 0 there are no x
  values to read, and the four authored columns measure 1.134-1.169 of the
  stage from the capture (wider than a field, by construction).  A baked effect
  fails on `LiveCount` 0 and its 6-7 blobs instead.
  The `--reference` capture is what the held numbers are judged against:
  at `at=x,0` the composite reads the group **+0.1404** body heights above the
  body centre with a 15.3 SWF px flake, the `--hold` capture **+0.1638** with a
  17.4 px one, so the difference is 0.023 body heights (1.3 px) -- the body mask,
  Ruffle's black silhouette against Unity's white shell -- which is the same
  residual the chip 151 work reported.
- **The particle frames are needed, not dead art.**  Before the field only frame
  1 of each symbol was referenced, so 1,714 of the 1,746 particle metas were
  weight in the build with nothing drawing them.  They are all referenced now.
  The cost to watch is texture memory rather than correctness: 151 carries 128
  frames, 152/153 160, 322 40, 452 50, 786 8, 1109 200 per symbol (four symbols)
  and 1133 200 (two).  Thinning to the SWF's 31 fps is the lever if import time
  or memory becomes a problem; nothing needs pruning.
- **Small particles are not blurry, and that is checked by the import scale.**
  Every particle sprite's texture is 4.9-8.7 pixels per SVG unit with
  `sampleCount: 4` (151: a 116 px texture over a 22.4 unit box for 15 px of ink,
  so about 2x the pixels the 1440 capture uses), so the import is not what limits
  a 15 px flake; the edge difference against Ruffle is its rasteriser, and the
  5x zoom panel `Logs/skcomp/c151_ppu.png` is the visual check.  The size,
  though, is measured: 15.0 x 16.7 SWF px in both panels and in `report.txt`.
- **The measurements live in the repo.**  `Logs/` is gitignored, so the chip 151
  check's `Logs/skcomp/measure_flakes.py`, `panel151.py` and `panel151_ppu.py` could not be
  re-run from a clean clone even though this file quoted their numbers.
  `Tools/SwfToSvg/measure_particles.py` is the tracked version: the same
  body-relative group centre (normalised by body height) plus what a stream
  needs -- blob count, mean blob height in SWF px, and x spread and stdev as
  fractions of body width, which is how a uniform `Math.random()` field is told
  from four fixed columns.
- `ChipMovieBuilder.Anchor` still holds the old assumption: it puts the movie's
  stage centre at (0.1, -2.25) px from the body pivot, 13.05 px above the
  holder's (-0.4, +10.8).  Chips 7-16 were measured against standalone Ruffle
  renders, which do not include the holder, so their placement on the Sitekick
  is off by that much and has not been re-checked.
- Chip 18 is static too: `effect_000018` -> symbol 1321, one frame, one
  placement (shape 1320), empty class.  Its art interior matches the Ruffle
  render at 0.77/255, and the art sits (-16.5, -34) px from the symbol origin
  -- already encoded in the prefab's sprite offset, so only the `STAGE_OFFSET`
  shift was needed (`Chip_0018_Effect.prefab` base renderer now
  (-0.28888, 0.38560)).  When building these references, composite the SVG over
  the Sitekick render with its alpha: a crop of the Ruffle frame is opaque and
  hides the Sitekick wherever the art has transparent gaps.  Evidence in
  `Logs/chip_0018_play/` (`reference.png`, `compare.png`, `report.txt`).
- Chip 19 is static as well: `effect_000019` -> symbol 1319, one frame, one
  placement (shape 1318), empty class.  Its art box is 578x705 at 6.94 px per
  SWF px (83.3 x 101.6) against Ruffle's 84x102, and the art sits (-7.0, -2.5) px
  from the symbol origin (the prefab had (-6.3, -2.35)), so only the
  `STAGE_OFFSET` shift was needed -- base renderer now (-0.11581, -0.14661).
  At 1:1 this art is mostly 1-2 px strokes, so the pixel diff is dominated by
  rasterisation: capture it through `ruffle_preview.html` in a headless browser
  with `--force-device-scale-factor=3` (the stage then renders about 4x) and
  compare content-box crops.  That reads shape IoU 0.930, interior colour
  2.59/255 and size ratio 1.0026, with the difference map
  (`Logs/chip_0019_play/art-diff.png`) showing only stroke edges -- no missing
  piece.  Gallery check: `bounds (3.53, 4.31, 0.50) @ (4.91, -0.37)`, sprite
  drawn, RESULT OK (`Logs/chip_0019_play/report.txt`, `reference.png`,
  `compare.png`).  Remember Unity deletes `Temp/` on launch, so re-extract the
  standalone SWF after a play check before capturing a reference.
- Chip 20 is static as well: `effect_000020` -> symbol 1317, one frame, one
  placement (shape 1316), empty class -- a dark red kabuto with a gold crest,
  drawn with a transparent well the Sitekick's face shows through.  Art box
  785x902 at 6.94 px per SWF px (113.1 x 130.0) against Ruffle's 114x130, art
  centre (1.0, -22.5) px from the symbol origin (prefab had (1.55, -22.18)), so
  only the `STAGE_OFFSET` shift was needed: base renderer now
  (0.01995, 0.19736).  The 4x Ruffle comparison reads shape IoU 0.989 and
  interior colour 1.81/255 over 101k px (`Logs/chip_0020_play/art-diff.png` is
  edges only).  Gallery check: `bounds (4.82, 5.54, 0.50) @ (5.25, 0.49)`,
  sprite drawn, RESULT OK (`report.txt`, `reference.png`, `compare.png`).
  **Correction, the art was right and Unity's material was wrong.**  The exported
  SVG carries five gradients (`url(#gradient0..4)`; three linear, two radial), so
  under the built-in sprite material the prefab drew the whole kabuto black --
  90,444 near-black px of 1.56M in `Logs/chip_0020_play/resting.png`, i.e. the
  same defect chip 42 hit.  Pointing the renderer at the shared
  `Assets/Materials/ChipMovie-Vector.mat` (Unlit/VectorGradient, guid
  31d1e238120410636b8eb04cc8ca4ff5, fileID 2100000) fixed it: the capture now
  reads its dark red (128,0,0), gold horn/crest (224,128,0) and the white face
  through the well, and the 4x Ruffle check is unchanged at zero shift (IoU 0.994,
  colour 1.94/255, against 0.92/17.6 at +-1 px), so the export never needed
  touching.  Gallery check re-run, still RESULT OK.  Rule for the rest of the run:
  any effect SVG with `url(#gradient...)` fills gets the vector material in its
  prefab -- the art check cannot catch this, since it compares the SVG against
  Ruffle and both are correct.
- Chip 21 is static too: `effect_000021` -> symbol 1315, one frame, one
  placement (shape 1314), empty class -- a small badge (22x17 SWF px), much
  smaller than the 17-20 art.  Art centre (11.0, -5.0) px from the symbol
  origin (prefab had (11.5, -4.3)), so only the `STAGE_OFFSET` shift was
  needed: base renderer now (0.19259, -0.11278).  4x Ruffle comparison:
  IoU 0.979, interior colour 1.46/255 (`Logs/chip_0021_play/`).  Gallery check:
  `bounds (0.82, 0.64, 0.50) @ (5.68, -0.28)`, sprite drawn, RESULT OK.
- Chip 22 is static too: `effect_000022` -> symbol 1313, one frame, one
  placement (shape 1312), empty class -- a wide red swoosh with pale bands in
  thin curved strokes (65.5 x 23.4 SWF px).  Art centre (-1.0, -0.5) px from the
  symbol origin (prefab had (0.1, -0.3)), so only the `STAGE_OFFSET` shift:
  base renderer now (-0.00521, -0.18218).  4x Ruffle comparison: IoU 0.976 and
  colour 8.23/255, which is crop alignment, not art: the difference map is
  dotted along every stroke, and searching a +/-10 px window on the 254x86
  upscaled crops takes the diff from 9.14 down to **1.36** at (+6, +9) px
  (about 1.5 x 2.3 px at 1:1) -- the two bounding boxes clip the thin strokes
  differently, and at the matched offset the art agrees.  Placement measured
  against the Sitekick's shell, not the eyes (the iris mask is 8 px tall at 1:1
  and its black pupil cuts the purple short): the band's top sits at 0.862 of the
  shell height on the site and 0.858 in the gallery capture, its left edge at
  -0.026 and -0.012 shell widths -- within half a pixel on both axes.  Gallery
  check:
  `bounds (2.68, 0.90, 0.50) @ (5.19, -0.46)`,
  sprite drawn, RESULT OK (`Logs/chip_0022_play/`).
- Chip 23 is static too: `effect_000023` -> symbol 1311, one frame, one
  placement (shape 1310), empty class -- two orange flame shapes that flank the
  Sitekick at its sides (art 121x44 at 1:1, 123.5 x 46.4 SWF px).  Art centre
  (0.5, -0.5) px from the symbol origin (prefab had (1.23, +0.05)), so only the
  `STAGE_OFFSET` shift: base renderer now (0.01431, -0.18825).  The 4x Ruffle
  comparison needs no alignment search here -- IoU 0.985 and colour 2.34/255 at
  zero shift.  Placement against the shell: the orange bbox spans x -0.56..1.68
  and y -0.27..1.15 plate widths/heights on the site, -0.57..1.56 and
  -0.30..1.22 in the gallery capture, i.e. the same flanking position within the
  mask's ~2% noise (`Logs/chip_0023_play/compare.png`).  Gallery check:
  `bounds (5.20, 1.90, 0.50) @ (5.24, -0.47)`, sprite drawn, RESULT OK.
- Chip 24 is static too: `effect_000024` -> symbol 1309, one frame, one
  placement (shape 1308), empty class -- a green pith helmet with a yellow band,
  tilted onto the upper-left of the head so the brim lies over the left eye (art
  49x34 at 1:1, 50.5 x 34.9 SWF px).  Art centre (-12.5, -28.5) px from the symbol
  origin (prefab had (-11.83, -27.6)), so only the `STAGE_OFFSET` shift: base
  renderer now (-0.21210, 0.29148).  4x Ruffle comparison: IoU 0.983, colour
  3.42/255 at zero shift, 3.43 at the best shift found (+0, +1) px -- already
  aligned.  Gallery check: `bounds (2.06, 1.40, 0.50) @ (4.67, 0.73)`, sprite
  drawn, RESULT OK; `Logs/chip_0024_play/compare.png` shows the brim over the
  left eye in both.
- Chip 25 is static too: `effect_000025` -> symbol 1307, one frame, one
  placement (shape 1306), empty class -- a yellow four-petal fan with orange
  shading, floating at the antenna tip above the head (art 33x34 at 1:1,
  33.9 x 35.6 SWF px).  Art centre (-24.5, -72.5) px from the symbol origin
  (prefab had (-23.97, -71.8)), so only the `STAGE_OFFSET` shift: base renderer
  now (-0.42291, 1.05835).  4x Ruffle comparison: IoU 0.970, colour 6.49/255 at
  zero shift and 3.25 at the best offset (+3, +10) px -- again the two bounding
  boxes clip this small art differently rather than a difference in the art.  The
  fan's middle is a transparent hole (alpha 0 over a 13x13 px box at native size),
  so it shows the stage blue in the site reference and the dark capture
  background in Unity -- not a white disc that went dark.  Gallery check:
  `bounds (1.37, 1.44, 0.50) @ (4.14, 2.65)` (well above the head, as drawn),
  sprite drawn, RESULT OK (`Logs/chip_0025_play/`).
- Chip 26 is static too: `effect_000026` -> symbol 1305, one frame, one
  placement (shape 1304), empty class -- a red and yellow striped scarf round the
  neck with the tail hanging below the body and one end flicking up to the right
  (art 65x94 at 1:1, 66.7 x 95.4 SWF px).  Art centre (2.5, +54.5) px below the
  symbol origin (prefab had (3.30, +54.8)), so only the `STAGE_OFFSET` shift:
  base renderer now (0.05031, -1.13773).  4x Ruffle comparison: IoU 0.990,
  colour 1.81/255 at zero shift (the search's best, 1.79, sits at the edge of the
  window, so it is already aligned).  Gallery check: `bounds (2.75, 3.96, 0.50)
  @ (5.33, -2.84)` -- hanging under the body, as drawn -- sprite drawn, RESULT
  OK (`Logs/chip_0026_play/compare.png` shows collar and flick in both).
- Chip 27 is static too: `effect_000027` -> symbol 1303, one frame, one
  placement (shape 1302), empty class -- black round eyeglasses over the eyes,
  the left lens on the left eye and the right lens low on the cheek (art 46x23 at
  1:1, 48.3 x 23.9 SWF px).  Art centre (10.0, -11.0) px from the symbol origin
  (prefab had (10.5, -10.55)), so only the `STAGE_OFFSET` shift: base renderer
  now (0.17524, -0.00434).  4x Ruffle comparison: colour 0.00/255 -- every shared
  pixel identical -- with IoU 0.910, which is thin black frames at 1:1 against
  the same frames 4x wide in the capture (best offset 0.24 at (+6, +8) px).
  Gallery check: `bounds (1.94, 0.92, 0.50) @ (5.64, -0.01)`, sprite drawn,
  RESULT OK (`Logs/chip_0027_play/compare.png` matches lens for lens).
- Chip 28 is static too: `effect_000028` -> symbol 1301, one frame, one
  placement (shape 1300), empty class -- a brown spiky mop of hair over the top of
  the head with a jagged fringe down the left cheek and the eyes peeking through
  (art 70x68 at 1:1, 71.4 x 68.7 SWF px).  Art centre (-5.0, -8.5) px from the
  symbol origin (prefab had (-4.72, -7.97)), so only the `STAGE_OFFSET` shift:
  base renderer now (-0.08892, -0.04901).  4x Ruffle comparison: IoU 0.985,
  colour 1.24/255 at zero shift (best 1.19 at the edge of the search window) --
  aligned.  Gallery check: `bounds (2.92, 2.81, 0.50) @ (4.98, -0.12)`, sprite
  drawn, RESULT OK (`Logs/chip_0028_play/compare.png` matches hairline, fringe and
  the visible eye).
- Chip 29 is static too, though its symbol is the first with two placements:
  `effect_000029` -> symbol 1299, one frame, placing sprite 1297 (itself one frame
  over shape 1296) and shape 1298.  Both children are single-frame, so nothing can
  move and the class is empty.  The effect is a lower-lip and chin band across the
  bottom of the face -- the mouth curve, the three cheek dots on the left and the
  grey swirl on the right (art 87x54 at 1:1, 87.9 x 55.8 SWF px).  Art centre
  (11.5, +17.5) px below-right of the symbol origin (prefab had (12.33, +19.3)), so
  only the `STAGE_OFFSET` shift: base renderer now (0.20690, -0.52233).  4x Ruffle
  comparison: IoU 0.990, colour 1.03/255 at zero shift and 0.24 at (-2, +10) px.
  Gallery check: `bounds (3.77, 2.36, 0.50) @ (5.72, -1.31)`, sprite drawn, RESULT
  OK (`Logs/chip_0029_play/compare.png` agrees on dots, swirl and chin line).
- Chip 30 is static too: `effect_000030` -> symbol 1295, one frame, one
  placement (shape 1294), empty class -- a black bat mask with violet-edged ears
  rising above the head and eye holes showing the one eye (art 79x99 at 1:1,
  80.4 x 101.1 SWF px).  Art centre (-8.5, -20.0) px from the symbol origin (prefab
  had (-6.78, -19.82)), so only the `STAGE_OFFSET` shift: base renderer now
  (-0.12449, 0.15658).  4x Ruffle comparison: IoU 0.972, colour 2.90/255 at zero
  shift with the search flat (best 2.94 at the window edge) -- aligned.  Gallery
  check: `bounds (3.33, 4.20, 0.50) @ (4.89, 0.39)`, sprite drawn, RESULT OK
  (`Logs/chip_0030_play/compare.png` matches brow band, chin edge and ears).
- Chip 31 is static too: `effect_000031` -> symbol 1293, one frame, one
  placement (shape 1292), empty class.  It is the widest effect so far -- a gold
  arrow with red fletching and a silver head passing through a purple sleeve, drawn
  right across the body (art 203x94 at 1:1, 204.6 x 95.4 SWF px).  Art centre
  (-13.5, -3.5) px from the symbol origin (prefab had (-12.98, -2.97)), so only the
  `STAGE_OFFSET` shift: base renderer now (-0.23206, -0.13576).  4x Ruffle
  comparison: IoU 0.982, colour 2.82/255 at zero shift (best 2.74 at the window
  corner) -- aligned.  Gallery check: `bounds (8.70, 4.01, 0.50) @ (4.62, -0.34)`,
  sprite drawn, RESULT OK (`Logs/chip_0031_play/compare.png` matches fletching,
  shaft height and sleeve over the head).
- Chip 32 is static too: `effect_000032` -> symbol 1291, one frame, one
  placement (shape 1290), empty class -- spiky glasses, black frames with grey
  shading and pale lavender lenses, and hair tufts over the brow (art 69x47 at
  1:1, 70.1 x 48.4 SWF px).  Art centre (-0.5, -7.0) px from the symbol origin
  (prefab had (0, -6.85)), so only the `STAGE_OFFSET` shift: base renderer now
  (-0.00694, -0.06853).  This is the first chip whose art needed a fix, not just
  the shift: it first read colour 12.61/255 with IoU 0.972, the hair shading
  nearly black where Ruffle shows #4b4b4b.  No path order fixes it (all five
  tried stay at 12.2-17.8): the cause is stroke width.  FFDec writes both of the
  shape's outlines at `stroke-width="1.0"` although the SWF's lines are 10 and
  20 twips, so the hair's 10-twip outline drew at double width and swallowed the
  grey bands under it.  Set that path (the second-to-last, the one starting
  `M15.55 -23.4`) to 0.5: colour 12.61 -> 6.30/255 (best 5.89 at (-8, +3) px) and
  IoU 0.972 -> 0.980.  Worth checking on later chips: a shape whose outlines come
  out at `stroke-width="1.0"` while its line styles differ in width is being
  drawn too heavy.  Gallery check after the fix: `bounds (2.87, 1.95, 0.50) @
  (5.18, -0.17)`, sprite drawn, RESULT OK (`Logs/chip_0032_play/compare.png`
  matches lens over eye, temple arm and hair tufts).
- Chip 33 is static too: `effect_000033` -> symbol 1289, one frame, one
  placement (shape 1288), empty class -- a big orange troll nose with a black
  moustache fringe under it, over the mouth (art 35x28 at 1:1, 36.8 x 29.2 SWF
  px).  Art centre (6.5, -3.5) px from the symbol origin (prefab had (7.02,
  -3.22)): base renderer now (0.11494, -0.13143).  It shows the same doubled
  outline as chip 32 -- shape 1288's line styles are 20 and 10 twips and FFDec
  writes both at `stroke-width="1.0"` -- and the narrow one hurts here too: its
  path (the last, starting `M15.55 1.4`) at 0.5 takes the 4x comparison from
  colour 5.20 to 4.66/255 against Ruffle's render, IoU 0.990 either way (the wide
  outline at 0.5 is much worse, 14.81, so only the 10-twip one is halved).  No
  shift helps (best 5.45 at the window edge).  Gallery check: `bounds (1.42, 1.11,
  0.50) @ (5.49, -0.33)`, sprite drawn, RESULT OK (`Logs/chip_0033_play/compare.png`
  matches nose over the eyes' midline and moustache under it).
- Chip 34 is static too: `effect_000034` -> symbol 1287, one frame, one
  placement (shape 1286), empty class -- two orange ear/tusk shapes, one on each
  side of the body at eye level, with a pale highlight and a dark droop under the
  right one (art 81x42 at 1:1, 79.2 x 40.1 SWF px).  The shape's art is centred
  on its registration point, so the prefab had no sprite offset of its own
  ((-0.00911, -0.01648)) and only the `STAGE_OFFSET` shift applies: base
  renderer now (-0.01605, -0.20386).  Third chip in a row with FFDec's doubled
  outlines: shape 1286's line styles are 20 and 10 twips and both paths come out
  at `stroke-width="1.0"`.  Halving the 10-twip one (the path starting
  `M34.35 -5.0`) takes the 4x Ruffle comparison from colour 20.17 to 14.49/255
  at zero shift, and with the capture's half-pixel phase (best at (+0.5, 0) px)
  it settles at 4.76/255, IoU 0.990 -- the half pixel is capture phase, not art.
  Gallery check: `bounds (3.39, 1.72, 0.50) @ (5.16, -0.51)`, sprite drawn,
  RESULT OK (`Logs/chip_0034_play/compare.png` puts both ears at the same height
  and size on the shell as the 1:1 Ruffle reference composite).
- Chip 35 is static too, and the widest art yet: `effect_000035` -> symbol
  1285, one frame, one placement (shape 1284), empty class -- giant purple
  sunglasses with gold frames crossing the lower face, the right lens raised
  higher than the left, with white lens highlights and small gold arms at the
  sides (art 183x93 at 1:1, 183.5 x 93.3 SWF px).  Art centre (-7.0, -23.0) px
  from the symbol origin (prefab had (-5.9, -23.0)), so only the `STAGE_OFFSET`
  shift: base renderer now (-0.10931, 0.21167).  Unlike 32-34 this shape is not
  drawn too heavy: its two line styles are 30 and 20 twips and FFDec writes them
  at `stroke-width="1.5"` and `"1.0"`, which is right -- halving the narrow one
  drops the 4x comparison from colour 2.49 to 7.72/255, so the art is left
  alone.  At those widths it reads IoU 0.996 and colour 2.49/255 at zero shift,
  the best in the window (difference map is stroke edges only).  The reference
  composite needs care here: the art box is 23 px above the symbol origin, so
  pasting its *bounding box* on the stage centre put it a whole row too low and
  made the glasses look like they sat under the eyes -- paste by the origin
  offset (centre at (180.5, 127.0)) and the frames cross over the eyes exactly
  as Unity draws them, which is what the chip does.  Gallery check:
  `bounds (7.90, 3.98, 0.50) @ (4.93, 0.53)`, sprite drawn, RESULT OK; the
  capture frames the body near the right edge, so `Logs/chip_0035_play/compare.png`
  shows the body and the left lens with the right lens running off the frame in
  both panels (aligned on the gold frame at the body's scale, the effect reads
  ~10% smaller than the SWF relative to the body, the same ratio chips 32-34
  show).
- Chip 36 is the first animated chip in the queue and needed no new export:
  its movie is the library root timeline already baked into `Movie/` (51 frames,
  12 fps, 38 distinct), which the export plays itself (`loop 1..51`, root 52
  returning to the sheathed pose, no pauses) because every clip in the SWF is
  single-frame and only a click on the mask -- unreachable in the gallery --
  starts the sword sequence.  Re-ran both checks on the shipped assets.  Ruffle,
  `ruffle_frames.py` over the whole range against `Movie/frame_NNN.svg`: **mean
  1.18/255, worst 2.50 on frame 46** (the documented 1.16/1.40 predates the
  current capture run); frame 46 zoomed is the two crossed swords over the mask,
  identical in both, with the residual on the sword hairlines and no missing
  piece.  Gallery (`ChipPlayCheck --chip 36`): `frames 51  fps 12  loop 1..51
  pauses []  pauseSeconds 0.75  sounds 8`, trace `1..51 | 1..51 | 1..16`,
  `samples 133  distinct 51  wraps 2  stopped at -`, `rest running on frame 16`,
  `cues 3,17,22,24,28,30,42,51  fired 18x  prefab 3,17,22,24,28,30,42,51` -- it
  plays all 51 frames in order, wraps twice without holding, and every cue that
  fires is in the prefab (`Logs/chip_0036_play/report.txt`, `resting.png`).
- Chip 37 is the animated jar effect pulled out of `effectlibrary1_250.swf`
  (`effect_000037` -> symbol 1274): the standalone's root is 75 empty frames with
  one placement of 1274 on frame 1, and 1274 is itself 75 frames of placements
  and removals (128 place, 65 remove) plus morph water -- so the animation is the
  sprite's own timeline, which is what `Movie/` carries (75 frames, 12 fps, loop
  1..75, no cues).  No new export was needed; this pass re-verified the art.  A
  Ruffle reference here is not `ruffle_frames.py`: it is AVM2, so its AVM1 stop
  never runs and a "frozen" movie just samples a random pose.  The working
  recipe: drop `DoABC2Tag`/`SymbolClassTag`/`ProtectTag` **and
  `SetBackgroundColorTag`** (leave it in and Ruffle paints the movie's own blue
  behind the art, which alone reads 240+/255), replay 1274's display list up to
  the Nth `ShowFrame` **keeping `clipDepth`** (drop it and the masked shapes draw
  as solid wedges -- green triangles across the jar), and emit that state as a
  one-frame sprite with every child frozen to its age.  Twelve states
  (1,9,18,21,30,45,55,58,62,66,70,75) read **2.50-2.76/255, worst pixel 181**, the
  same residual every time and the same order as the recorded 2.66 over all 75
  frames: the glass composite (the export's grey shadow ellipse and its white
  highlights against Ruffle's flatter fill), not a state error.  The water curve
  agrees on both sides -- water pixels at frames 1/9/18/21/55/58/62/66/75:
  Ruffle 874/874/3424/3406/3534/2882/1271/874/874 against the export's
  876/877/3482/3413/3579/2894/1294/876/876 -- i.e. empty through 9, water placed
  on 18, full 21-55, draining 58-62, empty from 66, exactly the timeline
  recorded above (`Logs/chip_0037/sample/`).  Gallery (`ChipPlayCheck --chip
  37`): `frames 75  fps 12  loop 1..75  pauses []  sounds 0`, trace
  `1..75 | 1..75 | 1..16`, `samples 181  distinct 75  wraps 2  stopped at -`,
  `rest running on frame 16`, no cues to fire -- plays the whole fill/drain cycle
  and wraps without holding (`Logs/chip_0037_play/report.txt`).
- Chip 38 is static too, and the first with a clip mask: `effect_000038` ->
  symbol 1225, one frame, five placements -- sprite 1219 (`eyeBagFill`), shape
  1220, shape 1221 carrying `clipDepth` (the mask), sprite 1223 (`pupil`) and
  shape 1224, every child single-frame, empty class.  The art is a baggy-eye /
  eyelid ring with lashes and a cream eye, 26x32 SWF px, centre (-7.0, -8.45) px
  from the symbol origin (prefab had (-6.05, -8.45)), so the base renderer is
  now (-0.11191, -0.04077).  Against a 4x Ruffle capture it reads IoU 0.976 and
  colour 8.79/255 with no shift helping; the difference map is only the thin
  inner curves (pigment and lid lines), which is expected here -- the shape has
  no line styles at all, every path is a fill, so the doubled-outline problem of
  chips 32-34 cannot apply.  The real defect was the import scale: this sprite's
  meta carried `svgPixelsPerUnit: 16.1757` where every verified chip has ~57.6
  (400 / 6.94), so Unity drew the eye 3.6x too large -- `bounds (3.44, 4.47)`,
  i.e. 1.2 body widths where the SWF's 26 px on a 70 px body is 0.37.  Set the
  PPU to 57.64 and the bounds become `(0.97, 1.26, 0.50) @ (4.92, -0.10)`, 0.33
  of the body -- the position was never affected, only the size.  Worth checking
  on later chips: a stale `svgPixelsPerUnit` silently resizes the effect while
  the prefab offset still looks plausible.  Gallery after the fix: sprite drawn,
  RESULT OK (`Logs/chip_0038_play/compare.png` puts the lid ring over the
  Sitekick's left eye at the same size and place as the 1:1 Ruffle composite).
  Its reference has to be rendered at the viewBox width (26 px), not at the
  SVG's own 180 px `width` -- at 180 the art composites 6.94x too big.
- Chip 39 is the first effect in this run whose *parts* move, and it exposed two
  real defects in the animated-effect export.  `effect_000039` -> symbol 1217,
  40 frames at 31 fps, no labels: shape 1212 at depth 1 (placed on frame 1 and
  never moved again -- the green goggles with an orange temple arm), sprite 1214
  at depths 18 and 22 (the two loose eyeballs) and sprite 1216 at depths 2..16
  (eight copies, the coil that unrolls across the stage).  337 placements, 8
  removes, every child single-frame, so all the motion is transform tracks.
  Checked frame-exactly by freezing the sprite's display list at frame N into a
  one-frame movie (`Logs/chip_0039_play/compare_frames.py freeze`, then composite
  the exported parts at the recorded matrices and diff).  Frames 10/20/30 read
  IoU 0.925/0.925/0.905 over the parts alone; adding the static depth-1 art takes
  frame 20 to IoU 0.977, colour 13.6/255, the residual being the hairlines of the
  coil.  Frames 1 and 40 draw *nothing but* the static art, which is how the
  first defect showed up: `build_prefabs.py` emits the base renderer only when
  nothing else animates, so any character no track moves is dropped from an
  animated effect -- here the goggles themselves, the most visible thing on the
  chip.  Added it by hand (`chip_0039_base`, sorting order 1, position = the
  base bbox centre, matching what the exporter's base path emits); the export's
  base art is exactly the untracked content, so it never doubles a part.
  The second: the clip's position keys carried the raw SWF matrices while the
  static prefabs bake `STAGE_OFFSET`, so the effect played 0.4 px right and
  10.8 px high on the body.  Shifted all 400 position keys of
  `Animations/Chip_0039.anim` and the 11 renderer transforms by
  (-0.00694, -0.18738); the goggles then sit on the body's own eyes in
  `Logs/chip_0039_play/compare.png`, as Ruffle has them.  Both fixes belong in
  the exporter (base rule, offset in the clip) before the next animated effect
  is exported.  The clip loops 0..1.2903225 s = 40/31 with `m_LoopTime: 1`,
  which is the SWF's own loop.  `ChipPlayCheck` prints "static effect  no
  ChipMoviePlayer" for this chip because it only looks for a movie
  frame-swapper; the Animator drives it, and the proof is that at rest only the
  two parts the clip gives alpha 1 are visible although the prefab carries all
  ten at alpha 1.  Gallery: renderers 11, `bounds (3.42, 2.06, 0.50) @
  (5.33, -0.56)`, RESULT OK.
- Chip 40 is static: `effect_000040` -> symbol 1211, one frame, one placement
  (shape 1210), empty class -- an orange/red flame crest that hangs *under* the
  shell like a jet, art 27.85 x 37.55 SWF px in one path made only of fills (no
  line styles at all, so the doubled-outline problem of chips 32-34 cannot
  apply).  Art centre is (10.0, 17.8) px below-right of the symbol origin, and
  the prefab already carried exactly the bbox centre as its offset
  ((0.19432, -0.30796)), so only the `STAGE_OFFSET` shift applies: base renderer
  now (0.18738, -0.49534).  The 4x Ruffle comparison reads IoU 0.988, colour
  4.53/255 at zero shift, and the shift search is flat in the right way -- every
  one of the 25 offsets from -2..+2 px reads 32.8-34.4/255, so the zero-shift
  figure is the aligned one, not a lucky draw.  The reference has to be pasted
  by the origin: the art box starts at viewBox (-2.9, -1), i.e. the origin sits
  near its top-left, so the art lands at stage (184.6, 149) and the flame hangs
  below the shell with its tip level with the body's lower edge.  Its sprite
  imports at `svgPixelsPerUnit: 60.8097`, the high end of the verified band
  (value 56.3-58.4 on chips 34/35), and the gallery bounds come out 1.06 x 1.46
  units -- 0.038 per SWF px against the SWF's 0.042-0.043, the same ~10% the
  static effects read, so nothing was changed.  Gallery check: `renderers 1
  sprites 1  bounds (1.06, 1.46, 0.50) @ (5.67, -1.24)`, sprite drawn, RESULT
  OK (`Logs/chip_0040_play/compare.png` puts the flame under the same part of
  the shell in both panels).
- Chip 41 is static: `effect_000041` -> symbol 1209, one frame, one placement
  (shape 1208), empty class -- a big orange/red flame plume (SVG viewBox
  51.95 x 94.8, 49.9 x 92.9 SWF px once the antialiased edge is trimmed) in one
  path made only of fills, with no line styles at all, so the doubled-outline
  problem of chips 32-34 cannot apply.  Its centre is (14.0, 45.0) px
  below-right of the symbol origin, i.e. the plume hangs out of the bottom of
  the shell like a jet, and the prefab already carried exactly that bbox centre
  ((0.24246625, -0.779015)), so only the `STAGE_OFFSET` shift applies: base
  renderer now (0.23552625, -0.966395).  The 4x Ruffle comparison reads
  **IoU 0.995 and colour 2.33/255** at zero shift, the tightest static match
  since chip 27's identical pixels, and the neighbourhood is unambiguous
  (-1 px in x: 18.93; 1 px down: 8.42), so it is aligned rather than lucky.  The
  1:1 reference pastes the art by its origin, viewBox min (-12, -2.4) against
  the stage centre, i.e. at stage (175.5, 147.6).  Its sprite imports at
  `svgPixelsPerUnit: 58.7907`, inside the verified band, and the gallery bounds
  come out 2.12 x 3.95 units -- 0.0424 per SWF px, square in the static band.
  Gallery check: `renderers 1  sprites 1  bounds (2.12, 3.95, 0.50) @
  (5.79, -2.42)`, sprite drawn, RESULT OK (`Logs/chip_0041_play/compare.png`
  hangs the plume off the same part of the shell in both panels).  One process
  note: the 4x capture page lived in `Temp/swftosvg/`, which Unity deletes on
  every launch, so a chip whose reference is rebuilt after a play check has to
  re-create it; it now lives in `Logs/capture_4x.html`, served off the repo
  root, which survives.
- Chip 42 is static: `effect_000042` -> symbol 1207, one frame but 14
  placements (shape 1198 at depth 1, sprite 1200 at depths 2 and 10, 1202 at 4,
  1203 at 9, 1204 at 12, 1206 at 13/15/17/19/21/23/25/27), empty class -- a
  silver viking helmet with gold horns sitting on the sitekick's upper right.
  Its SVG is a single path carrying 57 sub-shapes: the flat fills, twelve
  `fill="none"` outlines, and two `fill="url(#gradientN)"` fills that use
  `spreadMethod="reflect"` with huge x1/x2 (+-819.2), which is what keeps the
  band and horns shaded along their length.  Art box 77.7 x 68.65 SWF px; the
  4x Ruffle comparison reads **IoU 0.984 and colour 6.42/255** at zero shift
  with every neighbour at 36 or worse, so it is aligned rather than lucky, and
  `Logs/chip_0042_play/art-compare.png` shows capture and rsvg agreeing on the
  silver/gold, so the export itself was right from the start.  Only the
  `STAGE_OFFSET` shift applied: base renderer now (-0.371042479, 0.392873038).
  Gallery check: `renderers 1  sprites 1  bounds (3.12, 2.75, 0.50) @
  (4.27, 0.98)`, sprite drawn, RESULT OK.
  The interesting part is why Unity drew it *black* at first (31,358 pure-black
  px against a correct silhouette, only hairline gold/white edges).  The cause
  is the one `ChipMovieBuilder` already documents for gradient-heavy chips: the
  built-in sprite material samples the wrong place in a vector sprite's gradient
  atlas, so the first renderer came out as a dark wash.  Pointing the renderer at
  the shared `Assets/Materials/ChipMovie-Vector.mat` (Unlit/VectorGradient, guid
  31d1e238120410636b8eb04cc8ca4ff5, fileID 2100000) fixed it outright -- 11,619
  black px, all of them the art's own outlines -- and `Logs/chip_0042_play/
  compare.png` now shows the same silver dome, gold rivet band and red emblem in
  both panels.  Two dead ends worth recording: `fill-opacity="0"` on the twelve
  `fill="none"` outlines changed nothing (the outlines were never the problem,
  and the guard was reverted), and the SVG meta diff against chip 41 showed only
  guid/PPU/textureSize/SpriteRect, i.e. no import-setting difference at all.
  Scope: every static effect prefab so far (chips 17-41) still uses the built-in
  material, and nothing was visibly wrong because only chip 20 among them
  carries a gradient at all -- five of them.  Chip 20 was the earlier chip that
  needed the second look, and it needed it badly: under the built-in material it
  drew black (90,444 near-black px); it now uses this material too (see the chip
  20 note above).  Check every new effect SVG for `url(#gradient...)` fills before
  calling its prefab done.
- Chip 43 is static: `effect_000043` -> symbol 1197, one frame, one
  placement (shape 1196) at depth 1 with no matrix, and although the library's
  class is AS3 there is nothing on the timeline for a script to drive -- it is a
  cornucopia spilling over the sitekick's upper left, with a pineapple and its
  green leaves, bananas, purple grapes, a red apple, two oranges, a horn with
  leaves and two gold rings hanging off its tip (art 80.95 x 121.8 SWF px, SVG
  viewBox -55.7 -90.15 80.95 121.8).  The art's centre is (-15.2, -29.2) px from
  the symbol origin and the prefab already carried exactly that bbox centre,
  (-0.261985, 0.5074875), so only the `STAGE_OFFSET` shift applies: base
  renderer now (-0.268925, 0.3201075).  4x Ruffle comparison: **IoU 0.992,
  colour 4.09/255** at zero shift, and the neighbourhood is unambiguous (-1 px
  in x: 39.92; +1 px: 41.80; one row either way: 40.16 / 38.93), so it is
  aligned rather than lucky.
  This is the next chip with FFDec's doubled outline, and it needed the same
  treatment as 32-34, but only on one of its three stroked paths: shape 1196's
  line styles are 1, 10 and 20 twips and all three paths come out at
  `stroke-width="1.0"`.  The 9438-character black path is the 20-twip one --
  halving it is much worse (colour 18.76, IoU 0.970), so it stays at 1.0 -- while
  the `#996600` gold path (the ring and shine strokes) is the 10-twip one and
  halving it takes the comparison from 5.24 to **4.09/255**, with a clean
  minimum around it (0.05: 4.96, 0.25: 4.43, 0.5: 4.09, 0.75: 4.58, 1.0: 5.24,
  1.25: 5.90).  The third path, a tiny 1-twip dash set, reads 5.24 at any width
  from 0.05 to 1.0, so it is left as FFDec wrote it.  The art is all flat fills
  with no `url(#gradient)`, so the chip-42 material note does not apply here.
  Gallery check: `renderers 1  sprites 1  bounds (3.37, 5.11, 0.50) @
  (4.53, 0.80)`, sprite drawn, RESULT OK; 0.0416-0.0420 units per SWF px, in the
  static band (`Logs/chip_0043_play/compare.png` spills the horn over the same
  part of the upper-left shell and hangs the rings at the same place below it in
  both panels).
- Chip 44 is static: `effect_000044` -> symbol 1195, one frame with four
  placements -- shape 1189 at depth 2 (identity matrix), sprite 1191
  `beaniePropFill` at depth 3 and sprite 1193 `beaniePropShadow` at depth 5 (both
  one frame, both placed rotated: rotateSkew -+0.3914, scale 0.9189, translate
  (-453, -745) twips), and shape 1194 at depth 7 -- a propeller beanie, purple
  left panel, orange centre, blue right panel, white blades on a grey hub,
  dropped on the upper-left of the head over the left eye with the antenna
  passing behind it (art 49.2 x 37.15 SWF px, viewBox -42.95 -47.95 49.2 37.15).
  The two named prop sprites are the pieces an AS3 `setColors` could tint, but
  nothing on the timeline moves, so the chip is one pose.  The art's origin sits
  exactly at its top-left corner (`origin_px` 298.07, 332.77 over 6.94 =
  42.95, 47.95), so the whole drawing hangs down-right of the stage centre; the
  prefab already carried the bbox centre (-0.31924, 0.51572875) and only the
  `STAGE_OFFSET` shift applies: base renderer now (-0.32618, 0.32834875).
  4x Ruffle comparison: **IoU 0.980, colour 6.16/255** at zero shift, with the
  neighbourhood at 34.8-50.7, so it is aligned; the 6.16 is the art's many thin
  black contours (the difference map is edges only, no missing or shifted
  piece).  Shapes 1189 and 1194 have no line styles at all, so the SVG carries no
  strokes -- the doubled-outline problem of chips 32-34 and 43 cannot apply --
  and no `url(#gradient)`, so chip 42's material note does not either.  Gallery
  check: `renderers 1  sprites 1  bounds (1.97, 1.46, 0.50) @ (4.38, 0.82)`,
  sprite drawn, RESULT OK; 0.0400 / 0.0393 units per SWF px, in the static band
  (`Logs/chip_0044_play/compare.png` puts the same panels over the same part of
  the left eye, propeller above, in both).
- Chip 45 is static: `effect_000045` -> symbol 1188, one frame with a single
  placement -- character 1173, named `baseFill`, at depth 1 -- a big white
  muzzle laid across the lower face: the snout with brown mouth interior and
  pink tongue, and the long lip curling up and right until its tip reaches the
  body's right edge (art 81.1 x 51.8 SWF px, viewBox -16.25 -27 81.1 51.808).
  It is the first chip whose export nests a translated group, 1173 comes out
  under one (+7.75, -0.65) before its own shape group, which FFDec handles
  correctly here: the prefab already carried the bbox centre (0.4120625,
  0.0239670731) and only the `STAGE_OFFSET` shift applies, so the base renderer
  is now (0.4051225, -0.16341293).  4x Ruffle comparison: **IoU 0.996, colour
  3.78/255** at zero shift -- the tightest static match since chip 41 -- with the
  neighbourhood at 27.2-45.4, so it is aligned rather than lucky.  Nothing to
  fix in the art: no `url(#gradient)` fills, so chip 42's material note does not
  apply, and although the SVG carries one stroked path it is written at
  `stroke-width="1.0102857"`, i.e. FFDec's matrix-scaled value rather than the
  flat 1.0 that made chips 32-34 and 43 read heavy, so it is left alone.
  Gallery check: `renderers 1  sprites 1  bounds (3.41, 2.13, 0.50) @
  (6.21, -0.41)`, sprite drawn, RESULT OK; 0.0421 / 0.0411 units per SWF px, in
  the static band, and the bounds sit far right of the body as drawn --
  `Logs/chip_0045_play/compare.png` runs the white snout and tongue across the
  same part of the lower face and puts its up-curled tip at the body's right
  edge in both panels.
- Chip 46 is static: `effect_000046` -> symbol 1169, one frame with a single
  placement of shape 1168 at depth 1 -- a duck disguise: the sitekick's face
  turns yellow with an orange bill, two webbed orange feet under the body and a
  white cap over the crown with a small yellow tab on its left (art 71.2 x 67.35
  SWF px, viewBox -32.5 -31.6 71.2 67.35).  The prefab already carried exactly
  the bbox centre, (0.053785, -0.03600125) for (3.1, 2.075) px over 0.01735
  units, so only the `STAGE_OFFSET` shift applies: base renderer now
  (0.046845, -0.22338125).  4x Ruffle comparison: **IoU 0.996, colour 3.28/255**
  at zero shift, the best static figure in the queue so far, with the
  neighbourhood at 19.3-21.1, so it is aligned rather than lucky.  Nothing to
  fix: shape 1168's two line styles are 21 and 44 twips and FFDec writes them at
  `stroke-width="1.05"` and `"2.2"`, i.e. correctly scaled rather than the flat
  1.0 that made chips 32-34 and 43 read heavy, and there are no `url(#gradient)`
  fills, so chip 42's material note does not apply.  Gallery check:
  `renderers 1  sprites 1  bounds (2.92, 2.75, 0.50) @ (5.32, -0.56)`, sprite
  drawn, RESULT OK; 0.0410 / 0.0408 units per SWF px, in the static band
  (`Logs/chip_0046_play/compare.png` shows the same yellow dome, bill and both
  webbed feet on the same part of the shell in both panels).
- Chip 47 is static: `effect_000047` -> symbol 1167, one frame with a single
  placement of shape 1166 at depth 1 -- an orange whip leaving the body's right
  side as a thin arc that curls up and right into a golden knotted tip (art 53.9
  x 26.8 SWF px, viewBox 23.55 -28.9 53.9 26.8).  Its origin is outside the art
  (`origin_px` -163.44, 200.57 over 6.94 = -23.55, 28.9), so the whole drawing
  hangs up and to the right of the stage centre; the prefab already carried the
  bbox centre (0.876175, 0.2697925) for (50.5, 15.5) px, and only the
  `STAGE_OFFSET` shift applies: base renderer now (0.869235, 0.0824125).
  4x Ruffle comparison: **IoU 0.976, colour 3.07/255** at zero shift, with the
  neighbourhood at 10.2-11.5, so it is aligned rather than lucky.  Nothing to
  fix: shape 1166's single line style is 40 twips and FFDec writes it at
  `stroke-width="2.0"`, i.e. correctly scaled, and there are no
  `url(#gradient)` fills.  Gallery check: `renderers 1  sprites 1  bounds
  (2.17, 1.03, 0.50) @ (7.37, 0.21)`, sprite drawn, RESULT OK; 0.0403 / 0.0384
  units per SWF px, in the static band.  The gallery camera frames the body near
  the right edge here, so the knotted tip runs off the capture -- the same
  framing chip 35 shows -- which is why the check reads the renderer's own
  bounds (2.11 wide-to-tall against the art's 2.01) rather than the crop to
  confirm the whole sprite is bound (`Logs/chip_0047_play/compare.png` has the
  arc leaving the body at the same place in both panels).
- Chip 48 is static: `effect_000048` -> symbol 1165, one frame with a single
  placement of shape 1164 at depth 1 -- a magenta tricorn pirate hat with a
  white skull and crossbones on its front panel, worn on the crown with the brim
  dipping over the left eye and the point flicking out to the left (art 95.05 x
  58.2 SWF px, viewBox -55.5 -55.1 95.05 58.2).  The origin sits near the art's
  bottom-right (`origin_px` 385.17, 382.39 over 6.94 = 55.5, 55.1), so the whole
  drawing hangs up and to the left of the stage centre; the prefab already
  carried the bbox centre (-0.1396675, 0.4511) for (-7.975, 26.0) px, and only
  the `STAGE_OFFSET` shift applies: base renderer now (-0.1466075, 0.26372).
  4x Ruffle comparison: **IoU 0.994, colour 1.70/255** at zero shift, the
  closest static match since chip 27's identical pixels, with the neighbourhood
  at 13.8-16.3, so it is aligned rather than lucky.  Nothing to fix: shape 1164
  has no line styles at all -- the dark contours are fills, the SVG carries no
  strokes -- so the doubled-outline problem of chips 32-34 and 43 cannot apply,
  and there are no `url(#gradient)` fills either.  Gallery check:
  `renderers 1  sprites 1  bounds (4.01, 2.42, 0.50) @ (4.83, 0.66)`, sprite
  drawn, RESULT OK; 0.0422 / 0.0416 units per SWF px, in the static band
  (`Logs/chip_0048_play/compare.png` wears the hat on the same part of the crown
  with the brim over the left eye and the point to the same side in both
  panels).
- Chip 49 is static: `effect_000049` -> symbol 1163, one frame with a single
  placement of shape 1162 at depth 1 -- the smallest effect in the static run: a
  fringe of four thin black slivers sticking out of the body's lower-right rim
  like little legs or whiskers (art 23.7 x 16.9 SWF px, viewBox 0.15 7.55 23.7
  16.9, of which only about 62 px2 is filled).  The origin sits up and to the
  left of the art, so the drawing lands right of and below the stage centre; the
  prefab already carried the exact bbox centre (0.2082, -0.2776) for (12.0,
  16.0) px, and only the `STAGE_OFFSET` shift applies: base renderer now
  (0.20126, -0.46498).  4x Ruffle comparison: **IoU 0.899, colour 4.64/255** at
  zero shift, and the shift search is decisive even though the IoU is the lowest
  in this run (-1 px in x: IoU 0.271; +1 px: 0.283; one row: 0.423 / 0.383), so
  it is aligned.  The lower IoU is the art, not the export: the mask is 998
  capture px, i.e. ~62 at 1:1, and these are one-pixel-wide slivers, so the
  antialiasing band is a large fraction of the mask --
  `Logs/chip_0049_play/art-compare.png` (the capture crop against the SVG
  rendered at 12 px per unit) shows the same four slivers in the same
  arrangement and lengths.  Nothing to fix: shape 1162 has no line styles (the
  slivers are fills) and there are no `url(#gradient)` fills.  Gallery check:
  `renderers 1  sprites 1  bounds (0.86, 0.59, 0.50) @ (5.70, -1.16)`, sprite
  drawn, RESULT OK; 0.0363 / 0.0349 units per SWF px, the low end of the static
  band, which is what small art reads (chip 40's flame was 0.038)
  (`Logs/chip_0049_play/compare.png` puts the fringe at the same part of the
  lower-right rim in both panels).
- Chip 50 is static: `effect_000050` -> symbol 1161, one frame with a single
  placement of shape 1160 at depth 1 -- a gold hoop earring hanging at the
  sitekick's lower left, gold band outside an orange inner ring (art 19.95 x
  33.25 SWF px, viewBox -36.95 -6.6 19.95 33.25).  It is a narrow tall drawing
  left of the stage centre, so the prefab's bbox centre (0.468 px-scale units
  from the origin) plus the `STAGE_OFFSET` shift gives the base renderer
  (-0.48102875, -0.36131375).  4x Ruffle comparison: **IoU 0.973, colour
  6.05/255** at zero shift, and the neighbourhood is decisive in the way thin
  gold rings make it (-1 px in x: IoU 0.709, colour 62.95; +1 px: 0.679 / 66.97;
  one row either way: 0.842 / 28.66 and 0.843 / 27.69), i.e. a one-pixel shift
  drops the gold band off its black outline.  The 6.05 residual is that same
  outline-plus-band edge, not a missing piece (the difference map is contour
  only).  Nothing to fix: shape 1160 has no line styles -- the black outline is a
  fill -- and there are no `url(#gradient)` fills.  Gallery check:
  `renderers 1  sprites 1  bounds (0.73, 1.28, 0.50) @ (4.00, -0.90)`, sprite
  drawn, RESULT OK; 0.0366 / 0.0385 units per SWF px, the low end of the static
  band as small art reads (chips 40 and 49).  `Logs/chip_0050_play/compare.png`
  hangs the hoop from the same part of the left cheek, same size and colours, in
  both panels.
- Chip 51 is static: `effect_000051` -> symbol 1159, one frame with a single
  placement of shape 1158 at depth 1 -- a black eyepatch: an oval patch over the
  sitekick's right-hand eye with a thin strap running left across both eyes and
  hooking up at the left end (art 57.5 x 20.85 SWF px, viewBox -23.75 -26.3 57.5
  20.85, entirely above the stage centre).  The prefab already carried the bbox
  centre (0.0893525, 0.273479375) for (5.0, 15.875) px, so only the
  `STAGE_OFFSET` shift applies: base renderer now (0.0824125, 0.086099375).
  4x Ruffle comparison: **IoU 0.977, colour 1.11/255** at zero shift, with the
  neighbourhood clearly worse (-1 px in x: 0.869 / 3.25; +1 px: 0.846 / 3.25; one
  row either way: 0.711 / 3.90 and 0.745 / 4.53), so it is aligned.  Nothing to
  fix: shape 1158's single line style is 73 twips and FFDec writes it at
  `stroke-width="3.65"`, i.e. correctly scaled rather than the flat 1.0 of chips
  32-34 and 43, and the art is two flat fills with no `url(#gradient)`.
  Gallery check: `renderers 1  sprites 1  bounds (2.36, 0.80, 0.50) @
  (5.41, 0.22)`, sprite drawn, RESULT OK; 0.0410 / 0.0384 units per SWF px, in
  the static band (`Logs/chip_0051_play/compare.png` crosses the strap over the
  same part of both eyes and puts the patch over the same eye in both panels).
- Chip 52 is static: `effect_000052` -> symbol 1157, one frame with a single
  placement of shape 1156 at depth 1 -- a green and yellow striped scarf: the
  band passes over both eyes and the long tail hangs down the left cheek past
  the bottom of the body (art 63.5 x 80.3 SWF px, viewBox -40.75 -34.15 63.5
  80.3).  The prefab already carried the bbox centre (-0.15831875, -0.102365)
  for (-9.0, 6.0) px, so only the `STAGE_OFFSET` shift applies: base renderer
  now (-0.16525875, -0.289745).  4x Ruffle comparison: **IoU 0.990, colour
  3.39/255** at zero shift, with the neighbourhood at 0.843-0.854 and 31-36, so
  it is aligned rather than lucky.  Nothing to fix: shape 1156 has no line styles
  -- the black contour is a fill -- so the doubled-outline problem of chips 32-34
  and 43 cannot apply, and there are no `url(#gradient)` fills.  Gallery check:
  `renderers 1  sprites 1  bounds (2.62, 3.34, 0.50) @ (4.79, -0.72)`, sprite
  drawn, RESULT OK; 0.0413 / 0.0416 units per SWF px, square in the static band
  (`Logs/chip_0052_play/compare.png` wraps the band over the same part of both
  eyes and hangs the tail down the same side to the same length in both panels).
- Chip 53 is the animated AS3 effect (`effect_000053` -> symbol 1155, 126
  frames, label `start`), already exported: `Movie/` holds 54 frames at 12 fps,
  the prefab carries `loopFrom 1 / loopTo 54`, no cues and no pauses.  This pass
  re-verified the shipped assets rather than rebuilding them.  Ruffle, with the
  documented AVM2 recipe (the frozen states live in `Logs/chip_0053/ref/flat/`
  and `one/`), re-measured through `Logs/chip_0053/ref/analyze53.py`: **mean
  0.74/255, worst 3.16 (frame 3), best 0.48 (frame 5)** over all 54 frames, the
  offset scan flat at 0.74 for +0 (0.74 / 0.75 / 0.74 / 0.75 / 0.76 for -2..+2),
  so the index is aligned.  Gallery check (`ChipPlayCheck --chip 53`): `frames 54
  fps 12 loop 1..54 pauses [] pauseSeconds 0.75 sounds 0`, trace `1..54 | 1..54 |
  1..16`, `samples 139 distinct 54 wraps 2 stopped at -`, `rest running on frame
  16`, RESULT OK.
  **Correction to the frame-3 note above.**  Frame 3 is not the export's
  outlier, it is the middle of an authored blink, and the frozen reference is
  the side that cannot see it.  1155's frame 1 places shape 1140 at depth 46 and
  frames 2..5 each *replace* that depth with a different `DefineShape2` (1141,
  1142, 1143, 1144), i.e. five hand-drawn eyelid shapes at the head of the
  loop; the export draws exactly that sequence, purple ink per frame reading 740
  -> 340 -> 0 -> 340 -> 743, which is open, half-lidded, closed (white lid with
  the lash line, `Logs/chip_0053_play/blink.png`), half-lidded, open.  All five
  frozen `one/f001..f005.png` captures are pixel-identical to each other (5283
  ink px, 0 differing px) and hold the open eye, because the flatten keeps only
  the state's frame count and drops the replace chain -- so the frames 1..5
  error is the reference's, not the export's, and the earlier description of
  frame 3 as "the bow tie edge-on" (and the suggestion of five turned
  `x5_shape1` paths) is wrong: `x5_shape1` is byte-identical in frames 2, 3 and
  4.  The blink is reachable: the class's ENTER_FRAME loop runs `start`..
  `endStart`, so the chip blinks once per 54-frame cycle.  Excluding the five
  frames the reference cannot resolve, frames 6..54 read mean 0.66/255.
- Chip 54 is static: `effect_000054` -> symbol 1126, one frame placing sprite
  1124 (`nosefill`, itself one frame) at depth 1 and shape 1125 at depth 3 -- a
  black bandit mask across the eyes, with a thin white brow highlight, one end
  sweeping down to the lower left and the other spiking up above the head, and
  the purple of the eyes showing through the openings (art 71.95 x 58 SWF px,
  viewBox -47.75 -47.6 71.95 58).  The prefab already carried the exact bbox
  centre (-0.20429625, 0.32271) for (-11.775, 18.6) px, so only the
  `STAGE_OFFSET` shift applies: base renderer now (-0.21123625, 0.13533).
  4x Ruffle comparison: **IoU 0.988, colour 2.89/255** at zero shift, with the
  neighbourhood at 0.831-0.838 and 38-44, so it is aligned rather than lucky.
  Nothing to fix: shape 1125's four line styles are 20, 33, 40 and 30 twips and
  FFDec writes them at `stroke-width="1.0"`, `"1.65"`, `"2.0"` and `"1.5"`,
  i.e. correctly scaled rather than the flat 1.0 that made chips 32-34 and 43
  read heavy, and there are no `url(#gradient)` fills.  Gallery check:
  `renderers 1  sprites 1  bounds (2.95, 2.36, 0.50) @ (4.67, 0.34)`, sprite
  drawn, RESULT OK; 0.0410 / 0.0407 units per SWF px, in the static band
  (`Logs/chip_0054_play/compare.png` lays the mask across the same part of both
  eyes with the same two ends in both panels).
- Chip 55 is static: `effect_000055` -> symbol 1122, one frame placing shape
  1121 at depth 4 -- a red double-neck V guitar slung diagonally behind the
  sitekick: body and white pickguard to the lower left, two fretted necks with
  their tuner heads to the upper right, black pickups and the whammy bar over the
  shell (art 160 x 113.05 SWF px, viewBox -60 -22.5 160 113.05, the widest
  static art in the run).  The prefab already carried the bbox centre
  (-0.34743375, -0.6480225), so only the `STAGE_OFFSET` shift applies: base
  renderer now (0.34049375, -0.8354025).  4x Ruffle comparison: **IoU 0.998,
  colour 3.12/255** at zero shift -- the tightest static IoU in the queue -- over
  the largest mask (101,854 capture px), with the neighbourhood at 0.918-0.947
  and colour 31-39, so it is aligned.  Nothing to fix: shape 1121's single line
  style is 80 twips and FFDec writes the black outline at `stroke-width="4.0"`,
  correctly scaled, and there are no `url(#gradient)` fills.  The SVG also
  carries one white `stroke-width="1.0"` hairline path that has no matching line
  style in the shape; it is a sub-pixel highlight and the comparison is 3.12
  with it in place, so it is left as FFDec wrote it.  Gallery check:
  `renderers 1  sprites 1  bounds (6.76, 4.75, 0.50) @ (6.05, -2.09)`, sprite
  drawn, RESULT OK; 0.0423 / 0.0420 units per SWF px, square in the static band,
  and 6.76 x 4.75 the largest static bounds so far
  (`Logs/chip_0055_play/compare.png` crosses the guitar behind the shell in the
  same diagonal in both panels, body low-left, necks ending high-right).
- Chip 56 is static: `effect_000056` -> symbol 1120, one frame placing shape
  1119 at depth 1 -- a grey and white crash-helmet dome over a flame-orange face,
  white eye glints and a black mouth line, with a black-knobbed antenna on a thin
  rod and a purple glint at the brim (art 64.1 x 59.5 SWF px, viewBox
  -32.05 -29.75 64.1 59.5, centred on its own origin, so the prefab's child was
  already at 0,0 and only the `STAGE_OFFSET` shift applies: base renderer now
  (-0.00694, -0.18738)).  Two export defects, both fixed:
  **the gradient atlas again** -- shape 1119's ninth fill is a gradient
  (fillStyleType 16, one `linearGradient` with `spreadMethod="pad"`) and with the
  built-in sprite material Unity drew the whole face as a black wash (48,012
  black px, white plate only), exactly the chip-42 failure; pointing the prefab
  at `Assets/Materials/ChipMovie-Vector.mat` (`Unlit/VectorGradient`, guid
  `31d1e238120410636b8eb04cc8ca4ff5`) brings the flames back (17,494 black px,
  the art's own outline and mouth); and **a hairline written far too thick** --
  the shape's two line styles are 20 and 1 twips, but FFDec writes both strokes
  at `stroke-width="1.0"`, so the white 1-twip line came out 20x too heavy.  A
  width sweep on that white stroke: 1.0 -> colour 8.04, 0.5 -> 4.34, 0.2 ->
  **3.55**, 0.1 -> 3.88, 0.05 -> 4.09, 0.02 -> 4.23 (IoU 0.997 throughout), so it
  is set to 0.2, the width that matches Ruffle drawing a hairline at one device
  pixel rather than the literal 0.05.  The black 20-twip stroke is left at 1.0
  (halving it reads 9.71).  4x Ruffle comparison after both fixes: **IoU 0.997,
  colour 3.55/255** at zero shift, neighbourhood 0.957-0.963 and colour 30-35.
  Gallery check: `renderers 1  sprites 1  bounds (2.61, 2.42, 0.50) @
  (5.18, -0.47)`, sprite drawn, RESULT OK; 0.0407 / 0.0407 units per SWF px, dead
  in the static band (`Logs/chip_0056_play/compare.png` shows the same helmet,
  flame face and antenna in both panels with the purple glint on the right brim).
- Chip 57 is the first part-based effect in the queue whose *timing* was wrong:
  `effect_000057` -> symbol 1118, 87 frames at 31 fps, labels `start` 1,
  `endStart` 53, `fly` 54, `revert` 72, exported as a base SVG plus 23 part SVGs
  (24 characters, one of them -- sprite 1065 -- a 55-frame sub-clip) driven
  entirely by transform tracks.  Its class is a `TransformEffect` like chip 53's,
  but it does not loop: `onEnter` stops the movie on `endStart` and arms a click
  that runs `gotoAndPlay("fly")` with the `jetLoop` sound, so the worn movie is
  the 1..53 install, held -- the robot mask assembling itself (antenna, ear fin,
  goggles, two side pods and the needle fly in and attach) and then sitting
  still.  The shipped clip looped all 87 frames, which replays the fly *and* the
  revert for ever; it is now 53 frames, one shot (`m_StopTime` 1.70967742,
  `m_LoopTime` 0), 6,360 keys kept and 4,080 dropped.
  Art checked frame-exactly at six states of that range -- 1, 10, 27, 40, 53 and
  80 -- by freezing 1118's display list into a one-frame movie and compositing
  the exported parts at the matrices recorded in `chip_0057_effect.json`:
  **IoU 0.948 / 0.937 / 0.949 / 0.935 / 0.951 / 0.934, colour 0.15-0.35/255**
  (`Logs/chip_0057_play/compare_frames57.py`, `export_fNN_base.png` against
  `ruffle_fNN.png`).  Three things the chip-39 freeze recipe needs here, each of
  which produced a false reading until fixed: the effect's art is drawn around
  its own origin, so its display list has to be translated to the stage centre
  (+187.5, +150 px, i.e. 3750/3000 twips -- at sprite-local coordinates the whole
  comparison is clipped into the top-left corner); `clipDepth` must be kept or
  Ruffle draws the mask shapes as solid black blocks; and multi-frame children
  must be flattened to their age, because a one-frame movie shows sprite 1065's
  frame 1 while the export draws its frame N.  The two states in the fly (60 and
  70) read 0.206 and 0.574 for a real reason: the effect leaves the stage there
  (`ruffle_f60.png` is a corner sliver), which is exactly why the 87-frame loop
  could not stay.
  Gallery (`ChipPlayCheck --chip 57`): `static effect  no ChipMoviePlayer
  renderers 12  sprites 12  bounds (6.24, 3.66, 0.50) @ (5.22, -0.35)`, all
  twelve part renderers drawn, RESULT OK.  Like chip 39 it is Animator-driven,
  so the check reports it as static; the rest capture is the assembled mask of
  frame 53 -- antenna knob and arc, left ear fin, goggles, the two pods with
  their dark discs and the needle -- in the same pose as `ruffle_f53.png`
  (`Logs/chip_0057_play/compare.png`).
  One item is left as exported: the clip's position keys carry the raw SWF
  matrices, without the `STAGE_OFFSET` shift that chip 39 needed, and the two
  transforms of each part split the axes (the part node animates y, its `sprite`
  child animates x), so the offset cannot simply be added to every key.  Moving
  the effect root by the offset gave byte-identical gallery captures -- the
  check frames the effect on its own bounds -- so nothing was re-baked blind; it
  is recorded here for whoever fixes the exporter.
- Chip 58 is static: `effect_000058` -> symbol 1062, one frame placing shape
  1060 at depth 1 and sprite 1061 at depth 7, both single-frame -- a white cat
  face that hugs the Sitekick's shell: two tall ears with grey inner linings, a
  shaggy white brow, a pink nose, a muzzle of fangs with whiskers, and one eye
  left uncovered so the Sitekick's own purple iris shows through (art 117.35 x
  61.7 SWF px, viewBox -46.3 -50.45 117.35 61.7).  The prefab already carried
  the exact bbox centre (-0.21470625, 0.340277) for (12.375, -19.6) px, so only
  the `STAGE_OFFSET` shift applies: base renderer now (0.20776625, 0.15289687).
  4x Ruffle comparison: **IoU 0.978, colour 4.57/255** at zero shift, with the
  neighbourhood at 0.831-0.887 and 33-36, so it is aligned; the difference map
  is the whiskers and outline edges only.  Nothing to fix: the shape's fills are
  plain (`fillStyleType` 0, no `url(#gradient)`), so the built-in sprite material
  stays, and the two stroked paths are written at `stroke-width="1.25"` and
  `"1.0"` for the SWF's 25 and 20 twip styles -- correctly scaled, the opposite
  of the doubled 1.0 of chips 32-34.  Gallery check: `renderers 1  sprites 1
  bounds (4.92, 2.55, 0.50) @ (5.72, 0.38)`, sprite drawn, RESULT OK; 0.0419 /
  0.0413 units per SWF px, in the static band (`Logs/chip_0058_play/compare.png`
  puts the same ears, nose, fang line and whiskers over the same part of the
  shell in both panels).
- Chip 59 is static, though its symbol carries four frames: `effect_000059` ->
  symbol 1058, and all four frames hold the *same* placement (shape 1057 at
  depth 2, identity matrix), so nothing in the timeline can change; the class is
  a bare `BaseEffect` subclass with no timeline code either.  The art is a pink
  pig-snout mask over the face -- two ears with orange linings, a snout with two
  nostrils, one eye hole left open for the Sitekick's purple iris, a heavy black
  rim, and the face itself a linear gradient (81.55 x 47.65 SWF px, viewBox
  -42.5 -39.95 81.55 47.65).  The prefab carried the exact bbox centre
  (-0.02992875, 0.27803375) for (-1.725, -16.125) px, so only the
  `STAGE_OFFSET` shift applies: base renderer now (-0.03686875, 0.09065375).
  The gradient made it the third chip with the chip-42 defect: under the built-in
  sprite material the face renders as a hard dark-red-to-black wedge (29,827
  black px in the capture), and pointing the prefab at
  `Assets/Materials/ChipMovie-Vector.mat` (`Unlit/VectorGradient`, guid
  `31d1e238120410636b8eb04cc8ca4ff5`) gives the smooth pink face Ruffle draws
  (13,746 black px, the art's own outlines and nostrils).
  4x Ruffle comparison: **IoU 0.990, colour 2.90/255** at zero shift, the
  neighbourhood at 0.894-0.919 and 22-25.  Line widths are the one thing that
  does not follow FFDec's conversion here and are still left alone: the shape's
  styles are 45, 20, 2, 40 and 20 twips, written as 2.25, 1.0, 2.0 and 1.0 px
  except that the 2-twip *black* style comes out twice, once at `1.0` and once at
  `2.75`.  Thinning either black path to the literal 0.1 is worse -- the 1.0 one
  moves colour 2.90 -> 2.88 (noise) and the 2.75 one wrecks the frame (IoU 0.939,
  colour 27.8) -- so Ruffle really does draw that black outline heavy and both
  stay as exported.  Gallery check: `renderers 1  sprites 1  bounds (3.37, 1.93,
  0.50) @ (5.11, 0.23)`, sprite drawn, RESULT OK; 0.0413 / 0.0405 units per SWF
  px, in the static band (`Logs/chip_0059_play/compare.png` has the same ears,
  snout, nostrils and rim in both panels).
- Chip 60 is static: `effect_000060` -> symbol 1056, one frame, one placement
  (shape 1055 at depth 2) -- a shaggy dark-red wig over the top and left of the
  head: scalloped silhouette, a fringe across the brow with one darker under-lock
  falling in front of the face, the eyes peeking out below it (art 82.1 x 80.65
  SWF px, viewBox -54.4 -56.15 82.1 80.65).  The prefab carried the bbox centre
  (-0.23596, 0.27369625) for (-13.35, -15.825) px, so only the `STAGE_OFFSET`
  shift applies: base renderer now (-0.2429, 0.08631625).  4x Ruffle comparison:
  **IoU 0.994, colour 1.09/255** at zero shift -- the tightest colour since chip
  27's identical pixels -- with the neighbourhood at 0.943-0.948 and 3.0-3.5, so
  it is aligned.  Nothing to fix and nothing to check twice: the shape is two
  plain fills (`fillStyleType` 0) with no line styles at all -- so neither the
  doubled-outline problem of chips 32-34/56 nor the gradient defect of 42/56/59
  can apply -- and the built-in sprite material renders it correctly.  Gallery
  check: `renderers 1  sprites 1  bounds (3.42, 3.36, 0.50) @ (4.59, 0.22)`,
  sprite drawn, RESULT OK; 0.0417 / 0.0417 units per SWF px, square in the static
  band (`Logs/chip_0060_play/compare.png` has the fringe over the same brow and
  the tail notched at the same place in both panels).
- Chip 61 is static: `effect_000061` -> symbol 1054, one frame, one placement
  (shape 1053 at depth 1) -- a purple mohawk of six spiked locks sweeping up and
  to the right, the two right-hand locks carrying a light-violet highlight and
  the tips passing over the right eye (art 84.15 x 72.55 SWF px, viewBox -45 -75
  84.15 72.55).  The prefab carried the exact bbox centre (-0.05074875,
  0.67187875) for (-2.925, -38.775) px, so only the `STAGE_OFFSET` shift applies:
  base renderer now (-0.05768875, 0.48449875).  4x Ruffle comparison: **IoU
  0.997, colour 2.21/255** at zero shift, with the neighbourhood at 0.938-0.944
  and 20-37, so it is aligned.  Nothing to fix: five plain fills
  (`fillStyleType` 0), no line styles at all, no gradients -- so neither the
  doubled-outline nor the gradient defect can apply, and the built-in sprite
  material is right here.  Gallery check: `renderers 1  sprites 1  bounds (3.48,
  2.99, 0.50) @ (5.06, 1.21)`, sprite drawn, RESULT OK; 0.0413 / 0.0412 units per
  SWF px, in the static band (`Logs/chip_0061_play/compare.png` has the same six
  locks, the same highlight lock and the same tips over the right eye in both
  panels).
- Chip 62 is static: `effect_000062` -> symbol 1052, one frame, one placement
  (shape 1051 at depth 1) -- a brown shaggy mop: a fringe of jagged locks across
  the brow with the eyes under it, and one long lock falling down the left of the
  shell past its lower rim (art 75.6 x 90.6 SWF px, viewBox -47 -43 75.6 90.6).
  The prefab carried the exact bbox centre (-0.16092125, -0.039905) for (-9.2,
  +2.3) px, so only the `STAGE_OFFSET` shift applies: base renderer now
  (-0.16786125, -0.227285).  4x Ruffle comparison: **IoU 0.991, colour 1.86/255**
  at zero shift, with the neighbourhood at 0.842-0.869 and 8.9-9.9, so it is
  aligned.  Nothing to fix: three plain fills (`fillStyleType` 0), no line styles
  and no gradients, so neither the doubled-outline nor the gradient defect can
  apply and the built-in sprite material is correct.  Gallery check: `renderers 1
  sprites 1  bounds (3.12, 3.76, 0.50) @ (4.78, -0.57)`, sprite drawn, RESULT OK;
  0.0413 / 0.0415 units per SWF px, in the static band
  (`Logs/chip_0062_play/compare.png` has the same fringe over the eyes and the
  same lock ending past the shell's bottom-left in both panels).
- Chip 63 is static: `effect_000063` -> symbol 1050, one frame, one placement
  (shape 1049 at depth 1) -- a red bow tie with a rounded knot and a black
  outline, hanging just under the shell's lower edge and centred on the face
  (art 45.35 x 29.85 SWF px, viewBox -10.8 14.85 45.35 29.85; this art sits
  *below* its origin, so the prefab's offset already pointed down).  The prefab
  carried (-0.20082625, -0.51052375) against the bbox centre (11.875, 29.775) px
  = (0.20603, -0.51660), so only the `STAGE_OFFSET` shift applies: base renderer
  now (0.19388625, -0.69790375).  4x Ruffle comparison: **IoU 0.991, colour
  3.90/255** at zero shift over a small mask (13,049 px), with the neighbourhood
  at 0.886-0.906 and 13.5-17.7, so it is aligned.  Nothing to fix: four plain
  fills (`fillStyleType` 0), no line styles and no gradients, so neither the
  doubled-outline nor the gradient defect can apply and the built-in sprite
  material is correct.  Gallery check: `renderers 1  sprites 1  bounds (1.82,
  1.17, 0.50) @ (5.68, -1.74)`, sprite drawn, RESULT OK; 0.0401 / 0.0392 units
  per SWF px, the low end of the band that small art reads
  (`Logs/chip_0063_play/compare.png` hangs the same tie under the same part of
  the shell in both panels).
- Chip 64 is static: `effect_000064` -> symbol 1048, one frame placing shape 1046
  at depth 1 and shape 1047 at depth 3 -- a muzzle over the lower face: two pink
  cheeks with red curl marks either side of a grey mouth guard whose lower rim
  bubbles, hung under the eyes (art 96.9 x 58.2 SWF px, viewBox -48.75 -28.75
  96.9 58.2, centred almost exactly on its own origin at (-0.3, 0.35) px).  The
  prefab carried (0.00347, 0.00303625), so only the `STAGE_OFFSET` shift applies:
  base renderer now (-0.00347, -0.18434375).  4x Ruffle comparison: **IoU 0.994,
  colour 2.64/255** at zero shift, with the neighbourhood at 0.923-0.934 and
  23-29, so it is aligned.  Nothing to fix: shape 1047's single line style is 55
  twips and FFDec writes it at `stroke-width="2.75"`, correctly scaled; the eight
  fills are plain (`fillStyleType` 0) with no `url(#gradient)`, so the built-in
  sprite material is right.  Gallery check: `renderers 1  sprites 1  bounds (4.25,
  2.50, 0.50) @ (5.19, -0.46)`, sprite drawn, RESULT OK; 0.0439 / 0.0430 units
  per SWF px, the top of the static band.  `Logs/chip_0064_play/compare.png` has
  the cheeks, the red curls and the guard's bubbled rim in the same place under
  the eyes in both panels.
- Chip 65 is static: `effect_000065` -> symbol 1044, one frame, one placement
  (shape 1043 at depth 1) -- a black curly moustache: two tapered lobes meeting
  over the mouth line with pale highlight streaks, the right tip curling up and
  poking out past the shell's edge (art 66.85 x 32.8 SWF px, viewBox -23.35 -23.8
  66.85 32.8; bbox centre (10.075, -7.4) px = (0.17480, +0.12839)).  The prefab
  carried (0.17306625, 0.1327275), so only the `STAGE_OFFSET` shift applies: base
  renderer now (0.16612625, -0.0546525).  4x Ruffle comparison: **IoU 0.970,
  colour 4.37/255** at zero shift over a thin 9,399 px mask -- the lower IoU is
  the usual thin-art reading, not misalignment, since the neighbourhood collapses
  to 0.699-0.785 and 16.8-29.2.  Nothing to fix: three plain fills
  (`fillStyleType` 0), no line styles and no gradients, so neither the
  doubled-outline nor the gradient defect can apply and the built-in sprite
  material is correct.  Gallery check: `renderers 1  sprites 1  bounds (2.73,
  1.30, 0.50) @ (5.62, -0.14)`, sprite drawn, RESULT OK; 0.0408 / 0.0396 units
  per SWF px.  `Logs/chip_0065_play/compare.png` aligns on the shell disc (the
  moustache is too dark to bbox on its own) and shows the same lobes, streaks and
  curled right tip in both panels.
- Chip 66 is static: `effect_000066` -> symbol 1042, one frame, two placements
  (shape 1040 at depth 1 and shape 1041 at depth 6) -- a nautilus shell on the
  Sitekick's right: a cream body with fine radiating lines, a golden-brown
  gradient cup over the body's right side, a spiky tip and a red-streaked spiral
  above-right (art 161.987 x 133.986 stage px, viewBox -34.969 -72.021 161.987
  133.986; bbox centre (46.025, -5.028) px).  This is a **gradient chip**: the
  SVG defines three radial gradients used by `url(#gradient0/1/2)`, and the
  prefab still had the built-in sprite material (fileID 10754), so the prefab
  now uses `Assets/Materials/ChipMovie-Vector.mat` (fileID 2100000, guid
  31d1e238120410636b8eb04cc8ca4ff5) -- the shell's cup renders the cream/gold
  gradient instead of black, the same fix as chips 42, 56 and 59.  The 40-twip
  outline comes out at `stroke-width="2.0"`, correctly scaled, so nothing is
  halved.  The prefab carried (0.84668, 0.09499125), so only the `STAGE_OFFSET`
  shift applies: base renderer now (0.83974, -0.09238875).  4x Ruffle comparison:
  **IoU 0.881, colour 1.46/255** at zero shift, with the neighbourhood at
  0.861-0.868 and 15.0-17.7.  The lower IoU is edge antialiasing across this
  large art's dozens of hairlines, not shape: the mask reads 202,406 capture px
  against 229,638 art px and `art-diff.png` is stroke edges only with nothing
  misplaced or missing.  Gallery check: `renderers 1  sprites 1  bounds (6.96,
  5.76, 0.50) @ (7.30, -0.23)` -- far to the right of the panel, which is where
  the art is drawn -- sprite drawn, RESULT OK; 0.0430 / 0.0430 units per viewBox
  unit.  `Logs/chip_0066_play/compare.png` shows the same cup, radiating lines and
  red spiral in both panels, with the effect ~7% larger relative to the body, the
  ratio chips 32-35 show.
- Chip 67 is static: `effect_000067` -> symbol 1039, one frame, one placement
  (shape 1038 at depth 1) -- a shaggy brown mane with blonde streaks, flipped up
  over the brow and sweeping down both sides of the head past the eyes (art 89.6
  x 71.45 stage px, viewBox -50.55 -51.9 89.6 71.45; bbox centre (-6.25, -16.175)
  px = (-0.10844, +0.28064)).  The prefab carried (-0.0997625, 0.28150375), so
  only the `STAGE_OFFSET` shift applies: base renderer now (-0.1067025,
  0.09412375).  4x Ruffle comparison: **IoU 0.987, colour 2.60/255** at zero
  shift, with the neighbourhood at 0.882-0.896 and 14.8-16.0, so it is aligned.
  Nothing to fix: the single 20-twip line style is written at
  `stroke-width="1.0"`, correctly scaled (not the flat 1.0 defect of chips
  32-34), the nine fills are plain (`fillStyleType` 0) and there is no
  `url(#gradient)`, so the built-in sprite material is right.  Gallery check:
  `renderers 1  sprites 1  bounds (3.72, 2.95, 0.50) @ (4.93, 0.24)`, sprite
  drawn, RESULT OK; 0.0415 / 0.0413 units per SWF px.
  `Logs/chip_0067_play/compare.png` puts the blonde quiff over the same eye and
  the brown locks at the same spread in both panels.
- Chip 68 is static: `effect_000068` -> symbol 1037, one frame, one placement
  (shape 1036 at depth 1) -- black spiky hair swept over the brow: a jagged
  outer edge, a lank falling down the left past the eye and a short tail poking
  out at the right of the head (art 64.2 x 47 stage px, viewBox -38.05 -43.05
  64.2 47; bbox centre (-5.95, -19.55) px = (-0.10323, +0.33919), which the
  prefab already carried exactly).  Only the `STAGE_OFFSET` shift applies: base
  renderer now (-0.10973875, 0.1518125).  4x Ruffle comparison: **IoU 0.986,
  colour 0.68/255** at zero shift -- the closest colour match of the static run
  so far -- with the neighbourhood at 0.812-0.849 and 3.0-3.5, so it is aligned.
  Nothing to fix: the two line styles (40 and 60 twips) are written at
  `stroke-width="2.0"` and `"3.0"`, correctly scaled, and the three fills are
  plain with no `url(#gradient)`, so the built-in sprite material is right.
  Gallery check: `renderers 1  sprites 1  bounds (2.61, 1.89, 0.50) @ (4.93,
  0.38)`, sprite drawn, RESULT OK; 0.0407 / 0.0402 units per SWF px.
  `Logs/chip_0068_play/compare.png` shows the same brow sweep, left lank and
  right tail in both panels.
- Chip 69 is static: `effect_000069` -> symbol 1035, one frame, one placement
  (shape 1034 at depth 1) -- a wide multicoloured wrap over the head: a cream
  base with red, orange, green and purple bands sweeping round the brow from the
  left temple and hanging down both sides past the body, the right tail curling
  in front of it (art 74.7 x 92.6 stage px, viewBox -38.65 -41.15 74.7 92.6;
  bbox centre (-1.3, 5.15) px = (-0.02256, -0.08935)).  The prefab carried
  (-0.02385625, -0.09065375), so only the `STAGE_OFFSET` shift applies: base
  renderer now (-0.03079625, -0.27803375).  4x Ruffle comparison: **IoU 0.990,
  colour 4.02/255** at zero shift, with the neighbourhood at 0.879-0.924 and
  19.7-33.6, so it is aligned.  Nothing to fix: the four line styles (60, 40,
  40, 40 twips) are written at `stroke-width="3.0"` and `"2.0"`, correctly
  scaled, and the fifteen fills are plain with no `url(#gradient)`, so the
  built-in sprite material is right.  Gallery check: `renderers 1  sprites 1
  bounds (3.09, 3.85, 0.50) @ (5.12, -0.70)`, sprite drawn, RESULT OK; 0.0414 /
  0.0416 units per SWF px.  `Logs/chip_0069_play/compare.png` matches band for
  band: the purple and green over the brow, the red sweep down the left and the
  cream tail in front of the body.
- Chip 70 is static: `effect_000070` -> symbol 1033, one frame, one placement
  (shape 1032 at depth 1) -- a Frankenstein's-monster mask over the whole head:
  flat-topped green face with stitch lines, dark hair with a jagged fringe, angry
  brows over white eyes, a bolt at the left temple and one at the neck, and a
  yellow tab at the right (art 75.7 x 77.5 stage px, viewBox -39.35 -45 75.7
  77.5; bbox centre (-1.5, -6.25) px = (-0.026025, +0.10844), which the prefab
  already carried).  Only the `STAGE_OFFSET` shift applies: base renderer now
  (-0.032965, -0.0720025).  4x Ruffle comparison: **IoU 0.997, colour 2.68/255**
  at zero shift -- the best shape match of the static run -- with the
  neighbourhood at 0.962-0.965 and 16.3-18.5, so it is aligned.  Its five line
  styles are 40, 20, 20 and two 1-twip hairlines; FFDec draws all of them at
  `stroke-width="2.0"` / `"1.0"`, i.e. the 1-twip pair is 20x too wide exactly as
  chip 56's was, but here it costs nothing: at those widths the art already reads
  2.68/255, so the paths are left as written rather than thinned blind (the
  thirteen fills are plain, no `url(#gradient)`, so the built-in sprite material
  is right).  Gallery check: `renderers 1  sprites 1  bounds (3.15, 3.23, 0.50) @
  (5.12, -0.18)`, sprite drawn, RESULT OK; 0.0416 / 0.0417 units per SWF px.
  `Logs/chip_0070_play/compare.png` matches fringe, brows, stitch lines and both
  bolts in both panels.
- Chip 71 is static: `effect_000071` -> symbol 1031, one frame, one placement
  (shape 1030 at depth 1) -- a pair of goggles across the face: orange frame,
  lilac lens with a white highlight and a row of small dark dots along the top
  rim, and a red strap end at the left (art 72.1 x 33.95 stage px, viewBox -36
  -31 72.1 33.95; bbox centre (0.05, -14.025) px = (+0.00087, +0.24333), which
  the prefab already carried as (0, 0.24506875)).  Only the `STAGE_OFFSET` shift
  applies: base renderer now (-0.00694, 0.05768875).  4x Ruffle comparison:
  **IoU 0.996, colour 3.92/255** at zero shift, with the neighbourhood at
  0.908-0.949 and 27.7-39.7, so it is aligned.  Nothing to fix: the shape has no
  line styles at all (fills only, so the doubled-outline defect cannot apply),
  its ten fills are plain and there is no `url(#gradient)`, so the built-in
  sprite material is right.  Gallery check: `renderers 1  sprites 1  bounds
  (2.96, 1.35, 0.50) @ (5.18, 0.14)`, sprite drawn, RESULT OK; 0.0411 / 0.0398
  units per SWF px.  `Logs/chip_0071_play/compare.png` puts the frame, lens
  highlight, dot row and red strap end in the same place across the face in both
  panels.
- Chip 72 is static: `effect_000072` -> symbol 1029, one frame, three placements
  (shape 1025 at depth 1, sprite 1027 -- one frame over shape 1026 -- at depth 2,
  shape 1028 at depth 6) -- a big white boxing glove on a striped sleeve thrust
  out to the Sitekick's right: the ribbed cuff meets the body's right edge and
  the glove itself runs off past it (art 93.35 x 60.7 stage px, viewBox 29 -11.6
  93.35 60.7; bbox centre (75.675, 18.75) px = (1.31296, -0.32531), which the
  prefab already carried exactly).  Only the `STAGE_OFFSET` shift applies: base
  renderer now (1.3060213, -0.5126925).  4x Ruffle comparison: **IoU 0.995,
  colour 3.05/255** at zero shift, with the neighbourhood at 0.948-0.965 and
  27.0-34.1, so it is aligned.  Nothing to fix: its outlines come out at
  `stroke-width="2.0"` (black, four paths) and `"1.5"` (grey, one), i.e. 40 and
  30 twips correctly scaled rather than the flat 1.0 of chips 32-34, the fills are
  plain and there is no `url(#gradient)`, so the built-in sprite material is
  right; at those widths the art already reads 3.05/255, so no path was
  thinned.  Gallery check:
  `renderers 1  sprites 1  bounds (3.88, 2.49, 0.50) @ (8.47, -1.28)`, sprite
  drawn, RESULT OK; 0.0416 / 0.0410 units per SWF px.  The gallery capture's
  camera cuts the frame at the body's right edge, so only the cuff and the glove's
  leading edge are in it; `Logs/chip_0072_play/compare.png` aligns the two panels
  on the purple eyes and shows that cuff starting at the same point of the body
  and at the same height, with the rest of the glove outside the capture.
- Chip 73 is static: `effect_000073` -> symbol 1024, one frame, three placements
  (chars 1020, 1022 and 1023) -- a segmented mechanical arm on the Sitekick's
  left: a ribbed shoulder joint at the body's left edge, an upper arm and forearm
  of white plates with a grey-shaded sleeve running down-left, ending in a white
  fist with knuckle lines (art 71.25 x 106.7 stage px, viewBox -92.65 -5.75 71.25
  106.7; bbox centre (-57.025, 47.6) px = (-0.98939, -0.82586)).  The prefab
  carried (-0.98895, -0.8319325), so only the `STAGE_OFFSET` shift applies: base
  renderer now (-0.99589, -1.0193125).  4x Ruffle comparison: **IoU 0.997,
  colour 2.26/255** at zero shift, with the neighbourhood at 0.952-0.965 and
  29.6-35.0, so it is aligned.  Nothing to fix: the outlines come out at
  `stroke-width="1.0"`, `"2.0"` and `"3.0"`, i.e. 20, 40 and 60 twips correctly
  scaled, the fills are plain and there is no `url(#gradient)`, so the built-in
  sprite material is right.  Gallery check: `renderers 1  sprites 1  bounds
  (2.96, 4.48, 0.50) @ (2.71, -2.55)` -- left of and below the panel centre, which
  is where the arm hangs -- sprite drawn, RESULT OK; 0.0415 / 0.0420 units per SWF
  px.  `Logs/chip_0073_play/compare.png` (aligned on the purple eyes) puts the
  shoulder joint, forearm and fist at the same reach in both panels.
- Chip 74 is static: `effect_000074` -> symbol 1019, one frame, three placements
  (chars 1015, 1017 and 1018) -- a pair of big shoulder plates hung under the
  head: two white pauldrons with grey side panels, a grey trim band and rivet
  dots, each carrying a ribbed bolt on top (art 159.25 x 121.35 stage px, viewBox
  -62.85 14.75 159.25 121.35; bbox centre (16.775, 75.425) px = (+0.29105,
  -1.30862)).  The prefab carried (0.29885375, -1.3073225), so only the
  `STAGE_OFFSET` shift applies: base renderer now (0.29191375, -1.4947025).  4x
  Ruffle comparison: **IoU 0.997, colour 2.34/255** at zero shift, with the
  neighbourhood at 0.967-0.971 and 20.7-26.3, so it is aligned.  Nothing to fix:
  its outlines come out at `stroke-width="1.0"` and `"2.0"` (20 and 40 twips,
  correctly scaled), the nine fills are plain and there is no `url(#gradient)`, so
  the built-in sprite material is right.  Gallery check: `renderers 1  sprites 1
  bounds (6.77, 5.14, 0.50) @ (5.93, -3.74)` -- under the head, as drawn -- sprite
  drawn, RESULT OK; 0.0425 / 0.0424 units per SWF px.  The eye-aligned
  `Logs/chip_0074_play/compare.png` matches both bolts, the grey trim and the
  right-hand rivet dots in both panels.
- Chip 75 is static: `effect_000075` -> symbol 1014, one frame, one placement
  (shape 1013) -- a blonde bob: yellow hair swept back from a centre part with a
  forelock over the brow, hanging in a lock down each side of the face, the left
  one curling inward under the chin, with lighter highlight streaks throughout
  (art 86.5 x 89 stage px, viewBox -46 -44 86.5 89; bbox centre (-2.75, 0.5) px =
  (-0.04771, -0.00868)).  The prefab carried (-0.0459775, -0.00303625), so only
  the `STAGE_OFFSET` shift applies: base renderer now (-0.0529175, -0.19041625).
  4x Ruffle comparison: **IoU 0.996, colour 1.91/255** at zero shift, with the
  neighbourhood at 0.910-0.925 and 9.7-10.3, so it is aligned.  Nothing to fix:
  the shape is four fill paths with `stroke="none"` throughout (no line styles, so
  the doubled-outline defect cannot apply) and no `url(#gradient)`, so the
  built-in sprite material is right.  Gallery check: `renderers 1  sprites 1
  bounds (3.69, 3.79, 0.50) @ (5.07, -0.48)`, sprite drawn, RESULT OK; 0.0427 /
  0.0426 units per SWF px.  The eye-aligned `Logs/chip_0075_play/compare.png`
  matches the part, the forelock, the highlight streaks and the left lock's inward
  curl in both panels.
- Chip 76 is animated: `effect_000076` -> symbol 1012, 21 frames at 31 fps
  (`effect_000076.as` is an empty `LoopAnimation` subclass) -- a golden halo ring
  that bobs over the sitekick's antenna, plus a thin static line (depth 5, shape
  1011) drawn in front of it.  The timeline places the ring twice: depth 1 is
  sprite 1008 -> shape 1007 and depth 3 is sprite 1010 -> shape 1009, the same
  ring 5.8 / 1.05 px away, and both depths move in lockstep.  Only depth 1 became
  a track, and FFDec's frame export inlines the art instead of emitting `<use>`
  elements, so `remove_uses(drop_uses=...)` dropped nothing and the frame 1 copy
  of the ring stayed baked into `chip_0076_base.svg` (paths byte-identical to the
  part's, transform `matrix(1,0,0,1,-36.3,-64.1)`).  That doubled the ring wherever
  the part moved: the composite's yellow centroid travelled only 392.5 -> 403.9 ->
  392.5 of Ruffle's 392.3 -> 416.2 -> 392.3 while its yellow area grew 8,179 ->
  14,246 px.  The baked `g#x1_sprite0` group is now removed (backup
  `Logs/chip_0076_play/chip_0076_base.orig.svg`); the base keeps its viewBox, so
  the sprite pivot and the prefab offset are unchanged.  Per-frame check with
  `Logs/chip_0076_play/compare_frames76.py freeze 1 6 11 16 21` / `compose ...
  --base`: base+part against the 4x Ruffle captures gives **0.05/255** mean on all
  five frames (0.14% of pixels), yellow centroid 392.5/404.5/416.4/404.5/392.5
  against 392.3/404.3/416.2/404.3/392.3 and yellow area 7,954-8,022 against
  8,132-8,135, so the ring is single and travels the full 5.95 px.  The clip
  matches the tracks exactly: `Chip_0076.anim` has 21 keys, 0 -> 0.6451613 s at
  31 fps with `m_LoopTime 1`, and its y curve runs 1.112135 -> 1.008903 -> 1.112135,
  a 0.0/0.0 deviation from the SWF matrices.  `chip_0076_base.svg` also had no
  renderer in the prefab at all (the only `m_Sprite` was the part's), so the static
  line was never drawn -- `build_prefabs` does not give part-based chips a base
  renderer.  Chip 57 has the same gap: its prefab names ten sprites and none is its
  base (guid `250384a8`), whose twelve paths are nine shared with the parts and
  three base-only, so that chip is worth the same look.  A
  `chip_0076_base` GameObject with a SpriteRenderer on the base sprite is now
  added at (-0.37841471, 0.61503347), the line's art-bbox centre (-21.411,
  -46.249) px plus `STAGE_OFFSET`, with `m_SortingOrder 2` so the line stays in
  front of the ring as depth 5 does in the SWF.  Gallery check: `renderers 2
  sprites 2  bounds (2.12, 2.02, 0.50) @ (4.60, 1.70)`, both sprites drawn,
  RESULT OK; 0.01735 units per SWF px (the part-based scale).  The eye-aligned
  `Logs/chip_0076_play/compare.png` shows one halo with the line crossing it, the
  same as both reference panels (frame 1 and frame 11).
- Chip 77 is animated: `effect_000077` -> symbol 1006, 13 frames at 31 fps
  (`effect_000077.as` is an empty `LoopAnimation` subclass with `wing1`/`wing2`
  and `_beneath = true`) -- a pair of white feathered wings, cyan-edged, one on
  each side of the Sitekick, flapping.  The timeline places the *same* part
  sprite (1005, one subframe) twice, at depths 1 and 3, and rotates the pair
  against each other: frame 1 is (28.85, -16.2) rotated 39.631924 deg, frame 4
  the widest pose at 19.083735 deg, frame 7 back to frame 1's, while depth 3 is
  the mirror image (matrix determinant negative, -132.0733 deg at frame 1).  Like
  chip 76 its base SVG baked both wings at their frame-1 matrices -- FFDec inlines
  the art instead of emitting `<use>`, so `remove_uses(drop_uses=...)` had
  nothing to drop -- and this chip has no static art at all, so both groups are
  removed (backup `Logs/chip_0077_play/chip_0077_base.orig.svg`) and the base is
  an empty 187.094 x 59.276 canvas.  That is the right shape for the prefab it
  has: it references only the parts (`renderers 2`, sorting orders 1 and 3, both
  on the one `chip_0077_part_1005Sprite`), so composing with `--base` would have
  drawn the wings twice.  Per-frame check with
  `Logs/chip_0077_play/compare_frames77.py freeze 1 3 5 7 9 11 13` / `compose
  1 3 5 7 9 11 13`: parts-only against the 4x Ruffle captures gives **0.06/255**
  mean on all seven frames (0.24% of pixels), cyan centroid within 1.5 px (frame 1
  754.0/620.3 against 753.7/619.2, frame 3 747.4/589.7 against 748.4/588.3) and
  cyan area 21,392-21,440 against 19,465-19,512, the wing's pale rim sitting on
  the threshold.  Nothing to fix in the art: the outlines come out at
  `stroke-width` `1.5` and `2.0`, matching the two line styles, and the fills are
  plain, so the sprite material is right.  The clip matches the matrices: 13 keys
  per curve at 31 fps, `m_StopTime 0.41935483` (13/31) and `m_LoopTime 1`, with
  first keys (0.5005475, 0.28107) / -39.631924 deg / scale 0.895206 for part_1 and
  (-0.51009, 0.2541775) / -132.0733 deg / scale y -0.8964442 for part_3, i.e. the
  mirrored determinant, and Euler keys -39.632, -32.813, -25.831, -19.084 running
  with the matrices to 0.001 deg.  The 13 frames are a 6-frame flap played twice
  plus a repeat of frame 1 (7 and 13 compose identically to 1), so the wrap is
  seamless.  Gallery check: `renderers 2  sprites 2  bounds (8.60, 3.68, 0.50) @
  (5.19, 0.06)`, both drawn, RESULT OK; 0.01735 units per SWF px.  The capture
  frames the body near the right edge, so the right wing runs off it;
  `Logs/chip_0077_play/compare.png` (frame 1, frame 4, capture) has both wings in
  the same flanking pose behind the body in all three panels.
- Chip 78 is static: `effect_000078` -> symbol 1003, one frame, one placement
  (shape 1002, a `DefineShape4`) -- the class is a `BaseEffect` with no members
  and no clip, so nothing can move: a pair of red devil horns, one on each side
  of the head above the eyes, tips splayed outward, with pale pink highlights
  and a black outline (art 68 x 30.15 stage px, viewBox -39.5 -37 68 30.15;
  visible bbox 66 x 28.25, centre (-5.5, -21.88) px = (-0.095425, 0.37953)).
  The prefab carried (-0.095425, 0.38039875), so only the `STAGE_OFFSET` shift
  applies: base renderer now (-0.102365, 0.19215125).  4x Ruffle comparison:
  **IoU 0.984, colour 3.64/255** at zero shift, with the neighbourhood at
  0.72-0.82 and 27.9-39.8 (best neighbour 0.815 / 27.89 at (0, -1)), so it is
  aligned.  Nothing to fix: the six paths are two plain fills (`#e20000`,
  `#ff8080`) over one black line style that FFDec writes at
  `stroke-width="1.0"` -- a single width, so the doubled-outline defect cannot
  apply -- and there is no `url(#gradient)`, so the built-in sprite material is
  right.  Gallery check: `renderers 1  sprites 1  bounds (2.78, 1.18, 0.50) @
  (4.94, 0.48)` -- either side of the head, as drawn -- sprite drawn, RESULT OK;
  0.0409 / 0.0391 units per SWF px.  The eye-aligned
  `Logs/chip_0078_play/compare.png` puts both horns at the same height and the
  same splay on the shell in the reference composite and the gallery capture.
- Chip 79 is static: `effect_000079` -> symbol 1001, one frame, one placement
  (shape 1000, a `DefineShape4`) -- the class extends `Beneath` with no members
  and no clip, so nothing can move: the red devil tail that goes with chip 78's
  horns, a spade-shaped tip with a pale highlight and a black outline whose
  wavy tail runs down and to the right, behind the body's lower-left (art
  52.45 x 43.1 stage px, viewBox -75.95 -23.75 52.45 43.1; visible bbox
  49.75 x 41, centre (-50.08, -2.25) px = (-0.86880, 0.03904)).  The prefab
  carried (-0.87921125, 0.03817), so only the `STAGE_OFFSET` shift applies:
  base renderer now (-0.87574125, -0.1483425).  4x Ruffle comparison: **IoU
  0.974, colour 3.51/255** at zero shift, the neighbourhood at 0.66-0.81 and
  23.96-42.60 (best neighbour 0.807 / 25.06 at (-1, 0)), so it is aligned.
  Nothing to fix: five paths, the same two plain fills as chip 78 (`#e20000`,
  `#ff8080`) over one black line style that FFDec writes at
  `stroke-width="1.5"` -- one width, so the doubled-outline defect cannot apply
  -- and no `url(#gradient)`, so the built-in sprite material is right.  It is
  drawn behind the body, as a `Beneath` effect should be.  Gallery check:
  `renderers 1  sprites 1  bounds (2.15, 1.78, 0.50) @ (3.01, -0.37)` -- off the
  body's left side, as drawn -- sprite drawn, RESULT OK; 0.0432 / 0.0434 units
  per SWF px.  `Logs/chip_0079_play/compare.png` puts the tail's tip and its wave
  at the same height on the shell in the reference composite and the capture,
  the wave ending behind the body in both.
- Chip 80 is static: `effect_000080` -> symbol 999, one frame, one placement
  (shape 998, a `DefineShape4`) -- a `BaseEffect` with no members and no clip, so
  nothing can move.  It is the smallest effect so far, a little tilted golden
  block at the right corner of the mouth (a gold face with a cream highlight, an
  orange band down the left and along the bottom, a dark gold frame and a pale
  grey strip across its top edge; art 11.05 x 11.3 stage px, viewBox 12.5 -5.8
  11.05 11.3, visible bbox 9.0 x 8.62, centre (18.0, -0.49) px = (0.31230,
  0.00846)).  The prefab carried (0.31273375, 0.0026025), so only the
  `STAGE_OFFSET` shift applies: base renderer now (0.30536, -0.17892188).  4x
  Ruffle comparison: **IoU 0.988, colour 4.53/255** at zero shift, the
  neighbourhood at 0.62-0.77 and 24.59-49.89, so it is aligned.  Nothing to fix:
  six paths, plain fills only (`#fef9c0`, `#efd300`, `#dcb200`, `#ed8214`,
  `#999999`) over one `#6f5900` line style that FFDec writes at
  `stroke-width="1.5"` (a single width, so the doubled-outline defect cannot
  apply), and no `url(#gradient)`, so the built-in sprite material is right.
  Gallery check: `renderers 1  sprites 1  bounds (0.33, 0.31, 0.50) @ (5.96,
  -0.45)` -- on the cheek, as drawn -- sprite drawn, RESULT OK.  The art is too
  small for the bounds to give a clean units-per-pixel figure, so placement is
  measured from the eye centre instead: `Logs/chip_0080_play/compare.png` puts the
  badge (12.8, 18.2) px from the eye centre in the reference composite and
  (12.2, 17.3) px in the gallery capture, and the same size in both.
- Chip 81 is static: `effect_000081` -> symbol 997, one frame, one placement
  (shape 996, a plain `DefineShapeTag`) -- a `BaseEffect` with no members and no
  clip, so nothing can move: a pair of heavy black eyebrows over the eyes, the
  left a broad bar that covers the top half of the left eye and slopes down to
  the right, the right a shorter, thinner bar whose outer end runs past the right
  eye (art 43.7 x 9.75 stage px, viewBox -19.75 -24.25 43.7 9.75; visible bbox
  41.75 x 7.75, centre (2.12, -19.38) px = (0.03687, 0.33616)).  The prefab
  carried (0.036435, 0.33615625), so only the `STAGE_OFFSET` shift applies: base
  renderer now (0.02992875, 0.14877625).  4x Ruffle comparison: **IoU 0.992,
  colour 1.06/255** at zero shift -- the cleanest result in the queue -- with the
  neighbourhood at 0.52-0.79 and 4.95-6.76, so it is aligned.  Nothing to fix:
  the shape is a single fill path (`#000000`, `stroke="none"`), so it has no line
  styles at all and the doubled-outline defect cannot apply, and there is no
  `url(#gradient)`.  Gallery check: `renderers 1  sprites 1  bounds (1.72, 0.32,
  0.50) @ (5.27, 0.37)` -- across the eyes, as drawn -- sprite drawn, RESULT OK;
  0.0412 / 0.0413 units per SWF px.  The eye-aligned
  `Logs/chip_0081_play/compare.png` shows the left brow cutting the top of the
  left eye and the right bar reaching past the right eye in both panels.
- Chip 82 is static: `effect_000082` -> symbol 995, one frame, one placement
  (shape 994, a plain `DefineShapeTag`) -- a `BaseEffect` with no members and no
  clip, so nothing can move: a red cap, its dome over the crown, its peak drawn
  across the top of the eyes and a flap at the left side, with black outline,
  dark-red shading panels and pale pink highlight lines (art 71.35 x 44.2 stage
  px, viewBox -44 -44 71.35 44.2; visible bbox 69.62 x 42.25, centre (-8.31,
  -21.88) px = (-0.14422, 0.37953)).  The prefab carried (-0.1448725,
  0.37953125), so only the `STAGE_OFFSET` shift applies: base renderer now
  (-0.15116188, 0.19215125).  4x Ruffle comparison: **IoU 0.997, colour
  2.03/255** at zero shift, the neighbourhood at 0.895-0.947 and 15.49-28.75, so
  it is aligned.  Nothing to fix: six paths, five plain fills (`#000000`,
  `#890000`, `#e20000`, `#460000`, `#ff8080`) and a single `#ff8080` line at
  `stroke-width="1.5"` -- one width, so the doubled-outline defect cannot apply
  -- and no `url(#gradient)`, so the built-in sprite material is right.  Gallery
  check: `renderers 1  sprites 1  bounds (2.93, 1.78, 0.50) @ (4.82, 0.48)` --
  over the head, as drawn -- sprite drawn, RESULT OK; 0.0421 / 0.0421 units per
  SWF px.  The eye-aligned `Logs/chip_0082_play/compare.png` puts the peak across
  the eyes and the side flap at the left in both panels.
- Chip 83 is animated: `effect_000083` -> symbol 993, 34 frames at 31 fps (an
  `AnimationEffect` with `bling`, `loopOnce(false)` and `_beneath = true`) -- a
  silver "25" medallion on two bead chains, hanging below the body, with a white
  shine that sweeps across the medallion face over frames 1-9 and then rests at
  the sweep's start for frames 10-34.  It needed three fixes, and two of them are
  gaps the earlier part-based chips only hinted at:
  (1) the prefab drew *only* the glint -- one SpriteRenderer, on
  `chip_0083_part_990Sprite` -- while the base SVG carries the whole necklace
  (153 paths), so in Unity the chip was a floating white shape.  A
  `chip_0083_base` GameObject with a SpriteRenderer on the base sprite is now
  added at (0.01706373, -1.08719437), the base art bbox centre (1.38, 51.86) px
  plus `STAGE_OFFSET`, with `m_SortingOrder 71` so it sits behind the glint at
  72.
  (2) the glint is masked in the SWF and Unity had nothing to mask it with:
  depth 71 places shape 842 -- a circle of radius 18.3 at stage (1.3, 70) -- with
  `clipDepth 74`, so depths 72-74 are clipped to the medallion.  Without it the
  white sweep shows as a blob beside the chain.  Shape 842 is exported as
  `Sprites/chip_0083_mask.svg` (`-export shape` on the extracted SWF, viewBox
  `0 0 36.6 36.6`) and a `chip_0083_mask` SpriteMask sits at (0.01562, -1.40188)
  -- the circle's centre plus `STAGE_OFFSET` -- with the glint's
  `m_MaskInteraction: 1`; 2 is `VisibleOutsideMask` and leaves the blob in place.
  The harness capture confirms it: the white shape that hung beside the chain at
  the resting pose is gone.
  (3) as on chips 76 and 77 the base SVG also baked the glint at frame 1
  (`g#x73_sprite5`, `matrix(1,0,0,1,-45.75,29.65)`); that group is removed
  (backup `Logs/chip_0083_play/chip_0083_base.orig.svg`).
  `Logs/chip_0083_play/compare_frames83.py` gained a `--mask` step that clips the
  parts to shape 842's circle before compositing, and with it `compose 1 3 5 7 9
  17 25 33 --base --mask` against the 4x Ruffle captures reads **0.07-0.09/255**
  on all eight frames -- against 1.47 (frame-1 pose, white 16,455 px where
  Ruffle has 2,517) and 0.40 (frame 3) before the mask -- with white counts
  2,088 against 2,517 at the parked pose and 12,438 against 12,782 over the coin,
  centroids within 2 px.  The clip matches the SWF's eight move tags: 34 keys at
  31 fps, `m_StopTime 1.0967742` (34/31) with `m_LoopTime 1`, x running -0.7938
  -> 0.2941 -> -0.7938 by frame 9 and holding after; frames 1, 9, 17, 25 and 33
  compose identically, as do 3 and 7.  Gallery check: `renderers 2  sprites 2
  bounds (2.88, 3.28, 0.50) @ (4.66, -2.72)` -- hanging below the body, as drawn
  -- both drawn, RESULT OK; 0.01735 units per SWF px.  The eye-aligned
  `Logs/chip_0083_play/compare.png` hangs the necklace from the neck with the
  medallion centred under the chin in both panels.
- Chip 84 is static: `effect_000084` -> symbol 980, one frame, one placement
  (shape 979, a plain `DefineShapeTag`), so nothing can move -- a long red
  hairdo with a swept fringe over the eyes and a big flip curl at the top right,
  black outline over a `#b10b0b` fill with `#891108` / `#5a0b08` shading, a
  `#f45747` bright fold and `#f2cec0` / `#f1ac94` highlight lines, the fringed hem
  hanging about a head-height below the chin (art 96.95 x 96.55 stage px, viewBox
  -51.75 -40.7 96.95 96.55, centre (-3.275, 7.575) px).  The prefab carried that
  centre as (-0.05682125, -0.13186) and **no `STAGE_OFFSET` shift** -- the only
  chip in this run with the omission -- so the hair hung 10.8 SWF px (0.19 local
  units) high; the renderer is now (-0.06376125, -0.31880625), the art centre
  plus `STAGE_OFFSET` (-0.4, 10.8) px.  4x Ruffle comparison: **IoU 0.995,
  colour 1.06/255** at zero shift, the neighbourhood at 0.913-0.920 and
  6.8-7.6/255, so it is aligned.  Ten paths, six plain fills, no
  `url(#gradient)`; the strokes are `#000000` and `#350409` at 1.0 / 1.5 plus a
  single 2.4-wide outer line, and the 0.995 IoU says that heavy line is the SWF's
  own, not a doubled outline.  Gallery check: `renderers 1  sprites 1  bounds
  (4.01, 4.01, 0.50) @ (5.04, -0.80)` -- the hair over the crown and down both
  sides -- sprite drawn, RESULT OK; 0.0414 units per SWF px.  The design-scale
  composite and the capture agree on where the hem sits relative to the body:
  0.80 head-heights below the chin in the composite, 0.71 in the capture, with
  the fringe across the eyes in both (`Logs/chip_0084_play/compare.png`).
- Chip 85 is static too: `effect_000085` -> symbol 978, one frame, one placement
  (shape 977, a plain `DefineShapeTag`), so nothing can move -- long platinum
  hair, centre-parted with a swept fringe over both eyes and two locks falling
  past the chin to a wavy hem, filled `#ffffff` / `#c4bd8c` / `#a39b6f` / `#7c7442`
  with a `#f2cec0` highlight panel over a `#514924` outline (art 84.8 x 104.7
  stage px, viewBox -47 -37.95 84.8 104.7, ink 83x103, ink centre (-4.5, 14.55)
  px).  Like chip 84 the prefab carried the raw art centre (-0.07981,
  -0.24940625) with no `STAGE_OFFSET`; the renderer is now (-0.08675,
  -0.43678625), that centre plus `STAGE_OFFSET` (-0.4, 10.8) px.  Those two are
  the only chips in the recent run whose prefabs lacked the shift, and on both the
  art sat 10.8 SWF px high until it was added.  4x Ruffle comparison: **IoU
  0.993, colour 2.76/255** at zero shift, the neighbourhood at 0.902-0.915 and
  20.6-25.9/255, so it is aligned.  Six paths, six plain fills, **no strokes at
  all** and no `url(#gradient)`, so neither the doubled-outline nor the
  gradient-material caveat can apply here.  Gallery check: `renderers 1  sprites 1
  bounds (3.52, 4.37, 0.50) @ (4.98, -1.09)` -- the hair over the crown and down
  past the body -- sprite drawn, RESULT OK; 0.0415 units per SWF px.  The
  design-scale composite and the capture
  (`Logs/chip_0085_play/compare.png`) put the fringe across the eyes and both side
  locks at the same height, hem under the body in both, aligned on the white face
  at the capture's 4.33x scale.
- Chip 86 is static too: `effect_000086` -> symbol 976, one frame, one placement
  (character 975, a `DefineShape4Tag` -- the first in this run FFDec writes as the
  newer tag type, still one plain shape) -- a lilac cloud curl over the upper left
  of the head: a fluffy spiral starting at the crown, arching over the left eye
  and hanging down the left side in rounded puffs, `#ddbedd` / `#bc80bd` with
  `#ffffff` and `#f2cec0` / `#f1ac94` highlights inside a `#5a0c63` / `#811788`
  outline (art 85.1 x 81.35 stage px, viewBox -57.3 -45.75 85.1 81.35, ink centre
  (-14.75, -5.075) px).  Third chip in a row whose prefab carried the raw art
  centre (-0.25721375, 0.08805125) with no `STAGE_OFFSET`; the renderer is now
  (-0.26415375, -0.09932875), that centre plus (-0.4, 10.8) px.  4x Ruffle
  comparison: **IoU 0.995, colour 2.48/255** at zero shift, the neighbourhood at
  0.928-0.940 and 16.6-20.6/255, so it is aligned.  Seven paths, five plain fills,
  no `url(#gradient)`; the two outline weights (1.5 for `#5a0c63`, 1.0 for
  `#811788`) are the SWF's own -- unlike chips 32-34 there is only one narrow line,
  not a pair the exporter flattened to 1.0, and the 0.995 IoU confirms the weights
  are drawn right.  Gallery check: `renderers 1  sprites 1  bounds (3.53, 3.36,
  0.50) @ (4.54, -0.25)` -- over the upper left of the head -- sprite drawn, RESULT
  OK; 0.0415 units per SWF px.  Design composite vs capture
  (`Logs/chip_0086_play/compare.png`): the curl arches over the left eye and the
  tail hangs beside the left cheek in both, aligned on the white face at 4.30x.
- Chip 87 is static too: `effect_000087` -> symbol 974, one frame, one placement
  (character 973, another `DefineShape4Tag`) -- a flame claw arcing over the crown
  of the head, its tail hooking down past the left cheek and its spiky tips
  reaching out to both sides: cream `#fedfb3` with `#f49f17` / `#e66912` bands,
  `#f2cec0` / `#f1ac94` / `#f45747` highlights and a `#891108` dark-red outline
  over a `#bb4d0e` second line (art 88.1 x 63.65 stage px, viewBox -50.75 -36.7
  88.1 63.65, ink centre (-6.7, -4.875) px).  Fourth chip in a row whose prefab
  carried the raw art centre (-0.116245, 0.0841475) with no `STAGE_OFFSET`; the
  renderer is now (-0.123185, -0.1032325), that centre plus (-0.4, 10.8) px.  4x
  Ruffle comparison: **IoU 0.982, colour 4.35/255** at zero shift, the
  neighbourhood at 0.839-0.864 and 28.6-34.2/255.  The 4.35 is outline
  antialiasing, not a defect: the difference map (`Logs/chip_0087_play/
  art_diff.png`) is a contour along every edge, heaviest on the dark-red outline,
  with no missing or doubled piece, and the two stroke widths (1.5 for `#891108`,
  1.0 for `#bb4d0e`) are the SWF's own pair, not chips 32-34's flattened one.
  Eight paths, six plain fills, no `url(#gradient)`.  Gallery check:
  `renderers 1  sprites 1  bounds (3.65, 2.61, 0.50) @ (4.89, -0.26)` -- across the
  top of the head -- sprite drawn, RESULT OK; 0.0414 units per SWF px.  Design
  composite vs capture (`Logs/chip_0087_play/compare.png`): the claw arches over
  the crown with the tail beside the left cheek and the eyes under it in both,
  aligned on the white face at 4.32x.
- Chip 88 is static too: `effect_000088` -> symbol 972, one frame, one placement
  (character 971, another `DefineShape4Tag`) -- grey shaggy hair framing the whole
  head: a long bob with a jagged fringe over the brow, dark bands down each side
  and a spiky hem that hangs around and below the body, `#999999` / `#666666` /
  `#333333` with `#ffffff` and `#f2cec0` / `#f1ac94` highlights, `#333333` inner
  lines and a `#000000` outline (art 91.2 x 80.2 stage px, viewBox -46.75 -39.1
  91.2 80.2, ink centre (-1.15, 1.0) px).  Fifth chip in a row whose prefab
  carried the raw art centre (-0.01778375, -0.01431375) with no `STAGE_OFFSET`;
  the renderer is now (-0.02472375, -0.20169375), that centre plus (-0.4, 10.8)
  px.  4x Ruffle comparison: **IoU 0.991, colour 2.28/255** at zero shift, the
  neighbourhood at 0.872-0.877 and 25.3-28.3/255.  Ten paths, six plain fills, no
  `url(#gradient)`; the stroke set is `#333333` twice at 1.0 plus `#000000` at
  1.45 and 1.5, and since the two 1.0 lines share one colour they are not chips
  32-34's flattened narrow pair -- the 0.991 IoU puts the weights right either
  way.  Gallery check: `renderers 1  sprites 1  bounds (3.80, 3.33, 0.50) @
  (5.14, -0.50)` -- framing the head and hanging round the body -- sprite drawn,
  RESULT OK; 0.0417 units per SWF px.  Design composite vs capture
  (`Logs/chip_0088_play/compare.png`): fringe over the eyes, both side locks and
  the spiky hem at the same height in both, aligned on the white face at 4.47x.
- Chip 89 is static too: `effect_000089` -> symbol 970, one frame, one placement
  (character 969, another `DefineShape4Tag`) -- long grey hair parted over the
  antenna: two heavy locks drape down past the chin on both sides with the fringe
  across the eyes, and each lock ends in jagged bright-yellow flame tips,
  `#cccccc` / `#999999` / `#666666` / `#333333` greys over `#f1db14` / `#f49f17`
  tips with a `#f1ac94` highlight inside a black outline (art 94 x 104.15 stage px,
  viewBox -47.75 -40.75 94 104.15, ink centre (-0.75, 11.325) px).  Sixth chip in
  a row whose prefab carried the raw art centre (-0.0130125, -0.19301875) with no
  `STAGE_OFFSET`; the renderer is now (-0.0199525, -0.38039875), that centre plus
  (-0.4, 10.8) px.  4x Ruffle comparison: **IoU 0.997, colour 1.47/255** at zero
  shift -- the best of the run so far -- with the neighbourhood at 0.914-0.949 and
  13.9-25.0/255.  Ten paths, seven plain fills, no `url(#gradient)`; three black
  strokes at 1.0 / 1.5 / 1.6.  Gallery check: `renderers 1  sprites 1  bounds
  (3.93, 4.36, 0.50) @ (5.15, -0.95)` -- the hair framing the head and hanging
  under it -- sprite drawn, RESULT OK; 0.0418 units per SWF px.  The design
  composite / capture pair (`Logs/chip_0089_play/compare.png`) has to use a fixed
  4.40x, not the white-face ratio: the hair covers most of the face, so that ratio
  reads 5.75 and clearly over-scales the design side.  At 4.40 the fringe crosses
  the eyes and the yellow tips hang at both hems in the same place in both panels.
- Chip 90 is static too: `effect_000090` -> symbol 968, one frame, one placement
  (character 967, another `DefineShape4Tag`) -- icy pale-blue hair: a swept fringe
  across the eyes, one curl flicking out to the right, long waves down both sides
  and a wavy hem hanging round and below the body, `#ccecf4` / `#99d9e8` /
  `#34b3d1` over `#ffffff` with `#f2cec0` / `#f1ac94` highlights inside
  `#2493a5` (1.5) and `#167789` (1.0) outlines (art 108.45 x 106.9 stage px,
  viewBox -48.75 -32.55 108.45 106.9, ink centre (5.475, 20.9) px).  Seventh chip
  in a row whose prefab carried the raw art centre (0.09499125, -0.3617475) with
  no `STAGE_OFFSET`; the renderer is now (0.08805125, -0.5491275), that centre
  plus (-0.4, 10.8) px.  4x Ruffle comparison: **IoU 0.995, colour 1.91/255** at
  zero shift, the neighbourhood at 0.929-0.939 and 16.0-19.6/255.  Nine paths, six
  plain fills, no `url(#gradient)`; the two `#2493a5` lines at 1.5 plus `#167789`
  at 1.0 are the SWF's own widths.  Gallery check: `renderers 1  sprites 1  bounds
  (4.53, 4.46, 0.50) @ (5.42, -1.37)` -- framed round the head and hanging under
  the body -- sprite drawn, RESULT OK; 0.0418 units per SWF px.  Design composite
  vs capture (`Logs/chip_0090_play/compare.png`): the white-face ratio reads 4.34
  here and the panels agree at that scale -- fringe over the eyes, right-hand curl
  and the wavy hem at the same places.
- Chip 91 is static too: `effect_000091` -> symbol 966, one frame, one placement
  (character 965, another `DefineShape4Tag`) -- purple hair swept over the brow and
  parted at the antenna: two long side locks fall past the cheeks and end in wispy
  magenta tips, the fringe crossing the eyes with the left one showing through,
  `#ddbedd` / `#bc80bd` / `#9e49a1` over a `#5f0e68` base, `#ffffff` / `#f2cec0` /
  `#f1ac94` / `#f45747` highlight lines inside `#5f0e68` (2.0) and `#811788` (1.0)
  outlines (art 78.55 x 67.35 stage px, viewBox -42 -33.95 78.55 67.35, ink centre
  (-2.725, -0.275) px).  Eighth chip in a row whose prefab carried the raw art
  centre (-0.04641125, 0.0043375) with no `STAGE_OFFSET`; the renderer is now
  (-0.05335125, -0.1830425), that centre plus (-0.4, 10.8) px.  4x Ruffle
  comparison: **IoU 0.993, colour 2.83/255** at zero shift, the neighbourhood at
  0.872-0.892 and 24.8-34.6/255.  Ten paths, eight plain fills, no
  `url(#gradient)`.  Gallery check: `renderers 1  sprites 1  bounds (3.24, 2.76,
  0.50) @ (5.07, -0.46)` -- over the head with both locks beside the face -- sprite
  drawn, RESULT OK; 0.0412 units per SWF px.  Design composite vs capture
  (`Logs/chip_0091_play/compare.png`): white-face ratio 4.41, and the panels agree
  at that scale -- fringe across the eyes, both locks and their wispy tips in the
  same places.
- Chip 92 is static too: `effect_000092` -> symbol 964, one frame, one placement
  (character 963, another `DefineShape4Tag`) -- a long lilac mane swept in from the
  left: a pointed lock flicks out past the left cheek, the fringe crosses the brow
  with the eyes just under it, one heavy lock falls down the right side and the
  mass pools under the body, `#ddbedd` / `#bc80bd` / `#9e49a1` with `#ffffff` /
  `#f2cec0` / `#f1ac94` highlights inside `#811788` (1.5 and 1.6) and `#5f0e68`
  (1.0) outlines (art 102.2 x 103.2 stage px, viewBox -65.35 -39.7 102.2 103.2, ink
  centre (-14.25, 11.9) px).  Ninth chip in a row whose prefab carried the raw art
  centre (-0.24637, -0.20473) with no `STAGE_OFFSET`; the renderer is now
  (-0.25331, -0.39211), that centre plus (-0.4, 10.8) px.  4x Ruffle comparison:
  **IoU 0.993, colour 2.95/255** at zero shift, the neighbourhood at 0.917-0.927
  and 20.0-23.7/255.  Nine paths, six plain fills, no `url(#gradient)`.  Gallery
  check: `renderers 1  sprites 1  bounds (4.27, 4.31, 0.50) @ (4.57, -0.98)` -- the
  mane over the head and under the body -- sprite drawn, RESULT OK; 0.0418 units
  per SWF px.  Design composite vs capture (`Logs/chip_0092_play/compare.png`):
  white-face ratio 4.67, and at that scale the left lock, the right-hand fall and
  the pooled mass under the body all sit in the same places.
- Chip 93 is static too: `effect_000093` -> symbol 962, one frame, one placement
  (character 961, another `DefineShape4Tag`) -- pale ice-blue hair, the sparsest art
  in this run: a part at the antenna, the fringe curving over the brow in two arcs
  and one lock hanging on each side into pointed tips beside the cheeks, all of it
  a single `#99d9e8` fill inside two `#167789` outlines (1.5 and 1.0) -- three
  paths total, two of them stroke-only (art 81 x 78.35 stage px, viewBox -43.75
  -32.75 81 78.35, ink centre (-3.25, 6.425) px).  Tenth chip in a row whose
  prefab carried the raw art centre (-0.05682125, -0.11147375) with no
  `STAGE_OFFSET`; the renderer is now (-0.06376125, -0.29885375), that centre plus
  (-0.4, 10.8) px.  4x Ruffle comparison: **IoU 0.991, colour 0.95/255** at zero
  shift -- the lowest colour error of the run -- with the neighbourhood at
  0.822-0.894 and 14.1-26.5/255.  No gradients and no `fill-opacity`, so the
  sprite material and the glass-composite caveats cannot apply.  Gallery check:
  `renderers 1  sprites 1  bounds (3.35, 3.23, 0.50) @ (5.04, -0.75)` -- parting on
  the crown with a lock beside each cheek -- sprite drawn, RESULT OK; 0.0414 units
  per SWF px.  Design composite vs capture (`Logs/chip_0093_play/compare.png`):
  white-face ratio 4.60, and the two fringe arcs and both pointed tips land in the
  same places at that scale.
- Chip 94 is static too: `effect_000094` -> symbol 960, one frame, one placement
  (character 959, another `DefineShape4Tag`) -- long wavy green hair: a part at the
  antenna, the fringe hanging over the brow with the eyes just showing, a curl
  flipping out at the right and three wispy locks falling round the body,
  `#ccebb9` / `#99d47f` / `#66bb50` over `#ffffff` with `#f2cec0` / `#f1ac94`
  highlights inside `#1d6c24` (1.0, 1.0, 1.5) and `#33a02c` (1.3, 1.6) outlines
  (art 84.35 x 83.9 stage px, viewBox -38.75 -34.75 84.35 83.9, ink centre
  (3.425, 7.2) px).  Eleventh chip in a row whose prefab carried the raw art
  centre (0.05942375, -0.12361875) with no `STAGE_OFFSET`; the renderer is now
  (0.05248375, -0.31099875), that centre plus (-0.4, 10.8) px.  4x Ruffle
  comparison: **IoU 0.992, colour 2.81/255** at zero shift, the neighbourhood at
  0.899-0.915 and 24.6-28.7/255.  Eleven paths, six plain fills, no
  `url(#gradient)`; the five outline weights (two `#1d6c24` at 1.0, plus 1.5, and
  `#33a02c` at 1.3 and 1.6) are the SWF's own line styles, and the two identical
  1.0 lines are separate contours rather than chips 32-34's flattened pair.  Gallery
  check: `renderers 1  sprites 1  bounds (3.49, 3.46, 0.50) @ (5.33, -0.78)` --
  over the head with the locks round the body -- sprite drawn, RESULT OK; 0.0414
  units per SWF px.  Design composite vs capture (`Logs/chip_0094_play/compare.png`):
  white-face ratio 4.38, and at that scale the part, the right-hand curl and all
  three wispy tips land together.
- Chip 95 is static too: `effect_000095` -> symbol 958, one frame, one placement
  (character 957, another `DefineShape4Tag`) -- a wreath of lime-green fronds round
  the head: a seaweed / laurel mane whose leaf tips curl out all the way round,
  hang down past the cheeks and open again under the chin so the eyes stay clear,
  `#d1e220` / `#a1cd26` / `#7bbf3b` with `#f2cec0` / `#f1ac94` / `#f45747`
  highlight lines inside `#0d5821` (2.4, 1.0, 1.6) and `#279432` (1.5) outlines
  (art 108.7 x 91.2 stage px, viewBox -57.2 -49.2 108.7 91.2, ink centre (-2.85,
  -3.6) px).  Twelfth chip in a row whose prefab carried the raw art centre
  (-0.0494475, 0.06246) with no `STAGE_OFFSET`; the renderer is now (-0.0563875,
  -0.12492), that centre plus (-0.4, 10.8) px.  4x Ruffle comparison: **IoU 0.994,
  colour 2.60/255** at zero shift, the neighbourhood at 0.895-0.903 and
  18.4-19.7/255.  Ten paths, six plain fills, no `url(#gradient)`; the four outline
  weights (2.4, 1.0, 1.6 in `#0d5821`, 1.5 in `#279432`) are the SWF's own.  Gallery
  check: `renderers 1  sprites 1  bounds (4.54, 3.80, 0.50) @ (5.06, -0.31)` -- the
  wreath round the head with the eyes showing -- sprite drawn, RESULT OK; 0.0418
  units per SWF px.  Design composite vs capture (`Logs/chip_0095_play/compare.png`):
  white-face ratio 4.33, and the frond ring, the eye gap and the hanging tips sit in
  the same places at that scale.
- Chip 96 is static too: `effect_000096` -> symbol 956, one frame, one placement
  (character 955, another `DefineShape4Tag`) -- cream-blonde hair in two long
  straight locks: a centre part at the antenna, each lock falling past the cheek
  almost to the body's bottom edge and ending in three pointed strands, one eye
  showing through the gap on the left, `#ffffff` / `#c4bd8c` with `#f2cec0` /
  `#f1ac94` highlights inside `#514924` (1.75) and `#7c7442` (1.0) outlines (art
  85.15 x 97.55 stage px, viewBox -41.85 -39.75 85.15 97.55, ink centre (0.725,
  9.025) px).  Thirteenth chip in a row whose prefab carried the raw art centre
  (0.01257875, -0.15745125) with no `STAGE_OFFSET`; the renderer is now
  (0.00563875, -0.34483125), that centre plus (-0.4, 10.8) px.  4x Ruffle
  comparison: **IoU 0.993, colour 4.20/255** at zero shift, the neighbourhood at
  0.915-0.942 and 21.0-43.0/255.  The 4.20 is hairline antialiasing, not art: the
  difference map (`Logs/chip_0096_play/art_diff.png`) is a contour along every
  strand with no filled or missing patch, which is what this much line work costs
  at 4x.  Six paths, four plain fills, no `url(#gradient)`; the two outline
  colours carry their own widths.  Gallery check: `renderers 1  sprites 1  bounds
  (3.53, 4.06, 0.50) @ (5.21, -0.86)` -- both locks framing the head -- sprite
  drawn, RESULT OK; 0.0415 units per SWF px.  Design composite vs capture
  (`Logs/chip_0096_play/compare.png`): white-face ratio 4.30, and at that scale the
  part, the eye gap and all three strand tips land together.
- Chip 97 is static too, and the first in this run whose symbol is not one frame:
  `effect_000097` -> symbol 954 has **two frames but only one placement** --
  character 953 (a `DefineShape4Tag`) at depth 1 on frame 1, with no placement,
  move or remove tag at all on frame 2 -- so the two frames show the same picture.
  `-export frame` on the extracted SWF writes `1.png` and `2.png` byte-identical
  (md5 fba726965914, 6,734 bytes each), so a single still is the right export for
  it and there is no movie to bake.  The art is orange hair with a jagged fringe
  hanging over the eyes and one long sweep down the left, curling round the right
  side, `#fedfb3` / `#fdbf6f` / `#fe9f34` with `#f2cec0` / `#f1ac94` / `#f45747`
  highlights inside `#891108` (1.5 and 2.45) and `#e66912` (1.0) outlines (art 72.7
  x 79.45 stage px, viewBox -36.75 -35.75 72.7 79.45, ink centre (-0.4, 3.975) px).
  Fourteenth chip in a row whose prefab carried the raw art centre (-0.00650625,
  -0.0685325) with no `STAGE_OFFSET`; the renderer is now (-0.01344625,
  -0.2559125), that centre plus (-0.4, 10.8) px.  4x Ruffle comparison: **IoU
  0.995, colour 2.03/255** at zero shift, the neighbourhood at 0.889-0.917 and
  16.9-31.5/255.  Nine paths, six plain fills, no `url(#gradient)`.  Gallery check:
  `renderers 1  sprites 1  bounds (2.98, 3.27, 0.50) @ (5.17, -0.64)` -- the fringe
  over the eyes with the sweep beside the left cheek -- sprite drawn, RESULT OK;
  0.0410 units per SWF px.  Design composite vs capture
  (`Logs/chip_0097_play/compare.png`): the white-face ratio reads 5.27 because the
  fringe covers most of the face, so the fixed 4.42x was used; at that scale the
  fringe, both eyes under it and the right-hand curl agree.
- Chip 98 is static too: `effect_000098` -> symbol 952, one frame, one placement
  (character 951, another `DefineShape4Tag`) -- an orange conical hat with a white
  band, tilted so its brim sweeps out to both sides across the eyes while the dome
  rises over the crown, `#f47e49` / `#f76326` / `#cc3311` / `#a2190b` with a
  `#ffffff` band, `#f6deb2` highlight and `#cccccc` / `#9a9999` / `#666666` shadow,
  inside `#000000` (2.0) and `#a2190b` (1.85) outlines (art 97.05 x 84.9 stage px,
  viewBox -50.25 -71 97.05 84.9, ink centre (-1.725, -28.55) px -- it sits 28.5 px
  above the stage centre, over the head).  Fifteenth chip in a row whose prefab
  carried the raw art centre (-0.029711875, 0.4953425) with no `STAGE_OFFSET`; the
  renderer is now (-0.036651875, 0.3079625), that centre plus (-0.4, 10.8) px.  4x
  Ruffle comparison: **IoU 0.994, colour 2.00/255** at zero shift, the
  neighbourhood at 0.930-0.939 and 14.8-18.9/255.  Twelve paths, ten plain fills,
  no `url(#gradient)`.  Gallery check: `renderers 1  sprites 1  bounds (4.04, 3.52,
  0.50) @ (5.11, 0.77)` -- above the crown, brim across the eyes, as drawn -- sprite
  drawn, RESULT OK; 0.0416 units per SWF px.  Design composite vs capture
  (`Logs/chip_0098_play/compare.png`): white-face ratio 4.44, and at that scale the
  brim, the band and the dome sit in the same places on the head.
- Chip 99 is the first chip in this run whose symbol really animates, and its art
  needed three fixes.  `effect_000099` -> symbol 950, one frame, whose display list
  is `fill_1` (sprite 944 -> shape 943, the white body) at depth 1, a mask shape
  945 with `clipDepth 28` at depth 3, four instances of sprite 948 at depths
  4/10/16/22 -- the wing: a white fill at 0.4235 opacity, white dots, black
  outline, white scratch strokes -- each with its own rotation and flip, and shape
  949 (head, face, green eyes) at depth 30.  Sprite 948 has **two frames** (shape
  946 then 947) and the scratch pattern changes between them, so the effect
  flickers its wing scratches at 31 fps; that is the whole animation.  The export
  is `mode animated`, one part (948) with `chip_0099_part_948_f001.svg` /
  `f002.svg`, and a base `chip_0099_base.svg` that the exporter merged from 943
  and 949 **plus the four wing copies** -- drawing that behind the parts paints the
  42% wing fill twice (170,204,221 where Ruffle has 108,167,196), so the four wing
  groups were stripped out of the base (32 paths -> 12, then split again into
  body and head below).  The prefab had no base renderer at all (four wings
  floating with no head); it got one at sorting
  order **30**, above the parts, which is where 949 sits in the sprite, and that
  draw order is what the art check prefers: over the whole stage the f001 state
  reads **mean 5.01/255 on the art union, 0.34 whole-frame, p99 3** with the base
  on top, against 7.69 with the parts alone and 5.61 with a SpriteMask doing the
  clipping.  Ruffle's capture is at f001; f002 reads 47 because it is the other
  scratch pattern, i.e. the animation itself.  A SpriteMask was tried first (shape
  945 exported 1:1 at ppu 57.6) and abandoned: it imported, but its sprite drew
  about 1.75x too large in the prefab and clipped all four parts away, so the chip
  ships with draw order instead of a mask.  The four part transforms, like every
  other animated chip's, carried the raw art coordinates (no `STAGE_OFFSET`) --
  sixteenth in a row -- so they and the base got the shift: parts now
  (-0.664505, 0.48927), (-0.70788, 0.21167), (0.12492, 0.4884025), (0.47192,
  0.5838275) and base (0.03473193, -0.71168953) = its ink centre (2.402, 30.220)
  px + (-0.4, 10.8); the four `m_PositionCurves` keys in `Chip_0099.anim` got the
  same shift, since its single keyframe would otherwise put the parts straight
  back.  Gallery check: `renderers 5  sprites 5  bounds (5.85, 5.81, 0.50) @
  (5.03, 0.20)`, drawn `chip_0099_baseSprite` plus four
  `chip_0099_part_948_f001Sprite`, RESULT OK (bounds are sprite canvases, 139 px
  base at 0.0416 units per px).  The flicker initially did *not* play -- the clip
  had one keyframe and no sprite-swap curve, because `build_anim_plan.py` emitted
  `SWAP` only for backdrop/foreground clips, and 144 of the 254 animated effects
  carry multi-subframe parts -- and it is fixed in the toolchain, not per chip:
  `build_anim_plan.py` now emits `SWAP <part>/sprite <f001> <f002> ...` after a
  part's keys whenever its symbol has more than one usable frame (148 chips, 407
  swap lines if the whole plan is regenerated), and `ChipAnimBuilder` writes those
  as `m_Sprite` PPtr curves and lengthens the clip to the frame count (`stopTime`
  = frames/fps), because a single-frame `CHIP` line would wrap at 1/31 s and never
  reach f002.  Chip 99 was rebuilt alone (`-executeMethod ChipAnimBuilder.Run
  -chipIds 99`; the new `-chipIds` filter stops a one-chip rebuild rewriting 250
  other clips) and its position keys were re-shifted, since the plan carries raw
  art coordinates:
  `Chip_0099.anim` is 31 fps with `m_StopTime 0.06451613` and four `m_PPtrCurves`
  on `chip_0099_part_4/10/16/22/sprite`, guid 68f6a927 (f001) at t=0 swapping to
  eeaef86d (f002) at t=0.032258 -- the two scratch patterns alternate, twice per
  loop.  Verified by sampling rather than by inspecting the YAML:
  `ChipAnimValidate` now samples the clip too (it only checked transform motion
  before) and reports `sprite-swapping chips: 1 (Chip_0099_Effect)`,
  `problems: 0`, RESULT OK.  The gallery check is unchanged after the rebuild
  (`renderers 5  sprites 5  bounds (5.85, 5.81, 0.50) @ (5.03, 0.20)`, RESULT OK),
  since it captures the resting pose and that is f001.
  **Correction: the prefab drew three wings, and the fourth was lost to a draw
  order, not to a missing placement.**  The SWF puts the white dome (sprite 944
  -> shape 943) at depth **1**, i.e. *behind* the four wings, and only the face
  (949) at depth 30 in front of them.  The merged base drew dome and face
  together at order 30, so the dome covered the parts: invisible on the three
  wings that stick out past the head, fatal on the fourth -- part 16, the narrow
  wing between the ears at (0.12492, 0.4884025), lies wholly inside the head
  silhouette and disappeared.  Splitting the base along its own two groups is
  the fix: `chip_0099_body.svg` (group `x1_sprite0`, sprite 944 -> shape 943) is
  now a renderer at sorting order **1** and `chip_0099_head.svg` (`x11_shape5`,
  shape 949) stays at **30**, so the wings sit between them exactly as in the
  SWF.  Both keep the merged canvas, so the body's ink centre is inset from the
  head's: body at (-0.0174, -0.6943) = head + (-0.052, +0.017) local, from 21 px
  and 7 px of the 964 px canvas at 0.002479 local units per canvas px.  Two traps
  recorded: (a) this prefab had been left with `m_LocalPosition: {x:
  np.float64(0.03473193), ...}` -- a Python repr written into YAML by an earlier
  hand edit, which is not a number Unity can read; it is plain floats again;
  (b) the chip prefab is instanced under a parent scaled **2.5**, so a renderer's
  world bounds move 2.5x its local position -- fitting the body by world bounds
  first over-corrected by exactly that factor.  Verified in play mode:
  `renderers 6  sprites 6`, orders 1/4/10/16/22/30, all four wings in the Ruffle
  arrangement.  `ChipPlayCheck` grew the two things that made this findable: a
  `resting-art.png` framed on the whole effect (the plain `resting.png` still
  uses the game camera, which cropped a static chip at the screen edge) and a
  per-renderer line in `report.txt` with sprite, order, centre and size.
  Only the four `SWAP`
  lines for chip 99 were added to the committed plan by hand (+4 lines, nothing
  else touched): a full `build_anim_plan.py` run rewrites 5,954 unrelated lines of
  chip timelines, so the plan is not regenerated wholesale while chips are being
  fixed one at a time.  Design composite (`Logs/chip_0099_play/compare.png`,
  eye-anchored at 4.30x): wings read grey there instead of light blue because the
  gallery backdrop is dark rather than the stage blue -- the 42% white fill is the
  same.
- Chip 100 is static: `effect_00100` -> symbol 942, one frame, one placement
  (character 941, another `DefineShape4Tag`) -- a curled candy-striped mass of
  purple, yellow and orange wrapping the head's left side and top like a striped
  tail, with two orange hooks hanging under it and the brow cutting across the
  left eye, `#f2bc13` / `#f1db14` / `#f49f17` stripes with `#b93e95` / `#99137f` /
  `#d482b9` shading inside `#891108` (1.5 and 2.0) outlines and `#ffff41` /
  `#ffff00` hairlines (art 93.95 x 105.55 stage px, viewBox -54.8 -57.3 93.95
  105.55, viewBox centre (-7.825, -4.525) px; the prefab's old x read -7.9, the
  exporter's own origin rather than the viewBox, 0.075 px apart).  Seventeenth
  chip in a row whose prefab carried the raw art centre (-0.137065, 0.07850875)
  with no `STAGE_OFFSET`; the renderer is now (-0.144005, -0.10887125), that
  centre plus (-0.4, 10.8) px.  4x Ruffle comparison: **IoU 0.992, colour
  3.03/255** at zero shift, the neighbourhood at 0.918-0.928 and 20.2-21.9/255.
  Fifteen paths, seven plain fills, no `url(#gradient)`; the outline colours carry
  their own widths, and nothing comes out at a doubled `1.0` (the chip 32-34 trap).
  Gallery check: `renderers 1  sprites 1  bounds (3.91, 4.41, 0.50) @ (4.84,
  -0.27)` -- the striped curl over the left side of the head -- sprite drawn,
  RESULT OK; 0.0416 units per SWF px.  Design composite vs capture
  (`Logs/chip_0100_play/compare.png`): white-face ratio 4.43, and at that scale the
  stripes, both hooks and the brow all sit where the capture has them.
- Chip 137 is static: one renderer, one frame, `chip_0137_effect.svg` (viewBox
  `-9 -27.6 25.65 25.7`) -- a googly eye drawn over the face: a pale, faintly
  pink sclera inside a thick brown outline, an orange iris with yellow spots, a
  black pupil and a white catchlight.  Nothing to place and nothing to cut, and
  the `STAGE_OFFSET` pass had already put it at `bounds (0.95, 0.95, 0.50) @
  (5.35, 0.17)`.  It was drawn **black**: the SVG's sclera and iris are the
  chip's first two `url(#gradient...)` fills after chip 100
  (`radialGradient` `#95420f` -> `#d3751c` both times), and the prefab carried
  the built-in sprite material.  Swapping the renderer's `m_Materials` entry for
  `ChipMovie-Vector.mat` (fileID 2100000, guid `31d1e238...`) is the whole fix:
  `Logs/chip_0137_play/resting-close.png` now shows the shaded eye, matching a
  plain `rsvg-convert` of the same SVG (`art-ref.png`), and the near-black pixels
  are down to 10,368 of 1.56M (the pupil and the outlines, which are black in
  the art).  Gallery check after it: `renderers 1  sprites 1  bounds (0.95, 0.95,
  0.50) @ (5.35, 0.17)`, sprite drawn, RESULT OK.  This is the class the chip 20 /
  chip 42 notes describe, not a placement or colour-layer fault.
- Two whole-run audits from the chip 20 / chip 99 double report.  **Gradients:**
  of the ticked chips 17-100, only chip 20's *effect* art carries gradient fills
  (`url(#gradient)` in `<chip>_effect.svg`); the other gradient references live in
  the combined `<chip>_XXXX.svg` source files, which no renderer uses.  Chips 42,
  56, 59, 66 and now 20 use `ChipMovie-Vector.mat`; nothing else needs it before
  chip 100 -- but check every new effect SVG for gradient fills, because a wrong
  material renders black and the SVG-vs-Ruffle art check cannot see it.
  **Gradients past chip 100 (the sweep from 76 up), now done.**  The scan walks
  every chip 76-1500, per `SpriteRenderer`: resolve its `m_Sprite` guid to the
  `.svg`, require a real gradient reference (`url(#gradient`,
  `#radialGradient`, `#linearGradient`) and look at that renderer's own
  `m_Materials` entry.  `url(#clipPath0)` is a clip path, not a gradient -- chips
  76 and 83 have only that and render fine on the built-in material.  The scan
  found **390 chips / 560 renderers** drawing a gradient on the built-in sprite
  material, and all 560 were swapped to `ChipMovie-Vector.mat`; a re-scan now
  reads **0** left, with 588 renderers on the vector material in total.  The
  swap is per renderer, not per file, and that matters: chips 221 (1 of 4) and
  300 (1 of 6) each have exactly one gradient part, so their other renderers
  keep `10754` and must.  Others are all-gradient and take every renderer: 466
  (5), 770 (8), 863 (36), 1133 (5), 706/707 (4), 844 (12), 1069 (12).  Verify
  the split with the same per-renderer scan rather than `grep`ping the file.
  Evidence, all `ChipPlayCheck` `RESULT: OK` with the same bounds before and
  after (the pass touches no transform):
  * 164 -- four stars over the hair read as black tetrahedra before and as
    four cyan/orange gradient stars after (`Logs/chip_0164_play/
    before-resting-close.png` vs `resting-close.png`);
  * 175 -- the twelve-star tiara now matches a plain `rsvg-convert` of
    `chip_0175_effect.svg` star for star, yellow->pink through cyan and purple
    (`Logs/chip_0175_play/resting-close.png` vs `Logs/chip_0175_ref.png`);
  * 200 -- the striped limb stops being a black stub and shows its grey banding
    (`Logs/chip_0200_play/`);
  * 466 -- five renderers, one black teardrop with a sliver of blue becomes a
    filled cyan radial-gradient drop (`renderers 5  sprites 5`, same bounds).
  A clean re-scan afterwards reports 0 bad YAML preambles, 0 dangling sprite
  guids and 0 single-renderer static prefabs off the placement convention.
  **Multi-frame parts:** 148 chips in the plan have a part symbol with more than
  one frame, so their sprite has to swap inside the clip.  Only chip 99 does
  today; chip 57 is the one already ticked whose clip still holds a single pose
  (`chip_0057_part_1065` has 55 frames in an 87-frame clip, `CHIP 57 31 87`).
  Chip 57 was deliberately left alone here: rebuilding it from the plan replaces
  far more than the pose offsets (the regenerated track differs from the reviewed
  clip by thousands of keys) and nobody has compared that clip against Ruffle, so
  it needs its own check, not a drive-by rebuild.
- Movie frames are sprite-swap animations: `Tools/SwfToSvg/export_chip_movies.py`
  writes `Movie/frame_NNN.svg` plus `movie.json`; `Sitekick.ChipMovieBuilder.Run`
  builds the effect prefabs from them.
- Frame `.meta` guids are referenced by the prefabs. An export must preserve the
  existing guid of every frame it overwrites.
- An export rewrites every frame `.meta` from the template at
  `Chips/0101-0200/Chip_0177/Sprites/chip_0177_back.svg.meta`, and that template
  currently disagrees with what the committed frames carry (`viewportOptions:
  0` / `preserveViewport: 1` against `1` / `0`, and no `SpriteAlignment`).  A
  one-chip re-export therefore flips 59 sprites' import settings even though
  their guids survive.  Restore them after a re-export
  (`git checkout -- Assets/Chips/<range>/Chip_XXXX/Movie/*.svg.meta`) until the
  template and the shipped metas agree.

### Colour

- **What a chip colours is in the ActionScript, not the art.**
  `corus.effects.base.BaseEffect extends BasePaint`, and `BasePaint.checkKids`
  (and its `Event.ADDED` handler) paints every descendant clip whose instance
  name matches `/fill/i` with `new ColorTransform(0,0,0,1,r,g,b,0)`: the clip
  becomes a flat silhouette in the Sitekick's colour and keeps only its alpha.
  No effect class in 1-100 overrides `setColors`/`paint`, so that one rule is
  the whole story -- a chip with no `fill` clip is a chip that does not colour.
- `Tools/SwfToSvg/color_targets.py` walks the library XML once (8 s; one
  `extract_effect.py` per chip would be about a minute each) and prints the
  `fill` placements per chip, with the FFDec group (`spriteK`/`shapeK`) each one
  lands in.  Chips 1-100 with fills: 11, 12, 14, 16, 29, 36, 38, 42, 44, 45, 54,
  57, 58, 64, 72, 73, 74, 99.  Chips 3-6 are not in `effectlibrary1_250.swf`
  and have no class there.
- `split_fill_layers.py` cuts one exported SVG into **runs**: every maximal
  stretch of the drawing that is all-fill or all-not-fill becomes one layer,
  in the original draw order (chip 45's fills sit between other pieces, so a
  fixed three-layer cut covers parts of it wrongly).  FFDec writes the drawing
  as nested `<g id="xN_spriteK">` groups in draw order, so the fills are
  elements of that tree: each layer is a prune that keeps its pieces and the
  ancestors (and transforms) around them, plus its own copy of the `<defs>` /
  `<clipPath>` definitions, and `Logs/color-layers/<name>.layers.json` records
  the runs, which are fills and which are tinted.
- **A layer needs an anchor, or it lands in the wrong place.**  Unity's SVG
  importer measures a sprite from its own geometry bbox, not its viewBox (see
  `svg_bbox.py`), so a layer holding one small piece imported to a *smaller*
  rect, got centred on its own ink and drifted away from the rest of the chip;
  chips 72-74 were visibly out of register for that reason.  Every layer now
  carries an invisible `<rect>` over the *source* drawing's geometry bbox
  (`fill-opacity 0.001`), so all layers import to the same rect and pivot and
  share the original renderer's transform.  Verified by comparing each layer's
  import box with the source bbox (`svg_bbox.bbox` plus that rect) and by the
  play check, which now reports the same centre *and* size for every layer.
- **What the colour reaches is the fill plus its shading, not the whole
  drawing.**  Inside a fill clip everything is tinted (Flash paints it flat).
  Outside one, only a *translucent* piece is tinted: a 50 %-alpha grey is a
  shade drawn over the fill, so tinting it turns it into a darker shade of the
  colour.  Opaque art outside a fill clip is not painted by the effect at all
  and keeps its own greys -- chip 74's boots and hip screws, chip 73's shoulder
  knob, chip 44/72's spare pieces.  Chip 74 is the check: the shins follow the
  colour and the boots stay grey, which is the "ankle to knee" the colour is
  meant to cover.
- **Only the hands and feet stay as drawn; the limb between them and the joint
  takes the colour.**  Chips 72 and 73 put the *whole* arm -- hand included --
  in the one `fill` clip, so Flash would colour the fist too, and there is no
  separate hand piece in the art to leave alone; chip 74 needs no cut, because
  its boots and bolts really are opaque pieces outside the fill and stay grey
  by the rule above.  So 72 and 73 take a hand cut (`apply_color_layers.HANDS`),
  and the cut is **the seam the drawing already has**: `72` is the boxing
  glove's own silhouette (`shape2/6/2` -- thumb, knuckles, fingers and the cuff
  behind them, its lower edge is the wrist line), `73` is the fist's top
  outline (`shape2/7/6`'s points).  A straight line is not good enough: `x>87`
  on 72 left a white band up the sleeve's right end, and `slope -0.409,32.4` on
  73 cut a diagonal white strip and a grey wedge through the forearm because it
  ran through the mass rather than along the fist's black arc -- "the large
  mass between the hands/feet/joints is supposed to be fully coloured, not
  arbitrarily cut off".  A hand spec is one or more shapes separated by `;`:
  `outline shape2/7/3` (group, its 8th path, that path's 4th subpath, closed),
  `rect x,y,w,h`, `poly x,y x,y ...`, or the old `x>87` / `y<40` / `slope m,b`
  line cuts.  The shapes are unioned and may overshoot the drawing freely --
  the hand copy only draws where the run has art -- they just must not reach
  into the mass.
- **One shape per hand, because the union goes through an even-odd clip.**  The
  shapes are subpaths of one `clipPath` and the mass is that union knocked
  out of a rect (`clip-rule="evenodd"`), so where two shapes *overlap* the
  even-odd rule cancels them instead of merging: 72's glove, cut as the
  silhouette plus a knuckle band, a lobe and a right-hand rect, had the overlaps
  tinted -- a coloured knuckle in the middle of the hand -- while the rect that
  reached the art's edge took the forearm's bottom-right corner out of the
  colour with it.  `outline shape2/6/2` alone covers the whole glove and stops
  at the wrist line, so one shape is both the fix and the seam: overlapping
  specs need a `poly` that traces the outline they were approximating.
- **The hand copy and the tint are disjoint clips, not an overlay.**  A tinted
  run is written twice: clipped to the hand as an untinted layer, and clipped
  to the rest of the drawing's bbox with the hand shapes knocked out of it
  (`clip-rule="evenodd"` on that clipPath, named `rest`).  Drawing the untinted
  copy *over* the tint instead re-composites every translucent shade on the
  hand side: chip 73's fist came out a grey step darker at white (0.96 % of the
  composite's pixels, worst 39 levels), which is exactly the defect the old
  per-piece copy produced as a grey wedge.  Copying a whole *run* rather than
  each piece is what keeps the layer count down (72: four layers, 73: seven);
  the pieces of one run have to stay together anyway.  Unity's importer honours
  the even-odd clip -- checked in play mode, where the fist's 50 % shade renders
  `#CCCCCC`, the single-composite grey, not a blue-tinted one -- and at the
  default white the composite is unchanged to within the seam's antialiasing
  (72: 5 of 319k px differ, worst 6; 73: 8; 74: none).
- **The grey crease and edge lines take the colour too.**  They are drawn inside
  the fill clip in the SWF, so `paint()` multiplies them: Ruffle shows a darker
  shade of the colour there, not a grey line lying on top of it.  FFDec exports
  them flat and unclipped, so on 72 (the `#9e9e9e` band along the sleeve), 73
  (the `#666666` creases) and 74 (the `#666666` shin seams) they stayed grey
  while everything around them tinted -- "you missed the gray lines, those
  should be colored, not overlayed gray".  `split_fill_layers.grey_stroke`
  counts a stroke as shading when its colour is grey (r=g=b between 30 and
  225), which moves it into the tinted run and multiplies it to `(20,41,102)`
  for `#666666` under `3366FF` -- the values Ruffle renders.  Black outlines
  stay black, and the opaque grey *fills* that are really art outside the clip
  (74's boots, 73's shoulder knob) stay grey, so the rule is opt-in per chip
  (`apply_color_layers.TINT_STROKES = {72, 73, 74}`) rather than global: no
  other exported chip has been checked for it.
- **A coloured chip is checked against Ruffle with the fill recoloured.**  The
  effect's own `paint()` only ever tints the fill clip, so a reference is
  `extract_effect.py` on the chip, the fill shape's solid colour rewritten (72:
  1026, 73: 1021, 74: 1016), `-xml2swf`, and a screenshot through
  `ruffle_preview.html?swf=...&w=750&h=600` (the library stages are 550x400 and
  would crop the art).  What it shows is that **Flash paints the whole fill
  clip, fist included**: the hand cut is a deliberate difference from the site,
  asked for because only hands, feet and joints are meant to stay as drawn.
  Measured as colour-mask IoU against the painted render (art ink IoU 0.96-0.97
  first, so the alignment is good): 72 0.89, 73 0.60, 74 0.94.  Everything
  tinted in our layers that Ruffle does not paint is 2.7 % / 1.9 % / 2.7 % of
  the colour pixels -- seam antialiasing -- while what Ruffle paints and we do
  not is 8.4 % (72's glove) and 38.2 % (73's whole fist), plus 3.0 % on 74
  (its boot toes' antialiasing).  `Logs/chipcolor-review/chips-72-74-colour.png`
  holds the whole comparison per chip: Ruffle as drawn, Ruffle painted, our
  layers.  The sleeve band across 72's arm (the `#9e9e9e` stroke) does stay grey
  under colour on both sides, so the opaque-art rule holds there too.
- **The Sitekick body is a white/grey template tinted to Tuesday's palette.**
  The reference is not `sitekick.swf`'s runtime paint but **Tuesday.swf's
  sitekick, which is baked at its own colour**: at `#FFCC00` (100/80/0) its flat
  colours are `#FFCC00` body, `#D59A00` and `#B27600` shades, `#FFEB99` gloss
  and black lines.  `build_sitekick.py` rebuilds the head (sprite 29) as five
  display-list layers that reproduce exactly those relationships off one
  multiply:

  | object | SWF | art | tint |
  | --- | --- | --- | --- |
  | `Body` | shape 23, the opaque path | white | `C` |
  | `Body Gloss` | shape 23, its 60 %-white path | white, opaque | `Lift(C, 0.6)` |
  | `Body Shadow2` | sprite 25 (`paint(this,"shadow2")`) | `#B29393` = (0.698, 0.578) | `C` |
  | `Body Shadow` | sprite 27 (`paint(this,"shadow")`) | `#D5C1C1` = (0.835, 0.755) | `C` |
  | `Body Lines` | shape 28 (black outlines) | black | none |

  The shades are **baked ratios, not tone arithmetic**: Tuesday's deeper shade
  is `0.698 x C` on red and `0.578 x C` on green, so the layer art carries those
  greys and the runtime multiply does the rest.  At FFCC00 the body renders
  `#FFCC00` / `#D59A00` / `#B27600` / `#FFEB99` with the reference's proportions
  (shade2 15.4 % of the body's area against 16.1 %, shade 10.4 % against 13.4 %,
  gloss 5.5 % against 5.3 %).  The blue channel takes the green ratio because
  the baked reference is blue-less; at 3366FF the shades read `#2B4DC1` /
  `#243B93` rather than turning black.
  **The gloss cannot be a ratio, so it is a lift.**  It is the 60 %-white path
  inside shape 23, i.e. white over the body colour, which composites to
  `C + 0.6 (1 - C)` -- `#FFEB99` on `#FFCC00`, a pale blue on a blue Sitekick.
  Written as an art ratio it is impossible: it would need 235/204 = 1.15 on
  green and 153/0 on blue, and a multiplier above 1 is not a ratio.  So the
  layer ships as **opaque white art tinted by `SitekickColor.Lift(C, 0.6)`**,
  which is the same pixel the white alpha-0.6 overlay made (verified: the gloss
  mask against Tuesday's render is IoU 0.995, unchanged by the switch) while
  still following the picker like every other run instead of washing it white.
  `EditorSitekick` therefore has two lists and no tone fields:
  `coloredRenderers` = `Body`, `Body Shadow2`, `Body Shadow` (plain multiply)
  and `shineRenderers` = `Body Gloss` (`Lift`), and `SetColor` is those two
  multiplies plus the publish.  At white the gloss is white on white and so
  invisible -- that is inherent to a highlight, not a missing layer: the
  reference is paler than its body, and nothing can be paler than white.
  The other pieces (antenna, knob, washer, eyes) are never painted, so they keep
  their own colours.
  `sitekick.swf`'s own tone path still has a Ruffle reference, and it is what
  the movie chips will be wired against: `Tools/SwfToSvg/make_sitekick_probe.py
  ffcc00` inlines the transform into the
  48 painted clips' frame-1 scripts and writes `Temp/skpatch/sitekick_probe.swf`;
  serve the project root and open
  `Tools/SwfToSvg/sitekick_probe.html?swf=/Temp/skpatch/sitekick_probe.swf&w=1125&h=900`
  (a headless Chromium screenshot is the reliable way to capture it), then diff its
  histogram -- it reads `#FFCB00`, `#CB7900`, `#B26600`, i.e. the same values
  within one 1/255 step.  `SitekickColorCheck` (batch) renders the Unity body at
  FFCC00, white and 3366FF into `Logs/sitekick-colour-<hex>/art.png` and logs
  the six most common colours, which is the other half of that diff.
  Tinting is a multiply, so grey x colour is a darker
  shade of the colour -- that is the site's own math for a shaded piece
  (`paint(clip,"shadow")` is `rvalue - 20` on the multiplier) -- instead of an
  untinted grey overlay washing the colour towards grey.  Chip 73 is the
  example: its grey glove shadow is a 50 % overlay that used to read as a grey
  wedge over the colour and now reads as darker blue.  At the default white the
  multiply is the identity, and the check confirms it: the layered drawing with
  no tint is **0 differing pixels** from the original on all eleven chips.
  Checked with a tint by recolouring each tinted layer's white and grey fills
  (white -> colour, grey -> colour x grey, `Logs/color-check/<chip>_colour.svg`).
- `apply_color_layers.py` writes the layer sprites and their `.meta` (the
  original's import settings, new guid) and rewrites the prefab: one renderer
  per run at consecutive sorting orders, and the fill *and* shading runs in
  `ChipEffect.coloredRenderers`.  Chips done this way: 29, 38, 42, 44, 45, 54,
  58, 64, 72, 73, 74 (two runs each for 29/38/54/58/64, three for 42/44/72/73/74,
  six for 45).  Chip 99 needed nothing: its `fill_1` was already its own
  renderer (the white dome, order 1) after the four-wing split, so it is just
  listed in `coloredRenderers`.
- `apply_color_layers.check_prefab` refuses to write a prefab that is not real
  Unity YAML, or that points a renderer at a sprite that does not exist.  Both
  faults happened together on 72/73/74 and lived only in the prefab file, so
  nothing failed until the chip was drawn in game: the written prefab had lost
  its `%YAML` preamble and every block's `--- !u!` header (`1 &100001` instead
  of `--- !u!1 &100001`), and its four/five/seven `m_Sprite` refs named guids
  from an earlier split, so Unity still loaded the components and gave every
  renderer a null sprite.  `ChipPlayCheck --chip 72` is the check that sees it
  -- `renderers 4  sprites 0`, `FAIL the static effect draws nothing` -- while
  the prefab itself reads as complete.  A re-split deletes the old `_L*.svg`
  and mints a new guid per sprite (`sprite_meta`), so the patch has to be built
  from the `.svg.meta` files on disk, never from a listing of a previous run.
  The writer also appended to the old tint list instead of replacing it, so 72
  carried five copies of `L1` and four dead ids and 74 two dead ids;
  `coloredRenderers` is now the prefab's existing renderers, once each.
- The other half of that guard: a block header with **no body**.  Every
  colour-layer chip had stray `--- !u!114 &100020`-style lines with no
  `MonoBehaviour:` after them -- 36 of them across 11 prefabs (29, 38, 42, 44,
  45, 54, 58, 64, 72, 73, 74, 99), every id unreferenced.  A mid-file one
  truncates Unity's load: chip 74 reported `renderers 1  sprites 1` where its
  prefab has five renderers, and drew only the root sprite -- and
  `ChipPlayCheck` still said `RESULT OK`, because one sprite *was* drawn.  After
  deleting them all twelve chips load every renderer: 74 5/5, 45 8/8, 73 7/7,
  99 6/6, 38 5/5, 72 4/4, 42 4/4, 58 4/4, 44 3/3, 29/54/64 2/2.
  `check_prefab` misses this variant -- it looks for headers that lost their
  `--- !u!`, not headers whose body is empty -- so the scan has to also look for
  `^--- !u!\d+ &-?\d+\n(?=--- !u!|$)`.
  The variant was the layer writer's, not the library's: a sweep of all 1375
  `Chip_*_Effect.prefab` files finds **2144 declared `!u!212` blocks and 2144
  loaded SpriteRenderers, 0 empty headers, 0 orphan renderer blocks, 0 duplicate
  object ids, 0 malformed headers, 0 null sprites, 0 disabled renderers**, so
  the twelve fixed colour-layer chips were the whole class.  Two entry points
  keep it that way: `python3 Tools/check_renderer_counts.py` (text scan; writes
  `Logs/chip-renderer-counts-py.txt`) and the Unity batch
  `-executeMethod ChipRendererCountCheck.RunFromCommandLine` (loads every
  prefab and compares the live `GetComponentsInChildren<SpriteRenderer>(true)`
  count with the declared blocks; writes `Logs/chip-renderer-counts.txt`, exits
  1 on any under-load).  Run both after any change that writes prefab YAML --
  `ChipArtValidate` alone will not catch it, because one drawn sprite is enough
  for `ChipPlayCheck` to pass.
- **Tint under the vector material** (checked after the 390-chip material pass).
  Only twelve chips have colour layers at all -- 29, 38, 42, 44, 45, 54, 58,
  64, 72, 73, 74, 99 -- and exactly one of them, chip 42, also has a gradient
  sprite; there the gradient layer is `L3` (renderer 100016) and it is *not* in
  `coloredRenderers`, because the tinted layers L0/L2 are flat silver.  So no
  shipped chip pairs a tint with a gradient fill.  `ChipColorCheck`
  (`-executeMethod Sitekick.ChipColorCheck.RunFromCommandLine --chip N`, which
  writes `Logs/chip-colour/report.txt` and `art.png` captured *after* the tint)
  reads `RESULT OK` for 42 (two tinted renderers, vector material) and 74
  (built-in material): `_Color` FFCC00 at spawn, follows a change to 3C66FF,
  clears to white.  In pixels, 42 under FFCC00 goes from 39,731 silver px to
  742 and 13,422 yellow to 140,005 with the red emblem untouched.  Tinting L3 as
  well (temporary add to `coloredRenderers`, reverted) changed 72,489 px with
  mean delta RGB **(0.0, -19.9, -26.0)** -- r untouched, g -20%, b to 0, i.e.
  exactly the `_Color = (1, 0.8, 0)` multiply -- and all 21,476 pixels that had
  blue > 40 went to blue 0, so the multiply lands on gradient-sampled pixels too
  and the ramp survives it (`Logs/chip_0042_colour/art-with-gradient-layer.png`).
  Gotcha: `ChipPlayCheck --color` is not a tint test.  Both chips' captures came
  back byte-identical with and without `--color` (0 px changed), while
  `ChipColorCheck` sees the block set, so read the tint from `ChipColorCheck`.
- **Not coloured yet:** the movie chips 7, 8, 9, 10, 11, 12, 14, 16, 36, and
  chip 57.  Those chips are not painted by `BasePaint` at all: their own clips
  call the *site's* `paint(this,"shadow")` / `"shadow2"` / `"shadow3"` (or
  plain `paint(this)`) on their first frame -- sitekick.swf has 48 of those, and
  the chip SWFs use the same call -- so the colour reaches one *clip* at a time
  and each clip carries a tone.  Wiring them means knowing which clip each
  piece of each `Movie/frame_NNN.svg` came from, and `ChipMoviePlayer` swaps a
  single sprite per frame, so a frame needs to be split into a tinted and an
  untinted sprite (with the tint target swapped alongside).  The mapping is
  available -- the frame SVGs keep the same draw-order group numbering
  (`xN_spriteK`/`xN_shapeK`, nested) that `color_targets.py` uses, so the
  display list of the frame gives character id -> group -- but the movie
  prefabs, the player and the nine exports would all have to change together.
  Until then those chips do not change colour, like any chip with no fill clip.
  Chip 57's fills sit inside the part sprites and its animation is the
  known-broken one.
- **Unity side: one colour, one list per prefab.**  `SitekickColor`
  (Assets/Scripts) holds `Current`, raises `Changed`, and owns the arithmetic
  (`Tint(colour, tone, paintedParent)`: `C - tone/100` per channel, times `C`
  again when the piece sits inside a painted clip -- the tone path the movie
  chips need; the body and the static chips are a plain multiply).  A prefab
  says *which* renderers are painted by listing them --
  `ChipEffect.coloredRenderers` for a chip, `EditorSitekick.coloredRenderers`
  for the body -- and
  the scripts read the colour and follow it, so there is nothing per-renderer
  to set up.  That is the whole authoring surface a human touches: select the
  effect root, drag the tinted renderers into "Colored Renderers".
  `ChipGallery.ApplyColor` is one `SitekickColor.Set`, and `effectColor` only
  remembers the value across spawns, so an effect switched on later reads the
  colour as it enables.  Tinting itself is a `_Color` property block multiply
  (`Unlit/VectorGradient` multiplies both `_Color` and the renderer colour, and
  an unset block reads back as (0,0,0,0), not white).
  `ChipColorPanel` is the field under the grid: `RRGGBB` or `RGB`, with or
  without a leading `#`; empty or unreadable means white, which is the default.
  The scene comes from `ChipGalleryBuilder`; `Sitekick.ChipGalleryBuilder.AddColorRow`
  adds the row to an existing scene without rebuilding the 1375-cell grid.
  `ColorPicker` sits beside that row (`Sitekick.ChipGalleryBuilder.AddColorPicker`
  adds it to the existing scene): an HSV square and a hue strip that publish on
  every drag step, so the Sitekick and whatever effects are on show repaint
  under the pointer.  It builds its own gradient and cursor-ring textures, keeps
  its hue/value while dragging (a round trip through RGB would snap the hue at
  the grey ends), follows `SitekickColor.Changed` otherwise, and writes the hex
  field as it moves so the value can be copied.  `ColorPickerCheck` (batch,
  `-executeMethod Sitekick.ColorPickerCheck.RunFromCommandLine`) drives the real
  pointer handlers at screen points inside the two rects and reads back the
  published colour, the body's `_Color` and the field text;
  `Logs/color-picker/report.txt` reads `RESULT OK` with all three agreeing on
  every drag.
- `ChipColorCheck` (batch, `-executeMethod Sitekick.ChipColorCheck.RunFromCommandLine`,
  optional `--chip`) is the end-to-end check for that list: it sets FFCC00
  *before* spawning chip 45, so the effect has to come up in FFCC00 from its
  `coloredRenderers` alone, then changes the colour to 3366FF and back to white.
  `Logs/chip-colour/report.txt` reads `chip 45 colored renderers: 4`, the four
  `chip_0045_effect_L0/L2/L4/L6` tints at `RGBA(1.0, 0.8, 0.0)`, `followed a
  colour change: yes`, `reverted to white: yes`, `RESULT OK`.  `SitekickColorCheck`
  renders the body at FFCC00/FFFFFF/3366FF; at FFCC00 the capture reads
  `#FFCC00 108933`, `#B27600 16815`, `#D59A00 11341`, `#FFEB99 6086`,
  `#000000 30185` -- Tuesday's palette exactly, which is the point of the
  template (`Logs/sitekick-colour-ffcc00/`).
- **The Sitekick body is the reference for the chip math.**  `sitekick.swf` root
  frame 1 defines `_global.paint(clip, tone)` and 48 body clips call it on their
  own first frame: plain `paint(this)` is the colour itself, `"shadow"`,
  `"shadow2"` and `"shadow3"` are `rvalue/gvalue/bvalue` minus 20/30/40 on the
  per-channel *multiplier*, so each shade is a darker version of the chosen
  colour, never a grey.  The body art is a white and grey template under the
  same `_Color` multiply -- white -> colour, a shade grey -> a darker shade of
  the colour, black stays black -- so the Sitekick and the chips use one rule, a
  multiply of the chosen colour.  The body's greys are Tuesday's baked ratios,
  not `paint()`'s tones (see the template table above).  The washer, knob and
  eyes are not in `coloredRenderers` because nothing paints them.
- `ChipPlayCheck` takes `--hold`: it stops the spawned effect's Animators
  before their first update, so a chip whose parts animate is captured at the
  prefab's authored pose instead of a random frame of its fall (chip 151's
  flakes, see the particle composite above).
- `ChipPlayCheck` takes `--color RRGGBB`: it types the value into the field,
  presses Apply (`apply.onClick.Invoke()`, the same listener the button fires),
  spawns the chip into that colour and writes the tint of every renderer to
  `Logs/chip_NNNN_play_<hex>/report.txt`.  Chip 42 tints only
  `chip_0042_effect_L1`; chip 99 only `chip_0099_body`; chip 45 only L0/L2/L4;
  chip 20, which has no fill clip, reads `untouched`; every run also shows
  `sitekick Body: <hex> (set)` and `RESULT: OK`.  `ChipGalleryBuilder.Check`
  additionally reports the colour row: the field's character limit and font,
  the Apply button, and the result of typing `ff3322` then an empty value (back
  to `FFFFFF`).
- **A tint is a multiply, Flash's paint is a replace.**  Every fill drawing is
  `#ffffff` except one `#999999` path in chip 45 (`baseFill`, the shadow side of
  its guitar), which therefore comes out 0.6x the chosen colour rather than
  flat.  Nothing else in 1-100 is affected; fixing it means a shader that
  replaces the colour instead of multiplying, not a change to the art (toning
  that path to white would also change how chip 45 looks at the default white).

## Chip review queue

Chips 17-1375, in order, one per line.  Each gets the same pass: the export
checked against a Ruffle reference, then the movie played in the gallery
(`ChipPlayCheck`).  Mark `[x]` only when the art and the timing agree with
Ruffle and the animation plays correctly in Unity.

- [x] 17
- [x] 18
- [x] 19
- [x] 20
- [x] 21
- [x] 22
- [x] 23
- [x] 24
- [x] 25
- [x] 26
- [x] 27
- [x] 28
- [x] 29
- [x] 30
- [x] 31
- [x] 32
- [x] 33
- [x] 34
- [x] 35
- [x] 36
- [x] 37
- [x] 38
- [x] 39
- [x] 40
- [x] 41
- [x] 42
- [x] 43
- [x] 44
- [x] 45
- [x] 46
- [x] 47
- [x] 48
- [x] 49
- [x] 50
- [x] 51
- [x] 52
- [x] 53
- [x] 54
- [x] 55
- [x] 56
- [x] 57
- [x] 58
- [x] 59
- [x] 60
- [x] 61
- [x] 62
- [x] 63
- [x] 64
- [x] 65
- [x] 66
- [x] 67
- [x] 68
- [x] 69
- [x] 70
- [x] 71
- [x] 72
- [x] 73
- [x] 74
- [x] 75
- [x] 76
- [x] 77
- [x] 78
- [x] 79
- [x] 80
- [x] 81
- [x] 82
- [x] 83
- [x] 84
- [x] 85
- [x] 86
- [x] 87
- [x] 88
- [x] 89
- [x] 90
- [x] 91
- [x] 92
- [x] 93
- [x] 94
- [x] 95
- [x] 96
- [x] 97
- [x] 98
- [x] 99
- [x] 100
- [ ] 101
- [ ] 102
- [ ] 103
- [ ] 104
- [ ] 105
- [ ] 106
- [ ] 107
- [ ] 108
- [ ] 109
- [ ] 110
- [ ] 111
- [ ] 112
- [ ] 113
- [ ] 114
- [ ] 115
- [ ] 116
- [ ] 117
- [ ] 118
- [ ] 119
- [ ] 120
- [ ] 121
- [ ] 122
- [ ] 123
- [ ] 124
- [ ] 125
- [ ] 126
- [ ] 127
- [ ] 128
- [ ] 129
- [ ] 130
- [ ] 131
- [ ] 132
- [ ] 133
- [ ] 134
- [ ] 135
- [ ] 136
- [ ] 137
- [ ] 138
- [ ] 139
- [ ] 140
- [ ] 141
- [ ] 142
- [ ] 143
- [ ] 144
- [ ] 145
- [ ] 146
- [ ] 147
- [ ] 148
- [ ] 149
- [ ] 150
- [ ] 151
- [ ] 152
- [ ] 153
- [ ] 154
- [ ] 155
- [ ] 156
- [ ] 157
- [ ] 158
- [ ] 159
- [ ] 160
- [ ] 161
- [ ] 162
- [ ] 163
- [ ] 164
- [ ] 165
- [ ] 166
- [ ] 167
- [ ] 168
- [ ] 169
- [ ] 170
- [ ] 171
- [ ] 172
- [ ] 173
- [ ] 174
- [ ] 175
- [ ] 176
- [ ] 177
- [ ] 178
- [ ] 179
- [ ] 180
- [ ] 181
- [ ] 182
- [ ] 183
- [ ] 184
- [ ] 185
- [ ] 186
- [ ] 187
- [ ] 188
- [ ] 189
- [ ] 190
- [ ] 191
- [ ] 192
- [ ] 193
- [ ] 194
- [ ] 195
- [ ] 196
- [ ] 197
- [ ] 198
- [ ] 199
- [ ] 200
- [ ] 201
- [ ] 202
- [ ] 203
- [ ] 204
- [ ] 205
- [ ] 206
- [ ] 207
- [ ] 208
- [ ] 209
- [ ] 210
- [ ] 211
- [ ] 212
- [ ] 213
- [ ] 214
- [ ] 215
- [ ] 216
- [ ] 217
- [ ] 218
- [ ] 219
- [ ] 220
- [ ] 221
- [ ] 222
- [ ] 223
- [ ] 224
- [ ] 225
- [ ] 226
- [ ] 227
- [ ] 228
- [ ] 229
- [ ] 230
- [ ] 231
- [ ] 232
- [ ] 233
- [ ] 234
- [ ] 235
- [ ] 236
- [ ] 237
- [ ] 238
- [ ] 239
- [ ] 240
- [ ] 241
- [ ] 242
- [ ] 243
- [ ] 244
- [ ] 245
- [ ] 246
- [ ] 247
- [ ] 248
- [ ] 249
- [ ] 250
- [ ] 251
- [ ] 252
- [ ] 253
- [ ] 254
- [ ] 255
- [ ] 256
- [ ] 257
- [ ] 258
- [ ] 259
- [ ] 260
- [ ] 261
- [ ] 262
- [ ] 263
- [ ] 264
- [ ] 265
- [ ] 266
- [ ] 267
- [ ] 268
- [ ] 269
- [ ] 270
- [ ] 271
- [ ] 272
- [ ] 273
- [ ] 274
- [ ] 275
- [ ] 276
- [ ] 277
- [ ] 278
- [ ] 279
- [ ] 280
- [ ] 281
- [ ] 282
- [ ] 283
- [ ] 284
- [ ] 285
- [ ] 286
- [ ] 287
- [ ] 288
- [ ] 289
- [ ] 290
- [ ] 291
- [ ] 292
- [ ] 293
- [ ] 294
- [ ] 295
- [ ] 296
- [ ] 297
- [ ] 298
- [ ] 299
- [ ] 300
- [ ] 301
- [ ] 302
- [ ] 303
- [ ] 304
- [ ] 305
- [ ] 306
- [ ] 307
- [ ] 308
- [ ] 309
- [ ] 310
- [ ] 311
- [ ] 312
- [ ] 313
- [ ] 314
- [ ] 315
- [ ] 316
- [ ] 317
- [ ] 318
- [ ] 319
- [ ] 320
- [ ] 321
- [ ] 322
- [ ] 323
- [ ] 324
- [ ] 325
- [ ] 326
- [ ] 327
- [ ] 328
- [ ] 329
- [ ] 330
- [ ] 331
- [ ] 332
- [ ] 333
- [ ] 334
- [ ] 335
- [ ] 336
- [ ] 337
- [ ] 338
- [ ] 339
- [ ] 340
- [ ] 341
- [ ] 342
- [ ] 343
- [ ] 344
- [ ] 345
- [ ] 346
- [ ] 347
- [ ] 348
- [ ] 349
- [ ] 350
- [ ] 351
- [ ] 352
- [ ] 353
- [ ] 354
- [ ] 355
- [ ] 356
- [ ] 357
- [ ] 358
- [ ] 359
- [ ] 360
- [ ] 361
- [ ] 362
- [ ] 363
- [ ] 364
- [ ] 365
- [ ] 366
- [ ] 367
- [ ] 368
- [ ] 369
- [ ] 370
- [ ] 371
- [ ] 372
- [ ] 373
- [ ] 374
- [ ] 375
- [ ] 376
- [ ] 377
- [ ] 378
- [ ] 379
- [ ] 380
- [ ] 381
- [ ] 382
- [ ] 383
- [ ] 384
- [ ] 385
- [ ] 386
- [ ] 387
- [ ] 388
- [ ] 389
- [ ] 390
- [ ] 391
- [ ] 392
- [ ] 393
- [ ] 394
- [ ] 395
- [ ] 396
- [ ] 397
- [ ] 398
- [ ] 399
- [ ] 400
- [ ] 401
- [ ] 402
- [ ] 403
- [ ] 404
- [ ] 405
- [ ] 406
- [ ] 407
- [ ] 408
- [ ] 409
- [ ] 410
- [ ] 411
- [ ] 412
- [ ] 413
- [ ] 414
- [ ] 415
- [ ] 416
- [ ] 417
- [ ] 418
- [ ] 419
- [ ] 420
- [ ] 421
- [ ] 422
- [ ] 423
- [ ] 424
- [ ] 425
- [ ] 426
- [ ] 427
- [ ] 428
- [ ] 429
- [ ] 430
- [ ] 431
- [ ] 432
- [ ] 433
- [ ] 434
- [ ] 435
- [ ] 436
- [ ] 437
- [ ] 438
- [ ] 439
- [ ] 440
- [ ] 441
- [ ] 442
- [ ] 443
- [ ] 444
- [ ] 445
- [ ] 446
- [ ] 447
- [ ] 448
- [ ] 449
- [ ] 450
- [ ] 451
- [ ] 452
- [ ] 453
- [ ] 454
- [ ] 455
- [ ] 456
- [ ] 457
- [ ] 458
- [ ] 459
- [ ] 460
- [ ] 461
- [ ] 462
- [ ] 463
- [ ] 464
- [ ] 465
- [ ] 466
- [ ] 467
- [ ] 468
- [ ] 469
- [ ] 470
- [ ] 471
- [ ] 472
- [ ] 473
- [ ] 474
- [ ] 475
- [ ] 476
- [ ] 477
- [ ] 478
- [ ] 479
- [ ] 480
- [ ] 481
- [ ] 482
- [ ] 483
- [ ] 484
- [ ] 485
- [ ] 486
- [ ] 487
- [ ] 488
- [ ] 489
- [ ] 490
- [ ] 491
- [ ] 492
- [ ] 493
- [ ] 494
- [ ] 495
- [ ] 496
- [ ] 497
- [ ] 498
- [ ] 499
- [ ] 500
- [ ] 501
- [ ] 502
- [ ] 503
- [ ] 504
- [ ] 505
- [ ] 506
- [ ] 507
- [ ] 508
- [ ] 509
- [ ] 510
- [ ] 511
- [ ] 512
- [ ] 513
- [ ] 514
- [ ] 515
- [ ] 516
- [ ] 517
- [ ] 518
- [ ] 519
- [ ] 520
- [ ] 521
- [ ] 522
- [ ] 523
- [ ] 524
- [ ] 525
- [ ] 526
- [ ] 527
- [ ] 528
- [ ] 529
- [ ] 530
- [ ] 531
- [ ] 532
- [ ] 533
- [ ] 534
- [ ] 535
- [ ] 536
- [ ] 537
- [ ] 538
- [ ] 539
- [ ] 540
- [ ] 541
- [ ] 542
- [ ] 543
- [ ] 544
- [ ] 545
- [ ] 546
- [ ] 547
- [ ] 548
- [ ] 549
- [ ] 550
- [ ] 551
- [ ] 552
- [ ] 553
- [ ] 554
- [ ] 555
- [ ] 556
- [ ] 557
- [ ] 558
- [ ] 559
- [ ] 560
- [ ] 561
- [ ] 562
- [ ] 563
- [ ] 564
- [ ] 565
- [ ] 566
- [ ] 567
- [ ] 568
- [ ] 569
- [ ] 570
- [ ] 571
- [ ] 572
- [ ] 573
- [ ] 574
- [ ] 575
- [ ] 576
- [ ] 577
- [ ] 578
- [ ] 579
- [ ] 580
- [ ] 581
- [ ] 582
- [ ] 583
- [ ] 584
- [ ] 585
- [ ] 586
- [ ] 587
- [ ] 588
- [ ] 589
- [ ] 590
- [ ] 591
- [ ] 592
- [ ] 593
- [ ] 594
- [ ] 595
- [ ] 596
- [ ] 597
- [ ] 598
- [ ] 599
- [ ] 600
- [ ] 601
- [ ] 602
- [ ] 603
- [ ] 604
- [ ] 605
- [ ] 606
- [ ] 607
- [ ] 608
- [ ] 609
- [ ] 610
- [ ] 611
- [ ] 612
- [ ] 613
- [ ] 614
- [ ] 615
- [ ] 616
- [ ] 617
- [ ] 618
- [ ] 619
- [ ] 620
- [ ] 621
- [ ] 622
- [ ] 623
- [ ] 624
- [ ] 625
- [ ] 626
- [ ] 627
- [ ] 628
- [ ] 629
- [ ] 630
- [ ] 631
- [ ] 632
- [ ] 633
- [ ] 634
- [ ] 635
- [ ] 636
- [ ] 637
- [ ] 638
- [ ] 639
- [ ] 640
- [ ] 641
- [ ] 642
- [ ] 643
- [ ] 644
- [ ] 645
- [ ] 646
- [ ] 647
- [ ] 648
- [ ] 649
- [ ] 650
- [ ] 651
- [ ] 652
- [ ] 653
- [ ] 654
- [ ] 655
- [ ] 656
- [ ] 657
- [ ] 658
- [ ] 659
- [ ] 660
- [ ] 661
- [ ] 662
- [ ] 663
- [ ] 664
- [ ] 665
- [ ] 666
- [ ] 667
- [ ] 668
- [ ] 669
- [ ] 670
- [ ] 671
- [ ] 672
- [ ] 673
- [ ] 674
- [ ] 675
- [ ] 676
- [ ] 677
- [ ] 678
- [ ] 679
- [ ] 680
- [ ] 681
- [ ] 682
- [ ] 683
- [ ] 684
- [ ] 685
- [ ] 686
- [ ] 687
- [ ] 688
- [ ] 689
- [ ] 690
- [ ] 691
- [ ] 692
- [ ] 693
- [ ] 694
- [ ] 695
- [ ] 696
- [ ] 697
- [ ] 698
- [ ] 699
- [ ] 700
- [ ] 701
- [ ] 702
- [ ] 703
- [ ] 704
- [ ] 705
- [ ] 706
- [ ] 707
- [ ] 708
- [ ] 709
- [ ] 710
- [ ] 711
- [ ] 712
- [ ] 713
- [ ] 714
- [ ] 715
- [ ] 716
- [ ] 717
- [ ] 718
- [ ] 719
- [ ] 720
- [ ] 721
- [ ] 722
- [ ] 723
- [ ] 724
- [ ] 725
- [ ] 726
- [ ] 727
- [ ] 728
- [ ] 729
- [ ] 730
- [ ] 731
- [ ] 732
- [ ] 733
- [ ] 734
- [ ] 735
- [ ] 736
- [ ] 737
- [ ] 738
- [ ] 739
- [ ] 740
- [ ] 741
- [ ] 742
- [ ] 743
- [ ] 744
- [ ] 745
- [ ] 746
- [ ] 747
- [ ] 748
- [ ] 749
- [ ] 750
- [ ] 751
- [ ] 752
- [ ] 753
- [ ] 754
- [ ] 755
- [ ] 756
- [ ] 757
- [ ] 758
- [ ] 759
- [ ] 760
- [ ] 761
- [ ] 762
- [ ] 763
- [ ] 764
- [ ] 765
- [ ] 766
- [ ] 767
- [ ] 768
- [ ] 769
- [ ] 770
- [ ] 771
- [ ] 772
- [ ] 773
- [ ] 774
- [ ] 775
- [ ] 776
- [ ] 777
- [ ] 778
- [ ] 779
- [ ] 780
- [ ] 781
- [ ] 782
- [ ] 783
- [ ] 784
- [ ] 785
- [ ] 786
- [ ] 787
- [ ] 788
- [ ] 789
- [ ] 790
- [ ] 791
- [ ] 792
- [ ] 793
- [ ] 794
- [ ] 795
- [ ] 796
- [ ] 797
- [ ] 798
- [ ] 799
- [ ] 800
- [ ] 801
- [ ] 802
- [ ] 803
- [ ] 804
- [ ] 805
- [ ] 806
- [ ] 807
- [ ] 808
- [ ] 809
- [ ] 810
- [ ] 811
- [ ] 812
- [ ] 813
- [ ] 814
- [ ] 815
- [ ] 816
- [ ] 817
- [ ] 818
- [ ] 819
- [ ] 820
- [ ] 821
- [ ] 822
- [ ] 823
- [ ] 824
- [ ] 825
- [ ] 826
- [ ] 827
- [ ] 828
- [ ] 829
- [ ] 830
- [ ] 831
- [ ] 832
- [ ] 833
- [ ] 834
- [ ] 835
- [ ] 836
- [ ] 837
- [ ] 838
- [ ] 839
- [ ] 840
- [ ] 841
- [ ] 842
- [ ] 843
- [ ] 844
- [ ] 845
- [ ] 846
- [ ] 847
- [ ] 848
- [ ] 849
- [ ] 850
- [ ] 851
- [ ] 852
- [ ] 853
- [ ] 854
- [ ] 855
- [ ] 856
- [ ] 857
- [ ] 858
- [ ] 859
- [ ] 860
- [ ] 861
- [ ] 862
- [ ] 863
- [ ] 864
- [ ] 865
- [ ] 866
- [ ] 867
- [ ] 868
- [ ] 869
- [ ] 870
- [ ] 871
- [ ] 872
- [ ] 873
- [ ] 874
- [ ] 875
- [ ] 876
- [ ] 877
- [ ] 878
- [ ] 879
- [ ] 880
- [ ] 881
- [ ] 882
- [ ] 883
- [ ] 884
- [ ] 885
- [ ] 886
- [ ] 887
- [ ] 888
- [ ] 889
- [ ] 890
- [ ] 891
- [ ] 892
- [ ] 893
- [ ] 894
- [ ] 895
- [ ] 896
- [ ] 897
- [ ] 898
- [ ] 899
- [ ] 900
- [ ] 901
- [ ] 902
- [ ] 903
- [ ] 904
- [ ] 905
- [ ] 906
- [ ] 907
- [ ] 908
- [ ] 909
- [ ] 910
- [ ] 911
- [ ] 912
- [ ] 913
- [ ] 914
- [ ] 915
- [ ] 916
- [ ] 917
- [ ] 918
- [ ] 919
- [ ] 920
- [ ] 921
- [ ] 922
- [ ] 923
- [ ] 924
- [ ] 925
- [ ] 926
- [ ] 927
- [ ] 928
- [ ] 929
- [ ] 930
- [ ] 931
- [ ] 932
- [ ] 933
- [ ] 934
- [ ] 935
- [ ] 936
- [ ] 937
- [ ] 938
- [ ] 939
- [ ] 940
- [ ] 941
- [ ] 942
- [ ] 943
- [ ] 944
- [ ] 945
- [ ] 946
- [ ] 947
- [ ] 948
- [ ] 949
- [ ] 950
- [ ] 951
- [ ] 952
- [ ] 953
- [ ] 954
- [ ] 955
- [ ] 956
- [ ] 957
- [ ] 958
- [ ] 959
- [ ] 960
- [ ] 961
- [ ] 962
- [ ] 963
- [ ] 964
- [ ] 965
- [ ] 966
- [ ] 967
- [ ] 968
- [ ] 969
- [ ] 970
- [ ] 971
- [ ] 972
- [ ] 973
- [ ] 974
- [ ] 975
- [ ] 976
- [ ] 977
- [ ] 978
- [ ] 979
- [ ] 980
- [ ] 981
- [ ] 982
- [ ] 983
- [ ] 984
- [ ] 985
- [ ] 986
- [ ] 987
- [ ] 988
- [ ] 989
- [ ] 990
- [ ] 991
- [ ] 992
- [ ] 993
- [ ] 994
- [ ] 995
- [ ] 996
- [ ] 997
- [ ] 998
- [ ] 999
- [ ] 1000
- [ ] 1001
- [ ] 1002
- [ ] 1003
- [ ] 1004
- [ ] 1005
- [ ] 1006
- [ ] 1007
- [ ] 1008
- [ ] 1009
- [ ] 1010
- [ ] 1011
- [ ] 1012
- [ ] 1013
- [ ] 1014
- [ ] 1015
- [ ] 1016
- [ ] 1017
- [ ] 1018
- [ ] 1019
- [ ] 1020
- [ ] 1021
- [ ] 1022
- [ ] 1023
- [ ] 1024
- [ ] 1025
- [ ] 1026
- [ ] 1027
- [ ] 1028
- [ ] 1029
- [ ] 1030
- [ ] 1031
- [ ] 1032
- [ ] 1033
- [ ] 1034
- [ ] 1035
- [ ] 1036
- [ ] 1037
- [ ] 1038
- [ ] 1039
- [ ] 1040
- [ ] 1041
- [ ] 1042
- [ ] 1043
- [ ] 1044
- [ ] 1045
- [ ] 1046
- [ ] 1047
- [ ] 1048
- [ ] 1049
- [ ] 1050
- [ ] 1051
- [ ] 1052
- [ ] 1053
- [ ] 1054
- [ ] 1055
- [ ] 1056
- [ ] 1057
- [ ] 1058
- [ ] 1059
- [ ] 1060
- [ ] 1061
- [ ] 1062
- [ ] 1063
- [ ] 1064
- [ ] 1065
- [ ] 1066
- [ ] 1067
- [ ] 1068
- [ ] 1069
- [ ] 1070
- [ ] 1071
- [ ] 1072
- [ ] 1073
- [ ] 1074
- [ ] 1075
- [ ] 1076
- [ ] 1077
- [ ] 1078
- [ ] 1079
- [ ] 1080
- [ ] 1081
- [ ] 1082
- [ ] 1083
- [ ] 1084
- [ ] 1085
- [ ] 1086
- [ ] 1087
- [ ] 1088
- [ ] 1089
- [ ] 1090
- [ ] 1091
- [ ] 1092
- [ ] 1093
- [ ] 1094
- [ ] 1095
- [ ] 1096
- [ ] 1097
- [ ] 1098
- [ ] 1099
- [ ] 1100
- [ ] 1101
- [ ] 1102
- [ ] 1103
- [ ] 1104
- [ ] 1105
- [ ] 1106
- [ ] 1107
- [ ] 1108
- [ ] 1109
- [ ] 1110
- [ ] 1111
- [ ] 1112
- [ ] 1113
- [ ] 1114
- [ ] 1115
- [ ] 1116
- [ ] 1117
- [ ] 1118
- [ ] 1119
- [ ] 1120
- [ ] 1121
- [ ] 1122
- [ ] 1123
- [ ] 1124
- [ ] 1125
- [ ] 1126
- [ ] 1127
- [ ] 1128
- [ ] 1129
- [ ] 1130
- [ ] 1131
- [ ] 1132
- [ ] 1133
- [ ] 1134
- [ ] 1135
- [ ] 1136
- [ ] 1137
- [ ] 1138
- [ ] 1139
- [ ] 1140
- [ ] 1141
- [ ] 1142
- [ ] 1143
- [ ] 1144
- [ ] 1145
- [ ] 1146
- [ ] 1147
- [ ] 1148
- [ ] 1149
- [ ] 1150
- [ ] 1151
- [ ] 1152
- [ ] 1153
- [ ] 1154
- [ ] 1155
- [ ] 1156
- [ ] 1157
- [ ] 1158
- [ ] 1159
- [ ] 1160
- [ ] 1161
- [ ] 1162
- [ ] 1163
- [ ] 1164
- [ ] 1165
- [ ] 1166
- [ ] 1167
- [ ] 1168
- [ ] 1169
- [ ] 1170
- [ ] 1171
- [ ] 1172
- [ ] 1173
- [ ] 1174
- [ ] 1175
- [ ] 1176
- [ ] 1177
- [ ] 1178
- [ ] 1179
- [ ] 1180
- [ ] 1181
- [ ] 1182
- [ ] 1183
- [ ] 1184
- [ ] 1185
- [ ] 1186
- [ ] 1187
- [ ] 1188
- [ ] 1189
- [ ] 1190
- [ ] 1191
- [ ] 1192
- [ ] 1193
- [ ] 1194
- [ ] 1195
- [ ] 1196
- [ ] 1197
- [ ] 1198
- [ ] 1199
- [ ] 1200
- [ ] 1201
- [ ] 1202
- [ ] 1203
- [ ] 1204
- [ ] 1205
- [ ] 1206
- [ ] 1207
- [ ] 1208
- [ ] 1209
- [ ] 1210
- [ ] 1211
- [ ] 1212
- [ ] 1213
- [ ] 1214
- [ ] 1215
- [ ] 1216
- [ ] 1217
- [ ] 1218
- [ ] 1219
- [ ] 1220
- [ ] 1221
- [ ] 1222
- [ ] 1223
- [ ] 1224
- [ ] 1225
- [ ] 1226
- [ ] 1227
- [ ] 1228
- [ ] 1229
- [ ] 1230
- [ ] 1231
- [ ] 1232
- [ ] 1233
- [ ] 1234
- [ ] 1235
- [ ] 1236
- [ ] 1237
- [ ] 1238
- [ ] 1239
- [ ] 1240
- [ ] 1241
- [ ] 1242
- [ ] 1243
- [ ] 1244
- [ ] 1245
- [ ] 1246
- [ ] 1247
- [ ] 1248
- [ ] 1249
- [ ] 1250
- [ ] 1251
- [ ] 1252
- [ ] 1253
- [ ] 1254
- [ ] 1255
- [ ] 1256
- [ ] 1257
- [ ] 1258
- [ ] 1259
- [ ] 1260
- [ ] 1261
- [ ] 1262
- [ ] 1263
- [ ] 1264
- [ ] 1265
- [ ] 1266
- [ ] 1267
- [ ] 1268
- [ ] 1269
- [ ] 1270
- [ ] 1271
- [ ] 1272
- [ ] 1273
- [ ] 1274
- [ ] 1275
- [ ] 1276
- [ ] 1277
- [ ] 1278
- [ ] 1279
- [ ] 1280
- [ ] 1281
- [ ] 1282
- [ ] 1283
- [ ] 1284
- [ ] 1285
- [ ] 1286
- [ ] 1287
- [ ] 1288
- [ ] 1289
- [ ] 1290
- [ ] 1291
- [ ] 1292
- [ ] 1293
- [ ] 1294
- [ ] 1295
- [ ] 1296
- [ ] 1297
- [ ] 1298
- [ ] 1299
- [ ] 1300
- [ ] 1301
- [ ] 1302
- [ ] 1303
- [ ] 1304
- [ ] 1305
- [ ] 1306
- [ ] 1307
- [ ] 1308
- [ ] 1309
- [ ] 1310
- [ ] 1311
- [ ] 1312
- [ ] 1313
- [ ] 1314
- [ ] 1315
- [ ] 1316
- [ ] 1317
- [ ] 1318
- [ ] 1319
- [ ] 1320
- [ ] 1321
- [ ] 1322
- [ ] 1323
- [ ] 1324
- [ ] 1325
- [ ] 1326
- [ ] 1327
- [ ] 1328
- [ ] 1329
- [ ] 1330
- [ ] 1331
- [ ] 1332
- [ ] 1333
- [ ] 1334
- [ ] 1335
- [ ] 1336
- [ ] 1337
- [ ] 1338
- [ ] 1339
- [ ] 1340
- [ ] 1341
- [ ] 1342
- [ ] 1343
- [ ] 1344
- [ ] 1345
- [ ] 1346
- [ ] 1347
- [ ] 1348
- [ ] 1349
- [ ] 1350
- [ ] 1351
- [ ] 1352
- [ ] 1353
- [ ] 1354
- [ ] 1355
- [ ] 1356
- [ ] 1357
- [ ] 1358
- [ ] 1359
- [ ] 1360
- [ ] 1361
- [ ] 1362
- [ ] 1363
- [ ] 1364
- [ ] 1365
- [ ] 1366
- [ ] 1367
- [ ] 1368
- [ ] 1369
- [ ] 1370
- [ ] 1371
- [ ] 1372
- [ ] 1373
- [ ] 1374
- [ ] 1375
