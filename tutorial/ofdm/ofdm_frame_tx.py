#!/usr/bin/env python3
"""The B210 transmitter of the OFDM frames (S&C symbol, T1, T2 (QPSK training), 44 data symbols of 24 16-QAM subcarriers + 4 QPSK pilots, 80 idle samples = 3840 samples = 1 ms: ofdm_model.tx_frame, PLAN_OFDM.md) for the P501 receiver rtl/ofdm_rx.v.
One frame period is repeated by a vector source into the UHD sink (915 MHz, 3.84 MSPS, TX/RX port).

    source tools/gnuradio_env.sh
    python3 tutorial/ofdm/ofdm_frame_tx.py --tx-gain 76 --rms 0.25 --seconds 120      # very low power: antennas a few centimetres apart; check the rules where you are before radiating
--rms is the digital rms of the active part of the frame; the peak-to-average ratio of OFDM is 10.7 dB (3.4 x the rms), so rms 0.25 gives peaks of 0.85 of the full scale (the 16-QAM single-carrier link used rms 0.5 with peaks of 0.9). Keep the B210 TX gain at 76 dB or less
(it compresses above about 78 dB). As a module:  tx = OfdmFrameTx(tx_gain=76); tx.start(); tx.set_gain(70); ...; tx.stop(); tx.wait()"""
import argparse, os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gnuradio import gr, blocks, uhd
import ofdm_model as Fm

DEV = "num_send_frames=128,num_recv_frames=128,send_frame_size=16360,recv_frame_size=16360"


def one_period(fill=False, sts=False):
    """3840 complex samples, unit rms over the active part (the 3760 samples before the idle slot); fill=True puts white noise of the same rms in the idle slot
    (with an empty slot and a strong signal the detector, which has only a small absolute energy guard, fires on the falling edge into the receiver noise)"""
    x, d = Fm.tx_frame(preamble="sts16" if sts else "scu"); na = 3808 if sts else 3760                    # the active part: the frame without its idle slot (32 samples of the STS frame, 80 of the S&C frame)
    x = x / np.sqrt(np.mean(np.abs(x[:na]) ** 2))
    if fill:
        r = np.random.RandomState(1); x[na:] = np.clip(r.randn(3840 - na), -2.5, 2.5) / np.sqrt(2) + 1j * np.clip(r.randn(3840 - na), -2.5, 2.5) / np.sqrt(2)
    return x.astype(np.complex64)


class OfdmFrameTx(gr.top_block):
    def __init__(self, tx_gain=76.0, rms=0.25, freq=915.0e6, samp_rate=3.84e6, dev_args=DEV, fill=False, sts=False):
        gr.top_block.__init__(self, "ofdm_frame_tx")
        assert 0 <= rms <= 0.29, "the peaks of the OFDM frame are 3.4 x the rms: rms <= 0.29"
        self.period = one_period(fill, sts)
        src = blocks.vector_source_c(self.period.tolist(), True)
        self.amp = blocks.multiply_const_cc(float(rms))
        sink = uhd.usrp_sink(dev_args, uhd.stream_args(cpu_format="fc32", args="", channels=[0]), "")
        sink.set_samp_rate(samp_rate); sink.set_center_freq(uhd.tune_request(freq), 0); sink.set_gain(tx_gain, 0); sink.set_antenna("TX/RX", 0)
        self.sink = sink
        self.connect(src, self.amp, sink)

    def set_freq(self, f): self.sink.set_center_freq(uhd.tune_request(f), 0)
    def set_rms(self, rms):
        assert 0 <= rms <= 0.29; self.amp.set_k(float(rms))
    def set_gain(self, g):
        assert 0 <= g <= 89.75; self.sink.set_gain(g, 0)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tx-gain", type=float, default=76.0); p.add_argument("--rms", type=float, default=0.25); p.add_argument("--freq", type=float, default=915.0e6); p.add_argument("--seconds", type=float, default=30); p.add_argument("--fill", action="store_true", help="noise in the idle slot instead of zeros")
    p.add_argument("--sts", action="store_true", help="the frame of the 128-sample short training field (overlay p501_ofdm_rx_sts)")
    a = p.parse_args()
    tx = OfdmFrameTx(a.tx_gain, a.rms, a.freq, fill=a.fill, sts=a.sts); tx.start()
    print("transmitting OFDM frames (3840 samples, 1 ms, 3.84 MS/s) for %g s, TX gain %g dB, rms %g (peaks %.2f), %.6f MHz" % (a.seconds, a.tx_gain, a.rms, 3.5 * a.rms, a.freq / 1e6), flush=True)
    time.sleep(a.seconds); tx.stop(); tx.wait()
