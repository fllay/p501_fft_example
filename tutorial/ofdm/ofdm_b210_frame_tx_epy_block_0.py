
import os, sys
import numpy as np
from gnuradio import gr


class blk(gr.sync_block):
    """The OFDM frames as a periodic complex stream at 3.84 MS/s: S&C symbol | T1 | T2 | 44 data symbols (24 16-QAM subcarriers + 4 QPSK pilots, 16-sample prefix) | 80 idle
    = 3840 samples = 1 ms, the frame of the P501 receiver (tutorial/ofdm/PLAN_OFDM.md). The samples come from ofdm_frame.npy (made by tutorial/ofdm/make_ofdm_frame.py) or, if the file is not found,
    from ofdm_model.tx_frame (the repository's model; run from the repository root or from tutorial/ofdm). Unit rms over the active part (3760 samples); fill_idle puts noise of the same rms in the
    idle slot (it is empty by default: the receiver's detector has a guard for that)."""

    def __init__(self, frame_file="ofdm_frame.npy", fill_idle=False):
        gr.sync_block.__init__(self, name="OFDM frames", in_sig=None, out_sig=[np.complex64])
        x = None
        for f in (frame_file, os.path.join("tutorial", "ofdm", frame_file), os.path.join("..", "..", "tutorial", "ofdm", frame_file)):
            if os.path.exists(f):
                x = np.load(f).astype(complex); break
        if x is None:
            for d in (".", os.path.join("tutorial", "ofdm"), os.path.join("..", "..", "tutorial", "ofdm")):
                if os.path.exists(os.path.join(d, "ofdm_model.py")):
                    sys.path.insert(0, os.path.abspath(d)); import ofdm_model
                    x = ofdm_model.tx_frame(preamble="scu")[0]; break
        if x is None or len(x) != 3840:
            raise RuntimeError("ofdm_frame.npy (3840 samples) not found: run tutorial/ofdm/make_ofdm_frame.py and start from that folder")
        x = x / np.sqrt(np.mean(np.abs(x[:3760]) ** 2))
        if fill_idle:
            r = np.random.RandomState(1)
            x[3760:] = np.clip(r.randn(80), -2.5, 2.5) / np.sqrt(2) + 1j * np.clip(r.randn(80), -2.5, 2.5) / np.sqrt(2)
        self.data = x.astype(np.complex64)
        self.pos = 0

    def work(self, input_items, output_items):
        out = output_items[0]
        n = len(out)
        idx = (self.pos + np.arange(n)) % len(self.data)
        out[:] = self.data[idx]
        self.pos = (self.pos + n) % len(self.data)
        return n
