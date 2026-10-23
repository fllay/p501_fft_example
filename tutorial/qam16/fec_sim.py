#!/usr/bin/env python3
"""FEC study for the 16-QAM frame (882 payload symbols = 3528 coded bits, Gray-mapped, one codeword per frame): K=7 rate-1/2 convolutional code with soft Viterbi, polar code (N = 4096 shortened to 3528)
with plain successive cancellation and with CRC-16-aided list decoding. The decoders are in fec_core.c (compile: gcc -O3 -shared -fPIC -o libfec.so fec_core.c -lm).
    python3 fec_sim.py selftest | awgn | link        results -> results_fec.txt (appended by the caller)
Channels: AWGN at Es/N0, and the measured link model (LINK_REPORT_QAM16.md section 5): y = s (1 + eps) + n with n white, variance A (137/S)^2, and eps the slow multiplicative error measured on the P501 ADC capture."""
import sys, os, ctypes, time
import numpy as np
from scipy.special import erfc
HERE = os.path.dirname(os.path.abspath(__file__))
lib = ctypes.CDLL(os.path.join(HERE, "libfec.so"))
u8p, f32p, i32p = (np.ctypeslib.ndpointer(dtype=t, flags="C_CONTIGUOUS") for t in (np.uint8, np.float32, np.int32))
lib.conv_encode.argtypes = [u8p, ctypes.c_int, u8p]
lib.viterbi.argtypes = [f32p, ctypes.c_int, u8p]
lib.polar_encode.argtypes = [u8p, ctypes.c_int, u8p]
lib.crc16_bits.argtypes = [u8p, ctypes.c_int, u8p]
lib.polar_scl.argtypes = [f32p, ctypes.c_int, u8p, i32p, ctypes.c_int, ctypes.c_int, ctypes.c_int, u8p]
lib.polar_scl.restype = ctypes.c_int

N_SYM, BITS = 882, 3528
M, NP = 12, 4096
K_INFO = 1758                      # information bits per frame (convolutional: 1764 trellis steps - 6 tail bits)
A_FLOOR, B_MULT, S1 = 0.0115, 0.013, 137.0
S10 = np.sqrt(10.0)
LEV = np.array([-3.0, -1.0, 1.0, 3.0])                     # Gray: -3 = 00, -1 = 01, +1 = 11, +3 = 10
B0 = np.array([0, 0, 1, 1]); B1 = np.array([0, 1, 1, 0])
PERM = np.random.default_rng(12345).permutation(BITS)       # bit interleaver between the code and the 16-QAM mapping


# ------------------------------------------------------------------ mapping and soft demapping
def map16(bits):
    b = bits.reshape(-1, 4)
    code = lambda b0, b1: np.where(b0 == 0, np.where(b1 == 0, -3.0, -1.0), np.where(b1 == 1, 1.0, 3.0))
    return (code(b[:, 0], b[:, 1]) + 1j * code(b[:, 2], b[:, 3])) / S10


def llr16(y):
    out = np.empty((len(y), 4))
    for ax, v in enumerate((y.real * S10, y.imag * S10)):
        d = (v[:, None] - LEV[None, :]) ** 2
        for bi, bm in enumerate((B0, B1)):
            out[:, 2 * ax + bi] = d[:, bm == 1].min(axis=1) - d[:, bm == 0].min(axis=1)       # > 0: the bit is 0
    return out.reshape(-1)


# ------------------------------------------------------------------ polar code design (Gaussian approximation) with shortening
def _phi(x):
    x = np.asarray(x, float); out = np.empty_like(x)
    s = x <= 10
    out[s] = np.exp(-0.4527 * x[s] ** 0.86 + 0.0218)
    xl = x[~s]; out[~s] = np.sqrt(np.pi / xl) * np.exp(-xl / 4) * (1 - 10.0 / (7 * xl))
    return out
_GRID = np.geomspace(1e-5, 600, 6000); _PG = _phi(_GRID)
def _phi_inv(y): return np.exp(np.interp(np.log(np.clip(y, 1e-300, 1 - 1e-12)), np.log(_PG[::-1]), np.log(_GRID[::-1])))


def polar_design(ebn0_db, K, E=BITS, N=NP):
    R = K / E
    mu0 = np.full(N, 500.0); mu0[:E] = 4 * R * 10 ** (ebn0_db / 10)
    m = int(np.log2(N)); mu = {0: mu0[None, :]}
    for lam in range(1, m + 1):
        prev = mu[lam - 1]; nph = 2 ** lam; n = N >> lam
        cur = np.empty((nph, n))
        for phi in range(nph):
            a = prev[phi >> 1][0::2]; b = prev[phi >> 1][1::2]
            cur[phi] = _phi_inv(1 - (1 - _phi(a)) * (1 - _phi(b))) if phi % 2 == 0 else a + b
        mu[lam] = cur
    return mu[m][:, 0]                                       # reliability (mean LLR) of u_0 ... u_{N-1}


