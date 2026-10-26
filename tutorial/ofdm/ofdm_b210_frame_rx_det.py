"""Schmidl-and-Cox frame detector. Inputs: the received samples x, the S&C metric M = |S|^2 / (Ea Eb) and the sum S of 32 products x[n] conj(x[n-32]) (all three aligned: the window ends at sample n).
When M reaches `threshold` the next 72 windows are collected, the plateau (the windows with M >= 29/32 of the largest) is found and the middle of it gives the start of the S&C symbol: s0 = (window start) + (first + last + 1) // 2 - 8.
Only 1 frame in `skip + 1` is passed on (the transmitter repeats the same frame every 3840 samples; the python blocks behind could not follow 1000 frames per second in real time): after a frame the search starts again `skip` frames later.
The output is the frame as 3760 samples (47 symbols of 80: S&C, T1, T2 and 44 data symbols; the idle slot is dropped) starting `back` samples before s0 (the FFT windows then start inside the cyclic prefix: a timing error
of up to `back` samples is harmless). Two tags are put on the first sample: `cfo` (the coarse carrier offset in rad/sample = arg(sum of S over the plateau) / 32) and `gain` (1 / rms of the first 240 samples)."""
import numpy as np
import pmt
from gnuradio import gr

FRAME = 3760        # 47 symbols of 80 samples


class blk(gr.basic_block):
    def __init__(self, threshold=0.65, back=6, skip=3):
        gr.basic_block.__init__(self, name="S&C frame detector", in_sig=[np.complex64, np.float32, np.complex64], out_sig=[np.complex64])
        self.threshold, self.back, self.skip = threshold, back, skip
        self.x = np.zeros(0, np.complex64); self.M = np.zeros(0, np.float32); self.S = np.zeros(0, np.complex64)
        self.base = 0                 # absolute index of x[0]
        self.scan = 0                 # absolute index where the search for the next frame goes on
        self.total = 0                # absolute index of the next input sample
        self.skip_until = 0           # absolute index: input before it is dropped (the frames that are skipped)
        self.queue = []               # (frame, cfo, gain)
        self.cur = None; self.pos = 0
        self.frames = 0

    def forecast(self, noutput_items, ninputs):
        return [1] * ninputs

    def _trim(self, keep_from):
        k = int(min(max(keep_from, 0), len(self.x)))
        if k:
            self.x, self.M, self.S = self.x[k:], self.M[k:], self.S[k:]; self.base += k

    def _search(self):
        while True:
            lo = max(self.scan - self.base, 0)
            idx = np.nonzero(self.M[lo:] >= self.threshold)[0]
            if len(idx) == 0:
                self.scan = self.base + len(self.M); self._trim(len(self.M) - 400); return
            m0 = lo + int(idx[0])                         # the window ends here
            if m0 + 72 > len(self.M): self._trim(m0 - 120); return
            seg = self.M[m0:m0 + 72]; pk = float(seg.max())
            pl = np.nonzero(seg >= pk * 29 / 32)[0]; first, last = int(pl[0]), int(pl[-1])
            n0 = m0 - 63                                  # the window starts here
            s0 = n0 + ((first + last + 1) >> 1) - 8
            start = s0 - self.back; end = start + FRAME
            if start < 0:
                self.scan = self.base + m0 + 72; continue
            if end > len(self.x): self._trim(m0 - 120); return
            cfo = float(np.angle(np.sum(self.S[m0 + first:m0 + last + 1])) / 32.0)
            fr = self.x[start:end].copy(); rms = float(np.sqrt(np.mean(np.abs(fr[:240]) ** 2))) + 1e-20
            self.queue.append((fr, cfo, 1.0 / rms)); self.frames += 1
            self.scan = self.base + end; self._trim(end - 120)
            self.skip_until = max(self.scan, self.scan + 86 + int(self.skip) * 3840 - 600)       # the next frame's S&C symbol is 86 samples after the end of this one; start 600 samples before the frame to be used

    def general_work(self, input_items, output_items):
        out = output_items[0]; produced = 0
        n = min(len(input_items[0]), len(input_items[1]), len(input_items[2]), 16384)
        if n > 0 and len(self.queue) < 4:
            if self.total + n <= self.skip_until:                                   # inside the frames that are skipped: nothing is kept
                self.x = self.x[:0]; self.M = self.M[:0]; self.S = self.S[:0]; self.base = self.total + n; self.scan = self.base
            else:
                if len(self.x) == 0 and self.total < self.skip_until:                 # the chunk that ends the skipping: keep only its part after skip_until
                    k = self.skip_until - self.total
                    self.x = input_items[0][k:n].copy(); self.M = input_items[1][k:n].copy(); self.S = input_items[2][k:n].copy(); self.base = self.total + k; self.scan = self.base
                else:
                    self.x = np.concatenate([self.x, input_items[0][:n]]); self.M = np.concatenate([self.M, input_items[1][:n]]); self.S = np.concatenate([self.S, input_items[2][:n]])
                self._search()
            self.total += n; self.consume_each(n)
        while produced < len(out):
            if self.cur is None:
                if not self.queue: break
                self.cur, cfo, gain = self.queue.pop(0); self.pos = 0
                off = self.nitems_written(0) + produced
                self.add_item_tag(0, off, pmt.intern("cfo"), pmt.from_double(cfo)); self.add_item_tag(0, off, pmt.intern("gain"), pmt.from_double(gain))
            k = min(len(out) - produced, len(self.cur) - self.pos)
            out[produced:produced + k] = self.cur[self.pos:self.pos + k]; self.pos += k; produced += k
            if self.pos == len(self.cur): self.cur = None
        return produced
