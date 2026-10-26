
import numpy as np
from gnuradio import gr


class blk(gr.sync_block):
    """Frame-sync assistance for the carrier loops (the software version of what the FPGA does). Sits between the polyphase clock sync (1 sample per symbol) and the Costas loop.
    d_n = m_n conj(m_(n-1)) is the phase step between symbols: 2 pi f T for the m-sequence preamble steps (0 or 180 degrees, the chips of x^6 + x + 1) plus the frequency offset. The 63 chips are
    correlated with the unit-length steps: at the end of the preamble |C|/63 is large and arg(C) = 2 pi f T, the carrier offset per symbol, without any loop and whatever the carrier phase
    (+- 480 kHz at 960 ksym/s). From the symbol after the peak on, the stream is rotated by exp(-j phase) with that frequency (an NCO), so the Costas loop behind starts on frequency.
    Parameters: thr = detection threshold on |C|/63 (noise alone: 0.13 rms, a clean preamble: 1), assist = 1 applies the rotation, 0 passes the stream through (the estimate is still made),
    smooth = weight of a new estimate (1 = take it as it is), sym_rate for the output in Hz. Outputs: 0 the symbols, 1 the frequency estimate in Hz, 2 the number of preambles found."""

    def __init__(self, thr=0.5, assist=1, smooth=0.5, sym_rate=960000.0):
        gr.sync_block.__init__(self, name="Preamble frequency assist", in_sig=[np.complex64], out_sig=[np.complex64, np.float32, np.float32])
        self.thr = float(thr); self.assist = int(assist); self.smooth = float(smooth); self.sym_rate = float(sym_rate)
        a = [1, 0, 0, 0, 0, 0]
        while len(a) < 63:
            n = len(a) - 6
            a.append(a[n + 1] ^ a[n])
        chips = 1.0 - 2.0 * np.array(a, dtype=np.float64)           # bit 0 = step 0 (chip +1), bit 1 = step 180 degrees (chip -1)
        self.h = chips[::-1].astype(np.complex128)
        self.last_m = 1.0 + 0j; self.dtail = np.zeros(62, dtype=np.complex128)
        self.mprev = 0.0; self.cprev = 0j; self.since = 10 ** 9
        self.w_est = 0.0; self.have = False; self.phase = 0.0; self.hits = 0

    def work(self, input_items, output_items):
        x = input_items[0].astype(np.complex128); n = len(x)
        prev = np.concatenate([[self.last_m], x[:-1]]); d = x * np.conj(prev)
        mag = np.abs(d); du = np.where(mag > 1e-9, d / np.maximum(mag, 1e-9), 1.0)
        self.last_m = x[-1]
        ext = np.concatenate([self.dtail, du]); self.dtail = ext[-62:]
        corr = np.convolve(ext, self.h, mode="valid") if len(ext) >= 63 else np.zeros(n, dtype=np.complex128)
        cm = np.abs(corr) / 63.0
        M = np.concatenate([[self.mprev], cm]); C = np.concatenate([[self.cprev], corr])
        self.mprev = cm[-1]; self.cprev = corr[-1]
        w_arr = None; w_cur = self.w_est if self.assist else 0.0
        trig = []
        if len(M) > 2:
            j = np.nonzero((M[1:-1] >= self.thr) & (M[1:-1] >= M[:-2]) & (M[1:-1] > M[2:]))[0] + 1   # local maxima (one-symbol look-ahead); M[j] is chunk index j - 1
            last = -(10 ** 9)
            for jj in j:
                if jj - last < 32 and last > -(10 ** 9): continue
                last = jj; trig.append(jj - 1)
                est = float(np.angle(C[jj]))
                self.w_est = est if not self.have else self.w_est + self.smooth * (est - self.w_est)
                self.have = True; self.hits += 1
        if self.assist:
            w_arr = np.full(n, w_cur)
            for t in trig:
                w_arr[min(max(t + 1, 0), n):] = self.w_est
            ph = self.phase + np.cumsum(w_arr)
            self.phase = float(np.mod(ph[-1], 2 * np.pi))
            out = x * np.exp(-1j * ph)
        else:
            self.phase = 0.0; out = x
        output_items[0][:] = out.astype(np.complex64)
        output_items[1][:] = np.float32(self.w_est / (2 * np.pi) * self.sym_rate)
        output_items[2][:] = np.float32(self.hits)
        return n
