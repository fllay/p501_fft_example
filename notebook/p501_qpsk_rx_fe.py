"""Python side of the FPGA QPSK receiver with the FLL AND the 4th-power frequency estimator (rtl/qpsk_rx_fe.v, overlay p501_qpsk_trx_fe, ID 0xDD520003).
Everything of p501_qpsk_rx_fll.P501QpskRxFll works (acquire_fll, freeze_fll, ...); this adds the estimator.

    from p501_qpsk_rx_fe import P501QpskRxFe
    rx = P501QpskRxFe(ol.qpsk_rx)
    e = rx.measure(n=2048)          # one window of 2048 symbols (2.1 ms): {f_hz, quality, count, acc_re, acc_im, acc_abs}; f_hz is the offset of the signal AFTER the FLL (raw when the FLL is held at 0)
    e = rx.estimate_freq(n=2048, windows=8)       # several windows: mean, std, and total offset (= f - FLL frequency, the offset of the signal at the antenna)
    r = rx.acquire_fe()             # lock from cold with no hint: estimate once, load the derotator (apply="fll") or W0 (apply="w0"), then narrow loops
The estimator is the differential 4th-power one: d = m x conj(m_prev), psi = 4 arg d, ACC = sum exp(j psi) over N symbols, f = atan2(ACC_IM, ACC_RE) / (8 pi) x 960 kHz (|f| < 120 kHz)."""
import time
import numpy as np
from p501_qpsk_rx import REG, _signed, SYMBOL_RATE
from p501_qpsk_rx_fll import P501QpskRxFll, FS

REG.update(FE_CTRL=0x74, FE_N=0x78, FE_STATUS=0x7C, FE_CNT=0x80, ACC_RE=0x84, ACC_IM=0x88, ACC_ABS=0x8C, FE_FIRST=0x90)


