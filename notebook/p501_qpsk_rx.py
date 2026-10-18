"""Python side of the FPGA QPSK receiver (rtl/qpsk_rx.v, chapter 4d). The receiver works on its own; Python sets the loop gains, starts it and reads what it measured.

    from p501_qpsk_rx import P501QpskRx
    rx = P501QpskRx(ol.qpsk_rx)
    rx.configure(timing_bw=2*np.pi/400, phase_bw=2*np.pi/400)       # loop bandwidths (rad per symbol) -> the gain registers
    rx.start()
    rx.set_loops(2*np.pi/1600, 2*np.pi/1600)                          # e.g. after 30 ms: narrower loops, live
    s = rx.stats()      # symbols, checked bits, PRBS mismatches, BER estimate, carrier offset (Hz), clock offset (ppm), AGC gain
    z = rx.capture()    # 1024 soft symbols after the Costas loop (complex numpy array) for a constellation plot
    rx.stop()

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


def _signed(v, bits=32):
    return v - (1 << bits) if v & (1 << (bits - 1)) else v


class P501QpskRx:
    def __init__(self, ip):
        self.ip = ip
        if self.ip.read(REG["ID"]) != 0xDD520001:
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
