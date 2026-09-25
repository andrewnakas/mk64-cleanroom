#!/bin/sh
# Clean ROM from the spec, with the game's ROM layout kept exactly (MK64 does not survive shifted data):
#   generate -> build -> patch hardcoded sizes -> pad every compressed blob to its slot size
#   -> (blobs too big: simplify their textures, regenerate, repeat) -> final build -> checks
#   games/mk64/build_clean.sh [--fresh]
set -e
HERE="$(cd "$(dirname "$0")/../.." && pwd)"
. "$HERE/tools/mk64env.sh"
cd "$HERE"
C="$MK64W/clean"
MK="make -j4 COMPARE=0 NOEXTRACT=1 CC_CHECK=true"
# objects whose C #includes regenerated .inc.c textures (no .d files with CC_CHECK=true)
# the ELF's compressed-segment objects are not always remade by the default goal: name them
SEGS="$(cd "$C" && for d in startup_logo ceremony_data common_data; do printf 'build/us/assets/code/%s/%s.mio0.o ' $d $d; done; for c in courses/*/; do c=${c%/}; [ -f "$c/course_data.c" ] && printf 'build/us/%s/course_data.mio0.o build/us/%s/course_geography.mio0.o ' $c $c; done)"
build() { [ "$1" = keep ] || rm -rf "$C/build/us/assets/code" "$C"/build/us/courses/*/course_data.o "$C"/build/us/src/data/*.o; (cd "$C" && $MK $SEGS >> ../build_clean.log 2>&1 && $MK >> ../build_clean.log 2>&1) || { grep -a "\*\*\*\|rror" "$MK64W/build_clean.log" | tail -n 8; exit 1; }; }
: > "$MK64W/build_clean.log"
if [ "$1" = "--fresh" ]; then rm -f "$C/shrink.json"; python -m games.mk64.generate "$MK64W/pristine_src" "$C" 2>&1 | grep -v "WARN CI" | tail -n 6
else python -m games.mk64.generate "$MK64W/pristine_src" "$C" --only tex 2>&1 | grep -v "WARN CI" | tail -n 6; fi
python -m games.mk64.tree_patches "$C"
for round in 1 2 3 4 5; do
  build
  python -m games.mk64.fix_sizes "$C"
  if python -m games.mk64.pad_layout pad "$C"; then break; fi
  python -m games.mk64.pad_layout shrink "$C"
  python -m games.mk64.generate "$MK64W/pristine_src" "$C" --only tex 2>&1 | grep -v "WARN CI" | tail -n 2
done
python -m games.mk64.pad_layout pad "$C" || echo "WARNING: blobs still too big (layout shifted)"
build keep
python -m games.mk64.pad_layout pad "$C" > /dev/null || true
build keep
python -m games.mk64.check_limits "$C" || true
cp "$C/build/us/mk64.us.z64" "$MK64W/devsite/clean.z64"
python ports/ejs/patch_core.py "$MK64W/devsite/clean.z64" "$MK64W/emu/cores_orig" "$MK64W/devsite/data/cores"
sha1sum "$C/build/us/mk64.us.z64"
