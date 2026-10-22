"""Offline test of the epy block of qpsk_b210_frame_rx.grc (the source is taken from make_flowgraph_frame.py).   source tools/gnuradio_env.sh; python3 test_frame_rx_block.py"""
import sys, numpy as np
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_flowgraph_frame as M
ns = {}; exec(M.FRAME_RX_SOURCE, ns); B = ns["blk"]
from qpsk_frame import frames_bits
rng = np.random.default_rng(1)
def run(bits, chunks, pl=960):
    b = B(pl); i = 0; out = None
    while i < len(bits):
        n = int(rng.integers(*chunks)); x = bits[i:i+n]; i += n
        o = [np.zeros(len(x), np.float32) for _ in range(3)]
        b.work([x], o); out = (o[0][-1], o[1][-1], o[2][-1])
    return out
pl = 960; nfr = 40
bits = np.array(frames_bits(pl, nfr), dtype=np.uint8)
print("clean, big chunks     :", run(bits, (20000, 40000)))
print("clean, small chunks   :", run(bits, (100, 3000)))
print("clean, odd 1-bit chunks mix:", run(bits[:20000], (1, 50)))
# leading garbage (not frame aligned) + errors at BER 1e-2 in the payload only is hard to inject; use random flips everywhere
for p in (1e-3, 1e-2, 3e-2):
    e = bits.copy(); flips = rng.random(len(e)) < p; e[flips] ^= 1
    r = run(np.concatenate([rng.integers(0, 2, 777).astype(np.uint8), e]), (500, 5000))
    print("flip p=%g -> BER %.4f frames %d lock %d" % (p, *r))
# noise only
print("random bits           :", run(rng.integers(0, 2, 200000).astype(np.uint8), (500, 5000)))
