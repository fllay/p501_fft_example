"""Symbol error counter, one output value per frame. The payload of every frame is the PRBS-15 (x^15 + x^14 + 1, seed 0x7FFF, 4 bits per 16-QAM symbol, the first bit pair = I) restarted in every frame: 44 symbols x 24 subcarriers = 1056 values.
Every frame of 1056 slicer bytes (0 .. 15) is compared with it (a rejected frame, bytes of 255, is skipped). Outputs, one value per frame: 0: symbol error rate since the start, 1: symbol errors since the start, 2: frames decoded,
3: symbol error rate over the last 2000 frames (what the link does now). A decimating block with vectorised numpy: one value per frame instead of one per symbol keeps the Python interpreter, which the other Python blocks of the flowgraph share, free."""
import numpy as np
from gnuradio import gr

NPAY = 1056


def prbs15_symbols(n):
    s, bits = 0x7FFF, []
    for _ in range(4 * n):
        bits.append((s >> 14) & 1); s = ((s << 1) & 0x7FFF) | (((s >> 14) ^ (s >> 13)) & 1)
    b = np.array(bits, int).reshape(n, 4)
    return (b[:, 0] * 8 + b[:, 1] * 4 + b[:, 2] * 2 + b[:, 3]).astype(np.uint8)


class blk(gr.decim_block):
    def __init__(self):
        gr.decim_block.__init__(self, name="Symbol error counter (one value per frame)", in_sig=[np.uint8], out_sig=[np.float32, np.float32, np.float32, np.float32], decim=NPAY)
        self.ref = prbs15_symbols(NPAY)
        self.err = 0; self.frames = 0
        self.hist = np.zeros(0, np.int64)            # symbol errors of the last 2000 frames

    def work(self, input_items, output_items):
        nf = len(output_items[0])
        fr = input_items[0][:nf * NPAY].reshape(nf, NPAY)
        e = np.count_nonzero(fr != self.ref[None, :], axis=1).astype(np.int64)
        e[np.any(fr == 255, axis=1)] = -1                                           # rejected frames are not counted
        ok = e >= 0
        cum_e = self.err + np.cumsum(np.where(ok, e, 0)); cum_f = self.frames + np.cumsum(ok)
        allh = np.concatenate([self.hist, np.where(ok, e, 0)]); cs = np.concatenate([[0], np.cumsum(allh)]); k = len(self.hist) + np.arange(1, nf + 1); lo = np.maximum(k - 2000, 0)
        rec = (cs[k] - cs[lo]) / (NPAY * np.maximum(k - lo, 1))
        output_items[0][:] = np.where(cum_f > 0, cum_e / (NPAY * np.maximum(cum_f, 1)), 0.0); output_items[1][:] = cum_e; output_items[2][:] = cum_f; output_items[3][:] = rec
        self.err = int(cum_e[-1]); self.frames = int(cum_f[-1]); self.hist = allh[-2000:]
        return nf
