"""Fine carrier correction and the check of the frame. The two training symbols T1 and T2 are the same 64 samples, 80 samples apart: P = sum T2 conj(T1), the remaining carrier offset is arg(P) / 80 rad/sample.
The frame is accepted when the two symbols really repeat: 2 |P|^2 >= E1 E2 (the normalised correlation is above 0.71); a false detection in noise is replaced by zeros (the later blocks skip it).
Outputs: 1: the total carrier offset (coarse + fine) in Hz, 2: 1.0 for an accepted frame, 0.0 for a rejected one (one value per sample)."""
import numpy as np
import pmt
from gnuradio import gr

FRAME = 3760; FS = 3.84e6


class blk(gr.sync_block):
    def __init__(self, back=6, check=True):
        gr.sync_block.__init__(self, name="Fine CFO correction and T1/T2 check", in_sig=[np.complex64], out_sig=[np.complex64, np.float32, np.float32])
        self.back, self.check = back, check
        self.i = (np.arange(FRAME) - back).astype(np.float32)
        self.set_output_multiple(FRAME)
        self.accepted = 0; self.rejected = 0

    def work(self, input_items, output_items):
        x, y, hz, okf = input_items[0], output_items[0], output_items[1], output_items[2]
        nf = len(y) // FRAME
        i = self.i
        for f in range(nf):
            a = f * FRAME; cfo = 0.0
            for t in self.get_tags_in_window(0, a, a + 1):
                if pmt.symbol_to_string(t.key) == "cfo": cfo = pmt.to_double(t.value)
            fr = x[a:a + FRAME]
            T1, T2 = fr[96:160], fr[176:240]                     # the FFT windows of symbols 1 and 2: 80 s + 16
            P = np.sum(T2 * np.conj(T1)); E1 = float(np.sum(np.abs(T1) ** 2)); E2 = float(np.sum(np.abs(T2) ** 2))
            ok = (2 * abs(P) ** 2 >= E1 * E2) or not self.check
            wf = float(np.angle(P)) / 80.0
            if ok:
                ph = np.empty(FRAME, np.complex64); ang = np.float32(wf) * i; ph.real = np.cos(ang); ph.imag = -np.sin(ang)
                y[a:a + FRAME] = fr * ph; self.accepted += 1
            else:
                y[a:a + FRAME] = 0; self.rejected += 1
            hz[a:a + FRAME] = (cfo + wf) * FS / (2 * np.pi); okf[a:a + FRAME] = 1.0 if ok else 0.0
        return nf * FRAME
