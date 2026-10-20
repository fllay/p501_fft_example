"""Python side of the FPGA QPSK receiver (rtl/qpsk_rx.v, chapter 4d). The receiver works on its own; Python sets the loop gains, starts it and reads what it measured.

    from p501_qpsk_rx import P501QpskRx
    rx = P501QpskRx(ol.qpsk_rx)
    rx.configure(timing_bw=2*np.pi/400, phase_bw=2*np.pi/400)       # loop bandwidths (rad per symbol) -> the gain registers
    rx.start()
    rx.set_loops(2*np.pi/1600, 2*np.pi/1600)                          # e.g. after 30 ms: narrower loops, live
    s = rx.stats()      # symbols, checked bits, PRBS mismatches, BER estimate, carrier offset (Hz), clock offset (ppm), AGC gain
    z = rx.capture()    # 1024 soft symbols after the Costas loop (complex numpy array) for a constellation plot
    rx.stop()

    rx.acquire(track_div=400)    # robust start: wide loops with initial-frequency hints until the receiver is locked, then the narrow tracking loops

The bit checker is the self-synchronising PRBS-15 checker of the FPGA: it needs the PRBS-15 transmitter (chapter 4c, or GNU Radio with the same pattern)."""
import time
import numpy as np

REG = dict(ID=0x00, CTRL=0x04, TA=0x08, TB=0x0C, CA=0x10, CB=0x14, MU=0x18, REF=0x1C, G0=0x20, W0=0x24, MAXR=0x28,
           STATUS=0x30, SYMBOLS=0x34, BITS=0x38, MISMATCH=0x3C, OMEGA=0x40, RATE=0x44, GAIN=0x48, WRCNT=0x4C, OVERRUNS=0x50)
CAPTURE = 0x1000
NF, SPS, SYMBOL_RATE = 16, 4, 960e3


def loop_gains(bw, damping=np.sqrt(2) / 2):
    """alpha, beta of a second-order loop of bandwidth bw (rad per symbol): the formulas of GNU Radio's blocks."""
    den = 1 + 2 * damping * bw + bw * bw
    return 4 * damping * bw / den, 4 * bw * bw / den


def regs_from_bw(timing_bw, phase_bw, ref=16384, mu=40, g0=1024, init_freq_hz=0.0, max_rate=0.05):
    ta, tb = loop_gains(timing_bw); ca, cb = loop_gains(phase_bw)
    return dict(TA=int(round(ta * 2 ** 24)), TB=int(round(tb * 2 ** 24)), CA=int(round(ca * 2 ** 27 / (2 * np.pi))), CB=int(round(cb * 2 ** 27 / (2 * np.pi))),
                MU=int(mu), REF=int(ref), G0=int(g0), W0=int(round(init_freq_hz / SYMBOL_RATE * 2 ** 32)) & 0xFFFFFFFF, MAXR=int(round(max_rate * NF * 2 ** 16)))


UNIT = 8192.0                                       # soft symbols: the AGC makes the decision points about +-1.24 +-1.24j in these units


def soft_quality(z):
    """(mean |z|, angular spread in degrees) of soft symbols (complex, ADC units): the spread is the standard deviation of the angle to the nearest of the four ideal directions."""
    zn = np.asarray(z) / UNIT
    ang = np.angle(zn * np.exp(-1j * np.pi / 4)); dev = (ang + np.pi / 4) % (np.pi / 2) - np.pi / 4
    return float(np.abs(zn).mean()), float(np.degrees(np.std(dev)))


def constellation_ok(z):
    """Four sane clusters: mean magnitude near 1.75 and an angular spread below 25 degrees (a stuck or rotating receiver fails this, which the PRBS counters alone would not show)."""
    m, sp = soft_quality(z)
    return (1.2 < m < 2.4) and sp < 25.0


def _signed(v, bits=32):
    return v - (1 << bits) if v & (1 << (bits - 1)) else v


