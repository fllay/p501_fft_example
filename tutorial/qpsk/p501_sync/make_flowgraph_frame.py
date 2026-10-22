#!/usr/bin/env python3
"""Generates the GNU Radio flowgraph of the m-sequence synchronisation tests (the B210 side): qpsk_b210_frame_tx.grc, with Companion's own Python API (like ../gnuradio/make_flowgraph.py).

    source tools/gnuradio_env.sh
    python3 make_flowgraph_frame.py                 # writes qpsk_b210_frame_tx.grc next to this file
    grcc qpsk_b210_frame_tx.grc                     # or open it in gnuradio-companion

qpsk_b210_frame_tx.grc: FRAMES (64-symbol m-sequence preamble + payload_syms symbols of PRBS-15, repeated) -> differential QPSK (RRC 0.35, 4 samples/symbol) -> amplitude x Transmit -> TX/RX port.
The P501 overlay p501_qpsk_trx_sync receives it, finds the preamble in the FPGA and counts the payload bit errors only inside the frame.  Transmit is OFF when it starts."""
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


if __name__ == "__main__":
    build()
