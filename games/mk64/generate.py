"""CLEAN ROOM: games/mk64/spec -> a buildable MK64 tree with no ROM data.

    python -m games.mk64.generate <pristine decomp> <clean tree> [--only tex|snd]

1. copy the pristine decomp (no .git) and the spec's kept facts into <clean>
2. textures: every slot from its digest (or a hook: labels, faces, sprites),
   written in the slot's container (png / torch .inc.c / tkmk00), CI slots
   quantised per palette group so the build's exact-match palette lookup works
3. audio: every tbl sample resynthesised from its outline, our own 2-predictor
   VADPCM books written into the kept ctl structure, loop states recomputed
4. extraction sentinels touched so the build never looks for a ROM
"""
import collections
import glob
import json
import os
import shutil
import struct
import sys

import numpy as np
import yaml

from cleanroom.gfx import png, texfmt
from cleanroom.decomp import gen
from cleanroom.audio import descriptor, vadpcm
from games.mk64 import tkmk00
from games.mk64.extract_spec import FMT

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(HERE, "spec")
HOOKS = []                     # fn(path, d) -> rgba or None; filled by drawn.py etc.


TEXT_SLOTS = set()


def load_hooks():
    try:
        from games.mk64 import drawn
        HOOKS.extend(drawn.HOOKS)
        TEXT_SLOTS.update(drawn.LABELS)
        drawn.SHRINK = SHRINK
    except ImportError:
        pass


JITTER = ("finish_line_banner/",)
SHRINK = {}                    # texture path -> simplification level (from the last build's pad_over list)


def digest_rgba(path, d):
    """Colour grid upsampled + kept alpha outline; no noise (MIO0 must fit the game's slot size)."""
    w, h = d["w"], d["h"]
    n = int(round(len(d["grid"]) ** 0.5))
    rgba = gen.upsample_grid(d["grid"], n, w, h)
    rgba[..., 3] = gen.unpack_alpha2(d["alpha2"], w, h) if "alpha2" in d else 255
    # period-2 checker dither of one 5-bit step: compresses well, never follows retail ramps
    rgba[..., :3] += ((np.indices((h, w)).sum(0) % 2) * 8 - 4)[..., None]
    if any(k in path for k in JITTER):                   # slots where the checker still met retail runs (taint)
        rgba[..., :3] += np.random.default_rng(gen.h32("jit", path)).integers(-6, 7, (h, w, 1))
    return np.clip(rgba, 0, 255).astype(np.uint8)


