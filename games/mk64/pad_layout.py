"""Keep the ROM layout identical to the game's: every compressed blob (MIO0/TKMK00) in the
clean build is zero-padded to the size the game's own blob had (a size fact kept in the spec).
MK64 is not reliably shiftable (a 16-byte shift of retail data hangs at boot), so nothing moves.

    python -m games.mk64.pad_layout record <dirty tree>        (dirty room: sizes -> spec/slot_sizes.json)
    python -m games.mk64.pad_layout pad <clean tree>           (after a build; then build again)
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SIZES = os.path.join(HERE, "spec", "slot_sizes.json")
EXT = (".mio0", ".tkmk00")
SKIP = {".git", "tools", "modding"}


def blobs(tree):
    for d, dirs, files in os.walk(tree):
        dirs[:] = [x for x in dirs if x not in SKIP]
        for f in files:
            if f.endswith(EXT):
                p = os.path.join(d, f)
                yield os.path.relpath(p, tree).replace("\\", "/"), p


def record(tree):
    sizes = {rel: os.path.getsize(p) for rel, p in blobs(tree)}
    json.dump(sizes, open(SIZES, "w"), indent=0, sort_keys=True)
    print(f"pad_layout: {len(sizes)} blob sizes recorded")


def pad(tree):
    sizes = json.load(open(SIZES))
    padded = same = 0
    over = []
    for rel, p in blobs(tree):
        want = sizes.get(rel)
        if want is None:
            continue
        n = os.path.getsize(p)
        if n < want:
            with open(p, "ab") as f:
                f.write(bytes(want - n))
            padded += 1
            for obj in (p + ".o", p + ".s"):       # the .mio0.o rule only depends on its .s, not the blob
                if os.path.exists(obj):
                    os.remove(obj)
        elif n > want:
            over.append((n - want, rel, n, want))
        else:
            same += 1
    over.sort(reverse=True)
    print(f"pad_layout: {padded} padded, {same} already exact, {len(over)} TOO BIG")
    for d, rel, n, want in over[:12]:
        print(f"  OVER {rel}: {n} > {want} (+{d})")
    json.dump([o[1] for o in over], open(os.path.join(tree, "pad_over.json"), "w"), indent=0)
    return 1 if over else 0


def sources(blob, textures):
    """Texture slots that feed a compressed blob."""
    b = blob[len("build/us/"):] if blob.startswith("build/us/") else blob
    if b.endswith(".tkmk00"):
        return [b] if b in textures else []
    base = b[:-5]
    if base + ".png" in textures:
        return [base + ".png"]
    if b.endswith("/boo_frames.mio0"):
        return [t for t in textures if t.startswith(os.path.dirname(b) + "/gTextureBoo")]
    parts = b.split("/")
    if parts[0] == "courses" and len(parts) >= 3:                 # course_data.mio0 / geography
        return [t for t in textures if t.startswith(f"assets/courses/{parts[1]}/")]
    if parts[0] == "assets" and parts[1] == "code":              # common_data.mio0, ceremony_data.mio0 ...
        return [t for t in textures if t.startswith(f"assets/code/{parts[2]}/")]
    return []


def shrink_update(tree):
    over = json.load(open(os.path.join(tree, "pad_over.json")))
    textures = json.load(open(os.path.join(HERE, "spec", "textures.json")))
    sp = os.path.join(tree, "shrink.json")
    shrink = json.load(open(sp)) if os.path.exists(sp) else {}
    n = 0
    for blob in over:
        for t in sources(blob, textures):
            if shrink.get(t, 0) < 6:
                shrink[t] = shrink.get(t, 0) + 1
                n += 1
    json.dump(shrink, open(sp, "w"), indent=0)
    print(f"pad_layout: shrink level raised for {n} textures ({len(over)} blobs over)")


if __name__ == "__main__":
    cmd, tree = sys.argv[1], sys.argv[2]
    sys.exit({"record": record, "pad": pad, "shrink": shrink_update}[cmd](tree) or 0)
