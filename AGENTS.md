# Agent instructions

## Cursor Cloud specific instructions

### Keymap diagram walkthroughs

After any keymap or diagram change (`config/*.keymap`, `config/*.dtsi`, `keymap_drawer.config.yaml`, `keymap-drawer/*`), always show the **fresh full** keymap diagram in the final response — not only close-ups.

1. Regenerate with the draw pipeline (parse → draw → `postprocess_svg.py` → `rsvg-convert` PDF) when sources changed.
2. Render previews via `python3 keymap-drawer/render_previews.py` (writes `/opt/cursor/artifacts/keymap-full-*.png`).
3. Include the latest full PNG inline in the reply, e.g. `<img src="/opt/cursor/artifacts/keymap-full-….png" alt="Full updated keymap diagram" />`.
4. Close-ups are fine as extras; never substitute them for the full diagram.
5. Keep `keymap-drawer/keymap.png` in sync for the GitHub README landing image (same draw pipeline; `rsvg-convert -f png -w 1400`).
