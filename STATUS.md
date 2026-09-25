# Mario Kart 64 clean room: status

**Published 2026-09-25 ~09:00:** https://andrewnakas.github.io/mk64-cleanroom/ (repo https://github.com/andrewnakas/mk64-cleanroom)
- Verified natively (mupen64plus, scripted input): title -> game select -> player select -> map select -> Mushroom Cup race with HUD.
- Taint: 0 failing (13 449 textures + derived kart files + 202 samples). Code range identical to retail (layout kept).
- Not verified in a browser tonight: headless Edge/Chrome started freezing at the Nintendo logo even with the *retail* ROM after ~01:00 (GPU contention?). The first retail run at 00:35 worked. **Please try the page in a real browser first thing.** Chrome at 09:33 reported `WakeLock ... page is not visible` (the screen is locked, so rendering pauses), which likely explains the stalls.

## Decisions (log)
- 2026-09-25 00:10 ROM: the prompt's ROM path was a placeholder. I used `~/Downloads/Mario Kart 64 (USA).zip`, unpacked to `C:/Users/andre/n64work/mk64/pristine/`. SHA1 579c48e2… matches the decomp's `mk64.us.sha1`.
- Decomp: n64decomp/mk64 @ 58cfcb022, cloned LF-only to `C:/Users/andre/n64work/mk64/pristine_src`.
- **Web route = 3 (clean N64 ROM + WASM N64 emulator).**
  - Why: no MK64 PC port has an Emscripten target; SpaghettiKart (C++/LUS) is too heavy for tonight; the decomp matches and builds a ROM with its bundled IDO recomp.
  - Emulator: EmulatorJS 4.2.3 (GPL-3) + libretro mupen64plus_next (GPL-2), vendored into the site.
- **Emulator ROM database**: mupen64plus sets MK64's EEPROM 4 KB save type from an MD5-keyed database compiled into the core. Any modified ROM stalls at the logo without it (verified: the retail ROM with one byte changed hangs).
  - `ports/ejs/patch_core.py` points the DB's "Mario Kart 64 (U) (Super W00ting Hack)" entry (RefMD5 = the US game) at our ROM's MD5. It's a same-length byte replacement in the core wasm, redone per build.
- **ROM layout is kept exactly**: MK64 is not reliably shiftable (16 bytes of padding in retail data hangs at boot).
  - Every compressed blob (MIO0/TKMK00) is zero-padded to the game's own blob size (`games/mk64/pad_layout.py`; sizes in `spec/slot_sizes.json`).
  - Textures whose blob comes out bigger get simplified and rebuilt (shrink loop in `build_clean.sh`).
- Toolchain:
  - libdragon's mips64-elf binutils (Windows build) for as/ld; the decomp's IDO recomp for cc.
  - Build at `-j4` (`-j12` runs the Cygwin forks out of paging file). `CC_CHECK=true` skips the zig syntax check.
  - `games/mk64/tree_patches.py` holds the build-tool patches.
- **Kept facts beyond textures/samples** (please review):
  - RSP microcode binaries (`bin/lib/PR/*.bin`: F3DEX, F3DLX, aspMain). Code, not art; the emulator's HLE identifies them.
  - The 50 IPL3 font glyphs inside the boot code (ROM 0x40–0xFFF is covered by the CIC boot checksum).
  - Torch-generated geometry/data C: display lists, vertices, course metadata tables, CPU paths.
  - The ctl bank structure (envelopes, key ranges, tuning). Books and loop states are zeroed in the spec and regenerated.
