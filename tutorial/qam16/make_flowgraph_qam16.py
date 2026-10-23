#!/usr/bin/env python3
"""Generates the two GNU Radio flowgraphs of the 16-QAM link (the B210 side), with Companion's own Python API (the helpers of ../qpsk/gnuradio/make_flowgraph.py):

    source tools/gnuradio_env.sh
    python3 make_flowgraph_qam16.py                 # writes qam16_b210_frame_tx.grc and qam16_b210_frame_rx.grc next to this file
    grcc qam16_b210_frame_rx.grc                    # or open them in gnuradio-companion

qam16_b210_frame_tx.grc  (B210 -> P501): the 16-QAM frames [CP 8 | ZC word 63 | 14 x (63 16-QAM + 1 pilot)] with the PRBS-15 payload restarted in every frame (the pattern the P501's FPGA receiver counts against),
                         shaped with the root-raised-cosine 0.35 at 4 samples per symbol (one frame period, 3868 samples, repeated by an embedded Python block) -> amplitude x Transmit -> TX/RX port.
qam16_b210_frame_rx.grc  (P501 -> B210): RX2 -> AGC -> limiter -> FLL band-edge -> polyphase clock sync -> the block "16-QAM ZC receiver" (the streaming receiver qam16_stream_rx.StreamRx: Zadoff-Chu frame sync,
                         carrier from the word, PLL on the data, pilots and the known word, PRBS-15 check): constellation of the data symbols, symbol error rate, EVM, lock, frames, carrier offset; spectrum.
Only one direction is used at a time (both radios use 915.0 MHz)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "qpsk", "gnuradio"))
import make_flowgraph as G
G.HERE = HERE                                                         # finish() writes next to this file

CORE = open(os.path.join(HERE, "qam16_stream_rx.py")).read()

TX_SOURCE = '''
import numpy as np
from gnuradio import gr


class blk(gr.sync_block):
    """The 16-QAM frames as a periodic complex stream at 4 samples per symbol and unit RMS: CP 8 | ZC word 63 (root 1) | 14 x (63 16-QAM symbols + 1 pilot), 967 symbols = 3868 samples per frame;
    Gray levels -3 -1 3 1 (00 01 10 11) / sqrt(10), pilots +-1 (1 1 -1 1 -1 -1 1 1 1 -1 -1 1 -1 1), the payload = PRBS-15 (x^15 + x^14 + 1, seed 0x7FFF, 4 bits per symbol, I = the first two bits)
    restarted in every frame; root-raised-cosine 0.35, 45 taps. The period is made from the middle frame of five, so that the repetition is seamless."""

    def __init__(self):
        gr.sync_block.__init__(self, name="16-QAM frames", in_sig=None, out_sig=[np.complex64])
        N, NCP, NB, ND, SPS, BETA = 63, 8, 14, 63, 4, 0.35
        n = np.arange(N)
        zc = np.exp(-1j * np.pi * n * (n + 1) / N)
        s, bits = 0x7FFF, []
        for i in range(4 * NB * ND):
            bits.append((s >> 14) & 1)
            s = ((s << 1) & 0x7FFF) | (((s >> 14) ^ (s >> 13)) & 1)
        b = np.array(bits, dtype=int).reshape(NB * ND, 4)
        idx = b[:, 0] * 8 + b[:, 1] * 4 + b[:, 2] * 2 + b[:, 3]
        gray = np.array([-3, -1, 3, 1]) / np.sqrt(10.0)
        data = (gray[idx >> 2] + 1j * gray[idx & 3]).reshape(NB, ND)
        pil = np.array([1, 1, -1, 1, -1, -1, 1, 1, 1, -1, -1, 1, -1, 1], dtype=float)
        frame = np.concatenate([zc[-NCP:], zc, np.concatenate([data, pil[:, None].astype(complex)], axis=1).reshape(-1)])
        sym = np.tile(frame, 5)
        k = (np.arange(11 * SPS + 1) - 5 * SPS) / SPS
        h = np.zeros(len(k))
        for i, t in enumerate(k):
            if abs(t) < 1e-12: h[i] = 1 + BETA * (4 / np.pi - 1)
            elif abs(abs(t) - 1 / (4 * BETA)) < 1e-9: h[i] = BETA / np.sqrt(2) * ((1 + 2 / np.pi) * np.sin(np.pi / (4 * BETA)) + (1 - 2 / np.pi) * np.cos(np.pi / (4 * BETA)))
            else: h[i] = (np.sin(np.pi * t * (1 - BETA)) + 4 * BETA * t * np.cos(np.pi * t * (1 + BETA))) / (np.pi * t * (1 - (4 * BETA * t) ** 2))
        up = np.zeros(len(sym) * SPS, dtype=complex); up[::SPS] = sym
        x = np.convolve(up, h)[len(h) // 2:len(h) // 2 + len(up)]
        L = len(frame) * SPS
        seg = x[2 * L:3 * L] / np.sqrt(np.mean(np.abs(x[L:4 * L]) ** 2))
        self.data = seg.astype(np.complex64)
        self.pos = 0

    def work(self, input_items, output_items):
        out = output_items[0]
        n = len(out)
        idx = (self.pos + np.arange(n)) % len(self.data)
        out[:] = self.data[idx]
        self.pos = (self.pos + n) % len(self.data)
        return n
'''

RX_WRAPPER = '''

from gnuradio import gr


class blk(gr.basic_block):
    """16-QAM ZC receiver. Input: the symbols after the polyphase clock sync (1 sample per symbol, about unit RMS). Outputs: 0 the derotated data symbols of the frames found (882 per frame, for the constellation),
    1 symbol error rate since the lock (against the PRBS-15 of the frame), 2 EVM of the last frame (dB), 3 lock (1 / 0), 4 frames decoded, 5 carrier offset left for the PLL (Hz, at 960 ksym/s):
    one value per frame (one per call while not locked)."""

    def __init__(self, loop_bw=0.02, thr_search=0.6, thr_lock=0.45, pilot_weight=3.0, aided=True, symbol_rate=960000.0):
        gr.basic_block.__init__(self, name="16-QAM ZC receiver", in_sig=[np.complex64], out_sig=[np.complex64, np.float32, np.float32, np.float32, np.float32, np.float32])
        self.core = StreamRx(loop_bw=loop_bw, thr_search=thr_search, thr_lock=thr_lock, pilot_weight=pilot_weight, aided=bool(aided))
        self.rs = float(symbol_rate)
        self.pend = np.zeros(0, dtype=np.complex64)
        self.q = []
        self.ser = 0.5; self.evm_db = 0.0; self.locked = 0.0; self.frames = 0; self.cfo_hz = 0.0

    def forecast(self, noutput_items, ninputs):
        return [1] * ninputs

    def general_work(self, input_items, output_items):
        x = input_items[0]
        self.consume(0, len(x))
        d, info = self.core.push(x)
        c = self.core
        if len(d): self.pend = np.concatenate([self.pend, d.astype(np.complex64)])
        self.ser = (c.sym_err / c.sym_cnt) if c.sym_cnt else 0.5
        self.evm_db = c.evm_db if c.evm_db == c.evm_db else 0.0
        self.locked = 1.0 if c.locked else 0.0
        self.frames = c.frames
        self.cfo_hz = c.om / (2 * np.pi) * self.rs
        row = (self.ser, self.evm_db, self.locked, float(c.frames), self.cfo_hz)
        self.q.extend([row] * max(len(info), 1))
        n0 = min(len(self.pend), len(output_items[0]))
        if n0:
            output_items[0][:n0] = self.pend[:n0]; self.pend = self.pend[n0:]
        self.produce(0, n0)
        ns = min(len(self.q), len(output_items[1]))
        for k in range(5):
            if ns: output_items[k + 1][:ns] = [r[k] for r in self.q[:ns]]
            self.produce(k + 1, ns)
        self.q = self.q[ns:]
        return gr.WORK_CALLED_PRODUCE
'''


def build_tx():
    platform, fg, add, conn = G.new_graph("qam16_b210_frame_tx", "B210 transmitter: 16-QAM frames with a Zadoff-Chu word for the P501's FPGA receiver",
                                          "The B210 transmits the 16-QAM frames (CP | ZC word | 14 x (63 symbols + pilot), PRBS-15 payload) at 915 MHz, 3.84 MSPS; the P501 overlay p501_qam16_trx decodes them.")
    add("variable_qtgui_chooser", "tx_on", (240, 20), label="Transmit (B210 TX/RX port)", type="int", num_opts="2", option0="0", label0="OFF", option1="1", label1="ON",
        value="0", gui_hint="0,0,1,1", widget="radio_buttons", comment="OFF at start. Switch ON when the P501 is ready to receive.")
    add("variable_qtgui_range", "tx_gain", (240, 100), label="B210 TX gain (dB)", start="0", stop="86", step="1", value="80", gui_hint="0,1,1,3", widget="counter_slider",
        comment="very low power: antennas a few centimetres apart; at the digital level 0.35 the P501 decodes without an error from 80 to 86 dB (a strong link); lower it to see where the decoding stops")
    add("variable_qtgui_range", "tx_amp", (240, 180), label="TX digital amplitude (RMS)", start="0", stop="0.5", step="0.01", value="0.35", gui_hint="1,0,1,4", widget="counter_slider",
        comment="the peak is 1.8 x the RMS: 0.35 gives 0.64 of full scale; 0.18 is 6 dB weaker")
    add("import", "import_digital", (8, 330), imports="from gnuradio import digital", comment="only for the helper variable const_dqpsk of the common header")
    frames = add("epy_block", None, (240, 300), _source_code=TX_SOURCE)
    amp = add("blocks_multiply_const_vxx", None, (560, 300), type="complex", const="tx_amp*tx_on", vlen="1")
    sink = add("uhd_usrp_sink", None, (800, 280), type="fc32", num_mboards="1", nchan="1", samp_rate="samp_rate", center_freq0="freq", gain0="tx_gain", ant0="TX/RX", dev_addr="",
               dev_args=G.DEV, comment="the B210 transmitter (TX/RX port)")
    spec = add("qtgui_freq_sink_x", None, (800, 440), name='"spectrum of the transmitted signal"', type="complex", fftsize="2048", fc="0", bw="samp_rate", gui_hint="2,0,5,4", ymin="-100", ymax="20",
               update_time="0.1", average="0.2", grid="True", legend="False", label1="TX")
    env = add("blocks_complex_to_mag", None, (560, 440), vlen="1")
    tim = add("qtgui_time_sink_x", None, (800, 600), name='"envelope of the transmitted signal (one frame = 3868 samples)"', type="float", size="8192", srate="samp_rate", nconnections="1",
              gui_hint="7,0,3,4", ymin="0", ymax="0.8", update_time="0.1", label1="|x|", grid="True", legend="False", autoscale="False")
    conn(frames, amp); conn(amp, sink); conn(amp, spec); conn(amp, env); conn(env, tim)
    G.finish(platform, fg, "qam16_b210_frame_tx.grc")


def build_rx():
    platform, fg, add, conn = G.new_graph("qam16_b210_frame_rx", "B210 receiver: 16-QAM frames of the P501's FPGA transmitter, decoded with GNU Radio",
                                          "The B210 receives the 16-QAM frames of the P501's FPGA transmitter at 915 MHz and decodes them (Zadoff-Chu frame sync, PLL, PRBS-15 check): constellation, symbol error rate, EVM.")
    add("variable", "nfilts", (8, 330), value="32", comment="arms of the polyphase clock sync")
    add("variable", "rrc_taps", (8, 380), value="firdes.root_raised_cosine(nfilts, nfilts*sps, 1.0, excess_bw, 11*int(sps*nfilts))")
    add("import", "import_firdes", (8, 430), imports="from gnuradio.filter import firdes")
    add("variable_qtgui_range", "rx_gain", (240, 60), label="B210 RX gain (dB)", start="0", stop="76", step="1", value="45", gui_hint="0,0,1,4", widget="counter_slider",
        comment="raise it until the received spectrum is clearly above the noise; lower it if the constellation is squashed")
    add("variable_qtgui_range", "bw_div", (240, 140), label="Timing loop bandwidth: 2 pi / N", start="100", stop="1600", step="50", value="400", gui_hint="1,0,1,2", widget="counter_slider")
    add("variable_qtgui_range", "fll_div", (240, 200), label="FLL bandwidth: 2 pi / N", start="100", stop="6400", step="100", value="1600", gui_hint="1,2,1,2", widget="counter_slider",
        comment="the FLL's frequency noise decides how low the SNR can be: a narrower FLL (larger N) is quieter; it has to pull in the +9.6 kHz of the two radios")
    add("variable_qtgui_chooser", "fll_on", (240, 260), label="FLL band-edge", type="int", num_opts="2", option0="0", label0="OFF", option1="1", label1="ON", value="1", gui_hint="2,0,1,1",
        widget="radio_buttons", comment="OFF: zero loop gain, the FLL passes the signal through")
    src = add("uhd_usrp_source", None, (240, 340), type="fc32", num_mboards="1", nchan="1", samp_rate="samp_rate", center_freq0="freq", gain0="rx_gain", ant0="RX2", dev_addr="",
              dev_args=G.DEV, comment="the B210 receiver (RX2 port)")
    agc = add("analog_agc2_xx", None, (520, 240), type="complex", attack_rate="0.06", decay_rate="1e-3", reference="0.947", gain="1", max_gain="200",
              comment="reference 0.947 = the mean magnitude of 16-QAM at unit RMS")
    c2f = add("blocks_complex_to_float", None, (700, 240), vlen="1"); r_i = add("analog_rail_ff", None, (760, 200), lo="-3", hi="3"); r_q = add("analog_rail_ff", None, (760, 300), lo="-3", hi="3")
    f2c = add("blocks_float_to_complex", None, (880, 240), vlen="1")
    fll = add("digital_fll_band_edge_cc", None, (1040, 240), samps_per_sym="sps", rolloff="excess_bw", filter_size="55", w="2*3.14159265/fll_div*fll_on")
    clk = add("digital_pfb_clock_sync_xxx", None, (1260, 240), type="ccf", sps="sps", loop_bw="2*3.14159265/bw_div", taps="rrc_taps", filter_size="nfilts", init_phase="nfilts//2", max_dev="0.05")
    rxb = add("epy_block", None, (1480, 240), _source_code=CORE + RX_WRAPPER, loop_bw="0.02", thr_search="0.6", thr_lock="0.45", pilot_weight="3.0", aided="True", symbol_rate="samp_rate/sps")
    cons = add("qtgui_const_sink_x", None, (1700, 240), name='"data symbols after the PLL"', type="complex", nconnections="1", size="2048", gui_hint="4,0,4,2",
               xmin="-1.6", xmax="1.6", ymin="-1.6", ymax="1.6", update_time="0.1", label1="symbols", style1="0", width1="1", marker1="0", color1='"blue"', grid="True", legend="False")
    labels = [("symbol error rate", "SER", "0", "1", "3,0,1,2"), ("EVM of the last frame (dB)", "EVM", "-40", "0", "3,2,1,2"), ("lock (1 = locked on the frames)", "lock", "0", "1", "2,2,1,2"),
              ("frames decoded", "frames", "0", "100000000", "2,4,1,2"), ("carrier offset left for the PLL (Hz)", "offset", "-20000", "20000", "3,4,1,2")]
    sinks = []
    for k, (nm, lb, lo, hi, hint) in enumerate(labels):
        sinks.append(add("qtgui_number_sink", None, (1700, 400 + 90 * k), name='"%s"' % nm, type="float", nconnections="1", label1=lb, unit1="", graph_type="qtgui.NUM_GRAPH_NONE", gui_hint=hint,
                         avg="0.0", update_time="0.25", min=lo, max=hi, autoscale="True" if lb == "frames" else "False"))
    spec = add("qtgui_freq_sink_x", None, (240, 560), name='"received spectrum"', type="complex", fftsize="2048", fc="0", bw="samp_rate", gui_hint="8,0,4,6", ymin="-120", ymax="0",
               update_time="0.1", average="0.2", grid="True", legend="False", label1="B210 RX2")
    conn(src, agc); conn(agc, c2f); conn(c2f, r_i, "0", "0"); conn(c2f, r_q, "1", "0"); conn(r_i, f2c, "0", "0"); conn(r_q, f2c, "0", "1"); conn(f2c, fll); conn(fll, clk)
    conn(clk, rxb); conn(rxb, cons, "0", "0")
    for k, snk in enumerate(sinks): conn(rxb, snk, str(k + 1), "0")
    conn(src, spec)
    for blk_ in (fll, clk):
        for port in ("1", "2", "3"):
            nul = add("blocks_null_sink", None, (1700, 240), type="float", num_inputs="1", vlen="1")
            conn(blk_, nul, port, "0")
    G.finish(platform, fg, "qam16_b210_frame_rx.grc")


if __name__ == "__main__":
    build_tx(); build_rx()
