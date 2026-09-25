"""Check generated assets against the game's fixed DMA sizes (run after a clean build).

    python -m games.mk64.check_limits <clean tree>

- tkmk00: MenuTexture.size in src/data/textures.c (0 -> 0x1000 bytes are read)
- kart frames: compressed .mio0 <= D_800DDEB0[character] (src/kart_dma.c); tumble frames <= 0x900
"""
import glob
import os
import re
import sys

CHARS = ["mario", "luigi", "yoshi", "toad", "donkeykong", "wario", "peach", "bowser"]


def main(argv):
    t = argv[1]
    bad = 0
    src = open(os.path.join(t, "src/data/textures.c")).read()
    sizes = {}
    for sym, sz in re.findall(r"\{\s*\d+,\s*(\w+),\s*\d+,\s*\d+,\s*\d+,\s*\d+,\s*(0x[0-9a-fA-F]+|\d+),", src):
        sizes.setdefault(sym, set()).add(int(sz, 0) or 0x1000)
    for f in glob.glob(os.path.join(t, "bin", "*.tkmk00")):
        sym = os.path.basename(f).split(".")[0]
        n = os.path.getsize(f)
        lim = min(sizes.get(sym, {0x1000}))
        if n > lim:
            bad += 1
            print(f"  TKMK00 {sym}: {n} > {lim}")
    kd = open(os.path.join(t, "src/kart_dma.c")).read()
    lims = [int(x, 16) for x in re.findall(r"0x[0-9a-fA-F]+", re.search(r"D_800DDEB0\[\] = \{([^}]*)\}", kd).group(1))]
    worst = {}
    for i, ch in enumerate(CHARS):
        for f in glob.glob(os.path.join(t, "assets/karts", ch, "frames", "*.mio0")):
            n = os.path.getsize(f)
            worst[ch] = max(worst.get(ch, 0), n)
            if n > lims[i] and n > 0x900:
                bad += 1
        if worst.get(ch, 0) > lims[i]:
            print(f"  KART {ch}: largest frame {worst[ch]} > limit {lims[i]} (tumble frames may use 0x900)")
            bad += 1
    print(f"limits: {bad} over; kart worst {worst}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
