"""Coarse carrier correction and gain: every frame (3760 samples) is multiplied by gain * exp(-j cfo (i - back)), `cfo` and `gain` being the tags of the frame detector. The S&C estimate is unambiguous within +-60 kHz
(the phase over the 32-sample delay stays within +-pi); what is left (a few hundred Hz) is measured from the two training symbols in the next block."""
import numpy as np
import pmt
from gnuradio import gr

FRAME = 3760


class blk(gr.sync_block):
    def __init__(self, back=6):
        gr.sync_block.__init__(self, name="Coarse CFO correction", in_sig=[np.complex64], out_sig=[np.complex64])
        self.back = back
        self.i = (np.arange(FRAME) - back).astype(np.float32)
        self.set_output_multiple(FRAME)

    def work(self, input_items, output_items):
        x, y = input_items[0], output_items[0]
        nf = len(y) // FRAME
        i = self.i
        for f in range(nf):
            a = f * FRAME; cfo, gain = 0.0, 1.0
            for t in self.get_tags_in_window(0, a, a + 1):
                k = pmt.symbol_to_string(t.key)
                if k == "cfo": cfo = pmt.to_double(t.value)
                elif k == "gain": gain = pmt.to_double(t.value)
            ph = np.empty(FRAME, np.complex64); ang = np.float32(cfo) * i; ph.real = np.cos(ang); ph.imag = -np.sin(ang)
            y[a:a + FRAME] = x[a:a + FRAME] * ph * np.float32(gain)
        return nf * FRAME
