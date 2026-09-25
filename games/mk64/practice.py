"""MK64 voice practice pack (PERSONAL USE: clips decoded from the user's own ROM extraction;
written outside the repo, never published). Same layout as cleanroom.voice.practice, so
cleanroom.voice.takes can cut the recordings.

    python -m games.mk64.practice <dirty tree> <out dir>
"""
import json
import os
import sys
import wave

import numpy as np

from cleanroom.audio import vadpcm
from games.mk64 import audiobank

HERE = os.path.dirname(os.path.abspath(__file__))
HZ = 22050


def main(argv):
    dirty, out = argv[1], argv[2]
    S = json.load(open(os.path.join(HERE, "spec", "samples.json")))
    L = [(k, v) for k, v in json.load(open(os.path.join(HERE, "voice_lines.json"))).items() if not k.startswith("_")]
    L.sort(key=lambda kv: (kv[1]["who"], int(kv[0])))
    ctl = open(os.path.join(dirty, "bin/audiobanks.us.bin"), "rb").read()
    tbl = open(os.path.join(dirty, "bin/audiotables.bin"), "rb").read()
    os.makedirs(os.path.join(out, "clips"), exist_ok=True)

    def load(key):
        d = S[key]
        k = int(key)
        x = vadpcm.decode(tbl[k:k + d["size"]], audiobank.book_at(ctl, d["books"][0]), d["nframes"]).astype(np.float32) / 32768
        sr = d["rate"]
        return np.interp(np.arange(0, len(x) * HZ / sr) * sr / HZ, np.arange(len(x)), x).astype(np.float32)

    def wr(path, x):
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(HZ)
            w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())

    beep = (0.2 * np.sin(2 * np.pi * 880 * np.arange(int(0.08 * HZ)) / HZ)).astype(np.float32)
    tracks, lines = {}, ["MK64 voice practice script: record in this order, 2-3 takes each, in character.",
                         "Play practice_<character>_call_and_response.wav and speak after each beep.", ""]
    for i, (key, v) in enumerate(L, 1):
        x = load(key)
        x = x / (np.abs(x).max() + 1e-9) * 0.8
        wr(os.path.join(out, "clips", f"{i:02d}_{v['who']}_{key}.wav"), x)
        gap = np.zeros(int((len(x) / HZ * 1.5 + 1.5) * HZ), np.float32)
        tracks.setdefault(v["who"], []).extend([x, np.zeros(int(0.3 * HZ), np.float32), beep, gap])
        lines.append(f"{i:02d}  {v['who']:10s} slot {key:>8s}  max {S[key]['nframes'] / S[key]['rate']:.1f}s  \"{v['text']}\"")
    for who, parts in tracks.items():
        wr(os.path.join(out, f"practice_{who}_call_and_response.wav"), np.concatenate(parts))
    lines += ["", "Record each character's track in one take (WAV, any rate), then:",
              "  CLEANROOM_GAME=games/mk64 python -m cleanroom.voice.takes <your recording> <who>",
              "These clips come from your own ROM: practice only, do not share or commit them."]
    open(os.path.join(out, "SCRIPT.txt"), "w", encoding="utf8").write("\n".join(lines))
    print(f"practice pack: {len(L)} clips, tracks {sorted(tracks)} -> {out}")


if __name__ == "__main__":
    main(sys.argv)