class P501QpskRx:
    EXPECTED_ID = 0xDD520001                          # the receiver of this file; the variant with the FLL (p501_qpsk_rx_fll.py) has 0xDD520002

    def __init__(self, ip):
        self.ip = ip
        if self.ip.read(REG["ID"]) != self.EXPECTED_ID:
            raise RuntimeError("not the QPSK receiver (ID 0x%08X)" % self.ip.read(REG["ID"]))

    def configure(self, timing_bw=2 * np.pi / 400, phase_bw=2 * np.pi / 400, **kw):
        """Write the loop gains (and AGC settings) from loop bandwidths; effective at the next start (the gains TA..CB, MU, REF act live)."""
        for name, v in regs_from_bw(timing_bw, phase_bw, **kw).items():
            self.ip.write(REG[name], v)

    def set_loops(self, timing_bw, phase_bw):
        """Change only the four loop gains, while the receiver runs (the registers act on the next symbol): wide loops to acquire, narrow loops to track."""
        r = regs_from_bw(timing_bw, phase_bw)
        for name in ("TA", "TB", "CA", "CB"):
            self.ip.write(REG[name], r[name])

    def start(self):
        self.ip.write(REG["CTRL"], 1)

    def locked(self, settle_s=0.05):
        """True when the receiver runs, no new mismatch appeared in the last settle_s seconds, and the soft symbols form a sane constellation."""
        m0 = self.ip.read(REG["MISMATCH"]); time.sleep(settle_s)
        if self.ip.read(REG["MISMATCH"]) != m0 or not (self.ip.read(REG["STATUS"]) & 1):
            return False
        try:
            return constellation_ok(self.capture())
        except TimeoutError:
            return False

    def _omega_hz(self, n=10, dt=0.002):
        v = []
        for _ in range(n):
            v.append(_signed(self.ip.read(REG["OMEGA"])) / 2 ** 32 * SYMBOL_RATE); time.sleep(dt)
        return float(np.mean(v))

    def acquire(self, track_div=400, acq_div=100, hints_hz=(0.0, 6000.0, -6000.0, 12000.0, -12000.0), settle_s=0.08, check_s=0.05):
        """Start the receiver so that it locks reliably. The Costas loop has no frequency detector in front of it, and the pull-in range of a loop of bandwidth 2 pi/acq_div is
        about 960 kHz / acq_div (9.6 kHz for 100): the 9.7 kHz offset between the P501 and the B210 is at the edge. So the loops start wide with an initial-frequency hint, in turn
        0, +6, -6, +12, -12 kHz. A try counts when, after settle_s, the receiver is locked (no new mismatch, sane constellation) *and* the frequency estimate has stopped moving
        (two averages 40 ms apart within 1500 Hz); then both loops are narrowed live to 2 pi / track_div and the lock is checked once more. Returns {locked, hint_hz, tries, seconds}."""
        t0 = time.time()
        for i, h in enumerate(hints_hz):
            self.stop()
            self.configure(timing_bw=2 * np.pi / acq_div, phase_bw=2 * np.pi / acq_div, init_freq_hz=h)
            self.start(); time.sleep(settle_s)
            f1 = self._omega_hz(); time.sleep(0.04); f2 = self._omega_hz()
            if abs(f2 - f1) > 1500 or not self.locked(check_s):
                continue
            if track_div:
                self.set_loops(2 * np.pi / track_div, 2 * np.pi / track_div); time.sleep(0.1)
                if not self.locked(0.1):
                    continue
            return dict(locked=True, hint_hz=h, tries=i + 1, seconds=time.time() - t0)
        return dict(locked=False, hint_hz=None, tries=len(hints_hz), seconds=time.time() - t0)

    def stop(self):
        self.ip.write(REG["CTRL"], 0)

    def stats(self):
        r = lambda k: self.ip.read(REG[k])
        sym, bits, mism = r("SYMBOLS"), r("BITS"), r("MISMATCH")
        omega, rate = _signed(r("OMEGA")), _signed(r("RATE"))
        return dict(symbols=sym, bits=bits, mismatches=mism, ber_estimate=(mism / 3.0 / bits if bits else float("nan")),   # one bit error gives three mismatches
                    carrier_offset_hz=omega / 2 ** 32 * SYMBOL_RATE,                                                     # the Costas frequency: the signal's offset to the receiver's LO
                    clock_offset_ppm=-rate / 2 ** 16 / NF / SPS * 1e6,                                                   # transmitter's symbol clock relative to the receiver's sample clock
                    agc_gain=r("GAIN") / 1024.0, overruns=r("OVERRUNS"), running=bool(r("STATUS") & 1))

    def offsets(self, n=100, period_s=0.005):
        """Carrier offset (Hz) and clock offset (ppm) averaged over n readings: the loops' values jitter from symbol to symbol, the mean is the offset."""
        om, ra = [], []
        for _ in range(n):
            om.append(_signed(self.ip.read(REG["OMEGA"]))); ra.append(_signed(self.ip.read(REG["RATE"]))); time.sleep(period_s)
        return (np.mean(om) / 2 ** 32 * SYMBOL_RATE, -np.mean(ra) / 2 ** 16 / NF / SPS * 1e6)

    def capture(self, timeout_s=2.0):
        """1024 soft symbols after the Costas loop, as complex numbers (full scale 32768; |z| is about 2.0 * 8192 = 16384 with the default AGC reference)."""
        self.ip.write(REG["CTRL"], 1); self.ip.write(REG["CTRL"], 3)             # arm: bit 1 from 0 to 1
        t0 = time.time()
        while not (self.ip.read(REG["STATUS"]) & 2):
            if time.time() - t0 > timeout_s: raise TimeoutError("capture did not complete: is the receiver running and the AD9361 clock on?")
            time.sleep(0.005)
        w = np.array([self.ip.read(CAPTURE + 4 * i) for i in range(1024)], dtype=np.uint32)
        self.ip.write(REG["CTRL"], 1)
        zi = (w & 0xFFFF).astype(np.uint16).view(np.int16).astype(float); zq = (w >> 16).astype(np.uint16).view(np.int16).astype(float)
        return zi + 1j * zq
