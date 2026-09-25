"""HUD widgets, item icons, portraits and emblems drawn from our own descriptions.

Each hook matches slots by name (the decomp's symbols say what they show) and
draws at the slot size. i4/ia textures: white shapes, intensity = coverage.
"""
import re

import numpy as np
from PIL import Image, ImageDraw

from games.mk64 import labels
from games.mk64.drawn import head, emblem, CHAR

SS = 4
OL = (25, 15, 10, 255)


def _cv(w, h):
    im = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def _out(im, w, h):
    return np.asarray(im.resize((w, h), Image.LANCZOS), np.float32)


def shell(d, cx, cy, r, col):
    d.ellipse([cx - r, cy - r * 0.85, cx + r, cy + r * 0.85], fill=(250, 245, 230, 255), outline=OL, width=SS)
    d.chord([cx - r, cy - r * 0.95, cx + r, cy + r * 0.6], 180, 360, fill=col + (255,), outline=OL, width=SS)
    for k in (-0.5, 0, 0.5):
        d.ellipse([cx + k * r - r * 0.18, cy - r * 0.62, cx + k * r + r * 0.18, cy - r * 0.3], fill=(250, 245, 230, 255))
    if col == (40, 90, 230):                                  # spiny shell: wings
        for sx in (-1, 1):
            d.ellipse([cx + sx * r * 0.9 - r * 0.35, cy - r * 0.9, cx + sx * r * 0.9 + r * 0.35, cy - r * 0.35],
                      fill=(255, 255, 255, 255), outline=OL, width=SS)


def mushroom(d, cx, cy, r, cap=(230, 30, 30)):
    d.rectangle([cx - r * 0.38, cy, cx + r * 0.38, cy + r * 0.85], fill=(255, 235, 200, 255), outline=OL, width=SS)
    d.chord([cx - r, cy - r * 0.9, cx + r, cy + r * 0.45], 180, 360, fill=cap + (255,), outline=OL, width=SS)
    for sx, sy in ((0, -0.55), (-0.62, -0.2), (0.62, -0.2)):
        d.ellipse([cx + (sx - 0.22) * r, cy + (sy - 0.2) * r, cx + (sx + 0.22) * r, cy + (sy + 0.2) * r], fill=(255, 255, 255, 255))
    for sx in (-1, 1):
        d.ellipse([cx + sx * r * 0.14 - r * 0.07, cy + r * 0.2, cx + sx * r * 0.14 + r * 0.07, cy + r * 0.5], fill=(20, 20, 20, 255))


def banana(d, cx, cy, r):
    """Curved banana: a thick crescent with a dark outline and a brown stem."""
    box = [cx - r * 1.1, cy - r * 1.3, cx + r * 1.1, cy + r * 0.9]
    d.arc(box, 25, 155, fill=OL, width=int(r * 0.62))
    inner = [box[0] + r * 0.08, box[1] + r * 0.08, box[2] - r * 0.08, box[3] - r * 0.08]
    d.arc(inner, 28, 152, fill=(255, 225, 40, 255), width=int(r * 0.46))
    d.arc([inner[0] + r * 0.25, inner[1] + r * 0.25, inner[2] - r * 0.25, inner[3] - r * 0.25], 40, 140,
          fill=(255, 245, 150, 255), width=int(r * 0.12))
    sx, sy = cx + r * 1.02, cy + r * 0.12
    d.rectangle([sx - r * 0.12, sy - r * 0.25, sx + r * 0.12, sy + r * 0.05], fill=(110, 70, 20, 255))


def star(d, cx, cy, r, col=(255, 225, 40)):
    pts = []
    for k in range(10):
        a = np.pi * k / 5 - np.pi / 2
        rr = r if k % 2 == 0 else r * 0.46
        pts.append((cx + np.cos(a) * rr, cy + np.sin(a) * rr))
    d.polygon(pts, fill=col + (255,), outline=OL)
    for sx in (-1, 1):
        d.ellipse([cx + sx * r * 0.18 - r * 0.07, cy - r * 0.2, cx + sx * r * 0.18 + r * 0.07, cy + r * 0.12], fill=(20, 20, 20, 255))


