"""TKMK00 encoder (clean, non-matching) for MK64 menu textures.

Written from the decoder in the decomp (tools/libtkmk00.c). Layout:
  0x00 "TKMK00", 0x06 flags (bit i set = channel i is RLE bytes; we use raw
  words for all), 0x08 width, 0x0A height, 0x0C 8 x u32 channel offsets,
  0x2C main bit stream (MSB first, u32 words).
Channel 0 carries a Huffman tree (1 = node, 0 = leaf + 5-bit value) and the
symbols; channel 1+n carries a "new pixel?" bit where n = number of already
decoded neighbours (the decoder's tmp_buf count). The main stream carries
literal/MRU flags, 6-bit MRU indices and the (unused here) trail flags.

    encode(rgba16 uint16 array HxW, alpha_color) -> bytes
"""
import heapq

import numpy as np


class Bits:
    def __init__(self):
        self.bits = []

    def put(self, v, n):
        for i in range(n - 1, -1, -1):
            self.bits.append((v >> i) & 1)

    def bytes(self, pad_words=2):
        b = self.bits + [0] * ((-len(self.bits)) % 32 + 32 * pad_words)
        out = bytearray()
        for i in range(0, len(b), 8):
            v = 0
            for x in b[i:i + 8]:
                v = (v << 1) | x
            out.append(v)
        return bytes(out)


RLE_MAX = 128         # bytes per literal block (repeat runs up to 130)


def rle_bytes(bits):
    """Channel bits in the decoder's RLE byte mode: ctrl < 0x80 = next byte repeated ctrl+3 times,
    ctrl >= 0x80 = (ctrl & 0x7F) + 1 literal bytes follow. Bits are read MSB first."""
    raw = Bits()
    raw.bits = list(bits)
    data = raw.bytes(pad_words=0) or b"\0"
    out = bytearray()
    i, lit = 0, bytearray()

    def flush():
        while lit:
            chunk = lit[:RLE_MAX]
            out.append(0x80 | (len(chunk) - 1))
            out.extend(chunk)
            del lit[:RLE_MAX]
    while i < len(data):
        j = i
        while j < len(data) and data[j] == data[i] and j - i < 130:
            j += 1
        if j - i >= 3:
            flush()
            out.append(j - i - 3)
            out.append(data[i])
            i = j
        else:
            lit.append(data[i])
            i += 1
    flush()
    out += b"\x80\0\0\0"                                  # slack for look-ahead
    return bytes(out)


def c94(t8, t9):
    """The decoder's symbol -> value map around prediction t8."""
    if t8 >= 0x10:
        v0 = (0x1F - t8) * 2
        if v0 < t9:
            return 0x1F - t9
    else:
        if t8 * 2 < t9:
            return t9
    odd, t9 = t9 & 1, t9 >> 1
    return t9 + t8 + 1 if odd else t8 - t9


INV = [{c94(p, s): s for s in range(31, -1, -1)} for p in range(32)]


def huffman(freq):
    """-> (tree, codes): tree is nested tuples / leaf ints."""
    syms = [s for s in range(32) if freq[s]]
    if not syms:
        syms = [0]
    if len(syms) == 1:
        syms.append((syms[0] + 1) % 32)
    heap = [(freq[s], i, s) for i, s in enumerate(syms)]
    heapq.heapify(heap)
    k = len(heap)
    while len(heap) > 1:
        a, b = heapq.heappop(heap), heapq.heappop(heap)
        heapq.heappush(heap, (a[0] + b[0], k, (a[2], b[2])))
        k += 1
    tree = heap[0][2]
    codes = {}

    def walk(t, pre):
        if isinstance(t, int):
            codes[t] = pre
        else:
            walk(t[0], pre + [0])
            walk(t[1], pre + [1])
    walk(tree, [])
    return tree, codes


