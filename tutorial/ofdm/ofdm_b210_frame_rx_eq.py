"""One-tap equalizer per subcarrier and pilot tracking. Inputs: 0: the 44 data symbols of a frame (29 values each), 1: the channel estimate H of the frame. Per symbol l:
  1. zero forcing: Z[k] = Y[k] / H[k]  (the data subcarriers and the 4 pilots k = -11, -4, 4, 11)
  2. the pilots should be PIL_V * POL[l] (QPSK, the polarity follows the PRBS-7 of IEEE 802.11): the phase of Z[pilot] conj(reference) against k is a straight line: its slope is a timing drift, removed from all subcarriers;
     the mean of the pilots is the common complex gain g of the symbol (common phase error and a gain change)
  3. slope and g are averaged over `smooth` symbols (a moving average centred on the symbol, shorter at the ends of the frame), the data are divided by g.
Outputs: 0: the 24 corrected data values per symbol, 1: arg(g) of the symbol in rad (the common phase error), 2: |g|. A frame without a channel estimate (H = 0, a rejected frame) gives zeros."""
import numpy as np
from gnuradio import gr

NDATA_SYM = 44
KS = np.arange(-14, 15)
PIL = np.array([-11, -4, 4, 11]); DATA = np.array([k for k in range(-14, 15) if k != 0 and k not in (-11, -4, 4, 11)])
PIL_IDX, DATA_IDX = PIL + 14, DATA + 14
PIL_V = np.array([1 + 1j, 1 - 1j, -1 + 1j, -1 - 1j]) / np.sqrt(2)
POL = np.array([-1, -1, -1, -1, -1, -1, -1, 1, 1, 1, 1, 1, 1, -1, 1, 1, 1, 1, 1, -1, -1, 1, 1, 1, 1, -1, 1, -1, 1, 1, 1, -1, -1, -1, -1, 1, 1, -1, 1, 1, 1, -1, 1, -1], float)


REF = PIL_V[None, :] * POL[:, None]                  # the pilot values of every symbol (44 x 4)


def smoothing_matrix(n, L=NDATA_SYM):
    """centred moving average of n symbols, shorter at the ends of the frame, as a matrix (L x L)"""
    if n <= 1: return np.eye(L)
    w = np.ones(n); M = np.zeros((L, L))
    for j in range(L): M[:, j] = np.convolve(np.eye(L)[j], w, "same")
    return M / M.sum(axis=1, keepdims=True)


class blk(gr.basic_block):
    def __init__(self, smooth=5, slope=True):
        gr.basic_block.__init__(self, name="Equalizer and pilot tracking", in_sig=[(np.complex64, 29), (np.complex64, 29)], out_sig=[(np.complex64, 24), np.float32, np.float32])
        self.slope = slope
        self.smooth = smooth
        self.set_output_multiple(NDATA_SYM)

    @property
    def smooth(self):
        return self._smooth

    @smooth.setter
    def smooth(self, v):
        self._smooth = int(v); self.SM = smoothing_matrix(self._smooth)

    def forecast(self, noutput_items, ninputs):
        k = max(1, noutput_items // NDATA_SYM)
        return [NDATA_SYM * k, k]

    def general_work(self, input_items, output_items):
        y, h = input_items
        z, ph, mag = output_items
        nf = min(len(y) // NDATA_SYM, len(h), len(z) // NDATA_SYM, len(ph) // NDATA_SYM, len(mag) // NDATA_SYM)
        for f in range(nf):
            H = h[f].astype(complex); Y = y[f * NDATA_SYM:(f + 1) * NDATA_SYM].astype(complex)
            o = slice(f * NDATA_SYM, (f + 1) * NDATA_SYM)
            if np.all(np.abs(H) < 1e-12):
                z[o] = 0; ph[o] = 0; mag[o] = 0; continue
            zd = Y[:, DATA_IDX] / H[DATA_IDX]; zp = Y[:, PIL_IDX] / H[PIL_IDX]
            sl = np.zeros(NDATA_SYM)
            if self.slope:
                phs = np.unwrap(np.angle(zp * np.conj(REF)), axis=1); sl = (phs * PIL[None, :]).sum(axis=1) / np.sum(PIL ** 2)
                zp = zp * np.exp(-1j * sl[:, None] * PIL[None, :])
            g = (zp * np.conj(REF)).sum(axis=1) / len(PIL)
            g = self.SM @ g; sl = self.SM @ sl
            if self.slope: zd = zd * np.exp(-1j * sl[:, None] * DATA[None, :])
            z[o] = (zd / g[:, None]).astype(np.complex64); ph[o] = np.angle(g); mag[o] = np.abs(g)
        self.consume(0, nf * NDATA_SYM); self.consume(1, nf)
        for i in range(3): self.produce(i, nf * NDATA_SYM)
        return gr.WORK_CALLED_PRODUCE
