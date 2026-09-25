"""Kart + driver sprites rendered from our own primitive models (no ROM pixels).

Each driver is described in words-turned-shapes (ellipsoids, boxes, wheel
cylinders) with our own colours. A frame's viewing angle comes from the game's
frame tables (src/kart_dma.c + player_controller.c):
  files 0..188    9 slope groups x 21 yaw steps of 0x208 (2.86 deg) from the rear
  files 189..288  5 pitch sets x 20 yaw steps of 9 deg (0..171)
  files 289..320  32 tumble frames (end-over-end flip)
The sprite is fitted into the frame's kept 2-bit alpha outline bbox (bottom
centred), rendered toon-shaded with a dark outline. Wheel pixels are tagged so
the build's wheel palettes (0xC0..0xFF) animate the tread.

    render_frame(char, file_index, bbox) -> (rgba 64x64 uint8, wheel_mask 64x64 bool, tread 64x64 int)
"""
import math

import numpy as np

S = 2                     # supersampling
OUT = 64

# ------------------------------------------------------------ geometry

def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


class Prim:
    """kind: 'ell' (radii), 'box' (half extents), 'cyl' (radius, half width along x)."""

    def __init__(self, kind, c, size, color, R=None, wheel=False, shiny=0.0):
        self.kind, self.c, self.size = kind, np.asarray(c, float), np.asarray(size, float)
        self.color, self.R = np.asarray(color, float), (np.eye(3) if R is None else R)
        self.wheel, self.shiny = wheel, shiny


@np.errstate(all="ignore")
def intersect(p, o, d):
    """o, d: (N,3) rays in world. Returns t (N,), normal (N,3), local point (N,3)."""
    lo = (o - p.c) @ p.R          # R^T (o - c)  (row vectors)
    ld = d @ p.R
    N = len(o)
    t = np.full(N, np.inf)
    n = np.zeros((N, 3))
    if p.kind == "ell":
        r = p.size
        so, sd = lo / r, ld / r
        a = (sd * sd).sum(1)
        b = 2 * (so * sd).sum(1)
        cc = (so * so).sum(1) - 1
        disc = b * b - 4 * a * cc
        ok = disc > 0
        tt = np.where(ok, (-b - np.sqrt(np.maximum(disc, 0))) / (2 * a), np.inf)
        ok &= tt > 1e-4
        t = np.where(ok, tt, np.inf)
        lp = lo + ld * t[:, None]
        n = lp / (r * r)
    elif p.kind == "box":
        h = p.size
        with np.errstate(divide="ignore", invalid="ignore"):
            t1 = (-h - lo) / ld
            t2 = (h - lo) / ld
        tmin = np.nanmax(np.minimum(t1, t2), 1)
        tmax = np.nanmin(np.maximum(t1, t2), 1)
        ok = (tmax >= tmin) & (tmin > 1e-4)
        t = np.where(ok, tmin, np.inf)
        lp = lo + ld * t[:, None]
        q = np.abs(lp / h)
        ax = q.argmax(1)
        n = np.zeros((N, 3))
        n[np.arange(N), ax] = np.sign(lp[np.arange(N), ax])
    elif p.kind == "cyl":
        r, hw = p.size
        a = ld[:, 1] ** 2 + ld[:, 2] ** 2
        b = 2 * (lo[:, 1] * ld[:, 1] + lo[:, 2] * ld[:, 2])
        cc = lo[:, 1] ** 2 + lo[:, 2] ** 2 - r * r
        disc = b * b - 4 * a * cc
        ok = (disc > 0) & (a > 1e-12)
        ts = np.where(ok, (-b - np.sqrt(np.maximum(disc, 0))) / (2 * np.maximum(a, 1e-12)), np.inf)
        xs = lo[:, 0] + ld[:, 0] * ts
        side = ok & (np.abs(xs) <= hw) & (ts > 1e-4)
        with np.errstate(divide="ignore", invalid="ignore"):
            tc = np.where(ld[:, 0] != 0, (np.where(lo[:, 0] > 0, hw, -hw) - lo[:, 0]) / ld[:, 0], np.inf)
        yc = lo[:, 1] + ld[:, 1] * tc
        zc = lo[:, 2] + ld[:, 2] * tc
        cap = (tc > 1e-4) & (yc * yc + zc * zc <= r * r)
        t = np.where(side, ts, np.inf)
        use_cap = cap & (tc < t)
        t = np.where(use_cap, tc, t)
        lp = lo + ld * np.where(np.isfinite(t), t, 0)[:, None]
        n = np.stack([np.zeros(N), lp[:, 1], lp[:, 2]], 1)
        n[use_cap] = np.array([1.0, 0, 0]) * np.sign(lp[use_cap, 0:1])
        lp[~np.isfinite(t)] = 0
    wn = n @ p.R.T
    wn /= np.maximum(np.linalg.norm(wn, axis=1, keepdims=True), 1e-9)
    return t, wn, lp