def shortening_set(E=BITS, N=NP):
    """u positions that must be frozen so that the last N - E code bits are 0 (found from the encoder: rows of G with a 1 in the last N - E columns)"""
    Z = np.zeros(N, bool)
    for j in range(N):
        u = np.zeros(N, np.uint8); u[j] = 1; x = np.empty(N, np.uint8); lib.polar_encode(u, M, x); Z[j] = x[E:].any()
    return Z


class Polar:
    def __init__(self, K, crc, ebn0_db=3.0):
        self.K, self.crc = K, crc
        Z = shortening_set()
        rel = polar_design(ebn0_db, K); rel[Z] = -1
        self.info = np.sort(np.argsort(-rel)[:K]).astype(np.int32)
        self.frozen = np.ones(NP, np.uint8); self.frozen[self.info] = 0

    def encode(self, data):
        bits = data
        if self.crc:
            c = np.empty(16, np.uint8); lib.crc16_bits(np.ascontiguousarray(data), len(data), c); bits = np.concatenate([data, c])
        u = np.zeros(NP, np.uint8); u[self.info] = bits
        x = np.empty(NP, np.uint8); lib.polar_encode(u, M, x)
        assert not x[BITS:].any()
        return x[:BITS]

    def decode(self, llr, L):
        ch = np.full(NP, 1e6, np.float32); ch[:BITS] = llr
        u = np.empty(NP, np.uint8); lib.polar_scl(ch, M, self.frozen, self.info, self.K, L, 1 if self.crc else 0, u)
        bits = u[self.info]
        return bits[:-16] if self.crc else bits


