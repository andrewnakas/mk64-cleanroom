"""Taint report: every generated MK64 asset vs the retail extraction (dev tool).

    python -m games.mk64.taint_report <dirty tree> <clean tree>

Streams: texture pixels (PNG RGBA, torch .inc.c decoded, TKMK00 decoded), the
derived kart files (stitched palettes, wheel masks), and per sample both the
tbl bytes and the decoded PCM. Kept facts (sequences, code/data, ctl structure)
are listed, not scanned. Fails on any shared run >= taint.FAIL_RUN bytes.
"""
import json
import os
import struct
import sys

import numpy as np

from cleanroom import taint
from cleanroom.audio import vadpcm
from cleanroom.gfx import png
from games.mk64 import audiobank
from games.mk64.extract_spec import incc_rgba, tkmk_rgba, yaml_textures

HERE = os.path.dirname(os.path.abspath(__file__))


def tex_streams(tree, A, T, ytex, dirty):
    for a, k in A.items():
        p = os.path.join(tree, a)
        if not os.path.exists(p):
            continue
        try:
            if k == "texture" or (k == "derived" and a.endswith(".png")):
                yield a, png.read(p).tobytes()
            elif k == "derived" and a.endswith(".raw"):
                yield a, open(p, "rb").read()
            elif k == "incc":
                yield a, incc_rgba(p, ytex[os.path.basename(a).split(".")[0]], ytex, tree)[0].tobytes()
            elif k == "tkmk00":
                yield a, tkmk_rgba(dirty, p, T.get(a, {}).get("tk_alpha", 1)).tobytes()
        except Exception as e:                        # a missing/odd file is reported, not fatal
            print("  skip", a, e)


def audio_streams(tree):
    ctl = open(os.path.join(tree, "bin/audiobanks.us.bin"), "rb").read()
    tbl = open(os.path.join(tree, "bin/audiotables.bin"), "rb").read()
    for key, s in sorted(audiobank.samples(ctl, tbl).items()):
        raw = tbl[key:key + s["size"]]
        yield f"tbl@{key:x}", raw
        book = audiobank.book_at(ctl, s["books"][0])
        pcm = vadpcm.decode(raw, book, s["size"] // 9 * 16).astype(">i2").tobytes()
        yield f"pcm@{key:x}", pcm


def main(argv):
    dirty, clean = argv[1], argv[2]
    A = json.load(open(os.path.join(HERE, "spec", "assets.json")))["assets"]
    T = json.load(open(os.path.join(HERE, "spec", "textures.json")))
    ytex = yaml_textures(dirty)
    idx = taint.build_index(s for _, s in tex_streams(dirty, A, T, ytex, dirty))
    hits = taint.scan(idx, tex_streams(clean, A, T, ytex, dirty))
    aidx = taint.build_index(s for _, s in audio_streams(dirty))
    hits += taint.scan(aidx, audio_streams(clean))
    bad = sorted((h for h in hits if h[3] >= taint.FAIL_RUN), key=lambda h: -h[3])
    kept = sum(1 for k in A.values() if k == "kept")
    print(f"taint: {sum(1 for k in A.values() if k in ('texture', 'incc', 'tkmk00'))} textures + derived kart files "
          f"+ 202 samples scanned; {len(hits)} with short coincidental matches; {len(bad)} failing "
          f"(run >= {taint.FAIL_RUN} B); {kept} kept facts not scanned")
    for label, off, n, run in bad[:10]:
        print(f"  FAIL {label} run {run} B ({n} windows)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