# ------------------------------------------------------------ models

TIRE = (35, 35, 40)
METAL = (185, 190, 200)
DARK = (60, 60, 70)
SKIN = (255, 196, 150)
WHITE = (250, 250, 250)


def kart_base(body, trim, hub=(250, 205, 40), scale=1.0, bumper=None):
    """Kart in local coords: x right, y up, z forward (units ~ metres)."""
    s = scale
    P = [
        Prim("box", (0, 0.30 * s, 0.05 * s), (0.42 * s, 0.07 * s, 0.78 * s), body),              # floor pan
        Prim("box", (0, 0.40 * s, 0.62 * s), (0.30 * s, 0.10 * s, 0.22 * s), body),              # nose
        Prim("ell", (0, 0.36 * s, 0.86 * s), (0.34 * s, 0.09 * s, 0.10 * s), bumper or trim),     # front bumper
        Prim("box", (0, 0.44 * s, -0.55 * s), (0.30 * s, 0.14 * s, 0.18 * s), DARK),             # engine
        Prim("cyl", (0, 0.50 * s, -0.78 * s), (0.08 * s, 0.34 * s), METAL),                      # exhaust bar
        Prim("box", (0, 0.62 * s, -0.30 * s), (0.28 * s, 0.20 * s, 0.05 * s), trim),             # seat back
        Prim("box", (0.46 * s, 0.38 * s, 0.05 * s), (0.05 * s, 0.05 * s, 0.55 * s), trim),       # side rails
        Prim("box", (-0.46 * s, 0.38 * s, 0.05 * s), (0.05 * s, 0.05 * s, 0.55 * s), trim),
        Prim("cyl", (0, 0.62 * s, 0.32 * s), (0.12 * s, 0.025 * s), DARK, R=rot_z(math.pi / 2) @ rot_x(-0.9)),  # wheel
    ]
    for sx in (-1, 1):
        for sz, r, w in ((0.62, 0.21, 0.12), (-0.55, 0.26, 0.15)):
            P.append(Prim("cyl", (sx * 0.56 * s, r * s, sz * s), (r * s, w * s), TIRE, wheel=True))
            P.append(Prim("cyl", (sx * (0.56 + w + 0.005) * s, r * s, sz * s), (r * 0.45 * s, 0.01 * s), hub))
    return P


