"""Float model of a 16-QAM OFDM link for the P501 (3.84 MS/s), with QPSK training and pilot symbols. Reference for the design in PLAN_OFDM.md; no RTL, no hardware.

  N = 64 (60 kHz spacing), CP = 16, used subcarriers -14..-1, +1..+14 (28), 4 QPSK pilots (-11, -4, +4, +11), 24 16-QAM data subcarriers
  frame = STS (period 16, 128 samples) | LTS (GI2 32 + 2 x 64, QPSK on all 28 used subcarriers) | 44 data symbols of 80 samples | 32 idle = 3840 samples = 1 ms
  receiver = detection (lag-16 delay-and-correlate) -> coarse carrier from the STS -> fine carrier from the two LTS symbols -> channel from the LTS (QPSK known) -> equalise one tap per subcarrier
             -> per symbol: the QPSK pilots give the common complex gain (and the slope across the subcarriers) -> 16-QAM slicer
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "qam16"))
import frame16 as F

N, CP, FS = 64, 16, 3.84e6
DF = FS / N
HALF = 14
USED = np.array([k for k in range(-HALF, HALF + 1) if k != 0])
PIL = np.array([-11, -4, 4, 11])
DATA = np.array([k for k in USED if k not in PIL])
STS_K = np.array([-12, -8, -4, 4, 8, 12])
L_SYM = 44
STS_LEN, LTS_LEN, SYM, GAP = 128, 160, N + CP, 32
FRAME = STS_LEN + LTS_LEN + L_SYM * SYM + GAP
BITS_SYM = 4 * len(DATA)
BACK = 6                                                                    # the FFT window starts BACK samples early, inside the cyclic prefix (timing tolerance +-BACK)


def qpsk(rng, n): return ((1 - 2 * rng.integers(0, 2, n)) + 1j * (1 - 2 * rng.integers(0, 2, n))) / np.sqrt(2)
def papr_db(x): return 10 * np.log10(np.max(np.abs(x) ** 2) / np.mean(np.abs(x) ** 2))
def bin_of(k): return np.mod(k, N)


def to_time(Xk):
    """subcarrier values (dict k -> value as arrays over the used set) -> N samples; unit average power per loaded subcarrier"""
    X = np.zeros(N, complex); X[bin_of(Xk[0])] = Xk[1]
    return np.fft.ifft(X) * np.sqrt(N)


def best_qpsk(n_search=4000, seed=7, ks=USED):
    """the QPSK training values of the LTS: the best of n_search random sequences by the peak-to-average power ratio of the 64-sample symbol"""
    rng = np.random.default_rng(seed); best = None
    for _ in range(n_search):
        v = qpsk(rng, len(ks)); p = papr_db(to_time((ks, v)))
        if best is None or p < best[0]: best = (p, v)
    return best


PAPR_T, TRAIN = best_qpsk()
STS_V = qpsk(np.random.default_rng(11), len(STS_K)) * np.sqrt(len(USED) / len(STS_K))        # same power per sample as a data symbol
PIL_V = np.array([1 + 1j, 1 - 1j, -1 + 1j, -1 - 1j]) / np.sqrt(2)


def pilot_polarity(n):
    s, out = 0x7F, []                                                       # x^7 + x^6 + 1 as in IEEE 802.11
    for _ in range(n):
        out.append(1 - 2 * (s >> 6 & 1)); s = ((s << 1) & 0x7F) | ((s >> 6 ^ s >> 5) & 1)
    return np.array(out, float)
POL = pilot_polarity(L_SYM)


def payload_bits(): return F.prbs15_bits(L_SYM * BITS_SYM)
def qam_syms(bits):
    b = bits.reshape(-1, 4).astype(int); return F.qam(b[:, 0] * 8 + b[:, 1] * 4 + b[:, 2] * 2 + b[:, 3])


def tx_frame(bits=None, rms=None):
    """-> samples (FRAME), the data symbols sent (L_SYM x 24)"""
    bits = payload_bits() if bits is None else bits
    d = qam_syms(bits).reshape(L_SYM, len(DATA)) * np.sqrt(10) / np.sqrt(10)          # F.qam is unit power already
    sts = np.tile(to_time((STS_K, STS_V)), 2)[:STS_LEN]
    T = to_time((USED, TRAIN)); lts = np.concatenate([T[-2 * CP:], T, T])
    syms = []
    for l in range(L_SYM):
        X = np.zeros(N, complex); X[bin_of(DATA)] = d[l]; X[bin_of(PIL)] = PIL_V * POL[l]
        x = np.fft.ifft(X) * np.sqrt(N); syms.append(np.concatenate([x[-CP:], x]))
    x = np.concatenate([sts, lts] + syms + [np.zeros(GAP, complex)])
    return x, d


def channel(x, snr_db, cfo_hz=0.0, tau=0.0, ppm=0.0, taps=None, slow=0.0, slow_hz=137.0, white=0.0, lead=300, trail=300, rng=None, phase=None):
    """snr_db: per-subcarrier Es/N0 (unit power per loaded subcarrier, noise variance 10^(-snr/10) per sample and per FFT bin).
    tau: delay in samples (fractional ok); taps: multipath FIR; slow / white: variance of a slow (slow_hz) or white multiplicative modulation of the signal"""
    rng = rng or np.random.default_rng(); y = np.concatenate([np.zeros(lead, complex), x, np.zeros(trail, complex)])
    if taps is not None: y = np.convolve(y, taps)[:len(y)]
    if tau:
        n2 = 1 << int(np.ceil(np.log2(len(y) + 64))); Y = np.fft.fft(y, n2) * np.exp(-2j * np.pi * np.fft.fftfreq(n2) * tau); y = np.fft.ifft(Y)[:len(y)]
    if ppm:
        t = np.arange(len(y)) * (1 + ppm * 1e-6); y = np.interp(t, np.arange(len(y)), y.real) + 1j * np.interp(t, np.arange(len(y)), y.imag)
    n = np.arange(len(y)); ph = rng.uniform(0, 2 * np.pi) if phase is None else phase
    y = y * np.exp(1j * (2 * np.pi * cfo_hz / FS * n + ph))
    if slow: y = y * (1 + np.sqrt(slow) * np.exp(1j * (2 * np.pi * slow_hz / FS * n + rng.uniform(0, 2 * np.pi))))
    if white: y = y * (1 + np.sqrt(white / 2) * (rng.standard_normal(len(y)) + 1j * rng.standard_normal(len(y))))
    s2 = 10 ** (-snr_db / 10)
    return y + np.sqrt(s2 / 2) * (rng.standard_normal(len(y)) + 1j * rng.standard_normal(len(y)))


def timing_metric(x, lag=16, win=48):
    c = x[lag:] * np.conj(x[:-lag]); e = np.abs(x[lag:]) ** 2
    cs = np.concatenate([[0], np.cumsum(c)]); es = np.concatenate([[0], np.cumsum(e)])
    S = cs[win:] - cs[:-win]; E = es[win:] - es[:-win]
    return np.abs(S) ** 2 / (E ** 2 + 1e-12), S


def detect(x, thr=0.5, lag=16):
    """-> (start of the STS, coarse carrier offset in Hz) or None. The window of 48 products (lags of 16) is inside the 128-sample STS for 65 start positions: the plateau; its centre minus 32 is the STS start."""
    M, S = timing_metric(x, lag)
    idx = np.nonzero(M > thr)[0]
    if len(idx) == 0: return None
    n0 = idx[0]; seg = M[n0:n0 + 140]; pk = seg.max(); pl = np.nonzero(seg >= 0.8 * pk)[0]
    c = n0 + 0.5 * (pl[0] + pl[-1]); s0 = int(round(c - 32))
    f = np.angle(np.sum(S[n0 + pl[0]:n0 + pl[-1] + 1])) / (2 * np.pi * lag / FS)
    return s0, f, M


def receive(x, track="complex", genie=None, thr=0.5, return_all=False, gsmooth=1):
    """x: received samples (noise, then a frame). genie = (s0, cfo_hz): skip the detection. track: none | phase | complex | complex+slope (what the pilots correct per symbol).
    gsmooth: the pilot gain (and slope) estimates are averaged over this many symbols (centred moving average; 1 = none)"""
    if genie is None:
        d = detect(x, thr)
        if d is None: return None
        s0, f_c, _ = d
    else: s0, f_c = genie
    n = np.arange(len(x)); xr = x * np.exp(-2j * np.pi * f_c / FS * (n - s0))                            # coarse correction
    t1 = s0 + STS_LEN + 2 * CP - BACK
    if t1 < 0 or t1 + 2 * N > len(x): return None
    T1, T2 = xr[t1:t1 + N], xr[t1 + N:t1 + 2 * N]
    f_f = np.angle(np.sum(T2 * np.conj(T1))) / (2 * np.pi * N / FS)
    xr = xr * np.exp(-2j * np.pi * f_f / FS * (n - s0))                                                   # fine correction
    A = np.fft.fft(xr[t1:t1 + N]) / np.sqrt(N); B = np.fft.fft(xr[t1 + N:t1 + 2 * N]) / np.sqrt(N); kb = bin_of(USED)
    H = 0.5 * (A[kb] + B[kb]) * np.conj(TRAIN)                                                           # |TRAIN| = 1
    sig2 = np.mean(np.abs(A[kb] - B[kb]) ** 2) / 2                                                       # noise variance per bin from the two equal symbols
    Hd = dict(zip(USED, H)); Hdat = np.array([Hd[k] for k in DATA]); Hpil = np.array([Hd[k] for k in PIL])
    base = s0 + STS_LEN + LTS_LEN
    if base + L_SYM * SYM > len(xr): return None
    Zd, Zp, g, sl = [], [], np.zeros(L_SYM, complex), np.zeros(L_SYM)
    for l in range(L_SYM):
        st = base + l * SYM + CP - BACK
        Y = np.fft.fft(xr[st:st + N]) / np.sqrt(N)
        zd, zp = Y[bin_of(DATA)] / Hdat, Y[bin_of(PIL)] / Hpil; ref = PIL_V * POL[l]
        if track == "complex+slope":
            ph = np.unwrap(np.angle(zp * np.conj(ref))); sl[l] = np.polyfit(PIL, ph, 1)[0]
            zp = zp * np.exp(-1j * sl[l] * PIL)
        g[l] = np.sum(zp * np.conj(ref)) / len(PIL)                                                      # common complex gain of this symbol
        Zd.append(zd); Zp.append(zp)
    if gsmooth > 1:
        w = np.ones(gsmooth); cnt = np.convolve(np.ones(L_SYM), w, "same"); g = np.convolve(g, w, "same") / cnt; sl = np.convolve(sl, w, "same") / cnt
    out = np.zeros((L_SYM, len(DATA)), complex)
    for l in range(L_SYM):
        zd = Zd[l]
        if track == "phase": zd = zd * np.exp(-1j * np.angle(g[l]))
        elif track.startswith("complex"):
            if track == "complex+slope": zd = zd * np.exp(-1j * sl[l] * DATA)
            zd = zd / g[l]
        out[l] = zd
    if return_all: return dict(Z=out, H=H, sig2=sig2, s0=s0, f=f_c + f_f, f_c=f_c, f_f=f_f, gains=g)
    return out, dict(H=H, sig2=sig2, s0=s0, f=f_c + f_f)


def hard(Z):
    lv = np.array([-3, -1, 1, 3]) / np.sqrt(10)
    zi = lv[np.argmin(np.abs(Z.real[..., None] - lv), axis=-1)]; zq = lv[np.argmin(np.abs(Z.imag[..., None] - lv), axis=-1)]
    return zi + 1j * zq


def metrics(Z, d):
    e = Z - d; evm = 10 * np.log10(np.mean(np.abs(e) ** 2) / np.mean(np.abs(d) ** 2)); h = hard(Z)
    return evm, float(np.mean(np.abs(h - d) > 1e-6))


def sc_papr_db(nsym=20000, seed=3):
    """single-carrier 16-QAM with the RRC filter of the 16-QAM link, 4 samples per symbol: the PAPR distribution for comparison"""
    sys.path.insert(0, os.path.join(HERE, "..", "qam16")); from make_signal16 import tx_samples
    rng = np.random.default_rng(seed); idx = rng.integers(0, 16, nsym); x = tx_samples(F.qam(idx))[200:-200]
    p = np.abs(x) ** 2; return p / p.mean()
if __name__ == "__main__":
    print("frame %d samples, used %d, data %d, pilots %d, bits per frame %d, PAPR of the training symbol %.2f dB" % (FRAME, len(USED), len(DATA), len(PIL), L_SYM * BITS_SYM, PAPR_T))
    x, d = tx_frame(); print("mean power %.3f (expected %.3f)" % (np.mean(np.abs(x[:FRAME - GAP]) ** 2), len(USED) / N))
    rng = np.random.default_rng(1); y = channel(x, 40, cfo_hz=9700, tau=3.4, rng=rng)
    r = receive(y, return_all=True); print("detected: s0 %d (true 300+3 = 303), f %.0f Hz (true 9700)" % (r["s0"], r["f"]))
    print("EVM %.1f dB, SER %.2e" % metrics(r["Z"], d))
