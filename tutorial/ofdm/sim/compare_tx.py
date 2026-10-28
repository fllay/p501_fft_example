#!/usr/bin/env python3
"""Compare the DAC values of the xsim run of rtl/ofdm_tx.v (tx_out.txt) with ofdm_tx_fixed.py: the stream must be the frame, repeated, after a few zeros (the latency of the buffer)."""
import sys, os
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import ofdm_tx_fixed as T
amp = int(sys.argv[1]) if len(sys.argv) > 1 else 32767
var = sys.argv[2] if len(sys.argv) > 2 else "sc"
d = np.loadtxt("tx_out.txt", dtype=np.int64); oi, oq = d[:, 0], d[:, 1]
I, Q = T.frame_samples(var); ei, eq = T.dac(I, amp), T.dac(Q, amp)
n = len(oi); reps = n // 3840 + 2
Ei, Eq = np.tile(ei, reps), np.tile(eq, reps)
best = None
for off in range(0, 40):
    m = min(n - off, 3840 * 2)
    bad = int(np.count_nonzero(oi[off:off + m] != Ei[:m]) + np.count_nonzero(oq[off:off + m] != Eq[:m]))
    if best is None or bad < best[1]: best = (off, bad)
off, bad = best
print("samples %d, frame offset %d (leading zeros: %d), mismatches in the first two frames: %d" % (n, off, int(np.count_nonzero((oi[:off] == 0) & (oq[:off] == 0))), bad))
m = n - off; bad_all = int(np.count_nonzero(oi[off:] != Ei[:m]) + np.count_nonzero(oq[off:] != Eq[:m]))
print("mismatches in all %d samples after the offset: %d" % (m, bad_all))
print("peak output %d / %d" % (np.abs(oi).max(), np.abs(oq).max()))
sys.exit(0 if bad_all == 0 else 1)
