"""Python side of the FPGA QPSK receiver with the m-sequence FRAME SYNCHRONISER (rtl/qpsk_rx_sync.v, overlay p501_qpsk_trx_sync, ID 0xDD520005; chapter 4e, part 1).
The receiver is the one of chapter 4d plus a block beside the engine that correlates the phase steps of the received symbols with the known 63-chip m-sequence preamble,
finds the frame peaks, tracks the frame period and opens a payload gate. Everything of p501_qpsk_rx.P501QpskRx works as before (configure, set_loops, start, stats, capture, acquire, ...).

    from p501_qpsk_rx_sync import P501QpskRxSync
    rx = P501QpskRxSync(ol.qpsk_rx)
    rx.configure_sync(fl=1024, pl=960)          # frame = 64 preamble symbols + 960 payload symbols; the same as the transmitter
    rx.start(); rx.gate_enable(True)            # the PRBS-15 checker counts only inside the payload
    rx.wait_lock(1.0)                           # True when two preambles one frame apart have been found
    rx.sync_status()                            # locked, gate, peaks, hits, misses, false peaks, locks, losses, the correlation C at the last peak, the frequency from arg(C), ...
The frequency offset comes from the preamble itself: C is the sum of the phase steps times the known chips, so arg(C) = 2 pi f T and f = arg(C) / (2 pi) x 960 kHz (data aided,
|f| < 480 kHz), whatever the state of the Costas loop."""
import time
import numpy as np
from p501_qpsk_rx import P501QpskRx, REG, _signed, SYMBOL_RATE

REG.update(SY_CTRL=0x54, SY_FL=0x58, SY_PL=0x5C, SY_THR=0x60, SY_TOL=0x64, SY_MISSMAX=0x68, SY_GUARD=0x6C, SY_STATUS=0x70, SY_NDET=0x74, SY_NHIT=0x78, SY_NMISS=0x7C, SY_NFALSE=0x80,
           SY_NLOCK=0x84, SY_NLOST=0x88, SY_REF=0x8C, SY_CRE=0x90, SY_CIM=0x94, SY_MET=0x98, SY_EN=0x9C, SY_PEAK=0xA0, SY_LATE=0xA4)


class P501QpskRxSync(P501QpskRx):
    EXPECTED_ID = 0xDD520005

    def configure_sync(self, fl=1024, pl=960, thr=140, tol=1, missmax=3, guard=2):
        """fl, pl: frame and payload length in symbols (fl = 64 + pl); thr: detection threshold, 256 x |C| / sum|d| (140 = 0.55; random data gives about 0.13, a clean preamble 0.9);
        tol: tolerance of the frame period (symbols); missmax: misses in a row that lose the lock; guard: first payload symbol counted (the gate opens two symbols late: the peak is known one symbol after it)."""
        w = self.ip.write
        for k, v in (("SY_FL", fl), ("SY_PL", pl), ("SY_THR", thr), ("SY_TOL", tol), ("SY_MISSMAX", missmax), ("SY_GUARD", guard)):
            w(REG[k], int(v))

    def gate_enable(self, on=True):
        """With the gate on, the checker (BITS, MISMATCH) counts only inside the payload of locked frames and restarts at the start of each; off: it counts everything (the receiver of chapter 4d)."""
        self.ip.write(REG["SY_CTRL"], 1 if on else 0)

    def sync_status(self):
        r = lambda k: self.ip.read(REG[k])
        st = r("SY_STATUS"); cre, cim, met, en = _signed(r("SY_CRE")), _signed(r("SY_CIM")), r("SY_MET"), r("SY_EN")
        return dict(locked=bool(st & 1), gate=bool(st & 2), peaks=r("SY_NDET"), hits=r("SY_NHIT"), misses=r("SY_NMISS"), false=r("SY_NFALSE"), locks=r("SY_NLOCK"), lost=r("SY_NLOST"),
                    ref=r("SY_REF"), cre=cre, cim=cim, metric=met, energy=en, quality=(met / en if en else 0.0), peak_symbol=r("SY_PEAK"), late=r("SY_LATE"),
                    freq_hz=float(np.arctan2(cim, cre) / (2 * np.pi) * SYMBOL_RATE))

    def wait_lock(self, timeout_s=1.0):
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            if self.ip.read(REG["SY_STATUS"]) & 1:
                return True
        return False

    def corr_freq_hz(self, n=100, period_s=0.0013):
        """Frequency offset from the correlation at the peaks: the mean of n snapshots of C (circular mean), every period_s (a frame is 1.07 ms). Returns (Hz, quality, std of the single readings in Hz)."""
        z = []
        for _ in range(n):
            cre, cim = _signed(self.ip.read(REG["SY_CRE"])), _signed(self.ip.read(REG["SY_CIM"]))
            if cre or cim: z.append(complex(cre, cim))
            time.sleep(period_s)
        if not z: return float("nan"), 0.0, float("nan")
        z = np.array(z); f1 = np.angle(z) / (2 * np.pi) * SYMBOL_RATE
        return float(np.angle(np.mean(z / np.abs(z))) / (2 * np.pi) * SYMBOL_RATE), float(np.abs(np.mean(z / np.abs(z)))), float(np.std(f1))
