### Firmware for PAW3395 

[Download latest UF2](https://nightly.link/phuertay/endgame-trackball-config/workflows/build/paw3395/firmware.zip)

The `firmware.zip` contains two files:
- `efogtech_trackball_0-zmk.uf2` — the normal firmware.
- `efogtech_trackball_0-settings-reset.uf2` — flash this once to wipe the settings/keymap saved on the device (ZMK Studio persists the keymap to on-device storage, which otherwise shadows keymap changes shipped in new firmware), then flash the normal firmware.

