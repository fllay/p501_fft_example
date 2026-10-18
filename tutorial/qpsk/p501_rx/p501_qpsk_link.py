"""P501 side of chapter 4d (run on the board as root): the FPGA transmitter and the FPGA receiver in one overlay (p501_qpsk_trx), with the AD9361 in digital loopback
or over the air (TX1 antenna -> RX1 antenna). Nothing but register writes and reads passes through Python.

    python3 /tmp/p501_qpsk_link.py <loopback|air|rx> <TX attenuation dB> <seconds> [<RX gain index> [<loop bandwidth divisor> [<initial frequency Hz> [<tracking divisor> [<acquisition ms>]]]]]

loopback / air: the FPGA transmitter feeds the FPGA receiver (digital loopback of the AD9361, or TX1 antenna -> RX1 antenna).
rx: only the receiver runs (the transmitter is the B210's GNU Radio, started first by the host script); it starts when /tmp/go appears.
Loop bandwidths are 2 pi / divisor rad per symbol (default 400) for the timing loop and the Costas loop. With a tracking divisor (7th argument) the receiver acquires
with the first bandwidth and switches both loops live to the narrower one after <acquisition ms> (8th argument, default 30).
Prints the receiver's statistics once per second and saves 1024 soft symbols to /tmp/p501_link_soft.npy. Every run ends with the transmitter off, the loopback off and the TX attenuation at its maximum."""
import sys, time, os
import numpy as np
sys.path.insert(0, '/home/xilinx/jupyter_notebooks'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_fft_dds'); sys.path.insert(0, '/home/xilinx/jupyter_notebooks/p501_qpsk_trx')
from pynq import Overlay
import p501_radio
from p501_qpsk import P501QpskTx
from p501_qpsk_rx import P501QpskRx

MODE = sys.argv[1] if len(sys.argv) > 1 else "loopback"
ATTEN = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
SECONDS = float(sys.argv[3]) if len(sys.argv) > 3 else 6.0
RX_GAIN = int(sys.argv[4]) if len(sys.argv) > 4 else 45
DIV = float(sys.argv[5]) if len(sys.argv) > 5 else 400.0
FINIT = float(sys.argv[6]) if len(sys.argv) > 6 else 0.0
TRACK = float(sys.argv[7]) if len(sys.argv) > 7 else 0.0
ACQ_MS = float(sys.argv[8]) if len(sys.argv) > 8 else 30.0
FS = 3_840_000
ol = Overlay('/home/xilinx/jupyter_notebooks/p501_qpsk_trx/p501_qpsk_trx.bit')
tx = P501QpskTx(ol.qpsk_regs, FS); rx = P501QpskRx(ol.qpsk_rx)
ad = p501_radio.bring_up(ol, lo_hz=915_000_000, tx_atten_db=89.75, rx_gain_index=RX_GAIN)
tx.off(); rx.stop()
print("READY bring_up_ok=%s mode=%s" % (ad.info["ok"], MODE), flush=True)
try:
    if MODE == "loopback":
        p501_radio.loopback(ad, True); ad.set_tx_atten_db(ATTEN)
    else:
        ad.set_tx_atten_db(ATTEN if MODE == "air" else 89.75)
    rx.configure(timing_bw=2 * np.pi / DIV, phase_bw=2 * np.pi / DIV, init_freq_hz=FINIT)
    if MODE == "rx":
        print("WAITING for /tmp/go", flush=True)
        while not os.path.exists('/tmp/go'): time.sleep(0.01)
        os.remove('/tmp/go'); rx.start()
        print("RX_ON bandwidth 2pi/%g, initial frequency %.0f Hz, tracking 2pi/%g after %g ms" % (DIV, FINIT, TRACK, ACQ_MS), flush=True)
    else:
        rx.start(); tx.start(amp=0.5)
        print("TX_ON mode %s atten %.1f dB, bandwidth 2pi/%g" % (MODE, ATTEN, DIV), flush=True)
    t0 = time.time(); last_t, last_m, tsec, switched = 0.0, 0, 0, TRACK <= 0
    while time.time() - t0 < SECONDS:
        if not switched and time.time() - t0 >= ACQ_MS * 1e-3:
            rx.set_loops(2 * np.pi / TRACK, 2 * np.pi / TRACK); switched = True
        if time.time() - t0 > 0.3: time.sleep(0.005)               # the first 0.3 s are polled without a pause (about 20 us per reading): the time of the last mismatch is the pull-in time
        m = rx.ip.read(0x3C); now = time.time() - t0
        if m != last_m: last_m, last_t = m, now
        if now >= tsec:
            tsec += 1.0
            s = rx.stats()
            print("t=%4.1f s symbols %9d bits %9d mismatches %7d  BER~%.1e  carrier %+8.1f Hz  clock %+6.2f ppm  agc %.2f  overruns %d" % (now, s["symbols"], s["bits"], s["mismatches"], s["ber_estimate"], s["carrier_offset_hz"], s["clock_offset_ppm"], s["agc_gain"], s["overruns"]), flush=True)
    s = rx.stats()
    if last_t < 0.5 * SECONDS:
        print("PULLIN last mismatch at %.2f ms; %d mismatches (about %d bit errors) up to then, none in the remaining %.1f s (%d bits, BER after pull-in < %.1e)" % (1e3 * last_t, last_m, last_m // 3, now - last_t, s["bits"], 1.0 / max(1, s["bits"] * (now - last_t) / now)), flush=True)
    else:
        print("PULLIN errors continue to the end: %d mismatches (about %d bit errors) in %d bits, BER about %.1e" % (last_m, last_m // 3, s["bits"], last_m / 3.0 / max(1, s["bits"])), flush=True)
    f_hz, ppm = rx.offsets(n=400); print("averaged over 2 s: carrier offset %+.1f Hz, clock offset %+.2f ppm" % (f_hz, ppm), flush=True)
    z = rx.capture(); np.save('/tmp/p501_link_soft.npy', z)
    print("soft symbols saved; rms |z| %.0f" % np.sqrt(np.mean(np.abs(z) ** 2)), flush=True)
finally:
    tx.off(); rx.stop(); p501_radio.loopback(ad, False); p501_radio.quiet(ad, 89.75)
    print("DONE (transmitter off, loopback off, TX attenuation 89.75 dB)", flush=True)
