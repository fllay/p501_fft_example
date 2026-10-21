"""Python side of the FPGA QPSK receiver of chain 3: polyphase matched filter -> 4th-power estimator -> Costas loop (rtl/qpsk_rx_4p.v, overlay p501_qpsk_trx_4p, ID 0xDD520004).
There is no FLL in this overlay and no software in the loop: the FPGA accumulates exp(j 4 arg(m_n conj(m_n-1))) over a window of N symbols of the polyphase output, takes atan2 with a CORDIC
and writes the result into the Costas loop's frequency register (OMEGA). Python only enables it and reads what happened.

    from p501_qpsk_rx_4p import P501QpskRx4p
    rx = P501QpskRx4p(ol.qpsk_rx)
    r = rx.acquire_4p()          # cold start, no hint: wide loops, the estimator loads OMEGA once, then narrow loops. {locked, seconds, costas_hz, loads, west_hz}
    rx.auto_status()             # loads, windows, last frequency loaded, last window's frequency
    e = rx.measure(2048)         # one manual window (for measurements): {f_hz, quality, count, acc_re, acc_im, acc_abs}
Everything of p501_qpsk_rx.P501QpskRx works as before (configure, set_loops, start, stats, capture, offsets, acquire)."""
import time
import numpy as np
from p501_qpsk_rx import P501QpskRx, REG, _signed, SYMBOL_RATE

REG.update(FE_CTRL=0x74, FE_N=0x78, FE_STATUS=0x7C, FE_CNT=0x80, ACC_RE=0x84, ACC_IM=0x88, ACC_ABS=0x8C, FE_FIRST=0x90, FE_AUTO=0x94, FE_WEST=0x98, FE_NLOAD=0x9C, FE_QMIN=0xA0, FE_NWIN=0xA4, FE_WLAST=0xA8)
CORDIC_GAIN = 1.64676


def qmin_reg(q):
    """Gate register for a minimum quality q (mean resultant length, 0 .. 1): the CORDIC magnitude must be at least cnt x QMIN."""
    return int(round(q * 32767 * CORDIC_GAIN))


