#!/bin/sh
# Publish: the repo's tracked files -> andrewnakas/mk64-cleanroom (main), the site -> gh-pages.
# Never publishes spec_local (microcode, IPL3 glyphs), dev ROMs, dirty trees or practice clips.
#   tools/publish.sh "<commit message>"
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
W=/c/Users/andre/n64work/mk64
EXP=$W/export_repo
SITE=$W/site
FRESH=0; [ "$1" = "--fresh" ] && { FRESH=1; shift; }
SRC_ONLY=0; [ "$1" = "--source-only" ] && { SRC_ONLY=1; shift; }
MSG="${1:-Update}"
REPO=andrewnakas/mk64-cleanroom
cd "$HERE"
# --- guard: nothing retail-shaped in the tracked tree
if git ls-files | grep -E "spec_local|\.z64$|\.n64$|\.v64$|practice_pack|bin/lib/PR" ; then echo "refusing: retail-shaped files tracked"; exit 1; fi
# --- source repo
mkdir -p "$EXP"
[ $FRESH = 1 ] && rm -rf "$EXP/.git"                 # rewrite public history (e.g. to drop a leaked file)
[ -d "$EXP/.git" ] || (cd "$EXP" && git init -q -b main)
NAME="$(git -C "$HERE" config user.name)"; MAIL="$(git -C "$HERE" config user.email)"
git -C "$EXP" config user.name "$NAME"; git -C "$EXP" config user.email "$MAIL"
find "$EXP" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
git archive HEAD | tar -x -C "$EXP"
cd "$EXP"
git add -A
git -c core.autocrlf=false commit -q -m "$MSG

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>" || echo "(no source changes)"
if ! gh repo view $REPO > /dev/null 2>&1; then
  gh repo create $REPO --public --description "Mario Kart 64 clean-room web build: the n64decomp/mk64 decomp with every ROM asset regenerated, playable in the browser" --source . --push
else
  git remote get-url origin > /dev/null 2>&1 || git remote add origin https://github.com/$REPO.git
  if [ $FRESH = 1 ]; then git push -q -f origin main; else git push -q origin main; fi
fi
[ $SRC_ONLY = 1 ] && { echo "published source only"; exit 0; }
# --- site
python "$HERE/ports/ejs/make_site.py" $W/clean/build/us/mk64.us.z64 $W/emu/ejs "$SITE"
python "$HERE/ports/ejs/patch_core.py" "$SITE/mk64.z64" $W/emu/cores_orig "$SITE/data/cores"
cd "$SITE"
[ -d .git ] || (git init -q -b gh-pages && git remote add origin https://github.com/$REPO.git)
git config user.name "$NAME"; git config user.email "$MAIL"; git config core.autocrlf false
git add -A
git commit -q -m "Site: $MSG" || echo "(no site changes)"
git push -q -f origin gh-pages
gh api -X POST repos/$REPO/pages -f "source[branch]=gh-pages" -f "source[path]=/" > /dev/null 2>&1 || true
echo "published: https://github.com/$REPO  site: https://andrewnakas.github.io/mk64-cleanroom/"
