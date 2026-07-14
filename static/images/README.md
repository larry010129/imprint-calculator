# Product style images

Drop photos here using `{color}/{category}-{style}.png`. The calculator and admin previews load them automatically — no code changes needed (see `resolve_style_image_url()` in `diamond_calculator/filters.py` and `imageUrl()` in `static/js/script.js`, which must stay in sync).

## Color folders
`white/`, `yellow/`, `rose/` — matches the K-gold color a customer picks (9K/Pt950/925 always resolve to `white`; chain style A/B/C default to white/rose/yellow respectively when no color is set).

## Required filenames per color folder (15 slots)
| Category | Files |
|---|---|
| pendant | `pendant-A.png`, `pendant-B.png`, `pendant-C.png` |
| ring | `ring-A.png`, `ring-B.png`, `ring-C.png` |
| earring | `earring-A.png` (styles B/C not offered) |
| bracelet | `bracelet-A.png`, `bracelet-B.png`, `bracelet-C.png` |
| chain | `chain-A.png`, `chain-B.png`, `chain-C.png` |

There are also flat, colorless `.jpg` fallbacks directly in this folder (`pendant-A.jpg`, `ring-A.jpg`, etc.) used elsewhere as a generic preview; keep both in sync when replacing a product photo.

## Do not use
- The root-level `image/` folder — source/archive photos with Chinese filenames, not served by Flask.
- Old carat-based names like `0.1-A.jpg` — obsolete after the multi-category expansion.
