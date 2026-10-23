"""Bit-exact integer model of the ZC frame synchroniser of the 16-QAM receiver (the specification of the future rtl/qam_zc_sync.v). PLAN_QAM16.md section 2 (2).

Input per symbol: (mi, mq), 16-bit signed, the symbols after the AGC, before the derotation (unit RMS = R = 4096 sqrt(10) = 12953 counts).

  q[k]   = round(conj(ZC[k]) x 2^14)  (k = 0..62, 63rd roots of unity, Q14)           the reference ROM
  window of the 63 symbols ending at n:   A = sum_{k=0..30} x[n-62+k] q[k],  B = x[n-31] q[31],  D = sum_{k=32..62} x[n-62+k] q[k]     (complex integers, one complex MAC, one tap per clock)
  C = A + B + D,   M = max(|Cr|,|Ci|) + min(|Cr|,|Ci|)/2   (units of 2^-14 counts),   E = sum of the same magnitude of the 63 symbols (counts, a running sum)
  candidate(THR):   E > 0 and 256 M >= THR 2^14 E          (THR in 1/256: 154 = 0.60, 115 = 0.45)
  peak at n:        candidate(n) and M(n) >= M(n-1) and M(n) > M(n+1)       (decided at n+1: one symbol of look-ahead)
  tracker:          SEARCH: a peak with THR_S, and a peak with THR_L within FL +- TOL later -> LOCKED, frame reference = the second peak (the last symbol of the word).
                    LOCKED: around the expected position ref + FL the best metric among the candidates (THR_L) within +-WINDOW; none: miss (dead reckoning, ref + FL), more than MISSMAX misses in a row -> SEARCH.
  carrier from the word at a lock (A and D of the peak):
      w   = signed(atan2(Im(D conj A), Re(D conj A)) turns x 2^20) << 12 >> 5            frequency in turns / symbol x 2^32 (the OMEGA unit); unambiguous to +-15 kHz
      th0 = atan2(A e^{+j16w} + D e^{-j16w}) << 12  +  32 w                               phase of the first payload symbol, turns x 2^32 (e^{+-j16w} from the engine's 1024-entry Q15 table)
  atan2: the 18-iteration CORDIC of rtl/qpsk_sync.v (inputs reduced to 24 bit, angle in turns x 2^20).
"""
import math
import numpy as np
import frame16 as F

N_ZC, FRAME = F.N_ZC, F.FRAME
_n = np.arange(N_ZC)
_q = np.round(np.exp(1j * np.pi * _n * (_n + 1) / N_ZC) * 2 ** 14)                 # conj(ZC) in Q14
QR, QI = _q.real.astype(np.int64), _q.imag.astype(np.int64)
ZCR, ZCI = QR, -QI                                                                  # ZC itself (the known word symbols for the PLL), Q14
ATAB = [131072, 77376, 40884, 20753, 10417, 5213, 2607, 1304, 652, 326, 163, 81, 41, 20, 10, 5, 3, 1]


def cos_sin_lut():
    k = np.arange(1024); a = 2 * np.pi * k / 1024
    return np.round(np.cos(a) * 32767).astype(np.int64), np.round(np.sin(a) * 32767).astype(np.int64)


COS_L, SIN_L = cos_sin_lut()


def amag(re, im):
    a, b = np.abs(re), np.abs(im)
    return np.maximum(a, b) + (np.minimum(a, b) >> 1)


def cordic_turns20(re, im):
    """atan2 of (re, im) in turns x 2^20 (mod 2^20), as the CORDIC of rtl/qpsk_sync.v: inputs reduced to 24 bit signed, 18 iterations"""
    re, im = int(re), int(im)
    sh = max(0, max(abs(re), abs(im)).bit_length() - 23)
    re >>= sh; im >>= sh
    if re < 0: x, y, ang = -re, -im, 0x80000
    else: x, y, ang = re, im, 0
    for i in range(18):
        if y >= 0: x, y, ang = x + (y >> i), y - (x >> i), ang + ATAB[i]
        else: x, y, ang = x - (y >> i), y + (x >> i), ang - ATAB[i]
    return ang & 0xFFFFF


def signed(v, bits):
    v &= (1 << bits) - 1
    return v - (1 << bits) if v >> (bits - 1) else v


