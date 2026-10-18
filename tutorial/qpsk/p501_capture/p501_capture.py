"""P501 side of chapter 4b (run on the board as root, with the combined FFT+DDS overlay copied to /home/xilinx/jupyter_notebooks/p501_fft_dds/):
brings the AD9361 up at 915 MHz, receive only (TX fully attenuated, DDS off), waits for the file /tmp/go, then records SECONDS of raw I/Q
(3.84 MSPS) with the ADC DMA into /tmp/p501_cap.i16 (interleaved int16 I,Q, 4 bytes per sample). One DMA transfer is limited to 16 MiB: at most 1.09 s."""
import sys, time, os
import numpy as np
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds')
from pynq import Overlay, allocate
import p501_radio
from p501_dds import P501Dds
from axi_dmac import AxiDmac

SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
RX_GAIN = int(sys.argv[2]) if len(sys.argv) > 2 else 70
FS = 3_840_000
n = int(SECONDS * FS)
assert n * 4 <= 16 * 1024 * 1024, "one DMA transfer is limited to 16 MiB (1.09 s at 3.84 MSPS)"
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_fft_dds/p501_fft_dds.bit')
dds = P501Dds(ol.dds_regs, FS); rxd = AxiDmac(ol.axi_ad9361_adc_dma)
ad = p501_radio.bring_up(ol, lo_hz=915_000_000, tx_atten_db=89.75, rx_gain_index=RX_GAIN)       # receive only
dds.off()
buf = allocate(shape=(n * 2,), dtype=np.int16)
print("READY bring_up_ok=%s" % ad.info["ok"], flush=True)
t0 = time.time()
while not os.path.exists('/tmp/go'):
    if time.time() - t0 > 300: print("TIMEOUT", flush=True); sys.exit(1)
    time.sleep(0.01)
os.remove('/tmp/go')
ok = rxd.transfer_to_memory(buf.physical_address, buf.nbytes, timeout_s=10.0)
buf.invalidate()
a = np.array(buf)
a.tofile('/tmp/p501_cap.i16')
x = a[0::2].astype(float) + 1j * a[1::2].astype(float)
print("CAPTURED ok=%s samples=%d rms=%.1f peak=%d (full scale 2047)" % (ok, n, np.sqrt(np.mean(np.abs(x) ** 2)), int(np.max(np.abs(a)))), flush=True)
print("DONE", flush=True)
