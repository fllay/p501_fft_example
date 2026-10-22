"""All-FPGA test of the frame synchronisation (run on the board as root; overlay p501_qpsk_trx_sync with the framed transmitter): the FPGA transmitter sends frames, the FPGA receiver finds them.
    python3 /tmp/p501_sync_fpga.py <RX gain index> <payload symbols>
 1. digital loopback of the AD9361 (no antenna): hardware acquisition, then counting: frames found against the number sent, misses, the payload bit errors (gated), the frequency from the preamble;
    and the time from the start of the transmitter to the frame lock and to the receiver lock;
 2. over the air, TX1 antenna -> RX1 antenna a few centimetres apart, with the TX attenuation stepped up (weaker signal): hits, misses, false peaks, losses, payload BER.
Every run ends with the transmitter off, the loopback off and the TX attenuation at its maximum."""
import sys, time, os
import numpy as np
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_qpsk_trx_sync')
from pynq import Overlay
import p501_radio
from p501_qpsk import P501QpskTxFrames
from p501_qpsk_rx_sync import P501QpskRxSync, REG, SYMBOL_RATE, _signed
from p501_qpsk_rx import soft_quality
RX_GAIN = int(sys.argv[1]) if len(sys.argv) > 1 else 45
PL = int(sys.argv[2]) if len(sys.argv) > 2 else 960
FL = PL + 64; FS = 3_840_000
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_qpsk_trx_sync/p501_qpsk_trx_sync.bit')
tx = P501QpskTxFrames(ol.qpsk_regs, FS); rx = P501QpskRxSync(ol.qpsk_rx)
ad = p501_radio.bring_up(ol, lo_hz=915_000_000, tx_atten_db=89.75, rx_gain_index=RX_GAIN)
tx.off(); rx.stop()
print("READY bring_up_ok=%s rx id=0x%08X" % (ad.info["ok"], rx.ip.read(0)), flush=True)


def count(seconds):
    s0 = rx.stats(); y0 = rx.sync_status(); time.sleep(seconds); s1 = rx.stats(); y1 = rx.sync_status(); z = rx.capture()
    d = lambda k: y1[k] - y0[k]
    nb, nm = s1["bits"] - s0["bits"], s1["mismatches"] - s0["mismatches"]
    return dict(exp=seconds * SYMBOL_RATE / FL, hits=d("hits"), misses=d("misses"), false=d("false"), lost=d("lost"), bits=nb, mism=nm, ber=nm / 3.0 / max(nb, 1), spread=soft_quality(z)[1],
                f=y1["freq_hz"], om=rx._omega_hz(), q=y1["quality"], late=y1["late"], locked=y1["locked"])


try:
    # ---- 1. digital loopback
    p501_radio.loopback(ad, True); ad.set_tx_atten_db(20.0)
    for amp in (0.5, 0.25):
        tx.off(); r = rx.acquire_hw(fl=FL, pl=PL)   # the receiver starts first: nothing to find yet
        print("L amp %.2f: hardware acquisition with no transmitter: locked=%s, sync=%s (expected: not locked)" % (amp, r["locked"], r["sync_locked"]), flush=True)
        rx.stop(); time.sleep(0.05); rx.configure(timing_bw=2 * np.pi / 400, phase_bw=2 * np.pi / 400); rx.configure_sync(fl=FL, pl=PL); rx.configure_acquisition(load=1, nload=8, nsw=4); rx.gate_enable(True)
        rx.start(); time.sleep(0.2); t0 = time.time(); tx.start_frames(payload=PL, amp=amp); t1 = time.time(); ts = None; tl = None
        while time.time() - t1 < 1.0:
            if ts is None and rx.ip.read(REG["SY_STATUS"]) & 1: ts = (time.time() - t1) * 1e3
            if ts is not None and tl is None:
                try:
                    if rx.locked(0.01): tl = (time.time() - t1) * 1e3
                except TimeoutError: pass
            if ts is not None and tl is not None: break
        time.sleep(0.3); c = count(2.0)
        print("L amp %.2f: frame lock %.1f ms and receiver lock %.1f ms after the transmitter started | 2 s: frames %.0f sent, hits %d, misses %d, false %d, lost %d, late %d | payload bits %d mismatches %d (BER about %.1e) | frequency from the preamble %+.1f Hz, Costas %+.1f Hz, quality %.2f, spread %.1f deg" % (
              amp, ts if ts is not None else float("nan"), tl if tl is not None else float("nan"), c["exp"], c["hits"], c["misses"], c["false"], c["lost"], c["late"], c["bits"], c["mism"], c["ber"], c["f"], c["om"], c["q"], c["spread"]), flush=True)
    tx.off(); p501_radio.loopback(ad, False)
    # ---- 2. over the air, weaker and weaker
    for att in (20.0, 30.0, 40.0, 45.0, 50.0, 55.0, 60.0):
        tx.off(); ad.set_tx_atten_db(att); r = rx.acquire_hw(fl=FL, pl=PL, timeout_s=0.6)   # carrier acquisition needs a signal: start the transmitter first
        rx.stop(); tx.start_frames(payload=PL, amp=0.5); time.sleep(0.3)
        rx.configure(timing_bw=2 * np.pi / 400, phase_bw=2 * np.pi / 400); rx.configure_sync(fl=FL, pl=PL); rx.configure_acquisition(load=1, nload=8, nsw=4); rx.gate_enable(True); rx.start()
        ok = rx.wait_lock(1.0); time.sleep(0.4); c = count(2.0)
        print("A TX attenuation %.0f dB: frame sync locked=%s | 2 s: frames %.0f sent, hits %d, misses %d, false %d, lost %d | payload bits %d mismatches %d (BER about %.1e) | frequency from the preamble %+.0f Hz, Costas %+.0f Hz, quality %.2f, spread %.1f deg" % (
              att, ok, c["exp"], c["hits"], c["misses"], c["false"], c["lost"], c["bits"], c["mism"], c["ber"], c["f"], c["om"], c["q"], c["spread"]), flush=True)
finally:
    tx.off(); rx.configure_acquisition(load=0, nsw=0); rx.gate_enable(False); rx.stop(); p501_radio.loopback(ad, False); p501_radio.quiet(ad, 89.75)
    print("DONE (transmitter off, loopback off, TX attenuation 89.75 dB)", flush=True)
