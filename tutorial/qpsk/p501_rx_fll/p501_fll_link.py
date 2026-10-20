"""P501 side of the FLL receiver test (run on the board as root; overlay p501_qpsk_trx_fll). The B210 (GNU Radio, started first by run_fll_test.py) transmits the PRBS-15 DQPSK signal.

    python3 /tmp/p501_fll_link.py <RX gain index> <trials> <seconds> [pullin]

Starts when /tmp/go appears. Then, <trials> times each:
  A. acquire_fll()                         - FLL + Costas, no frequency hint: wide gains, then narrow
  B. acquire(hints_hz=(0.0,))              - the original receiver's procedure (Costas only, a single try without hint) on the same overlay with the FLL held at 0
  C. acquire(hints_hz=(0, 6e3, -6e3, 12e3, -12e3)) - the original with its default hints
and prints locked / tries / seconds / FLL, Costas and total offsets. Then a long run (<seconds>) with the narrow loops: statistics once per second, mismatches, FLL late count, overruns.
With the 4th argument "pullin" it instead measures the true pull-in time: <trials> times each for the receiver with the FLL (wide gain 0.002, Costas 2 pi/100) and without (FLL held at 0, Costas 2 pi/100),
the receiver is started and the mismatch counter is polled without a pause for 0.3 s; the time of the last change is the time the receiver needed to lock (lines "P ...").
Ends with the TX attenuation at its maximum."""
import sys, time, os
import numpy as np
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_qpsk_trx_fll')
from pynq import Overlay
import p501_radio
from p501_qpsk_rx_fll import P501QpskRxFll, REG

RX_GAIN = int(sys.argv[1]) if len(sys.argv) > 1 else 70
TRIALS = int(sys.argv[2]) if len(sys.argv) > 2 else 5
SECONDS = float(sys.argv[3]) if len(sys.argv) > 3 else 6.0
PULLIN = len(sys.argv) > 4 and sys.argv[4] == "pullin"
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_qpsk_trx_fll/p501_qpsk_trx_fll.bit')
rx = P501QpskRxFll(ol.qpsk_rx)
ad = p501_radio.bring_up(ol, lo_hz=915_000_000, tx_atten_db=89.75, rx_gain_index=RX_GAIN)
rx.stop()
print("READY bring_up_ok=%s id=0x%08X" % (ad.info["ok"], rx.ip.read(0)), flush=True)
try:
    ad.set_tx_atten_db(89.75)
    print("WAITING for /tmp/go", flush=True)
    while not os.path.exists('/tmp/go'): time.sleep(0.01)
    os.remove('/tmp/go')
    def pullin(use_fll):
        rx.stop(); time.sleep(0.05); rx.configure(timing_bw=2 * np.pi / 100, phase_bw=2 * np.pi / 100, init_freq_hz=0.0)
        rx.ip.write(REG["FLL_F0"], 0); rx.set_fll(0.002); rx.fll_enable(use_fll)
        rx.start(); t0 = time.time(); last_m, last_t = 0, 0.0
        while time.time() - t0 < 0.3:
            m = rx.ip.read(0x3C)
            if m != last_m: last_m, last_t = m, time.time() - t0
        ok = rx.locked(0.05); fl, co = rx.fll_hz(), rx._omega_hz()
        return last_t * 1e3, last_m, ok, fl, co
    if PULLIN:
        for t in range(TRIALS):
            for use_fll, name in ((True, "fll+costas"), (False, "costas only")):
                ms, mm, ok, fl, co = pullin(use_fll)
                print("P %-11s trial %d: pull-in %6.1f ms  (%5d mismatches)  locked=%s  fll %+8.1f Hz  costas %+8.1f Hz  total %+8.1f Hz" % (name, t, ms, mm, ok, fl, co, co - fl), flush=True)
        TRIALS = 0
        SECONDS = 0
    for t in range(TRIALS):
        rx.stop(); time.sleep(0.05)
        r = rx.acquire_fll()
        print("A fll+costas  trial %d: locked=%s tries=%d %.2f s  fll %+8.1f Hz  costas %+8.1f Hz  total %+8.1f Hz" % (t, r["locked"], r["tries"], r["seconds"], r["fll_hz"], r["costas_hz"], r["total_hz"]), flush=True)
        rx.stop(); time.sleep(0.05); rx.fll_enable(False); rx.ip.write(REG["FLL_F0"], 0); rx.fll_load(0.0)       # the FLL held at zero: the original receiver
        r = rx.acquire(hints_hz=(0.0,))
        print("B costas only trial %d: locked=%s hint %s %.2f s  costas %+8.1f Hz" % (t, r["locked"], r["hint_hz"], r["seconds"], rx._omega_hz()), flush=True)
        rx.stop(); time.sleep(0.05)
        r = rx.acquire()
        print("C costas+hints trial %d: locked=%s hint %s tries %d %.2f s  costas %+8.1f Hz" % (t, r["locked"], r["hint_hz"], r["tries"], r["seconds"], rx._omega_hz()), flush=True)
        rx.fll_enable(True)
    if PULLIN: raise SystemExit
    rx.stop(); time.sleep(0.05)
    r = rx.acquire_fll()
    print("LONG run starts, acquire_fll: %s" % r, flush=True)
    t0 = time.time(); tsec = 0
    while time.time() - t0 < SECONDS:
        time.sleep(0.01)
        if time.time() - t0 >= tsec:
            tsec += 1.0
            s = rx.stats()
            print("t=%4.1f s bits %9d mismatches %6d  BER~%.1e  total %+8.1f Hz (fll %+8.1f costas %+8.1f)  clock %+6.2f ppm  agc %.2f  overruns %d  fll late %d" % (
                  time.time() - t0, s["bits"], s["mismatches"], s["ber_estimate"], s["carrier_offset_hz"], s["fll_hz"], s["costas_hz"], s["clock_offset_ppm"], s["agc_gain"], s["overruns"], s["late"]), flush=True)
    z = rx.capture(); np.save('/tmp/p501_fll_soft.npy', z)
    from p501_qpsk_rx import soft_quality
    print("soft symbols: mean |z|/8192 %.2f, angular spread %.1f deg" % soft_quality(z), flush=True)
finally:
    rx.stop(); p501_radio.quiet(ad, 89.75)
    print("DONE (TX attenuation 89.75 dB)", flush=True)
