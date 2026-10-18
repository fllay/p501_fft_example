#!/usr/bin/env python3
"""Decode a recorded complex64 file (3.84 MSPS) with the receiver chain of chapter 4a, offline.

    python3 qpsk_decode_file.py recording.c64 --out /tmp/decode_run [--skip 0.0]
    python3 qpsk_analyze.py /tmp/decode_run          (needs the same repeating pattern as qpsk_b210_loop.py)
"""
import argparse, os, sys
import numpy as np
from gnuradio import gr, blocks
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qpsk_b210_loop import connect_rx_chain

p = argparse.ArgumentParser()
p.add_argument("file"); p.add_argument("--out", default="/tmp/decode_run"); p.add_argument("--skip", type=float, default=0.0, help="seconds at the start to leave out")
p.add_argument("--samp-rate", type=float, default=3.84e6); p.add_argument("--sps", type=int, default=4); p.add_argument("--excess-bw", type=float, default=0.35)
p.add_argument("--freq-bw", type=float, default=2 * np.pi / 100); p.add_argument("--timing-bw", type=float, default=2 * np.pi / 100); p.add_argument("--phase-bw", type=float, default=2 * np.pi / 100)
p.add_argument("--max-rate-dev", type=float, default=0.05); p.add_argument("--tap-every-s", type=float, default=0.1)
a = p.parse_args()
os.makedirs(a.out, exist_ok=True)
tb = gr.top_block()
src = blocks.file_source(gr.sizeof_gr_complex, a.file, False)
sk = blocks.skiphead(gr.sizeof_gr_complex, int(a.skip * a.samp_rate))
tb.connect(src, sk)
connect_rx_chain(tb, sk, a)
tb.run()
print("decoded", a.file, "->", a.out)
