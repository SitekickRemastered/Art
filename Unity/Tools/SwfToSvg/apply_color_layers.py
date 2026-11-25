#!/usr/bin/env python3
"""Give a chip's effect a tinted layer for every piece Flash would repaint.

`color_targets.py` says which display objects the Sitekick colour reaches;
`split_fill_layers.py` cuts that art out into `_below` / `_fill` / `_above`.
This script puts the result into the prefab: the layer drawings are imported
next to the original, and the prefab gets one renderer per layer at
consecutive sorting orders, with only the fill layer in
`ChipEffect.coloredRenderers` -- the list `ApplyColor` tints.

    python3 Tools/SwfToSvg/apply_color_layers.py 42 44 45
"""
import argparse
import glob
import json
import os
import re
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

import split_fill_layers as splitter

SPRITE_FILE_ID = 3286163911610860551

# Chips whose art puts the hand inside the same fill clip as the arm, so the
# whole limb would take the colour.  The value is the hand side, as shapes in
# the art's own coordinates (see `split_fill_layers.hand_parts`): the seam is an
# outline the drawing already has, so the colour reaches the mass right up to
# the joint's black line instead of stopping at a straight cut somewhere in it.
# Only the hand is kept as drawn -- the arm or leg between it and the joint
# takes the colour.  Chip 74 needs no cut: its boots and bolts are opaque
# pieces outside the fill and stay grey on their own.
HANDS = {
    # 72: a boxing glove on a sleeve, and the glove's own silhouette
    # (shape2/6/2) is the whole hand: thumb, knuckles, fingers and the cuff
    # behind them, down to the wrist line its lower edge already draws.  One
    # shape, deliberately: overlapping shapes leave even-odd holes in the
    # `rest` clip where they intersect, which coloured a knuckle, and a rect
    # out to the art's edge took the forearm's bottom-right corner with it.
    72: "outline shape2/6/2",
    # 73: a fist under the wrist joint -- everything the fist's own top outline
    # (shape2/7/6) encloses.  The arm keeps the colour down to that black arc;
    # its points are the outline's own, so the seam is the line the art draws
    # rather than a chord across the fist's shoulder.  The fist stays as drawn,
    # which is grey: its white fill carries a 50 % shade, so the cut copy reads
    # 204/179 like the SWF's own render.  Colouring it (`HANDS` dropped) paints
    # the whole fist `(255, 204, 0)`, and dropping the cut is not what the chip
    # should look like.
    73: "poly -76.25,78.1 -74.85,72.15 -71.45,68.1 -67.65,63.5 -61.3,61.25 "
        "-51.2,61.55 -47.5,63.35 -44.6,65.55 -42.9,67.3 -39.85,71.35 -37.5,75.95 "
        "-36.8,78.1 -32,100.65 -91.65,100.65 -91.65,84",
}

# The hand copy's own colour, for chips whose fist is drawn in the fill clip's
# white.  White is the fill clip's colour, not the hand's: untinted it sat under
# a coloured sleeve as a bright blob, so 73's hand is drawn in the grey the rest
# of the chip is shaded with -- #CCCCCC body, 179 under its 50 % shade and 102
# on its creases, which is what the SWF shows there.
HAND_FILL = {
    73: "#cccccc",
}
# Chips whose grey crease and edge lines are drawn inside the fill clip in the
# SWF, so `paint()` multiplies them: Ruffle shows a darker shade of the colour
# where FFDec's export has a flat grey line lying on top of it.  See
# `split_fill_layers.grey_stroke`.
TINT_STROKES = {72, 73, 74}
BLOCK = re.compile(r"(?ms)^--- !u!(\d+) &(-?\d+)\n.*?(?=^--- !u!|\Z)")


def chip_dir(chip):
    return os.path.join(ROOT, "Assets", "Chips", "0001-0100", "Chip_%04d" % chip)


def meta_guid(path):
    for line in open(path, encoding="utf-8"):
        if line.startswith("guid: "):
            return line.split()[1]
    raise SystemExit("no guid in " + path)


def sprite_meta(source_meta, name):
    """The original's import settings, with a new identity."""
    text = open(source_meta, encoding="utf-8").read()
    text = re.sub(r"(?m)^guid: [0-9a-f]{32}$", "guid: " + uuid.uuid4().hex, text)
    text = re.sub(r"(?m)^(\s*)SpriteName: .*$",
                  lambda m: "%sSpriteName: %sSprite" % (m.group(1), name), text)
    text = re.sub(r"(?m)^(\s*)SpriteID: [0-9a-f]{32}$",
                  lambda m: m.group(1) + "SpriteID: " + uuid.uuid4().hex, text)
    return text


