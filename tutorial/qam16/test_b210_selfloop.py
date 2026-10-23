#!/usr/bin/env python3
"""The B210 receives its own 16-QAM transmission (TX/RX port to RX2, antennas a few cm apart or a cable with attenuation): tells whether the B210's transmitted signal is clean, independent of the P501.
    source tools/gnuradio_env.sh; python3 test_b210_selfloop.py --tx-gain 40 --rms 0.35 --rx-gain 40 --seconds 6
Very low power; check the rules where you are before radiating."""
import argparse, os, subprocess, sys, tempfile, time
import numpy as np
from gnuradio import gr, blocks, analog, digital, uhd
from gnuradio.filter import firdes
HERE = os.path.dirname(os.path.abspath(__file__))
p = argparse.ArgumentParser()
p.add_argument("--tx-gain", type=float, default=40); p.add_argument("--rms", type=float, default=0.35); p.add_argument("--rx-gain", type=float, default=40); p.add_argument("--seconds", type=float, default=6)
p.add_argument("--freq", type=float, default=915e6); p.add_argument("--fll-div", type=float, default=1600)
a = p.parse_args()
tmp = tempfile.mkdtemp(prefix="qam16_grc_")
for g in ("qam16_b210_frame_tx", "qam16_b210_frame_rx"):
    subprocess.run(["grcc", "-o", tmp, os.path.join(HERE, g + ".grc")], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
sys.path.insert(0, tmp)
import qam16_b210_frame_tx_epy_block_0 as T
import qam16_b210_frame_rx_epy_block_0 as R
fs, sps, nfilts = 3.84e6, 4, 32
DEV = "num_send_frames=128,num_recv_frames=128,send_frame_size=16360,recv_frame_size=16360"


class Top(gr.top_block):
    def __init__(self):
        gr.top_block.__init__(self, "b210_selfloop")
        self.tx = T.blk(); self.amp = blocks.multiply_const_cc(a.rms)
        sink = uhd.usrp_sink(DEV, uhd.stream_args(cpu_format="fc32", args="", channels=[0]), "")
        sink.set_samp_rate(fs); sink.set_center_freq(uhd.tune_request(a.freq), 0); sink.set_gain(a.tx_gain, 0); sink.set_antenna("TX/RX", 0)
        src = uhd.usrp_source(DEV, uhd.stream_args(cpu_format="fc32", args="", channels=[0]))
        src.set_samp_rate(fs); src.set_center_freq(uhd.tune_request(a.freq), 0); src.set_gain(a.rx_gain, 0); src.set_antenna("RX2", 0)
        self.sink, self.src = sink, src
        agc = analog.agc2_cc(0.06, 1e-3, 0.947, 1.0, 200)
        c2f = blocks.complex_to_float(); ri = analog.rail_ff(-3, 3); rq = analog.rail_ff(-3, 3); f2c = blocks.float_to_complex()
        fll = digital.fll_band_edge_cc(sps, 0.35, 55, 2 * np.pi / a.fll_div)
        taps = firdes.root_raised_cosine(nfilts, nfilts * sps, 1.0, 0.35, 11 * sps * nfilts)
        clk = digital.pfb_clock_sync_ccf(sps, 2 * np.pi / 400, taps, nfilts, nfilts // 2, 0.05, 1)
        self.rx = R.blk(symbol_rate=fs / sps)
        self.keep = [blocks.null_sink(gr.sizeof_gr_complex)] + [blocks.null_sink(gr.sizeof_float) for _ in range(5)] + [blocks.null_sink(gr.sizeof_float) for _ in range(6)]
        self.connect(self.tx, self.amp, sink)
        self.connect(src, agc, c2f); self.connect((c2f, 0), ri, (f2c, 0)); self.connect((c2f, 1), rq, (f2c, 1)); self.connect(f2c, fll, clk, self.rx)
        for k in range(3): self.connect((fll, k + 1), self.keep[6 + k]); self.connect((clk, k + 1), self.keep[9 + k])
        for k in range(6): self.connect((self.rx, k), self.keep[k])


tb = Top(); tb.start(); t0 = time.time()
try:
    while time.time() - t0 < a.seconds:
        time.sleep(1.0)
        c = tb.rx.core
        print("t=%3.0f s locked %d frames %5d SER %.2e EVM %.1f dB offset left %+6.0f Hz | locks %d hits %d misses %d lost %d" % (time.time() - t0, tb.rx.locked, c.frames, c.sym_err / max(c.sym_cnt, 1), tb.rx.evm_db, tb.rx.cfo_hz, c.locks, c.hits, c.misses, c.lost), flush=True)
finally:
    tb.amp.set_k(0.0); tb.stop(); tb.wait()
