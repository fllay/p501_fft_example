"""Raw ADC capture of the P501 receiver (run on the board as root; overlay p501_fft, which has the ADC DMA): the AD9361 is brought up at the given LO and RX gain, the transmitter stays at its
maximum attenuation, and N_BLOCKS x 8192 complex samples in ONE contiguous DMA transfer (3.84 MSPS, I/Q as 12-bit values in int16) are written to /tmp/adc_<tag>.npy for the host to analyse (analyse_adc.py).
    python3 /tmp/p501_adc_capture.py <tag> <RX gain index> <LO Hz> <blocks>
Run it once with the interferer / transmitter off (the noise floor of the receive path) and once with the B210 transmitting (signal + whatever else is there)."""
import sys
import numpy as np
from pynq import Overlay, allocate
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds')
from axi_dmac import AxiDmac
import p501_radio

TAG = sys.argv[1] if len(sys.argv) > 1 else "x"
RX_GAIN = int(sys.argv[2]) if len(sys.argv) > 2 else 70
LO = int(float(sys.argv[3])) if len(sys.argv) > 3 else 915_000_000
BLOCKS = int(sys.argv[4]) if len(sys.argv) > 4 else 32
N = 8192

ol = Overlay('/home/xilinx/jupyter_notebooks/p501_fft/p501_fft.bit')
ad = p501_radio.bring_up(ol, lo_hz=LO, tx_atten_db=89.75, rx_gain_index=RX_GAIN)
print("bring_up_ok=%s" % ad.info["ok"], flush=True)
try:
    p501_radio.loopback(ad, False)
    rxd = AxiDmac(ol.axi_ad9361_adc_dma)
    buf = allocate(shape=(N * BLOCKS * 2,), dtype=np.int16)           # one DMA transfer: the capture is contiguous (separate transfers leave gaps between the blocks)
    ok = rxd.transfer_to_memory(buf.physical_address, buf.nbytes, timeout_s=10.0)
    buf.invalidate()
    a = np.array(buf); buf.freebuffer()
    if not ok:
        print("DMA timeout")
    x = (a[0::2].astype(np.float32) + 1j * a[1::2].astype(np.float32)).astype(np.complex64)
    np.save("/tmp/adc_%s.npy" % TAG, x)
    print("saved /tmp/adc_%s.npy: %d samples, rms %.1f counts, peak %.0f" % (TAG, len(x), np.sqrt(np.mean(np.abs(x) ** 2)), np.abs(x.real).max()), flush=True)
finally:
    p501_radio.quiet(ad, 89.75)
    print("DONE (TX attenuation 89.75 dB)")
