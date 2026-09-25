"""Title-screen illustrations composed from our own kart renders (kartrender) over painted scenes.

    scene(name, w, h) -> RGBA uint8
"""
import numpy as np

from games.mk64 import kartrender as K


def _noise(w, h, seed, cell):
    rng = np.random.default_rng(seed)
    lat = rng.random((h // cell + 3, w // cell + 3))
    ys, xs = np.arange(h) / cell, np.arange(w) / cell
    y0, x0 = ys.astype(int), xs.astype(int)
    fy, fx = (ys - y0)[:, None], (xs - x0)[None, :]
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    return (lat[y0][:, x0] * (1 - fx) + lat[y0][:, x0 + 1] * fx) * (1 - fy) + \
        (lat[y0 + 1][:, x0] * (1 - fx) + lat[y0 + 1][:, x0 + 1] * fx) * fy


def _fbm(w, h, seed):
    return sum(_noise(w, h, seed + i, max(2, 64 >> i)) * (0.5 ** i) for i in range(5)) / 1.9


def _paste(img, spr, x, y):
    h, w = spr.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(img.shape[1], x + w), min(img.shape[0], y + h)
    if x1 <= x0 or y1 <= y0:
        return
    s = spr[y0 - y:y1 - y, x0 - x:x1 - x]
    a = s[..., 3:4] / 255.0
    img[y0:y1, x0:x1, :3] = img[y0:y1, x0:x1, :3] * (1 - a) + s[..., :3] * a


def sky_scene(w, h, top, bottom, clouds=True, sun=None, seed=1):
    y = np.linspace(0, 1, h)[:, None, None]
    img = np.zeros((h, w, 4), np.float32)
    img[..., :3] = np.asarray(top, np.float32) * (1 - y) + np.asarray(bottom, np.float32) * y
    img[..., 3] = 255
    if sun:
        cx, cy, r, col = sun
        yy, xx = np.mgrid[0:h, 0:w]
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        glow = np.clip(1 - d / (r * 4), 0, 1) ** 2
        img[..., :3] += glow[..., None] * np.array([90, 60, 10])
        img[d < r, :3] = col
    if clouds:
        n = _fbm(w, h, seed)
        m = np.clip((n - 0.52) * 5, 0, 1) * np.linspace(1, 0.2, h)[:, None]
        img[..., :3] = img[..., :3] * (1 - m[..., None]) + 250 * m[..., None]
    return img


def ground(img, horizon, color, color2, seed):
    h, w = img.shape[:2]
    n = _fbm(w, h, seed)
    yy = np.arange(h)[:, None]
    m = (yy > horizon + (n[:, :1] - 0.5) * 6)
    g = np.asarray(color, np.float32) * (0.8 + 0.4 * n[..., None]) * 0.6 + np.asarray(color2, np.float32) * 0.4
    img[..., :3] = np.where(m[..., None], g, img[..., :3])


def road(img, horizon, color=(120, 120, 130)):
    h, w = img.shape[:2]
    for y in range(horizon, h):
        t = (y - horizon) / max(1, h - horizon)
        half = int(20 + t * w * 0.9)
        cx = int(w * 0.62 - t * w * 0.1)
        x0, x1 = max(0, cx - half), min(w, cx + half)
        img[y, x0:x1, :3] = np.asarray(color) * (0.8 + 0.2 * t)
        for edge in (x0, x1 - 1):
            if 0 <= edge < w:
                img[y, max(0, edge - 2):edge + 3, :3] = (230, 40, 40) if (y // 6) % 2 else (245, 245, 245)


def hill(img, cx, cy, rx, ry, col, seed):
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    m = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 < 1
    n = _fbm(w, h, seed)
    shade = 0.75 + 0.35 * n - 0.25 * ((yy - (cy - ry)) / (2 * ry)).clip(0, 1)
    img[m, :3] = (np.asarray(col) * shade[..., None])[m]


def scene(name, w, h):
    if name == "background_blue_sky":
        img = sky_scene(w, h, (40, 90, 230), (150, 200, 255), seed=11)
        hz = int(h * 0.55)
        hill(img, int(w * 0.18), hz + 10, int(w * 0.3), int(h * 0.3), (60, 160, 60), 3)
        ground(img, hz, (80, 170, 70), (60, 140, 60), 5)
        road(img, hz)
        karts = [("toad", 158, 8, 58, 262, 88), ("peach", 160, 8, 70, 222, 86), ("bowser", 150, 8, 104, 100, 92),
                 ("wario", 140, 6, 132, 10, 106), ("mario", 165, 6, 158, 150, 90)]
    else:
        img = sky_scene(w, h, (120, 70, 90), (255, 190, 90), clouds=False, sun=(int(w * 0.35), int(h * 0.38), 14, (255, 250, 200)), seed=21)
        hz = int(h * 0.5)
        ground(img, hz, (150, 100, 50), (110, 70, 40), 7)
        karts = [("peach", 150, 8, 60, 150, 70), ("mario", 150, 6, 64, 250, 78), ("luigi", 158, 8, 80, 100, 96),
                 ("yoshi", 145, 6, 110, 0, 104), ("donkeykong", 160, 6, 150, 150, 86)]
    for ch, yaw, pitch, size, x, y in karts:
        spr = K.render_view(ch, yaw, pitch, size)
        _paste(img, spr, x, y)
    return np.clip(img, 0, 255).astype(np.uint8)
