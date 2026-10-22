"""Python side of the FPGA QPSK receiver with the m-sequence FRAME SYNCHRONISER (rtl/qpsk_rx_sync.v, overlay p501_qpsk_trx_sync, ID 0xDD520005; chapter 4e, part 1).
The receiver is the one of chapter 4d plus a block beside the engine that correlates the phase steps of the received symbols with the known 63-chip m-sequence preamble,
finds the frame peaks, tracks the frame period and opens a payload gate. Everything of p501_qpsk_rx.P501QpskRx works as before (configure, set_loops, start, stats, capture, acquire, ...).

    from p501_qpsk_rx_sync import P501QpskRxSync
    rx = P501QpskRxSync(ol.qpsk_rx)
    rx.configure_sync(fl=1024, pl=960)          # frame = 64 preamble symbols + 960 payload symbols; the same as the transmitter
    r = rx.acquire_hw(fl=1024, pl=960)           # HARDWARE ACQUISITION: the synchroniser loads the Costas frequency from the preamble and switches the loop gains; no hint, no search in Python
    rx.start(); rx.gate_enable(True)            # the PRBS-15 checker counts only inside the payload
    rx.wait_lock(1.0)                           # True when two preambles one frame apart have been found
    rx.sync_status()                            # locked, gate, peaks, hits, misses, false peaks, locks, losses, the correlation C at the last peak, the frequency from arg(C), ...
The frequency offset comes from the preamble itself: C is the sum of the phase steps times the known chips, so arg(C) = 2 pi f T and f = arg(C) / (2 pi) x 960 kHz (data aided,
|f| < 480 kHz), whatever the state of the Costas loop."""
import time
import numpy as np
from p501_qpsk_rx import P501QpskRx, REG, _signed, SYMBOL_RATE, constellation_ok

REG.update(SY_CTRL=0x54, SY_FL=0x58, SY_PL=0x5C, SY_THR=0x60, SY_TOL=0x64, SY_MISSMAX=0x68, SY_GUARD=0x6C, SY_STATUS=0x70, SY_NDET=0x74, SY_NHIT=0x78, SY_NMISS=0x7C, SY_NFALSE=0x80,
           SY_NLOCK=0x84, SY_NLOST=0x88, SY_REF=0x8C, SY_CRE=0x90, SY_CIM=0x94, SY_MET=0x98, SY_EN=0x9C, SY_PEAK=0xA0, SY_LATE=0xA4,
           SY_NSW=0xA8, SY_CAW=0xAC, SY_CBW=0xB0, SY_LOAD=0xB4, SY_NLOAD=0xB8, SY_NLD=0xBC, SY_WLAST=0xC0)


class P501QpskRxSync(P501QpskRx):
    EXPECTED_ID = 0xDD520005

    def configure_sync(self, fl=1024, pl=960, thr=140, tol=1, missmax=3, guard=2):
        """fl, pl: frame and payload length in symbols (fl = 64 + pl); thr: detection threshold, 256 x |C| / sum|d| (140 = 0.55; random data gives about 0.13, a clean preamble 0.9);
        tol: tolerance of the frame period (symbols); missmax: misses in a row that lose the lock; guard: first payload symbol counted (the gate opens two symbols late: the peak is known one symbol after it)."""
        w = self.ip.write
        for k, v in (("SY_FL", fl), ("SY_PL", pl), ("SY_THR", thr), ("SY_TOL", tol), ("SY_MISSMAX", missmax), ("SY_GUARD", guard)):
            w(REG[k], int(v))

    def configure_acquisition(self, load=1, nload=8, nsw=4, acq_div=100):
        """HARDWARE ACQUISITION, no Python carrier search: the frame synchroniser loads the Costas frequency from the preamble (arg(C), 1 to 3.5 kHz low on this link, good enough for the wide loop)
        and switches the Costas loop from the acquisition gains (bandwidth 2 pi / acq_div) to the tracking gains (CA, CB: the ones of configure() / set_loops()) once the tracker is locked and nsw hits have followed.
        load: 0 off, 1 the first nload locks/hits, 2 every lock/hit (follows a drifting offset; the loop's own integrator is replaced once per frame).  nsw = 0: always the tracking gains."""
        from p501_qpsk_rx import loop_gains
        ca, cb = loop_gains(2 * np.pi / acq_div)
        w = self.ip.write
        w(REG["SY_CAW"], int(round(ca * 2 ** 27 / (2 * np.pi)))); w(REG["SY_CBW"], int(round(cb * 2 ** 27 / (2 * np.pi))))
        w(REG["SY_NSW"], int(nsw)); w(REG["SY_NLOAD"], int(nload)); w(REG["SY_LOAD"], int(load))

    def acquire_hw(self, fl=1024, pl=960, track_div=400, load=1, nload=8, nsw=4, acq_div=100, timeout_s=1.0, thr=140, tol=1, missmax=3, guard=2):
        """Cold start with the frame synchroniser doing the carrier acquisition (no hints, no search loop in Python): the timing loop and the tracking Costas gains 2 pi / track_div, the acquisition gains
        2 pi / acq_div until the tracker has locked; then wait until the receiver is locked (a sane constellation and a Costas frequency that has settled to within 1.5 kHz). Returns {locked, sync_locked, seconds, loads, costas_hz}."""
        t0 = time.time()
        self.stop(); time.sleep(0.05)
        self.configure(timing_bw=2 * np.pi / track_div, phase_bw=2 * np.pi / track_div, init_freq_hz=0.0)
        self.configure_sync(fl=fl, pl=pl, thr=thr, tol=tol, missmax=missmax, guard=guard); self.configure_acquisition(load=load, nload=nload, nsw=nsw, acq_div=acq_div); self.gate_enable(True)
        self.start()
        sync = self.wait_lock(timeout_s); ok = False
        while sync and time.time() - t0 < timeout_s + 0.5:
            f1 = self._omega_hz(n=3, dt=0.001); time.sleep(0.02); f2 = self._omega_hz(n=3, dt=0.001)
            try: sane = constellation_ok(self.capture())
            except TimeoutError: sane = False
            if sane and abs(f2 - f1) < 1500: ok = True; break                           # a sane constellation and a frequency that has settled: not 'no mismatch in 20 ms', which a noisy channel never satisfies
        y = self.sync_status()
        return dict(locked=ok, sync_locked=sync, seconds=time.time() - t0, loads=self.ip.read(REG["SY_NLD"]), costas_hz=self._omega_hz(), freq_hz=y["freq_hz"])

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
