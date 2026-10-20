"""Python side of the FPGA QPSK receiver WITH THE BAND-EDGE FLL (rtl/qpsk_rx_fll.v, overlay p501_qpsk_trx_fll): the chain of the GNU Radio flowgraph, FLL -> polyphase matched filter / timing loop -> Costas loop.
Everything of p501_qpsk_rx.P501QpskRx works as before (configure, set_loops, start, stats, capture, offsets, acquire); this adds the FLL registers and an acquire that needs no frequency hints.

    from p501_qpsk_rx_fll import P501QpskRxFll
    rx = P501QpskRxFll(ol.qpsk_rx)
    r = rx.acquire_fll()          # FLL + Costas wide, then both narrow: locks without a frequency hint. r = {locked, seconds, fll_hz, costas_hz, total_hz}
    rx.total_offset_hz()          # carrier offset of the received signal: Costas frequency minus the FLL's derotation frequency
    rx.fll_status()               # FLL frequency (Hz), last error, blocks measured, late count (must stay 0)
    rx.set_fll(0.0003)            # FLL integral gain in rad per symbol (per unit of the normalised error), live
Sign convention: the FLL derotates (y = x e^{+j phi}), so its frequency is the NEGATIVE of the offset it removes: total offset = Costas frequency - FLL frequency."""
import time
import numpy as np
from p501_qpsk_rx import P501QpskRx, REG, _signed, SYMBOL_RATE

REG.update(FLL_CTRL=0x54, FLL_GI=0x58, FLL_GP=0x5C, FLL_F0=0x60, FLL_FREQ=0x64, FLL_ERR=0x68, FLL_NBLK=0x6C, FLL_LATE=0x70)
FS = 3.84e6


def fll_gains(gi_rad, gp_rad=0.0):
    """Register values GI, GP from loop gains in rad per symbol (the normalised band-edge error is +-1 at full scale); the same as qpsk_fll_fixed.gains()."""
    return int(round(gi_rad / (2 * np.pi) * 2 ** 32)), int(round(gp_rad / (2 * np.pi) * 2 ** 32))


class P501QpskRxFll(P501QpskRx):
    EXPECTED_ID = 0xDD520002

    def set_fll(self, gi_rad, gp_rad=0.0):
        """FLL gains, live. gi 0.0005-0.002 acquires fast and is noisy (kHz jitter), 0.0001-0.0003 tracks quietly."""
        gi, gp = fll_gains(gi_rad, gp_rad)
        self.ip.write(REG["FLL_GI"], gi); self.ip.write(REG["FLL_GP"], gp)

    def fll_enable(self, on=True):
        """0 holds the FLL's frequency (it still derotates); 1 lets the loop run. Written without disturbing the load bit."""
        self.ip.write(REG["FLL_CTRL"], 1 if on else 0)

    def fll_load(self, f_hz):
        """Load the FLL frequency now (a live handover): f_hz is the derotation frequency, i.e. minus the offset to remove."""
        self.ip.write(REG["FLL_F0"], int(round(f_hz / FS * 2 ** 32)) & 0xFFFFFFFF)
        c = self.ip.read(REG["FLL_CTRL"]) & 1
        self.ip.write(REG["FLL_CTRL"], c | 2); self.ip.write(REG["FLL_CTRL"], c)

    def fll_hz(self, n=10, dt=0.002):
        v = []
        for _ in range(n):
            v.append(_signed(self.ip.read(REG["FLL_FREQ"])) / 2 ** 32 * FS); time.sleep(dt)
        return float(np.mean(v))

    def costas_hz(self, n=10, dt=0.002):
        return self._omega_hz(n, dt)

    def total_offset_hz(self, n=50, dt=0.004):
        """The received signal's carrier offset: Costas frequency minus FLL frequency (both averaged over n readings)."""
        fl, co = [], []
        for _ in range(n):
            fl.append(_signed(self.ip.read(REG["FLL_FREQ"])) / 2 ** 32 * FS); co.append(_signed(self.ip.read(REG["OMEGA"])) / 2 ** 32 * SYMBOL_RATE); time.sleep(dt)
        return float(np.mean(co) - np.mean(fl))

    def fll_status(self):
        r = lambda k: self.ip.read(REG[k])
        return dict(fll_hz=_signed(r("FLL_FREQ")) / 2 ** 32 * FS, err=_signed(r("FLL_ERR"), 16) / 32768.0, blocks=r("FLL_NBLK"), late=r("FLL_LATE"),
                    enabled=bool(r("FLL_CTRL") & 1))

    def stats(self):
        d = super().stats()
        d["carrier_offset_hz"] = self.total_offset_hz(n=10, dt=0.002)           # Costas frequency minus FLL frequency: the offset of the signal, not just the Costas part
        d.update({"costas_hz": self._omega_hz(n=5, dt=0.001)}); d.update(self.fll_status())
        return d

    def acquire_fll(self, wide_fll=0.002, narrow_fll=0.0003, acq_div=100, track_div=400, settle_s=0.05, check_s=0.05, f0_hz=0.0, tries=3):
        """Lock without a frequency hint. The FLL has a pull-in range of about +-FS/NTAPS-ish tens of kHz, so the wide FLL (gain wide_fll) and the wide Costas loop (2 pi / acq_div)
        start together at zero offset; after settle_s the FLL has taken out most of the offset and the Costas loop only has to follow the rest. Then both loops are narrowed live
        (FLL narrow_fll, Costas 2 pi / track_div) and the lock is checked. Returns {locked, tries, seconds, fll_hz, costas_hz, total_hz}."""
        t0 = time.time()
        for i in range(tries):
            self.stop()
            self.configure(timing_bw=2 * np.pi / acq_div, phase_bw=2 * np.pi / acq_div, init_freq_hz=0.0)
            self.ip.write(REG["FLL_F0"], int(round(f0_hz / FS * 2 ** 32)) & 0xFFFFFFFF)
            self.set_fll(wide_fll); self.ip.write(REG["FLL_CTRL"], 1)
            self.start(); time.sleep(settle_s)
            f1 = self._omega_hz(); time.sleep(0.04); f2 = self._omega_hz()
            if abs(f2 - f1) > 1500 or not self.locked(check_s):
                continue
            self.set_fll(narrow_fll)
            if track_div:
                self.set_loops(2 * np.pi / track_div, 2 * np.pi / track_div)
            time.sleep(0.1)
            if not self.locked(0.1):
                continue
            fl, co = self.fll_hz(), self._omega_hz()
            return dict(locked=True, tries=i + 1, seconds=time.time() - t0, fll_hz=fl, costas_hz=co, total_hz=co - fl)
        return dict(locked=False, tries=tries, seconds=time.time() - t0, fll_hz=self.fll_hz(), costas_hz=self._omega_hz(), total_hz=float("nan"))