class P501QpskRxFe(P501QpskRxFll):
    EXPECTED_ID = 0xDD520003

    def measure(self, n=2048, timeout_s=1.0):
        """One window of n symbols (n / 960 kHz seconds; 1 .. 65535). The receiver must be running; the symbols are those after the AGC, before the Costas loop."""
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
        return dict(f_hz=float(theta / (8 * np.pi) * SYMBOL_RATE), quality=float(np.hypot(re, im) / (max(cnt, 1) * 32767.0)), count=cnt, acc_re=re, acc_im=im, acc_abs=ab, first=first,
                    w0=int(round(theta / (8 * np.pi) * 2 ** 32)) & 0xFFFFFFFF)

    def estimate_freq(self, n=2048, windows=8):
        """Mean and std of the estimate over several windows (the mean of the unit vectors, so a wrap at +-120 kHz does not bite), and the total offset at the antenna: f - FLL frequency."""
        fs, qs = [], []
        for _ in range(windows):
            e = self.measure(n); fs.append(e["f_hz"]); qs.append(e["quality"])
        th = np.array(fs) / SYMBOL_RATE * 8 * np.pi
        f = float(np.angle(np.mean(np.exp(1j * th))) / (8 * np.pi) * SYMBOL_RATE)
        fll = _signed(self.ip.read(REG["FLL_FREQ"])) / 2 ** 32 * FS
        return dict(f_hz=f, std_hz=float(np.std(fs)), quality=float(np.mean(qs)), fll_hz=fll, total_hz=f - fll, windows=windows, n=n)

    def acquire_fe(self, n=1024, settle_symbols=2000, acq_div=100, track_div=400, apply="fll", check_s=0.05, tries=3):
        """Lock from cold with no hint. The receiver starts with the FLL held at 0 Hz and wide loops; after settle_symbols (the AGC and the timing loop have to converge first: 1000 symbols give an error of 70 Hz rms at 9.5 kHz, 2000 are used)
        the estimator measures the offset in one window of n symbols. apply="fll": load the derotator with minus that offset, live, and keep the FLL loop off (the Costas loop only has to follow
        the small rest); apply="w0": restart with W0 = the estimate. Then both loops are narrowed to 2 pi / track_div. Returns {locked, tries, seconds, f_hz, quality, costas_hz, total_hz}."""
        t0 = time.time()
        for i in range(tries):
            self.stop(); time.sleep(0.05)
            self.configure(timing_bw=2 * np.pi / acq_div, phase_bw=2 * np.pi / acq_div, init_freq_hz=0.0)
            self.ip.write(REG["FLL_F0"], 0); self.fll_enable(False)
            if apply != "w0":
                self.ip.write(REG["CA"], 0); self.ip.write(REG["CB"], 0)        # the Costas loop waits at 0 Hz during the measurement: it would pull in to the offset by itself, and the derotator step that follows would then unlock it
            self.start(); time.sleep(settle_symbols / SYMBOL_RATE)
            e = self.measure(n)
            if apply == "w0":
                self.stop(); self.configure(timing_bw=2 * np.pi / acq_div, phase_bw=2 * np.pi / acq_div, init_freq_hz=e["f_hz"]); self.start()
            else:
                self.fll_load(-e["f_hz"]); self.set_loops(2 * np.pi / acq_div, 2 * np.pi / acq_div)       # the derotator now removes the offset; the Costas loop starts from 0 Hz
            time.sleep(0.05)
            if track_div:
                self.set_loops(2 * np.pi / track_div, 2 * np.pi / track_div)
            time.sleep(0.1)
            if not self.locked(check_s):
                continue
            fl, co = self.fll_hz(), self._omega_hz()
            return dict(locked=True, tries=i + 1, seconds=time.time() - t0, f_hz=e["f_hz"], quality=e["quality"], costas_hz=co, fll_hz=fl, total_hz=co - fl)
        return dict(locked=False, tries=tries, seconds=time.time() - t0, f_hz=e["f_hz"], quality=e["quality"], costas_hz=self._omega_hz(), fll_hz=self.fll_hz(), total_hz=float("nan"))

    def timed_lock(self, method, acq_div=100, settle_symbols=2000, n=1024, window_s=0.3):
        """Cold start with the mismatch counter polled without a pause; the time of its last change is the time to lock. method: "costas" (wide Costas loop only, FLL held at 0), "fll" (FLL + Costas,
        gain 0.002), "fe-fll" (settle, one window, derotator loaded with minus the estimate, Costas held at 0 until then), "fe-w0" (the same, then a restart with W0 = the estimate).
        Returns {ms, mismatches, locked, estimate_hz, fll_hz, costas_hz}."""
        self.stop(); time.sleep(0.05)
        self.configure(timing_bw=2 * np.pi / acq_div, phase_bw=2 * np.pi / acq_div, init_freq_hz=0.0)
        self.ip.write(REG["FLL_F0"], 0); self.set_fll(0.002); self.fll_enable(method == "fll")
        if method == "fe-fll":
            self.ip.write(REG["CA"], 0); self.ip.write(REG["CB"], 0)
        st = [0, 0.0, 0.0]

        def poll(seconds):
            end = time.time() + seconds
            while time.time() < end:
                m = self.ip.read(REG["MISMATCH"])
                if m != st[0]: st[0], st[1] = m, time.time() - st[2]
        self.start(); st[2] = time.time(); est = None
        if method in ("fe-fll", "fe-w0"):
            poll(settle_symbols / SYMBOL_RATE)
            self.ip.write(REG["FE_N"], int(n)); self.ip.write(REG["FE_CTRL"], 0); self.ip.write(REG["FE_CTRL"], 1)
            t0 = time.time()
            while not (self.ip.read(REG["FE_STATUS"]) & 2) and time.time() - t0 < 1.0:
                m = self.ip.read(REG["MISMATCH"])
                if m != st[0]: st[0], st[1] = m, time.time() - st[2]
            re, im = _signed(self.ip.read(REG["ACC_RE"])), _signed(self.ip.read(REG["ACC_IM"]))
            est = float(np.arctan2(im, re) / (8 * np.pi) * SYMBOL_RATE)
            if method == "fe-fll":
                self.fll_load(-est); self.set_loops(2 * np.pi / acq_div, 2 * np.pi / acq_div)
            else:
                self.stop(); self.configure(timing_bw=2 * np.pi / acq_div, phase_bw=2 * np.pi / acq_div, init_freq_hz=est); self.start()
        poll(window_s)
        ok = self.locked(0.05)
        return dict(ms=st[1] * 1e3, mismatches=st[0], locked=bool(ok), estimate_hz=est, fll_hz=self.fll_hz(), costas_hz=self._omega_hz())

    def handover(self, n=4096, windows=3):
        """Take the residual offset the estimator sees (after the derotator) out of the derotator: new FLL frequency = current - residual, loop off. The Costas loop, which has been following the residual,
        then has about nothing left to do. Returns {residual_hz, new_fll_hz, quality}."""
        es = [self.measure(n) for _ in range(windows)]
        th = np.array([e["f_hz"] for e in es]) / SYMBOL_RATE * 8 * np.pi
        f = float(np.angle(np.mean(np.exp(1j * th))) / (8 * np.pi) * SYMBOL_RATE)
        cur = _signed(self.ip.read(REG["FLL_FREQ"])) / 2 ** 32 * FS
        self.fll_load(cur - f); self.fll_enable(False)
        return dict(residual_hz=f, new_fll_hz=cur - f, quality=float(np.mean([e["quality"] for e in es])))