def carrier_from_word(Ar, Ai, Dr, Di):
    """(w, th0): frequency (signed) and first-payload phase (unsigned 32 bit), turns x 2^32, from the half sums A = Ar + j Ai and D = Dr + j Di (Python ints)"""
    pr = Dr * Ar + Di * Ai                                                          # D conj(A)
    pi_ = Di * Ar - Dr * Ai
    w = signed(cordic_turns20(pr, pi_) << 12, 32) >> 5
    idx = ((16 * w) & 0xFFFFFFFF) >> 22
    c, s = int(COS_L[idx]), int(SIN_L[idx])
    rr = Ar * c - Ai * s + Dr * c + Di * s                                          # A e^{+j16w} + D e^{-j16w}
    ri = Ar * s + Ai * c + Di * c - Dr * s
    th0 = ((cordic_turns20(rr, ri) << 12) + 32 * w) & 0xFFFFFFFF
    return w, th0


class Sync:
    pass


def _sums(cx, L, lo, hi):
    """sum_{k=lo..hi-1} x[s + k] q[k] for every window start s (exact: integers below 2^53)"""
    c = np.correlate(cx, np.conj((QR + 1j * QI)[lo:hi]), "valid")
    c = c[lo:lo + L - N_ZC + 1]
    return np.rint(c.real).astype(np.int64), np.rint(c.imag).astype(np.int64)


def sync(mi, mq, thr_s=154, thr_l=115, tol=3, window=4, missmax=3):
    """The synchroniser over a record of symbols (the tracker is a loop over the peaks, the sums are exact integer arrays). Returns an object with
       frames: list of dicts {e: index of the last word symbol, known: the symbol index at which the decision is available, lock: first frame after a lock, w / th0 (lock only), miss: dead reckoning}
       lost: symbol indices where a lock was lost;  M, E, cand_s, cand_l, peaks_s: the metric arrays, indexed by the window END"""
    xr = np.asarray(mi, dtype=np.int64); xi = np.asarray(mq, dtype=np.int64); L = len(xr)
    cx = (xr + 1j * xi).astype(np.complex128)
    Ar, Ai = _sums(cx, L, 0, 31); Br, Bi = _sums(cx, L, 31, 32); Dr, Di = _sums(cx, L, 32, 63)
    Cr, Ci = Ar + Br + Dr, Ai + Bi + Di
    e = np.concatenate([[0], np.cumsum(amag(xr, xi))]); E = e[N_ZC:] - e[:-N_ZC]
    M = amag(Cr, Ci)
    pad = N_ZC - 1                                                                   # index by the window end n = s + 62
    z = np.zeros(pad, dtype=np.int64)
    Mn = np.concatenate([np.full(pad, -1, dtype=np.int64), M]); En = np.concatenate([z, E])
    Arn, Ain, Drn, Din = (np.concatenate([z, v]) for v in (Ar, Ai, Dr, Di))
    cand_s = (En > 0) & ((Mn << 8) >= thr_s * En * 2 ** 14)
    cand_l = (En > 0) & ((Mn << 8) >= thr_l * En * 2 ** 14)
    pk = np.zeros(L, dtype=bool)
    pk[1:-1] = (Mn[1:-1] >= Mn[:-2]) & (Mn[1:-1] > Mn[2:])
    peaks_s = np.nonzero(pk & cand_s)[0]; peaks_l = np.nonzero(pk & cand_l)[0]
    r = Sync(); r.M, r.E, r.cand_s, r.cand_l, r.peaks_s, r.frames, r.lost = Mn, En, cand_s, cand_l, peaks_s, [], []
    r.Ar, r.Ai, r.Dr, r.Di = Arn, Ain, Drn, Din                                        # the half sums, indexed by the window end
    pos = 0
    while True:
        lock_at = None                                                               # SEARCH: a peak, and a second one a frame later
        for p in peaks_s[peaks_s >= pos]:
            q = peaks_l[(peaks_l >= p + FRAME - tol) & (peaks_l <= p + FRAME + tol)]
            if len(q): lock_at = int(q[0]); break
        if lock_at is None: break
        w, th0 = carrier_from_word(int(Arn[lock_at]), int(Ain[lock_at]), int(Drn[lock_at]), int(Din[lock_at]))
        r.frames.append(dict(e=lock_at, known=lock_at + 1, lock=True, w=w, th0=th0, miss=False))
        ref, miss = lock_at, 0
        while True:                                                                  # LOCKED
            ee = ref + FRAME
            lo, hi = ee - window, ee + window
            if hi >= L - 1: pos = L; break
            win = np.nonzero(cand_l[lo:hi + 1])[0]
            if len(win):
                j = lo + int(win[np.argmax(Mn[lo + win])]); ref, miss = j, 0
                r.frames.append(dict(e=j, known=hi, lock=False, miss=False))
            else:
                ref, miss = ee, miss + 1
                if miss > missmax:
                    r.lost.append(hi); pos = hi + 1; break
                r.frames.append(dict(e=ee, known=hi, lock=False, miss=True))
        if pos >= L: break
    return r
