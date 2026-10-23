#!/usr/bin/env python3
"""Is the B210's transmitted 16-QAM signal clean? The B210 transmits (the light vector-source flowgraph of qam16_frame_tx.py) and, in the same process, records its own RX2 input to a file (no processing during the recording: no
underflows); the recording is then run through the receiver chain of qam16_b210_frame_rx.grc offline. For every TX gain the RX gain is set so that the recorded level is about 0.15 RMS (no saturation, the same level for every row).
    source tools/gnuradio_env.sh; python3 test_b210_record.py --tx-gains 30,45,60,70,80,86 --rms 0.35
Very low power; the antennas a few cm apart; check the rules where you are before radiating."""
import argparse, os, subprocess, sys, tempfile, time
import numpy as np
from gnuradio import gr, blocks, analog, digital, uhd
from gnuradio.filter import firdes
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
p = argparse.ArgumentParser()
p.add_argument("--no-offline", action="store_true", help="only record (files in /tmp/qam16_rec_keep)"); p.add_argument("--tx-gains", default="30,60,80,86"); p.add_argument("--rms", type=float, default=0.35); p.add_argument("--seconds", type=float, default=1.0); p.add_argument("--freq", type=float, default=915e6)
a = p.parse_args()
tmp = tempfile.mkdtemp(prefix="qam16_rec_")
for g in ("qam16_b210_frame_tx", "qam16_b210_frame_rx"):
    subprocess.run(["grcc", "-o", tmp, os.path.join(HERE, g + ".grc")], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
sys.path.insert(0, tmp)
import qam16_b210_frame_tx_epy_block_0 as T
import qam16_b210_frame_rx_epy_block_0 as R
fs, sps, nfilts = 3.84e6, 4, 32
DEV = "num_send_frames=128,num_recv_frames=128,send_frame_size=16360,recv_frame_size=16360"


class Rec(gr.top_block):
    def __init__(self, path, n, tx_gain, rx_gain):
        gr.top_block.__init__(self, "rec")
        self.tx = T.blk()
        period = self.tx.data
        src = blocks.vector_source_c(period.tolist(), True); amp = blocks.multiply_const_cc(a.rms)
        sink = uhd.usrp_sink(DEV, uhd.stream_args(cpu_format="fc32", args="", channels=[0]), "")
        sink.set_samp_rate(fs); sink.set_center_freq(uhd.tune_request(a.freq), 0); sink.set_gain(tx_gain, 0); sink.set_antenna("TX/RX", 0)
        rxs = uhd.usrp_source(DEV, uhd.stream_args(cpu_format="fc32", args="", channels=[0]))
        rxs.set_samp_rate(fs); rxs.set_center_freq(uhd.tune_request(a.freq), 0); rxs.set_gain(rx_gain, 0); rxs.set_antenna("RX2", 0)
        self.keep = [src, amp, sink, rxs]
        self.connect(src, amp, sink)
        self.connect(rxs, blocks.skiphead(gr.sizeof_gr_complex, int(0.3 * fs)), blocks.head(gr.sizeof_gr_complex, n), blocks.file_sink(gr.sizeof_gr_complex, path))


def record(tx_gain, rx_gain, secs, path):
    tb = Rec(path, int(secs * fs) + 0, tx_gain, rx_gain)
    tb.start()
    want = int(secs * fs) * 8; t0 = time.time()
    while (not os.path.exists(path) or os.path.getsize(path) < want) and time.time() - t0 < secs + 15: time.sleep(0.1)      # the transmit branch never ends: stop the flowgraph when the recording is complete
    time.sleep(0.2); tb.stop(); tb.wait()
    return np.fromfile(path, dtype=np.complex64)


class Offline(gr.top_block):
    def __init__(self, path):
        gr.top_block.__init__(self, "offline")
        src = blocks.file_source(gr.sizeof_gr_complex, path, False)
        agc = analog.agc2_cc(0.06, 1e-3, 0.947, 1.0, 200)
        c2f = blocks.complex_to_float(); ri = analog.rail_ff(-3, 3); rq = analog.rail_ff(-3, 3); f2c = blocks.float_to_complex()
        fll = digital.fll_band_edge_cc(sps, 0.35, 55, 2 * np.pi / 1600)
        taps = firdes.root_raised_cosine(nfilts, nfilts * sps, 1.0, 0.35, 11 * sps * nfilts)
        clk = digital.pfb_clock_sync_ccf(sps, 2 * np.pi / 400, taps, nfilts, nfilts // 2, 0.05, 1)
        self.rx = R.blk(symbol_rate=fs / sps)
        self.keep = [blocks.null_sink(gr.sizeof_gr_complex)] + [blocks.null_sink(gr.sizeof_float) for _ in range(11)]
        self.connect(src, agc, c2f); self.connect((c2f, 0), ri, (f2c, 0)); self.connect((c2f, 1), rq, (f2c, 1)); self.connect(f2c, fll, clk, self.rx)
        for k in range(3): self.connect((fll, k + 1), self.keep[6 + k]); self.connect((clk, k + 1), self.keep[9 + k])
        for k in range(6): self.connect((self.rx, k), self.keep[k])


print("%-8s %-8s %-9s %-10s | %-8s %-10s %-9s %-9s" % ("TX gain", "RX gain", "rec. rms", "rec. peak", "frames", "SER", "EVM dB", "offset Hz"))
for tg in [float(v) for v in a.tx_gains.split(",")]:
    rg = 20.0
    for it in range(3):
        x = record(tg, rg, 0.3, os.path.join(tmp, "rec.c64"))
        rms = float(np.sqrt(np.mean(np.abs(x) ** 2)))
        newg = float(np.clip(rg + 20 * np.log10(0.15 / max(rms, 1e-6)), 0, 76))
        if abs(newg - rg) < 1.5: break
        rg = round(newg)
    x = record(tg, rg, a.seconds, os.path.join(tmp, "rec.c64"))
    os.makedirs("/tmp/qam16_rec_keep", exist_ok=True); x.tofile("/tmp/qam16_rec_keep/rec_tx%d_rx%d.c64" % (tg, rg))
    rms, peak = float(np.sqrt(np.mean(np.abs(x) ** 2))), float(np.max(np.abs(x)))
    if a.no_offline: print("%-8.0f %-8.0f %-9.3f %-10.3f | recorded" % (tg, rg, rms, peak), flush=True); continue
    off = Offline(os.path.join(tmp, "rec.c64")); off.start(); off.wait(); c = off.rx.core
    print("%-8.0f %-8.0f %-9.3f %-10.3f | %-8d %-10.2e %-9.1f %-9.0f  (locks %d lost %d)" % (tg, rg, rms, peak, c.frames, c.sym_err / max(c.sym_cnt, 1), c.evm_db, c.om / (2 * np.pi) * fs / sps, c.locks, c.lost), flush=True)
