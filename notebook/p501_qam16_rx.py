"""Python side of the FPGA 16-QAM receiver with the Zadoff-Chu frame synchroniser and the band-edge FLL (rtl/qam16_rx.v, overlay p501_qam16_trx) and of its frame transmitter (rtl/qam16_tx_fr.v).

    from p501_qam16_rx import P501Qam16Rx, P501Qam16Tx
    tx = P501Qam16Tx(ol.qpsk_regs, 3_840_000); rx = P501Qam16Rx(ol.qam16_rx)
    tx.start(amp=0.25)                        # frames of 967 symbols (CP 8 | ZC word 63 | 14 x (63 16-QAM + 1 pilot)), PRBS-15 payload restarted in every frame
    rx.acquire()                              # configure, FLL acquiring then tracking, start, wait for the lock
    rx.stats()                                # frames, symbol / bit errors, EVM, lock state, gain, clock offset, FLL ...
    z = rx.capture()                          # 1024 soft symbols (complex, unit RMS 1.0) for a constellation plot

The numbers behind the register values are in tutorial/qam16/qam16_rx_fixed.py (regs16): unit RMS = 12953 counts, 16-QAM levels +-4096 / +-12288, thresholds 0 / +-8192."""
import time
import numpy as np

REG = dict(ID=0x00, CTRL=0x04, TA=0x08, TB=0x0C, CA=0x10, CB=0x14, MU=0x18, PREF=0x1C, G0=0x20, MAXR=0x28, TAA=0x2C, TBA=0x30, MUA=0x34, ACQ=0x38, PCFG=0x3C,
           THR=0x40, TOL=0x44, WIN=0x48, MISSMAX=0x4C, STATUS=0x50, SYMBOLS=0x54, FRAMES=0x58, SYM_ERR=0x5C, BIT_ERR=0x60, SYM_CNT=0x64, BAD=0x68,
           EVM_LO=0x6C, EVM_HI=0x70, EVM_REF=0x74, FRAME_ERR=0x78, GAIN=0x7C, RATE=0x80, OMEGA=0x84, WRCNT=0x88, OVERRUNS=0x8C,
           N_PEAK=0x90, N_LOCK=0x94, N_HIT=0x98, N_MISS=0x9C, N_LOST=0xA0, SY_LATE=0xA4, EV_OVER=0xA8, EV_LATE=0xAC, LOCK_W=0xB0, POS=0xB4, NSW=0xB8,
           FLL_CTRL=0xBC, FLL_GI=0xC0, FLL_GP=0xC4, FLL_F0=0xC8, FLL_FREQ=0xCC, FLL_ERR=0xD0, FLL_NBLK=0xD4, FLL_LATE=0xD8)
CAPTURE = 0x1000
NF, SPS, SYMBOL_RATE, FS = 16, 4, 960e3, 3.84e6
R_UNIT, LV = 12953, 4096
EXPECTED_ID = 0xDD520006


def _signed(v, bits=32):
    return v - (1 << bits) if v & (1 << (bits - 1)) else v


def loop_gains(bw, damping=np.sqrt(2) / 2):
    den = 1 + 2 * damping * bw + bw * bw
    return 4 * damping * bw / den, 4 * bw * bw / den


def regs16(timing_bw=2 * np.pi / 400, loop_bw=0.02, mu=136, g0=1024, max_rate=0.05, timing_bw_acq=2 * np.pi / 100, mu_acq=544, acq_symbols=0, nsw=4,
           aided=True, pilot_weight=3, thr_s=154, thr_l=115, tol=3, window=4, missmax=3):
    """the register values (the same numbers as qam16_rx_fixed.regs16 and the testbench)"""
    ta, tb = loop_gains(timing_bw); al, be = loop_gains(loop_bw); taa, tba = loop_gains(timing_bw_acq)
    return dict(TA=int(round(ta * 2 ** 24)), TB=int(round(tb * 2 ** 24)), CA=int(round(al * 2 ** 40 / (2 * np.pi * 640))), CB=int(round(be * 2 ** 40 / (2 * np.pi * 640))), MU=int(mu),
                PREF=(R_UNIT * R_UNIT) >> 8, G0=int(g0), MAXR=int(round(max_rate * NF * 2 ** 16)), TAA=int(round(taa * 2 ** 24)), TBA=int(round(tba * 2 ** 24)), MUA=int(mu_acq), ACQ=int(acq_symbols),
                NSW=int(nsw), PCFG=(1 if aided else 0) | ((3 * int(pilot_weight)) << 8), THR=(int(thr_l) << 8) | int(thr_s), TOL=int(tol), WIN=int(window), MISSMAX=int(missmax))


