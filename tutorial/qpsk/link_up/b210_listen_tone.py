"""Host side of the link-up test: `source tools/gnuradio_env.sh`, start p501_tone_burst.py on the P501 with its output going to
/tmp/p501_tx.log (see RESULTS.md), then run this: it waits for READY, records the B210 at 915.0 MHz / 3.84 MSPS (reader thread +
processing, no overruns), touches /tmp/go on the board and summarises the measured tone per phase and the offset between the radios.
"""
import numpy as np, uhd, time, subprocess, sys, threading, queue
O = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o BatchMode=yes"
t0 = time.time()
while "READY" not in open('/tmp/p501_tx.log').read():
    if time.time() - t0 > 200: print("P501 not ready"); sys.exit(1)
    time.sleep(0.5)
fs, F0 = 3.84e6, 915.0e6
u = uhd.usrp.MultiUSRP("")
u.set_rx_rate(fs, 0); u.set_rx_freq(uhd.types.TuneRequest(F0), 0); u.set_rx_gain(45, 0); u.set_rx_antenna("RX2", 0)
st = uhd.usrp.StreamArgs("fc32", "sc16"); st.channels = [0]; rx = u.get_rx_stream(st)
time.sleep(0.2)
q = queue.Queue(); stop = threading.Event(); errs = [0]
def reader():                                    # only reads: never blocks on processing
    md = uhd.types.RXMetadata(); buf = np.zeros((1, 100000), np.complex64)
    cmd = uhd.types.StreamCMD(uhd.types.StreamMode.start_cont); cmd.stream_now = True; rx.issue_stream_cmd(cmd)
    while not stop.is_set():
        k = rx.recv(buf, md, 1.0)
        if md.error_code != uhd.types.RXMetadataErrorCode.none: errs[0] += 1
        q.put((time.time(), buf[0, :k].copy()))
    rx.issue_stream_cmd(uhd.types.StreamCMD(uhd.types.StreamMode.stop_cont))
th = threading.Thread(target=reader); th.start()
CH = 1 << 19                                      # 0.137 s, 7.3 Hz bins
win = np.hanning(CH); fr = np.fft.fftshift(np.fft.fftfreq(CH, 1/fs)); band = (fr > 440e3) & (fr < 560e3)
cur, have, rows, t_go, tstart = [], 0, [], None, time.time()
while time.time() - tstart < 36:
    try: t, blk = q.get(timeout=1)
    except queue.Empty: continue
    cur.append(blk); have += len(blk)
    if t_go is None and time.time() - tstart > 2.0:
        subprocess.run(["ssh"] + O.split() + ["xilinx@192.168.2.1", "touch /tmp/go"]); t_go = time.time()
    if have >= CH:
        x = np.concatenate(cur); cur = [x[CH:]]; have = len(cur[0]); x = x[:CH]
        db = 10*np.log10(np.abs(np.fft.fftshift(np.fft.fft(x * win)))**2 + 1e-20); floor = np.median(db)
        i = np.argmax(np.where(band, db, -999)); a, b, c = db[i-1], db[i], db[i+1]; d = a - 2*b + c
        rows.append((t - t_go, fr[i] + (0.5*(a-c)/d if d else 0) * (fs/CH), b - floor, floor)) if t_go else None
stop.set(); th.join()
print(f"B210: {len(rows)} spectra, stream errors: {errs[0]}\n")
rows = np.array(rows)
sched = [("TX atten 80 dB", 0.8, 5.8), ("silence", 6.8, 8.8), ("TX atten 70 dB", 9.8, 14.8), ("silence", 15.8, 17.8), ("TX atten 60 dB", 18.8, 23.8), ("silence", 24.8, 26.8)]
print(f"{'phase':>16} {'n':>3} {'tone [kHz]':>11} {'std [Hz]':>9} {'SNR dB':>7} {'level dB':>9}")
res = {}
for name, a, b in sched:
    m = (rows[:, 0] >= a) & (rows[:, 0] <= b); r = rows[m]
    if len(r) == 0: continue
    print(f"{name:>16} {len(r):3d} {np.mean(r[:,1])/1e3:11.4f} {np.std(r[:,1]):9.1f} {np.mean(r[:,2]):7.1f} {np.mean(r[:,2]+r[:,3]):9.1f}")
    res[name] = r
t = [r for n, r in res.items() if n.startswith("TX")]
f_all = np.concatenate([r[:,1] for r in t]); 
print(f"\nmeasured tone {np.mean(f_all)/1e3:.4f} kHz  vs  500 kHz set  ->  offset between the radios {np.mean(f_all)-500e3:+.0f} Hz = {(np.mean(f_all)-500e3)/F0*1e6:+.2f} ppm at 915 MHz")