def parse(text):
    """[(kind, id, block text)] in file order."""
    return [(int(m.group(1)), int(m.group(2)), m.group(0)) for m in BLOCK.finditer(text)]


def find(blocks, kind, predicate):
    for entry in blocks:
        if entry[0] == kind and predicate(entry[2]):
            return entry
    return None


def set_field(text, field, value):
    return re.sub(r"(?m)^(\s*%s: ).*$" % re.escape(field),
                  lambda m: m.group(1) + value, text, count=1)


def strip_layers(text):
    """Remove the layer children a previous run added, keeping one renderer.

    A re-split can need fewer layers than last time.  The patch below only
    renames and clones, so anything left over would stay in the prefab as a
    renderer with no sprite (the play check reports it as a `sprite -` row).
    The lowest sorting order is kept as the base renderer to clone from, which
    covers both a fresh prefab (its own renderer) and a re-split one (layer 0).
    """
    blocks = parse(text)
    root = find(blocks, 4, lambda b: "m_Father: {fileID: 0}" in b)
    layer = re.compile(r"_L\d+$")
    found = []
    for kind, ident, body in blocks:
        if kind != 1:
            continue
        name = re.search(r"m_Name: (.*)", body).group(1)
        if not layer.search(name):
            continue
        components = [int(i) for i in re.findall(r"component: \{fileID: (\d+)\}", body)]
        transform = [i for i in components if find(blocks, 4, lambda b, i=i: "&%d\n" % i in b)]
        renderer = [i for i in components if find(blocks, 212, lambda b, i=i: "&%d\n" % i in b)]
        if not transform or not renderer:
            continue
        renderer_body = find(blocks, 212, lambda b, i=renderer[0]: "&%d\n" % i in b)[2]
        order = int(re.search(r"m_SortingOrder: (-?\d+)", renderer_body).group(1))
        found.append((order, ident, transform[0], renderer[0]))
    if not found:
        return text
    found.sort()
    # keep the lowest sorting order, the base to clone from; drop the rest,
    # which includes the orphans a previous, longer split left behind
    for order, game_object_id, transform_id, renderer_id in found[1:]:
        for kind, ident in ((4, transform_id), (1, game_object_id), (212, renderer_id)):
            block = find(blocks, kind, lambda b, i=ident: "&%d\n" % i in b)
            text = text.replace(block[2], "")
    kept = [found[0][2]]
    listing = "".join("%s- {fileID: %d}\n" % (re.search(r"(?m)^(\s*)m_Children:", root[2]).group(1), i)
                      for i in kept)
    root_text = re.sub(r"(?ms)^(\s*m_Children:\n)(?:\s*- \{fileID: -?\d+\}\n)*",
                       lambda m: m.group(1) + listing, root[2], count=1)
    text = text.replace(root[2], root_text)
    return text


def drop_empty_headers(text):
    """Delete `--- !u!N &id` lines with no body under them.

    A header with nothing after it truncates Unity's load at that point: chip
    74 reported one renderer of five and drew only the root sprite.  Every
    colour-layer chip carried a run of them at the end of its old renderers,
    and `check_prefab` does not see this variant -- it looks for headers that
    lost their `--- !u!`, not headers whose body is empty.
    """
    while True:
        trimmed = re.sub(r"(?m)^--- !u!\d+ &-?\d+\n(?=--- !u!|\Z)", "", text)
        if trimmed == text:
            return text
        text = trimmed