class P501QpskRx4p(P501QpskRx):
    EXPECTED_ID = 0xDD520004

    # ---- the autonomous estimator ----
    def set_auto(self, n=1024, q_min=0.3):
        """Window length (symbols, 1 .. 65535) and the quality gate for the autonomous estimator (it is not enabled yet)."""
        self.ip.write(REG["FE_AUTO"], 0); self.ip.write(REG["FE_N"], int(n)); self.ip.write(REG["FE_QMIN"], qmin_reg(q_min))

    def enable_auto(self, continuous=False):
        """Enable: the first window starts with the next symbol. Once: windows repeat until one passes the gate, that one loads OMEGA, then the Costas loop tracks alone. Continuous: every passing window loads OMEGA.
        Write 0 and 1 again to start over."""
        self.ip.write(REG["FE_AUTO"], 0); self.ip.write(REG["FE_AUTO"], 3 if continuous else 1)

    def disable_auto(self):
        self.ip.write(REG["FE_AUTO"], 0)

    def auto_status(self):
        r = lambda k: self.ip.read(REG[k])
        return dict(loads=r("FE_NLOAD"), windows=r("FE_NWIN"), west_hz=_signed(r("FE_WEST")) / 2 ** 32 * SYMBOL_RATE, wlast_hz=_signed(r("FE_WLAST")) / 2 ** 32 * SYMBOL_RATE,
                    auto=r("FE_AUTO"), n=r("FE_N"), qmin=r("FE_QMIN"))

    def acquire_4p(self, n=1024, q_min=0.3, continuous=False, acq_div=100, track_div=400, settle_symbols=2000, check_s=0.05, tries=3):
        """Cold start with no hint. The loops start wide (2 pi / acq_div); after settle_symbols (the AGC and the timing loop converge first) the autonomous estimator is enabled; once it has loaded OMEGA
        (continuous: keeps loading), both loops are narrowed live to 2 pi / track_div and the lock is checked. Returns {locked, tries, seconds, costas_hz, loads, windows, west_hz}."""
        t0 = time.time()
        for i in range(tries):
            self.disable_auto(); self.stop(); time.sleep(0.05)
            self.configure(timing_bw=2 * np.pi / acq_div, phase_bw=2 * np.pi / acq_div, init_freq_hz=0.0)
            self.set_auto(n, q_min)
            self.start(); time.sleep(settle_symbols / SYMBOL_RATE)
            self.enable_auto(continuous)
            t1 = time.time()
            while self.ip.read(REG["FE_NLOAD"]) == 0 and time.time() - t1 < 0.5:
                time.sleep(0.0005)
            time.sleep(0.08)
            f1 = self._omega_hz(); time.sleep(0.03); f2 = self._omega_hz()
            if abs(f2 - f1) > 1500 or not self.locked(check_s):
                continue
            if track_div:
                self.set_loops(2 * np.pi / track_div, 2 * np.pi / track_div)
            time.sleep(0.1)
            if not self.locked(0.1):
                continue
            a = self.auto_status()
            return dict(locked=True, tries=i + 1, seconds=time.time() - t0, costas_hz=self._omega_hz(), loads=a["loads"], windows=a["windows"], west_hz=a["west_hz"])
        a = self.auto_status()
        return dict(locked=False, tries=tries, seconds=time.time() - t0, costas_hz=self._omega_hz(), loads=a["loads"], windows=a["windows"], west_hz=a["west_hz"])

    def timed_lock(self, mode="once", n=1024, q_min=0.3, acq_div=100, settle_symbols=2000, window_s=0.3):
        """Cold start with the mismatch counter polled without a pause: the time of its last change is the time to lock. mode: "costas" (autonomous estimator off: the Costas loop alone, for reference),
        "once" or "continuous". Returns {ms, mismatches, locked, costas_hz, loads}."""
        self.disable_auto(); self.stop(); time.sleep(0.05)
        self.configure(timing_bw=2 * np.pi / acq_div, phase_bw=2 * np.pi / acq_div, init_freq_hz=0.0)
        self.set_auto(n, q_min)
        st = [0, 0.0, 0.0]

        def poll(seconds):
            end = time.time() + seconds
            while time.time() < end:
                m = self.ip.read(REG["MISMATCH"])
                if m != st[0]: st[0], st[1] = m, time.time() - st[2]
        self.start(); st[2] = time.time()
        if mode != "costas":
            poll(settle_symbols / SYMBOL_RATE); self.enable_auto(mode == "continuous")
        poll(window_s)
        ok = self.locked(0.05)
        return dict(ms=st[1] * 1e3, mismatches=st[0], locked=bool(ok), costas_hz=self._omega_hz(), loads=self.ip.read(REG["FE_NLOAD"]))

    # ---- one manual window, for measurements ----
    def measure(self, n=2048, timeout_s=1.0):
        """One manual window of n symbols (n / 960 kHz seconds). The receiver must be running."""
        w = self.ip.write
        w(REG["FE_N"], int(n)); w(REG["FE_CTRL"], 0); w(REG["FE_CTRL"], 1)
        t0 = time.time()
        while not (self.ip.read(REG["FE_STATUS"]) & 2):
            if time.time() - t0 > timeout_s:
                raise TimeoutError("estimator window did not finish: is the receiver running (rx.start())?")
            time.sleep(0.0005)
        cnt, re, im, ab, first = [self.ip.read(REG[k]) for k in ("FE_CNT", "ACC_RE", "ACC_IM", "ACC_ABS", "FE_FIRST")]
        re, im = _signed(re), _signed(im)
        theta = np.arctan2(im, re)
        return dict(f_hz=float(theta / (8 * np.pi) * SYMBOL_RATE), quality=float(np.hypot(re, im) / (max(cnt, 1) * 32767.0)), count=cnt, acc_re=re, acc_im=im, acc_abs=ab, first=first)
