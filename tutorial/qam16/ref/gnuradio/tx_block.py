"""16-QAM + Zadoff-Chu framed symbol source, 1 sample per symbol, unit average power.

Frame (967 symbols) = [ CP 8 | ZC sync word 63 | 14 x ( 63 x 16-QAM data + 1 pilot ) ]
  CP    = last 8 symbols of the ZC word (cyclic prefix)
  ZC    = Zadoff-Chu, root 1, length 63, constant amplitude 1 (= average payload power)
  pilot = known +-1 symbol at the end of every 64-symbol block
fixed_payload = True repeats the same payload (from seed) in every frame, so the receiver can count symbol errors.
"""
import numpy as np
from gnuradio import gr

N_ZC, ROOT, N_CP, N_BLK, N_DATA = 63, 1, 8, 14, 63
N_PAY = N_BLK * N_DATA                       # 882 data symbols per frame
FRAME = N_CP + N_ZC + N_BLK * (N_DATA + 1)   # 967
GRAY = np.array([-3, -1, 3, 1]) / np.sqrt(10.0)     # 2-bit index -> level (00,01,10,11)
PILOTS = np.array([1, 1, -1, 1, -1, -1, 1, 1, 1, -1, -1, 1, -1, 1], dtype=float)


def zc_word():
    n = np.arange(N_ZC)
    return np.exp(-1j * np.pi * ROOT * n * (n + 1) / N_ZC)


def qam_from_index(k):
    k = np.asarray(k)
    return GRAY[k >> 2] + 1j * GRAY[k & 3]


class blk(gr.sync_block):
    def __init__(self, seed=1, fixed_payload=False):
        gr.sync_block.__init__(self, name='16-QAM + ZC frame source', in_sig=None, out_sig=[np.complex64])
        self.rng = np.random.RandomState(int(seed))
        self.fixed = bool(fixed_payload)
        self.zc = zc_word()
        self.fixed_idx = np.random.RandomState(int(seed)).randint(0, 16, N_PAY)
        self.pending = np.zeros(0, dtype=np.complex64)

    def make_frame(self):
        idx = self.fixed_idx if self.fixed else self.rng.randint(0, 16, N_PAY)
        data = qam_from_index(idx).reshape(N_BLK, N_DATA)
        blocks = np.concatenate([data, PILOTS[:, None].astype(complex)], axis=1).reshape(-1)
        return np.concatenate([self.zc[-N_CP:], self.zc, blocks]).astype(np.complex64)

    def work(self, input_items, output_items):
        out = output_items[0]
        n = len(out)
        while len(self.pending) < n:
            self.pending = np.concatenate([self.pending, self.make_frame()])
        out[:] = self.pending[:n]
        self.pending = self.pending[n:]
        return n
