"""FrameRxHW: the floating-point model of the receiver the FPGA will implement (PLAN_QAM16.md section 2), at 1 sample per symbol, with the same job as the handoff's FrameRx.

The metric arrays are computed for the whole record at once (numpy), but only quantities a streaming implementation has at that moment are used: the peak decision at window n needs
the metric of n-1, n, n+1 (one-symbol look-ahead), the tracker looks at +-WINDOW symbols around the expected position, the carrier acquisition at the word needs nothing after it.
What differs from FrameRx (ref/gnuradio/rx_block.py), each switchable:
  norm='mag'      rho = |C| / sum|x| (no square root; |.| = max + min/2 when approx=True)      FrameRx: |C| / sqrt(63 sum|x|^2)
  frequency       arg(C2 conj C1) / 32 with C1 = taps 0..30, C2 = taps 32..62                    FrameRx: FFT of the despread word, zero-padded, parabolic interpolation
  phase           arg(C1 e^{+j16w} + C2 e^{-j16w}) + 32 w   (centre of the word, then to the first payload symbol)   FrameRx: sum of z e^{-jw(n-c)}
  word_mode       'freeze': the PLL does not run over CP + word (FrameRx), 'aided': it keeps tracking with the KNOWN symbols (CP = ZC tail, word = ZC) as references
  anchor          'every': the phase is re-anchored by the word in every frame (FrameRx), 'first': only at the lock, the PLL phase is continuous afterwards
  pd              'plain' e = Im(z conj(s)) (what the FPGA does with shift-adds), 'ring' = divided by the ring radius with shift-add weights {4, 1, 1/2}, 'corner' = only the 4 outer corners
  amp_mode        'agc': the input is already unit power (the FPGA's AGC); 'word': divided by the amplitude measured on the word, low-passed 0.7 / 0.3 (FrameRx)
"""
import math
import numpy as np
import frame16 as F

N_ZC, FRAME, PAY_LEN, BLK, N_CP, N_PAY, S10 = F.N_ZC, F.FRAME, F.PAY_LEN, F.BLK, F.N_CP, F.N_PAY, F.S10
ZC = F.ZC
CP_REF = ZC[-N_CP:]


def amag(z):
    a, b = np.abs(z.real), np.abs(z.imag)
    return np.maximum(a, b) + 0.5 * np.minimum(a, b)


class Result:
    pass


