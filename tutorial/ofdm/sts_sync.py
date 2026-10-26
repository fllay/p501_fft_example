"""Frame synchroniser for the 128-sample STS frame (the part that the stock Schmidl-and-Cox block does for the S&C frame). Inputs: the received samples x, the timing metric M and the sum S of 48 products x[n] conj(x[n-16]),
all aligned (the window of 64 samples ends at sample n; the stock blocks in front compute M = |S|^2 / (Ea Eb + guard)). When M reaches `threshold` the next 144 windows are collected; the plateau (the windows with M >= 24/32 of the largest)
gives the start of the STS: s0 = window start + (first + last + 1) // 2 - 32. The carrier offset is the coarse one from the angle of S over the plateau (lag 16, unambiguous to +-120 kHz) plus the fine one from the two training symbols
T1 and T2 (64 samples apart, the windows start at s0 + 154 and s0 + 218), which must repeat (|P|^2 >= E1 E2 / 2) or the frame is a false detection and is dropped.
Outputs (one value per input sample): 0: the carrier offset in the unit of the stock Schmidl-and-Cox block (the stock oscillator turns by -2/N x this per sample), switched to the new value `delay` - 38 samples after s0 (the samples
reach the oscillator `delay` samples late, through a Delay block); 1: the trigger of the stock Header/Payload Demux, a 1 at s0 + 122 + `delay` (the demux then skips the 16 samples of its guard interval, takes the two header symbols
at s0 + 138 and s0 + 218 and the data symbols from s0 + 298, as the FPGA receiver does); 2: frames found since the start; 3: frames dropped by the training-symbol check."""
import numpy as np
from gnuradio import gr

N, FS = 64, 3.84e6


class blk(gr.sync_block):
    def __init__(self, threshold=0.65, delay=384):
        gr.sync_block.__init__(self, name="STS frame synchroniser", in_sig=[np.complex64, np.float32, np.complex64], out_sig=[np.float32, np.uint8, np.float32, np.float32])
        self.threshold, self.delay = threshold, delay
        self.x = np.zeros(0, np.complex64); self.M = np.zeros(0, np.float32); self.S = np.zeros(0, np.complex64)
        self.base = 0; self.total = 0; self.scan = 0
        self.stage = 0; self.m0 = 0; self.s0 = 0; self.fc = 0.0              # 0: searching, 1: collecting the windows, 2: waiting for the training symbols
        self.events = []                                                     # (absolute output index, kind, value): kind 0 = set the carrier, 1 = trigger
        self.cfo = 0.0; self.found = 0; self.rejected = 0

    def set_threshold(self, t): self.threshold = float(t)

    def _trim(self):
        keep = 4096
        if len(self.x) > 2 * keep:
            k = len(self.x) - keep; self.x, self.M, self.S = self.x[k:], self.M[k:], self.S[k:]; self.base += k

    def _step(self):
        while True:
            if self.stage == 0:
                lo = max(self.scan - self.base, 0); idx = np.nonzero(self.M[lo:] >= self.threshold)[0]
                if len(idx) == 0: self.scan = self.base + len(self.M); return
                self.m0 = self.base + lo + int(idx[0]); self.stage = 1
            if self.stage == 1:
                a = self.m0 - self.base
                if a + 144 > len(self.M): return
                seg = self.M[a:a + 144]; pk = float(seg.max()); pl = np.nonzero(seg >= pk * 24 / 32)[0]; first, last = int(pl[0]), int(pl[-1])
                n0 = self.m0 - 63; self.s0 = n0 + ((first + last + 1) >> 1) - 32
                self.fc = float(np.angle(np.sum(self.S[a + first:a + last + 1])) / (2 * np.pi * 16 / FS))
                self.stage = 2
            if self.stage == 2:
                t2_end = self.s0 + 218 + N
                if self.s0 + 154 - self.base < 0:                              # the samples are gone (a very late decision): drop it
                    self.rejected += 1; self.scan = self.m0 + 144; self.stage = 0; continue
                if t2_end > self.base + len(self.x): return
                i1, i2 = self.s0 + 154 - self.base, self.s0 + 218 - self.base
                rot = np.exp(-2j * np.pi * self.fc / FS * (np.arange(N) + (self.s0 + 154 - self.s0)))                  # the coarse correction (a common phase does not matter)
                a1 = self.x[i1:i1 + N] * rot; b1 = self.x[i2:i2 + N] * rot * np.exp(-2j * np.pi * self.fc / FS * 64)
                P = np.sum(b1 * np.conj(a1)); e1 = float(np.sum(np.abs(a1) ** 2)); e2 = float(np.sum(np.abs(b1) ** 2))
                if 2 * abs(P) ** 2 >= e1 * e2:
                    ff = float(np.angle(P)) / (2 * np.pi * 64 / FS); f = self.fc + ff; val = np.pi * N * f / FS
                    self.events.append((self.s0 + self.delay - 38, 0, val)); self.events.append((self.s0 + 122 + self.delay, 1, 0.0)); self.found += 1
                else: self.rejected += 1
                self.scan = self.m0 + 144; self.stage = 0; continue

    def work(self, input_items, output_items):
        x, M, S = input_items; n = len(x); out_cfo, out_trg, out_fnd, out_rej = output_items
        self.x = np.concatenate([self.x, x]); self.M = np.concatenate([self.M, M]); self.S = np.concatenate([self.S, S])
        self.total += n; self._step(); self._trim()
        lo = self.total - n
        out_trg[:] = 0; out_cfo[:] = self.cfo
        for ev in sorted(self.events):
            if ev[0] < lo: continue
            if ev[0] >= lo + n: break
            i = ev[0] - lo
            if ev[1] == 0: out_cfo[i:] = ev[2]; self.cfo = ev[2]
            else: out_trg[i] = 1
        self.events = [e for e in self.events if e[0] >= lo + n]
        out_fnd[:] = self.found; out_rej[:] = self.rejected
        return n
