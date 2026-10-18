"""Host side of the B210 -> P501 test: `source tools/gnuradio_env.sh`, start p501_listen_tone.py on the P501 with its output going to
/tmp/p501_rx.log, then run this: B210 TX/RX port, 915.0 MHz, tone +500 kHz, TX gain 30/40/50/60 dB for 5 s each (3 s silence between), stops
raising the gain if the P501 ADC peak exceeds 1500. The antenna must be on the TX/RX port. Prints the summary per step.
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
sched = [(30, 5), (40, 5), (50, 5), (60, 5)]                  # (TX gain dB, seconds on), 3 s of silence after each
subprocess.run(["ssh"] + O.split() + ["xilinx@192.168.2.1", "touch /tmp/go"]); t_go = time.time()
def send(seconds, amp):
    global phase, md
    end = time.time() + seconds
    while time.time() < end:
        x = (amp * np.exp(1j * (phase + dphi * n))).astype(np.complex64); phase = (phase + dphi * B) % (2 * np.pi)
        tx.send(x.reshape(1, -1), md); md.start_of_burst = False
time.sleep(3.0)
def p501_adc_peak(since):
    rows = [json.loads(l) for l in open('/tmp/p501_rx.log') if l.startswith('{')]
    r = [x["adc_peak"] for x in rows if x["t"] >= since]
    return max(r) if r else 0
log = []
try:
    for g, sec in sched:
        u.set_tx_gain(g, 0); t_on = time.time() - t_go; log.append((g, t_on)); print(f"B210 TX gain {g} dB on at t={t_on:.1f} s", flush=True)
        send(sec, 0.5)
        u.set_tx_gain(0, 0); send(3, 0.0)
        pk = p501_adc_peak(t_on - 0.4)
        print(f"   P501 ADC peak during this step: {pk} (full scale 2047)", flush=True)
        if pk > 1500: print("   near clipping: not going higher", flush=True); break
finally:
    u.set_tx_gain(0, 0)
    md.end_of_burst = True; tx.send(np.zeros((1, 1000), np.complex64), md)
    print("B210 TX stopped, gain 0", flush=True)
time.sleep(max(0, 3.0 + 8 * len(log) + 3 - (time.time() - t_go)))
rows = [json.loads(l) for l in open('/tmp/p501_rx.log') if l.startswith('{')]
print(f"\nP501 recorded {len(rows)} readings\n")
print(f"{'B210 gain':>10} {'n':>3} {'FFT chain [kHz]':>16} {'SNR':>5} {'raw 64k FFT [kHz]':>18} {'std Hz':>7} {'SNR':>5} {'ADC peak':>9}")
tone = []
for g, t_on in log:
    a_, b_ = t_on - 0.4 + 1.0, t_on - 0.4 + 4.6
    r = [x for x in rows if a_ <= x["t"] <= b_]
    if not r: continue
    w = np.array([x["raw_khz"] for x in r]); ws = np.array([x["raw_snr"] for x in r]); h = np.array([x["hw_khz"] for x in r]); hs = np.array([x["hw_snr"] for x in r])
    print(f"{g:7d} dB {len(r):3d} {np.median(h):16.3f} {np.mean(hs):5.1f} {np.mean(w):18.4f} {np.std(w)*1e3:7.1f} {np.mean(ws):5.1f} {max(x['adc_peak'] for x in r):9d}")
    if np.mean(ws) > 20: tone += list(w)
if tone: print(f"\ntone {np.mean(tone):.4f} kHz -> B210 LO - P501 LO = {(np.mean(tone)-500)*1e3:+.0f} Hz = {(np.mean(tone)-500)*1e3/F0*1e6:+.2f} ppm")