class FrameRxHW:
    def __init__(self, loop_bw=0.02, thr_search=0.6, thr_lock=0.45, window=4, max_miss=3, tol_verify=3, pilot_weight=3.0,
                 word_mode="freeze", word_weight=1.0, anchor="every", pd="plain", norm="mag", approx=True, amp_mode="agc", data_weight=1.0, dd_gate=None):
        zeta = 0.7071
        den = 1 + 2 * zeta * loop_bw + loop_bw ** 2
        self.alpha, self.beta = 4 * zeta * loop_bw / den, 4 * loop_bw ** 2 / den
        self.thr_s, self.thr_l, self.win, self.max_miss, self.tolv = thr_search, thr_lock, window, max_miss, tol_verify
        self.pw, self.ww = pilot_weight, word_weight
        self.dw, self.gate = data_weight, dd_gate           # data_weight 0: the loop is data-aided only (pilots, CP and word); dd_gate g: a data symbol drives the loop only if both components are within g x (level spacing / 2) of the decision
        self.word_mode, self.anchor, self.pd, self.norm, self.approx, self.amp_mode = word_mode, anchor, pd, norm, approx, amp_mode

    # ---------------------------------------------------------------- the metric (index i = start of the 63-symbol window)
    def metric(self, x):
        c = np.correlate(x, ZC, "valid")
        ax = amag(x) if self.approx else np.abs(x)
        e = np.concatenate([[0.0], np.cumsum(ax)]); s1 = e[N_ZC:] - e[:-N_ZC]
        m = amag(c) if self.approx else np.abs(c)
        if self.norm == "mag":
            rho = m / (s1 + 1e-20)
        else:
            e2 = np.concatenate([[0.0], np.cumsum(np.abs(x) ** 2)]); s2 = e2[N_ZC:] - e2[:-N_ZC]
            rho = np.abs(c) / np.sqrt(N_ZC * s2 + 1e-20); m = np.abs(c)
        return rho, m

    def peaks(self, rho, m, thr):
        """local maxima of the metric (look-ahead of one symbol) whose rho >= thr: window start indices"""
        ok = np.zeros(len(m), dtype=bool)
        ok[1:-1] = (rho[1:-1] >= thr) & (m[1:-1] >= m[:-2]) & (m[1:-1] > m[2:])
        return np.nonzero(ok)[0]

    # ---------------------------------------------------------------- carrier from the word
    @staticmethod
    def word_estimate(w):
        """frequency (rad / symbol) and the phase at the first payload symbol, from a despread word z = w conj(ZC) (63 values)"""
        z = w * np.conj(ZC)
        c1, c2 = z[:31].sum(), z[32:].sum()
        om = math.atan2((c2 * np.conj(c1)).imag, (c2 * np.conj(c1)).real) / 32.0
        return om, c1, c2

    @staticmethod
    def phase_first_payload(c1, c2, om):
        r = c1 * np.exp(1j * 16 * om) + c2 * np.exp(-1j * 16 * om)
        return math.atan2(r.imag, r.real) + 32 * om, abs(r) / 62.0

    # ---------------------------------------------------------------- run over a record
    def run(self, x, ref_idx=None):
        x = np.asarray(x, dtype=complex); L = len(x)
        rho, m = self.metric(x)
        pk = self.peaks(rho, m, self.thr_s)
        r = Result(); r.frames = r.locks = r.hits = r.misses = r.lost = 0
        r.sym_err = r.sym_cnt = r.bit_err = r.bad_frames = 0
        r.lock_starts = []; r.lock_om = []; r.frame_starts = []; r.evm = []; r.om_end = []; r.frame_errs = []
        r.n_peaks = len(pk); r.out = []
        self.rho_all, self.m_all = rho, m
        pos0 = 0
        while True:
            # ---- SEARCH + VERIFY
            cand = pk[pk >= pos0]
            start = None
            for p in cand:
                lo, hi = p + FRAME - self.tolv, p + FRAME + self.tolv
                if hi + 1 + 0 > len(rho): break
                if rho[lo:hi + 1].max() >= self.thr_l:
                    start = int(p); break
            if start is None: break
            r.locks += 1; r.lock_starts.append(start)
            self.acq = True; self.miss = 0; amp = 1.0
            theta = om = 0.0
            first = True
            s = start
            while True:
                if s + N_ZC + PAY_LEN > L: break
                if not first:
                    e = s_prev + FRAME
                    lo, hi = max(e - self.win, 0), min(e + self.win, len(rho) - 1)
                    if hi < lo: break
                    j = lo + int(np.argmax(rho[lo:hi + 1]))
                    if rho[j] >= self.thr_l: s = j; self.miss = 0; r.hits += 1
                    else:
                        s = e; self.miss += 1; r.misses += 1
                        if self.miss > self.max_miss:
                            r.lost += 1; pos0 = e + 1; s = None; break
                    if s + N_ZC + PAY_LEN > L: break
                w = x[s:s + N_ZC]
                om_w, c1, c2 = self.word_estimate(w)
                if first:
                    om = om_w; r.lock_om.append(om_w)
                    th0, h = self.phase_first_payload(c1, c2, om)
                    amp = h if self.amp_mode == "word" else 1.0
                    theta = th0
                else:
                    # CP + word: freeze or aided (theta, om are the PLL state at the first CP symbol)
                    cp = x[s - N_CP:s] / max(amp, 1e-9); wd = w / max(amp, 1e-9)
                    theta, om = self._known(theta, om, cp, CP_REF)
                    theta, om = self._known(theta, om, wd, ZC)
                    if self.anchor == "every":
                        th0, h = self.phase_first_payload(c1, c2, om)       # frequency: the PLL's own (as FrameRx)
                        theta = th0
                        if self.amp_mode == "word": amp = 0.7 * amp + 0.3 * h
                    elif self.amp_mode == "word":
                        _, h = self.phase_first_payload(c1, c2, om); amp = 0.7 * amp + 0.3 * h
                pay = x[s + N_ZC:s + N_ZC + PAY_LEN] / max(amp, 1e-9)
                theta, om, data, idx, evm = self._pll(pay, theta, om)
                r.frames += 1; r.frame_starts.append(s); r.evm.append(evm); r.om_end.append(om)
                r.out.append(data)
                if ref_idx is not None:
                    ri = ref_idx if ref_idx.ndim == 1 else ref_idx[min(len(r.out) - 1 + 0, len(ref_idx) - 1)]
                    d = np.asarray(idx) != ri; ne = int(d.sum()); r.sym_err += ne; r.sym_cnt += N_PAY; r.frame_errs.append(ne)
                    xb = np.asarray(idx) ^ ri; r.bit_err += int(sum(bin(v).count("1") for v in xb[d]))
                    if ne > 0.2 * N_PAY: r.bad_frames += 1
                s_prev = s; first = False
            if s is not None:                         # ran out of record
                break
        return r

    # ---------------------------------------------------------------- PLL over known symbols (CP, word)
    def _known(self, theta, om, seg, ref):
        if self.word_mode == "freeze":
            return theta + om * len(seg), om
        al, be, ww = self.alpha, self.beta, self.ww
        for v, rf in zip(seg.tolist(), ref.tolist()):
            cs, sn = math.cos(theta), math.sin(theta)
            zr, zi = v.real * cs + v.imag * sn, v.imag * cs - v.real * sn
            e = (zi * rf.real - zr * rf.imag) * ww
            om += be * e; theta += om + al * e
        return theta, om

    # ---------------------------------------------------------------- PLL over the 896 payload symbols
    def _pll(self, pay, theta, om):
        al, be, pw, pd = self.alpha, self.beta, self.pw, self.pd
        data, idx = [], []
        err2 = ref2 = 0.0
        pr, pi_ = pay.real.tolist(), pay.imag.tolist()
        for i in range(PAY_LEN):
            cs, sn = math.cos(theta), math.sin(theta)
            yr, yi = pr[i], pi_[i]
            zr, zi = yr * cs + yi * sn, yi * cs - yr * sn
            if i % BLK == BLK - 1:
                rr, ri, w = F.PILOTS[i // BLK], 0.0, pw
            else:
                lr, lq = F.level(zr * S10), F.level(zi * S10)
                rr, ri, w = lr / S10, lq / S10, 1.0
                data.append(complex(zr, zi)); idx.append(4 * F.LEVEL_IDX[lr] + F.LEVEL_IDX[lq])
                err2 += (zr - rr) ** 2 + (zi - ri) ** 2; ref2 += rr * rr + ri * ri
                if pd == "ring":
                    p2 = rr * rr + ri * ri; w = 4.0 if p2 < 0.5 else (1.0 if p2 < 1.4 else 0.5)
                elif pd == "corner":
                    w = 1.0 if (rr * rr + ri * ri) > 1.4 else 0.0
                w *= self.dw
                if self.gate is not None and (abs(zr - rr) > self.gate / S10 or abs(zi - ri) > self.gate / S10): w = 0.0
            e = (zi * rr - zr * ri) * w
            om += be * e; theta += om + al * e
        return theta, om, np.array(data, dtype=complex), idx, 10 * math.log10(max(err2, 1e-12) / max(ref2, 1e-12))
