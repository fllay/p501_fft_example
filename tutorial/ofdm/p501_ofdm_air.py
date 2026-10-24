"""Over-the-air test of the OFDM receiver, P501 to P501 (run on the board as root; overlay p501_ofdm_rx_sc): the host frame goes out through the DAC DMA into TX1 (915 MHz), the receiver on RX1 decodes it. Antennas a few
centimetres apart, or a cable with an attenuator. For every TX attenuation the counters are read over 2 s after the third frame. Ends with the DMA stopped and the TX attenuation at its maximum.
    python3 /tmp/p501_ofdm_air.py /tmp/ofdm_frame.npy <RX gain index> <attenuations, e.g. 20,30,40> [buffer level 500 [window seconds 2]]
The buffer level is the rms of the 16-bit DAC values divided by 16 (a level of 500 gives peaks of 0.84 of the DAC's full scale for the 10.7 dB peak-to-average ratio of the frame)."""
import sys, time
import numpy as np
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_ofdm')
from pynq import Overlay, allocate
from axi_dmac import AxiDmac
import p501_radio
from p501_ofdm_rx import P501OfdmRx
frame = np.load(sys.argv[1]); RX_GAIN = int(sys.argv[2]); ATTS = [float(v) for v in sys.argv[3].split(",")]; LEVEL = float(sys.argv[4]) if len(sys.argv) > 4 else 500.0; WIN = float(sys.argv[5]) if len(sys.argv) > 5 else 2.0
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_ofdm/p501_ofdm_rx_sc.bit')
rx = P501OfdmRx(ol.ofdm_rx); txd = AxiDmac(ol.axi_ad9361_dac_dma)
ad = p501_radio.bring_up(ol, lo_hz=915_000_000, tx_atten_db=89.75, rx_gain_index=RX_GAIN)
rx.stop(); p501_radio.loopback(ad, False)
print("READY bring_up_ok=%s rx id=0x%08X" % (ad.info["ok"], rx.ip.read(0)), flush=True)
k = LEVEL * 16.0 / np.sqrt(np.mean(np.abs(frame) ** 2)) * np.sqrt(28 / 64)
buf = allocate(shape=(len(frame) * 2,), dtype=np.int16)
buf[0::2] = np.clip(np.round(frame.real * k), -32767, 32767).astype(np.int16); buf[1::2] = np.clip(np.round(frame.imag * k), -32767, 32767).astype(np.int16); buf.flush()
try:
    txd.stop(); txd.transfer_from_memory(buf.physical_address, buf.nbytes, cyclic=True)
    for att in ATTS:
        ad.set_tx_atten_db(att); rx.stop(); time.sleep(0.2); rx.configure(); rx.start(continuous=True, capture=True)
        ok = rx.wait_frames(3, timeout_s=3.0); time.sleep(0.3); s0 = rx.stats(); time.sleep(WIN); s = rx.stats(); d = lambda q: s[q] - s0[q]
        print("A atten %5.1f dB: locked %s | in %.0f s frames %d found %d rejected %d bad %d, symbol errors %d of %d (SER %.2e) bit errors %d | last frame: EVM %.1f dB SNR %.1f dB carrier %+.0f Hz level %.0f counts gain %.2f | late %d ovf %s/%s" %
              (att, ok, WIN, d("frames"), d("found"), d("rejected"), d("bad_frames"), d("tot_err"), d("tot_sym"), d("tot_err") / max(d("tot_sym"), 1), d("tot_bit"), s["evm_db"], s["snr_db"], s["carrier_hz"], s["level_counts"], s["gain"], s["late_count"], s["ovf"], s["fft_ovf"]), flush=True)
        if s["capture_done"]:
            np.save("/tmp/ofdm_air_cap_%d.npy" % int(att), rx.capture()); kk, h = rx.channel(); np.save("/tmp/ofdm_air_h_%d.npy" % int(att), h)
finally:
    rx.stop(); txd.stop(); p501_radio.quiet(ad, 89.75); buf.freebuffer()
    print("DONE (receiver stopped, DMA stopped, TX attenuation 89.75 dB)")
