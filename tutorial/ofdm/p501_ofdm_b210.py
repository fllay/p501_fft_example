"""P501 side of the B210 -> P501 OFDM test (run on the board as root; overlay p501_ofdm_rx_sc): the B210 transmits the OFDM frames (ofdm_frame_tx.py on the host) at 915.0 MHz (the natural carrier offset of the two radios, no hint),
the P501's own transmitter stays off. N windows of W seconds: the counters as differences, EVM, SNR, the carrier word (the offset the receiver found), the level.
    python3 /tmp/p501_ofdm_b210.py <RX gain index> [windows 10 [seconds 2]]"""
import os, sys, time
import numpy as np
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_ofdm')
from pynq import Overlay
import p501_radio
from p501_ofdm_rx import P501OfdmRx
RX_GAIN = int(sys.argv[1]) if len(sys.argv) > 1 else 70; NW = int(sys.argv[2]) if len(sys.argv) > 2 else 10; W = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
LO = int(float(sys.argv[4])) if len(sys.argv) > 4 else 915_000_000      # must equal the B210 --freq
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_ofdm/p501_ofdm_rx_%s.bit' % os.environ.get('OFDM_VARIANT', 'sc'))      # OFDM_VARIANT=sts: the 128-sample STS overlay
rx = P501OfdmRx(ol.ofdm_rx)
ad = p501_radio.bring_up(ol, lo_hz=LO, tx_atten_db=89.75, rx_gain_index=RX_GAIN)
rx.stop(); p501_radio.loopback(ad, False)
print("READY bring_up_ok=%s rx id=0x%08X (RX gain index %d)" % (ad.info["ok"], rx.ip.read(0), RX_GAIN), flush=True)
try:
    rx.configure(); rx.start(continuous=True, capture=True); time.sleep(0.5)
    for i in range(NW):
        s0 = rx.stats(); time.sleep(W); s = rx.stats(); d = lambda q: s[q] - s0[q]
        print("W %2d: frames %5d found %5d rejected %5d bad %5d | symbol errors %7d of %8d (SER %.2e) | last frame: EVM %6.1f dB SNR %5.1f dB carrier %+7.0f Hz (coarse %+7.0f) level %5.0f counts gain %6.2f | late %d ovf %s/%s" %
              (i, d("frames"), d("found"), d("rejected"), d("bad_frames"), d("tot_err"), d("tot_sym"), d("tot_err") / max(d("tot_sym"), 1), s["evm_db"], s["snr_db"], s["carrier_hz"], s["carrier_coarse_hz"], s["level_counts"], s["gain"], s["late_count"], s["ovf"], s["fft_ovf"]), flush=True)
    if rx.stats()["capture_done"]:
        np.save("/tmp/ofdm_b210_cap.npy", rx.capture()); k, h = rx.channel(); np.save("/tmp/ofdm_b210_h.npy", h)
finally:
    rx.stop(); p501_radio.quiet(ad, 89.75); print("DONE (receiver stopped, TX attenuation 89.75 dB)")
