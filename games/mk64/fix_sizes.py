"""Patch compressed-size fields that the game hardcodes, from the sizes of our built MIO0 files.

    python -m games.mk64.fix_sizes <clean tree>      (after a build; then build again)

course_texture tables (courses/*/course_offsets.c): { symbol, compressed size, size, 0 }.
The symbol -> file map comes from the data/*.s glabel + .incbin pairs.
"""
import glob
import os
import re
import sys


def symbol_files(tree):
    out = {}
    for s in glob.glob(os.path.join(tree, "data", "**", "*.s"), recursive=True):
        sym = None
        for line in open(s, errors="replace"):
            m = re.match(r"\s*glabel\s+(\w+)", line)
            if m:
                sym = m.group(1)
                continue
            m = re.match(r'\s*\.incbin\s+"([^"]+\.mio0)"', line)
            if m and sym:
                out[sym] = m.group(1)
                sym = None
    return out


def main(argv):
    tree = argv[1]
    build = os.path.join(tree, "build", "us")
    files = symbol_files(tree)
    changed = missing = 0
    for p in glob.glob(os.path.join(tree, "courses", "*", "course_offsets.c")):
        src = open(p, newline="").read()

        def fix(m):
            nonlocal changed, missing
            sym, csize = m.group(2), int(m.group(3), 0)
            f = files.get(sym)
            path = None
            for base in (build, tree):
                if f and os.path.exists(os.path.join(base, f)):
                    path = os.path.join(base, f)
                    break
            if path is None:
                missing += 1
                return m.group(0)
            n = os.path.getsize(path)
            if n != csize:
                changed += 1
                return f"{m.group(1)}0x{n:04X}{m.group(4)}"
            return m.group(0)
        new = re.sub(r"(\{\s*(\w+),\s*)(0x[0-9a-fA-F]+)(,\s*0x[0-9a-fA-F]+,\s*0x[0-9a-fA-F]+\s*\})", fix, src)
        if new != src:
            open(p, "w", newline="").write(new)
    # MenuTexture tables (src/data/textures.c): { type, symbol, w, h, dx, dy, compressed size, 0 }
    menu = 0
    tk = {os.path.basename(f).split(".")[0]: f for f in glob.glob(os.path.join(tree, "bin", "*.tkmk00"))}
    p = os.path.join(tree, "src", "data", "textures.c")
    src = open(p, newline="").read()

    def fixm(m):
        nonlocal menu
        sym, size = m.group(2), int(m.group(3), 0)
        path = tk.get(sym)
        if path is None and sym in files:
            for base in (build, tree):
                if os.path.exists(os.path.join(base, files[sym])):
                    path = os.path.join(base, files[sym])
                    break
        if path is None:
            return m.group(0)
        n = os.path.getsize(path)
        want = (n + 7) // 8 * 8
        if n <= (size or 0x1000):                 # the game reads enough already
            return m.group(0)
        menu += 1
        return f"{m.group(1)}0x{want:x}{m.group(4)}"
    new = re.sub(r"(\{\s*\d+,\s*(\w+),\s*\d+,\s*\d+,\s*\d+,\s*\d+,\s*)(0x[0-9a-fA-F]+|\d+)(,)", fixm, src)
    if new != src:
        open(p, "w", newline="").write(new)
    print(f"fix_sizes: {changed} course texture sizes, {menu} menu texture sizes patched; "
          f"{missing} course symbols without a built mio0")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
