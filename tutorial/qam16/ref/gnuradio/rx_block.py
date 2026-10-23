"""ZC frame sync + carrier PLL + gain for the 16-QAM / Zadoff-Chu frame (1 sample per symbol in, data symbols out).

In : complex symbols after the matched filter and timing recovery (1 sps)
Out: the 882 payload data symbols of every locked frame, gain-normalised and derotated (unit average power)

States: SEARCH (normalised correlation with the ZC word) -> verify one frame later (967 symbols) -> LOCKED.
Per locked frame: gain and absolute phase from the sync word, then a 2nd-order PLL over the payload
(decision-directed on data, data-aided on the pilot at the end of every 64-symbol block). The PLL is frozen over CP + sync word.
"""
import math
import numpy as np
from gnuradio import gr

N_ZC, ROOT, N_CP, N_BLK, N_DATA = 63, 1, 8, 14, 63
N_PAY = N_BLK * N_DATA
BLK = N_DATA + 1
PAY_LEN = N_BLK * BLK                        # 896
FRAME = N_CP + N_ZC + PAY_LEN                # 967
S10 = math.sqrt(10.0)
PILOTS = [1.0, 1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0, -1.0, -1.0, 1.0, -1.0, 1.0]
_N = np.arange(N_ZC)
ZC = np.exp(-1j * np.pi * ROOT * _N * (_N + 1) / N_ZC)
GRAY_IDX = {-3: 0, -1: 1, 1: 3, 3: 2}        # level -> 2-bit index (inverse of the transmitter table)


def _level(a):                               # a = value * sqrt(10)
    return -3 if a < -2 else (-1 if a < 0 else (1 if a < 2 else 3))


def tx_fixed_indices(seed):
    return np.random.RandomState(int(seed)).randint(0, 16, N_PAY)


def tone_freq(z, pad=16):
    """frequency (cycles/symbol) of the strongest tone in z: zero-padded FFT + parabolic interpolation"""
    nf = pad * len(z)
    s = np.abs(np.fft.fft(z, nf))
    k = int(np.argmax(s))
    a, b, c = np.log(s[(k - 1) % nf] + 1e-30), np.log(s[k] + 1e-30), np.log(s[(k + 1) % nf] + 1e-30)
    den = a - 2 * b + c
    d = 0.5 * (a - c) / den if den != 0 else 0.0
    kk = k + d
    if kk > nf / 2:
        kk -= nf
    return kk / nf


