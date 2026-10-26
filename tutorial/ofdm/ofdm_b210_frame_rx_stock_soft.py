"""Soft equalizer for the plots (the stock equalizer outputs only its decisions, so its constellation is always perfect). Input: the FFT of the data symbols (64 values per symbol, DC in the middle) of the Header/Payload Demux, 44 symbols
per frame; the first symbol of a frame carries the tag ofdm_sync_chan_taps (the channel estimate of the stock channel estimator). For every symbol:
  1. Z[k] = Y[k] / H[k] on the 24 data subcarriers and the 4 pilots (k = -11, -4, 4, 11)
  2. the pilots must be PIL_V x polarity of the symbol (QPSK, PRBS-7 of IEEE 802.11): the phase of Z[pilot] conj(reference) against k is a straight line, its slope is a timing drift; the mean of the 4 pilots is the common complex gain g
  3. slope and g are averaged over `smooth` symbols (centred), the data are divided by g and turned back by the slope.
Outputs: 0: the 24 soft data values per symbol (no decisions); 1: the error vector magnitude in dB, measured against the PRBS-15 payload that the transmitter sends, as a running average over about 30 frames (frames with an error above -6 dB, wrong cuts or the start-up, are not counted)."""
import numpy as np
from gnuradio import gr

L_SYM = 44
KP = np.array([-11, -4, 4, 11]); KD = np.array([k for k in range(-14, 15) if k != 0 and k not in (-11, -4, 4, 11)])
IP, ID = 32 + KP, 32 + KD
PIL_V = np.array([1 + 1j, 1 - 1j, -1 + 1j, -1 - 1j]) / np.sqrt(2)
POL = np.array([-1, -1, -1, -1, -1, -1, -1, 1, 1, 1, 1, 1, 1, -1, 1, 1, 1, 1, 1, -1, -1, 1, 1, 1, 1, -1, 1, -1, 1, 1, 1, -1, -1, -1, -1, 1, 1, -1, 1, 1, 1, -1, 1, -1], float)
REF_P = PIL_V[None, :] * POL[:, None]
GRAY = np.array([-3, -1, 3, 1]) / np.sqrt(10)


def prbs15_symbols(n):
    s, bits = 0x7FFF, []
    for _ in range(4 * n):
        bits.append((s >> 14) & 1); s = ((s << 1) & 0x7FFF) | (((s >> 14) ^ (s >> 13)) & 1)
    b = np.array(bits, int).reshape(n, 4)
    return b[:, 0] * 8 + b[:, 1] * 4 + b[:, 2] * 2 + b[:, 3]


IDX = prbs15_symbols(L_SYM * 24)
REF_D = (GRAY[IDX >> 2] + 1j * GRAY[IDX & 3]).reshape(L_SYM, 24)


def smoothing_matrix(n, L=L_SYM):
    if n <= 1: return np.eye(L)
    w = np.ones(n); M = np.zeros((L, L))
    for j in range(L): M[:, j] = np.convolve(np.eye(L)[j], w, "same")
    return M / M.sum(axis=1, keepdims=True)


class blk(gr.sync_block):
    def __init__(self, smooth=5):
        gr.sync_block.__init__(self, name="Soft equalizer (for the plots)", in_sig=[(np.complex64, 64)], out_sig=[(np.complex64, 24), np.float32])
        self.smooth = smooth
        self.set_output_multiple(L_SYM)
        self.pw = None

    @property
    def smooth(self):
        return self._smooth

    @smooth.setter
    def smooth(self, v):
        self._smooth = int(v); self.M = smoothing_matrix(self._smooth)

    def work(self, input_items, output_items):
        y = input_items[0]; z = output_items[0]; ev = output_items[1]
        n0 = self.nitems_read(0); nf = len(y) // L_SYM
        tags = {t.offset: t for t in self.get_tags_in_window(0, 0, nf * L_SYM) if t.key.__str__() == "ofdm_sync_chan_taps"}
        import pmt
        for f in range(nf):
            sl = slice(f * L_SYM, (f + 1) * L_SYM); t = tags.get(n0 + f * L_SYM)
            if t is None:
                z[sl] = 0; ev[sl] = ev[f * L_SYM - 1] if f else 0.0; continue
            H = np.array(pmt.c32vector_elements(t.value), dtype=complex)
            Y = y[sl].astype(complex)
            with np.errstate(divide="ignore", invalid="ignore"):
                Zp = Y[:, IP] / H[IP]; Zd = Y[:, ID] / H[ID]
            if not (np.all(np.isfinite(Zp)) and np.all(np.isfinite(Zd))): z[sl] = 0; continue
            ph = np.unwrap(np.angle(Zp * np.conj(REF_P)), axis=1)
            sl_k = (ph @ KP) / np.sum(KP ** 2)                                    # least squares slope (the 4 pilots are symmetric around k = 0)
            sl_k = self.M @ sl_k
            g = np.mean(Zp * np.conj(REF_P) * np.exp(-1j * sl_k[:, None] * KP[None, :]), axis=1); g = self.M @ g
            out = Zd * np.exp(-1j * sl_k[:, None] * KD[None, :]) / g[:, None]
            z[sl] = out
            e = np.mean(np.abs(out - REF_D) ** 2) / np.mean(np.abs(REF_D) ** 2)
            if e < 0.25: self.pw = e if self.pw is None else 0.97 * self.pw + 0.03 * e
            ev[sl] = 10 * np.log10(max(self.pw, 1e-12)) if self.pw is not None else 0.0
        return nf * L_SYM
