
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
