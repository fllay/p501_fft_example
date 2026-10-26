"""Header stand-in. The stock receiver chain expects a header with the length of the packet after the synchronisation symbols; this frame has none: it always has 44 data symbols after S&C, T1 and T2.
Input: the third symbol of every frame (T2) after the FFT and the channel estimator, 64 values, with the tags of the channel estimator. For every frame it sends the message that the Header/Payload Demux waits for:
frame_length = nsym data symbols, and the channel estimate and the carrier offset of the tags (the equalizer of the payload needs them). Output: the channel estimate H[k] of the frame (64 values, DC in the middle, zero on the unused subcarriers) for the plots."""
import numpy as np
import pmt
from gnuradio import gr


class blk(gr.sync_block):
    def __init__(self, nsym=44):
        gr.sync_block.__init__(self, name="Header stand-in (fixed frame length)", in_sig=[(np.complex64, 64)], out_sig=[(np.complex64, 64)])
        self.nsym = nsym
        self.frames = 0
        self.message_port_register_out(pmt.intern("header_data"))

    def work(self, input_items, output_items):
        n0 = self.nitems_read(0); n = len(input_items[0]); out = output_items[0]
        out[:] = 0
        for i in range(n):
            d = pmt.make_dict()
            d = pmt.dict_add(d, pmt.intern("frame_length"), pmt.from_long(int(self.nsym)))
            for t in self.get_tags_in_range(0, n0 + i, n0 + i + 1):
                d = pmt.dict_add(d, t.key, t.value)
                if pmt.symbol_to_string(t.key) == "ofdm_sync_chan_taps":
                    out[i] = np.array(pmt.c32vector_elements(t.value), dtype=np.complex64)
            self.message_port_pub(pmt.intern("header_data"), d)
            self.frames += 1
        return n
