"""P501 side of the frame-receiver test (run on the board as root; overlay p501_qpsk_trx_sync): brings the AD9361 up at 915 MHz, waits for /tmp/go, then transmits FRAMES
(64-symbol m-sequence preamble + payload symbols of PRBS-15, generated in the FPGA) for HOLD seconds and ends quiet (transmitter off, TX attenuation at its maximum).

    python3 /tmp/p501_frame_tx.py <TX attenuation dB> <amplitude 0..1> <hold seconds> <payload symbols>

The overlay (p501_qpsk_trx_sync.bit / .hwh) and p501_radio.py are expected in /home/xilinx/jupyter_notebooks/p501_qpsk_trx_sync/ and .../p501_fft_dds/."""
import sys, time, os
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_qpsk_trx_sync')
from pynq import Overlay
import p501_radio
from p501_qpsk import P501QpskTxFrames

ATTEN = float(sys.argv[1]) if len(sys.argv) > 1 else 40.0
AMP = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
HOLD = float(sys.argv[3]) if len(sys.argv) > 3 else 12.0
PL = int(sys.argv[4]) if len(sys.argv) > 4 else 960
FS = 3_840_000
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_qpsk_trx_sync/p501_qpsk_trx_sync.bit')
tx = P501QpskTxFrames(ol.qpsk_regs, FS)
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
    tx.start_frames(payload=PL, amp=AMP)
    print("TX_ON atten %.1f dB amp %.2f frames of %d symbols (payload %d)" % (ATTEN, AMP, PL + 64, PL), flush=True)
    time.sleep(HOLD)
finally:
    tx.off(); p501_radio.quiet(ad, 89.75)
    print("DONE (transmitter off, TX attenuation 89.75 dB)", flush=True)
