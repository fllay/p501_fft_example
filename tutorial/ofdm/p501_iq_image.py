"""IQ image and distortion of the P501 TX1 -> RX1 path over the air (run on the board as root; overlay p501_fft: the base design's DAC DMA and ADC DMA).
The DAC DMA sends a complex tone at +f (a cyclic buffer, 3840 samples), the ADC captures it, the host measures the tone, its image at -f (the IQ imbalance of the transmitter and the receiver together), the DC and the harmonics:
    python3 /tmp/p501_iq_image.py <tag> <tone kHz, e.g. 120,480,840> <TX atten dB> <RX gain index> [LO Hz, default 850e6] [bring-ups, default 1] [amplitude, default 8000 = the rms of the OFDM buffer at level 500]
Writes /tmp/iq_<tag>_<bring-up>_<tone>.npy (the ADC samples). The transmitter is silent at the end (TX attenuation 89.75 dB)."""
import sys, time
import numpy as np
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds')
from pynq import Overlay, allocate
from axi_dmac import AxiDmac
import p501_radio
TAG = sys.argv[1]; TONES = [float(t) * 1e3 for t in sys.argv[2].split(",")]; ATT = float(sys.argv[3]); RXG = int(sys.argv[4])
LO = int(float(sys.argv[5])) if len(sys.argv) > 5 else 850_000_000; NB = int(sys.argv[6]) if len(sys.argv) > 6 else 1; AMP = float(sys.argv[7]) if len(sys.argv) > 7 else 8000.0
FS, N, BLOCKS = 3.84e6, 3840, 64
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_fft/p501_fft.bit'); txd = AxiDmac(ol.axi_ad9361_dac_dma); rxd = AxiDmac(ol.axi_ad9361_adc_dma)
for b in range(NB):
    ad = p501_radio.bring_up(ol, lo_hz=LO, tx_atten_db=89.75, rx_gain_index=RXG); p501_radio.loopback(ad, False)
    try:
        for f in TONES:
            n = np.arange(N); tone = AMP * np.exp(2j * np.pi * f * n / FS)                               # an integer number of periods in the buffer for f = multiples of 1 kHz
            buf = allocate(shape=(N * 2,), dtype=np.int16); buf[0::2] = np.round(tone.real).astype(np.int16); buf[1::2] = np.round(tone.imag).astype(np.int16); buf.flush()
            txd.stop(); txd.transfer_from_memory(buf.physical_address, buf.nbytes, cyclic=True); ad.set_tx_atten_db(ATT); time.sleep(0.3)
            cap = allocate(shape=(8192 * BLOCKS * 2,), dtype=np.int16); ok = rxd.transfer_to_memory(cap.physical_address, cap.nbytes, timeout_s=10.0); cap.invalidate()
            a = np.array(cap); x = (a[0::2].astype(np.float32) + 1j * a[1::2].astype(np.float32)).astype(np.complex64)
            np.save("/tmp/iq_%s_%d_%d.npy" % (TAG, b, int(f / 1e3)), x); cap.freebuffer()
            ad.set_tx_atten_db(89.75); txd.stop(); buf.freebuffer()
            print("bring-up %d tone %+.0f kHz: captured %d samples, rms %.1f counts, dma ok %s" % (b, f / 1e3, len(x), np.sqrt(np.mean(np.abs(x) ** 2)), ok), flush=True)
    finally:
        txd.stop(); p501_radio.quiet(ad, 89.75)
print("DONE (TX attenuation 89.75 dB)")
