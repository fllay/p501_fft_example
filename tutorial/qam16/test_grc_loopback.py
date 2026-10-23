#!/usr/bin/env python3
"""Software loopback of the two flowgraphs' blocks (no radio): the transmitter's embedded block -> carrier offset -> noise -> AGC -> limiter -> FLL -> polyphase clock sync -> the receiver's embedded block.
    source tools/gnuradio_env.sh; python3 test_grc_loopback.py [seconds [snr_db [cfo_hz]]]       (the .grc files are compiled with grcc into a temporary folder first)"""
import os, subprocess, sys, tempfile, time
import numpy as np
from gnuradio import gr, blocks, analog, digital, filter as gfilter
from gnuradio.filter import firdes
HERE = os.path.dirname(os.path.abspath(__file__))
tmp = tempfile.mkdtemp(prefix="qam16_grc_")
for g in ("qam16_b210_frame_tx", "qam16_b210_frame_rx"):
    subprocess.run(["grcc", "-o", tmp, os.path.join(HERE, g + ".grc")], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
sys.path.insert(0, tmp)
import qam16_b210_frame_tx_epy_block_0 as T
import qam16_b210_frame_rx_epy_block_0 as R

seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
snr = float(sys.argv[2]) if len(sys.argv) > 2 else 25.0
cfo = float(sys.argv[3]) if len(sys.argv) > 3 else 9600.0
fs, sps, nfilts = 3.84e6, 4, 32


class Top(gr.top_block):
    def __init__(self):
        gr.top_block.__init__(self, "loopback")
        tx = self.tx = T.blk()                                       # a Python block must be kept alive by a reference
        sig_pow = 0.3 ** 2                                           # the block's samples have unit RMS, x 0.3
        amp = blocks.multiply_const_cc(0.3)
        rot = blocks.rotator_cc(2 * np.pi * cfo / fs)
        noise = analog.noise_source_c(analog.GR_GAUSSIAN, np.sqrt(sig_pow / 10 ** (snr / 10) * sps), 7)    # Es/N0 = snr: the noise power per sample is sig * sps / (Es/N0)
        add = blocks.add_cc()
        head = blocks.head(gr.sizeof_gr_complex, int(seconds * fs))
        agc = analog.agc2_cc(0.06, 1e-3, 0.947, 1.0, 200)
        c2f = blocks.complex_to_float(); ri = analog.rail_ff(-3, 3); rq = analog.rail_ff(-3, 3); f2c = blocks.float_to_complex()
        fll = digital.fll_band_edge_cc(sps, 0.35, 55, 2 * np.pi / 1600)
        taps = firdes.root_raised_cosine(nfilts, nfilts * sps, 1.0, 0.35, 11 * sps * nfilts)
        clk = digital.pfb_clock_sync_ccf(sps, 2 * np.pi / 400, taps, nfilts, nfilts // 2, 0.05, 1)
        self.rx = R.blk(symbol_rate=fs / sps)
        sinks = [blocks.null_sink(gr.sizeof_gr_complex)] + [blocks.null_sink(gr.sizeof_float) for _ in range(5)]
        nul1, nul2 = [blocks.null_sink(gr.sizeof_float) for _ in range(3)], [blocks.null_sink(gr.sizeof_float) for _ in range(3)]
        self.connect(tx, amp, rot, (add, 0)); self.connect(noise, (add, 1)); self.connect(add, head, agc, c2f)
        self.connect((c2f, 0), ri, (f2c, 0)); self.connect((c2f, 1), rq, (f2c, 1)); self.connect(f2c, fll, clk, self.rx)
        for k in range(3): self.connect((fll, k + 1), nul1[k]); self.connect((clk, k + 1), nul2[k])
        for k in range(6): self.connect((self.rx, k), sinks[k])


tb = Top(); t0 = time.time(); tb.start()
while time.time() - t0 < seconds + 1:
    time.sleep(0.5)
    r = tb.rx
    print("t=%3.1f s locked %d frames %5d SER %.2e EVM %.1f dB offset left %+.0f Hz | core: locks %d hits %d misses %d lost %d" % (time.time() - t0, r.locked, r.frames, r.ser, r.evm_db, r.cfo_hz, r.core.locks, r.core.hits, r.core.misses, r.core.lost), flush=True)
    if time.time() - t0 > seconds + 0.3: break
tb.stop(); tb.wait()
r = tb.rx.core
print("RESULT: %d frames, %d symbol errors of %d (SER %.2e), %d locks, %d lost" % (r.frames, r.sym_err, r.sym_cnt, r.sym_err / max(r.sym_cnt, 1), r.locks, r.lost))
