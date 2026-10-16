#!/usr/bin/env python3
"""Post-parse keymap YAML: combo labels, sentence-case names, layer order."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

# Approximate complexity order; first six = letter page 1, rest = page 2.
LAYER_ORDER = [
    "default",
    "edit",
    "media",
    "excel",
    "system",
    "scroll lock",
    "scroll",
    "snipe",
    "alt+tab",
]

PAGE1_LAYERS = LAYER_ORDER[:6]
PAGE2_LAYERS = LAYER_ORDER[6:]

COMBO_LABELS = {
    frozenset({0, 1}): {"t": "excel", "h": "tog"},
    frozenset({6, 7}): {"t": "snipe", "h": "tog"},
    frozenset({1, 3}): {"t": "alt+tab", "h": "hold"},
}


def prepare(data: dict) -> dict:
    for combo in data.get("combos") or []:
        combo["d"] = False
        positions = frozenset(combo.get("p") or [])
        label = COMBO_LABELS.get(positions, {"t": "combo", "h": "tog"})
        combo["k"] = dict(label)
        # Parse keeps display-name case; layers dict is lowercased below.
        if combo.get("l"):
            combo["l"] = [name.lower() for name in combo["l"]]

    # Sentence-case layer titles on the diagram (not ALL CAPS).
    layers = {name.lower(): keys for name, keys in data["layers"].items()}
    ordered = {name: layers[name] for name in LAYER_ORDER if name in layers}
    for name, keys in layers.items():
        if name not in ordered:
            ordered[name] = keys
    data["layers"] = ordered
    return data


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "keymap-drawer/keymap.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    prepare(data)
    path.write_text(
        yaml.dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print("layers:", ", ".join(data["layers"]))


if __name__ == "__main__":
    main()
