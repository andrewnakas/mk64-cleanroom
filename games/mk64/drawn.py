"""Texture hooks: text-bearing textures re-typeset, emblems/icons drawn from our own descriptions.

HOOKS: fn(path, digest) -> RGBA uint8 or None (None = next hook / default digest texture).
"""
import json
import os

import numpy as np
from PIL import Image, ImageDraw

from cleanroom.decomp import gen
from games.mk64 import labels

HERE = os.path.dirname(os.path.abspath(__file__))
LABELS = json.load(open(os.path.join(HERE, "tex_labels.json")))
SHRINK = {}          # set by generate: slot -> fit level (labels drop ornaments instead of blurring)
SS = 4

CHAR = {  # our own palette descriptions of each driver (cap/hair, face, accent)
    "mario": dict(cap=(220, 30, 30), skin=(255, 200, 150), hair=(90, 50, 20), letter="M", emblem=(255, 255, 255)),
    "luigi": dict(cap=(40, 170, 50), skin=(255, 200, 150), hair=(90, 50, 20), letter="L", emblem=(255, 255, 255)),
    "peach": dict(cap=(255, 215, 70), skin=(255, 214, 180), hair=(255, 215, 70), crown=(255, 200, 40), gem=(60, 120, 255)),
    "toad": dict(cap=(255, 255, 255), spots=(220, 30, 40), skin=(255, 214, 180)),
    "yoshi": dict(cap=(60, 190, 60), skin=(60, 190, 60), snout=(120, 220, 110)),
    "dk": dict(cap=(120, 70, 30), skin=(210, 160, 110), hair=(120, 70, 30)),
    "wario": dict(cap=(250, 210, 40), skin=(255, 190, 140), hair=(90, 50, 20), letter="W", emblem=(40, 60, 200)),
    "bowser": dict(cap=(250, 150, 40), skin=(240, 200, 60), hair=(250, 90, 30), horns=(250, 245, 225)),
}


def _canvas(w, h):
    im = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def _down(im, w, h):
    return np.asarray(im.resize((w, h), Image.LANCZOS), np.float32)


def head(name, w, h):
    """A driver's head icon, front view, drawn from simple shapes."""
    c = CHAR[name]
    im, d = _canvas(w, h)
    W, H = w * SS, h * SS
    cx, cy, r = W / 2, H * 0.56, min(W, H) * 0.40
    ol = (20, 10, 10, 255)
    d.ellipse([cx - r, cy - r * 0.95, cx + r, cy + r * 0.95], fill=c["skin"] + (255,), outline=ol, width=SS)
    if name in ("mario", "luigi", "wario"):
        d.pieslice([cx - r * 1.05, cy - r * 1.35, cx + r * 1.05, cy + r * 0.55], 180, 360, fill=c["cap"] + (255,), outline=ol, width=SS)
        d.rectangle([cx - r * 1.05, cy - r * 0.42, cx + r * 1.15, cy - r * 0.3], fill=c["cap"] + (255,))
        er = r * 0.28
        d.ellipse([cx - er, cy - r * 1.05, cx + er, cy - r * 0.5], fill=(255, 255, 255, 255))
        for sx in (-1, 1):
            d.ellipse([cx + sx * r * 0.32 - r * 0.1, cy - r * 0.2, cx + sx * r * 0.32 + r * 0.1, cy + r * 0.12], fill=(30, 60, 160, 255))
        d.ellipse([cx - r * 0.22, cy + r * 0.0, cx + r * 0.22, cy + r * 0.35], fill=(255, 170, 130, 255), outline=ol)
        d.chord([cx - r * 0.55, cy + r * 0.2, cx + r * 0.55, cy + r * 0.6], 0, 180, fill=c["hair"] + (255,))
    elif name == "peach":
        d.ellipse([cx - r * 1.15, cy - r * 1.1, cx + r * 1.15, cy + r * 1.0], fill=c["hair"] + (255,), outline=ol, width=SS)
        d.ellipse([cx - r * 0.8, cy - r * 0.7, cx + r * 0.8, cy + r * 0.9], fill=c["skin"] + (255,))
        d.polygon([(cx - r * 0.5, cy - r * 0.8), (cx - r * 0.35, cy - r * 1.3), (cx, cy - r * 0.95), (cx + r * 0.35, cy - r * 1.3),
                   (cx + r * 0.5, cy - r * 0.8)], fill=c["crown"] + (255,), outline=ol)
        d.ellipse([cx - r * 0.1, cy - r * 1.05, cx + r * 0.1, cy - r * 0.85], fill=c["gem"] + (255,))
        for sx in (-1, 1):
            d.ellipse([cx + sx * r * 0.3 - r * 0.1, cy - r * 0.2, cx + sx * r * 0.3 + r * 0.1, cy + r * 0.1], fill=(40, 90, 200, 255))
        d.arc([cx - r * 0.25, cy + r * 0.25, cx + r * 0.25, cy + r * 0.55], 20, 160, fill=(200, 60, 80, 255), width=SS)
    elif name == "toad":
        d.ellipse([cx - r * 1.2, cy - r * 1.35, cx + r * 1.2, cy + r * 0.2], fill=c["cap"] + (255,), outline=ol, width=SS)
        for sx, sy, sr in ((0, -0.85, 0.3), (-0.8, -0.45, 0.25), (0.8, -0.45, 0.25)):
            d.ellipse([cx + (sx - sr) * r, cy + (sy - sr) * r, cx + (sx + sr) * r, cy + (sy + sr) * r], fill=c["spots"] + (255,))
        for sx in (-1, 1):
            d.ellipse([cx + sx * r * 0.3 - r * 0.1, cy + r * 0.2, cx + sx * r * 0.3 + r * 0.1, cy + r * 0.55], fill=(20, 20, 20, 255))
    else:                                                  # yoshi / dk / bowser: simpler round faces
        if name == "bowser":
            for sx in (-1, 1):
                d.polygon([(cx + sx * r * 0.5, cy - r * 0.7), (cx + sx * r * 0.95, cy - r * 1.35), (cx + sx * r * 0.85, cy - r * 0.55)],
                          fill=c["horns"] + (255,), outline=ol)
            d.polygon([(cx - r * 0.3, cy - r * 0.9), (cx, cy - r * 1.3), (cx + r * 0.3, cy - r * 0.9)], fill=c["hair"] + (255,))
        if name == "yoshi":
            d.ellipse([cx - r * 0.2, cy - r * 0.1, cx + r * 1.1, cy + r * 0.7], fill=c["snout"] + (255,), outline=ol)
        for sx in (-1, 1):
            d.ellipse([cx + sx * r * 0.35 - r * 0.16, cy - r * 0.55, cx + sx * r * 0.35 + r * 0.16, cy - r * 0.05], fill=(255, 255, 255, 255), outline=ol)
            d.ellipse([cx + sx * r * 0.35 - r * 0.07, cy - r * 0.4, cx + sx * r * 0.35 + r * 0.07, cy - r * 0.15], fill=(20, 20, 20, 255))
    return _down(im, w, h)


