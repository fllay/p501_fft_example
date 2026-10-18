"""Python reader for the FFT chain of the P501 FFT overlay (fft_dma, rtl/fft_power_gate.v).

    from p501_fft import P501Fft
    fft = P501Fft(ol.fft_dma, nfft_log2=10, fs_hz=3_840_000)
    avg = fft.average(16)                  # mean power spectrum of 16 frames computed in the FPGA, fftshifted (DC in the middle)
    f_hz, level_db = fft.peak(avg)

The FFT is computed by the FPGA on the live ADC stream; Python only starts the DMA and reads the 32-bit power values.
"""
import sys

import numpy as np
from pynq import allocate

sys.path.insert(0, '/home/xilinx/jupyter_notebooks')
from axi_dmac import AxiDmac                                                 # noqa: E402


class P501Fft:
    def __init__(self, dma_ip, nfft_log2=10, fs_hz=3_840_000, scale_shift=None):
        self.dma = AxiDmac(dma_ip)
        self.n = 1 << nfft_log2
        self.fs = float(fs_hz)
        self.scale_shift = (nfft_log2 - 4) & ~1 if scale_shift is None else scale_shift
        self.freqs = np.fft.fftshift(np.fft.fftfreq(self.n, 1 / self.fs))      # Hz, matches the fftshifted spectra
        self.bin_hz = self.fs / self.n
        self._buf = {}

    def bin_of(self, f_hz):
        """Index in a fftshifted spectrum of the bin that holds f_hz."""
        return int(round(f_hz / self.bin_hz)) + self.n // 2

    def read_frames(self, n_frames=16, timeout_s=5.0):
        """(ok, array (n_frames, N)) of |X|^2 per bin, natural FFT order (bin 0 = DC)."""
        buf = self._buf.get(n_frames)
        if buf is None:
            buf = self._buf[n_frames] = allocate(shape=(n_frames, self.n), dtype=np.uint32)
        ok = self.dma.transfer_to_memory(buf.physical_address, buf.nbytes, timeout_s=timeout_s)
        buf.invalidate()
        return ok, np.array(buf, dtype=np.float64)

    def average(self, n_frames=16):
        """Mean power spectrum of n_frames frames, fftshifted (frequency axis: self.freqs)."""
        ok, p = self.read_frames(n_frames)
        if not ok:
            raise TimeoutError("FFT DMA did not complete: is the AD9361 clock running? Run p501_radio.bring_up() first.")
        return np.fft.fftshift(p.mean(axis=0))

    @staticmethod
    def db(p):
        return 10 * np.log10(p + 1.0)

    def peak(self, avg):
        """(frequency in Hz, level in dB) of the strongest bin, with parabolic interpolation on the dB values."""
        m = self.db(avg)
        k = int(np.argmax(m))
        if 0 < k < self.n - 1:
            a, b, c = m[k - 1], m[k], m[k + 1]
            d = a - 2 * b + c
            k_f = k + (0.5 * (a - c) / d if d != 0 else 0.0)
        else:
            k_f = float(k)
        return (k_f - self.n // 2) * self.bin_hz, float(m[k])

    def image_rejection_db(self, avg, f_hz):
        """Tone at f_hz minus its mirror image at -f_hz, in dB."""
        m = self.db(avg)
        k, ki = self.bin_of(f_hz), self.bin_of(-f_hz)
        return float(m[k - 1:k + 2].max() - m[ki - 1:ki + 2].max())
