"""P501 side of the false-alarm test (run on the board as root; overlay p501_qpsk_trx_sync): counts the peaks and locks of the synchroniser over <seconds> of (a) noise only, (b) PRBS-15 data
without preamble (the signal the host sends), with the same threshold as the frame tests.     python3 /tmp/p501_sync_false.py <RX gain index> <seconds> <label>
Starts when /tmp/go_f appears; prints one F line: symbols, peaks, hits, false, locks, losses, late."""
import sys, time, os
import numpy as np
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_qpsk_trx_sync')
from pynq import Overlay
import p501_radio
from p501_qpsk_rx_sync import P501QpskRxSync, REG
RX_GAIN = int(sys.argv[1]); SECONDS = float(sys.argv[2]); LABEL = sys.argv[3] if len(sys.argv) > 3 else "?"
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_qpsk_trx_sync/p501_qpsk_trx_sync.bit')
rx = P501QpskRxSync(ol.qpsk_rx)
ad = p501_radio.bring_up(ol, lo_hz=915_000_000, tx_atten_db=89.75, rx_gain_index=RX_GAIN)
rx.stop()
try:
    ad.set_tx_atten_db(89.75); print("WAITING for /tmp/go_f", flush=True)
    while not os.path.exists('/tmp/go_f'): time.sleep(0.01)
    os.remove('/tmp/go_f')
    rx.configure(timing_bw=2 * np.pi / 100, phase_bw=2 * np.pi / 100); rx.configure_sync(fl=1024, pl=960); rx.gate_enable(True); rx.start()
    time.sleep(0.2); y0 = rx.sync_status(); s0 = rx.stats(); time.sleep(SECONDS); y1 = rx.sync_status(); s1 = rx.stats()
    d = lambda k: y1[k] - y0[k]
    print("F %s: %.0f s, %.1f M symbols: peaks %d (one per %.1f M symbols), hits %d, false %d, locks %d, losses %d, late %d, AGC gain %.1f" % (
          LABEL, SECONDS, (s1["symbols"] - s0["symbols"]) / 1e6, d("peaks"), (s1["symbols"] - s0["symbols"]) / 1e6 / max(d("peaks"), 1), d("hits"), d("false"), d("locks"), d("lost"), y1["late"], s1["agc_gain"]), flush=True)
finally:
    rx.gate_enable(False); rx.stop(); p501_radio.quiet(ad, 89.75); print("DONE", flush=True)
