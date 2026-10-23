"""P501 side of the P501 -> B210 16-QAM test (run on the board as root; overlay p501_qam16_trx): brings the AD9361 up at 915 MHz, waits for /tmp/go, then transmits the 16-QAM frames of the FPGA
transmitter for HOLD seconds and ends quiet (transmitter off, TX attenuation at its maximum).
    python3 /tmp/p501_qam16_tx_only.py <TX attenuation dB> <amplitude 0..1> <hold seconds>
The overlay (p501_qam16_trx.bit / .hwh), p501_qam16_rx.py are expected in /home/xilinx/jupyter_notebooks/p501_qam16/ and p501_radio.py / p501_dds.py in .../p501_fft_dds/."""
import sys, time, os
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_qam16')
from pynq import Overlay
import p501_radio
from p501_qam16_rx import P501Qam16Tx

ATTEN = float(sys.argv[1]) if len(sys.argv) > 1 else 24.0
AMP = float(sys.argv[2]) if len(sys.argv) > 2 else 0.25
HOLD = float(sys.argv[3]) if len(sys.argv) > 3 else 12.0
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_qam16/p501_qam16_trx.bit')
tx = P501Qam16Tx(ol.qpsk_regs, 3_840_000)
ad = p501_radio.bring_up(ol, lo_hz=915_000_000, tx_atten_db=89.75)          # starts fully attenuated; the calibrations run quiet
tx.off()
print("READY bring_up_ok=%s" % ad.info["ok"], flush=True)
t0 = time.time()
while not os.path.exists('/tmp/go'):
    if time.time() - t0 > 300: print("TIMEOUT", flush=True); sys.exit(1)
    time.sleep(0.01)
os.remove('/tmp/go')
try:
    ad.set_tx_atten_db(ATTEN)
    tx.start(amp=AMP)
    print("TX_ON atten %.1f dB amp %.2f 16-QAM frames" % (ATTEN, AMP), flush=True)
    time.sleep(HOLD)
finally:
    tx.off(); p501_radio.quiet(ad, 89.75)
    print("DONE (transmitter off, TX attenuation 89.75 dB)", flush=True)
