"""MK64 audio banks (SM64-US-style ctl, one shared tbl bank).

ctl  (bin/audiobanks.us.bin): u16 rev, u16 n, n x {u32 off, u32 len}; bank =
     0x10 header (u32 nInst, u32 nDrums, u32 ?, u32 date) + body; body offsets
     are relative to the body. body+0: drums table ptr, body+4: instrument ptrs.
     Instrument (0x20): loaded, lo, hi, release, env, 3 x {sample, f32 tuning}.
     Drum: release, pan, loaded, pad, {sample, tuning}, env.
     Sample (0x14): unused, loaded, pad2, addr (tbl-relative), loop, book, size.
     Book: s32 order, s32 npred, 8*order*npred s16.  Loop: start, end, count,
     pad, 16 x s16 state if count.
tbl  (bin/audiotables.bin): same header, all banks point at one sample blob.

samples(ctl, tbl) -> {tbl_addr: info}; each info has the absolute ctl
offsets of its book and loop so the clean room can rewrite them in place.
"""
import struct


def u32(b, o):
    return struct.unpack_from(">I", b, o)[0]


def header(b):
    rev, n = struct.unpack_from(">HH", b, 0)
    return [struct.unpack_from(">II", b, 4 + 8 * i) for i in range(n)]


def samples(ctl, tbl):
    tbl_base = header(tbl)[0][0]
    out = {}

    def sound(body, bank, sp, tuning, who):
        if sp == 0:
            return
        s = body + sp
        _, loaded, addr, loop, book, size = struct.unpack_from(">BBxxIIII", ctl, s)
        bo = body + book
        order, npred = struct.unpack_from(">ii", ctl, bo)
        lo = body + loop
        start, end, count = struct.unpack_from(">III", ctl, lo)
        key = tbl_base + addr
        d = out.setdefault(key, {"tbl": key, "size": size, "order": order, "npred": npred,
                                 "books": set(), "loops": set(), "start": start, "end": end,
                                 "count": count, "tunings": [], "refs": []})
        d["books"].add(bo)
        d["loops"].add(lo)
        d["tunings"].append(tuning)
        d["refs"].append(f"{bank}:{who}")
        assert d["size"] == size and (d["start"], d["end"], d["count"]) == (start, end, count), hex(key)

    for bank, (off, ln) in enumerate(header(ctl)):
        if ln == 0:
            continue
        ninst, ndrum = u32(ctl, off), u32(ctl, off + 4)
        body = off + 0x10
        drums = u32(ctl, body)
        for i in range(ninst):
            ip = u32(ctl, body + 4 + 4 * i)
            if ip:
                ins = body + ip
                for k in range(3):
                    sp, tun = struct.unpack_from(">If", ctl, ins + 8 + 8 * k)
                    sound(body, bank, sp, tun, f"i{i}.{k}")
        if drums and ndrum:
            for i in range(ndrum):
                dp = u32(ctl, body + drums + 4 * i)
                if dp:
                    sp, tun = struct.unpack_from(">If", ctl, body + dp + 4)
                    sound(body, bank, sp, tun, f"d{i}")
    for d in out.values():
        d["books"], d["loops"] = sorted(d["books"]), sorted(d["loops"])
    return out


def book_at(ctl, bo):
    order, npred = struct.unpack_from(">ii", ctl, bo)
    vals = struct.unpack_from(">%dh" % (8 * order * npred), ctl, bo + 8)
    return {"order": order, "npred": npred, "book": list(vals)}