def encode(img, alpha_color=1):
    """img: uint16 (h, w) RGBA5551 as the game stores it. Pixels whose value
    the decoder can't produce are adjusted: with alpha_color 0xBE a
    transparent pixel becomes 0x00BE, every opaque pixel gets bit 0 set and
    is nudged off 0x00BF."""
    h, w = img.shape
    tgt = img.astype(np.int64).ravel().copy()
    for i, v in enumerate(tgt):
        if alpha_color != 1 and (v & 1) == 0:
            tgt[i] = alpha_color
        else:
            v |= 1
            if (v & 0xFFFE) == alpha_color:
                v ^= 2
            tgt[i] = v
    # pass 1: decisions + literal symbols; pass 2: emit with the tree
    for pass_ in (1, 2):
        out = np.zeros(h * w, np.int64)
        tmp = np.zeros(h * w + 2 * w + 3, np.int64)
        mru = [0xFFFF] * 64
        t7 = 0
        main, ch = Bits(), [Bits() for _ in range(8)]
        syms = []
        if pass_ == 2:
            def tree_bits(t):
                if isinstance(t, int):
                    ch[0].put(0, 1)
                    ch[0].put(t, 5)
                else:
                    ch[0].put(1, 1)
                    tree_bits(t[0])
                    tree_bits(t[1])
            tree_bits(tree)
        for p in range(h * w):
            row, col = divmod(p, w)
            v = int(tgt[p])
            c = int(tmp[p]) + 1
            if v == t7:
                ch[c].put(0, 1)
                out[p] = t7
                continue
            ch[c].put(1, 1)
            if v in mru:
                i = mru.index(v)
                main.put(0, 1)
                main.put(i, 6)
                mru.insert(0, mru.pop(i))
            else:
                main.put(1, 1)
                up = int(out[p - w]) if row else 0
                left = int(out[p - 1]) if (row or col) else 0
                A = lambda x: (x & 0x7C0) >> 6
                B = lambda x: (x & 0xF800) >> 11
                C = lambda x: (x & 0x3E) >> 1
                ta, tb, tc = A(v), B(v), C(v)
                p0 = (A(up) + A(left)) // 2
                s0 = INV[p0][ta]
                d = ta - p0
                p1 = min(31, max(0, d + (B(up) + B(left)) // 2))
                s1 = INV[p1][tb]
                p2 = min(31, max(0, d + (C(up) + C(left)) // 2))
                s2 = INV[p2][tc]
                for s in (s0, s1, s2):
                    syms.append(s)
                    if pass_ == 2:
                        for bit in codes[s]:
                            ch[0].put(bit, 1)
                nv = (tb << 11) | (ta << 6) | (tc << 1)
                if nv != alpha_color:
                    nv |= 1
                assert nv == v, (p, hex(nv), hex(v))
                mru.insert(0, v)
                mru.pop()
            out[p] = v
            t7 = v
            if col < w - 1:
                tmp[p + 1] += 1
            if col < w - 2:
                tmp[p + 2] += 1
            if row < h - 1:
                if col:
                    tmp[p + w - 1] += 1
                tmp[p + w] += 1
                if col < w - 1:
                    tmp[p + w + 1] += 1
            if row < h - 2:
                tmp[p + 2 * w] += 1
            main.put(0, 1)                                 # no trail
        if pass_ == 1:
            freq = [0] * 32
            for s in syms:
                freq[s] += 1
            tree, codes = huffman(freq)
    body = main.bytes()
    streams, flags = [], 0
    for i, c in enumerate(ch):
        raw, rle = c.bytes(pad_words=1), rle_bytes(c.bits)
        if len(rle) < len(raw):
            streams.append(rle + bytes((-len(rle)) % 4))   # the game reads raw channels with lw: keep offsets 4-aligned
            flags |= 1 << i
        else:
            streams.append(raw)
    hdr = bytearray(b"TKMK00" + bytes([flags, 0]))
    hdr += w.to_bytes(2, "big") + h.to_bytes(2, "big")
    off = 0x2C + len(body)
    offs = []
    for s in streams:
        offs.append(off)
        off += len(s)
    for o in offs:
        hdr += o.to_bytes(4, "big")
    data = bytes(hdr) + body + b"".join(streams)
    return data + b"\0" * ((-len(data)) % 8), out.astype(np.uint16).reshape(h, w)