class FrameRx:
    def __init__(self, loop_bw=0.02, thr_search=0.6, thr_lock=0.45, max_miss=3, pilot_weight=3.0,
                 check_payload=False, seed=1):
        zeta = 0.7071
        den = 1 + 2 * zeta * loop_bw + loop_bw ** 2
        self.alpha, self.beta = 4 * zeta * loop_bw / den, 4 * loop_bw ** 2 / den
        self.thr_search, self.thr_lock, self.max_miss, self.pw = thr_search, thr_lock, max_miss, pilot_weight
        self.check = bool(check_payload)
        self.ref_idx = tx_fixed_indices(seed)
        self.buf = np.zeros(0, dtype=complex)
        self.locked = False
        self.pos = 0
        self.first = True
        self.miss = 0
        self.omega = 0.0           # rad / symbol, residual carrier frequency (PLL integrator)
        self.amp = 1.0
        self.frames = 0
        self.evm_db = float('nan')
        self.sym_err = 0
        self.sym_cnt = 0
        self.lock_count = 0

    # ---------- helpers ----------
    @staticmethod
    def _rho(seg):
        c = np.abs(np.correlate(seg, ZC, 'valid'))
        e = np.concatenate([[0.0], np.cumsum(np.abs(seg) ** 2)])
        we = e[N_ZC:] - e[:-N_ZC]
        return c / np.sqrt(we * N_ZC + 1e-20)

    # ---------- main entry ----------
    def push(self, x):
        self.buf = np.concatenate([self.buf, np.asarray(x, dtype=complex)])
        out = []
        while True:
            more = self._frame(out) if self.locked else self._search()
            if not more:
                break
        return np.concatenate(out) if out else np.zeros(0, dtype=complex)

    def _search(self):
        L = len(self.buf)
        if L < N_ZC:
            return False
        rho = self._rho(self.buf)
        k = int(np.argmax(rho))
        if rho[k] < self.thr_search:
            self.buf = self.buf[-(N_ZC - 1):]
            return False
        if k + FRAME + N_ZC + 4 > L:           # cannot verify yet: wait, keeping data from the candidate on
            self.buf = self.buf[k:]
            return False
        seg = self.buf[k + FRAME - 3: k + FRAME + 3 + N_ZC]
        if np.max(self._rho(seg)) >= self.thr_lock:
            self.buf = self.buf[k:]
            self.pos, self.locked, self.first, self.miss = 0, True, True, 0
            self.lock_count += 1
            return True
        self.buf = self.buf[k + 1:]            # false alarm: look further
        return True

    def _frame(self, out):
        L = len(self.buf)
        if L < self.pos + N_ZC + PAY_LEN + 8:
            return False
        lo = max(self.pos - 4, 0)
        seg = self.buf[lo: self.pos + 4 + N_ZC]
        rho = self._rho(seg)
        j = int(np.argmax(rho))
        if rho[j] >= self.thr_lock:
            start, self.miss = lo + j, 0
        else:
            start, self.miss = self.pos, self.miss + 1
            if self.miss > self.max_miss:      # lost the frame: back to SEARCH
                self.locked = False
                self.buf = self.buf[self.pos + 1:]
                self.omega = 0.0
                return True
        win = self.buf[start: start + N_ZC]
        z = win * np.conj(ZC)
        h = z.sum() / N_ZC
        if self.first:
            self.omega = 2 * math.pi * tone_freq(z)
            self.amp = abs(h)
        else:
            self.amp = 0.7 * self.amp + 0.3 * abs(h)
        c = (N_ZC - 1) / 2.0
        ph_c = np.angle(np.sum(z * np.exp(-1j * self.omega * (_N - c))))
        theta = ph_c + self.omega * (N_ZC - c)
        self.first = False
        pay = self.buf[start + N_ZC: start + N_ZC + PAY_LEN] / max(self.amp, 1e-9)
        res = self._pll(pay, theta)
        out.append(res)
        self.frames += 1
        self.pos = start + FRAME - FRAME          # next frame starts FRAME symbols after this one's start
        self.buf = self.buf[start + FRAME - 4:]
        self.pos = 4
        return True

    def _pll(self, pay, theta):
        al, be, pw = self.alpha, self.beta, self.pw
        om = self.omega
        data = []
        err2 = ref2 = 0.0
        ref_idx = self.ref_idx
        d = 0
        mism = 0
        pr = pay.real.tolist()
        pi_ = pay.imag.tolist()
        for i in range(PAY_LEN):
            cs, sn = math.cos(theta), math.sin(theta)
            yr, yi = pr[i], pi_[i]
            zr, zi = yr * cs + yi * sn, yi * cs - yr * sn
            if i % BLK == BLK - 1:                                   # pilot
                rr, ri, w = PILOTS[i // BLK], 0.0, pw
            else:
                lr, lq = _level(zr * S10), _level(zi * S10)
                rr, ri, w = lr / S10, lq / S10, 1.0
                data.append(complex(zr, zi))
                err2 += (zr - rr) ** 2 + (zi - ri) ** 2
                ref2 += rr * rr + ri * ri
                if self.check:
                    if 4 * GRAY_IDX[lr] + GRAY_IDX[lq] != ref_idx[d]:
                        mism += 1
                d += 1
            e = (zi * rr - zr * ri) * w
            om += be * e
            theta += om + al * e
        self.omega = om
        if self.check:
            self.sym_err += mism
            self.sym_cnt += N_PAY
        self.evm_db = 10 * math.log10(max(err2, 1e-12) / max(ref2, 1e-12))
        return np.array(data, dtype=complex)


class blk(gr.basic_block):
    def __init__(self, symbol_rate=250000.0, loop_bw=0.02, thr_search=0.6, pilot_weight=3.0,
                 check_payload=False, seed=1, print_every=200):
        gr.basic_block.__init__(self, name='ZC frame sync + carrier PLL', in_sig=[np.complex64], out_sig=[np.complex64])
        self.rs = float(symbol_rate)
        self.core = FrameRx(loop_bw=loop_bw, thr_search=thr_search, pilot_weight=pilot_weight,
                            check_payload=check_payload, seed=seed)
        self.pending = np.zeros(0, dtype=np.complex64)
        self.print_every = int(print_every)
        self.last_print = 0

    def forecast(self, noutput_items, ninputs):
        return [1] * ninputs

    def general_work(self, input_items, output_items):
        out = output_items[0]
        if len(self.pending) < 4 * max(len(out), 1):
            x = input_items[0]
            self.consume(0, len(x))
            self.pending = np.concatenate([self.pending, self.core.push(x).astype(np.complex64)])
            c = self.core
            if self.print_every and c.frames - self.last_print >= self.print_every:
                self.last_print = c.frames
                msg = "ZC sync: locked=%s frames=%d cfo=%.1f Hz evm=%.1f dB" % (c.locked, c.frames, self.get_cfo_hz(), c.evm_db)
                if c.check and c.sym_cnt:
                    msg += " SER=%.2e (%d/%d)" % (c.sym_err / c.sym_cnt, c.sym_err, c.sym_cnt)
                print(msg, flush=True)
        n = min(len(self.pending), len(out))
        out[:n] = self.pending[:n]
        self.pending = self.pending[n:]
        return n

    def get_locked(self):
        return 1.0 if self.core.locked else 0.0

    def get_cfo_hz(self):
        return float(self.core.omega / (2 * math.pi) * self.rs)

    def get_evm_db(self):
        return float(self.core.evm_db)

    def get_ser(self):
        c = self.core
        return float(c.sym_err / c.sym_cnt) if c.sym_cnt else 0.0
