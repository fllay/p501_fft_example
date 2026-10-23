#!/usr/bin/env python3
"""The B210 transmitter of the 16-QAM frames (CP 8 | ZC 63 | 14 x (63 16-QAM + 1 pilot), PRBS-15 payload restarted in every frame: frame16.py) for the P501 receiver rtl/qam16_rx.v.
The samples are made in Python (RRC 0.35, 4 samples per symbol, make_signal16.tx_samples), one frame period (3868 samples) is repeated by a vector source into the UHD sink (915 MHz, 3.84 MSPS, TX/RX port).

    source tools/gnuradio_env.sh
    python3 qam16_frame_tx.py --tx-gain 80 --seconds 30          # very low power: antennas a few centimetres apart; check the rules where you are before radiating
As a module:  tx = Qam16FrameTx(tx_gain=80); tx.start(); tx.set_gain(84); ...; tx.stop(); tx.wait()"""
import argparse, os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gnuradio import gr, blocks, uhd
import frame16 as F
from make_signal16 import tx_samples, SPS

DEV = "num_send_frames=128,num_recv_frames=128,send_frame_size=16360,recv_frame_size=16360"


def one_period(rms=0.18):
    """3868 complex samples = exactly one frame, the shaped signal of the frame repeated (the filter tails of the neighbouring frames included); unit-RMS symbols scaled to `rms`"""
    sym, _ = F.make_frames(5, "prbs15")
    x = tx_samples(sym)
    n = F.FRAME * SPS
    seg = x[2 * n:3 * n]                                                      # the middle frame: its neighbours are the same frame
    seg = seg / np.sqrt(np.mean(np.abs(x[n:4 * n]) ** 2)) * rms
    return seg.astype(np.complex64)


class Qam16FrameTx(gr.top_block):
    def __init__(self, tx_gain=80.0, rms=0.18, freq=915.0e6, samp_rate=3.84e6, dev_args=DEV):
        gr.top_block.__init__(self, "qam16_frame_tx")
        self.period = one_period(1.0)                                      # unit RMS; the amplitude is a separate multiplier so that it can be changed live
        src = blocks.vector_source_c(self.period.tolist(), True)
        self.amp = blocks.multiply_const_cc(float(rms))
        sink = uhd.usrp_sink(dev_args, uhd.stream_args(cpu_format="fc32", args="", channels=[0]), "")
        sink.set_samp_rate(samp_rate); sink.set_center_freq(uhd.tune_request(freq), 0); sink.set_gain(tx_gain, 0); sink.set_antenna("TX/RX", 0)
        self.sink = sink
        self.connect(src, self.amp, sink)

    def set_freq(self, f):
        self.sink.set_center_freq(uhd.tune_request(f), 0)

    def set_rms(self, rms):
        """digital RMS of the samples, live (the peak is 1.8 x the RMS)"""
        assert 0 <= rms <= 0.5
        self.amp.set_k(float(rms))

    def set_gain(self, g):
        """B210 TX gain in dB, live (the hardware limit is 89.75)"""
        assert 0 <= g <= 89.75
        self.sink.set_gain(g, 0)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tx-gain", type=float, default=80.0); p.add_argument("--rms", type=float, default=0.18); p.add_argument("--freq", type=float, default=915.0e6); p.add_argument("--seconds", type=float, default=30)
    a = p.parse_args()
    tx = Qam16FrameTx(a.tx_gain, a.rms, a.freq); tx.start(); print("transmitting 16-QAM frames (967 symbols, 1.007 ms) for %g s, TX gain %g dB" % (a.seconds, a.tx_gain), flush=True)
    time.sleep(a.seconds); tx.stop(); tx.wait()
