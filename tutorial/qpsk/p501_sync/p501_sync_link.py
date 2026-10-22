"""P501 side of the frame-synchronisation test (run on the board as root; overlay p501_qpsk_trx_sync). The B210 (GNU Radio / Python, started first by run_sync_test.py) transmits frames:
a 64-symbol m-sequence preamble + payload symbols of PRBS-15, repeated.

    python3 /tmp/p501_sync_link.py <RX gain index> <payload symbols> <levels> <seconds per level>

The host changes the B210 TX gain between the levels and releases each one with /tmp/go_<k>. For the first level the script also runs
  N  the synchroniser with the Costas loop UNLOCKED (loops 2 pi/1600 from a cold start: they cannot pull in the +9.7 kHz): the time to lock and the frequency from the preamble correlation,
  L  10 cold starts with wide loops (2 pi/100, no hint): the time until the synchroniser has locked (two preambles found) with the mismatch counter and the sync registers polled without a pause.
For every level (S): the carrier search (rx.acquire), then <seconds> of counting: peaks, hits, misses, false peaks, losses, the payload bit errors (gated: only inside the frames),
the frequency from the correlation against the Costas frequency, and the quality |C| / sum|d| of the preamble. Ends with the TX attenuation at its maximum."""
import sys, time, os
import numpy as np
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_qpsk_trx_sync')
from pynq import Overlay
import p501_radio
from p501_qpsk_rx_sync import P501QpskRxSync, REG, SYMBOL_RATE, _signed
from p501_qpsk_rx import soft_quality

RX_GAIN = int(sys.argv[1]) if len(sys.argv) > 1 else 70
PL = int(sys.argv[2]) if len(sys.argv) > 2 else 960
LEVELS = int(sys.argv[3]) if len(sys.argv) > 3 else 1
SECONDS = float(sys.argv[4]) if len(sys.argv) > 4 else 3.0
FL = PL + 64
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_qpsk_trx_sync/p501_qpsk_trx_sync.bit')
rx = P501QpskRxSync(ol.qpsk_rx)
ad = p501_radio.bring_up(ol, lo_hz=915_000_000, tx_atten_db=89.75, rx_gain_index=RX_GAIN)
rx.stop()
print("READY bring_up_ok=%s id=0x%08X" % (ad.info["ok"], rx.ip.read(0)), flush=True)


def cold(div, hint=0.0):
    rx.stop(); time.sleep(0.05)
    rx.configure(timing_bw=2 * np.pi / div, phase_bw=2 * np.pi / div, init_freq_hz=hint)
    rx.configure_sync(fl=FL, pl=PL); rx.gate_enable(True)


def wait_go(k):
    while not os.path.exists('/tmp/go_%d' % k): time.sleep(0.01)
    os.remove('/tmp/go_%d' % k)


try:
    ad.set_tx_atten_db(89.75)
    print("WAITING for /tmp/go_0", flush=True)
    for k in range(LEVELS):
        wait_go(k)
        gain_line = open('/tmp/tx_gain').read().strip() if os.path.exists('/tmp/tx_gain') else "?"
        if k == 0:
            # N: the Costas loop cannot lock (narrow loops, no hint): the synchroniser must work anyway
            cold(1600); rx.start(); t0 = time.time(); locked = False
            while time.time() - t0 < 0.5 and not locked: locked = bool(rx.ip.read(REG["SY_STATUS"]) & 1)
            t_lock = (time.time() - t0) * 1e3
            time.sleep(0.2); f, q, sd = rx.corr_freq_hz(n=150, period_s=0.0013); z = rx.capture(); st = rx.sync_status()
            print("N Costas unlocked (2pi/1600, W0 = 0): sync locked=%s after %.1f ms; frequency from the preamble %+.1f Hz (std of single frames %.0f Hz, consistency %.2f); Costas OMEGA %+.0f Hz; constellation spread %.0f deg; peaks %d hits %d misses %d false %d lost %d late %d" % (
                  locked, t_lock, f, sd, q, rx._omega_hz(), soft_quality(z)[1], st["peaks"], st["hits"], st["misses"], st["false"], st["lost"], st["late"]), flush=True)
            # L: lock time from a cold start with wide loops
            ts = []
            for i in range(10):
                cold(100); rx.start(); t0 = time.time(); locked = False
                while time.time() - t0 < 0.3 and not locked: locked = bool(rx.ip.read(REG["SY_STATUS"]) & 1)
                ts.append((time.time() - t0) * 1e3 if locked else float("nan"))
            ts = np.array(ts); print("L lock time from a cold start (wide loops), 10 starts: median %.1f ms, min %.1f, max %.1f, not locked: %d" % (np.nanmedian(ts), np.nanmin(ts), np.nanmax(ts), int(np.isnan(ts).sum())), flush=True)
        # S: carrier search, then count
        cold(100)
        r = rx.acquire(track_div=400)
        rx.configure_sync(fl=FL, pl=PL); rx.gate_enable(True)
        time.sleep(0.2); s0 = rx.stats(); y0 = rx.sync_status(); t0 = time.time()
        time.sleep(SECONDS)
        s1 = rx.stats(); y1 = rx.sync_status(); dt = time.time() - t0
        f, q, sd = rx.corr_freq_hz(n=100, period_s=0.0013); om = rx._omega_hz(); z = rx.capture()
        nb, nm = s1["bits"] - s0["bits"], s1["mismatches"] - s0["mismatches"]
        d = lambda key: y1[key] - y0[key]
        print("S tx_gain %s dB: carrier search locked=%s | sync locked=%s: %.2f s: peaks %d hits %d misses %d false %d losses %d late %d | frames %.0f expected | payload bits %d, mismatches %d (BER about %.1e) | "
              "frequency from the preamble %+.0f Hz (std %.0f), Costas %+.0f Hz | quality |C|/sum|d| %.2f | spread %.1f deg" % (
              gain_line, r["locked"], y1["locked"], dt, d("peaks"), d("hits"), d("misses"), d("false"), d("lost"), y1["late"], dt / (FL / SYMBOL_RATE), nb, nm, nm / 3.0 / max(nb, 1), f, sd, om, y1["quality"], soft_quality(z)[1]), flush=True)
        print("LEVEL_DONE %d" % k, flush=True)
finally:
    rx.gate_enable(False); rx.stop(); p501_radio.quiet(ad, 89.75)
    print("DONE (TX attenuation 89.75 dB)", flush=True)
