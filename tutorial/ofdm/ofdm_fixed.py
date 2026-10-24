"""Bit-exact integer model of the Schmidl-and-Cox OFDM receiver (the specification of the future rtl/ofdm_rx.v). Frame: PLAN_OFDM.md (uniform variant: S&C symbol, T1, T2 and 44 data symbols, each with a 16-sample prefix).

Input: ADC counts xi, xq (12 bit signed), a recorded frame with noise in front. Every number is an integer; right shifts are arithmetic.
  1 detector     c[n] = x[n+32] conj(x[n]);  S[n] = sum of 32 c;  E[n] = sum of 32 |x[n+32]|^2;  S' = S >> 8, E' = E >> 8;  M = S'^2 / E'^2  (10-bit fraction: both squares shifted right by max(0, bitlen(E'^2) - 20), mq = min((S2s << 10) // E2s, 2047))
                 first n0 with E' >= 4 and 256 S'^2 >= THR E'^2 (THR in 1/256: 166 = 0.65); plateau = the positions in n0 .. n0+71 with mq >= 29/32 of the maximum; start of the S&C symbol s0 = n0 + ((first + last + 1) >> 1) - 8
                 coarse carrier: angle of the sum of S over the plateau (CORDIC, turns x 2^20) x 2^12 / 32 = w_c in turns x 2^32 per sample
  2 gain         G (Q8) = 256 TARGET / isqrt(E_peak >> 5):  the rms of the samples after the gain is TARGET (400) counts;   y = (x G + 128) >> 8
  3 derotation   theta = (w m) mod 2^32 (m = sample - s0),  idx = theta >> 22 (1024-entry cos / sin table, Q15),  (yr + j yi) (c - j s) rounded >> 15
  4 fine carrier T1 and T2 (64-sample windows, BACK = 6 samples inside their prefixes, 80 apart) derotated by w_c;  P = sum T2 conj(T1);  w_f = angle(P) x 2^12 / 80;   w = w_c + w_f;  the false-alarm check: 2 |P'|^2 >= E1' E2' (all >> 10)
  5 FFT 64      radix-2 decimation in time, bit-reversed input, twiddles Q15 with rounding after every butterfly multiply, NO scaling (20-bit data path: asserted)
  6 channel      H_k = ((A_k + B_k) conj(T_k) / sqrt 2) / 2   (T_k = (+-1 +-j)/sqrt 2: sign operations, 181 / 256 for 1 / sqrt 2);  W_k = conj(H_k) R 2^14 / |H_k|^2 (rounded integer division, R = 12953: unit RMS)
  7 per symbol   Z_k = (Y_k W_k + 2^13) >> 14;  pilots q = Z conj(ref) (signs, 181 / 256);  g = sum q / 4;  slope from the angle of d4 d11, d = q(+k) conj(q(-k)) (normalised to 14 bits): slope = angle / 30;  g and slope averaged over 5 symbols;
                 c_k = conj(g) R 2^14 / |g|^2 (Q14) x exp(-j slope k) (table);  Z' = Z c_k >> 14;   slicer thresholds 0, +-8192 (levels +-4096, +-12288), Gray decision, PRBS-15 checker, EVM sums
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "qam16"))
import qam_zc_fixed as Zc
import ofdm_model as Fm

N, CP, SYM, BACK = 64, 16, 80, 6
R, LV = 12953, 4096
TARGET = 400
THR256 = 166
USED, DATA, PIL = Fm.USED, Fm.DATA, Fm.PIL
KB = np.mod(USED, N)
UIDX = {int(k): i for i, k in enumerate(USED)}
D_IDX = np.array([UIDX[int(k)] for k in DATA]); P_IDX = np.array([UIDX[int(k)] for k in PIL])
TW_R = np.round(np.cos(2 * np.pi * np.arange(32) / 64) * 32767).astype(np.int64)
TW_I = np.round(-np.sin(2 * np.pi * np.arange(32) / 64) * 32767).astype(np.int64)
BITREV = np.array([int(format(i, "06b")[::-1], 2) for i in range(64)])
TR_S = np.sign(Fm.TRAIN.real * np.sqrt(2)).astype(np.int64), np.sign(Fm.TRAIN.imag * np.sqrt(2)).astype(np.int64)
PV_S = np.sign(Fm.PIL_V.real * np.sqrt(2)).astype(np.int64), np.sign(Fm.PIL_V.imag * np.sqrt(2)).astype(np.int64)
COS_L, SIN_L = Zc.COS_L, Zc.SIN_L
SQ2 = 181                                                                                                 # 1 / sqrt 2 in Q8


def rdiv(n, d):
    """integer division n / d rounded half away from zero (d > 0)"""
    n, d = int(n), int(d)
    return (1 if n >= 0 else -1) * ((2 * abs(n) + d) // (2 * d))


def isqrt(v): return int(np.sqrt(float(v))) if v < 2 ** 52 else int(v ** 0.5)


def signed(v, bits): return Zc.signed(int(v), bits)


def derotate(xi, xq, n0, count, s0, w, G):
    """samples n0 .. n0 + count - 1: gain, then rotation by exp(-j w (n - s0))"""
    n = np.arange(n0, n0 + count); gi = np.clip((xi[n0:n0 + count] * G + 128) >> 8, -16384, 16383); gq = np.clip((xq[n0:n0 + count] * G + 128) >> 8, -16384, 16383)
    th = ((int(w) * (n - s0)) & 0xFFFFFFFF); idx = th >> 22; c, s = COS_L[idx], SIN_L[idx]
    return (gi * c + gq * s + 16384) >> 15, (gq * c - gi * s + 16384) >> 15


def fft64(xr, xi):
    ar = np.array(xr, dtype=np.int64)[BITREV].copy(); ai = np.array(xi, dtype=np.int64)[BITREV].copy(); size = 2
    while size <= 64:
        half, step = size // 2, 64 // size
        i1 = np.concatenate([np.arange(s, s + half) for s in range(0, 64, size)]); i2 = i1 + half; wi = np.tile(np.arange(half) * step, 64 // size)
        wr_, wi_ = TW_R[wi], TW_I[wi]
        tr = (ar[i2] * wr_ - ai[i2] * wi_ + 16384) >> 15; ti = (ar[i2] * wi_ + ai[i2] * wr_ + 16384) >> 15
        ar[i2], ai[i2] = ar[i1] - tr, ai[i1] - ti; ar[i1] = ar[i1] + tr; ai[i1] = ai[i1] + ti
        size *= 2
    assert max(np.abs(ar).max(), np.abs(ai).max()) < 2 ** 19, "FFT data path overflow"
    return ar, ai


def norm14(re, im):
    sh = max(0, max(abs(int(re)), abs(int(im))).bit_length() - 14)
    return int(re) >> sh, int(im) >> sh


def metric(xi, xq):
    xi, xq = xi.astype(np.int64), xq.astype(np.int64)
    cr = xi[32:] * xi[:-32] + xq[32:] * xq[:-32]; ci = xq[32:] * xi[:-32] - xi[32:] * xq[:-32]; e = xi[32:] ** 2 + xq[32:] ** 2
    cs = lambda a: np.concatenate([[0], np.cumsum(a)]); Cr, Ci, Ee = cs(cr), cs(ci), cs(e)
    Sr, Si, E = Cr[32:] - Cr[:-32], Ci[32:] - Ci[:-32], Ee[32:] - Ee[:-32]
    Sr1, Si1, E1 = Sr >> 8, Si >> 8, E >> 8; S2 = Sr1 * Sr1 + Si1 * Si1; E2 = E1 * E1
    Ea = np.concatenate([np.zeros(32, dtype=np.int64), E[:-32]])[:len(E)]                                # the energy of the multiplied samples = E of the window 32 earlier (0 before): a strong signal ending in a quiet slot is not a plateau
    cond = (E1 >= 4) & (S2 * 256 >= THR256 * E2) & (Ea <= 2 * E)
    bl = np.array([int(v).bit_length() for v in E2]); sh = np.maximum(bl - 20, 0)                       # the quotient needs 20 bits of the divisor only
    S2s, E2s = S2 >> sh, E2 >> sh; mq = np.minimum((S2s << 10) // np.maximum(E2s, 1), 2047)
    return cond, mq, Sr, Si, E


def detect_info(xi, xq):
    """the detector, the plateau, the coarse carrier and the gain (the part of the receiver that rtl/ofdm_detect.v implements); None if nothing is found"""
    cond, mq, Sr, Si, E = metric(xi, xq); idx = np.nonzero(cond)[0]
    if len(idx) == 0 or idx[0] + 72 > len(mq): return None
    n0 = int(idx[0]); seg = mq[n0:n0 + 72]; pk = int(seg.max()); t90 = (pk * 29) >> 5; pl = np.nonzero(seg >= t90)[0]
    first, last = int(pl[0]), int(pl[-1]); s0 = n0 + ((first + last + 1) >> 1) - 8
    sr, si = int(Sr[n0 + first:n0 + last + 1].sum()), int(Si[n0 + first:n0 + last + 1].sum())
    w_c = signed(Zc.cordic_turns20(sr, si), 20) * 128
    Epk = int(E[n0 + int(np.argmax(seg))]); G = min(65535, (TARGET * 256) // max(isqrt(Epk >> 5), 1))
    return dict(n0=n0, first=first, last=last, s0=s0, w_c=w_c, G=G, Epk=Epk, sr=sr, si=si, pk=pk, cond=cond, mq=mq, Sr=Sr, Si=Si, E=E)


def receive_fixed(xi, xq, track_win=5, check=True):
    xi, xq = np.asarray(xi, dtype=np.int64), np.asarray(xq, dtype=np.int64)
    d = detect_info(xi, xq)
    if d is None: return None
    n0, s0, w_c, G, first, last = d["n0"], d["s0"], d["w_c"], d["G"], d["first"], d["last"]; pl = (first, last)
    t1 = s0 + SYM + CP - BACK; t2 = t1 + SYM
    if s0 < 0 or t2 + N > len(xi) or s0 + 240 + 44 * SYM > len(xi): return None
    a_r, a_i = derotate(xi, xq, t1, N, s0, w_c, G); b_r, b_i = derotate(xi, xq, t2, N, s0, w_c, G)
    Pr = int((b_r * a_r + b_i * a_i).sum()); Pi = int((b_i * a_r - b_r * a_i).sum())
    if check:
        e1, e2 = int((a_r ** 2 + a_i ** 2).sum()) >> 10, int((b_r ** 2 + b_i ** 2).sum()) >> 10; p1, p2 = Pr >> 10, Pi >> 10
        if 2 * (p1 * p1 + p2 * p2) < e1 * e2: return None                                              # the two training symbols do not repeat: not a frame
    w_f = (signed(Zc.cordic_turns20(Pr, Pi), 20) * 52429) >> 10
    w = signed(w_c + w_f, 32)
    # channel
    a_r, a_i = derotate(xi, xq, t1, N, s0, w, G); b_r, b_i = derotate(xi, xq, t2, N, s0, w, G)
    Ar, Ai = fft64(a_r, a_i); Br, Bi = fft64(b_r, b_i)
    sr_, si_ = Ar[KB] + Br[KB], Ai[KB] + Bi[KB]; u = TR_S[0] * sr_ + TR_S[1] * si_; v = TR_S[0] * si_ - TR_S[1] * sr_
    Hr = (((u * SQ2 + 128) >> 8) + 1) >> 1; Hi = (((v * SQ2 + 128) >> 8) + 1) >> 1
    noise = int(((Ar[KB] - Br[KB]) ** 2 + (Ai[KB] - Bi[KB]) ** 2).sum())
    K = R << 14; Wr = np.zeros(len(USED), dtype=np.int64); Wi = np.zeros(len(USED), dtype=np.int64)
    for i in range(len(USED)):
        den = int(Hr[i]) ** 2 + int(Hi[i]) ** 2
        if den: Wr[i] = rdiv(int(Hr[i]) * K, den); Wi[i] = rdiv(-int(Hi[i]) * K, den)
    # data symbols
    L = 44; Zr = np.zeros((L, len(USED)), dtype=np.int64); Zi = np.zeros_like(Zr); g = np.zeros((L, 2), dtype=np.int64); sl = np.zeros(L, dtype=np.int64); wins = []
    for l in range(L):
        ws = s0 + 240 + l * SYM + CP - BACK
        yr, yi = derotate(xi, xq, ws, N, s0, w, G); wins.append((yr, yi)); Yr, Yi = fft64(yr, yi); Yr, Yi = Yr[KB], Yi[KB]
        Zr[l] = (Yr * Wr - Yi * Wi + 8192) >> 14; Zi[l] = (Yr * Wi + Yi * Wr + 8192) >> 14
        pol = Fm.POL[l]; ps = int(pol)
        qr = np.zeros(4, dtype=np.int64); qi = np.zeros(4, dtype=np.int64)
        for j, ip in enumerate(P_IDX):
            rs, rsi = PV_S[0][j] * ps, PV_S[1][j] * ps                                                      # the reference (+-1 +-j) x polarity, still to be divided by sqrt 2
            uu = Zr[l, ip] * rs + Zi[l, ip] * rsi; vv = Zi[l, ip] * rs - Zr[l, ip] * rsi
            qr[j], qi[j] = (uu * SQ2 + 128) >> 8, (vv * SQ2 + 128) >> 8
        g[l] = ((int(qr.sum()) + 2) >> 2, (int(qi.sum()) + 2) >> 2)
        d4 = norm14(int(qr[2]) * int(qr[1]) + int(qi[2]) * int(qi[1]), int(qi[2]) * int(qr[1]) - int(qr[2]) * int(qi[1]))           # PIL = (-11, -4, 4, 11): q(+4) conj q(-4)
        d11 = norm14(int(qr[3]) * int(qr[0]) + int(qi[3]) * int(qi[0]), int(qi[3]) * int(qr[0]) - int(qr[3]) * int(qi[0]))
        dr, di = d4[0] * d11[0] - d4[1] * d11[1], d4[0] * d11[1] + d4[1] * d11[0]
        sl[l] = (signed(Zc.cordic_turns20(dr, di), 20) * 139811) >> 10
    assert np.abs(Zr).max() < 2 ** 23 and np.abs(Zi).max() < 2 ** 23, "Z does not fit 24 bits"
    half = track_win // 2; gs = np.zeros_like(g); ss = np.zeros_like(sl); g_raw, sl_raw = g.copy(), sl.copy()
    for l in range(L):
        lo, hi = max(0, l - half), min(L, l + half + 1); cnt = hi - lo; rc = (65536 + cnt // 2) // cnt
        gs[l] = ((g[lo:hi, 0].sum() * rc + 32768) >> 16, (g[lo:hi, 1].sum() * rc + 32768) >> 16); ss[l] = (sl[lo:hi].sum() * rc + 32768) >> 16
    out_r = np.zeros((L, len(DATA)), dtype=np.int64); out_i = np.zeros_like(out_r)
    for l in range(L):
        den = int(gs[l, 0]) ** 2 + int(gs[l, 1]) ** 2
        ir, ii = (rdiv(int(gs[l, 0]) * K, den), rdiv(-int(gs[l, 1]) * K, den)) if den else (1 << 14, 0)
        for j, kk in enumerate(DATA):
            th = (-int(ss[l]) * int(kk)) & 0xFFFFFFFF; c, s = int(COS_L[th >> 22]), int(SIN_L[th >> 22])
            cr_, ci_ = (ir * c - ii * s + 16384) >> 15, (ir * s + ii * c + 16384) >> 15
            assert abs(cr_) < 2 ** 19 and abs(ci_) < 2 ** 19, "correction does not fit 20 bits"
            zr, zi = int(Zr[l, D_IDX[j]]), int(Zi[l, D_IDX[j]])
            out_r[l, j], out_i[l, j] = (zr * cr_ - zi * ci_ + 8192) >> 14, (zr * ci_ + zi * cr_ + 8192) >> 14
    return dict(s0=s0, w_c=w_c, w_f=w_f, w=w, G=G, Zr=out_r, Zi=out_i, H=(Hr, Hi), W=(Wr, Wi), T1=(a_r, a_i), T2=(b_r, b_i), wins=wins, Zeq=(Zr, Zi), g_raw=g_raw, sl_raw=sl_raw, noise=noise, n0=n0, plateau=(first, last), g=gs, slope=ss, hz=signed(w, 32) / 2 ** 32 * Fm.FS)


LEVEL = lambda z: np.where(z < -8192, -3, np.where(z < 0, -1, np.where(z < 8192, 1, 3)))
GRAY_IDX = {-3: 0, -1: 1, 1: 3, 3: 2}


def score(res, bits=None):
    """symbol and bit errors against the PRBS-15 payload, EVM (the checker of the receiver)"""
    bits = Fm.payload_bits() if bits is None else bits
    ref = bits.reshape(44, len(DATA), 4).astype(int); ridx = ref[..., 0] * 8 + ref[..., 1] * 4 + ref[..., 2] * 2 + ref[..., 3]
    si, sq = LEVEL(res["Zr"]), LEVEL(res["Zi"]); gi = np.vectorize(GRAY_IDX.get)(si) * 4 + np.vectorize(GRAY_IDX.get)(sq)
    ser = float(np.mean(gi != ridx)); ber = float(np.mean([bin(int(a) ^ int(b)).count("1") for a, b in zip(gi.ravel(), ridx.ravel())]) / 4)
    err = ((res["Zr"] - si * LV) ** 2 + (res["Zi"] - sq * LV) ** 2).sum(); refp = ((si ** 2 + sq ** 2) * LV * LV).sum()
    return dict(ser=ser, ber=ber, evm=10 * np.log10(err / refp))


def to_adc(y, rms_counts):
    """float samples of ofdm_model.channel -> 12-bit counts; the time-domain signal power of a frame is 28 / 64"""
    k = rms_counts / np.sqrt(28 / 64); return np.clip(np.round(y.real * k), -2047, 2047).astype(np.int64), np.clip(np.round(y.imag * k), -2047, 2047).astype(np.int64)
