"""Build-tool patches for building the mk64 decomp on Windows (dirty and clean trees).

    python -m games.mk64.tree_patches <tree>
Each patch: (file, old, new). Idempotent (skips when `new` is already present).
"""
import os
import sys

PATCHES = [
    # the torch submodule is not built here (assets come from the spec / a prebuilt torch in the dirty room)
    ("tools/Makefile", "all: $(PROGRAMS) torch\n", "all: $(PROGRAMS)\n"),
    # CreateProcess needs the .exe of the IDO recomp wrapper
    ("tools/asm_processor/build.py", "    try:\n        subprocess.check_call(compile_cmdline)",
     "    import shutil as _sh\n"
     "    compile_cmdline[0] = _sh.which(compile_cmdline[0]) or compile_cmdline[0]\n"
     "    try:\n        subprocess.check_call(compile_cmdline)"),
]


def apply(tree):
    n = 0
    for f, old, new in PATCHES:
        p = os.path.join(tree, f)
        s = open(p, newline="").read()
        if new in s:
            continue
        assert old in s, f"patch target missing in {f}"
        open(p, "w", newline="").write(s.replace(old, new, 1))
        n += 1
    print(f"tree_patches: {n} applied, {len(PATCHES) - n} already present")


if __name__ == "__main__":
    apply(sys.argv[1])
