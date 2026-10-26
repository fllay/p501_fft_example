"""16-QAM slicer: the nearest of the levels -3 -1 +1 +3 (/ sqrt 10) on each axis, as the Gray code of the transmitter (levels -3 -1 +1 +3 = 00 01 11 10): the output byte is 4 * (I code) + (Q code), 0 .. 15.
A value of exactly 0 (a rejected frame) gives 255."""
import numpy as np
from gnuradio import gr

T = np.float32(2 / np.sqrt(10))              # decision thresholds -2, 0, +2 (/ sqrt 10)
GRAY = np.array([0, 1, 3, 2], np.uint8)       # the level index 0 1 2 3 (-3 -1 +1 +3) -> the Gray code


class blk(gr.sync_block):
    def __init__(self):
        gr.sync_block.__init__(self, name="16-QAM slicer", in_sig=[np.complex64], out_sig=[np.uint8])

    def work(self, input_items, output_items):
        z, o = input_items[0], output_items[0]
        re, im = z.real, z.imag
        ii = (re > -T).astype(np.uint8) + (re > 0) + (re > T); qq = (im > -T).astype(np.uint8) + (im > 0) + (im > T)
        o[:] = GRAY[ii] * 4 + GRAY[qq]
        o[z == 0] = 255
        return len(o)
