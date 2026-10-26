
import numpy as np
from gnuradio import gr


class blk(gr.sync_block):
    """The 16-QAM frames as a periodic complex stream at 4 samples per symbol and unit RMS: CP 8 | ZC word 63 (root 1) | 14 x (63 16-QAM symbols + 1 pilot), 967 symbols = 3868 samples per frame;
    Gray levels -3 -1 3 1 (00 01 10 11) / sqrt(10), pilots +-1 (1 1 -1 1 -1 -1 1 1 1 -1 -1 1 -1 1), the payload = PRBS-15 (x^15 + x^14 + 1, seed 0x7FFF, 4 bits per symbol, I = the first two bits)
    restarted in every frame; root-raised-cosine 0.35, 45 taps. The period is made from the middle frame of five, so that the repetition is seamless."""

    def __init__(self):
        gr.sync_block.__init__(self, name="16-QAM frames", in_sig=None, out_sig=[np.complex64])
        N, NCP, NB, ND, SPS, BETA = 63, 8, 14, 63, 4, 0.35
        n = np.arange(N)
        zc = np.exp(-1j * np.pi * n * (n + 1) / N)
        s, bits = 0x7FFF, []
        for i in range(4 * NB * ND):
            bits.append((s >> 14) & 1)
            s = ((s << 1) & 0x7FFF) | (((s >> 14) ^ (s >> 13)) & 1)
        b = np.array(bits, dtype=int).reshape(NB * ND, 4)
        idx = b[:, 0] * 8 + b[:, 1] * 4 + b[:, 2] * 2 + b[:, 3]
        gray = np.array([-3, -1, 3, 1]) / np.sqrt(10.0)
        data = (gray[idx >> 2] + 1j * gray[idx & 3]).reshape(NB, ND)
        pil = np.array([1, 1, -1, 1, -1, -1, 1, 1, 1, -1, -1, 1, -1, 1], dtype=float)
        frame = np.concatenate([zc[-NCP:], zc, np.concatenate([data, pil[:, None].astype(complex)], axis=1).reshape(-1)])
        sym = np.tile(frame, 5)
        k = (np.arange(11 * SPS + 1) - 5 * SPS) / SPS
        h = np.zeros(len(k))
        for i, t in enumerate(k):
            if abs(t) < 1e-12: h[i] = 1 + BETA * (4 / np.pi - 1)
            elif abs(abs(t) - 1 / (4 * BETA)) < 1e-9: h[i] = BETA / np.sqrt(2) * ((1 + 2 / np.pi) * np.sin(np.pi / (4 * BETA)) + (1 - 2 / np.pi) * np.cos(np.pi / (4 * BETA)))
            else: h[i] = (np.sin(np.pi * t * (1 - BETA)) + 4 * BETA * t * np.cos(np.pi * t * (1 + BETA))) / (np.pi * t * (1 - (4 * BETA * t) ** 2))
        up = np.zeros(len(sym) * SPS, dtype=complex); up[::SPS] = sym
        x = np.convolve(up, h)[len(h) // 2:len(h) // 2 + len(up)]
        L = len(frame) * SPS
        seg = x[2 * L:3 * L] / np.sqrt(np.mean(np.abs(x[L:4 * L]) ** 2))
        self.data = seg.astype(np.complex64)
        self.pos = 0

    def work(self, input_items, output_items):
        out = output_items[0]
        n = len(out)
        idx = (self.pos + np.arange(n)) % len(self.data)
        out[:] = self.data[idx]
        self.pos = (self.pos + n) % len(self.data)
        return n