def fll_gains(gi_rad, gp_rad=0.0):
    return int(round(gi_rad / (2 * np.pi) * 2 ** 32)), int(round(gp_rad / (2 * np.pi) * 2 ** 32))


class P501Qam16Tx:
    """the frame transmitter shares the register block of the DDS / QPSK transmitter (enable, amplitude)"""
    def __init__(self, ip, fs_hz=3_840_000):
        from p501_dds import P501Dds
        self._dds = P501Dds(ip, fs_hz)

    @property
    def enabled(self):
        return self._dds.enabled

    @property
    def amp(self):
        return self._dds.amp

    def set(self, amp=None, enable=None, timeout_s=1.0):
        self._dds.set(amp=amp, enable=enable, timeout_s=timeout_s)

    def start(self, amp=0.25, timeout_s=1.0):
        self._dds.off(timeout_s=timeout_s); self._dds.set(amp=amp, enable=True, timeout_s=timeout_s)

    def stop(self, timeout_s=1.0):
        self._dds.off(timeout_s=timeout_s)

    off = stop


class P501Qam16Rx:
    def __init__(self, ip):
        self.ip = ip
        if self.ip.read(REG["ID"]) != EXPECTED_ID:
            raise RuntimeError("not the 16-QAM receiver (ID 0x%08X)" % self.ip.read(REG["ID"]))

    def r(self, name):
        return self.ip.read(REG[name])

    # ---------------------------------------------------------------- configuration
    def configure(self, **kw):
        """write the loop, AGC, synchroniser and PLL registers (regs16 arguments: loop_bw, timing_bw, mu, nsw, aided, pilot_weight, thr_s, thr_l, ...)"""
        for name, v in regs16(**kw).items():
            self.ip.write(REG[name], int(v) & 0xFFFFFFFF)

    def set_fll(self, gi_rad, gp_rad=0.0):
        """FLL gains, live. 0.002 acquires fast (kHz jitter), 0.0003 tracks quietly."""
        gi, gp = fll_gains(gi_rad, gp_rad)
        self.ip.write(REG["FLL_GI"], gi); self.ip.write(REG["FLL_GP"], gp)

    def fll_enable(self, on=True):
        self.ip.write(REG["FLL_CTRL"], 1 if on else 0)

    def fll_load(self, f_hz):
        """load the FLL frequency now: f_hz is the derotation frequency, i.e. minus the offset to remove"""
        self.ip.write(REG["FLL_F0"], int(round(f_hz / FS * 2 ** 32)) & 0xFFFFFFFF)
        c = self.ip.read(REG["FLL_CTRL"]) & 1
        self.ip.write(REG["FLL_CTRL"], c | 2); self.ip.write(REG["FLL_CTRL"], c)

    def set_pll(self, loop_bw=0.02, aided=True, pilot_weight=3):
        """the carrier PLL, live: loop bandwidth (rad per symbol; 0.015 to 0.03 are equivalent with the quiet FLL, 0.04 and above are worse), the known CP / word symbols in the loop, the pilot weight (1, 3, 5)"""
        r = regs16(loop_bw=loop_bw, aided=aided, pilot_weight=pilot_weight)
        for k in ("CA", "CB", "PCFG"): self.ip.write(REG[k], int(r[k]) & 0xFFFFFFFF)

    def set_timing(self, timing_bw=2 * np.pi / 400):
        r = regs16(timing_bw=timing_bw)
        for k in ("TA", "TB"): self.ip.write(REG[k], int(r[k]) & 0xFFFFFFFF)

    def set_sync(self, thr_s=154, thr_l=115, tol=3, window=4, missmax=3, nsw=4):
        r = regs16(thr_s=thr_s, thr_l=thr_l, tol=tol, window=window, missmax=missmax, nsw=nsw)
        for k in ("THR", "TOL", "WIN", "MISSMAX", "NSW"): self.ip.write(REG[k], int(r[k]) & 0xFFFFFFFF)

    def hold_fll(self, n=50, dt=0.002):
        """load the FLL with its mean frequency over n readings and stop its loop (a constant derotation: no more tracking noise); returns the frequency in Hz"""
        f = self.fll_hz(n=n, dt=dt); self.fll_load(f); self.fll_enable(False)
        return f

    def start(self):
        self.ip.write(REG["CTRL"], 1)

    def stop(self):
        self.ip.write(REG["CTRL"], 0)

    # ---------------------------------------------------------------- measurements
    def fll_hz(self, n=10, dt=0.002):
        v = []
        for _ in range(n):
            v.append(_signed(self.r("FLL_FREQ")) / 2 ** 32 * FS); time.sleep(dt)
        return float(np.mean(v))

    def locked(self):
        return bool(self.r("STATUS") & 8)

    def wait_lock(self, timeout_s=1.0, frames=2):
        """True when the synchroniser is locked and the engine runs; `frames` payloads must have been completed since the call"""
        t0 = time.time(); f0 = self.r("FRAMES")
        while time.time() - t0 < timeout_s:
            if self.locked() and (self.r("STATUS") & 16) and self.r("FRAMES") - f0 >= frames:
                return True
            time.sleep(0.002)
        return False

    def stats(self):
        r = self.r
        sym_err, sym_cnt, bit_err = r("SYM_ERR"), r("SYM_CNT"), r("BIT_ERR")
        evm_err = (r("EVM_HI") << 32) | r("EVM_LO"); evm_ref = r("EVM_REF")
        st = r("STATUS")
        return dict(running=bool(st & 1), overrun=bool(st & 4), locked=bool(st & 8), run_active=bool(st & 16), symbols=r("SYMBOLS"), frames=r("FRAMES"), bad_frames=r("BAD"),
                    sym_err=sym_err, sym_cnt=sym_cnt, ser=(sym_err / sym_cnt if sym_cnt else float("nan")), bit_err=bit_err, ber=(bit_err / (4 * sym_cnt) if sym_cnt else float("nan")),
                    evm_db=(10 * np.log10(evm_err / (evm_ref * LV * LV)) if evm_ref and evm_err else float("nan")), frame_err=r("FRAME_ERR"),
                    agc_gain=r("GAIN") / 1024.0, clock_offset_ppm=-_signed(r("RATE")) / 2 ** 16 / NF / SPS * 1e6, pll_hz=_signed(r("OMEGA")) / 2 ** 32 * SYMBOL_RATE,
                    lock_w_hz=_signed(r("LOCK_W")) / 2 ** 32 * SYMBOL_RATE, fll_hz=_signed(r("FLL_FREQ")) / 2 ** 32 * FS,
                    peaks=r("N_PEAK"), locks=r("N_LOCK"), hits=r("N_HIT"), misses=r("N_MISS"), lost=r("N_LOST"), sy_late=r("SY_LATE"), ev_over=r("EV_OVER"), ev_late=r("EV_LATE"),
                    fll_late=r("FLL_LATE"), engine_overruns=r("OVERRUNS"))

    def capture(self, timeout_s=2.0):
        """1024 soft data symbols after the PLL (complex, unit RMS 1.0)"""
        self.ip.write(REG["CTRL"], 1); self.ip.write(REG["CTRL"], 3)
        t0 = time.time()
        while not (self.r("STATUS") & 2):
            if time.time() - t0 > timeout_s: raise TimeoutError("capture did not complete: is the receiver locked on frames?")
            time.sleep(0.005)
        w = np.array([self.ip.read(CAPTURE + 4 * i) for i in range(1024)], dtype=np.uint32)
        self.ip.write(REG["CTRL"], 1)
        zi = (w & 0xFFFF).astype(np.uint16).view(np.int16).astype(float); zq = (w >> 16).astype(np.uint16).view(np.int16).astype(float)
        return (zi + 1j * zq) / R_UNIT

    def acquire(self, acq_gi=0.002, trk_gi=0.0001, fll_acq_s=0.02, timeout_s=1.5, hold=False, **kw):
        """Start from cold: registers, the FLL with its acquiring gain for fll_acq_s seconds, then its tracking gain; wait for the lock. Returns a dict {locked, seconds, fll_hz}.
        trk_gi: the FLL's tracking gain. 0.0001 (the default) keeps its frequency noise low enough for the 16-QAM PLL down to about 12 dB SNR; 0.0003 jitters by 1 to 4 kHz and loses the carrier below about 14 dB
        (tutorial/qam16/results_pll_lowsnr.txt). hold=True then loads the FLL with its mean frequency and stops its loop (a constant derotation; the PLL tracks the rest, +-4 kHz)."""
        t0 = time.time()
        self.stop(); self.configure(**kw)
        self.ip.write(REG["FLL_F0"], 0); self.fll_enable(True); self.set_fll(acq_gi)
        self.start(); time.sleep(fll_acq_s); self.set_fll(trk_gi)
        ok = self.wait_lock(timeout_s)
        if hold and ok:
            time.sleep(0.05); f = self.fll_hz(n=50, dt=0.002); self.fll_load(f); self.fll_enable(False)
        return dict(locked=ok, seconds=time.time() - t0, fll_hz=self.fll_hz())