def patch_prefab(prefab, layers, dry_run):
    """layers: [(name, sprite guid, is_fill)] in draw order."""
    text = drop_empty_headers(strip_layers(open(prefab, encoding="utf-8").read()))
    blocks = parse(text)

    renderer = find(blocks, 212, lambda b: True)
    if renderer is None:
        raise SystemExit("%s: no SpriteRenderer" % prefab)
    game_object_id = int(re.search(r"m_GameObject: \{fileID: (\d+)\}", renderer[2]).group(1))
    game_object = find(blocks, 1, lambda b: "&%d\n" % game_object_id in b)
    component_ids = [int(i) for i in
                     re.findall(r"component: \{fileID: (\d+)\}", game_object[2])]
    transform_id = [i for i in component_ids if find(blocks, 4, lambda b: "&%d\n" % i in b)][0]
    transform = find(blocks, 4, lambda b: "&%d\n" % transform_id in b)
    root_transform = find(blocks, 4, lambda b: "m_Father: {fileID: 0}" in b)
    if root_transform is None:
        raise SystemExit("%s: no root transform" % prefab)

    base_order = int(re.search(r"m_SortingOrder: (-?\d+)", renderer[2]).group(1))
    next_id = max(i for _, i, _ in blocks) + 1
    order_of = {}

    # reuse the existing renderer for the first layer, clone it for the others
    first_name, first_guid, _ = layers[0]
    renderer_text = set_field(renderer[2], "m_Sprite",
                              "{fileID: %d, guid: %s, type: 3}" % (SPRITE_FILE_ID, first_guid))
    renderer_text = set_field(renderer_text, "m_SortingOrder", str(base_order))
    text = text.replace(renderer[2], renderer_text)

    game_object_text = set_field(game_object[2], "m_Name", first_name)
    text = text.replace(game_object[2], game_object_text)

    transform = find(parse(text), 4, lambda b: "&%d\n" % transform_id in b)
    order_of[first_name] = base_order
    new_transforms = []
    renderer_ids = {first_name: renderer[1]}

    for index, (name, guid, _) in enumerate(layers[1:], start=1):
        go_id, tr_id, sr_id = next_id, next_id + 1, next_id + 2
        next_id += 3
        order_of[name] = base_order + index
        new_transforms.append(tr_id)
        renderer_ids[name] = sr_id

        cloned_renderer = renderer[2].replace("&%d\n" % renderer[1], "&%d\n" % sr_id)
        cloned_renderer = cloned_renderer.replace("m_GameObject: {fileID: %d}" % game_object_id,
                                                  "m_GameObject: {fileID: %d}" % go_id)
        cloned_renderer = set_field(cloned_renderer, "m_Sprite",
                                    "{fileID: %d, guid: %s, type: 3}" % (SPRITE_FILE_ID, guid))
        cloned_renderer = set_field(cloned_renderer, "m_SortingOrder", str(base_order + index))

        cloned_go = game_object[2].replace("&%d\n" % game_object_id, "&%d\n" % go_id)
        cloned_go = re.sub(r"\{fileID: %d\}" % renderer[1], "{fileID: %d}" % sr_id, cloned_go)
        cloned_go = re.sub(r"\{fileID: %d\}" % transform_id, "{fileID: %d}" % tr_id, cloned_go)
        cloned_go = set_field(cloned_go, "m_Name", name)

        cloned_transform = transform[2].replace("&%d\n" % transform_id, "&%d\n" % tr_id)
        cloned_transform = cloned_transform.replace("m_GameObject: {fileID: %d}" % game_object_id,
                                                    "m_GameObject: {fileID: %d}" % go_id)

        text = text.rstrip("\n") + "\n" + cloned_go.rstrip("\n") + "\n" \
            + cloned_transform.rstrip("\n") + "\n" + cloned_renderer.rstrip("\n") + "\n"

    children = [transform_id] + new_transforms
    root = find(parse(text), 4, lambda b: "&%d\n" % root_transform[1] in b)
    indent = re.search(r"(?m)^(\s*)m_Children:", root[2]).group(1)
    listing = "".join("%s- {fileID: %d}\n" % (indent, i) for i in children)
    root_text = re.sub(r"(?ms)^(\s*m_Children:\n)(?:\s*- \{fileID: -?\d+\}\n)*",
                       lambda m: m.group(1) + listing, root[2], count=1)
    text = text.replace(root[2], root_text)

    # the tinted renderers: every layer the colour reaches -- the fills Flash
    # paints flat, plus the runs of shading that follow the colour
    tinted_ids = [renderer_ids[name] for name, _, is_tint in layers if is_tint]
    effect = find(parse(text), 114, lambda b: "coloredRenderers:" in b)
    if effect is None:
        raise SystemExit("%s: no ChipEffect" % prefab)
    ids = tinted_ids
    field = re.search(r"(?m)^([ \t]*)coloredRenderers:[^\n]*\n(?:[ \t]*- \{fileID: -?\d+\}\n)*",
                      effect[2])
    indent = field.group(1)
    # the whole old list goes: replacing only the field line leaves the entries
    # that were under it, i.e. a list longer than the layers the run produced
    listing = ("%scoloredRenderers: []\n" % indent if not ids else
               "%scoloredRenderers:\n" % indent + "".join(
                   "%s- {fileID: %d}\n" % (indent, i) for i in ids))
    effect_text = effect[2][:field.start()] + listing + effect[2][field.end():]
    text = text.replace(effect[2], effect_text)

    if dry_run:
        print(text)
        return
    check_prefab(text, prefab)
    open(prefab, "w", encoding="utf-8").write(text)
    print("patched", os.path.relpath(prefab, ROOT),
          "orders", order_of, "tinted", ids)