def emblem(kind, w, h, color=None):
    im, d = _canvas(w, h)
    W, H = w * SS, h * SS
    cx, cy, r = W / 2, H / 2, min(W, H) * 0.42
    ol = (30, 10, 10, 255)
    if kind == "flower":
        for k in range(5):
            a = np.pi * 2 * k / 5 - np.pi / 2
            px, py = cx + np.cos(a) * r * 0.55, cy + np.sin(a) * r * 0.55
            d.ellipse([px - r * 0.45, py - r * 0.45, px + r * 0.45, py + r * 0.45], fill=(255, 120, 30, 255), outline=ol, width=SS)
        d.ellipse([cx - r * 0.35, cy - r * 0.35, cx + r * 0.35, cy + r * 0.35], fill=(255, 240, 80, 255), outline=ol, width=SS)
    elif kind == "mushroom":
        d.rectangle([cx - r * 0.35, cy, cx + r * 0.35, cy + r * 0.9], fill=(255, 235, 200, 255), outline=ol, width=SS)
        d.chord([cx - r, cy - r * 0.9, cx + r, cy + r * 0.5], 180, 360, fill=(230, 30, 30, 255), outline=ol, width=SS)
        for sx, sy in ((0, -0.55), (-0.6, -0.25), (0.6, -0.25)):
            d.ellipse([cx + (sx - 0.2) * r, cy + (sy - 0.2) * r, cx + (sx + 0.2) * r, cy + (sy + 0.2) * r], fill=(255, 255, 255, 255))
    elif kind in ("star", "diamond"):
        if kind == "star":
            pts = []
            for k in range(10):
                a = np.pi * k / 5 - np.pi / 2
                rr = r if k % 2 == 0 else r * 0.45
                pts.append((cx + np.cos(a) * rr, cy + np.sin(a) * rr))
            d.polygon(pts, fill=(255, 225, 40, 255), outline=ol)
        else:
            d.polygon([(cx, cy - r), (cx + r * 0.75, cy), (cx, cy + r), (cx - r * 0.75, cy)], fill=(40, 200, 220, 255), outline=ol)
            d.polygon([(cx, cy - r * 0.55), (cx + r * 0.4, cy), (cx, cy + r * 0.55), (cx - r * 0.4, cy)], fill=(170, 250, 255, 255))
    elif kind == "bomb":
        d.ellipse([cx - r * 0.8, cy - r * 0.6, cx + r * 0.8, cy + r], fill=(30, 30, 40, 255), outline=(200, 200, 220, 255), width=SS)
        d.line([cx + r * 0.3, cy - r * 0.5, cx + r * 0.7, cy - r], fill=(240, 180, 60, 255), width=SS * 2)
    elif kind in ("flag", "flag2"):
        n = 4
        s = 2 * r / n
        for i in range(n):
            for j in range(n):
                col = (255, 255, 255, 255) if (i + j) % 2 == 0 else (20, 20, 20, 255)
                d.rectangle([cx - r + i * s, cy - r + j * s, cx - r + (i + 1) * s, cy - r + (j + 1) * s], fill=col)
    elif kind == "clock":
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 255), outline=ol, width=SS)
        d.line([cx, cy, cx, cy - r * 0.7], fill=ol, width=SS)
        d.line([cx, cy, cx + r * 0.5, cy], fill=ol, width=SS)
    elif kind in ("L", "R"):
        d.rounded_rectangle([cx - r, cy - r, cx + r, cy + r], radius=r * 0.3, fill=(235, 235, 235, 255), outline=ol, width=SS)
        m = labels.text_mask(kind, max(2, int(w * 0.5)), max(2, int(h * 0.6)), "lilita")
        return _stamp(_down(im, w, h), m, (20, 20, 20))
    return _down(im, w, h)


