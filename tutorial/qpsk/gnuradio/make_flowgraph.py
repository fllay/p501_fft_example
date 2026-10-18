#!/usr/bin/env python3
"""Generates the two GNU Radio flowgraphs of the interactive link test (the B210 side), with GNU Radio Companion's own Python API, so that every block gets
all its default parameters and the result is validated the way Companion does it.

    source tools/gnuradio_env.sh
    python3 make_flowgraph.py                      # writes qpsk_b210_tx.grc and qpsk_b210_rx.grc next to this file
    grcc qpsk_b210_tx.grc                          # compiles one to Python (or open the .grc files in gnuradio-companion)

  qpsk_b210_tx.grc  (direction A, B210 -> P501):  PRBS-15 (8 periods = 32767 packed bytes, repeating) -> differential QPSK (generic_mod, RRC 0.35, 4 samples/symbol)
                    -> amplitude x Transmit -> TX/RX port; the spectrum of what is sent is shown. Transmit is OFF when it starts.
  qpsk_b210_rx.grc  (direction B, P501 -> B210):  RX2 -> AGC -> limiter -> FLL band-edge -> polyphase clock sync -> Costas loop -> decision -> differential decode -> bits
                    -> PRBS-15 checker -> BER; constellation after the Costas loop, spectrum of the received signal.

Two flowgraphs, not one: the transmit and the receive chain together load the host enough to cause transmit underflows, which degrade the signal the P501 sees.
Only one direction is used at a time anyway (both radios use 915.0 MHz).
"""
import os
from gnuradio import gr
from gnuradio.grc.core.platform import Platform

HERE = os.path.dirname(os.path.abspath(__file__))

PRBS_SOURCE = '''
import numpy as np
from gnuradio import gr


class blk(gr.sync_block):
    """PRBS-15 (x^15 + x^14 + 1, seed 0x7FFF) as packed bytes, repeated: 8 periods = 262136 bits = 32767 whole bytes, so the repeat is seamless.
    The bits are the ones that the FPGA transmitter (qpsk_tx.v) sends and that the FPGA receiver's self-synchronising checker expects."""

    def __init__(self):
        gr.sync_block.__init__(self, name="PRBS-15 bytes", in_sig=None, out_sig=[np.uint8])
        s, bits = 0x7FFF, np.zeros(32767, dtype=np.uint8)
        for i in range(32767):
            bits[i] = (s >> 14) & 1
            s = ((s << 1) & 0x7FFF) | (((s >> 14) ^ (s >> 13)) & 1)
        self.data = np.packbits(np.tile(bits, 8))
        self.pos = 0

    def work(self, input_items, output_items):
        out = output_items[0]
        n = len(out)
        idx = (self.pos + np.arange(n)) % len(self.data)
        out[:] = self.data[idx]
        self.pos = (self.pos + n) % len(self.data)
        return n
'''

PRBS_CHECK = '''
import numpy as np
from gnuradio import gr


class blk(gr.sync_block):
    """Self-synchronising PRBS-15 checker, the same rule as the FPGA's: a[n] = a[n-15] ^ a[n-14]; a mismatch is counted when the received bit differs from
    the prediction, and an isolated bit error gives 3 mismatches. Input: one bit per byte. Output: the bit error rate over about the last second
    (mismatches / 3 / bits, exponentially weighted), one value per input bit; 0.17 means 'not locked' (random bits). A stream that is not half ones (for example
    stuck at 0, which also satisfies the PRBS rule) is reported as 0.5."""

    def __init__(self, window_bits=1920000):
        gr.sync_block.__init__(self, name="PRBS-15 BER", in_sig=[np.uint8], out_sig=[np.float32])
        self.window = float(window_bits)
        self.hist = np.zeros(15, dtype=np.uint8)
        self.filled = 0
        self.m = 0.0
        self.n = 0.0
        self.o = 0.0
        self.ber = 0.5

    def work(self, input_items, output_items):
        x = input_items[0] & 1
        a = np.concatenate([self.hist, x])
        if self.filled >= 15:
            pred = a[:-15] ^ a[1:-14]
            mism = float(np.count_nonzero(a[15:] != pred))
            k = np.exp(-len(x) / self.window)
            self.m = self.m * k + mism
            self.n = self.n * k + len(x)
            self.o = self.o * k + float(np.count_nonzero(x))
            self.ber = 0.5 if abs(self.o / self.n - 0.5) > 0.15 else self.m / 3.0 / self.n
        self.filled += len(x)
        self.hist = a[-15:].copy()
        output_items[0][:] = self.ber
        return len(x)
'''



