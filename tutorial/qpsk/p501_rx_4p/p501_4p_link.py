"""P501 side of the chain-3 test (run on the board as root; overlay p501_qpsk_trx_4p). The B210 (GNU Radio, started first by run_4p_test.py) transmits the PRBS-15 DQPSK signal.

    python3 /tmp/p501_4p_link.py <RX gain index> <trials> [acquire|stats|both|sweep]

Starts when /tmp/go appears.
acquire: <trials> times each from a cold start, the mismatch counter polled without a pause (the time of the last change is the time to lock), after the lock narrow loops for 2 s:
         costas (the Costas loop alone, reference), once (autonomous estimator, loads OMEGA once), continuous (every passing window loads OMEGA). "T" lines per trial, "Q" lines: quality over 2 s.
stats:   the accuracy of the estimator: manual windows of N = 128 ... 16384 symbols against the Costas loop's mean ("E" lines), and what the autonomous estimator loaded ("A" lines).
Ends with the TX attenuation at its maximum."""
import sys, time, os
import numpy as np
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_qpsk_trx_4p')
from pynq import Overlay
import p501_radio
from p501_qpsk_rx_4p import P501QpskRx4p, REG, SYMBOL_RATE, _signed
from p501_qpsk_rx import soft_quality

RX_GAIN = int(sys.argv[1]) if len(sys.argv) > 1 else 70
TRIALS = int(sys.argv[2]) if len(sys.argv) > 2 else 5
WHAT = sys.argv[3] if len(sys.argv) > 3 else "both"
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_qpsk_trx_4p/p501_qpsk_trx_4p.bit')
rx = P501QpskRx4p(ol.qpsk_rx)
ad = p501_radio.bring_up(ol, lo_hz=915_000_000, tx_atten_db=89.75, rx_gain_index=RX_GAIN)
rx.stop()
print("READY bring_up_ok=%s id=0x%08X" % (ad.info["ok"], rx.ip.read(0)), flush=True)
try:
    ad.set_tx_atten_db(89.75)
    print("WAITING for /tmp/go", flush=True)
    while not os.path.exists('/tmp/go'): time.sleep(0.01)
    os.remove('/tmp/go')
    if WHAT in ("acquire", "both"):
        for t in range(TRIALS):
            for mode in ("costas", "once", "continuous"):
                r = rx.timed_lock(mode)
                a = rx.auto_status()
                print("T %-10s trial %d: lock at %6.1f ms (%6d mismatches)  locked=%s  costas %+8.1f Hz   loads %2d  last loaded %+8.1f Hz" % (mode, t, r["ms"], r["mismatches"], r["locked"], r["costas_hz"], a["loads"], a["west_hz"]), flush=True)
        for mode in ("costas", "once", "continuous"):                      # steady state: narrow loops, 2 s
            rx.timed_lock(mode); rx.set_loops(2 * np.pi / 400, 2 * np.pi / 400); time.sleep(0.2)
            s0 = rx.stats(); om = []; sp = []
            t0 = time.time()
            while time.time() - t0 < 2.0:
                om.append(_signed(rx.ip.read(REG["OMEGA"])) / 2 ** 32 * SYMBOL_RATE); time.sleep(0.004)
                if len(om) % 50 == 0: sp.append(soft_quality(rx.capture())[1])
            s1 = rx.stats(); om = np.array(om)
            print("Q %-10s 2 s after the lock (loops 2pi/400): new mismatches %d in %d bits, Costas mean %+8.1f Hz std %6.1f Hz, constellation spread %.1f deg, loads %d, overruns %d" % (
                  mode, s1["mismatches"] - s0["mismatches"], s1["bits"] - s0["bits"], om.mean(), om.std(), np.mean(sp), rx.auto_status()["loads"], s1["overruns"]), flush=True)
    if WHAT == "sweep":
        # how good is the first estimate after a cold start? loop bandwidth of the timing loop (2 pi / div) and settling time before the autonomous estimator is enabled; truth = a 16384-symbol manual window later
        print("S cold starts of the autonomous estimator (once, N = 1024, q_min 0.3), %d each; truth = manual window of 16384 symbols after 50 ms" % TRIALS, flush=True)
        for div in (100, 400):
            for settle in (1000, 2000, 6000, 12000):
                err = []; truth = []
                for _ in range(TRIALS):
                    rx.disable_auto(); rx.stop(); time.sleep(0.03); rx.configure(timing_bw=2 * np.pi / div, phase_bw=2 * np.pi / div); rx.set_auto(1024, 0.3); rx.start()
                    time.sleep(settle / SYMBOL_RATE); rx.enable_auto(False)
                    t1 = time.time()
                    while rx.ip.read(REG["FE_NLOAD"]) == 0 and time.time() - t1 < 0.3: time.sleep(0.0005)
                    w = rx.auto_status()["west_hz"]; time.sleep(0.05); rx.disable_auto(); t = rx.measure(16384)["f_hz"]
                    err.append(w - t); truth.append(t)
                err = np.array(err)
                print("S timing 2pi/%3d settle %5d symbols (%5.1f ms): first loaded value - truth: mean %+7.0f Hz  rms %6.0f Hz  max |.| %6.0f Hz   (truth %+.0f Hz)" % (div, settle, settle / 960.0, err.mean(), np.sqrt(np.mean(err ** 2)), np.abs(err).max(), np.mean(truth)), flush=True)
    if WHAT in ("stats", "both"):
        rx.stop(); time.sleep(0.05); rx.configure(); rx.set_auto(1024, 0.3); rx.start(); time.sleep(0.5)
        co = np.array([_signed(rx.ip.read(REG["OMEGA"])) / 2 ** 32 * SYMBOL_RATE for _ in range(400) if not time.sleep(0.003)])
        print("E reference T = Costas mean %+8.1f Hz (std of the readings %.0f Hz), AGC gain %.2f" % (co.mean(), co.std(), rx.stats()["agc_gain"]), flush=True)
        for n in (128, 256, 512, 1024, 2048, 4096, 16384):
            es = [rx.measure(n) for _ in range(20)]
            f = np.array([e["f_hz"] for e in es]); q = np.mean([e["quality"] for e in es])
            print("E N %6d (%5.1f ms): mean %+8.1f Hz  bias %+7.1f  std %6.1f Hz  quality %.2f" % (n, n / 960.0, f.mean(), f.mean() - co.mean(), f.std(), q), flush=True)
        for n in (256, 1024, 4096):
            v = []
            for _ in range(10):
                rx.stop(); time.sleep(0.03); rx.configure(); rx.set_auto(n, 0.3); rx.start(); time.sleep(2000 / SYMBOL_RATE); rx.enable_auto(False)
                t1 = time.time()
                while rx.ip.read(REG["FE_NLOAD"]) == 0 and time.time() - t1 < 0.5: time.sleep(0.0005)
                v.append(rx.auto_status()["west_hz"])
            v = np.array(v)
            print("A autonomous, N %5d: loaded %+8.1f Hz mean, std %6.1f Hz over 10 cold starts (min %+.0f, max %+.0f)" % (n, v.mean(), v.std(), v.min(), v.max()), flush=True)
finally:
    rx.stop(); p501_radio.quiet(ad, 89.75)
    print("DONE (TX attenuation 89.75 dB)", flush=True)
