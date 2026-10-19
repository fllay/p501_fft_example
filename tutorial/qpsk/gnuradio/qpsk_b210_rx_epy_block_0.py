
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
