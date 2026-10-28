"""Board test of the FPGA OFDM transmitter (run on the board as root; overlay p501_ofdm_trx_sc, or p501_ofdm_trx_sts with OFDM_VARIANT=sts): the transmitter in the PL makes the frame (no host frame, no DMA), the AD9361's digital loopback
returns it, the receiver finds the frame, decodes the 44 data symbols and counts symbol and bit errors against the PRBS-15 payload.
    python3 /tmp/p501_ofdm_txtest.py [amplitudes, e.g. 0.8,0.2,0.4] [seconds per amplitude, default 2]
Digital loopback: nothing is radiated. The test ends with the transmitter off, the loopback off and the TX attenuation at its maximum."""
import os, sys, time
import numpy as np
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_ofdm')
from pynq import Overlay
import p501_radio
from p501_ofdm_rx import P501OfdmRx
from p501_ofdm_tx import P501OfdmTx
amps = [float(v) for v in sys.argv[1].split(",")] if len(sys.argv) > 1 else [0.8, 0.2, 0.4]
SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
VAR = os.environ.get('OFDM_VARIANT', 'sc')
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_ofdm/p501_ofdm_trx_%s.bit' % VAR)
rx = P501OfdmRx(ol.ofdm_rx); tx = P501OfdmTx(ol.qpsk_regs, 3_840_000)
ad = p501_radio.bring_up(ol, lo_hz=850_000_000, tx_atten_db=89.75, rx_gain_index=45)
tx.stop(); rx.stop()
print("READY bring_up_ok=%s rx id=0x%08X tx regs id=0x%08X" % (ad.info["ok"], rx.ip.read(0), ol.qpsk_regs.read(0)), flush=True)
try:
    p501_radio.loopback(ad, True); ad.set_tx_atten_db(89.75)
    for amp in amps:
        tx.stop(); rx.stop(); time.sleep(0.05)
        tx.start(amp=amp); time.sleep(0.05)
        rx.configure(); rx.start(continuous=True, capture=True)
        ok = rx.wait_frames(3, timeout_s=2.0); time.sleep(0.3); s0 = rx.stats()
        time.sleep(SECS); s = rx.stats()
        d = lambda k: s[k] - s0[k]
        print("L amp %.2f (about %.0f counts at the ADC): in %.0f s frames %d (about %d expected), found %d, rejected %d, bad frames %d, symbol errors %d of %d (SER %.2e), bit errors %d" %
              (amp, tx.adc_counts(amp), SECS, d("frames"), 1000 * SECS, d("found"), d("rejected"), d("bad_frames"), d("tot_err"), d("tot_sym"), d("tot_err") / max(d("tot_sym"), 1), d("tot_bit")), flush=True)
        print("L   last frame: EVM %.1f dB SNR %.1f dB carrier %+.0f Hz gain %.2f = level %.0f counts s0 %d | late %d status: ovf %s fft_ovf %s overrun %s" %
              (s["evm_db"], s["snr_db"], s["carrier_hz"], s["gain"], s["level_counts"], s["s0"], s["late_count"], s["ovf"], s["fft_ovf"], s["overrun"]), flush=True)
finally:
    tx.stop(); rx.stop(); p501_radio.loopback(ad, False); p501_radio.quiet(ad, 89.75)
    print("DONE (transmitter off, receiver stopped, loopback off, TX attenuation 89.75 dB)")
