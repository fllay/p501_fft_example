
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
