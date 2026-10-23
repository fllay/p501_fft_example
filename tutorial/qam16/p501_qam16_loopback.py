"""First board test of the 16-QAM receiver (run on the board as root; overlay p501_qam16_trx): the FPGA frame transmitter sends frames, the AD9361's digital loopback returns them, the receiver
(FLL, polyphase / timing, power AGC, ZC synchroniser, PLL, slicer) locks on them and counts symbol and bit errors against the PRBS-15 payload. Then over the air (TX1 -> RX1 antennas, optional).
    python3 /tmp/p501_qam16_loopback.py <RX gain index> [air [attenuations, e.g. 20,24,28,32]]
Every run ends with the transmitter off, the loopback off and the TX attenuation at its maximum. The soft symbols of each step are saved in /tmp/qam16_cap_*.npy."""
import sys, time, os
import numpy as np
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_qam16')
from pynq import Overlay
import p501_radio
from p501_qam16_rx import P501Qam16Rx, P501Qam16Tx
RX_GAIN = int(sys.argv[1]) if len(sys.argv) > 1 else 45
AIR = len(sys.argv) > 2 and sys.argv[2] == "air"
AIR_ATTENS = [float(v) for v in sys.argv[3].split(",")] if len(sys.argv) > 3 else [20.0, 30.0, 40.0]       # TX attenuations (dB) of the air test; 20 dB is the strongest signal
FS = 3_840_000
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_qam16/p501_qam16_trx.bit')
tx = P501Qam16Tx(ol.qpsk_regs, FS); rx = P501Qam16Rx(ol.qam16_rx)
ad = p501_radio.bring_up(ol, lo_hz=915_000_000, tx_atten_db=89.75, rx_gain_index=RX_GAIN)
tx.off(); rx.stop()
print("READY bring_up_ok=%s rx id=0x%08X" % (ad.info["ok"], rx.ip.read(0)), flush=True)


def report(tag, secs=1.0):
    s0 = rx.stats(); time.sleep(secs); s1 = rx.stats()
    d = lambda k: s1[k] - s0[k]
    sc = d("sym_cnt"); se = d("sym_err")
    try:
        z = rx.capture(); np.save("/tmp/qam16_cap_%s.npy" % tag.replace(" ", "_"), z)
        lev = np.array([-3, -1, 1, 3]) / np.sqrt(10)
        ev = np.sqrt(np.mean(np.min(np.abs(z.real[:, None] - lev[None, :]), axis=1) ** 2 + np.min(np.abs(z.imag[:, None] - lev[None, :]), axis=1) ** 2))
    except TimeoutError:
        ev = float("nan")
    print("R %-22s locked=%s frames %5d (+%d) SER %.2e (%d of %d) BER %.2e EVM %.1f dB (soft %.1f dB) bad %d | gain %.1f ppm %+.1f | lock w %+.0f Hz PLL %+.0f Hz FLL %+.0f Hz | peaks %d locks %d hits %d miss %d lost %d late %d/%d/%d ev %d/%d ovr %d" %
          (tag, s1["locked"], s1["frames"], d("frames"), (se / sc if sc else float("nan")), se, sc, (d("bit_err") / (4 * sc) if sc else float("nan")), s1["evm_db"], 20 * np.log10(max(ev, 1e-9)), s1["bad_frames"],
           s1["agc_gain"], s1["clock_offset_ppm"], s1["lock_w_hz"], s1["pll_hz"], s1["fll_hz"], s1["peaks"], s1["locks"], s1["hits"], s1["misses"], s1["lost"], s1["sy_late"], s1["ev_late"], s1["ev_over"], s1["fll_late"], s1["engine_overruns"], s1["engine_overruns"]), flush=True)
    return s1


try:
    if not AIR:
        p501_radio.loopback(ad, True); ad.set_tx_atten_db(20.0)
        for amp in (0.25, 0.15, 0.4):
            tx.off(); rx.stop(); time.sleep(0.05)
            tx.start(amp=amp); time.sleep(0.05)
            t0 = time.time(); r = rx.acquire(); dt = time.time() - t0
            print("A amp %.2f: acquire locked=%s in %.3f s, FLL %+.0f Hz" % (amp, r["locked"], r["seconds"], r["fll_hz"]), flush=True)
            time.sleep(0.2); report("loopback amp %.2f" % amp, 1.0); report("loopback amp %.2f later" % amp, 2.0)
    else:
        p501_radio.loopback(ad, False)
        for att in AIR_ATTENS:
            ad.set_tx_atten_db(att); tx.off(); rx.stop(); time.sleep(0.05)
            tx.start(amp=0.25); time.sleep(0.05)
            r = rx.acquire()
            print("A air atten %.0f: acquire locked=%s in %.3f s, FLL %+.0f Hz" % (att, r["locked"], r["seconds"], r["fll_hz"]), flush=True)
            time.sleep(0.2); report("air atten %.0f" % att, 2.0)
finally:
    tx.off(); rx.stop(); p501_radio.loopback(ad, False); p501_radio.quiet(ad, 89.75)
    print("DONE (transmitter off, loopback off, TX attenuation 89.75 dB)", flush=True)
