#!/usr/bin/env python3
"""Generates the GNU Radio flowgraph of the m-sequence synchronisation tests (the B210 side): qpsk_b210_frame_tx.grc and qpsk_b210_frame_rx.grc, with Companion's own Python API (like ../gnuradio/make_flowgraph.py).

    source tools/gnuradio_env.sh
    python3 make_flowgraph_frame.py                 # writes both .grc files next to this file
    grcc qpsk_b210_frame_rx.grc                     # or open it in gnuradio-companion

qpsk_b210_frame_tx.grc: FRAMES (64-symbol m-sequence preamble + payload_syms symbols of PRBS-15, repeated) -> differential QPSK (RRC 0.35, 4 samples/symbol) -> amplitude x Transmit -> TX/RX port.
The P501 overlay p501_qpsk_trx_sync receives it, finds the preamble in the FPGA and counts the payload bit errors only inside the frame.  Transmit is OFF when it starts.
qpsk_b210_frame_rx.grc: the B210 RECEIVES the frames of the P501's FPGA transmitter (rtl/qpsk_tx_fr.v): AGC -> limiter -> FLL band-edge -> polyphase clock sync -> Costas loop -> decision -> differential decoder -> bits ->
a block that finds the m-sequence preamble in the bit stream (Hamming distance of the 128 preamble bits) and counts the payload errors against the PRBS-15 of the frame: BER, frames found, frame lock."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "gnuradio"))
import make_flowgraph as G
G.HERE = HERE                                                         # finish() writes next to this file

FRAME_SOURCE = '''
import numpy as np
from gnuradio import gr


class blk(gr.sync_block):
    """Frames as packed bytes, repeated: preamble (64 symbols: a reference symbol, then 63 phase STEPS = the chips of the m-sequence x^6 + x + 1: step 0 for chip +1, step 180 degrees for chip -1)
    followed by payload_syms symbols of PRBS-15 (x^15 + x^14 + 1, seed 0x7FFF, restarted in every frame). The bits are before the differential encoder: chip +1 = chunk 00, chip -1 = chunk 11."""

    def __init__(self, payload_syms=960):
        gr.sync_block.__init__(self, name="Frame bytes", in_sig=None, out_sig=[np.uint8])
        assert payload_syms % 4 == 0
        a = [1, 0, 0, 0, 0, 0]
        while len(a) < 63:
            n = len(a) - 6
            a.append(a[n + 1] ^ a[n])
        pre = [0, 0]
        for b in a:
            pre += [1, 1] if b else [0, 0]
        s, pay = 0x7FFF, []
        for i in range(2 * int(payload_syms)):
            pay.append((s >> 14) & 1)
            s = ((s << 1) & 0x7FFF) | (((s >> 14) ^ (s >> 13)) & 1)
        self.data = np.packbits(np.array(pre + pay, dtype=np.uint8))
        self.pos = 0

    def work(self, input_items, output_items):
        out = output_items[0]
        n = len(out)
        idx = (self.pos + np.arange(n)) % len(self.data)
        out[:] = self.data[idx]
        self.pos = (self.pos + n) % len(self.data)
        return n
'''

FRAME_RX_SOURCE = '''
import numpy as np
from gnuradio import gr


class blk(gr.sync_block):
    """Frame synchroniser and bit error counter of the frame receiver. Input: the decoded bits, one per byte, two per symbol (after the differential decoder and the symbol map: the bits that were sent).
    A frame is 64 preamble symbols (128 bits: symbol 0 = 00, then 00 for a chip +1 and 11 for a chip -1 of the m-sequence x^6 + x + 1) followed by payload_syms symbols of PRBS-15 restarted in every frame.
    The preamble is found by the Hamming distance of 128 bits to the known pattern (<= dmax; random data are at 64 +- 6, so a false match is practically impossible); then the 2 x payload_syms bits
    that follow are compared with the PRBS-15 (a known pattern: every error counts once).
    Output 0: the bit error rate over about the last window_frames frames (0.5 until a frame is found). Output 1: the frames found since the start.
    Output 2: 1 while the last frame was found one frame period after the one before (locked)."""

    def __init__(self, payload_syms=960, dmax=16, window_frames=2000):
        gr.sync_block.__init__(self, name="Frame sync + BER", in_sig=[np.uint8], out_sig=[np.float32, np.float32, np.float32])
        self.pl = int(payload_syms); self.dmax = int(dmax); self.win = float(window_frames)
        a = [1, 0, 0, 0, 0, 0]
        while len(a) < 63:
            n = len(a) - 6
            a.append(a[n + 1] ^ a[n])
        pre = [0, 0]
        for b in a:
            pre += [1, 1] if b else [0, 0]
        self.pre = np.array(pre, dtype=np.uint8)
        s, pay = 0x7FFF, []
        for i in range(2 * self.pl):
            pay.append((s >> 14) & 1)
            s = ((s << 1) & 0x7FFF) | (((s >> 14) ^ (s >> 13)) & 1)
        self.pay = np.array(pay, dtype=np.uint8)
        self.fb = 2 * (64 + self.pl)                       # frame length in bits
        self.need = 128 + 2 * self.pl                      # a whole frame (preamble + payload) must be in the buffer
        self.buf = np.zeros(0, dtype=np.uint8); self.base = 0       # absolute bit index of buf[0]
        self.next_scan = 0                                 # absolute index: nothing before it is searched
        self.frames = 0; self.m = 0.0; self.n = 0.0; self.ber = 0.5; self.locked_flag = 0.0; self.last_q = None

    def work(self, input_items, output_items):
        x = input_items[0]
        self.buf = np.concatenate([self.buf, x & 1])
        start = max(self.next_scan - self.base, 0)
        while len(self.buf) - start >= self.need:
            last = len(self.buf) - self.need               # last position whose whole frame is present
            win = np.lib.stride_tricks.sliding_window_view(self.buf[start:last + 128], 128)
            dist = np.count_nonzero(win != self.pre, axis=1)
            hit = np.nonzero(dist <= self.dmax)[0]
            if len(hit) == 0:
                start = last + 1                           # nothing in this stretch; the rest arrives with the next bits
                break
            k = int(hit[0]); k += int(np.argmin(dist[k:k + 4]))
            q = start + k
            err = float(np.count_nonzero(self.buf[q + 128:q + self.need] != self.pay))
            kk = np.exp(-1.0 / self.win)
            self.m = self.m * kk + err; self.n = self.n * kk + 2 * self.pl
            self.ber = self.m / self.n
            self.frames += 1
            absq = self.base + q
            self.locked_flag = 1.0 if (self.last_q is not None and abs(absq - self.last_q - self.fb) <= 4) else 0.0
            self.last_q = absq
            self.next_scan = absq + self.fb - 16           # the next preamble is one frame later (a margin for a lost or added bit)
            start = max(self.next_scan - self.base, 0)
        self.next_scan = self.base + start
        cut = min(start, len(self.buf))
        if cut > 0:
            self.buf = self.buf[cut:]; self.base += cut
        output_items[0][:] = self.ber; output_items[1][:] = self.frames; output_items[2][:] = self.locked_flag
        return len(x)
'''


def build():
    platform, fg, add, conn = G.new_graph("qpsk_b210_frame_tx", "B210 transmitter: m-sequence preamble + PRBS-15 payload frames (DQPSK) for the P501's FPGA synchroniser",
                                          "The B210 transmits frames (64-symbol m-sequence preamble + payload) as differential QPSK at 915 MHz, 3.84 MSPS; the P501 overlay with the frame synchroniser finds them.")
    add("variable", "payload_syms", (8, 330), value="960", comment="payload symbols per frame (a multiple of 4); the frame is 64 + payload_syms symbols = 1024 symbols = 1.067 ms for 960; set the same FL, PL in the P501 notebook/driver")
    add("variable_qtgui_chooser", "tx_on", (240, 20), label="Transmit (B210 TX/RX port)", type="int", num_opts="2", option0="0", label0="OFF", option1="1", label1="ON",
        value="0", gui_hint="0,0,1,1", widget="radio_buttons", comment="OFF at start. Switch ON when the P501 is ready to receive.")
    add("variable_qtgui_range", "tx_gain", (240, 100), label="B210 TX gain (dB)", start="0", stop="80", step="1", value="80", gui_hint="0,1,1,3", widget="counter_slider",
        comment="very low power: antennas a few centimetres apart; lower it to see where the synchroniser stops finding the preamble")
    add("variable_qtgui_range", "tx_amp", (240, 180), label="TX digital amplitude", start="0", stop="0.5", step="0.01", value="0.25", gui_hint="1,0,1,4", widget="counter_slider")
    frames = add("epy_block", None, (240, 300), _source_code=FRAME_SOURCE, payload_syms="payload_syms")
    mod = add("digital_constellation_modulator", None, (520, 290), constellation="const_dqpsk", differential="True", samples_per_symbol="sps", excess_bw="excess_bw",
              verbose="False", log="False", truncate="False")
    amp = add("blocks_multiply_const_vxx", None, (800, 300), type="complex", const="tx_amp*tx_on", vlen="1")
    sink = add("uhd_usrp_sink", None, (1040, 280), type="fc32", num_mboards="1", nchan="1", samp_rate="samp_rate", center_freq0="freq", gain0="tx_gain", ant0="TX/RX", dev_addr="",
               dev_args=G.DEV, comment="the B210 transmitter (TX/RX port)")
    spec = add("qtgui_freq_sink_x", None, (1040, 440), name='"spectrum of the transmitted signal"', type="complex", fftsize="2048", fc="0", bw="samp_rate", gui_hint="2,0,5,4", ymin="-100", ymax="20",
               update_time="0.1", average="0.2", grid="True", legend="False", label1="TX")
    env = add("blocks_complex_to_mag", None, (800, 440), vlen="1")
    tim = add("qtgui_time_sink_x", None, (1040, 600), name='"envelope of the transmitted signal (the preamble is the first 64 symbols of each frame)"', type="float", size="4096", srate="samp_rate", nconnections="1",
              gui_hint="7,0,3,4", ymin="0", ymax="0.5", update_time="0.1", label1="|x|", grid="True", legend="False", autoscale="False")
    conn(frames, mod); conn(mod, amp); conn(amp, sink); conn(amp, spec); conn(amp, env); conn(env, tim)
    G.finish(platform, fg, "qpsk_b210_frame_tx.grc")


def build_rx():
    platform, fg, add, conn = G.new_graph("qpsk_b210_frame_rx", "B210 receiver: the frames of the P501's FPGA transmitter, decoded with GNU Radio",
                                          "The B210 receives the frames (m-sequence preamble + PRBS-15 payload) of the P501's FPGA transmitter at 915 MHz and decodes them: constellation, spectrum, frames found and bit error rate of the payload.")
    add("variable", "payload_syms", (8, 330), value="960", comment="payload symbols per frame: the same as the P501's start_frames(payload=...)")
    add("variable", "nfilts", (8, 380), value="32", comment="arms of the polyphase clock sync")
    add("variable", "rrc_taps", (8, 430), value="firdes.root_raised_cosine(nfilts, nfilts*sps, 1.0, excess_bw, 11*int(sps*nfilts))")
    add("import", "import_firdes", (8, 480), imports="from gnuradio.filter import firdes")
    add("variable_qtgui_range", "rx_gain", (240, 60), label="B210 RX gain (dB)", start="0", stop="76", step="1", value="45", gui_hint="0,0,1,4", widget="counter_slider",
        comment="raise it until the received spectrum is clearly above the noise; lower it if the constellation is squashed")
    add("variable_qtgui_range", "bw_div", (240, 140), label="Loop bandwidth: 2 pi / N (FLL, timing, Costas)", start="50", stop="1600", step="10", value="400", gui_hint="1,0,1,4",
        widget="counter_slider", comment="wide (small N) pulls in fast and is noisy; narrow (large N) is quieter but may not pull in")
    src = add("uhd_usrp_source", None, (240, 240), type="fc32", num_mboards="1", nchan="1", samp_rate="samp_rate", center_freq0="freq", gain0="rx_gain", ant0="RX2", dev_addr="",
              dev_args=G.DEV, comment="the B210 receiver (RX2 port)")
    agc = add("analog_agc2_xx", None, (520, 240), type="complex", attack_rate="0.06", decay_rate="1e-3", reference="1", gain="1", max_gain="200")
    c2f = add("blocks_complex_to_float", None, (700, 240), vlen="1"); r_i = add("analog_rail_ff", None, (760, 200), lo="-1.5", hi="1.5"); r_q = add("analog_rail_ff", None, (760, 300), lo="-1.5", hi="1.5")
    f2c = add("blocks_float_to_complex", None, (880, 240), vlen="1")
    fll = add("digital_fll_band_edge_cc", None, (1040, 240), samps_per_sym="sps", rolloff="excess_bw", filter_size="55", w="2*3.14159265/bw_div")
    clk = add("digital_pfb_clock_sync_xxx", None, (1260, 240), type="ccf", sps="sps", loop_bw="2*3.14159265/bw_div", taps="rrc_taps", filter_size="nfilts", init_phase="nfilts//2", max_dev="0.05")
    cos = add("digital_costas_loop_cc", None, (1480, 240), w="2*3.14159265/bw_div", order="4", use_snr="False")
    dec = add("digital_constellation_decoder_cb", None, (240, 420), constellation="const_dqpsk")
    dif = add("digital_diff_decoder_bb", None, (460, 420), modulus="4")
    mp = add("digital_map_bb", None, (660, 420), map="[0, 1, 3, 2]", comment="inverse of the pre-differential code (it is its own inverse)")
    unp = add("blocks_unpack_k_bits_bb", None, (860, 420), k="2")
    fb = add("epy_block", None, (1060, 420), _source_code=FRAME_RX_SOURCE, payload_syms="payload_syms", dmax="16", window_frames="2000")
    k0 = add("blocks_keep_one_in_n", None, (1300, 400), type="float", n="19200", vlen="1")
    k1 = add("blocks_keep_one_in_n", None, (1300, 480), type="float", n="19200", vlen="1")
    k2 = add("blocks_keep_one_in_n", None, (1300, 560), type="float", n="19200", vlen="1")
    n0 = add("qtgui_number_sink", None, (1480, 400), name='"payload bit error rate"', type="float", nconnections="1", label1="BER", unit1="", graph_type="qtgui.NUM_GRAPH_NONE", gui_hint="2,0,1,2",
             avg="0.0", update_time="0.25", min="0", max="1", autoscale="False", comment="0.5 = no frames found; 0 = every payload bit right")
    n1 = add("qtgui_number_sink", None, (1480, 480), name='"frames found"', type="float", nconnections="1", label1="frames", unit1="", graph_type="qtgui.NUM_GRAPH_NONE", gui_hint="2,2,1,2",
             avg="0.0", update_time="0.25", min="0", max="100000000", autoscale="True", comment="937.5 frames per second for 960 payload symbols (3.84 MSPS / 4 / 1024)")
    n2 = add("qtgui_number_sink", None, (1480, 560), name='"frame lock (1 = frames arrive one frame period apart)"', type="float", nconnections="1", label1="lock", unit1="", graph_type="qtgui.NUM_GRAPH_NONE",
             gui_hint="3,0,1,4", avg="0.0", update_time="0.25", min="0", max="1", autoscale="False")
    cons = add("qtgui_const_sink_x", None, (1480, 680), name='"after the Costas loop"', type="complex", nconnections="1", size="1024", gui_hint="4,0,4,2",
               xmin="-2", xmax="2", ymin="-2", ymax="2", update_time="0.1", label1="symbols", style1="0", width1="1", marker1="0", color1='"blue"', grid="True", legend="False")
    spec = add("qtgui_freq_sink_x", None, (240, 560), name='"received spectrum"', type="complex", fftsize="2048", fc="0", bw="samp_rate", gui_hint="4,2,4,2", ymin="-120", ymax="0",
               update_time="0.1", average="0.2", grid="True", legend="False", label1="B210 RX2")
    conn(src, agc); conn(agc, c2f); conn(c2f, r_i, "0", "0"); conn(c2f, r_q, "1", "0"); conn(r_i, f2c, "0", "0"); conn(r_q, f2c, "0", "1"); conn(f2c, fll); conn(fll, clk)
    conn(clk, cos); conn(cos, dec); conn(cos, cons); conn(dec, dif); conn(dif, mp); conn(mp, unp); conn(unp, fb)
    conn(fb, k0, "0", "0"); conn(fb, k1, "1", "0"); conn(fb, k2, "2", "0"); conn(k0, n0); conn(k1, n1); conn(k2, n2); conn(src, spec)
    for blk_ in (fll, clk):
        for port in ("1", "2", "3"):
            nul = add("blocks_null_sink", None, (1700, 240), type="float", num_inputs="1", vlen="1")
            conn(blk_, nul, port, "0")
    G.finish(platform, fg, "qpsk_b210_frame_rx.grc")


if __name__ == "__main__":
    build(); build_rx()
