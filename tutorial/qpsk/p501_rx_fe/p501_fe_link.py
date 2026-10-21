"""P501 side of the estimator test (run on the board as root; overlay p501_qpsk_trx_fe). The B210 (GNU Radio, started first by run_fe_test.py) transmits the PRBS-15 DQPSK signal.

    python3 /tmp/p501_fe_link.py <RX gain index> <trials> [stats|acquire|both|settle]

Starts when /tmp/go appears.
stats:   the receiver runs Costas-only (FLL held at 0), its mean Costas frequency over 1 s is the reference T; then the estimator: <20 windows> for N = 128 ... 16384 symbols: mean, std, quality ("E" lines);
         and for comparison the FLL's own instantaneous frequency (loop on, narrow gain) over 400 readings ("F" line)
acquire: <trials> times each, from a cold start, with the mismatch counter polled without a pause; the time of the last change is the time to lock ("T" lines):
         costas  - wide Costas loop only (the FLL held at 0)            fll - FLL + Costas wide (acquire_fll's gains)
         fe-fll  - 2000 symbols (2.1 ms) settling, one window of 1024 symbols (1.1 ms), derotator loaded with the estimate (FLL loop off)         fe-w0 - the same, then a restart with W0 = the estimate
Ends with the TX attenuation at its maximum."""
import sys, time, os
import numpy as np
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_qpsk_trx_fe')
from pynq import Overlay
import p501_radio
from p501_qpsk_rx_fe import P501QpskRxFe, REG, SYMBOL_RATE, FS, _signed
from p501_qpsk_rx import soft_quality

RX_GAIN = int(sys.argv[1]) if len(sys.argv) > 1 else 70
TRIALS = int(sys.argv[2]) if len(sys.argv) > 2 else 5
WHAT = sys.argv[3] if len(sys.argv) > 3 else "both"
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_qpsk_trx_fe/p501_qpsk_trx_fe.bit')
rx = P501QpskRxFe(ol.qpsk_rx)
ad = p501_radio.bring_up(ol, lo_hz=915_000_000, tx_atten_db=89.75, rx_gain_index=RX_GAIN)
rx.stop()
print("READY bring_up_ok=%s id=0x%08X" % (ad.info["ok"], rx.ip.read(0)), flush=True)


def poll(seconds, st):
    """Busy-poll the mismatch counter; st = [last_m, last_t, t0]: updates the time of the last change."""
    end = time.time() + seconds
    while time.time() < end:
        m = rx.ip.read(REG["MISMATCH"])
        if m != st[0]: st[0], st[1] = m, time.time() - st[2]


def timed(method, acq_div=100):
    rx.stop(); time.sleep(0.05)
    rx.configure(timing_bw=2 * np.pi / acq_div, phase_bw=2 * np.pi / acq_div, init_freq_hz=0.0)
    rx.ip.write(REG["FLL_F0"], 0); rx.set_fll(0.002); rx.fll_enable(method == "fll")
    st = [0, 0.0, time.time()]
    if method == "fe-fll": rx.ip.write(REG["CA"], 0); rx.ip.write(REG["CB"], 0)       # the Costas loop waits at 0 Hz while the estimator measures
    rx.start(); st[2] = time.time(); est = None
    if method in ("fe-fll", "fe-w0"):
        poll(2000 / SYMBOL_RATE, st)
        w = rx.ip.write; w(REG["FE_N"], 1024); w(REG["FE_CTRL"], 0); w(REG["FE_CTRL"], 1)
        while not (rx.ip.read(REG["FE_STATUS"]) & 2):
            m = rx.ip.read(REG["MISMATCH"])
            if m != st[0]: st[0], st[1] = m, time.time() - st[2]
        re, im = _signed(rx.ip.read(REG["ACC_RE"])), _signed(rx.ip.read(REG["ACC_IM"]))
        est = np.arctan2(im, re) / (8 * np.pi) * SYMBOL_RATE
        if method == "fe-fll": rx.fll_load(-est); rx.set_loops(2 * np.pi / acq_div, 2 * np.pi / acq_div)
        else:
            rx.stop(); rx.configure(timing_bw=2 * np.pi / acq_div, phase_bw=2 * np.pi / acq_div, init_freq_hz=est); rx.start(); st[2] = st[2]     # the restart counts in the time
    poll(0.3, st)
    ok = rx.locked(0.05); fl, co = rx.fll_hz(), rx._omega_hz()
    return st[1] * 1e3, st[0], ok, est, fl, co


