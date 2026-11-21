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
- `Tools/SwfToSvg/patch_stopped_clips.py` runs on every chip during export. It
  freezes the stops no script can reach (a clip that stops itself, still has art
  after the stop, and is placed under a name the ActionScript never mentions and
  never builds on the fly) so the clip holds its parked frame instead of playing
  out and looping. Clips whose names the scripts do jump are left alone: those
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