def plumber(cap, shirt, overalls, letter_col, s=1.0, tall=1.0, nose=1.0, mustache=(70, 40, 20), cap_col2=None):
    y0 = 0.58 * s
    P = [
        Prim("ell", (0, y0 + 0.18 * s * tall, -0.12 * s), (0.25 * s, 0.24 * s * tall, 0.2 * s), overalls),   # body
        Prim("ell", (0, y0 + 0.30 * s * tall, -0.08 * s), (0.22 * s, 0.14 * s, 0.17 * s), shirt),           # chest/shoulders
        Prim("ell", (0, y0 + 0.62 * s * tall, -0.05 * s), (0.19 * s, 0.19 * s, 0.19 * s), SKIN),            # head
        Prim("ell", (0, y0 + 0.64 * s * tall, -0.12 * s), (0.185 * s, 0.17 * s, 0.14 * s), (95, 55, 25)),    # hair (back of head)
        Prim("ell", (0, y0 + 0.62 * s * tall, 0.14 * s), (0.07 * s * nose, 0.06 * s * nose, 0.07 * s * nose), (255, 170, 130)),  # nose
        Prim("ell", (0, y0 + 0.555 * s * tall, 0.13 * s), (0.11 * s, 0.03 * s, 0.04 * s), mustache),         # mustache
        Prim("ell", (0, y0 + 0.77 * s * tall, -0.05 * s), (0.205 * s, 0.11 * s, 0.205 * s), cap),           # cap dome
        Prim("ell", (0, y0 + 0.73 * s * tall, 0.10 * s), (0.17 * s, 0.03 * s, 0.13 * s), cap_col2 or cap),  # brim
        Prim("ell", (0, y0 + 0.82 * s * tall, 0.12 * s), (0.06 * s, 0.05 * s, 0.03 * s), letter_col),       # emblem
        Prim("ell", (-0.075 * s, y0 + 0.67 * s * tall, 0.15 * s), (0.03 * s, 0.05 * s, 0.02 * s), (40, 70, 190)),  # eyes
        Prim("ell", (0.075 * s, y0 + 0.67 * s * tall, 0.15 * s), (0.03 * s, 0.05 * s, 0.02 * s), (40, 70, 190)),
    ]
    for sx in (-1, 1):  # arms to the wheel, gloves
        P.append(Prim("ell", (sx * 0.22 * s, y0 + 0.18 * s, 0.12 * s), (0.07 * s, 0.07 * s, 0.2 * s), shirt, R=rot_x(0.5)))
        P.append(Prim("ell", (sx * 0.12 * s, y0 + 0.08 * s, 0.30 * s), (0.07 * s, 0.07 * s, 0.07 * s), WHITE))
    return P


DRIVER_SCALE = 1.45


def driver(name):
    """Kart prims + the driver scaled up about the seat (chibi proportions)."""
    P = _driver(name)
    nk = len(kart_base((0, 0, 0), (0, 0, 0)))
    piv = np.array([0, 0.5, -0.12])
    for p in P[nk:]:
        p.c = piv + (p.c - piv) * DRIVER_SCALE
        p.size = p.size * DRIVER_SCALE
    return P


