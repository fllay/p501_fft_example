"""Does the quality of the OFDM link change from one AD9361 bring-up to the next (the analog TX / RX state is random after every start, as in the bring-up report)? P501 to P501 at one TX attenuation, the bring-up repeated N times.
    python3 /tmp/p501_ofdm_bringups.py /tmp/ofdm_frame.npy <RX gain index> <TX attenuation> <N>"""
import os, sys, time
import numpy as np
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_ofdm')
from pynq import Overlay, allocate
from axi_dmac import AxiDmac
import p501_radio
from p501_ofdm_rx import P501OfdmRx
frame = np.load(sys.argv[1]); RX_GAIN = int(sys.argv[2]); ATT = float(sys.argv[3]); N = int(sys.argv[4]); LEVEL = 500.0
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_ofdm/p501_ofdm_rx_%s.bit' % os.environ.get('OFDM_VARIANT', 'sc'))      # OFDM_VARIANT=sts: the 128-sample STS overlay
rx = P501OfdmRx(ol.ofdm_rx); txd = AxiDmac(ol.axi_ad9361_dac_dma)
k = LEVEL * 16.0 / np.sqrt(np.mean(np.abs(frame) ** 2)) * np.sqrt(28 / 64)
buf = allocate(shape=(len(frame) * 2,), dtype=np.int16)
buf[0::2] = np.clip(np.round(frame.real * k), -32767, 32767).astype(np.int16); buf[1::2] = np.clip(np.round(frame.imag * k), -32767, 32767).astype(np.int16); buf.flush()
try:
    for i in range(N):
        rx.stop(); txd.stop()
        ad = p501_radio.bring_up(ol, lo_hz=915_000_000, tx_atten_db=89.75, rx_gain_index=RX_GAIN); p501_radio.loopback(ad, False)
        ad.set_tx_atten_db(ATT); txd.transfer_from_memory(buf.physical_address, buf.nbytes, cyclic=True); time.sleep(0.2)
        rx.configure(); rx.start(continuous=True, capture=False); ok = rx.wait_frames(3, timeout_s=3.0); time.sleep(0.3); s0 = rx.stats(); time.sleep(2.0); s = rx.stats(); d = lambda q: s[q] - s0[q]
        print("B bring-up %d: frames %d bad %d symbol errors %d of %d (SER %.2e) | EVM %.1f dB SNR %.1f dB level %.0f counts" % (i, d("frames"), d("bad_frames"), d("tot_err"), d("tot_sym"), d("tot_err") / max(d("tot_sym"), 1), s["evm_db"], s["snr_db"], s["level_counts"]), flush=True)
finally:
    rx.stop(); txd.stop(); p501_radio.quiet(ad, 89.75); buf.freebuffer(); print("DONE (TX attenuation 89.75 dB)")
