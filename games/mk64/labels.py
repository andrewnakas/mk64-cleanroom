"""Re-typeset text-bearing textures with our own fonts (games/mk64/fonts, OFL/Apache).

A label = words (from the decomp's symbol names / the game's own strings) +
a style: font, fill gradient, outline, panel. The kept colour grid supplies
the panel colours; letter shapes are never taken from the ROM.

    render(label, w, h, base_rgba) -> (h, w, 4) uint8
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
FACES = {"lucky": "LuckiestGuy-Regular.ttf", "lilita": "LilitaOne-Regular.ttf",
         "pixel": "PressStart2P-Regular.ttf", "sans": "Rubik.ttf"}
SS = 4                                                     # supersampling

STYLES = {
    # fill top, fill bottom, outline, outline px, panel (None = keep grid), border
    "course_title": dict(font="lucky", top=(250, 240, 80), bot=(250, 240, 80), outline=(10, 10, 20), ow=1,
                         panel=(16, 22, 60), border=None, crisp=True),
    "big_title": dict(font="lucky", top=(250, 236, 66), bot=(250, 126, 24), outline=(22, 12, 2), ow=2,
                      panel=(0, 0, 0), border=None),
    "big_title_green": dict(font="lucky", top=(200, 255, 80), bot=(40, 190, 40), outline=(10, 30, 10), ow=2,
                            panel=(0, 0, 0), border=None),
    "button": dict(font="lucky", top=(255, 210, 60), bot=(255, 210, 60), outline=(60, 10, 0), ow=1,
                   panel=(150, 40, 20), border=(90, 20, 10), crisp=True),
    "cup": dict(font="lilita", top=(255, 255, 255), bot=(255, 230, 150), outline=(40, 0, 30), ow=1,
                panel=None, border=None, text_frac=0.34, valign="bottom"),
    "menu_game": dict(font="lilita", top=(255, 255, 255), bot=(255, 240, 120), outline=(0, 40, 0), ow=1,
                      panel=None, border=None, text_frac=0.34, valign="bottom"),
    "mode": dict(font="lilita", top=(255, 150, 220), bot=(200, 60, 170), outline=(30, 0, 30), ow=1,
                 panel=None, border=None, icon_left=True),
    "name_plate": dict(font="lilita", top=(40, 40, 50), bot=(20, 20, 30), outline=None, ow=0,
                       panel=(185, 185, 195), border=(110, 110, 120)),
    "ghost": dict(font="lucky", top=(235, 235, 255), bot=(235, 235, 255), outline=(20, 20, 60), ow=1,
                  panel=(60, 50, 120), border=(30, 20, 70), crisp=True),
    "hud": dict(font="lucky", top=(255, 245, 120), bot=(255, 170, 40), outline=(20, 10, 0), ow=1,
                panel=(0, 0, 0, 0), border=None),
    "white": dict(font="lucky", top=(255, 255, 255), bot=(230, 230, 230), outline=(0, 0, 0), ow=1,
                  panel=(0, 0, 0, 0), border=None),
    "msg": dict(font="sans", top=(255, 255, 255), bot=(255, 255, 255), outline=None, ow=0, panel=(0, 0, 0, 0), border=None,
                crisp=True),
    "sign": dict(font="lucky", top=None, bot=None, outline=None, ow=1, panel=None, border=None),
    "push_start": dict(font="lucky", top=(120, 220, 255), bot=(40, 110, 255), outline=(0, 0, 40), ow=1,
                       panel=(0, 0, 0, 0), border=None),
}


def _font(name, px):
    return ImageFont.truetype(os.path.join(FONTS, FACES[name]), max(4, int(px)))


def text_mask(text, w, h, font="lucky", tracking=0.02):
    """Coverage mask (h, w) float in [0,1]: text fitted into w x h (squeezed, never cropped)."""
    W, H = w * SS, h * SS
    size = H
    f = _font(font, size)
    lines = text.split("\n")
    for _ in range(40):
        f = _font(font, size)
        boxes = [f.getbbox(l) for l in lines]
        lh = max(b[3] - b[1] for b in boxes)
        th = lh * len(lines) + (len(lines) - 1) * size * 0.12
        if th <= H * 0.98:
            break
        size *= 0.93
    tw = max(b[2] - b[0] for b in boxes) + int(size * tracking * max(len(l) for l in lines))
    canvas = Image.new("L", (max(tw, 1) + 8 * SS, int(th) + 8 * SS), 0)
    d = ImageDraw.Draw(canvas)
    y = 4 * SS
    for l, b in zip(lines, boxes):
        lw = b[2] - b[0] + int(size * tracking * len(l))
        x = 4 * SS + (tw - lw) // 2
        for ch in l:
            d.text((x - f.getbbox(ch)[0] if ch != " " else x, y - b[1]), ch, font=f, fill=255)
            x += f.getlength(ch) + size * tracking
        y += lh + size * 0.12
    bb = canvas.getbbox() or (0, 0, 1, 1)
    canvas = canvas.crop(bb)
    cw, chh = canvas.size
    scale = min(W / cw, H / chh)
    nw, nh = max(1, int(cw * min(scale, W / cw))), max(1, int(chh * scale))
    if nw > W:
        nw = W
    canvas = canvas.resize((nw, nh), Image.LANCZOS)
    full = Image.new("L", (W, H), 0)
    full.paste(canvas, ((W - nw) // 2, (H - nh) // 2))
    m = np.asarray(full.resize((w, h), Image.BOX), np.float32) / 255.0
    return np.clip(m * 1.15, 0, 1)


def _dilate(m, r):
    img = Image.fromarray((m * 255).astype(np.uint8))
    for _ in range(r):
        img = img.filter(ImageFilter.MaxFilter(3))
    return np.asarray(img, np.float32) / 255.0


def _over(dst, rgb, a):
    a = a[..., None]
    dst[..., :3] = dst[..., :3] * (1 - a) + np.asarray(rgb, np.float32)[:3] * a
    dst[..., 3] = np.maximum(dst[..., 3], a[..., 0] * 255)


def render(label, w, h, base=None):
    """label: {"text": str, "style": name, overrides...}; base: digest RGBA for panel colours."""
    st = dict(STYLES[label.get("style", "course_title")])
    st.update({k: v for k, v in label.items() if k not in ("text", "style")})
    img = np.zeros((h, w, 4), np.float32)
    panel = st.get("panel")
    if panel is None and base is not None:
        img[:] = base.astype(np.float32)
        if (img[..., 3] < 255).any() and not st.get("keep_alpha", False):
            img[..., 3] = 255
    elif panel is not None:
        img[..., :3] = panel[:3]
        img[..., 3] = panel[3] if len(panel) > 3 else 255
    if st.get("top") is None:
        lum = float((img[..., :3] * [0.3, 0.59, 0.11]).sum(-1).mean())
        dark = lum > 140
        st["top"] = st["bot"] = (20, 20, 30) if dark else (255, 255, 255)
        if st.get("outline") is None and st.get("ow"):
            st["outline"] = (255, 255, 255) if dark else (20, 20, 30)
    if st.get("border") and w > 8 and h > 6:
        b = st["border"]
        img[0, :, :3] = img[-1, :, :3] = b
        img[:, 0, :3] = img[:, -1, :3] = b
    # text box
    pad_x, pad_y = max(1, w // 40), max(1, h // 10)
    x0, y0, x1, y1 = pad_x, pad_y, w - pad_x, h - pad_y
    tf = st.get("text_frac")
    if tf:
        th = max(5, int(h * tf))
        y0, y1 = (h - th - 1, h - 1) if st.get("valign") == "bottom" else (1, 1 + th)
    if st.get("icon_left"):
        x0 = min(w - 4, h + 1)
    ow = st.get("ow", 0)
    tw, th = x1 - x0 - 2 * ow, y1 - y0 - 2 * ow
    if tw < 3 or th < 3:
        return np.clip(img, 0, 255).astype(np.uint8)
    m = np.zeros((h, w), np.float32)
    m[y0 + ow:y0 + ow + th, x0 + ow:x0 + ow + tw] = text_mask(label["text"], tw, th, st["font"])
    if st.get("crisp"):
        m = (m >= 0.45).astype(np.float32)
    if ow and st.get("outline") is not None:
        _over(img, st["outline"], np.clip(_dilate(m, ow), 0, 1))
    g = np.linspace(0, 1, h, dtype=np.float32)
    g = np.clip((g - y0 / h) / max(1e-3, (y1 - y0) / h), 0, 1)[:, None, None]
    fill = np.asarray(st["top"], np.float32) * (1 - g) + np.asarray(st["bot"], np.float32) * g
    a = m[..., None]
    img[..., :3] = img[..., :3] * (1 - a) + fill * a
    img[..., 3] = np.maximum(img[..., 3], m * 255)
    if st.get("crisp"):                            # 1-bit coverage: sharp small text that compresses well
        on = img[..., 3] >= 110
        img[..., 3] = on * 255
        img[..., :3] = np.where(on[..., None], img[..., :3], 0)
    return np.clip(img, 0, 255).astype(np.uint8)
