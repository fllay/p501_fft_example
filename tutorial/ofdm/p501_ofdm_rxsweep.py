"""RX gain sweep of the OFDM receiver against a transmitter that stays on (run on the board as root; OFDM_VARIANT=sc|sts selects the overlay): one AD9361 bring-up, then for every RX gain index of the list
the counters over a window. The SNR of the link falls as the gain falls (the receiver noise is referred to a weaker signal), so one fixed transmitter gives a curve of error rate against SNR, and two overlays can be
compared with the same transmitter, the same antennas and the same bring-up state.
    OFDM_VARIANT=sts python3 /tmp/p501_ofdm_rxsweep.py <LO Hz, e.g. 850e6> <window seconds, e.g. 4> <index list, e.g. 50,40,36,32,28,24,20>"""
import os, sys, time
import numpy as np
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_ofdm')
from pynq import Overlay
import p501_radio
from p501_ofdm_rx import P501OfdmRx
LO = int(float(sys.argv[1])); W = float(sys.argv[2]); IDX = [int(v) for v in sys.argv[3].split(",")]
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_ofdm/p501_ofdm_rx_%s.bit' % os.environ.get('OFDM_VARIANT', 'sc'))      # OFDM_VARIANT=sts: the 128-sample STS overlay
rx = P501OfdmRx(ol.ofdm_rx)
ad = p501_radio.bring_up(ol, lo_hz=LO, tx_atten_db=89.75, rx_gain_index=IDX[0])
rx.stop(); p501_radio.loopback(ad, False)
print("READY bring_up_ok=%s rx id=0x%08X" % (ad.info["ok"], rx.ip.read(0)), flush=True)
try:
    rx.configure(); rx.start(continuous=True, capture=False)
    for g in IDX:
        ad.set_rx_manual_gain(g); time.sleep(0.6)
        s0 = rx.stats(); time.sleep(W); s = rx.stats(); d = lambda q: s[q] - s0[q]
        print("G index %2d: frames %5d found %5d rejected %5d bad %5d | symbol errors %7d of %8d (SER %.2e) | last frame: EVM %6.1f dB SNR %5.1f dB level %5.0f counts gain %6.2f | late %d ovf %s/%s" %
              (g, d("frames"), d("found"), d("rejected"), d("bad_frames"), d("tot_err"), d("tot_sym"), d("tot_err") / max(d("tot_sym"), 1), s["evm_db"], s["snr_db"], s["level_counts"], s["gain"], s["late_count"], s["ovf"], s["fft_ovf"]), flush=True)
finally:
    rx.stop(); p501_radio.quiet(ad, 89.75); print("DONE (receiver stopped, TX attenuation 89.75 dB)")