def bolt(d, cx, cy, r):
    pts = [(cx + r * 0.3, cy - r), (cx - r * 0.5, cy + r * 0.1), (cx - r * 0.05, cy + r * 0.1), (cx - r * 0.35, cy + r),
           (cx + r * 0.55, cy - r * 0.2), (cx + r * 0.05, cy - r * 0.2)]
    d.polygon(pts, fill=(255, 240, 60, 255), outline=OL)


def boo(d, cx, cy, r):
    d.ellipse([cx - r, cy - r, cx + r, cy + r * 0.9], fill=(250, 250, 255, 255), outline=OL, width=SS)
    for sx in (-1, 1):
        d.ellipse([cx + sx * r * 0.32 - r * 0.1, cy - r * 0.4, cx + sx * r * 0.32 + r * 0.1, cy - r * 0.05], fill=(20, 20, 20, 255))
    d.chord([cx - r * 0.45, cy - r * 0.05, cx + r * 0.45, cy + r * 0.6], 0, 180, fill=(200, 40, 60, 255))


def item_box(d, cx, cy, r, fake=False):
    d.rounded_rectangle([cx - r, cy - r, cx + r, cy + r], radius=r * 0.2, fill=(120, 170, 255, 200) if not fake else (255, 120, 120, 220),
                        outline=OL, width=SS)
    return "?" if not fake else "?"


ITEM = {
    "banana": lambda d, W, H: banana(d, W / 2, H / 2, H * 0.4),
    "banana_bunch": lambda d, W, H: [banana(d, W / 2 + dx * H * 0.18, H / 2 + dy * H * 0.12, H * 0.28)
                                     for dx, dy in ((-1, 0.6), (1, 0.6), (0, -0.6), (-1.5, -0.3), (1.5, -0.3))],
    "green_shell": lambda d, W, H: shell(d, W / 2, H / 2, H * 0.4, (40, 170, 60)),
    "red_shell": lambda d, W, H: shell(d, W / 2, H / 2, H * 0.4, (220, 30, 30)),
    "blue_shell": lambda d, W, H: shell(d, W / 2, H / 2, H * 0.36, (40, 90, 230)),
    "triple_green_shell": lambda d, W, H: [shell(d, W / 2 + dx * H * 0.3, H / 2 + dy * H * 0.18, H * 0.24, (40, 170, 60))
                                           for dx, dy in ((0, -1), (-1, 0.8), (1, 0.8))],
    "triple_red_shell": lambda d, W, H: [shell(d, W / 2 + dx * H * 0.3, H / 2 + dy * H * 0.18, H * 0.24, (220, 30, 30))
                                         for dx, dy in ((0, -1), (-1, 0.8), (1, 0.8))],
    "mushroom": lambda d, W, H: mushroom(d, W / 2, H / 2, H * 0.4),
    "double_mushroom": lambda d, W, H: [mushroom(d, W / 2 + dx * H * 0.3, H / 2, H * 0.3) for dx in (-1, 1)],
    "triple_mushroom": lambda d, W, H: [mushroom(d, W / 2 + dx * H * 0.32, H / 2 + dy * H * 0.15, H * 0.26)
                                        for dx, dy in ((0, -1), (-1, 0.9), (1, 0.9))],
    "super_mushroom": lambda d, W, H: mushroom(d, W / 2, H / 2, H * 0.42, cap=(250, 200, 30)),
    "star": lambda d, W, H: star(d, W / 2, H / 2, H * 0.44),
    "thunder_bolt": lambda d, W, H: bolt(d, W / 2, H / 2, H * 0.42),
    "boo": lambda d, W, H: boo(d, W / 2, H / 2, H * 0.4),
    "fake_item_box": lambda d, W, H: item_box(d, W / 2, H / 2, H * 0.36, True),
    "none": lambda d, W, H: None,
}


