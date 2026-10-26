"""Symbol error counter. The payload of every frame is the PRBS-15 (x^15 + x^14 + 1, seed 0x7FFF, 4 bits per 16-QAM symbol, the first bit pair = I) restarted in every frame: 44 symbols x 24 subcarriers = 1056 values.
Every frame of 1056 slicer bytes is compared with it (a rejected frame, bytes of 255, is skipped). Outputs (one value per input byte): 0: symbol error rate since the start, 1: symbol errors, 2: frames decoded."""
import numpy as np
from gnuradio import gr

NPAY = 1056


def prbs15_symbols(n):
    s, bits = 0x7FFF, []
    for _ in range(4 * n):
        bits.append((s >> 14) & 1); s = ((s << 1) & 0x7FFF) | (((s >> 14) ^ (s >> 13)) & 1)
    b = np.array(bits, int).reshape(n, 4)
    return (b[:, 0] * 8 + b[:, 1] * 4 + b[:, 2] * 2 + b[:, 3]).astype(np.uint8)


class blk(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(self, name="Symbol error counter", in_sig=[np.uint8], out_sig=[np.float32, np.float32, np.float32])
        self.ref = prbs15_symbols(NPAY)
        self.sym = 0; self.err = 0; self.frames = 0
        self.set_output_multiple(NPAY)

    def work(self, input_items, output_items):
        x = input_items[0]; nf = len(output_items[0]) // NPAY
        for f in range(nf):
            fr = x[f * NPAY:(f + 1) * NPAY]
            if not np.any(fr == 255):
                self.err += int(np.count_nonzero(fr != self.ref)); self.sym += NPAY; self.frames += 1
            sl = slice(f * NPAY, (f + 1) * NPAY)
            output_items[0][sl] = self.err / self.sym if self.sym else 0.0; output_items[1][sl] = self.err; output_items[2][sl] = self.frames
        return nf * NPAY