def check_prefab(text, prefab):
    """Refuse to write a prefab Unity cannot load or whose sprites are gone.

    A re-split rewrites the `_L*` SVGs with fresh guids, so a patch built from
    an older listing leaves renderers pointing at assets that no longer exist:
    the file still looks fine and Unity still loads the components, but every
    renderer has a null sprite and the chip draws nothing (`ChipPlayCheck
    --chip N` then reports `sprites 0`).  The same art is lost, silently, if a
    writer drops the `%YAML` preamble or the `--- !u!` header prefixes.
    """
    if not text.startswith("%YAML 1.1\n%TAG !u! tag:unity3d.com,2011:\n"):
        raise SystemExit("%s: YAML preamble missing" % prefab)
    if re.search(r"(?m)^--- !u!\d+ &-?\d+\n(?=--- !u!|\Z)", text):
        raise SystemExit("%s: empty block header" % prefab)
    if re.search(r"(?m)^\d+ &-?\d+$", text):
        raise SystemExit("%s: blocks are missing their `--- !u!` headers" % prefab)
    folder = os.path.join(os.path.dirname(prefab), "Sprites")
    known = {meta_guid(p) for p in glob.glob(os.path.join(folder, "*.svg.meta"))}
    missing = [g for g in re.findall(r"m_Sprite: \{fileID: \d+, guid: ([0-9a-f]{32})", text)
               if g not in known]
    if missing:
        raise SystemExit("%s: sprites that do not exist: %s" % (prefab, ", ".join(missing)))
    # a tint list that names anything but this prefab's renderers is a list that
    # grew instead of being replaced; Unity just reports the extras as missing
    renderers = {int(i) for i in re.findall(r"(?m)^--- !u!212 &(\d+)", text)}
    tint = re.search(r"(?m)^[ \t]*coloredRenderers:[^\n]*\n((?:[ \t]*- \{fileID: -?\d+\}\n)*)", text)
    stale = [i for i in (re.findall(r"fileID: (-?\d+)", tint.group(1)) if tint else [])
             if int(i) not in renderers]
    if stale:
        raise SystemExit("%s: tint list names non-renderers: %s" % (prefab, ", ".join(stale)))


def do_chip(chip, targets, dry_run):
    folder = chip_dir(chip)
    svg = os.path.join(folder, "Sprites", "chip_%04d_effect.svg" % chip)
    prefab = os.path.join(folder, "Chip_%04d_Effect.prefab" % chip)
    if not os.path.exists(svg):
        print("chip %3d: no single effect drawing, skipped" % chip)
        return False

    # a re-split can need fewer layers than last time, and a stale `_L*.svg`
    # would still import and still hold art, so drop them first
    for old in glob.glob(svg[:-4] + "_L*.svg*"):
        os.remove(old)
    runs, manifest_path = splitter.split(svg, [t["group"] for t in targets], svg[:-4],
                                        os.path.join(ROOT, "Logs", "color-layers"),
                                        hand=HANDS.get(chip),
                                        tint_strokes=chip in TINT_STROKES,
                                        hand_fill=HAND_FILL.get(chip))
    layers = []
    for entry in runs:
        path = entry["path"]
        name = os.path.basename(path)[:-4]
        meta = path + ".meta"
        if not os.path.exists(meta):
            open(meta, "w", encoding="utf-8").write(sprite_meta(svg + ".meta", name))
        layers.append((name, meta_guid(meta), entry["tint"]))
    print("chip %3d: layers %s" % (chip, ", ".join(
        (n + ("[fill]" if f else "")) for n, _, f in layers)))
    patch_prefab(prefab, layers, dry_run)
    return True


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("chips", nargs="*", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", default=os.path.join(ROOT, "Logs", "color-targets.json"))
    args = parser.parse_args(argv)

    targets = {t["chip"]: t for t in json.load(open(args.json))}
    chips = args.chips or sorted(t["chip"] for t in targets.values() if t["targets"])
    done = 0
    for chip in chips:
        entry = targets.get(chip)
        if entry is None or not entry["targets"]:
            print("chip %3d: nothing to colour" % chip)
            continue
        done += do_chip(chip, entry["targets"], args.dry_run)
    print("%d chips patched" % done)


if __name__ == "__main__":
    main(sys.argv[1:])