def new_graph(ident, title, description):
    platform = Platform(name=ident, prefs=gr.prefs(), version=gr.version(), version_parts=(gr.major_version(), gr.api_version(), gr.minor_version()), install_prefix=gr.prefix())
    platform.build_library()
    fg = platform.make_flow_graph()
    counts = {}

    def add(kind, ident_=None, pos=(0, 0), **params):
        b = fg.new_block(kind)
        counts[kind] = counts.get(kind, -1) + 1
        b.params["id"].set_value(ident_ or "%s_%d" % (kind, counts[kind]))
        if "_source_code" in params:                 # the parameters of an embedded Python block exist only after its source has been read
            b.params["_source_code"].set_value(params.pop("_source_code")); b.rewrite()
        for k, v in params.items():
            b.params[k].set_value(v)
        b.states["coordinate"] = pos
        b.rewrite()
        return b

    def conn(a, b, pa="0", pb="0"):
        fg.connect(a.get_source(pa), b.get_sink(pb))

    o = fg.options_block
    for k, v in dict(id=ident, title=title, author="p501_fft_example", generate_options="qt_gui", description=description, window_size="(1100, 800)", run_options="prompt").items():
        o.params[k].set_value(v)
    o.states["coordinate"] = (8, 8)
    add("variable", "samp_rate", (8, 80), value="3840000", comment="3.84 MSPS: the P501's sample rate; 960 ksym/s at 4 samples per symbol")
    add("variable", "sps", (8, 130), value="4")
    add("variable", "excess_bw", (8, 180), value="0.35", comment="root-raised-cosine roll-off")
    add("variable", "freq", (8, 230), value="915e6", comment="carrier; check the rules where you are before transmitting")
    add("variable", "const_dqpsk", (8, 280), value="digital.constellation_dqpsk().base()", comment="differential QPSK: rotation-proof, the same as the FPGA")
    return platform, fg, add, conn


def finish(platform, fg, name):
    fg.rewrite(); fg.validate()
    problems = [(b.name, b.get_error_messages()) for b in fg.iter_enabled_blocks() if not b.is_valid()]
    problems += [("flowgraph", fg.get_error_messages())] if not fg.is_valid() else []
    for n, msg in problems: print("PROBLEM", n, msg)
    out = os.path.join(HERE, name)
    platform.save_flow_graph(out, fg)
    print("wrote", out, "- blocks:", len(fg.blocks), "- problems:", len(problems))


DEV = "num_send_frames=128,num_recv_frames=128,send_frame_size=16360,recv_frame_size=16360"


def build_tx():
    platform, fg, add, conn = new_graph("qpsk_b210_tx", "B210 transmitter: PRBS-15 DQPSK for the P501's FPGA receiver",
                                        "The B210 transmits PRBS-15 differential QPSK at 915 MHz, 3.84 MSPS; the P501 notebook receives it with its FPGA receiver.")
    add("variable_qtgui_chooser", "tx_on", (240, 20), label="Transmit (B210 TX/RX port)", type="int", num_opts="2", option0="0", label0="OFF", option1="1", label1="ON",
        value="0", gui_hint="0,0,1,1", widget="radio_buttons", comment="OFF at start. Switch ON when the P501 notebook is ready to receive.")
    add("variable_qtgui_range", "tx_gain", (240, 100), label="B210 TX gain (dB)", start="0", stop="80", step="1", value="80", gui_hint="0,1,1,3", widget="counter_slider",
        comment="very low power: antennas a few centimetres apart; 80 dB decodes cleanly at the P501, 70 is marginal, 60 does not lock")
    add("variable_qtgui_range", "tx_amp", (240, 180), label="TX digital amplitude", start="0", stop="0.5", step="0.01", value="0.25", gui_hint="1,0,1,4", widget="counter_slider")
    prbs = add("epy_block", None, (240, 300), _source_code=PRBS_SOURCE)
    mod = add("digital_constellation_modulator", None, (520, 290), constellation="const_dqpsk", differential="True", samples_per_symbol="sps", excess_bw="excess_bw",
              verbose="False", log="False", truncate="False")
    amp = add("blocks_multiply_const_vxx", None, (800, 300), type="complex", const="tx_amp*tx_on", vlen="1")
    sink = add("uhd_usrp_sink", None, (1040, 280), type="fc32", num_mboards="1", nchan="1", samp_rate="samp_rate", center_freq0="freq", gain0="tx_gain", ant0="TX/RX", dev_addr="",
               dev_args=DEV, comment="the B210 transmitter (TX/RX port)")
    spec = add("qtgui_freq_sink_x", None, (1040, 440), name='"spectrum of the transmitted signal"', type="complex", fftsize="2048", fc="0", bw="samp_rate", gui_hint="2,0,5,4", ymin="-100", ymax="20",
               update_time="0.1", average="0.2", grid="True", legend="False", label1="TX")
    conn(prbs, mod); conn(mod, amp); conn(amp, sink); conn(amp, spec)
    finish(platform, fg, "qpsk_b210_tx.grc")


