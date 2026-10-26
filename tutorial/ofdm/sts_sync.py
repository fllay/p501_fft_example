"""Frame synchroniser for the 128-sample STS frame (the part that the stock Schmidl-and-Cox block does for the S&C frame). Inputs: the received samples x, the timing metric M and the sum S of 48 products x[n] conj(x[n-16]),
all aligned (the window of 64 samples ends at sample n; the stock blocks in front compute M = |S|^2 / (Ea Eb + guard)). When M reaches `threshold` the next 144 windows are collected; the plateau (the windows with M >= 24/32 of the largest)
gives the start of the STS: s0 = window start + (first + last + 1) // 2 - 32. The carrier offset is the coarse one from the angle of S over the plateau (lag 16, unambiguous to +-120 kHz) plus the fine one from the two training symbols
T1 and T2 (64 samples apart, the windows start at s0 + 154 and s0 + 218), which must repeat (|P|^2 >= E1 E2 / 2) or the frame is a false detection and is dropped.
Outputs (one value per input sample): 0: the carrier offset in the unit of the stock Schmidl-and-Cox block (the stock oscillator turns by -2/N x this per sample), switched to the new value `delay` - 38 samples after s0 (the samples
reach the oscillator `delay` samples late, through a Delay block); 1: the trigger of the stock Header/Payload Demux, a 1 at s0 + 122 + `delay` (the demux then skips the 16 samples of its guard interval, takes the two header symbols
at s0 + 138 and s0 + 218 and the data symbols from s0 + 298, as the FPGA receiver does).
It runs in the Python interpreter that the other Python blocks of the flowgraph share, at 3.84 million samples per second, so it is written to make as few NumPy calls as possible: GNU Radio keeps the last 1024 input samples for it (the history), it
looks at M only when a frame is not being processed, and it writes its two outputs once per call. `found` and `rejected` count the frames."""
import numpy as np
from gnuradio import gr

N, FS, HIST = 64, 3.84e6, 1024


class blk(gr.sync_block):
    def __init__(self, threshold=0.65, delay=384):
        gr.sync_block.__init__(self, name="STS frame synchroniser", in_sig=[np.complex64, np.float32, np.complex64], out_sig=[np.float32, np.uint8])
        self.set_history(HIST)
        self.threshold, self.delay = threshold, delay
        self.scan = 0                                                       # absolute index of the first window not yet looked at
        self.stage = 0; self.m0 = 0; self.s0 = 0; self.fc = 0.0              # 0: searching, 1: collecting the windows, 2: waiting for the training symbols
        self.events = []                                                     # (absolute output index, kind, value): kind 0 = set the carrier, 1 = trigger
        self.cfo = 0.0; self.found = 0; self.rejected = 0

    def set_threshold(self, t): self.threshold = float(t)

    def _step(self, x, M, S, base, end):
        """x, M, S: the input arrays, element i has the absolute index base + i; end = the absolute index after the last one"""
        while True:
            if self.stage == 0:
                lo = max(self.scan, base) - base
                if lo >= len(M): self.scan = end; return
                idx = np.flatnonzero(M[lo:] >= self.threshold)
                if len(idx) == 0: self.scan = end; return
                self.m0 = base + lo + int(idx[0]); self.stage = 1
            if self.stage == 1:
                a = self.m0 - base
                if a < 0: self.rejected += 1; self.scan = self.m0 + 144; self.stage = 0; continue
                if a + 144 > len(M): return
                seg = M[a:a + 144]; pk = float(seg.max()); pl = np.flatnonzero(seg >= pk * 24 / 32); first, last = int(pl[0]), int(pl[-1])
                self.s0 = self.m0 - 63 + ((first + last + 1) >> 1) - 32
                self.fc = float(np.angle(np.sum(S[a + first:a + last + 1])) / (2 * np.pi * 16 / FS))
                self.stage = 2
            if self.stage == 2:
                i1, i2 = self.s0 + 154 - base, self.s0 + 218 - base
                if i1 < 0: self.rejected += 1; self.scan = self.m0 + 144; self.stage = 0; continue
                if i2 + N > len(x): return
                rot = np.exp(-2j * np.pi * self.fc / FS * (np.arange(N) + 154))
                a1 = x[i1:i1 + N] * rot; b1 = x[i2:i2 + N] * rot * np.exp(-2j * np.pi * self.fc / FS * 64)
                P = np.sum(b1 * np.conj(a1)); e1 = float(np.sum(np.abs(a1) ** 2)); e2 = float(np.sum(np.abs(b1) ** 2))
                if 2 * abs(P) ** 2 >= e1 * e2:
                    ff = float(np.angle(P)) / (2 * np.pi * 64 / FS); f = self.fc + ff; val = np.pi * N * f / FS
                    self.events.append((self.s0 + self.delay - 38, 0, val)); self.events.append((self.s0 + 122 + self.delay, 1, 0.0)); self.found += 1
                else: self.rejected += 1
                self.scan = self.m0 + 144; self.stage = 0; continue

    def work(self, input_items, output_items):
        x, M, S = input_items; out_cfo, out_trg = output_items; n = len(out_cfo)
        end = self.nitems_read(0) + n; base = end - len(x)                                        # absolute index of x[0] (the history comes first)
        self._step(x, M, S, base, end)
        lo = end - n
        out_trg[:] = 0
        if not self.events: out_cfo[:] = self.cfo
        else:
            pos = 0
            for ev in sorted(self.events):
                if ev[0] >= end: break
                i = max(ev[0] - lo, 0)
                if ev[1] == 0: out_cfo[pos:i] = self.cfo; pos = i; self.cfo = ev[2]
                else: out_trg[i] = 1
            out_cfo[pos:] = self.cfo
            self.events = [e for e in self.events if e[0] >= end]
        return n