def item_window(kind, w, h):
    im, d = _cv(w, h)
    W, H = w * SS, h * SS
    ITEM[kind](d, W, H)
    img = _out(im, w, h)
    if kind == "fake_item_box":
        m = labels.text_mask("?", int(h * 0.5), int(h * 0.55), "lucky")
        _stamp(img, m, (255, 255, 255), w // 2 - m.shape[1] // 2, h // 2 - m.shape[0] // 2)
    return img


def _stamp(img, m, rgb, x0, y0):
    mh, mw = m.shape
    reg = img[y0:y0 + mh, x0:x0 + mw]
    a = m[:reg.shape[0], :reg.shape[1], None]
    reg[..., :3] = reg[..., :3] * (1 - a) + np.asarray(rgb, np.float32) * a
    reg[..., 3] = np.maximum(reg[..., 3], a[..., 0] * 255)


def white_text(text, w, h, font="lucky"):
    """i4/ia slot: white glyphs, intensity = coverage."""
    m = labels.text_mask(text, w - 2, h - 2, font)
    img = np.zeros((h, w, 4), np.float32)
    img[1:h - 1, 1:w - 1] = (m * 255)[..., None]
    return img


def place_graphic(n, w, h):
    """'1st'... big italic numeral + small suffix, white on transparent (i4)."""
    suf = {1: "st", 2: "nd", 3: "rd"}.get(n, "th")
    img = np.zeros((h, w, 4), np.float32)
    big = labels.text_mask(str(n), int(w * 0.42), int(h * 0.92), "lucky")
    small = labels.text_mask(suf, int(w * 0.44), int(h * 0.45), "lucky")
    img[int(h * 0.04):int(h * 0.04) + big.shape[0], int(w * 0.04):int(w * 0.04) + big.shape[1]] = (big * 255)[..., None]
    y0 = int(h * 0.5)
    x0 = int(w * 0.5)
    reg = img[y0:y0 + small.shape[0], x0:x0 + small.shape[1]]
    reg[:] = np.maximum(reg, (small[:reg.shape[0], :reg.shape[1]] * 255)[..., None])
    # italic shear
    out = np.zeros_like(img)
    for y in range(h):
        dx = int(round((h - 1 - y) * 0.22))
        out[y, dx:] = img[y, :w - dx] if dx else img[y]
    return out


def hud_label(text, w, h, top, bot):
    return labels.render({"text": text, "style": "hud", "top": top, "bot": bot, "panel": (0, 0, 0, 0)}, w, h).astype(np.float32)


def digit_strip(chars, cell, h, top=(255, 245, 90), bot=(255, 110, 20)):
    img = np.zeros((h, cell * len(chars), 4), np.float32)
    for i, c in enumerate(chars):
        img[:, i * cell:(i + 1) * cell] = labels.render({"text": c, "style": "hud", "top": top, "bot": bot,
                                                         "panel": (0, 0, 0, 0)}, cell, h)
    return img


PORTRAIT = {"mario": "mario", "luigi": "luigi", "peach": "peach", "toad": "toad", "yoshi": "yoshi",
            "donkey_kong": "dk", "wario": "wario", "bowser": "bowser"}
PLAYER_COL = {1: (40, 120, 255), 2: (230, 40, 40), 3: (255, 150, 20), 4: (40, 190, 60)}


def _grid_cols(d):
    g = np.asarray(d["grid"], np.float32)
    lum = g[:, :3] @ [0.3, 0.59, 0.11]
    return g[lum.argmax(), :3], g[lum.argmin(), :3]


def _alpha(d, img):
    if "alpha2" in d:
        from cleanroom.decomp.gen import unpack_alpha2
        img[..., 3] = (unpack_alpha2(d["alpha2"], d["w"], d["h"]) >= 128) * 255
    return img


def soft_shadow(w, h, half=False):
    """i4/i8 slot: soft dark ellipse (intensity carries the shape)."""
    yy, xx = np.indices((h, w)).astype(np.float32)
    cy = (h - 1) if half else (h - 1) / 2
    ry = h if half else h / 2
    r = np.sqrt(((xx - (w - 1) / 2) / (w / 2)) ** 2 + ((yy - cy) / ry) ** 2)
    v = np.clip(1.15 - r, 0, 1) ** 0.8 * 200
    img = np.zeros((h, w, 4), np.float32)
    img[...] = v[..., None]
    return img


def hook(path, d):
    w, h = d["w"], d["h"]
    b = path.rsplit("/", 1)[-1]
    if b == "kart_shadow.i8.png":
        return soft_shadow(w, h)
    if b == "common_shadow_i4.i4.inc.c":                    # stored as the top half of a round shadow
        return soft_shadow(w, h, half=True)
    if b.startswith(("checkerboard_", "checkerbord_", "gray_checkerboard")):      # a real checkerboard
        hi, lo = _grid_cols(d)
        c = max(2, min(w, h) // 4)
        yy, xx = np.indices((h, w))
        img = np.zeros((h, w, 4), np.float32)
        img[..., :3] = np.where((((yy // c) + (xx // c)) % 2 == 0)[..., None], hi, lo)
        img[..., 3] = 255
        return _alpha(d, img)
    if re.match(r"gTexture(Gold|GreenGold|White|Pink)(Bar|Stripe)\.", b):          # menu bars: horizontal bands
        from cleanroom.decomp.gen import upsample_grid
        n = int(round(len(d["grid"]) ** 0.5))
        img = upsample_grid(d["grid"], n, w, h).mean(1, keepdims=True).repeat(w, 1)
        img[..., :3] = np.round(img[..., :3] / 8) * 8
        img[..., 3] = 255
        return img
    m = re.match(r"gTextureBoo(\d+)\.png$", b)
    if m:                                                   # Boo ghost frames (banshee boardwalk)
        k = int(m.group(1))
        im, dd = _cv(w, h)
        W, H = w * SS, h * SS
        boo(dd, W / 2, H / 2 + np.sin(k * 0.6) * H * 0.03, min(W, H) * 0.42)
        return _out(im, w, h)
    m = re.match(r"common_texture_item_window_(\w+)\.ci8\.inc\.c$", b)
    if m and m.group(1) in ITEM:
        return item_window(m.group(1), w, h)
    m = re.match(r"common_texture_hud_(\d)(st|nd|rd|th)\.i4\.inc\.c$", b)
    if m:
        return place_graphic(int(m.group(1)), w, h)
    m = re.match(r"common_texture_portrait_(\w+)\.ci8\.inc\.c$", b)
    if m:
        k = m.group(1)
        img = np.zeros((h, w, 4), np.float32)
        img[..., :3] = (20, 40, 90)
        img[..., 3] = 255
        if k in PORTRAIT:
            hd = head(PORTRAIT[k], w, h)
        elif k == "bomb_kart":
            hd = emblem("bomb", w, h)
        else:
            hd = np.zeros((h, w, 4), np.float32)
            q = labels.text_mask("?", int(w * 0.6), int(h * 0.8), "lucky")
            _stamp(hd, q, (255, 230, 60), (w - q.shape[1]) // 2, (h - q.shape[0]) // 2)
        a = hd[..., 3:4] / 255
        img[..., :3] = img[..., :3] * (1 - a) + hd[..., :3] * a
        return img
    m = re.match(r"common_texture_player_emblem_(\d)p\.ci8\.inc\.c$", b)
    if m:
        n = int(m.group(1))
        return labels.render({"text": f"{n}P", "style": "hud", "top": (255, 255, 255), "bot": PLAYER_COL[n],
                              "outline": (10, 10, 30), "ow": 2, "panel": (0, 0, 0, 0)}, w, h).astype(np.float32)
    m = re.match(r"common_texture_minimap_kart_(\w+)\.rgba16\.inc\.c$", b)
    if m:
        k = PORTRAIT.get(m.group(1), m.group(1))
        col = CHAR.get(k, {}).get("cap", (255, 255, 255))
        im, dd = _cv(w, h)
        dd.ellipse([SS * 0.5, SS * 0.5, w * SS - SS * 0.5, h * SS - SS * 0.5], fill=tuple(col) + (255,), outline=(0, 0, 0, 255), width=SS)
        return _out(im, w, h)
    if b == "common_texture_hud_normal_digit.rgba16.inc.c":
        return digit_strip(list("0123456789") + ["'", "\"", "!"], w // 13, h)
    if b == "common_texture_hud_123.rgba16.inc.c":
        return digit_strip(list("123/"), w // 4, h, (255, 170, 255), (180, 90, 220))
    if b == "common_texture_hud_lap.rgba16.inc.c":
        return hud_label("LAP", w, h, (255, 170, 255), (170, 90, 220))
    m = re.match(r"common_texture_hud_lap_(\d)_on_3\.rgba16\.inc\.c$", b)
    if m:
        return hud_label(f"{m.group(1)}/3", w, h, (255, 190, 255), (200, 100, 230))
    if b == "common_texture_hud_time.rgba16.inc.c":
        return hud_label("TIME", w, h, (230, 255, 90), (90, 200, 40))
    if b == "common_texture_hud_total_time.rgba16.inc.c":
        return hud_label("TOTAL", w, h, (230, 255, 90), (90, 200, 40))
    if b == "common_texture_hud_lap_time.rgba16.inc.c":
        return hud_label("LAP", w, h, (230, 255, 90), (90, 200, 40))
    m = re.match(r"common_texture_hud_type_C_rank_(tiny_)?font_(\d)\.ci8\.inc\.c$", b)
    if m:
        return hud_label(m.group(2), w, h, (255, 245, 90), (255, 120, 20))
    if b == "common_texture_item_box_question_mark.rgba16.inc.c":
        img = np.zeros((h, w, 4), np.float32)
        q = labels.text_mask("?", w - 4, h // 2 - 4, "lucky")
        for k in range(2):                                   # two stacked frames
            _stamp(img, q, (255, 220, 40), 2, k * (h // 2) + 2)
        return img
    if b in ("common_texture_banana.rgba16.inc.c", "common_texture_flat_banana.rgba16.inc.c"):
        im, dd = _cv(w, h)
        W, H = w * SS, h * SS
        if "flat" in b:
            dd.polygon([(W * 0.05, H * 0.9), (W * 0.45, H * 0.35), (W * 0.5, H * 0.1), (W * 0.55, H * 0.35), (W * 0.95, H * 0.9),
                        (W * 0.5, H * 0.6)], fill=(255, 225, 40, 255), outline=OL)
        else:
            banana(dd, W / 2, H / 2, H * 0.42)
        return _out(im, w, h)
    if b == "common_texture_character_portrait_border.ia4.inc.c":
        img = np.zeros((h, w, 4), np.float32)
        img[:2], img[-2:], img[:, :2], img[:, -2:] = 255, 255, 255, 255
        return img
    m = re.match(r"common_texture_traffic_light_(\d+)\.ci8\.inc\.c$", b)
    if m:
        k = int(m.group(1))
        im, dd = _cv(w, h)
        W, H = w * SS, h * SS
        dd.rounded_rectangle([W * 0.1, H * 0.02, W * 0.9, H * 0.98], radius=W * 0.15, fill=(40, 40, 50, 255), outline=OL, width=SS)
        lit = {1: 0, 2: 0, 3: 0, 4: 1, 5: 1, 6: 1, 7: 2, 8: 2, 9: 2, 10: 2}.get(k, -1)   # red -> red -> blue
        for i in range(3):
            cy = H * (0.2 + 0.3 * i)
            on = i <= lit if lit < 2 else i == 2
            col = ((255, 60, 40) if i < 2 else (80, 170, 255)) if on else (80, 80, 90)
            dd.ellipse([W / 2 - W * 0.28, cy - W * 0.28, W / 2 + W * 0.28, cy + W * 0.28], fill=col + (255,))
        return _out(im, w, h)
    return None


# ---------------------------------------------------------------- Lakitu
LAKITU_SIGN = {"reverse": ("REVERSE", (230, 40, 60)), "finallap": ("FINAL LAP", (40, 80, 230)),
               "secondlap": ("LAP 2", (40, 80, 230))}
LAKITU_N = {"reverse": 16, "finallap": 16, "secondlap": 16, "checkeredflag": 32, "redlights": 16, "bluelight": 8,
            "nolights": 8, "fishing": 4}


def lakitu_body(d, cx, top, s):
    """Cloud rider: white cloud puffs, shell-yellow head with round goggles, one arm raised."""
    ol = OL
    for dx, dy, r in ((-0.55, 0.55, 0.32), (0.55, 0.55, 0.32), (0, 0.62, 0.38), (-0.25, 0.45, 0.3), (0.25, 0.45, 0.3)):
        d.ellipse([cx + (dx - r) * s, top + (dy - r) * s, cx + (dx + r) * s, top + (dy + r) * s], fill=(250, 250, 255, 255),
                  outline=(150, 160, 190, 255), width=max(1, SS // 2))
    d.ellipse([cx - 0.3 * s, top + 0.02 * s, cx + 0.3 * s, top + 0.52 * s], fill=(250, 210, 40, 255), outline=ol, width=SS)
    d.ellipse([cx - 0.34 * s, top + 0.33 * s, cx + 0.34 * s, top + 0.58 * s], fill=(90, 190, 90, 255), outline=ol, width=SS)
    for sx in (-1, 1):
        ex = cx + sx * 0.12 * s
        d.ellipse([ex - 0.1 * s, top + 0.14 * s, ex + 0.1 * s, top + 0.32 * s], fill=(255, 255, 255, 255), outline=ol, width=SS)
        d.ellipse([ex - 0.035 * s, top + 0.2 * s, ex + 0.035 * s, top + 0.27 * s], fill=(20, 20, 20, 255))


def lakitu(group, k, w, h):
    im, d = _cv(w, h)
    W, H = w * SS, h * SS
    n = LAKITU_N.get(group, 16)
    t = (k - 1) / max(1, n - 1)
    glow = 0.35 + 0.65 * abs(np.sin(np.pi * t * 2))
    if group in LAKITU_SIGN:                                   # landscape: body top-centre, sign below
        s = H * 0.62
        lakitu_body(d, W / 2, H * 0.02, s)
        text, col = LAKITU_SIGN[group]
        sy0, sy1 = H * 0.58, H * 0.97
        c = tuple(int(v * glow + 25 * (1 - glow)) for v in col) + (255,)
        d.rounded_rectangle([W * 0.04, sy0, W * 0.96, sy1], radius=H * 0.06, fill=c, outline=OL, width=SS)
        img = _out(im, w, h)
        m = labels.text_mask(text, int(w * 0.84), int(h * 0.3), "lucky")
        _stamp(img, m, (255, 255, 255), int(w * 0.08), int(h * 0.62))
        return img
    s = min(W, H) * 0.7
    lakitu_body(d, W * 0.42, H * 0.3, s)
    rx = W * 0.8
    d.line([rx, H * 0.08, rx, H * 0.72], fill=(90, 70, 50, 255), width=SS * 2)     # the pole he holds
    if group == "checkeredflag":
        wave = np.sin(np.pi * 2 * t)
        cell = W * 0.08
        for j in range(4):
            for i in range(3):
                x0 = rx - (i + 1) * cell
                y0 = H * 0.08 + j * cell + wave * cell * 0.3 * (i + 1) / 3
                d.rectangle([x0, y0, x0 + cell, y0 + cell], fill=(250, 250, 250, 255) if (i + j) % 2 else (20, 20, 20, 255))
    elif group in ("redlights", "bluelight", "nolights"):
        d.rounded_rectangle([rx - W * 0.13, H * 0.02, rx + W * 0.13, H * 0.42], radius=W * 0.05, fill=(40, 40, 50, 255), outline=OL, width=SS)
        lit = {"redlights": min(3, 1 + int(t * 3)), "bluelight": 0, "nolights": -1}[group]
        for i in range(3):
            cy = H * (0.08 + 0.115 * i)
            on = (group == "redlights" and i < lit)
            col = (255, 60, 40) if on else (80, 80, 90)
            if group == "bluelight" and i == 2:
                col = (80, 170, 255)
            d.ellipse([rx - W * 0.08, cy - W * 0.08, rx + W * 0.08, cy + W * 0.08], fill=col + (255,))
    elif group == "fishing":
        d.line([rx, H * 0.72, rx, H * 0.98], fill=(200, 200, 210, 255), width=max(1, SS // 2))
    return _out(im, w, h)


def lakitu_hook(path, d):
    m = re.match(r"assets/lakitu/(\w+)/gTextureLakitu\w*?(\d+)\.png$", path)
    if not m:
        return None
    return lakitu(m.group(1), int(m.group(2)), d["w"], d["h"])
