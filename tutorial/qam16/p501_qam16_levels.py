"""P501 side of the B210 -> P501 16-QAM test (run on the board as root; overlay p501_qam16_trx): the B210 (run_qam16_b210.py on the host) transmits 16-QAM frames at 915.0 MHz (the natural +9.7 kHz offset of the
two radios, no hint), the P501's own transmitter stays off. For every level k the host changes the B210 TX gain and releases it with /tmp/go_<k>; the receiver then starts from cold (rx.acquire(): FLL acquiring then tracking,
the lock follows the synchroniser) and counts for <seconds>: frames, symbol / bit errors against the PRBS-15 payload, EVM, the AGC gain, the carrier from the FLL and the PLL, the synchroniser's counters.
    python3 /tmp/p501_qam16_levels.py <RX gain index> <levels> <seconds per level>
/tmp/rx_gain (optional, written by the host before the release) sets another RX gain index for the level; /tmp/tx_gain only labels the output. The TX attenuation stays at its maximum: the P501 does not transmit."""
import sys, time, os
import numpy as np
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_qam16')
from pynq import Overlay
import p501_radio
from p501_qam16_rx import P501Qam16Rx
RX_GAIN = int(sys.argv[1]) if len(sys.argv) > 1 else 70
LEVELS = int(sys.argv[2]) if len(sys.argv) > 2 else 1
SECONDS = float(sys.argv[3]) if len(sys.argv) > 3 else 3.0
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_qam16/p501_qam16_trx.bit')
rx = P501Qam16Rx(ol.qam16_rx)
ad = p501_radio.bring_up(ol, lo_hz=915_000_000, tx_atten_db=89.75, rx_gain_index=RX_GAIN)
rx.stop()
print("READY bring_up_ok=%s id=0x%08X" % (ad.info["ok"], rx.ip.read(0)), flush=True)


def wait_go(k):
    while not os.path.exists('/tmp/go_%d' % k): time.sleep(0.01)
    os.remove('/tmp/go_%d' % k)


def report(tag, secs):
    s0 = rx.stats(); time.sleep(secs); s1 = rx.stats()
    d = lambda k: s1[k] - s0[k]
    sc, se = d("sym_cnt"), d("sym_err")
    try:
        z = rx.capture(); np.save("/tmp/qam16_cap_%s.npy" % tag.replace(" ", "_"), z)
        lev = np.array([-3, -1, 1, 3]) / np.sqrt(10)
        ev = np.sqrt(np.mean(np.min(np.abs(z.real[:, None] - lev[None, :]), axis=1) ** 2 + np.min(np.abs(z.imag[:, None] - lev[None, :]), axis=1) ** 2))
    except TimeoutError:
        ev = float("nan")
    print("R %-12s locked=%s frames %5d (+%d of %.0f) SER %.2e (%d of %d) BER %.2e EVM %.1f dB (soft %.1f dB) bad %d | AGC gain %.1f clock %+.1f ppm | lock w %+.0f Hz PLL %+.0f Hz FLL %+.0f Hz => offset %+.0f Hz | peaks %d locks %d hits %d miss %d lost %d | late sy %d ev %d fll %d ovr %d" %
          (tag, s1["locked"], s1["frames"], d("frames"), secs * 960e3 / 967, (se / sc if sc else float("nan")), se, sc, (d("bit_err") / (4 * sc) if sc else float("nan")), s1["evm_db"], 20 * np.log10(max(ev, 1e-9)), s1["bad_frames"],
           s1["agc_gain"], s1["clock_offset_ppm"], s1["lock_w_hz"], s1["pll_hz"], s1["fll_hz"], s1["pll_hz"] - s1["fll_hz"], s1["peaks"], s1["locks"], s1["hits"], s1["misses"], s1["lost"], s1["sy_late"], s1["ev_late"], s1["fll_late"], s1["engine_overruns"]), flush=True)
    return s1


try:
    ad.set_tx_atten_db(89.75); p501_radio.loopback(ad, False)
    print("WAITING for /tmp/go_0", flush=True)
    for k in range(LEVELS):
        wait_go(k)
        g = open('/tmp/tx_gain').read().strip() if os.path.exists('/tmp/tx_gain') else "?"
        if os.path.exists('/tmp/rx_gain'):
            rg = int(open('/tmp/rx_gain').read().strip()); ad.set_rx_manual_gain(rg); time.sleep(0.05)
        else: rg = RX_GAIN
        rx.stop(); time.sleep(0.05)
        r = rx.acquire(timeout_s=2.0)
        print("A B210 TX gain %s dB, RX gain index %d: acquire locked=%s in %.3f s (FLL %+.0f Hz)" % (g, rg, r["locked"], r["seconds"], r["fll_hz"]), flush=True)
        time.sleep(0.3)
        report("tx%s" % g, SECONDS)
        print("LEVEL_DONE %d" % k, flush=True)
finally:
    rx.stop(); p501_radio.quiet(ad, 89.75)
    print("DONE (receiver stopped, TX attenuation 89.75 dB)", flush=True)
