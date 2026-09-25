"""DIRTY ROOM helper: which tbl samples are speech? faster-whisper over the decoded samples.

    python -m games.mk64.find_voices <dirty tree> [out.json]

Prints key, bank refs, duration, no-speech probability and the transcript; the words (a
text fact, like the decomp's text) go into voice_lines.json by hand. No audio is kept.
"""
import json
import os
import sys

import numpy as np

from cleanroom.audio import vadpcm
from games.mk64 import audiobank


def main(argv):
    dirty = argv[1]
    out = argv[2] if len(argv) > 2 else None
    from faster_whisper import WhisperModel
    from scipy.signal import resample_poly
    model = WhisperModel("small.en", device="cpu", compute_type="int8")
    ctl = open(os.path.join(dirty, "bin/audiobanks.us.bin"), "rb").read()
    tbl = open(os.path.join(dirty, "bin/audiotables.bin"), "rb").read()
    rows = []
    for key, s in sorted(audiobank.samples(ctl, tbl).items()):
        rate = 32000 * max(s["tunings"])
        n = s["size"] // 9 * 16
        dur = n / rate
        if not (0.25 < dur < 4.0):
            continue
        pcm = vadpcm.decode(tbl[key:key + s["size"]], audiobank.book_at(ctl, s["books"][0]), n).astype(np.float32) / 32768
        x = resample_poly(pcm, 16000, int(round(rate)))
        segs, info = model.transcribe(x.astype(np.float32), language="en", beam_size=1, vad_filter=False)
        segs = list(segs)
        text = " ".join(t.text.strip() for t in segs)
        nsp = min((t.no_speech_prob for t in segs), default=1.0)
        lp = max((t.avg_logprob for t in segs), default=-9)
        rows.append({"key": key, "refs": s["refs"][:3], "dur": round(dur, 2), "rate": round(rate), "nospeech": round(nsp, 2),
                     "logprob": round(lp, 2), "text": text})
    rows.sort(key=lambda r: (r["nospeech"], -r["logprob"]))
    for r in rows[:60]:
        print(f"{r['key']:8x} {r['dur']:5.2f}s {r['nospeech']:.2f} {r['logprob']:6.2f} {','.join(r['refs']):24s} {r['text'][:60]}")
    if out:
        json.dump(rows, open(out, "w"), indent=0)


if __name__ == "__main__":
    main(sys.argv)