class Conv:
    def encode(self, data):
        u = np.concatenate([data, np.zeros(6, np.uint8)]); c = np.empty(BITS, np.uint8); lib.conv_encode(u, len(u), c); return c

    def decode(self, llr):
        u = np.empty(BITS // 2, np.uint8); lib.viterbi(np.ascontiguousarray(llr, dtype=np.float32), BITS // 2, u); return u[:-6]


# ------------------------------------------------------------------ channels
def eps_bank(path=os.path.join(HERE, "sim", "eps_c1.npy")):
    return np.load(path)


def chan_awgn(s, esn0_db, rng):
    n = np.sqrt(0.5 / 10 ** (esn0_db / 10)) * (rng.standard_normal(len(s)) + 1j * rng.standard_normal(len(s)))
    return s + n


def chan_link(s, level, rng, bank):
    eps = bank[rng.integers(len(bank))]                      # the slow part of the multiplicative error as measured (variance 0.0006 to 0.0012)
    v_slow = float(np.mean(np.abs(bank) ** 2))
    w = np.sqrt(0.5 * max(B_MULT - v_slow, 0.0)) * (rng.standard_normal(len(s)) + 1j * rng.standard_normal(len(s)))      # the rest of B: not reproducible from the capture, taken as white
    n = np.sqrt(0.5 * A_FLOOR * (S1 / level) ** 2) * (rng.standard_normal(len(s)) + 1j * rng.standard_normal(len(s)))
    return s * (1 + eps + w) + n


# ------------------------------------------------------------------ one operating point
def run_point(args):
    """args: (scheme, channel, param, frames, seed). Returns (scheme, param, FER, BER, uncoded SER of the symbols)"""
    scheme, chan, param, frames, seed = args
    design = 3.0
    if "@" in scheme: scheme, design = scheme.split("@"); design = float(design)          # e.g. "scl8@2.0": polar code designed for Eb/N0 = 2.0 dB
    rng = np.random.default_rng(seed)
    bank = eps_bank() if chan == "link" else None
    if scheme == "conv": code = Conv()
    elif scheme == "sc": code = Polar(K_INFO, False, design)
    elif scheme.startswith("scl"): code = Polar(K_INFO, True, design)
    L = int(scheme[3:]) if scheme.startswith("scl") else 1
    kdata = K_INFO - 16 if scheme.startswith("scl") else K_INFO
    fe = be = se = 0
    for _ in range(frames):
        data = rng.integers(0, 2, kdata).astype(np.uint8)
        if scheme == "uncoded":
            bits = rng.integers(0, 2, BITS).astype(np.uint8)
        else:
            c = code.encode(data); bits = np.empty(BITS, np.uint8); bits[PERM] = c
        s = map16(bits)
        y = chan_awgn(s, param, rng) if chan == "awgn" else chan_link(s, param, rng, bank)
        l = llr16(y)
        hard = (l < 0).astype(np.uint8)
        se += int(np.sum(np.any((hard != bits).reshape(-1, 4), axis=1)))
        if scheme == "uncoded":
            fe += int(np.any(hard != bits)); be += int(np.sum(hard != bits)); continue
        lc = l[PERM].astype(np.float32)
        d = code.decode(lc) if scheme == "conv" else code.decode(lc, L)
        e = int(np.sum(d != data)); fe += int(e > 0); be += e
    return scheme, param, fe / frames, be / (frames * (kdata if scheme != "uncoded" else BITS)), se / (frames * N_SYM)


# ------------------------------------------------------------------ the measured multiplicative error (from analyse_avg.py's receiver run on the capture)
def make_eps_bank(capfile="sim/adc_c1.c64", out="sim/eps_c1.npy", blk=21):
    import qam16_rx_fixed as X, frame16 as F
    from study_pll_lowsnr import GI_ACQ
    gi_trk = X.FL.gains(0.0001)[0]; LV = 4096
    inv = {v: k for k, v in F.LEVEL_IDX.items()}; ref = F.prbs15_indices()
    ideal = np.array([(inv[i // 4] + 1j * inv[i % 4]) * LV for i in ref], dtype=complex)
    x = np.fromfile(os.path.join(HERE, capfile), dtype=np.complex64).astype(complex); y = x / np.sqrt(np.mean(np.abs(x) ** 2)) * 100.0
    xi, xq = np.clip(np.round(y.real), -2047, 2047).astype(np.int64), np.clip(np.round(y.imag), -2047, 2047).astype(np.int64)
    fe, sy, r = X.receive16(xi, xq, X.regs16(), fll=(GI_ACQ, 0, 0), fll_sched={19200: (gi_trk, 0)})
    z = np.array([a + 1j * b for a, b in r.out], dtype=complex); n = len(z) // F.N_PAY; z = z[:n * F.N_PAY].reshape(n, F.N_PAY)[30:]
    e = z - ideal
    nb = F.N_PAY // blk
    g = np.sum(e.reshape(-1, nb, blk) * np.conj(ideal).reshape(nb, blk), axis=2) / np.sum(np.abs(ideal.reshape(nb, blk)) ** 2, axis=1)      # block gain error (additive noise averaged over the block)
    centres = (np.arange(nb) + 0.5) * blk
    bank = np.array([np.interp(np.arange(F.N_PAY), centres, gg.real) + 1j * np.interp(np.arange(F.N_PAY), centres, gg.imag) for gg in g])
    np.save(os.path.join(HERE, out), bank)
    print("eps bank: %d frames x %d, variance %.4f (%.1f dB), after removing the block noise ~ %.4f; autocorrelation of eps over %d symbols: %s" %
          (len(bank), F.N_PAY, np.mean(np.abs(bank) ** 2), 10 * np.log10(np.mean(np.abs(bank) ** 2)), np.mean(np.abs(bank) ** 2) - A_FLOOR / blk, 21,
           np.round([np.real(np.mean(bank[:, :-l] * np.conj(bank[:, l:])) / np.mean(np.abs(bank) ** 2)) for l in (1, 5, 21, 63, 200)], 2)))
    return bank


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "selftest"
    if cmd == "selftest":
        rng = np.random.default_rng(1)
        c = Conv(); d = rng.integers(0, 2, K_INFO).astype(np.uint8); x = c.encode(d); l = np.where(x == 0, 4.0, -4.0).astype(np.float32)
        print("conv noiseless:", np.array_equal(c.decode(l), d))
        t = time.time(); pc = Polar(K_INFO, True); print("polar design %.1f s, info positions %d, frozen incl. shortened %d" % (time.time() - t, len(pc.info), int(pc.frozen.sum())))
        d2 = rng.integers(0, 2, K_INFO - 16).astype(np.uint8); x2 = pc.encode(d2); l2 = np.where(x2 == 0, 4.0, -4.0).astype(np.float32)
        t = time.time(); print("polar CA-SCL L=8 noiseless:", np.array_equal(pc.decode(l2, 8), d2), "%.2f s" % (time.time() - t))
        ps = Polar(K_INFO, False); d3 = rng.integers(0, 2, K_INFO).astype(np.uint8); x3 = ps.encode(d3); l3 = np.where(x3 == 0, 4.0, -4.0).astype(np.float32)
        print("polar SC noiseless:", np.array_equal(ps.decode(l3, 1), d3))
        for sch in ("uncoded", "conv", "sc", "scl8"):
            t = time.time(); print(run_point((sch, "awgn", 9.0, 20, 5)), "%.2f s per 20 frames" % (time.time() - t))