def _driver(name):
    if name == "mario":
        return kart_base((220, 30, 30), (240, 240, 245)) + plumber((225, 25, 25), (225, 25, 25), (40, 70, 200), WHITE)
    if name == "luigi":
        return kart_base((40, 170, 60), (240, 240, 245)) + plumber((40, 170, 60), (40, 170, 60), (40, 60, 170), WHITE, tall=1.12)
    if name == "wario":
        return kart_base((250, 205, 40), (120, 40, 150)) + plumber((250, 210, 40), (250, 210, 40), (120, 40, 160),
                                                                     (40, 60, 200), s=1.05, nose=1.4, mustache=(40, 25, 15))
    if name == "peach":
        y0 = 0.58
        P = kart_base((255, 150, 200), (255, 255, 255))
        P += [Prim("ell", (0, y0 + 0.18, -0.12), (0.27, 0.26, 0.22), (255, 140, 200)),                # dress
              Prim("ell", (0, y0 + 0.62, -0.05), (0.18, 0.19, 0.18), SKIN),
              Prim("ell", (0, y0 + 0.64, -0.12), (0.23, 0.26, 0.2), (255, 215, 80)),                 # hair
              Prim("ell", (0, y0 + 0.47, -0.16), (0.2, 0.2, 0.12), (255, 215, 80)),
              Prim("box", (0, y0 + 0.86, -0.05), (0.09, 0.05, 0.09), (255, 200, 40)),                # crown
              Prim("ell", (0, y0 + 0.86, 0.045), (0.03, 0.03, 0.01), (60, 120, 255)),
              Prim("ell", (-0.07, y0 + 0.66, 0.155), (0.03, 0.045, 0.02), (40, 90, 200)),
              Prim("ell", (0.07, y0 + 0.66, 0.155), (0.03, 0.045, 0.02), (40, 90, 200))]
        for sx in (-1, 1):
            P.append(Prim("ell", (sx * 0.22, y0 + 0.18, 0.12), (0.06, 0.06, 0.2), SKIN, R=rot_x(0.5)))
            P.append(Prim("ell", (sx * 0.12, y0 + 0.08, 0.30), (0.065, 0.065, 0.065), WHITE))
        return P
    if name == "toad":
        y0 = 0.52
        P = kart_base((250, 250, 250), (40, 70, 200))
        P += [Prim("ell", (0, y0 + 0.16, -0.12), (0.2, 0.2, 0.18), (40, 70, 200)),                   # vest
              Prim("ell", (0, y0 + 0.44, -0.05), (0.17, 0.16, 0.16), SKIN),
              Prim("ell", (0, y0 + 0.64, -0.05), (0.34, 0.2, 0.32), WHITE),                          # mushroom cap
              Prim("ell", (0, y0 + 0.74, 0.20), (0.11, 0.09, 0.08), (220, 30, 40)),
              Prim("ell", (0.26, y0 + 0.66, 0.0), (0.08, 0.1, 0.1), (220, 30, 40)),
              Prim("ell", (-0.26, y0 + 0.66, 0.0), (0.08, 0.1, 0.1), (220, 30, 40)),
              Prim("ell", (0, y0 + 0.78, -0.26), (0.11, 0.09, 0.08), (220, 30, 40)),
              Prim("ell", (-0.06, y0 + 0.46, 0.13), (0.028, 0.05, 0.02), (20, 20, 20)),
              Prim("ell", (0.06, y0 + 0.46, 0.13), (0.028, 0.05, 0.02), (20, 20, 20))]
        for sx in (-1, 1):
            P.append(Prim("ell", (sx * 0.18, y0 + 0.14, 0.12), (0.06, 0.06, 0.18), SKIN, R=rot_x(0.5)))
            P.append(Prim("ell", (sx * 0.11, y0 + 0.08, 0.30), (0.06, 0.06, 0.06), WHITE))
        return P
    if name == "yoshi":
        y0 = 0.58
        G = (70, 195, 70)
        P = kart_base((70, 195, 70), (250, 250, 250), hub=(250, 120, 30))
        P += [Prim("ell", (0, y0 + 0.18, -0.12), (0.24, 0.26, 0.2), G),
              Prim("ell", (0, y0 + 0.16, -0.02), (0.17, 0.2, 0.14), WHITE),                          # belly
              Prim("ell", (0, y0 + 0.20, -0.30), (0.22, 0.12, 0.12), (220, 40, 40)),                 # saddle/shell
              Prim("ell", (0, y0 + 0.60, -0.04), (0.17, 0.2, 0.18), G),                              # head
              Prim("ell", (0, y0 + 0.56, 0.17), (0.15, 0.12, 0.14), G),                              # snout
              Prim("ell", (0, y0 + 0.70, -0.20), (0.06, 0.08, 0.08), (230, 60, 40)),                 # spines
              Prim("ell", (-0.07, y0 + 0.78, 0.04), (0.06, 0.08, 0.05), WHITE),                      # eyes
              Prim("ell", (0.07, y0 + 0.78, 0.04), (0.06, 0.08, 0.05), WHITE),
              Prim("ell", (-0.07, y0 + 0.78, 0.085), (0.025, 0.04, 0.02), (20, 20, 20)),
              Prim("ell", (0.07, y0 + 0.78, 0.085), (0.025, 0.04, 0.02), (20, 20, 20))]
        for sx in (-1, 1):
            P.append(Prim("ell", (sx * 0.21, y0 + 0.18, 0.12), (0.06, 0.06, 0.2), G, R=rot_x(0.5)))
            P.append(Prim("ell", (sx * 0.12, y0 + 0.08, 0.30), (0.065, 0.065, 0.065), G))
        return P
    if name == "donkeykong":
        y0 = 0.58
        B, T = (130, 75, 35), (225, 175, 120)
        P = kart_base((120, 70, 40), (240, 200, 60), scale=1.08)
        P += [Prim("ell", (0, y0 + 0.24, -0.12), (0.34, 0.32, 0.26), B),
              Prim("ell", (0, y0 + 0.24, 0.04), (0.2, 0.22, 0.14), T),                               # chest
              Prim("ell", (0, y0 + 0.16, 0.14), (0.08, 0.14, 0.03), (220, 30, 30)),                  # tie
              Prim("ell", (0, y0 + 0.66, -0.04), (0.22, 0.2, 0.2), B),
              Prim("ell", (0, y0 + 0.60, 0.13), (0.15, 0.1, 0.1), T),                                # muzzle
              Prim("ell", (-0.08, y0 + 0.72, 0.13), (0.035, 0.04, 0.03), (20, 20, 20)),
              Prim("ell", (0.08, y0 + 0.72, 0.13), (0.035, 0.04, 0.03), (20, 20, 20))]
        for sx in (-1, 1):
            P.append(Prim("ell", (sx * 0.3, y0 + 0.2, 0.12), (0.1, 0.1, 0.24), B, R=rot_x(0.5)))
            P.append(Prim("ell", (sx * 0.14, y0 + 0.08, 0.32), (0.08, 0.08, 0.08), T))
        return P
    if name == "bowser":
        y0 = 0.62
        Y, Gs = (240, 205, 70), (40, 150, 60)
        P = kart_base((40, 40, 50), (240, 150, 40), scale=1.15, hub=(200, 200, 210))
        P += [Prim("ell", (0, y0 + 0.28, -0.22), (0.4, 0.34, 0.26), Gs),                             # shell
              Prim("ell", (0, y0 + 0.24, 0.0), (0.28, 0.28, 0.2), Y),                                # belly
              Prim("ell", (0, y0 + 0.72, -0.02), (0.22, 0.2, 0.22), Y),                              # head
              Prim("ell", (0, y0 + 0.64, 0.17), (0.16, 0.1, 0.12), (250, 225, 160)),                 # snout
              Prim("ell", (0, y0 + 0.86, -0.16), (0.12, 0.1, 0.1), (240, 90, 30)),                   # hair
              Prim("ell", (-0.16, y0 + 0.9, -0.02), (0.04, 0.1, 0.04), (250, 245, 225), R=rot_z(0.5)),  # horns
              Prim("ell", (0.16, y0 + 0.9, -0.02), (0.04, 0.1, 0.04), (250, 245, 225), R=rot_z(-0.5)),
              Prim("ell", (-0.08, y0 + 0.78, 0.15), (0.035, 0.035, 0.02), (200, 30, 30)),
              Prim("ell", (0.08, y0 + 0.78, 0.15), (0.035, 0.035, 0.02), (200, 30, 30))]
        for k in range(5):  # shell spikes
            a = -1.0 + k * 0.5
            P.append(Prim("ell", (math.sin(a) * 0.36, y0 + 0.36 + math.cos(a) * 0.1, -0.44), (0.05, 0.05, 0.07), WHITE))
        for sx in (-1, 1):
            P.append(Prim("ell", (sx * 0.32, y0 + 0.22, 0.12), (0.1, 0.1, 0.24), Y, R=rot_x(0.5)))
            P.append(Prim("ell", (sx * 0.16, y0 + 0.1, 0.34), (0.08, 0.08, 0.08), Y))
        return P
    raise KeyError(name)


