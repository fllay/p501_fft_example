
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
