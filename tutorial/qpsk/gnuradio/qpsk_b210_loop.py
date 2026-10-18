#!/usr/bin/env python3
"""GNU Radio QPSK reference link on one USRP B210 (chapter 4a): TX/RX port -> air (antennas close) -> RX2.

    source tools/gnuradio_env.sh
    python3 qpsk_b210_loop.py --tx-gain 60 --rx-gain 20 --rx-offset-hz 9500 --seconds 10 --out /tmp/qpsk_run
    python3 qpsk_analyze.py /tmp/qpsk_run

Transmitter: a repeating pseudo-random bit pattern (packed into bytes: `generic_mod` takes 8 bits per byte) -> `digital.generic_mod` (differential QPSK, Gray/pre-differential code, RRC pulse).
Receiver: exactly the chain inside `digital.generic_demod`, written out so that its internal signals can be recorded:
AGC -> FLL band-edge (coarse frequency) -> polyphase clock sync (symbol timing, 32 matched filters) -> constellation receiver
(Costas loop, order 4) + constellation decoder -> differential decoder -> symbol map -> unpack bits.
`--rx-offset-hz` tunes the RX LO that far from the TX LO, a deliberate carrier frequency offset (the P501 and the B210 are about 9.5 kHz apart).
Very low power: TX gain 60 dB and RX gain 20 dB with the antennas of the two ports a few centimetres apart (raise the RX gain only if the received peak stays well below 1.0) and the antennas of the two ports close together; check the rules where you are.
"""
import argparse, os, sys, time
import numpy as np
from gnuradio import gr, blocks, digital, filter, analog, uhd
from gnuradio.digital import mod_codes

SYMBOLS_PER_PERIOD = 4096                      # the bit pattern repeats every 8192 bits


def tx_bits(seed=1):
    return np.random.RandomState(seed).randint(0, 2, 2 * SYMBOLS_PER_PERIOD).astype(np.uint8)


class Tx(gr.top_block):
    def __init__(self, a):
        gr.top_block.__init__(self, "qpsk_tx")
        fs, sps, bw = a.samp_rate, a.sps, a.excess_bw
        const = digital.constellation_dqpsk().base()          # differential QPSK constellation: with it the loops may lock to any of the 4 rotations
        arity, nfilts = 4, 32
        os.makedirs(a.out, exist_ok=True)
        f = lambda n: os.path.join(a.out, n)

        # ---- transmitter ----
        src = blocks.vector_source_b(np.packbits(tx_bits()).tolist(), True)        # generic_mod takes PACKED bytes (8 bits per byte)
        mod = digital.generic_mod(const, differential=True, samples_per_symbol=sps, pre_diff_code=True, excess_bw=bw)
        amp = blocks.multiply_const_cc(a.tx_amp)
        sink = uhd.usrp_sink(a.dev_args, uhd.stream_args(cpu_format="fc32", args="", channels=[0]), "")
        sink.set_samp_rate(fs); sink.set_center_freq(uhd.tune_request(a.freq), 0); sink.set_gain(a.tx_gain, 0); sink.set_antenna("TX/RX", 0)
        self.connect(src, mod, amp, sink)
        # taps for the analysis use keep_m_in_n (a block that never finishes: a finished `head` on a branch would stall the whole stream)
        self.connect(amp, blocks.keep_m_in_n(gr.sizeof_gr_complex, 65536, int(fs), 0), blocks.file_sink(gr.sizeof_gr_complex, f("tx_raw.c64")))



