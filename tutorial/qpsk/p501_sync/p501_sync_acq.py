"""P501 side of the hardware-acquisition test (run on the board as root; overlay p501_qpsk_trx_sync with the frequency load): the B210 sends frames; at every level (a B210 carrier, set by the host)
the receiver is started cold <trials> times in two ways and the results are printed:
  H  hardware: rx.acquire_hw(): the frame synchroniser loads the Costas frequency from the preamble and switches the gains (no hint, no Python search loop)
  P  Python:   rx.acquire(): the chapter-4d search (wide loops with hints 0, +-6, +-12 kHz), the frame sync only gates the checker
    python3 /tmp/p501_sync_acq.py <RX gain index> <payload symbols> <levels> <trials>
Each level starts when /tmp/go_<k> appears. For each start: locked, seconds until locked, the loads, then 1 s of counting (payload bits and mismatches inside the gate, the constellation spread, the Costas frequency)."""
import sys, time, os
import numpy as np
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_qpsk_trx_sync')
from pynq import Overlay
import p501_radio
from p501_qpsk_rx_sync import P501QpskRxSync, REG, SYMBOL_RATE, _signed
from p501_qpsk_rx import soft_quality
RX_GAIN, PL, LEVELS, TRIALS = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
FL = PL + 64
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_qpsk_trx_sync/p501_qpsk_trx_sync.bit')
rx = P501QpskRxSync(ol.qpsk_rx)
ad = p501_radio.bring_up(ol, lo_hz=915_000_000, tx_atten_db=89.75, rx_gain_index=RX_GAIN)
rx.stop()
print("READY bring_up_ok=%s id=0x%08X" % (ad.info["ok"], rx.ip.read(0)), flush=True)


def count(seconds=1.0):
    s0 = rx.stats(); time.sleep(seconds); s1 = rx.stats(); z = rx.capture(); y = rx.sync_status()
    return s1["bits"] - s0["bits"], s1["mismatches"] - s0["mismatches"], soft_quality(z)[1], rx._omega_hz(), y


try:
    ad.set_tx_atten_db(89.75); print("WAITING for /tmp/go_0", flush=True)
    for k in range(LEVELS):
        while not os.path.exists('/tmp/go_%d' % k): time.sleep(0.01)
        os.remove('/tmp/go_%d' % k); label = open('/tmp/tx_label').read().strip() if os.path.exists('/tmp/tx_label') else "?"
        for t in range(TRIALS):
            rx.configure_acquisition(load=0, nsw=0)                    # the Python search must not be helped
            rx.stop(); rx.configure(timing_bw=2 * np.pi / 100, phase_bw=2 * np.pi / 100); rx.configure_sync(fl=FL, pl=PL); rx.gate_enable(True)
            t0 = time.time(); r = rx.acquire(track_div=400); tp = time.time() - t0
            time.sleep(0.2); nb, nm, sp, om, y = count(1.0)
            print("P %s trial %d: search locked=%s %.2f s | payload bits %d mismatches %d (BER about %.1e), spread %.1f deg, Costas %+.0f Hz, sync locked=%s" % (label, t, r["locked"], tp, nb, nm, nm / 3.0 / max(nb, 1), sp, om, y["locked"]), flush=True)
            r = rx.acquire_hw(fl=FL, pl=PL)
            time.sleep(0.2); nb, nm, sp, om, y = count(1.0)
            print("H %s trial %d: hardware locked=%s sync=%s %.2f s, loads %d | payload bits %d mismatches %d (BER about %.1e), spread %.1f deg, Costas %+.0f Hz" % (label, t, r["locked"], r["sync_locked"], r["seconds"], r["loads"], nb, nm, nm / 3.0 / max(nb, 1), sp, om), flush=True)
        print("LEVEL_DONE %d" % k, flush=True)
finally:
    rx.configure_acquisition(load=0, nsw=0); rx.gate_enable(False); rx.stop(); p501_radio.quiet(ad, 89.75)
    print("DONE (TX attenuation 89.75 dB)", flush=True)
