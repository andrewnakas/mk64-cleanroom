# Mario Kart 64 — clean room web build

Play: **https://andrewnakas.github.io/mk64-cleanroom/**

Mario Kart 64 built from the [n64decomp/mk64](https://github.com/n64decomp/mk64) decompilation into an N64 ROM in which
**every asset the decomp extracts from a ROM is regenerated**. It runs in the browser in
[EmulatorJS](https://github.com/EmulatorJS/EmulatorJS) (libretro mupen64plus-next). No original ROM is needed to play.

Keys: **Arrows** steer · **X** A (gas) · **C** B (brake) · **Z** Z (item) · **S** R (hop/drift) · **Q** L · **Enter** Start ·
**I J K L** C-buttons. Gamepads work too.

## What is kept, what is generated

The decomp is C code. Its extractors (torch + `extract_assets.py`) pull the remaining assets from a ROM. This project
reads the ROM **once, in a "dirty room" step** (`games/mk64/extract_spec.py`), keeps only coarse facts
(`games/mk64/spec`), and builds every asset from them.

| Asset | Kept fact | Generated |
|---|---|---|
| Textures (≈13.5k slots incl. palettes) | format, size, 4×4 colour grid, 2-bit alpha outline | colour from the grid, checker-dithered |
| Kart sprites (8 drivers × 321 frames) | frame roles from the game's tables, alpha-outline bounding box | rendered from our own primitive 3D models of each driver and kart (`kartrender.py`), toon-shaded; wheel pixels use the build's wheel palettes so the tread turns |
| Character-select portraits (8 × 17) | — | the same models, head and shoulders, with a thumbs-up and a turn-away frame |
| Title backgrounds, title logo | — | illustrations composed from our renders (`illustrations.py`), logo drawn (`drawn.py`) |
| Text in textures: menus, course names, cups, Controller Pak messages, signs, HUD | the words (from symbol names / the game) | re-typeset with open fonts (Luckiest Guy, Lilita One, Rubik, M PLUS Rounded 1c) — `tex_labels.json`, `labels.py` |
| Fonts (the game's kana + italic Latin sets) | which character each cell holds (from names and order) | drawn with open fonts |
| Item icons, portraits, 1P–4P emblems, place graphics, digits, traffic lights, Boo | — | drawn from our own descriptions (`icons.py`) |
| Instrument and sound-effect samples (202) | length, rate, loop points, coarse spectral outline | resynthesised; our own 2-predictor VADPCM codebooks |
| Voices (57 lines) | the words, speaker, slot length | placeholder TTS (Piper) character voices — to be replaced by the author's own recordings |
| Music | note sequences (m64) | played by the resynthesised instruments |
| Menu texture compression (TKMK00) | — | our own encoder (`tkmk00.py`, written from the decomp's decoder) |

Kept as code, not regenerated: the decomp's C and geometry/data, the RSP microcode and the IPL3 boot code (extracted
from your own ROM when building; not in this repository).

MK64 does not survive moved data, so the ROM layout is kept byte-for-byte: every compressed asset is padded to the size
the game's own asset had (`pad_layout.py`), and textures that come out bigger are simplified until they fit.

`games/mk64/taint_report.py` scans every generated texture and sample against the retail extraction for shared byte
runs of 32 bytes or more.

## Build (Windows, Git Bash)

Needs Python 3 (numpy, scipy, Pillow, PyYAML, py7zr), GNU make, the decomp's tools, libdragon's mips64-elf binutils,
and a way to build torch (MSVC). See `tools/mk64env.sh` and `games/mk64/build_clean.sh`.

```sh
# dirty room, once (your own ROM; nothing from it is published):
git clone --recursive -c core.autocrlf=false https://github.com/n64decomp/mk64 dirty && cp baserom.us.z64 dirty/
(cd dirty && make assets && make -j4 COMPARE=1 CC_CHECK=true)          # must match the retail sha1
python -m games.mk64.extract_spec pristine dirty games/mk64/spec     # coarse facts only
python -m games.mk64.pad_layout record dirty                         # blob sizes
# clean room:
games/mk64/build_clean.sh --fresh                                    # clean ROM
python ports/ejs/make_site.py clean/build/us/mk64.us.z64 <emulatorjs> site
python ports/ejs/patch_core.py site/mk64.z64 site/data/cores site/data/cores   # emulator settings for our ROM
```

The emulator identifies ROMs by MD5 to pick settings (MK64 needs a 4 KB EEPROM); `patch_core.py` points the core's
MK64 settings entry at our ROM.

## Legal note

This repository contains no ROM data other than the kept facts described above. All textures, sprites, fonts, icons,
samples and voices are generated. The game code is the community decompilation. Mario Kart 64 is a trademark of
Nintendo; this project is not affiliated with Nintendo. EmulatorJS is GPL-3.0 and mupen64plus-next GPL-2.0
(see `THIRD_PARTY.md` on the site).
