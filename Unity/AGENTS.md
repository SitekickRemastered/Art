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
- [ ] 34
- [ ] 35
- [ ] 36
- [ ] 37
- [ ] 38
- [ ] 39
- [ ] 40
- [ ] 41
- [ ] 42
- [ ] 43
- [ ] 44
- [ ] 45
- [ ] 46
- [ ] 47
- [ ] 48
- [ ] 49
- [ ] 50
- [ ] 51
- [ ] 52
- [ ] 53
- [ ] 54
- [ ] 55
- [ ] 56
- [ ] 57
- [ ] 58
- [ ] 59
- [ ] 60
- [ ] 61
- [ ] 62
- [ ] 63
- [ ] 64
- [ ] 65
- [ ] 66
- [ ] 67
- [ ] 68
- [ ] 69
- [ ] 70
- [ ] 71
- [ ] 72
- [ ] 73
- [ ] 74
- [ ] 75
- [ ] 76
- [ ] 77
- [ ] 78
- [ ] 79
- [ ] 80
- [ ] 81
- [ ] 82
- [ ] 83
- [ ] 84
- [ ] 85
- [ ] 86
- [ ] 87
- [ ] 88
- [ ] 89
- [ ] 90
- [ ] 91
- [ ] 92
- [ ] 93
- [ ] 94
- [ ] 95
- [ ] 96
- [ ] 97
- [ ] 98
- [ ] 99
- [ ] 100
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