# ------------------------------------------------------------ camera per frame

SLOPE = [-12, -8.5, -5, -2.5, 0, 2.5, 5, 8.5, 12]            # animGroupSelector 0..8 (deg)
SET_SLOPE = [-10, -5, 0, 5, 10]                               # files 189.. (pitch sets)
BASE_PITCH = 11.0


def frame_view(i):
    """-> (yaw deg, pitch deg, tumble deg)."""
    if i < 189:
        g, j = divmod(i, 21)
        return j * 0x208 * 360 / 65536, BASE_PITCH - SLOPE[g], 0.0
    if i < 289:
        k, j = divmod(i - 189, 20)
        return j * 9.0, BASE_PITCH - SET_SLOPE[k], 0.0
    return 0.0, BASE_PITCH, (i - 289) * 360 / 32


def _rays(yaw, pitch, n, span):
    """Orthographic rays (camera looks at the origin region)."""
    cam = rot_y(math.radians(-yaw)) @ rot_x(math.radians(pitch))
    fwd = cam @ np.array([0, 0, 1.0])
    right = cam @ np.array([1.0, 0, 0])
    up = cam @ np.array([0, 1.0, 0])
    ys, xs = np.mgrid[0:n, 0:n]
    u = (xs + 0.5) / n * 2 - 1
    v = 1 - (ys + 0.5) / n * 2
    centre = np.array([0, 0.62, 0])
    o = centre - fwd * 5 + (u.ravel()[:, None] * right + v.ravel()[:, None] * up) * span
    d = np.tile(fwd, (n * n, 1))
    return o, d, cam


