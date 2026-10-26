"""Pilot equalizer: the equalizer of the P501 OFDM receivers (the same method as `ofdm_model.receive`) in place of the stock Frame Equalizer, which updates its channel taps from its own decisions: a wrong decision then corrupts
the tap of its subcarrier for the symbols that follow (on a recording of the B210 with the P501 transmitting 4.7e-4 symbol errors, against none with the method of this block).
Input: the FFT of the data symbols (64 values per symbol, DC in the middle) of the Header/Payload Demux, 44 symbols per frame; the first symbol of a frame carries the tag ofdm_sync_chan_taps (the channel estimate of the stock
channel estimator, from the first training symbol). The taps are NOT updated within the frame. For every symbol:
  1. Z[k] = Y[k] / H[k] on the 24 data subcarriers and the 4 pilots (k = -11, -4, 4, 11)
  2. the pilots must be PIL_V x polarity of the symbol (QPSK, PRBS-7 of IEEE 802.11): mean of Z[pilot] conj(reference) over the 4 pilots = the common complex gain g of the symbol (carrier residue and gain), and with `slope` 1 the straight
     line of its phase against k is a timing drift; g (and the slope) are averaged over `smooth` symbols (centred; 1 = none)
  3. the data are divided by g (and turned back by the slope).
Outputs: 0: the decided points (the nearest of the 16 points, 24 per symbol: the stock slicer after this block gives the index 0 .. 15); 1: the 24 soft values per symbol, for the plot; 2: the error vector magnitude in dB,
measured against the PRBS-15 payload that the transmitter sends, as a running average over about 30 frames (frames with an error above -6 dB, wrong cuts or the start-up, are not counted).
All the arithmetic of a frame is done in a few NumPy calls on all the symbols at once, because the Python interpreter is shared with the other Python blocks of the flowgraph and 1000 frames per second are to be done."""
import numpy as np
import pmt
from gnuradio import gr

L_SYM = 44
KP = np.array([-11, -4, 4, 11]); KD = np.array([k for k in range(-14, 15) if k != 0 and k not in (-11, -4, 4, 11)])
IP, ID = 32 + KP, 32 + KD
PIL_V = np.array([1 + 1j, 1 - 1j, -1 + 1j, -1 - 1j]) / np.sqrt(2)
POL = np.array([-1, -1, -1, -1, -1, -1, -1, 1, 1, 1, 1, 1, 1, -1, 1, 1, 1, 1, 1, -1, -1, 1, 1, 1, 1, -1, 1, -1, 1, 1, 1, -1, -1, -1, -1, 1, 1, -1, 1, 1, 1, -1, 1, -1, ], float)
REF_P = PIL_V[None, :] * POL[:, None]
LV = np.array([-3, -1, 1, 3]) / np.sqrt(10)
GRAY = np.array([-3, -1, 3, 1]) / np.sqrt(10)


def prbs15_symbols(n):
    s, bits = 0x7FFF, []
    for _ in range(4 * n):
        bits.append((s >> 14) & 1); s = ((s << 1) & 0x7FFF) | (((s >> 14) ^ (s >> 13)) & 1)
    b = np.array(bits, int).reshape(n, 4)
    return b[:, 0] * 8 + b[:, 1] * 4 + b[:, 2] * 2 + b[:, 3]


IDX = prbs15_symbols(L_SYM * 24)
REF_D = (GRAY[IDX >> 2] + 1j * GRAY[IDX & 3]).reshape(L_SYM, 24)
P_REF = np.mean(np.abs(REF_D) ** 2)


def smoothing_matrix(n, L=L_SYM):
    if n <= 1: return np.eye(L)
    w = np.ones(n); M = np.zeros((L, L))
    for j in range(L): M[:, j] = np.convolve(np.eye(L)[j], w, "same")
    return M / M.sum(axis=1, keepdims=True)


S10 = np.sqrt(10)
LV32 = LV.astype(np.float32)
REF_PC = np.conj(REF_P).astype(np.complex64)                  # [symbol, pilot]


