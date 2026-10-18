"""Host side of the B210 -> P501 test: `source tools/gnuradio_env.sh`, start p501_listen_tone.py on the P501 with its output going to
/tmp/p501_rx.log, then run this: B210 TX/RX port, 915.0 MHz, tone +500 kHz, TX gain 0/10/20/30 dB for 6 s each (3 s silence between).
Very low power; the antenna must be on the TX/RX port. Prints the summary per phase.
"""
import numpy as np, uhd, time, subprocess, sys, json
O = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o BatchMode=yes"
t0 = time.time()
while "READY" not in open('/tmp/p501_rx.log').read():
    if time.time() - t0 > 200: print("P501 not ready"); sys.exit(1)
    time.sleep(0.5)
fs, F0, FT = 3.84e6, 915.0e6, 500e3
u = uhd.usrp.MultiUSRP("")
u.set_tx_rate(fs, 0); u.set_tx_freq(uhd.types.TuneRequest(F0), 0); u.set_tx_gain(0, 0); u.set_tx_antenna("TX/RX", 0)
st = uhd.usrp.StreamArgs("fc32", "sc16"); st.channels = [0]; tx = u.get_tx_stream(st)
md = uhd.types.TXMetadata(); md.start_of_burst = True; md.end_of_burst = False
B = 9600; phase = 0.0; dphi = 2 * np.pi * FT / fs; n = np.arange(B)
sched = [(0, 6), (10, 6), (20, 6), (30, 6)]                  # (TX gain dB, seconds on), 3 s of silence after each
subprocess.run(["ssh"] + O.split() + ["xilinx@192.168.2.1", "touch /tmp/go"]); t_go = time.time()
def send(seconds, amp):
    global phase, md
    end = time.time() + seconds
    while time.time() < end:
        x = (amp * np.exp(1j * (phase + dphi * n))).astype(np.complex64); phase = (phase + dphi * B) % (2 * np.pi)
        tx.send(x.reshape(1, -1), md); md.start_of_burst = False
time.sleep(3.0)
log = []
try:
    for g, sec in sched:
        u.set_tx_gain(g, 0); log.append(("ON", g, time.time() - t_go)); print(f"B210 TX gain {g} dB on at t={time.time()-t_go:.1f} s", flush=True)
        send(sec, 0.5)
        u.set_tx_gain(0, 0); log.append(("OFF", g, time.time() - t_go)); send(3, 0.0)
finally:
    u.set_tx_gain(0, 0)
    md.end_of_burst = True; tx.send(np.zeros((1, 1000), np.complex64), md)
    print("B210 TX stopped, gain 0", flush=True)
time.sleep(max(0, 43 - (time.time() - t_go)))
rows = [json.loads(l) for l in open('/tmp/p501_rx.log') if l.startswith('{')]
print(f"\nP501 recorded {len(rows)} readings\n")
print(f"{'phase':>14} {'n':>3} {'FFT chain [kHz]':>16} {'SNR':>5} {'raw 64k FFT [kHz]':>18} {'std Hz':>7} {'SNR':>5}")
tone = []
for name, (a, b) in [("gain 0 dB", (3.8, 8.8)), ("silence", (9.8, 11.8)), ("gain 10 dB", (13.8, 18.8)), ("silence", (19.8, 21.8)), ("gain 20 dB", (23.8, 28.8)), ("silence", (29.8, 31.8)), ("gain 30 dB", (33.8, 38.8)), ("silence", (39.8, 41.8))]:
    r = [x for x in rows if a <= x["t"] <= b]
    if not r: continue
    h = np.array([x["hw_khz"] for x in r]); hs = np.array([x["hw_snr"] for x in r]); w = np.array([x["raw_khz"] for x in r]); ws = np.array([x["raw_snr"] for x in r])
    print(f"{name:>14} {len(r):3d} {np.mean(h):16.3f} {np.mean(hs):5.1f} {np.mean(w):18.4f} {np.std(w)*1e3:7.1f} {np.mean(ws):5.1f}")
    if name.startswith("gain") and np.mean(ws) > 15: tone += list(w)
if tone: print(f"\nraw tone {np.mean(tone):.4f} kHz vs 500 kHz sent -> B210 LO - P501 LO = {(np.mean(tone)-500)*1e3:+.0f} Hz = {(np.mean(tone)-500)*1e3/F0*1e6:+.2f} ppm (the first test gave -9510 Hz in the other direction)")
else: print("\nno tone found at any gain")