def raster(prims, yaw, pitch, tumble, n, span):
    o, d, cam = _rays(yaw, pitch, n, span)
    if tumble:
        T = rot_x(math.radians(tumble))
        piv = np.array([0, 0.5, 0])
        o = (o - piv) @ T + piv       # rotate the world the other way instead of the kart
        d = d @ T
        light_R = T.T
    else:
        light_R = np.eye(3)
    N = len(o)
    best = np.full(N, np.inf)
    idx = np.full(N, -1)
    nor = np.zeros((N, 3))
    lps = np.zeros((N, 3))
    for k, p in enumerate(prims):
        t, wn, lp = intersect(p, o, d)
        m = t < best
        best[m], idx[m], nor[m], lps[m] = t[m], k, wn[m], lp[m]
    return best.reshape(n, n), idx.reshape(n, n), nor.reshape(n, n, 3), lps.reshape(n, n, 3), cam, light_R


def shade(prims, idx, nor, lps, cam, light_R):
    n = idx.shape[0]
    L = cam @ np.array([-0.45, 0.75, -0.5])        # key light from upper left, towards camera
    L /= np.linalg.norm(L)
    col = np.zeros((n, n, 3))
    tread = np.zeros((n, n), int)
    wheel = np.zeros((n, n), bool)
    for k, p in enumerate(prims):
        m = idx == k
        if not m.any():
            continue
        nd = (nor[m] @ (light_R @ L)).clip(-1, 1)
        lv = np.where(nd > 0.55, 1.0, np.where(nd > 0.05, 0.78, 0.58))  # 3 toon bands
        c = p.color[None, :] * lv[:, None]
        col[m] = c
        if p.wheel:
            lp = lps[m]
            ang = np.arctan2(lp[:, 1], lp[:, 2])
            band = ((ang / (2 * np.pi) * 8) % 8).astype(int)
            tread[m] = band * 4 + np.digitize(lv, [0.6, 0.8, 0.99])
            wheel[m] = True
    return col, wheel, tread


