#!/usr/bin/env python3
"""The B210 frame transmitter for the m-sequence synchronisation tests (chapter 4e, part 1), in Python: the same chain as qpsk_b210_tx.grc (differential QPSK, RRC 0.35,
4 samples per symbol), but the bits are FRAMES: a 64-symbol m-sequence preamble followed by PL payload symbols (PRBS-15), repeated.

    source tools/gnuradio_env.sh
    python3 qpsk_frame_tx.py --tx-gain 80 --payload 960 --seconds 30        # transmits for 30 s (very low power: antennas a few centimetres apart)

As a module:  tx = FrameTx(tx_gain=80, payload=960); tx.start(); ...; tx.stop(); tx.wait()
The frame format is in qpsk_frame.py (preamble: reference symbol + 63 phase steps from the m-sequence x^6 + x + 1; payload: PRBS-15 restarted in every frame)."""
import argparse, os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gnuradio import gr, blocks, digital, uhd
from qpsk_frame import frame_bits

DEV = "num_send_frames=128,num_recv_frames=128,send_frame_size=16360,recv_frame_size=16360"


class FrameTx(gr.top_block):
    def __init__(self, tx_gain=80.0, tx_amp=0.25, freq=915.0e6, payload=960, samp_rate=3.84e6, sps=4, excess_bw=0.35, dev_args=DEV, gap_symbols=0):
        gr.top_block.__init__(self, "qpsk_frame_tx")
        assert payload % 4 == 0, "the payload must be a multiple of 4 symbols (whole bytes)"
        bits = frame_bits(payload)
        if gap_symbols:                                                    # optional silence after every frame is not possible with this chain: the option is for the offline tests only
            raise NotImplementedError
        self.nbytes = len(bits) // 8
        src = blocks.vector_source_b(np.packbits(bits).tolist(), True)
        mod = digital.generic_mod(digital.constellation_dqpsk().base(), differential=True, samples_per_symbol=sps, pre_diff_code=True, excess_bw=excess_bw)
        amp = blocks.multiply_const_cc(tx_amp)
        sink = uhd.usrp_sink(dev_args, uhd.stream_args(cpu_format="fc32", args="", channels=[0]), "")
        sink.set_samp_rate(samp_rate); sink.set_center_freq(uhd.tune_request(freq), 0); sink.set_gain(tx_gain, 0); sink.set_antenna("TX/RX", 0)
        self.sink = sink
        self.connect(src, mod, amp, sink)

    def set_freq(self, f):
        """B210 carrier in Hz, live."""
        self.sink.set_center_freq(uhd.tune_request(f), 0)

    def set_gain(self, g):
        """B210 TX gain in dB, live (limited to 80)."""
        assert g <= 80
        self.sink.set_gain(g, 0)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tx-gain", type=float, default=80.0); p.add_argument("--tx-amp", type=float, default=0.25); p.add_argument("--freq", type=float, default=915.0e6)
    p.add_argument("--payload", type=int, default=960, help="payload symbols per frame (a multiple of 4); the frame is 64 + payload symbols")
    p.add_argument("--seconds", type=float, default=30)
    a = p.parse_args()
    assert a.tx_gain <= 80, "B210 TX gain is limited to 80 dB"
    tx = FrameTx(a.tx_gain, a.tx_amp, a.freq, a.payload); tx.start(); print("transmitting frames (%d symbols, %.3f ms each) for %g s" % (64 + a.payload, (64 + a.payload) / 960.0, a.seconds), flush=True)
    time.sleep(a.seconds); tx.stop(); tx.wait()
