# Z mouse → Endgame trackball — shortcut migration ranking sheet

Fill **Rank** (1 = most important / most-accessible spot) and **Keep** (✓/✗).
Side profiles (Side / Side T / Side E) are excluded per request.

Legend for **Scope**:
- `Universal` = same on all layouts (send as-is)
- `Layout` = needs per-layout key translation on the trackball (like copy/paste) — keys shown as `Desktop → Term/Neu`
- `App` = app/AHK/launcher-specific chord; only you know what it does (label it)

Legend for **On TB?** (already in the current trackball keymap): Yes / No / Partial

---

## Editing
| Rank | Keep | Action | Keys | Z button | Scope | On TB? |
|---|---|---|---|---|---|---|
|  |  | Copy | Ctrl+Insert | Fingertip L (release) | Universal | Yes |
|  |  | Paste | Shift+Insert | Fingertip R (release) | Universal | Yes |
|  |  | Cut | Ctrl+X | L-trigger pull | Layout (Desktop was Ctrl+B/Bold) | Yes |
|  |  | Undo | Ctrl+Z | Right click (deep press) | Layout (Desktop was Ctrl+/ ) | Yes |
|  |  | Reload | Ctrl+R | Right click | Layout (Desktop was Ctrl+O/Open) | No |

## Tabs & windows
| Rank | Keep | Action | Keys | Z button | Scope | On TB? |
|---|---|---|---|---|---|---|
|  |  | Switch window | Alt+Tab | L-trigger push | Universal | No |
|  |  | Next tab | Ctrl+Tab | R-trigger push | Universal | Yes (encoder) |
|  |  | Prev tab | Ctrl+Shift+Tab / Ctrl+PgUp | Tilt left | Universal | Yes (encoder) |
|  |  | Next tab (alt) | Ctrl+PgDn | Tilt right | Universal | No |
|  |  | Back-tab | Shift+Tab | Tilt left | Universal | No |
|  |  | Tab | Tab | Tilt right / Right click | Universal | Partial |
|  |  | Reopen closed tab | Ctrl+Shift+T | Thumb Top | Layout (Desktop was Ctrl+Shift+K) | No |
|  |  | Switch keyboard layout/profile | (profile jump) | Thumb Top | n/a → maps to `bst_tog` | Yes |

## Navigation & text
| Rank | Keep | Action | Keys | Z button | Scope | On TB? |
|---|---|---|---|---|---|---|
|  |  | Escape | Esc | Fingertip L | Universal | Yes |
|  |  | Enter | Enter | Fingertip R | Universal | Yes |
|  |  | Backspace | Backspace | Left click | Universal | No |
|  |  | Delete | Del | L-trigger push | Universal | No |
|  |  | Space | Space | Middle click | Universal | No |
|  |  | Forward (browser) | Alt+Right | Thumb Bottom | Universal | No |
|  |  | Rename | F2 | R-trigger push | Universal | No |
|  |  | Screenshot | PrtSc | Right click (release) | Universal | No |

## Media
| Rank | Keep | Action | Keys | Z button | Scope | On TB? |
|---|---|---|---|---|---|---|
|  |  | Volume + | Vol Up | Scroll up | Universal | Yes |
|  |  | Volume − | Vol Down | Scroll down | Universal | Yes |
|  |  | Mute | Mute | Middle click | Universal | No |
|  |  | Play / Pause | Play/Pause | Edge Rear | Universal | No |
|  |  | Next track | Next | R-trigger push | Universal | No |
|  |  | Prev track | Prev | L-trigger push | Universal | No |

## Pointer / scroll
| Rank | Keep | Action | Keys | Z button | Scope | On TB? |
|---|---|---|---|---|---|---|
|  |  | Precision scroll (Ctrl held while scrolling) | Ctrl + wheel | Scroll up/down | Universal | Partial (scroll layer) |
|  |  | Left-click + Shift held | Shift + click | Left click | Universal | No |

## App / custom chords — identify or drop
_These resolved to app-specific chords; label what each does (or mark ✗)._
| Rank | Keep | Resolved keys | Z button | What it does (fill in) |
|---|---|---|---|---|
|  |  | Ctrl+Shift+9 (Term/Neu) / Ctrl+Shift+5 (Desktop) | Left click | |
|  |  | Shift+Alt+7 (Term/Neu) / Shift+Alt+1 (Desktop) | Edge Front | |
|  |  | Gui+F13 | Fingertip R | |
|  |  | Shift+Alt+1 / +3 / +4 / +5 | Fingertip R | |
|  |  | Shift+1 (Term) / Alt+1 (Neu) | Fingertip R | |
|  |  | Ctrl + macro `D V Enter` (Term) / `T V Enter` (Neu) / `K . Enter` (Desktop) | Fingertip R | |
|  |  | Ctrl+Alt + macro `V F Enter` | Fingertip R | |
|  |  | Ctrl+Alt + macro `V V E Enter` | Edge Front / Left click | |
|  |  | Ctrl+Alt + macro `. Y Enter` (Desktop) | Fingertip R | |
|  |  | Ctrl + macro `0 1` (Term/Neu) / `7 4` (Desktop) | Middle click | |
|  |  | (Shift / Alt / Shift+Alt) + `6 Down Enter` (or `0 Down Enter`) | Fingertip L | |
|  |  | Ctrl held (modifier only) | Thumb Bottom (Desktop) | |

---

### Notes
- The trackball has ~8 buttons across 6 layers + 2 encoders, so this list needs pruning to fit; rank the top ones for the most accessible spots (base-layer buttons, encoder turns).
- `Layout`-scoped rows need the same per-layout key translation we already use for copy/paste (Terminator vs Neu). `Universal` rows can be bound directly.
- Copy/Paste on the Z use `Ctrl+Insert` / `Shift+Insert`, which are **layout-independent** — if you like, we can switch the trackball's copy/paste to those and delete the per-layout `V`/`/`/`X` handling entirely.