def decide(z):
    """the nearest of the 16 points: the levels -3 -1 1 3 (over sqrt 10) on I and on Q"""
    i = np.clip(np.floor(z.real * (S10 / 2) + 2), 0, 3).astype(np.intp); q = np.clip(np.floor(z.imag * (S10 / 2) + 2), 0, 3).astype(np.intp)
    return LV32[i] + 1j * LV32[q]


class blk(gr.sync_block):
    def __init__(self, smooth=1, slope=0, frames=16, evm_every=8):
        gr.sync_block.__init__(self, name="Pilot equalizer (no decision feedback)", in_sig=[(np.complex64, 64)], out_sig=[(np.complex64, 24), (np.complex64, 24), np.float32])
        self.smooth = smooth; self.slope = slope; self.evm_every = max(int(evm_every), 1)
        self.set_output_multiple(L_SYM * max(int(frames), 1))                       # many frames per call: the NumPy calls cost the same for 1 frame as for 16
        self.pw = None; self.key = pmt.intern("ofdm_sync_chan_taps")

    @property
    def smooth(self):
        return self._smooth

    @smooth.setter
    def smooth(self, v):
        self._smooth = int(v); self.M = smoothing_matrix(self._smooth)

    def work(self, input_items, output_items):
        y = input_items[0]; dec, soft, ev = output_items
        n0 = self.nitems_read(0); nf = len(y) // L_SYM
        Hi = np.zeros((nf, 64), np.complex64); ok = np.zeros(nf, bool)
        for t in self.get_tags_in_window(0, 0, nf * L_SYM, self.key):
            f, r = divmod(t.offset - n0, L_SYM)
            if r == 0 and f < nf: Hi[f] = pmt.c32vector_elements(t.value); ok[f] = True
        with np.errstate(divide="ignore", invalid="ignore"):
            Hi = 1 / Hi                                                              # the taps are divided out: Y x (1 / H)
        ok &= np.isfinite(Hi[:, IP]).all(axis=1) & np.isfinite(Hi[:, ID]).all(axis=1)
        Hi[~ok] = 0
        Y = y[:nf * L_SYM].reshape(nf, L_SYM, 64)
        Zp = Y[:, :, IP] * Hi[:, None, IP]
        if self.slope:                                                               # the straight line of the pilot phases against k: a timing drift
            P = Zp * REF_PC[None]; ph = np.unwrap(np.angle(P), axis=2)
            sl = np.einsum("ij,fj->fi", self.M, (ph @ KP) / np.sum(KP ** 2)).astype(np.float32)
            Zp = Zp * np.exp(-1j * sl[:, :, None] * KP[None, None, :]).astype(np.complex64)
        g = np.einsum("fsp,sp->fs", Zp, REF_PC) / 4                                  # the common complex gain of the symbol: mean of Z[pilot] conj(reference)
        if self._smooth > 1: g = np.einsum("ij,fj->fi", self.M, g)
        gi = 1 / np.where(g == 0, 1, g)
        Zd = Y[:, :, ID] * Hi[:, None, ID]
        if self.slope: Zd = Zd * np.exp(-1j * sl[:, :, None] * KD[None, None, :]).astype(np.complex64)
        out = Zd * gi[:, :, None].astype(np.complex64)
        dec[:nf * L_SYM] = decide(out).reshape(-1, 24); soft[:nf * L_SYM] = out.reshape(-1, 24)
        for f in range(0, nf, self.evm_every):                                       # the EVM of 1 frame in evm_every
            if ok[f]:
                e = np.mean(np.abs(out[f] - REF_D) ** 2) / P_REF
                if e < 0.25: self.pw = e if self.pw is None else 0.9 * self.pw + 0.1 * e
        ev[:nf * L_SYM] = 10 * np.log10(max(self.pw, 1e-12)) if self.pw is not None else 0.0
        return nf * L_SYM
