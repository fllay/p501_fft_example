"""Channel estimate. Input: the 47 symbols of a frame as vectors of 29 values (subcarriers k = -14 .. +14, the middle one is the unused DC). Symbol 0 is the S&C symbol (not used here), symbols 1 and 2 are the two training
symbols T1 and T2 (the same known QPSK value TRAIN[k] of unit power on all 28 used subcarriers): H[k] = (T1[k] + T2[k]) / 2 * conj(TRAIN[k]). Outputs: 0: the 44 data symbols (29 values each), 1: H (29 values, one per frame; 0 at DC)."""
import numpy as np
from gnuradio import gr

TRAIN_SIGNS = [(1, -1), (-1, -1), (1, -1), (1, -1), (-1, 1), (-1, -1), (1, -1), (1, 1), (1, -1), (-1, 1), (1, 1), (-1, -1), (1, -1), (1, 1), (1, -1), (-1, 1), (1, 1), (-1, -1), (1, -1), (1, -1), (1, 1), (1, 1), (1, 1), (1, -1), (-1, 1), (-1, -1), (-1, 1), (-1, -1)]
TRAIN = np.array([(a + 1j * b) / np.sqrt(2) for a, b in TRAIN_SIGNS])
USED_IDX = np.array([i for i in range(29) if i != 14])           # index = k + 14
NSYM, NDATA = 47, 44


class blk(gr.basic_block):
    def __init__(self):
        gr.basic_block.__init__(self, name="Channel estimator", in_sig=[(np.complex64, 29)], out_sig=[(np.complex64, 29), (np.complex64, 29)])
        self.set_output_multiple(NDATA)

    def forecast(self, noutput_items, ninputs):
        return [NSYM * max(1, noutput_items // NDATA)]

    def general_work(self, input_items, output_items):
        x, d, h = input_items[0], output_items[0], output_items[1]
        nf = min(len(x) // NSYM, len(d) // NDATA, len(h))
        for f in range(nf):
            fr = x[f * NSYM:(f + 1) * NSYM]
            H = np.zeros(29, np.complex64); H[USED_IDX] = 0.5 * (fr[1][USED_IDX] + fr[2][USED_IDX]) * np.conj(TRAIN)
            h[f] = H; d[f * NDATA:(f + 1) * NDATA] = fr[3:]
        self.consume_each(nf * NSYM)
        self.produce(0, nf * NDATA); self.produce(1, nf)
        return gr.WORK_CALLED_PRODUCE