def render_frame(name, i, bbox=None, prims=None):
    """bbox: (x0, y0, x1, y1) in the 64x64 frame to fit (kept alpha outline), else centred."""
    prims = prims or driver(name)
    yaw, pitch, tumble = frame_view(i)
    span = 1.35
    lo = 48
    d, idx, _, _, _, _ = raster(prims, yaw, pitch, tumble, lo, span)
    ys, xs = np.nonzero(idx >= 0)
    if len(xs) == 0:
        return np.zeros((OUT, OUT, 4), np.uint8), np.zeros((OUT, OUT), bool), np.zeros((OUT, OUT), int)
    # my silhouette bbox in normalised [-1,1] view coords
    mx0, mx1 = (xs.min()) / lo * 2 - 1, (xs.max() + 1) / lo * 2 - 1
    my0, my1 = 1 - (ys.max() + 1) / lo * 2, 1 - ys.min() / lo * 2
    if bbox is None:
        bbox = (6, 6, 58, 58)
    bx0, by0, bx1, by1 = bbox
    tw, th = (bx1 - bx0) / OUT * 2, (by1 - by0) / OUT * 2
    sc = min(tw / (mx1 - mx0), th / (my1 - my0))
    # view window so that my bbox maps onto the target bbox (bottom centred)
    n = OUT * S
    cx_t = (bx0 + bx1) / 2 / OUT * 2 - 1
    by_t = 1 - by1 / OUT * 2
    span2 = span / sc
    cxm = (mx0 + mx1) / 2 * span
    bym = my0 * span
    o, dd, cam = _rays(yaw, pitch, n, span2)
    right = cam @ np.array([1.0, 0, 0])
    up = cam @ np.array([0, 1.0, 0])
    shift = right * (cxm - cx_t * span2) + up * (bym - by_t * span2)
    # re-raster with the shifted window
    dist, idx, nor, lps, cam, light_R = _raster_shift(prims, yaw, pitch, tumble, n, span2, shift)
    col, wheel, tread = shade(prims, idx, nor, lps, cam, light_R)
    hit = idx >= 0
    # outline: silhouette edge + part boundaries with a depth step
    edge = np.zeros_like(hit)
    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        sh_hit = np.roll(np.roll(hit, dy, 0), dx, 1)
        sh_d = np.roll(np.roll(np.where(hit, dist, 1e9), dy, 0), dx, 1)
        sh_i = np.roll(np.roll(idx, dy, 0), dx, 1)
        edge |= hit & (~sh_hit | ((sh_i != idx) & (sh_d - dist > 0.08)))
    col[edge] = col[edge] * 0.25
    # downsample
    col = col.reshape(OUT, S, OUT, S, 3).mean((1, 3))
    a = hit.reshape(OUT, S, OUT, S).mean((1, 3)) >= 0.5
    wm = wheel.reshape(OUT, S, OUT, S).mean((1, 3)) >= 0.5
    tr = tread.reshape(OUT, S, OUT, S)[:, 0, :, 0]
    rgba = np.zeros((OUT, OUT, 4), np.uint8)
    rgba[..., :3] = np.clip(col, 0, 255)
    rgba[..., 3] = a * 255
    rgba[~a] = 0
    return rgba, wm & a, tr


def _raster_shift(prims, yaw, pitch, tumble, n, span, shift):
    o, d, cam = _rays(yaw, pitch, n, span)
    o = o + shift
    if tumble:
        T = rot_x(math.radians(tumble))
        piv = np.array([0, 0.5, 0])
        o = (o - piv) @ T + piv
        d = d @ T
        light_R = T.T
    else:
        light_R = np.eye(3)
    N = len(o)
    best = np.full(N, np.inf)
    idx = np.full(N, -1)
    nor = np.zeros((N, 3))
    lps = np.zeros((N, 3))
    for k, p in enumerate(prims):
        t, wn, lp = intersect(p, o, d)
        m = t < best
        best[m], idx[m], nor[m], lps[m] = t[m], k, wn[m], lp[m]
    return best.reshape(n, n), idx.reshape(n, n), nor.reshape(n, n, 3), lps.reshape(n, n, 3), cam, light_R


