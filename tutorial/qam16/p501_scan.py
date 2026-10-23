"""P501 as a spectrum scanner (run on the board as root, overlay p501_fft which has the ADC DMA): the AD9361 receive LO is stepped over a band, a contiguous ADC capture is taken at every step at a fixed gain, and all of them are saved
in /tmp/scan_<tag>.npz (lo_hz, samples) for analyse_scan.py. The transmitter stays at its maximum attenuation. Nothing is transmitted.
    python3 /tmp/p501_scan.py <tag> <start MHz> <stop MHz> <step MHz> <RX gain index> [blocks of 8192 samples]"""
import sys, time
import numpy as np
from pynq import Overlay, allocate
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds')
from axi_dmac import AxiDmac
import p501_radio

TAG = sys.argv[1]; F0, F1, DF = (float(v) * 1e6 for v in sys.argv[2:5]); GAIN = int(sys.argv[5]); BLOCKS = int(sys.argv[6]) if len(sys.argv) > 6 else 32
N = 8192
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_fft/p501_fft.bit')
ad = p501_radio.bring_up(ol, lo_hz=int(F0), tx_atten_db=89.75, rx_gain_index=GAIN)
print("bring_up_ok=%s" % ad.info["ok"], flush=True)
try:
    p501_radio.loopback(ad, False)
    rxd = AxiDmac(ol.axi_ad9361_adc_dma)
    los, data = [], []
    for lo in np.arange(F0, F1 + DF / 2, DF):
        ok = ad.set_rx_lo_freq(int(lo)); time.sleep(0.05)
        buf = allocate(shape=(N * BLOCKS * 2,), dtype=np.int16)
        okd = rxd.transfer_to_memory(buf.physical_address, buf.nbytes, timeout_s=10.0); buf.invalidate()
        a = np.array(buf); buf.freebuffer()
        x = (a[0::2].astype(np.float32) + 1j * a[1::2].astype(np.float32)).astype(np.complex64)
        los.append(lo); data.append(x)
        print("%.1f MHz lock=%s dma=%s rms %.1f counts" % (lo / 1e6, ok, okd, np.sqrt(np.mean(np.abs(x) ** 2))), flush=True)
    np.savez("/tmp/scan_%s.npz" % TAG, lo_hz=np.array(los), x=np.array(data))
finally:
    p501_radio.quiet(ad, 89.75)
    print("DONE (TX attenuation 89.75 dB)")
