"""Streaming receiver of the 16-QAM / Zadoff-Chu frames for GNU Radio: the algorithm of framerx_hw.FrameRxHW (the float model of the FPGA receiver) as a class that takes the symbols (1 sample per symbol, after the matched filter
and the timing recovery) in chunks of any size and keeps its state: SEARCH -> VERIFY -> LOCKED (word correlation with |C| / sum|x|, thresholds 0.6 / 0.45, window +-4, 3 misses), carrier frequency and phase from the two half-word correlations,
the PLL (decision directed on the data, pilot weight 3, the known CP and word symbols in the loop, loop bandwidth 0.02), the payload checked against the PRBS-15 restarted in every frame.

    rx = StreamRx(); data, info = rx.push(x)         # data: the derotated, normalised data symbols of the frames completed by this chunk (882 per frame); info: one dict per frame
It is self-contained (numpy only): the GNU Radio block (make_flowgraph_qam16.py) embeds this file. Tested against FrameRxHW with random chunk sizes (test_stream_rx.py)."""
import math
import numpy as np

N_ZC, ROOT, N_CP, N_BLK, N_DATA = 63, 1, 8, 14, 63
N_PAY = N_BLK * N_DATA
BLK = N_DATA + 1
PAY_LEN = N_BLK * BLK
FRAME = N_CP + N_ZC + PAY_LEN
S10 = math.sqrt(10.0)
_n = np.arange(N_ZC)
ZC = np.exp(-1j * np.pi * ROOT * _n * (_n + 1) / N_ZC)
CP_REF = ZC[-N_CP:]
PILOTS = [1.0, 1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0, -1.0, -1.0, 1.0, -1.0, 1.0]
LEVEL_IDX = {-3: 0, -1: 1, 1: 3, 3: 2}


def _prbs15_indices():
    s, bits = 0x7FFF, []
    for i in range(4 * N_PAY):
        bits.append((s >> 14) & 1)
        s = ((s << 1) & 0x7FFF) | (((s >> 14) ^ (s >> 13)) & 1)
    b = np.array(bits, dtype=int).reshape(N_PAY, 4)
    return b[:, 0] * 8 + b[:, 1] * 4 + b[:, 2] * 2 + b[:, 3]


REF_IDX = _prbs15_indices()


def _level(a):
    return -3 if a < -2 else (-1 if a < 0 else (1 if a < 2 else 3))


def _amag(z):
    a, b = np.abs(z.real), np.abs(z.imag)
    return np.maximum(a, b) + 0.5 * np.minimum(a, b)