def _stamp(img, m, rgb):
    h, w = img.shape[:2]
    mh, mw = m.shape
    y0, x0 = (h - mh) // 2, (w - mw) // 2
    a = m[..., None]
    reg = img[y0:y0 + mh, x0:x0 + mw]
    reg[..., :3] = reg[..., :3] * (1 - a) + np.asarray(rgb, np.float32) * a
    reg[..., 3] = np.maximum(reg[..., 3], m * 255)
    return img


def _paste(dst, src, x, y):
    h, w = src.shape[:2]
    a = src[..., 3:4] / 255.0
    reg = dst[y:y + h, x:x + w]
    reg[..., :3] = reg[..., :3] * (1 - a) + src[..., :3] * a
    reg[..., 3] = np.maximum(reg[..., 3], src[..., 3])


def label_hook(path, d):
    lab = LABELS.get(path)
    if lab is None:
        return None
    lvl = SHRINK.get(path, 0)
    if lvl:
        lab = dict(lab)
        if lvl >= 1:
            lab["border"] = None
        if lvl >= 2:
            lab["crisp"] = True
            lab["bot"] = lab.get("top") or labels.STYLES[lab.get("style", "course_title")].get("top")
        if lvl >= 3:
            lab["ow"] = 0
    w, h = d["w"], d["h"]
    from games.mk64.generate import digest_rgba
    base = digest_rgba(path, d)
    if lvl >= 2:                                            # flat panel: the grid's mean colour
        m = base[..., :3].reshape(-1, 3).mean(0)
        base = base.copy()
        base[..., :3] = np.round(m / 8) * 8
    if lab.get("split"):                                    # one label drawn across n side-by-side slots
        i, n = lab["split"]
        big = labels.render(lab, w * n, h, np.concatenate([base] * n, 1)).astype(np.float32)
        out = big[:, i * w:(i + 1) * w]
        if lvl >= 4:
            out[..., :3] = np.round(out[..., :3] / (16 * (lvl - 3))) * (16 * (lvl - 3))
        return np.clip(out, 0, 255).astype(np.uint8)
    img = labels.render(lab, w, h, base).astype(np.float32)
    top_h = h - max(5, int(h * 0.34)) - 2
    if lab.get("icon") and top_h > 4:
        e = emblem(lab["icon"], top_h, top_h)
        _paste(img, e, (w - top_h) // 2, 1)
    if lab.get("heads") and top_h > 4:
        n = len(lab["heads"])
        hw = min(top_h, (w - 2) // n)
        x0 = (w - hw * n) // 2
        for i, nm in enumerate(lab["heads"]):
            _paste(img, head(nm, hw, top_h), x0 + i * hw, 1)
    if lab.get("badge"):
        s = h - 2
        _paste(img, emblem(lab["badge"], s, s), 1, 1)
    if lvl >= 4:                                            # fewer colours, no blur (text stays sharp)
        step = 16 * (lvl - 3)
        img[..., :3] = np.round(img[..., :3] / step) * step
        img[..., 3] = (img[..., 3] >= 128) * 255
    return np.clip(img, 0, 255).astype(np.uint8)


HOOKS = [label_hook]


# ---------------------------------------------------------------- fonts
# textures/raw/7F*.i4.png in address order (the game's text font); multi-letter
# cells are suffix glyphs ("ND", "RD", "ST", "TH", "cc").
KANA = ("あいうえおぁぃぅぇぉかきくけこさしすせそたちつってとなにぬねのはひふへほまみむめもやゆよゃゅょ"
        "らりるれろわをんがぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽ"
        "アイウエオァィゥェォカキクケコサシスセソタチツッテトナニヌネノハヒフヘホマミムメモヤユヨャュョ"
        "ラリルレロワヲンガギグゲゴザジズゼゾダヂヅデドバビブベボパピプペポ")
RAW7F = list(KANA) + ["D", "S", "V"] + list("0123456789") + \
    ["cc", "\"", "!", "。", "-", "~", "ND", ".", "+", " ", " ", "?", "RD", "ST", "TH"]
FONT_NAMES = {"apostrophe": "'", "cc": "cc", "comma": ",", "dot": ".", "double_quote": "\"",
              "exclamation_mark": "!", "four_dote": "....", "interogation_mark": "?", "minus": "-",
              "plus": "+", "simple_quote": "'"}
NUM = dict(zero="0", one="1", two="2", three="3", four="4", five="5", six="6", seven="7", eight="8", nine="9")
_RAW7F_INDEX = None


def _glyph_char(path):
    global _RAW7F_INDEX
    b = os.path.basename(path)
    if b.startswith("font_"):
        k = b[5:].split(".")[0]
        if k.startswith("letter_"):
            return k[7:], "italic"
        if k.startswith("number_"):
            return NUM[k[7:]], "italic"
        return FONT_NAMES.get(k), "italic"
    if path.startswith("textures/raw/7F") and path.endswith(".i4.png"):
        if _RAW7F_INDEX is None:
            import glob
            spec = json.load(open(os.path.join(HERE, "spec", "assets.json")))["assets"]
            names = sorted(a for a in spec if a.startswith("textures/raw/7F") and a.endswith(".i4.png"))
            _RAW7F_INDEX = {a: i for i, a in enumerate(names)}
        i = _RAW7F_INDEX.get(path)
        if i is not None and i < len(RAW7F):
            return RAW7F[i], "upright"
    return None, None


def glyph_cell(ch, w, h, style):
    """White glyph, alpha = coverage (i4 texture: intensity is used as alpha)."""
    if ch.strip() == "":
        return np.zeros((h, w, 4), np.uint8)
    kana = any(ord(c) > 0x2FFF for c in ch)
    font = "mplus" if kana else ("lilita" if style == "italic" else "lilita")
    labels.FACES.setdefault("mplus", "MPLUSRounded1c-ExtraBold.ttf")
    tw = w - 2 if len(ch) == 1 else w - 1
    th = max(3, int(h * (0.62 if ch in "。、.,'\"-~+" else 0.86)))
    if ch in ("cc", "ND", "RD", "ST", "TH"):
        th = max(3, int(h * 0.5))
    if ch in (".", ",", "'", "。", "、"):
        th = tw = max(2, int(h * 0.24))
    elif ch == "\"":
        th = max(2, int(h * 0.3))
        tw = min(w - 2, 2 * th)
    elif ch == "-":
        th, tw = max(2, int(h * 0.16)), min(w - 2, int(h * 0.55))
    m = labels.text_mask(ch, tw, th, font)
    if style == "italic":                                    # shear to the right
        sh = np.zeros_like(m)
        for y in range(th):
            dx = int(round((th - 1 - y) * 0.22))
            sh[y, dx:] = m[y, :tw - dx] if dx else m[y]
        m = sh
    img = np.zeros((h, w, 4), np.float32)
    y0 = (h - th) // 2 if ch not in ".,'\"" else (h - th if ch in ".," else 1)
    if ch in ("cc", "ND", "RD", "ST", "TH"):
        y0 = h - th - 1
    x0 = (w - tw) // 2
    img[y0:y0 + th, x0:x0 + tw, :3] = 255
    img[y0:y0 + th, x0:x0 + tw, 3] = np.clip(m * 1.3, 0, 1) * 255
    img[..., :3] = img[..., 3:4]                             # i4: intensity carries the shape
    return img.astype(np.uint8)


def font_hook(path, d):
    ch, style = _glyph_char(path)
    if ch is None:
        return None
    return glyph_cell(ch, d["w"], d["h"], style)


HOOKS.insert(0, font_hook)


def illustration_hook(path, d):
    if path in ("bin/background_blue_sky.rgba16.tkmk00", "bin/background_sunset.rgba16.tkmk00"):
        from games.mk64 import illustrations
        return illustrations.scene(os.path.basename(path).split(".")[0], d["w"], d["h"])
    return None


HOOKS.insert(0, illustration_hook)


def charsel_hook(path, d):
    import re
    m = re.match(r"assets/character_select/(\w+)/\w+_face_(\d+)\.png$", path)
    if not m:
        return None
    from games.mk64 import kartrender
    return kartrender.render_bust(m.group(1), int(m.group(2)), d["w"])


HOOKS.insert(0, charsel_hook)


def icons_hook(path, d):
    from games.mk64 import icons
    return icons.hook(path, d)


HOOKS.append(icons_hook)


def title_logo(w, h):
    """Our own title logo: multicoloured 'MARIO KART' over a big '64' with a checkered flag."""
    img = np.zeros((h, w, 4), np.float32)
    # checkered flag behind the 64
    fx0, fy0, cell = int(w * 0.30), int(h * 0.50), max(3, h // 18)
    for j in range(5):
        for i in range(9):
            x, y = fx0 + i * cell, fy0 + j * cell + int(3 * np.sin(i * 0.8))
            col = (250, 250, 250) if (i + j) % 2 == 0 else (25, 25, 30)
            img[y:y + cell, x:x + cell, :3] = col
            img[y:y + cell, x:x + cell, 3] = 255
    # 64
    m64 = labels.text_mask("64", int(w * 0.42), int(h * 0.50), "lucky")
    y0, x0 = int(h * 0.46), int(w * 0.50)
    reg = np.zeros((h, w), np.float32)
    reg[y0:y0 + m64.shape[0], x0:x0 + m64.shape[1]] = m64
    labels._over(img, (255, 255, 255), np.clip(labels._dilate(reg, 3), 0, 1))
    labels._over(img, (20, 10, 10), np.clip(labels._dilate(reg, 2), 0, 1) * (1 - np.clip(labels._dilate(reg, 1), 0, 1)))
    g = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    fill = np.array([255, 70, 40], np.float32) * (1 - g) + np.array([180, 10, 20], np.float32) * g
    img[..., :3] = img[..., :3] * (1 - reg[..., None]) + fill * reg[..., None]
    img[..., 3] = np.maximum(img[..., 3], reg * 255)
    # MARIO KART, one colour per letter
    cols = [(230, 40, 40), (255, 200, 30), (60, 190, 60), (40, 120, 240), (250, 140, 30), None,
            (230, 40, 40), (255, 200, 30), (60, 190, 60), (40, 120, 240)]
    text = "MARIO KART"
    lh, lw = int(h * 0.44), int(w * 0.94)
    full = labels.text_mask(text, lw, lh, "lucky")
    row = np.zeros((h, w), np.float32)
    ry, rx = int(h * 0.03), (w - lw) // 2
    row[ry:ry + lh, rx:rx + lw] = full
    labels._over(img, (255, 255, 255), np.clip(labels._dilate(row, 3), 0, 1))
    labels._over(img, (20, 10, 10), np.clip(labels._dilate(row, 2), 0, 1))
    xs = np.nonzero(row.max(0) > 0.3)[0]
    # split letters by empty columns
    groups, start = [], xs[0]
    for a, b in zip(xs[:-1], xs[1:]):
        if b - a > 1:
            groups.append((start, a + 1))
            start = b
    groups.append((start, xs[-1] + 1))
    letters = [c for c in cols if c is not None]
    for k, (a, b) in enumerate(groups):
        c = np.asarray(letters[k % len(letters)], np.float32)
        seg = np.zeros_like(row)
        seg[:, a:b] = row[:, a:b]
        shade = (1.15 - 0.4 * g)                               # (h, 1, 1)
        img[..., :3] = img[..., :3] * (1 - seg[..., None]) + np.clip(c[None, None, :] * shade, 0, 255) * seg[..., None]
        img[..., 3] = np.maximum(img[..., 3], seg * 255)
    return np.clip(img, 0, 255).astype(np.uint8)


def logo_hook(path, d):
    if path == "textures/standalone/logo_mario_kart_64.rgba32.png":
        return title_logo(d["w"], d["h"])
    return None


HOOKS.insert(0, logo_hook)


def lakitu_hook(path, d):
    from games.mk64 import icons
    return icons.lakitu_hook(path, d)


HOOKS.insert(0, lakitu_hook)
