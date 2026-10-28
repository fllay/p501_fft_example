"""Over-the-air test of the FPGA OFDM transmitter, P501 to P501 (run on the board as root; overlay p501_ofdm_trx_sc, or p501_ofdm_trx_sts with OFDM_VARIANT=sts): the transmitter in the PL sends the frame through TX1 (850 MHz), the
receiver on RX1 decodes it. Antennas a few centimetres apart, or a cable with an attenuator. For every TX attenuation the counters are read over the window after the third frame. RADIATES: start with a large attenuation.
    python3 /tmp/p501_ofdm_txair.py <RX gain index> <attenuations, e.g. 30,26,22,20> [amp 0.9 [window seconds 4]]
amp is the digital amplitude of the transmitter (1.0 = 8034 counts rms at the DAC input, peaks 0.83 of full scale). Ends with the transmitter off and the TX attenuation at its maximum."""
import os, sys, time
import numpy as np
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_ofdm')
from pynq import Overlay
import p501_radio
from p501_ofdm_rx import P501OfdmRx
from p501_ofdm_tx import P501OfdmTx
RX_GAIN = int(sys.argv[1]); ATTS = [float(v) for v in sys.argv[2].split(",")]; AMP = float(sys.argv[3]) if len(sys.argv) > 3 else 0.9; WIN = float(sys.argv[4]) if len(sys.argv) > 4 else 4.0
VAR = os.environ.get('OFDM_VARIANT', 'sc')
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_ofdm/p501_ofdm_trx_%s.bit' % VAR)
rx = P501OfdmRx(ol.ofdm_rx); tx = P501OfdmTx(ol.qpsk_regs, 3_840_000)
ad = p501_radio.bring_up(ol, lo_hz=850_000_000, tx_atten_db=89.75, rx_gain_index=RX_GAIN)
tx.stop(); rx.stop(); p501_radio.loopback(ad, False)
print("READY bring_up_ok=%s rx id=0x%08X tx regs id=0x%08X" % (ad.info["ok"], rx.ip.read(0), ol.qpsk_regs.read(0)), flush=True)
try:
    for att in ATTS:
        tx.stop(); rx.stop(); ad.set_tx_atten_db(att); time.sleep(0.1); tx.start(amp=AMP); time.sleep(0.1)
        rx.configure(); rx.start(continuous=True, capture=True)
        ok = rx.wait_frames(3, timeout_s=3.0); time.sleep(0.3); s0 = rx.stats(); time.sleep(WIN); s = rx.stats(); d = lambda q: s[q] - s0[q]
        print("A atten %5.1f dB: locked %s | in %.0f s frames %d found %d rejected %d bad %d, symbol errors %d of %d (SER %.2e) bit errors %d | last frame: EVM %.1f dB SNR %.1f dB carrier %+.0f Hz level %.0f counts gain %.2f | late %d ovf %s/%s" %
              (att, ok, WIN, d("frames"), d("found"), d("rejected"), d("bad_frames"), d("tot_err"), d("tot_sym"), d("tot_err") / max(d("tot_sym"), 1), d("tot_bit"), s["evm_db"], s["snr_db"], s["carrier_hz"], s["level_counts"], s["gain"], s["late_count"], s["ovf"], s["fft_ovf"]), flush=True)
finally:
    tx.stop(); rx.stop(); p501_radio.quiet(ad, 89.75)
    print("DONE (transmitter off, receiver stopped, TX attenuation 89.75 dB)")
