#!/usr/bin/env python3
"""StreamRx (the GNU Radio block's core) against FrameRxHW on the same records, fed in chunks of random sizes.   source tools/gnuradio_env.sh; python3 test_stream_rx.py"""
import numpy as np
import frame16 as F
from framerx_hw import FrameRxHW
from qam16_stream_rx import StreamRx

REF = F.prbs15_indices()
rng = np.random.default_rng(3)
sym, ids = F.make_frames(40, "prbs15")
cases = [(20, 3000, 137), (15, -4000, 1500), (25, 0, 0), (30, 5500, 4000)]
for snr, cfo, lead in cases:
    x = F.channel(sym, snr, cfo_hz=cfo, lead=lead)
    f = FrameRxHW(word_mode="aided", anchor="first", amp_mode="word").run(x, ref_idx=REF)
    s = StreamRx(); data = []; infos = []; i = 0
    while i < len(x):
        n = int(rng.integers(1, 6000)); d, inf = s.push(x[i:i + n]); i += n; data.append(d); infos += inf
    d = np.concatenate(data)
    fe = [v["sym_err"] for v in infos]
    same = (fe == f.frame_errs[:len(fe)]) and (len(fe) >= f.frames - 1)            # the last frame of a record needs the window after it: the streaming receiver waits for it
    dd = np.concatenate(f.out) if f.out else np.zeros(0)
    ok_d = len(d) <= len(dd) and np.allclose(d, dd[:len(d)], atol=1e-9) and len(d) == F.N_PAY * len(fe)
    print("%2d dB %+6d Hz lead %4d: frames stream %2d float %2d, symbol errors %d (float, same frames: %d), locks %d / %d, data symbols identical: %s -> %s" %
          (snr, cfo, lead, s.frames, f.frames, s.sym_err, sum(f.frame_errs[:len(fe)]), s.locks, f.locks, ok_d, "SAME" if (same and ok_d) else "DIFFERENT"))