def simplify(rgba, level):
    """Fewer distinct texels so LZ finds repeats: blur + posterise (level 1..4)."""
    if level <= 0:
        return rgba
    if level >= 6:                                  # one flat colour inside the kept outline
        x = rgba.astype(np.float32).copy()
        a = x[..., 3] > 0
        x[..., :3] = x[a, :3].mean(0) if a.any() else x[..., :3].mean((0, 1))
        return np.clip(np.round(x / 8) * 8, 0, 255).astype(np.uint8)
    if level >= 5:                                  # flat 4x4-pixel blocks, 16 levels per channel
        h, w = rgba.shape[:2]
        x = rgba.astype(np.float32).copy()
        bh, bw = max(1, h // max(1, h // 4)), max(1, w // max(1, w // 4))
        for y in range(0, h, bh):
            for xx in range(0, w, bw):
                x[y:y + bh, xx:xx + bw, :3] = x[y:y + bh, xx:xx + bw, :3].reshape(-1, 3).mean(0)
        x[..., :3] = np.round(x[..., :3] / 16) * 16
        return np.clip(x, 0, 255).astype(np.uint8)
    x = rgba.astype(np.float32)
    k = 1 + level
    for _ in range(level):
        x[..., :3] = (x[..., :3] + np.roll(x[..., :3], 1, 0) + np.roll(x[..., :3], 1, 1) + np.roll(x[..., :3], -1, 0)
                      + np.roll(x[..., :3], -1, 1)) / 5
    step = 8 * (2 ** level)
    x[..., :3] = np.round(x[..., :3] / step) * step
    return np.clip(x, 0, 255).astype(np.uint8)


def texture_rgba(path, d):
    r = None
    for h in HOOKS:
        r = h(path, d)
        if r is not None:
            break
    rgba = np.clip(np.asarray(r), 0, 255).astype(np.uint8) if r is not None else digest_rgba(path, d)
    if r is not None and path in TEXT_SLOTS:          # text is never blurred; labels fit by dropping ornaments
        return rgba
    return simplify(rgba, SHRINK.get(path, 0))


# ------------------------------------------------------------- CI palettes

def snap16(rgba):
    """Round RGBA8 to what an rgba16 palette can hold (5-bit colour, 1-bit alpha)."""
    c = rgba.astype(np.int32)
    out = np.empty_like(c)
    out[..., :3] = ((c[..., :3] >> 3) << 3) | (c[..., :3] >> 5)
    out[..., 3] = np.where(c[..., 3] >= 128, 255, 0)
    out[out[..., 3] == 0] = 0
    return out.astype(np.uint8)


def quantize(images, n, seed=1):
    """Jointly quantise RGBA images to <= n rgba16 colours.
    Returns palette (n, 4) uint8 and index arrays."""
    snapped = [snap16(im) for im in images]
    px = np.concatenate([s.reshape(-1, 4) for s in snapped])
    uniq, counts = np.unique(px.view(np.uint32), return_counts=True)
    cols = uniq.view(np.uint8).reshape(-1, 4)
    has_clear = (cols[:, 3] == 0).any()
    opaque = cols[cols[:, 3] == 255]
    wopq = counts[cols[:, 3] == 255].astype(np.float64)
    k = n - (1 if has_clear else 0)
    if len(opaque) <= k:
        centers = opaque.astype(np.float64)
    else:
        rng = np.random.default_rng(seed)
        x = opaque[:, :3].astype(np.float64)
        centers = x[rng.choice(len(x), k, replace=False, p=wopq / wopq.sum())]
        for _ in range(12):
            d = ((x[:, None, :] - centers[None]) ** 2).sum(-1) if len(x) * k < 4e7 else None
            if d is None:
                lab = np.concatenate([((x[i:i + 4096, None, :] - centers[None]) ** 2).sum(-1).argmin(1)
                                      for i in range(0, len(x), 4096)])
            else:
                lab = d.argmin(1)
            for j in range(k):
                m = lab == j
                if m.any():
                    centers[j] = (x[m] * wopq[m, None]).sum(0) / wopq[m].sum()
        centers = np.concatenate([centers, np.full((k, 1), 255.0)], 1)
    pal = np.zeros((n, 4), np.uint8)
    base = 1 if has_clear else 0
    pal[base:base + len(centers)] = snap16(np.clip(np.round(centers), 0, 255))
    pal[base:base + len(centers), 3] = 255
    if len(centers) < k:                                   # unused slots: repeat the last colour
        pal[base + len(centers):] = pal[base + len(centers) - 1] if len(centers) else 0
    opal = pal[base:base + max(1, len(centers))].astype(np.int32)
    idxs = []
    for s in snapped:
        flat = s.reshape(-1, 4).astype(np.int32)
        idx = np.zeros(len(flat), np.int64)
        op = flat[:, 3] == 255
        if op.any():
            f = flat[op, :3]
            idx[op] = np.concatenate([((f[i:i + 8192, None, :] - opal[None, :, :3]) ** 2).sum(-1).argmin(1)
                                      for i in range(0, len(f), 8192)]) + base
        idxs.append(idx.reshape(s.shape[:2]))
    return pal, idxs


def apply_palette(pal, idx):
    return pal[idx]


# ------------------------------------------------------------- writers

def write_png(clean, path, rgba):
    p = os.path.join(clean, path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    png.write(p, rgba)


def incc_text(vals, width):
    fmt = "0x%04x, " if width == 2 else "0x%02x, "
    per = 8 if width == 2 else 16
    lines = ["".join(fmt % v for v in vals[i:i + per]) for i in range(0, len(vals), per)]
    return "\n".join(lines) + "\n"


def write_incc(clean, path, rgba=None, fmt=None, index=None):
    """rgba16 / i / ia textures from RGBA; CI from an index array."""
    if index is not None:
        vals = list(np.asarray(index, np.uint8).ravel()) if fmt == "ci8" else \
            list(texfmt.encode(np.stack([index] * 4, -1), texfmt.CI, texfmt.B4))
        width = 1
    else:
        f, s = FMT[fmt]
        data = texfmt.encode(rgba, f, s)
        if fmt in ("rgba16", "tlut"):
            vals, width = list(struct.unpack(">%dH" % (len(data) // 2), data)), 2
        else:
            vals, width = list(data), 1
    p = os.path.join(clean, path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", newline="\n").write(incc_text(vals, width))


def rgba16_words(rgba):
    return np.frombuffer(texfmt.encode(rgba, texfmt.RGBA, texfmt.B16), ">u2").reshape(rgba.shape[:2])


# ------------------------------------------------------------- karts

TIRE_RGB = np.array([34, 34, 40], np.float64)


def wheel_palette(phase):
    """64 entries; tread index = band * 4 + level (8 bands around the tyre, 4 light levels)."""
    pal = np.zeros((64, 4), np.uint8)
    for band in range(8):
        stripe = 1.9 if (band + phase) % 4 == 0 else 1.0
        for lev, lv in enumerate((0.55, 0.7, 0.85, 1.0)):
            pal[band * 4 + lev, :3] = np.clip(TIRE_RGB * stripe * lv * 1.4, 0, 255)
            pal[band * 4 + lev, 3] = 255
    pal[32:] = pal[:32]
    return snap16(pal[None])[0]


def gen_kart(clean, ch, frames, T, done):
    from cleanroom.decomp.gen import unpack_alpha2
    from games.mk64 import kartrender
    kdir = f"assets/karts/{ch}"
    prims = kartrender.driver(ch)
    renders = []
    for f in frames:
        i = int(os.path.basename(f)[:-4].rsplit("frame", 1)[1])
        d = T[f]
        bbox = None
        if "alpha2" in d:
            a = unpack_alpha2(d["alpha2"], d["w"], d["h"]) > 100
            ys, xs = np.nonzero(a)
            if len(xs):
                bbox = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
        rgba, wm, tr = kartrender.render_frame(ch, i, bbox, prims)
        has_wheel_pal = f"{kdir}/palettes/kart_{i:03d}_wheel_0.png" in T
        if not has_wheel_pal:
            wm = np.zeros_like(wm)
        renders.append((f, i, rgba, wm, tr, has_wheel_pal))
    body_px = [np.where(r[3][..., None], 0, r[2]) for r in renders]
    p_, ix = quantize(body_px, 0xC0)
    write_png(clean, f"{kdir}/palettes/{ch}_kart_palette.png", p_.reshape(12, 16, 4))
    done.add(f"{kdir}/palettes/{ch}_kart_palette.png")
    wp = [wheel_palette(k) for k in range(4)]
    for (f, i, rgba, wm, tr, hw), idx in zip(renders, ix):
        out = p_[idx]
        tri = np.clip(tr, 0, 31)
        out[wm] = wp[0][tri[wm]]
        write_png(clean, f, out)
        name = os.path.basename(f)[:-4]
        write_png(clean, f"{kdir}/frames/stitched_palettes/{name}_stitched_palette.png",
                  np.concatenate([p_, wp[0]]).reshape(16, 16, 4))
        mp = os.path.join(clean, f"{kdir}/frames/wheel_masks/{name}_wheel_mask.raw")
        os.makedirs(os.path.dirname(mp), exist_ok=True)
        open(mp, "wb").write(wm.astype(np.uint8).tobytes())
        if hw:
            for k in range(4):
                q = f"{kdir}/palettes/kart_{i:03d}_wheel_{k}.png"
                write_png(clean, q, wp[k].reshape(4, 16, 4))
                done.add(q)
        done.add(f)
    for q in T:                                    # wheel palettes of frames we did not see
        if q.startswith(f"{kdir}/palettes/kart_") and q not in done:
            write_png(clean, q, wp[0].reshape(4, 16, 4))
            done.add(q)


# ------------------------------------------------------------- textures

def gen_textures(pristine, clean, spec):
    T = json.load(open(os.path.join(spec, "textures.json")))
    A = json.load(open(os.path.join(spec, "assets.json")))["assets"]
    G = json.load(open(os.path.join(spec, "ci_groups.json")))
    ytex = {}
    for f in glob.glob(os.path.join(pristine, "yamls/us/*.yml")):
        for k, v in (yaml.safe_load(open(f)) or {}).items():
            if isinstance(v, dict) and v.get("type") == "texture":
                ytex[v.get("symbol", k)] = v
    img = {p: texture_rgba(p, d) for p, d in T.items()}
    done = set()
    stats = collections.Counter()

    # 1) PNG palette groups from the build's own n64graphics -p calls
    kart_frames = collections.defaultdict(list)
    for pal, frames in G.items():
        if "stitched_palettes/" in pal:                     # kart sprite: handled per character below
            for fr in frames:
                kart_frames[fr["png"].split("/")[2]].append(fr["png"])
            continue
        frames = [f["png"] for f in frames if f["png"] in img]
        if not frames:
            continue
        if pal.startswith("build/"):                        # the build derives the palette: <= 256/16 colours
            for f in frames:
                n = 16 if f.endswith(".ci4.png") else 256
                p_, (ix,) = quantize([img[f]], n)
                write_png(clean, f, apply_palette(p_, ix))
                done.add(f)
                stats["ci_self"] += 1
            continue
        if pal not in T:
            print("  WARN palette not in spec:", pal)
            continue
        n = T[pal]["w"] * T[pal]["h"]
        p_, ix = quantize([img[f] for f in frames], n)
        write_png(clean, pal, p_.reshape(T[pal]["h"], T[pal]["w"], 4))
        done.add(pal)
        for f, i in zip(frames, ix):
            write_png(clean, f, apply_palette(p_, i))
            done.add(f)
        stats["ci_group"] += 1

    # 2) kart sprites: rendered from our own models (kartrender), shared body palette
    #    (0..0xBF) + per-frame wheel palettes (0xC0..) whose 4 phases turn the tread
    for ch, frames in kart_frames.items():
        gen_kart(clean, ch, sorted(set(frames)), T, done)
        stats["kart_chars"] += 1

    # 3) torch .inc.c textures (CI ones grouped by their TLUT symbol)
    incc = {p: d for p, d in T.items() if A.get(p) == "incc"}
    by_sym = {os.path.basename(p).split(".")[0]: p for p in T if p.endswith(".png")}
    by_sym.update({os.path.basename(p).split(".")[0]: p for p in incc})
    tl_groups = collections.defaultdict(list)
    for p in incc:
        sym = os.path.basename(p).split(".")[0]
        t = ytex.get(sym, {}).get("tlut_symbol")
        if t and t in by_sym:
            tl_groups[t].append(p)
    for t, users in tl_groups.items():
        tp = by_sym[t]
        n = T[tp]["w"] * T[tp]["h"]
        p_, ix = quantize([img[u] for u in users], n)
        if tp.endswith(".png"):
            write_png(clean, tp, p_.reshape(T[tp]["h"], T[tp]["w"], 4))
        else:
            write_incc(clean, tp, rgba=p_.reshape(T[tp]["h"], T[tp]["w"], 4), fmt="rgba16")
        done.add(tp)
        for u, i in zip(users, ix):
            write_incc(clean, u, fmt=os.path.basename(u).split(".")[-3], index=i)
            done.add(u)
        stats["incc_ci"] += len(users)
    for p in incc:
        if p in done:
            continue
        fmt = os.path.basename(p).split(".")[-3]
        if fmt.startswith("ci"):
            print("  WARN CI inc.c without TLUT group:", p)
            write_incc(clean, p, fmt=fmt, index=np.zeros((T[p]["h"], T[p]["w"]), np.int64))
        else:
            write_incc(clean, p, rgba=img[p], fmt=fmt)
        done.add(p)
        stats["incc"] += 1

    # 4) tkmk00 menu textures
    sizes = {}
    for p, d in T.items():
        if A.get(p) != "tkmk00":
            continue
        rgba = img[p]
        data, _ = tkmk00.encode(rgba16_words(rgba), d.get("tk_alpha", 1))
        q = os.path.join(clean, p)
        os.makedirs(os.path.dirname(q), exist_ok=True)
        open(q, "wb").write(data)
        sizes[p] = len(data)
        done.add(p)
        stats["tkmk00"] += 1

    # 5) everything else: plain PNG (CI slots quantised alone)
    for p, d in T.items():
        if p in done:
            continue
        rgba = img[p]
        if ".ci8." in p or ".ci4." in p:
            p_, (ix,) = quantize([rgba], 16 if ".ci4." in p else 256)
            rgba = apply_palette(p_, ix)
        write_png(clean, p, rgba)
        stats["png"] += 1
    print("textures:", dict(stats))
    return sizes


# ------------------------------------------------------------- audio

def gen_audio(clean, spec):
    S = json.load(open(os.path.join(spec, "samples.json")))
    L = json.load(open(os.path.join(spec, "tbl_layout.json")))
    ctl = bytearray(open(os.path.join(spec, "kept", "bin", "audiobanks.us.bin"), "rb").read())
    tbl = bytearray(L["tbl_len"])
    hdr = bytes.fromhex(L["tbl_header"])
    tbl[:len(hdr)] = hdr
    for key, d in S.items():
        key = int(key)
        n = d["nframes"]
        st, en, cnt = d["loop"]
        dd = {"nframes": n, "rate": d["rate"], "desc": d["desc"]}
        vw = os.path.join(HERE, "voices", f"{key}.wav")
        if os.path.exists(vw):                               # a voice line (TTS placeholder or the user's take)
            import wave
            with wave.open(vw) as wf:
                x = np.frombuffer(wf.readframes(wf.getnframes()), "<i2").astype(np.float32) / 32768
        else:
            x = descriptor.synthesize(d["desc"], n, d["rate"], seed=gen.h32("smp", key))
        x = np.asarray(x, np.float32)[:n]
        x = np.pad(x, (0, n - len(x)))
        if cnt and en > st + 16:
            x = descriptor.make_loop_seamless(x, st, min(en, n))
        dither = np.random.default_rng(gen.h32("dither", key)).integers(-1, 2, n)
        pcm = np.clip(np.round(np.clip(x, -1, 1) * 32000) + dither, -32768, 32767).astype(np.int16)
        book = vadpcm.make_book(gen.two_predictors(pcm.astype(np.float64)))
        data, _, dec = vadpcm.encode(pcm, book)
        data = data[:d["size"]] + bytes(max(0, d["size"] - len(data)))
        tbl[key:key + d["size"]] = data
        vals = struct.pack(">%dh" % len(book["book"]), *book["book"])
        for bo in d["books"]:
            assert struct.unpack_from(">ii", ctl, bo) == (2, 2)
            ctl[bo + 8:bo + 8 + len(vals)] = vals
        if cnt:
            state = vadpcm.loop_state(dec, st)
            sv = struct.pack(">16h", *[int(v) for v in state])
            for lo in d["loops"]:
                ctl[lo + 16:lo + 48] = sv
    os.makedirs(os.path.join(clean, "bin"), exist_ok=True)
    open(os.path.join(clean, "bin", "audiotables.bin"), "wb").write(tbl)
    open(os.path.join(clean, "bin", "audiobanks.us.bin"), "wb").write(ctl)
    print(f"audio: {len(S)} samples resynthesised, tbl {len(tbl)} B, ctl {len(ctl)} B")


# ------------------------------------------------------------- tree

def copy_tree(pristine, clean, spec):
    if os.path.exists(clean):
        for sub in os.listdir(clean):
            if sub not in ("build", "tools"):
                q = os.path.join(clean, sub)
                shutil.rmtree(q) if os.path.isdir(q) else os.remove(q)
    shutil.copytree(pristine, clean, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".git", "cmake-build-release", "baserom*"))
    n = 0
    for kept in (os.path.join(spec, "kept"), os.path.join(HERE, "spec_local", "kept")):
      for d, _, files in os.walk(kept):
        for f in files:
            src = os.path.join(d, f)
            rel = os.path.relpath(src, kept)
            dst = os.path.join(clean, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(src, dst)
            n += 1
    # never extract: the torch rule is dropped and every export sentinel exists
    from games.mk64 import tree_patches
    tree_patches.apply(clean)
    print(f"tree: pristine copied, {n} kept files")


def touch_sentinels(clean):
    """Create every *_EXPORT_SENTINEL the asset makefiles name."""
    import re
    n = 0
    for mk in glob.glob(os.path.join(clean, "assets", "include", "**", "*.mk"), recursive=True):
        txt = open(mk).read()
        dirs = dict(re.findall(r"^(\w+_DIR) := (\S+)", txt, re.M))
        for var, val in re.findall(r"^(\w+_EXPORT_SENTINEL) := (\S+)", txt, re.M):
            for k, v in dirs.items():
                val = val.replace(f"$({k})", v)
            p = os.path.join(clean, val)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w").close()
            n += 1
    print(f"sentinels: {n}")


def patch_menu_sizes(clean, sizes):
    """MenuTexture.size is the compressed size the game DMAs; raise it where our TKMK00 is bigger."""
    import re
    p = os.path.join(clean, "src/data/textures.c")
    src = open(p, newline="").read()
    n = 0

    def fix(m):
        nonlocal n
        sym, size = m.group(2), int(m.group(3), 0)
        ours = sizes.get(f"bin/{sym}.rgba16.tkmk00")
        lim = size or 0x1000
        if ours and ours > lim:
            n += 1
            return f"{m.group(1)}0x{(ours + 7) // 8 * 8:x}{m.group(4)}"
        return m.group(0)
    src = re.sub(r"(\{\s*\d+,\s*(\w+),\s*\d+,\s*\d+,\s*\d+,\s*\d+,\s*)(0x[0-9a-fA-F]+|\d+)(,)",
                 fix, src)
    open(p, "w", newline="").write(src)
    print(f"menu sizes: {n} MenuTexture sizes raised")


def main(argv):
    pristine, clean = argv[1], argv[2]
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    load_hooks()
    sp = os.path.join(clean, "shrink.json")
    if os.path.exists(sp):
        SHRINK.update(json.load(open(sp)))
    if only is None:
        copy_tree(pristine, clean, SPEC)
    if only in (None, "tex"):
        sizes = gen_textures(pristine, clean, SPEC)
        json.dump(sizes, open(os.path.join(clean, "tkmk00_sizes.json"), "w"), indent=0)
        patch_menu_sizes(clean, sizes)
    if only in (None, "snd"):
        gen_audio(clean, SPEC)
    if only is None:
        touch_sentinels(clean)


if __name__ == "__main__":
    main(sys.argv)