try:
    ad.set_tx_atten_db(89.75)
    print("WAITING for /tmp/go", flush=True)
    while not os.path.exists('/tmp/go'): time.sleep(0.01)
    os.remove('/tmp/go')
    if WHAT in ("stats", "both"):
        rx.fll_enable(False); rx.ip.write(REG["FLL_F0"], 0)          # the FLL held at 0 Hz: the estimator and the Costas loop see the whole offset
        r = rx.acquire(hints_hz=(0.0,))
        print("E reference: Costas-only acquire locked=%s" % r["locked"], flush=True)
        rx.fll_enable(False)
        co = np.array([_signed(rx.ip.read(REG["OMEGA"])) / 2 ** 32 * SYMBOL_RATE for _ in range(400) if not time.sleep(0.003)])
        print("E reference T = Costas mean %+8.1f Hz (std of the readings %.0f Hz), AGC gain %.2f" % (co.mean(), co.std(), rx.stats()["agc_gain"]), flush=True)
        for n in (128, 256, 512, 1024, 2048, 4096, 16384):
            es = [rx.measure(n) for _ in range(20)]
            f = np.array([e["f_hz"] for e in es]); q = np.mean([e["quality"] for e in es])
            print("E N %6d (%5.1f ms): mean %+8.1f Hz  bias %+7.1f  std %6.1f Hz  quality %.2f  (%d windows)" % (n, n / 960.0, f.mean(), f.mean() - co.mean(), f.std(), q, len(f)), flush=True)
        r = rx.acquire_fll()
        fl = np.array([_signed(rx.ip.read(REG["FLL_FREQ"])) / 2 ** 32 * FS for _ in range(400) if not time.sleep(0.003)])
        print("F FLL loop on (narrow): locked=%s  frequency mean %+8.1f Hz  std %6.1f Hz  (instantaneous readings; -offset is expected)" % (r["locked"], fl.mean(), fl.std()), flush=True)
    if WHAT == "settle":
        # how long must the AGC and the timing loop converge before the estimate is good? cold start (FLL at 0, Costas held), wait, measure 1024 symbols; the reference is a long window at the end
        res = {}
        for t in range(TRIALS):
            for settle in (250, 500, 1000, 2000, 4000, 8000):
                rx.stop(); time.sleep(0.03); rx.configure(timing_bw=2 * np.pi / 100, phase_bw=2 * np.pi / 100, init_freq_hz=0.0)
                rx.ip.write(REG["FLL_F0"], 0); rx.fll_enable(False); rx.ip.write(REG["CA"], 0); rx.ip.write(REG["CB"], 0)
                rx.start(); time.sleep(settle / SYMBOL_RATE); e1 = rx.measure(1024); time.sleep(0.03); ref = rx.measure(16384)
                res.setdefault(settle, []).append((e1["f_hz"], ref["f_hz"], e1["quality"]))
        for settle, v in res.items():
            v = np.array(v); err = v[:, 0] - v[:, 1]
            print("E settle %5d symbols (%4.2f ms): error vs the 16384-symbol window: mean %+7.1f Hz  rms %7.1f Hz  max %7.1f Hz  quality %.2f  (reference %+.0f Hz)" % (settle, settle / 960.0, err.mean(), np.sqrt(np.mean(err ** 2)), np.abs(err).max(), v[:, 2].mean(), v[:, 1].mean()), flush=True)
    if WHAT in ("acquire", "both"):
        for t in range(TRIALS):
            for method in ("costas", "fll", "fe-fll", "fe-w0"):
                ms, mm, ok, est, fl, co = timed(method)
                print("T %-7s trial %d: lock at %6.1f ms (%6d mismatches)  locked=%s  estimate %s  fll %+8.1f  costas %+8.1f  total %+8.1f Hz" % (
                      method, t, ms, mm, ok, ("%+8.1f" % est) if est is not None else "     -  ", fl, co, co - fl), flush=True)
finally:
    rx.stop(); p501_radio.quiet(ad, 89.75)
    print("DONE (TX attenuation 89.75 dB)", flush=True)
