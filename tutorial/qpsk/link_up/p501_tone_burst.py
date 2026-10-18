"""P501 side of the link-up test (run on the board as root, with the combined FFT+DDS overlay copied to
/home/xilinx/jupyter_notebooks/p501_fft_dds/): brings the AD9361 up at 915 MHz with the TX attenuation at its maximum, waits for
the file /tmp/go, then sends a DDS tone at +500 kHz for 6 s at TX attenuation 80, 70 and 60 dB (3 s of silence in between) and
ends quiet. Very low power, short bursts: check that the frequency and power are permitted where you are before using antennas.
"""
import sys, time, os
sys.path.insert(0,'/home/xilinx/jupyter_notebooks'); sys.path.insert(0,'/home/xilinx/jupyter_notebooks/p501_fft_dds')
from pynq import Overlay
import p501_radio
from p501_dds import P501Dds
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_fft_dds/p501_fft_dds.bit')
dds = P501Dds(ol.dds_regs, 3_840_000)
ad = p501_radio.bring_up(ol, lo_hz=915_000_000, tx_atten_db=89.75)      # starts fully quiet
print("READY bring_up_ok=%s" % ad.info["ok"], flush=True)
t0 = time.time()
while not os.path.exists('/tmp/go'):
    if time.time() - t0 > 240: print("TIMEOUT", flush=True); dds.off(); sys.exit(1)
    time.sleep(0.02)
os.remove('/tmp/go')
try:
    for a in (80, 70, 60):
        ad.set_tx_atten_db(a); dds.set(freq_hz=500e3, amp=0.5)
        print("ON  atten %d dB at %.2f" % (a, time.time()), flush=True); time.sleep(6)
        dds.off(); print("OFF at %.2f" % time.time(), flush=True); time.sleep(3)
finally:
    dds.off(); p501_radio.quiet(ad, 89.75)
    print("DONE (DDS off, TX attenuation 89.75 dB)", flush=True)
