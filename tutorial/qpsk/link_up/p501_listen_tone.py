"""P501 side of the B210 -> P501 test (run on the board as root, combined FFT+DDS overlay): brings the AD9361 up at 915 MHz with
TX fully attenuated and the DDS off (receive only, RX gain index 70 for weak signals), waits for /tmp/go, then prints one JSON line
per reading for 42 s: the strongest line 300-700 kHz from the LO, in the FPGA FFT chain (3.75 kHz bins) and in a 64k-point FFT of a raw capture.
"""
import sys, time, os, json
import numpy as np
sys.path.insert(0,'/home/xilinx/jupyter_notebooks'); sys.path.insert(0,'/home/xilinx/jupyter_notebooks/p501_fft_dds')
from pynq import Overlay, allocate
import p501_radio
from p501_dds import P501Dds
from p501_fft import P501Fft
from axi_dmac import AxiDmac
FS = 3_840_000
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_fft_dds/p501_fft_dds.bit')
dds = P501Dds(ol.dds_regs, FS); fft = P501Fft(ol.fft_dma, 10, FS); rxd = AxiDmac(ol.axi_ad9361_adc_dma)
ad = p501_radio.bring_up(ol, lo_hz=915_000_000, tx_atten_db=89.75, rx_gain_index=70)     # TX stays fully attenuated, DDS off: this side only listens; high RX gain for weak signals
dds.off()
N = 1 << 16
buf = allocate(shape=(N * 2,), dtype=np.int16)
win = np.hanning(N); fr = np.fft.fftshift(np.fft.fftfreq(N, 1 / FS)); band = (np.abs(fr) > 300e3) & (np.abs(fr) < 700e3)
fb = (np.abs(fft.freqs) > 300e3) & (np.abs(fft.freqs) < 700e3)
print("READY bring_up_ok=%s" % ad.info["ok"], flush=True)
t0 = time.time()
while not os.path.exists('/tmp/go'):
    if time.time() - t0 > 240: print("TIMEOUT", flush=True); sys.exit(1)
    time.sleep(0.02)
os.remove('/tmp/go'); tg = time.time()
while time.time() - tg < 42:
    t = time.time() - tg
    avg = fft.average(16); db = fft.db(avg); i = int(np.argmax(np.where(fb, db, -999)))
    hw = (float(fft.freqs[i]), float(db[i] - np.median(db)))
    rxd.transfer_to_memory(buf.physical_address, buf.nbytes); buf.invalidate()
    a = np.array(buf); x = a[0::2].astype(float) + 1j * a[1::2].astype(float); x -= x.mean()
    m = 20 * np.log10(np.abs(np.fft.fftshift(np.fft.fft(x * win))) + 1e-9)
    j = int(np.argmax(np.where(band, m, -999))); p, q, r = m[j-1], m[j], m[j+1]; d = p - 2*q + r
    f = fr[j] + (0.5 * (p - r) / d if d else 0) * (FS / N)
    print(json.dumps({"t": round(t, 3), "hw_khz": hw[0] / 1e3, "hw_snr": hw[1], "raw_khz": f / 1e3, "raw_snr": float(q - np.median(m))}), flush=True)
print("DONE", flush=True)