class Rx(gr.top_block):
    def __init__(self, a):
        gr.top_block.__init__(self, "qpsk_rx")
        fs, sps, bw = a.samp_rate, a.sps, a.excess_bw
        const = digital.constellation_dqpsk().base(); arity, nfilts = 4, 32
        f = lambda n: os.path.join(a.out, n)
        usrp = uhd.usrp_source(a.dev_args, uhd.stream_args(cpu_format="fc32", args="", channels=[0]))
        usrp.set_samp_rate(fs); usrp.set_center_freq(uhd.tune_request(a.freq + a.rx_offset_hz), 0); usrp.set_gain(a.rx_gain, 0); usrp.set_antenna("RX2", 0)
        agc = analog.agc2_cc(0.6e-1, 1e-3, 1, 1)
        fll = digital.fll_band_edge_cc(sps, bw, 55, a.freq_bw)
        taps = filter.firdes.root_raised_cosine(nfilts, nfilts * sps, 1.0, bw, 11 * int(sps * nfilts))
        clk = digital.pfb_clock_sync_ccf(sps, a.timing_bw, taps, nfilts, nfilts // 2, a.max_rate_dev)
        costas = digital.costas_loop_cc(a.phase_bw, 4, False)             # carrier phase / fine frequency loop (order 4 for QPSK)
        dec = digital.constellation_decoder_cb(const)                       # nearest constellation point
        dif = digital.diff_decoder_bb(arity)
        mapper = digital.map_bb(mod_codes.invert_code(const.pre_diff_code()))        # undoes the pre-differential (Gray-like) code of the DQPSK constellation
        unp = blocks.unpack_k_bits_bb(2)
        bits = blocks.file_sink(gr.sizeof_char, f("rx_bits.u8"))
        self.connect(usrp, agc, fll, clk, costas, dec, dif, mapper, unp, bits)
        if a.save_raw:                                                                    # the whole received stream (about 31 MB per second): for offline replays
            self.connect(usrp, blocks.file_sink(gr.sizeof_gr_complex, f("rx_full.c64")))
        # taps for the analysis
        if a.save_raw:                                                                    # the whole received stream (about 31 MB per second): for offline replays
            self.connect(usrp, blocks.file_sink(gr.sizeof_gr_complex, f("rx_full.c64")))
        self.connect(usrp, blocks.keep_m_in_n(gr.sizeof_gr_complex, 65536, int(fs), 0), blocks.file_sink(gr.sizeof_gr_complex, f("rx_raw.c64")))
        # the FLL writes its outputs 1..3 (frequency, phase, error) only if all four outputs are connected
        self.connect((fll, 1), blocks.keep_one_in_n(gr.sizeof_float, 1000), blocks.file_sink(gr.sizeof_float, f("fll_freq.f32")))            # every 1000th sample
        self.connect((fll, 2), blocks.null_sink(gr.sizeof_float)); self.connect((fll, 3), blocks.null_sink(gr.sizeof_float))
        self.connect(clk, blocks.keep_m_in_n(gr.sizeof_gr_complex, 4000, int(fs / sps), 0), blocks.file_sink(gr.sizeof_gr_complex, f("sym_after_clock.c64")))
        self.connect(costas, blocks.keep_m_in_n(gr.sizeof_gr_complex, 4000, int(fs / sps), 0), blocks.file_sink(gr.sizeof_gr_complex, f("sym_after_costas.c64")))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--freq", type=float, default=915.0e6); p.add_argument("--samp-rate", type=float, default=3.84e6)
    p.add_argument("--sps", type=int, default=4); p.add_argument("--excess-bw", type=float, default=0.35)
    p.add_argument("--tx-gain", type=float, default=60); p.add_argument("--rx-gain", type=float, default=20); p.add_argument("--tx-amp", type=float, default=0.1)
    p.add_argument("--rx-offset-hz", type=float, default=0.0)
    p.add_argument("--freq-bw", type=float, default=2 * np.pi / 100); p.add_argument("--timing-bw", type=float, default=2 * np.pi / 100); p.add_argument("--phase-bw", type=float, default=2 * np.pi / 100)
    p.add_argument("--dev-args", default="num_send_frames=128,num_recv_frames=128,send_frame_size=16360,recv_frame_size=16360", help="UHD device arguments (buffer sizes against underflows)")
    p.add_argument("--max-rate-dev", type=float, default=0.05, help="limit of the timing loop (samples per symbol); the stock block uses 1.5")
    p.add_argument("--rx-delay", type=float, default=2.0, help="seconds the transmitter runs alone before the receiver starts")
    p.add_argument("--save-raw", action="store_true", help="also save the complete received I/Q stream (rx_full.c64)")
    p.add_argument("--seconds", type=float, default=10); p.add_argument("--out", default="/tmp/qpsk_run")
    a = p.parse_args()
    os.makedirs(a.out, exist_ok=True)
    tx, rx = Tx(a), Rx(a)
    tx.start(); time.sleep(a.rx_delay)                      # the transmitter first: the receiver's loops must not run on start-up noise
    rx.start(); time.sleep(a.seconds); rx.stop(); rx.wait()
    tx.stop(); tx.wait()
    print("done:", a.out)
