"""First board test of the OFDM receiver (run on the board as root; overlay p501_ofdm_rx_sc): the host's frame (make_ofdm_frame.py) goes out through the DAC DMA as a cyclic buffer, the AD9361's digital loopback returns it,
the receiver finds the frame, estimates the carrier and the channel, decodes the 44 data symbols and counts symbol and bit errors against the PRBS-15 payload.
    python3 /tmp/p501_ofdm_loopback.py /tmp/ofdm_frame.npy [adc rms counts list, e.g. 300,150,600]
The level is set by the amplitude of the buffer: the DAC takes 16-bit values (12 bit, left-justified), so an ADC level of R counts needs about 16 R rms in the buffer. The test ends with the DMA stopped, the loopback off and the TX attenuation at its maximum."""
import sys, time
import numpy as np
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_ofdm')
from pynq import Overlay, allocate
from axi_dmac import AxiDmac
import p501_radio
from p501_ofdm_rx import P501OfdmRx
frame = np.load(sys.argv[1]) if len(sys.argv) > 1 else np.load('/tmp/ofdm_frame.npy')
levels = [float(v) for v in sys.argv[2].split(",")] if len(sys.argv) > 2 else [300.0, 100.0, 600.0]
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_ofdm/p501_ofdm_rx_sc.bit')
rx = P501OfdmRx(ol.ofdm_rx); txd = AxiDmac(ol.axi_ad9361_dac_dma)
ad = p501_radio.bring_up(ol, lo_hz=915_000_000, tx_atten_db=89.75, rx_gain_index=45)
rx.stop()
print("READY bring_up_ok=%s rx id=0x%08X" % (ad.info["ok"], rx.ip.read(0)), flush=True)
try:
    p501_radio.loopback(ad, True); ad.set_tx_atten_db(89.75)                       # digital loopback: nothing is radiated
    for lvl in levels:
        k = lvl * 16.0 / np.sqrt(np.mean(np.abs(frame) ** 2))                                        # DAC buffer scale: lvl counts at the ADC (the frame's rms is sqrt(28/64))
        buf = allocate(shape=(len(frame) * 2,), dtype=np.int16)
        buf[0::2] = np.clip(np.round(frame.real * k * np.sqrt(28 / 64)), -32767, 32767).astype(np.int16); buf[1::2] = np.clip(np.round(frame.imag * k * np.sqrt(28 / 64)), -32767, 32767).astype(np.int16)
        buf.flush(); txd.stop(); txd.transfer_from_memory(buf.physical_address, buf.nbytes, cyclic=True); time.sleep(0.05)
        rx.stop(); rx.configure(); rx.start(continuous=True, capture=True)
        ok = rx.wait_frames(3, timeout_s=2.0); time.sleep(0.3); s0 = rx.stats()
        time.sleep(2.0); s = rx.stats()                                                              # the steady state: the counters are cumulative, so look at the differences over 2 s
        d = lambda k: s[k] - s0[k]
        print("L level %5.0f counts (buffer): in 2 s frames %d (about 2000 expected), found %d, rejected %d, bad frames %d, symbol errors %d of %d (SER %.2e), bit errors %d" %
              (lvl, d("frames"), d("found"), d("rejected"), d("bad_frames"), d("tot_err"), d("tot_sym"), d("tot_err") / max(d("tot_sym"), 1), d("tot_bit")), flush=True)
        print("L   last frame: EVM %.1f dB SNR %.1f dB carrier %+.0f Hz (coarse %+.0f) gain %.2f = level %.0f counts s0 %d | late %d status: ovf %s fft_ovf %s overrun %s" %
              (s["evm_db"], s["snr_db"], s["carrier_hz"], s["carrier_coarse_hz"], s["gain"], s["level_counts"], s["s0"], s["late_count"], s["ovf"], s["fft_ovf"], s["overrun"]), flush=True)
        if s["capture_done"]:
            np.save("/tmp/ofdm_cap_%d.npy" % int(lvl), rx.capture()); k_, h = rx.channel(); np.save("/tmp/ofdm_h_%d.npy" % int(lvl), h)
        buf.freebuffer()
finally:
    rx.stop(); txd.stop(); p501_radio.loopback(ad, False); p501_radio.quiet(ad, 89.75)
    print("DONE (receiver stopped, DMA stopped, loopback off, TX attenuation 89.75 dB)")
