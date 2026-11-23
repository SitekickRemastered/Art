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

# Chips whose art puts the hand inside the same fill clip as the forearm, so
# the whole arm would take the colour.  The value keeps that side of the line as
# drawn (see `split_fill_layers.clip_rect`); chip 74 needs no cut because its
# boots are opaque pieces outside the fill.
HANDS = {72: "x>87", 73: "slope -0.409,32.4"}
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


def patch_prefab(prefab, layers, dry_run):
    """layers: [(name, sprite guid, is_fill)] in draw order."""
    text = open(prefab, encoding="utf-8").read()
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

    def tinted(match):
        if not ids:
            return match.group(1) + "coloredRenderers: []"
        return match.group(1) + "coloredRenderers:" + "".join(
            "\n%s- {fileID: %d}" % (match.group(1), i) for i in ids)

    effect_text = re.sub(r"(?m)^(\s*)coloredRenderers:.*$", tinted, effect[2], count=1)
    text = text.replace(effect[2], effect_text)

    if dry_run:
        print(text)
        return
    open(prefab, "w", encoding="utf-8").write(text)
    print("patched", os.path.relpath(prefab, ROOT),
          "orders", order_of, "tinted", ids)


def do_chip(chip, targets, dry_run):
    folder = chip_dir(chip)
    svg = os.path.join(folder, "Sprites", "chip_%04d_effect.svg" % chip)
    prefab = os.path.join(folder, "Chip_%04d_Effect.prefab" % chip)
    if not os.path.exists(svg):
        print("chip %3d: no single effect drawing, skipped" % chip)
        return False

    runs, manifest_path = splitter.split(svg, [t["group"] for t in targets], svg[:-4],
                                        os.path.join(ROOT, "Logs", "color-layers"),
                                        hand=HANDS.get(chip))
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