class StreamRx:
    def __init__(self, loop_bw=0.02, thr_search=0.6, thr_lock=0.45, window=4, max_miss=3, tol_verify=3, pilot_weight=3.0, aided=True, amp_mode="word"):
        zeta = 0.7071
        den = 1 + 2 * zeta * loop_bw + loop_bw ** 2
        self.alpha, self.beta = 4 * zeta * loop_bw / den, 4 * loop_bw ** 2 / den
        self.thr_s, self.thr_l, self.win, self.max_miss, self.tolv = thr_search, thr_lock, window, max_miss, tol_verify
        self.pw, self.aided, self.amp_mode = pilot_weight, aided, amp_mode
        self.buf = np.zeros(0, dtype=complex)
        self.locked = False
        self.first = True
        self.nxt = 0                      # expected word start of the next frame, index in buf
        self.miss = 0
        self.theta = self.om = 0.0
        self.amp = 1.0
        self.frames = self.locks = self.hits = self.misses = self.lost = 0
        self.sym_err = self.sym_cnt = self.bit_err = self.bad_frames = 0
        self.evm_db = float("nan"); self.cfo = 0.0; self.lock_cfo = 0.0

    # ---------------------------------------------------------------- metric
    @staticmethod
    def _rho(x, idx):
        """rho = |C| / sum|x| (max + min/2 magnitudes) of the 63-symbol windows starting at idx (array)"""
        idx = np.asarray(idx)
        out = np.zeros(len(idx))
        for k, i in enumerate(idx):
            w = x[i:i + N_ZC]
            c = np.dot(w, np.conj(ZC))
            e = _amag(w).sum()
            out[k] = _amag(np.array([c]))[0] / e if e > 0 else 0.0
        return out

    @staticmethod
    def _rho_all(x):
        c = np.correlate(x, ZC, "valid")
        e = np.concatenate([[0.0], np.cumsum(_amag(x))]); s1 = e[N_ZC:] - e[:-N_ZC]
        m = _amag(c)
        return m / (s1 + 1e-20), m

    # ---------------------------------------------------------------- carrier from the word
    @staticmethod
    def _word(w):
        z = w * np.conj(ZC)
        c1, c2 = z[:31].sum(), z[32:].sum()
        p = c2 * np.conj(c1)
        return math.atan2(p.imag, p.real) / 32.0, c1, c2

    @staticmethod
    def _phase(c1, c2, om):
        r = c1 * np.exp(1j * 16 * om) + c2 * np.exp(-1j * 16 * om)
        return math.atan2(r.imag, r.real) + 32 * om, abs(r) / 62.0

    def _known(self, theta, om, seg, ref):
        if not self.aided:
            return theta + om * len(seg), om
        al, be = self.alpha, self.beta
        for v, rf in zip(seg.tolist(), ref.tolist()):
            cs, sn = math.cos(theta), math.sin(theta)
            zr, zi = v.real * cs + v.imag * sn, v.imag * cs - v.real * sn
            e = zi * rf.real - zr * rf.imag
            om += be * e; theta += om + al * e
        return theta, om

    def _pll(self, pay, theta, om):
        al, be, pw = self.alpha, self.beta, self.pw
        data, idx = [], []
        err2 = ref2 = 0.0
        pr, pi_ = pay.real.tolist(), pay.imag.tolist()
        for i in range(PAY_LEN):
            cs, sn = math.cos(theta), math.sin(theta)
            yr, yi = pr[i], pi_[i]
            zr, zi = yr * cs + yi * sn, yi * cs - yr * sn
            if i % BLK == BLK - 1:
                rr, ri, w = PILOTS[i // BLK], 0.0, pw
            else:
                lr, lq = _level(zr * S10), _level(zi * S10)
                rr, ri, w = lr / S10, lq / S10, 1.0
                data.append(complex(zr, zi)); idx.append(4 * LEVEL_IDX[lr] + LEVEL_IDX[lq])
                err2 += (zr - rr) ** 2 + (zi - ri) ** 2; ref2 += rr * rr + ri * ri
            e = (zi * rr - zr * ri) * w
            om += be * e; theta += om + al * e
        return theta, om, np.array(data, dtype=complex), idx, 10 * math.log10(max(err2, 1e-12) / max(ref2, 1e-12))

    # ---------------------------------------------------------------- streaming
    def push(self, x):
        self.buf = np.concatenate([self.buf, np.asarray(x, dtype=complex)])
        data, info = [], []
        while True:
            if self.locked:
                if not self._locked_step(data, info): break
            elif not self._search(): break
        return (np.concatenate(data) if data else np.zeros(0, dtype=complex)), info

    def _search(self):
        L = len(self.buf)
        if L < N_ZC + 2:
            return False
        rho, m = self._rho_all(self.buf)
        ok = np.zeros(len(m), dtype=bool)
        ok[1:-1] = (rho[1:-1] >= self.thr_s) & (m[1:-1] >= m[:-2]) & (m[1:-1] > m[2:])
        for p in np.nonzero(ok)[0]:
            hi = p + FRAME + self.tolv
            if hi >= len(rho):                                  # cannot verify yet: wait, keeping the data from the candidate on
                self.buf = self.buf[p:]
                return False
            if rho[p + FRAME - self.tolv:hi + 1].max() >= self.thr_l:
                self.buf = self.buf[p:]
                self.locked, self.first, self.miss, self.nxt = True, True, 0, 0
                self.locks += 1
                return True
        self.buf = self.buf[max(len(self.buf) - (N_ZC + 1), 0):]       # nothing: keep the tail (a window and the neighbours of a peak)
        return False

    def _locked_step(self, data, info):
        L = len(self.buf)
        e, W = self.nxt, self.win
        if not self.first and L < e + W + N_ZC + PAY_LEN:
            return False
        if self.first and L < e + N_ZC + PAY_LEN:
            return False
        if self.first:
            s = e; hit = True
        else:
            lo, hi = e - W, e + W
            rho = self._rho(self.buf, np.arange(lo, hi + 1))
            j = int(np.argmax(rho))
            if rho[j] >= self.thr_l:
                s = lo + j; self.miss = 0; self.hits += 1; hit = True
            else:
                s = e; self.miss += 1; self.misses += 1; hit = False
                if self.miss > self.max_miss:
                    self.locked = False; self.lost += 1; self.theta = self.om = 0.0
                    self.buf = self.buf[e + 1:]
                    return True
        w = self.buf[s:s + N_ZC]
        om_w, c1, c2 = self._word(w)
        if self.first:
            self.om = om_w; self.lock_cfo = om_w
            th0, h = self._phase(c1, c2, self.om)
            self.amp = h if self.amp_mode == "word" else 1.0
            self.theta = th0
        else:
            a = max(self.amp, 1e-9)
            self.theta, self.om = self._known(self.theta, self.om, self.buf[s - N_CP:s] / a, CP_REF)
            self.theta, self.om = self._known(self.theta, self.om, w / a, ZC)
            if self.amp_mode == "word":
                _, h = self._phase(c1, c2, self.om); self.amp = 0.7 * self.amp + 0.3 * h
        pay = self.buf[s + N_ZC:s + N_ZC + PAY_LEN] / max(self.amp, 1e-9)
        self.theta, self.om, d, idx, self.evm_db = self._pll(pay, self.theta, self.om)
        ne = int(np.sum(np.asarray(idx) != REF_IDX)); xb = np.asarray(idx) ^ REF_IDX
        nb = int(sum(bin(int(v)).count("1") for v in xb[np.asarray(idx) != REF_IDX]))
        self.frames += 1; self.sym_err += ne; self.sym_cnt += N_PAY; self.bit_err += nb; self.bad_frames += int(ne > 0.2 * N_PAY)
        self.cfo = self.om
        data.append(d)
        info.append(dict(frame=self.frames, sym_err=ne, bit_err=nb, evm_db=self.evm_db, hit=hit, start=s))
        self.first = False
        cut = s + FRAME - W - N_CP - 2                          # keep the CP before the next word and the window
        self.buf = self.buf[cut:]
        self.nxt = s + FRAME - cut
        return True