def build_rx():
    platform, fg, add, conn = new_graph("qpsk_b210_rx", "B210 receiver: the P501's FPGA transmitter, decoded with GNU Radio",
                                        "The B210 receives the P501's FPGA QPSK transmitter (PRBS-15) at 915 MHz and decodes it: constellation, spectrum and bit error rate.")
    add("variable", "nfilts", (8, 330), value="32", comment="arms of the polyphase clock sync")
    add("variable", "rrc_taps", (8, 380), value="firdes.root_raised_cosine(nfilts, nfilts*sps, 1.0, excess_bw, 11*int(sps*nfilts))")
    add("import", "import_firdes", (8, 430), imports="from gnuradio.filter import firdes")
    add("variable_qtgui_range", "rx_gain", (240, 60), label="B210 RX gain (dB)", start="0", stop="76", step="1", value="45", gui_hint="0,0,1,4", widget="counter_slider",
        comment="raise it until the received spectrum is clearly above the noise; lower it if the constellation is squashed")
    add("variable_qtgui_range", "bw_div", (240, 140), label="Loop bandwidth: 2 pi / N (FLL, timing, Costas)", start="50", stop="1600", step="10", value="400", gui_hint="1,0,1,4",
        widget="counter_slider", comment="wide (small N) pulls in fast and is noisy; narrow (large N) is quieter but may not pull in")
    src = add("uhd_usrp_source", None, (240, 240), type="fc32", num_mboards="1", nchan="1", samp_rate="samp_rate", center_freq0="freq", gain0="rx_gain", ant0="RX2", dev_addr="",
              dev_args=DEV, comment="the B210 receiver (RX2 port)")
    agc = add("analog_agc2_xx", None, (520, 240), type="complex", attack_rate="0.06", decay_rate="1e-3", reference="1", gain="1", max_gain="200")
    # the limiter: when the signal appears after the receiver has run on noise, the AGC (gain up to 200) outputs a burst of tens of units; the polyphase clock sync
    # then runs away and stalls the whole flowgraph. Limiting each component to +-1.5 (a normal symbol is about 1.0) prevents that.
    c2f = add("blocks_complex_to_float", None, (700, 240), vlen="1"); r_i = add("analog_rail_ff", None, (760, 200), lo="-1.5", hi="1.5"); r_q = add("analog_rail_ff", None, (760, 300), lo="-1.5", hi="1.5")
    f2c = add("blocks_float_to_complex", None, (880, 240), vlen="1")
    fll = add("digital_fll_band_edge_cc", None, (1040, 240), samps_per_sym="sps", rolloff="excess_bw", filter_size="55", w="2*3.14159265/bw_div")
    clk = add("digital_pfb_clock_sync_xxx", None, (1260, 240), type="ccf", sps="sps", loop_bw="2*3.14159265/bw_div", taps="rrc_taps", filter_size="nfilts", init_phase="nfilts//2", max_dev="0.05")
    cos = add("digital_costas_loop_cc", None, (1480, 240), w="2*3.14159265/bw_div", order="4", use_snr="False")
    dec = add("digital_constellation_decoder_cb", None, (240, 420), constellation="const_dqpsk")
    dif = add("digital_diff_decoder_bb", None, (460, 420), modulus="4")
    mp = add("digital_map_bb", None, (660, 420), map="[0, 1, 3, 2]", comment="inverse of the pre-differential code (it is its own inverse)")
    unp = add("blocks_unpack_k_bits_bb", None, (860, 420), k="2")
    ber = add("epy_block", None, (1060, 420), _source_code=PRBS_CHECK, window_bits="480000")
    keep = add("blocks_keep_one_in_n", None, (1300, 420), type="float", n="19200", vlen="1")
    num = add("qtgui_number_sink", None, (1480, 420), name='"PRBS-15 bit error rate"', type="float", nconnections="1", label1="BER", unit1="", graph_type="qtgui.NUM_GRAPH_NONE",
              gui_hint="2,0,1,4", avg="0.0", update_time="0.25", min="0", max="1", autoscale="False", comment="0.17 = not locked; 0.5 = no valid stream; 0 = locked and error-free")
    cons = add("qtgui_const_sink_x", None, (1480, 560), name='"after the Costas loop"', type="complex", nconnections="1", size="1024", gui_hint="3,0,4,2",
               xmin="-2", xmax="2", ymin="-2", ymax="2", update_time="0.1", label1="symbols", style1="0", width1="1", marker1="0", color1='"blue"', grid="True", legend="False")
    spec = add("qtgui_freq_sink_x", None, (240, 560), name='"received spectrum"', type="complex", fftsize="2048", fc="0", bw="samp_rate", gui_hint="3,2,4,2", ymin="-120", ymax="0",
               update_time="0.1", average="0.2", grid="True", legend="False", label1="B210 RX2")
    conn(src, agc); conn(agc, c2f); conn(c2f, r_i, "0", "0"); conn(c2f, r_q, "1", "0"); conn(r_i, f2c, "0", "0"); conn(r_q, f2c, "0", "1"); conn(f2c, fll); conn(fll, clk)
    conn(clk, cos); conn(cos, dec); conn(cos, cons); conn(dec, dif); conn(dif, mp); conn(mp, unp); conn(unp, ber); conn(ber, keep); conn(keep, num); conn(src, spec)
    # the FLL and the clock sync have three extra outputs each (frequency/phase/error, rate/phase/error): each goes to a null sink
    for blk_ in (fll, clk):
        for port in ("1", "2", "3"):
            nul = add("blocks_null_sink", None, (1700, 240), type="float", num_inputs="1", vlen="1")
            conn(blk_, nul, port, "0")
    finish(platform, fg, "qpsk_b210_rx.grc")


if __name__ == "__main__":
    build_tx(); build_rx()