- Menu textures in TKMK00: our own encoder (`games/mk64/tkmk00.py`, verified against the decomp's decoder on all 63 files).
- Hardcoded compressed sizes (MenuTexture tables, course texture tables) are patched from our blobs by `fix_sizes.py`.
- Fonts used for re-typesetting: Luckiest Guy (Apache-2.0), Lilita One / Press Start 2P / Rubik / M PLUS Rounded 1c (OFL), with licenses in `games/mk64/fonts`.

## What is generated how
- Kart sprites (8 drivers × 321 frames): rendered from our own primitive models (`kartrender.py`).
  - Pose per frame comes from the game's frame tables: 9 slope groups × 21 yaw steps, 5 pitch sets × 20 steps, 32 tumble frames.
  - Wheel pixels use the build's wheel palettes, so the tread animates.
- Character-select busts (8 × 17 frames): the same models, head and shoulders, with a thumbs-up and a turn-away frame.
- Title backgrounds: illustrations composed from our renders over painted scenes (`illustrations.py`). Title logo drawn (`drawn.title_logo`).
- Text: menu/course/cup/mode labels, Controller Pak messages, data-screen words, signs, HUD labels and digits, place graphics (1st–8th), the game's kana and italic Latin fonts. All re-typeset from names/order (`tex_labels.json`, `labels.py`, `drawn.py`, `icons.py`).
- Icons: item-window items, item box, bananas, rank portraits, 1P–4P emblems, minimap markers, traffic lights (`icons.py`).
- Everything else: kept 4×4 colour grid + 2-bit alpha outline, checker-dithered (no noise, so MIO0 fits).
- Audio: 202 tbl samples resynthesised from coarse outlines, with our own 2-predictor VADPCM books written into the kept ctl.

## Hard-won facts (08:30)
- Stale objects: flags aren't make dependencies, and with `CC_CHECK=true` there are no `.d` files, so C files that `#include` regenerated `.inc.c` never recompile.
  - `build_clean.sh` deletes those objects each round and names the compressed-segment objects explicitly (the default goal doesn't always remake them).
  - `pad_layout.py` deletes a padded blob's `.o`/`.s`, since those rules don't depend on the blob.
- Layout check: clean ROM vs retail must show 0 differing bytes in the code range 0x1000–0xD9B70.
- TKMK00 RLE channels: the game reads raw channel words with `lw`, so every channel stream must be 4-byte aligned. The C port reads bytes and hides this.
- Headless browser testing became unreliable overnight: even the retail ROM froze at the logo, probably GPU contention with other sessions.
  - Deterministic harness now: native mupen64plus 2.6.0 (`tools/m64p_test.py`) with our scripted-input plugin (`tools/m64p_script_input`).
  - `tools/race.script` drives title → 1P → Mario GP → 50cc → Mario → Mushroom Cup → race.

## Fixed 10:30
- 38 palette/podium `.inc.c` files had been kept verbatim (retail pixel data) and 179 PNG-derived `.inc.c` files were listed as kept. All are now generated or derived; the public repo was re-created as a single clean commit (history rewritten), and the site ROM was rebuilt.
- Rank portraits, rank numbers and the item window now render in races.

## Works
- Dirty tree round-trip: build == retail sha1.
- Headless testing: `ports/ejs/cdp_shot.py --gpu` (real GPU via ANGLE/D3D11, CDP key events + page screenshots). SwiftShader is too slow for this emulator.
- Taint scan (`games/mk64/taint_report.py`): 8 small failing runs on the first build (smooth gradients); dither added since. To re-run on the final build.

## Next
- Finish the layout-keeping build, boot → menus → race headless, then taint → publish.
- Course previews / minimap outlines from course geometry; Rainbow Road neon portraits; Lakitu signs.

## For the morning
- Open the site in Chrome/Edge and play a Mushroom Cup race; report anything broken.
- Voices: **one combined track** `~/Downloads/MK64_voice_practice/mk64_all_voices_call_and_response.wav` + `SCRIPT.txt` (all 57 lines, all characters, 5 min; asked for 10:15). Per-character tracks: `C:/Users/andre/n64work/mk64/practice_pack/` (57 clips, one call-and-response track per speaker, `SCRIPT.txt`). Record, then cut with `cleanroom.voice.takes` into `games/mk64/voices/<slot>.wav` and rebuild (`games/mk64/build_clean.sh` + `generate --only snd`).
- Look at: kart sprites / busts (our primitive models), title illustration and logo, menu labels.
- Review the kept facts listed above (microcode, IPL3 glyphs, geometry C).
- Voices: MK64 has few voice lines (character select names, "Mario Kart!" etc.). Placeholder/practice pack not built yet.
- Look at: the kart sprites and busts (our own primitive models), and the title screen.