def render_view(name, yaw, pitch, size, span=1.35, roll=0.0):
    """A driver at any size (illustrations): RGBA (size, size), toon-shaded, outlined."""
    prims = driver(name)
    n = size * S
    dist, idx, nor, lps, cam, light_R = _raster_shift(prims, yaw, pitch, 0.0, n, span, np.zeros(3))
    col, wheel, tread = shade(prims, idx, nor, lps, cam, light_R)
    hit = idx >= 0
    edge = np.zeros_like(hit)
    k = max(1, S * size // 96)
    for dy, dx in ((0, k), (k, 0), (0, -k), (-k, 0)):
        sh_hit = np.roll(np.roll(hit, dy, 0), dx, 1)
        sh_d = np.roll(np.roll(np.where(hit, dist, 1e9), dy, 0), dx, 1)
        sh_i = np.roll(np.roll(idx, dy, 0), dx, 1)
        edge |= hit & (~sh_hit | ((sh_i != idx) & (sh_d - dist > 0.08)))
    col[edge] = col[edge] * 0.25
    # tyres: tread stripes
    col[wheel] *= np.where((tread[wheel] // 4) % 4 == 0, 1.6, 1.0)[:, None]
    col = col.reshape(size, S, size, S, 3).mean((1, 3))
    a = hit.reshape(size, S, size, S).mean((1, 3))
    rgba = np.zeros((size, size, 4), np.float32)
    rgba[..., :3] = np.clip(col / np.maximum(a[..., None], 1e-3), 0, 255)
    rgba[..., 3] = a * 255
    return rgba


def render_bust(name, frame, size=64, nframes=17):
    """Character-select portrait: driver without the kart, head and shoulders, front view.
    Frames 0..10 look around, 11..15 raise a thumb, the last turns away (selected)."""
    P = driver(name)
    nk = len(kart_base((0, 0, 0), (0, 0, 0)))
    prims = P[nk:]
    if frame >= 11 and frame < nframes - 1:
        up = min(1.0, (frame - 10) / 3)
        glove = [p for p in prims if tuple(p.color) == WHITE or p.size.max() < 0.12 * DRIVER_SCALE]
        g = Prim("ell", (0.28, 1.05 + 0.4 * up, 0.35), (0.11, 0.11, 0.11), prims[1].color if name not in ("peach",) else SKIN)
        thumb = Prim("ell", (0.28, 1.2 + 0.4 * up, 0.38), (0.04, 0.08, 0.04), g.color)
        prims = prims + [g, thumb]
    if frame == nframes - 1:
        yaw, pitch = 200.0, 4.0
    else:
        yaw = 180.0 + 12.0 * math.sin(frame / 10.0 * math.pi * 2)
        pitch = 4.0
    # fit: silhouette of the upper body (above the seat) fills the frame, head at the top
    probe = 64
    _, pid, _, _, cam0, _ = _raster_shift(prims, 180.0, pitch, 0.0, probe, 1.4, np.array([0, 0.9 - 0.62, 0.0]))
    ys, xs = np.nonzero(pid >= 0)
    top = 1.4 * (1 - ys.min() / probe * 2) + 0.9            # world-ish height of the top of the head
    half_w = 1.4 * max(abs(xs.min() / probe * 2 - 1), abs((xs.max() + 1) / probe * 2 - 1))
    span = max(0.45, min(0.9, max(half_w * 0.62, 0.55 * (top - 0.75))))
    cy = top - span * 0.96
    n = size * S
    dist, idx, nor, lps, cam, light_R = _raster_shift(prims, yaw, pitch, 0.0, n, span, np.array([0, cy - 0.62, 0.0]))
    col, _, _ = shade(prims, idx, nor, lps, cam, light_R)
    hit = idx >= 0
    edge = np.zeros_like(hit)
    for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
        sh_hit = np.roll(np.roll(hit, dy, 0), dx, 1)
        sh_d = np.roll(np.roll(np.where(hit, dist, 1e9), dy, 0), dx, 1)
        sh_i = np.roll(np.roll(idx, dy, 0), dx, 1)
        edge |= hit & (~sh_hit | ((sh_i != idx) & (sh_d - dist > 0.05)))
    col[edge] = col[edge] * 0.25
    col = col.reshape(size, S, size, S, 3).mean((1, 3))
    a = hit.reshape(size, S, size, S).mean((1, 3)) >= 0.5
    rgba = np.zeros((size, size, 4), np.uint8)
    rgba[..., :3] = np.clip(col, 0, 255)
    rgba[..., 3] = a * 255
    rgba[~a] = 0
    return rgba
