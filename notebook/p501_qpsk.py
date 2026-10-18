"""Python side of the FPGA QPSK transmitter (rtl/qpsk_tx.v, chapter 4c): the register block is the one of the DDS, so P501Dds does the work.

    from p501_qpsk import P501QpskTx
    tx = P501QpskTx(ol.qpsk_regs, fs_hz=3_840_000)
    tx.start(amp=0.5)       # the PRBS-15 QPSK signal starts from its first bit, 960 ksym/s, 1.92 Mbit/s
    tx.stop()               # zeros to the DAC
"""
from p501_dds import P501Dds


class P501QpskTx(P501Dds):
    def start(self, amp=0.5, timeout_s=1.0):
        self.set(amp=amp, enable=True, timeout_s=timeout_s)

    def stop(self, timeout_s=1.0):
        self.off(timeout_s=timeout_s)
