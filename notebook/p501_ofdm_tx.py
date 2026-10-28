"""Python side of the FPGA OFDM transmitter (rtl/ofdm_tx.v, overlays p501_ofdm_trx_sc / p501_ofdm_trx_sts): the register block is the one of the DDS and of the QPSK transmitter (instance qpsk_regs, 0x9C460000).

    from p501_ofdm_tx import P501OfdmTx
    tx = P501OfdmTx(ol.qpsk_regs, fs_hz=3_840_000)
    tx.start(amp=0.5)       # the OFDM frame (1 ms, 3840 samples) repeats from its first sample; amp 1.0 = 8034 counts rms at the DAC input (the DAC takes 16 bits, 12 used: 8034 / 16 = 502 counts at the ADC in the digital loopback)
    tx.stop()               # zeros to the DAC

The frame is made in the PL: 44 data symbols of the PRBS-15 payload (restarted in every frame, the receiver's checker expects it), pilots, IFFT, prefix. No DMA, no host frame."""
from p501_dds import P501Dds

DAC_RMS_AT_FULL_SCALE = 8034.0        # counts rms of the frame at amp = 1.0 (peak 27187): the integer model tutorial/ofdm/ofdm_tx_fixed.py


class P501OfdmTx(P501Dds):
    def start(self, amp=0.5, timeout_s=1.0):
        if not 0.0 < amp <= 1.0:
            raise ValueError("amp: 0 < amp <= 1")
        self.off(timeout_s=timeout_s)
        self.ip.write(0x08, 0)
        self.set(amp=amp, enable=True, timeout_s=timeout_s)

    def stop(self, timeout_s=1.0):
        self.off(timeout_s=timeout_s)

    @staticmethod
    def adc_counts(amp):
        """rms ADC counts in the digital loopback of the AD9361 for a given amp"""
        return DAC_RMS_AT_FULL_SCALE * amp / 16.0
