"""One-call AD9361 bring-up for the P501 overlays.

    import p501_radio
    ad = p501_radio.bring_up(ol)                 # clocks, LO, calibrations, filters, FDD: the AD9361 is configured over SPI
    p501_radio.settle(ad, ol, measure)           # optional: repeat the TX/RX start until measure() >= 45 dB

This is the *only* software the data path needs. The chip has to be configured over SPI before it produces a data clock,
so this part cannot be left out; but there is no sample-moving code left in Python: with the DDS overlay the tone is generated in
the FPGA, with the FFT overlay the spectrum is computed in the FPGA. The sequence is the one of the bring-up notebooks
(see boards/P501/docs/AD9361_BRINGUP_REPORT.md): 3.84 MSPS, 1R1T, TX1 and RX1.
"""
import sys

sys.path.insert(0, '/home/xilinx/jupyter_notebooks')
from ad9361_driver import (AD9361, FIR_RX1, FIR_TX1,                       # noqa: E402
                           REG_ENSM_CONFIG_1, TO_ALERT, FORCE_ALERT_STATE)
import ad9361_full_bypass_test as fb                                         # noqa: E402
from ad9361_fir_test import make_fir_coef                                    # noqa: E402

OBS = 0x3F5                      # observation/loopback register of the AD9361: bit0 = digital loopback
FS_HZ = 3_840_000                # sample rate of the clock-chain preset


def bring_up(ol, lo_hz=700_000_000, rf_bw_hz=4_000_000, tx_atten_db=10, rx_gain_index=45):
    """Configure the AD9361 for 3.84 MSPS, 1R1T (TX1/RX1) at the given LO and enable the axi_ad9361 core.

    The TX attenuation is held at its maximum (89.75 dB) until the calibrations have run, then set to `tx_atten_db`.
    Returns the AD9361 object; `ad.info` holds the lock flags and calibration results."""
    ad = AD9361()
    ad.power_up_clocks()
    ad.set_tx_atten_db(89.75)          # quietest before anything is switched on: the calibrations below run with the TX path active
    if not ad.set_bbpll_rate(983_040_000):
        raise RuntimeError("BBPLL did not lock")
    ad.set_clock_chain()                                                     # 3.84 MSPS
    ad.synth_cp_calib(False)
    ad.synth_cp_calib(True)
    rx_ok = ad.set_rx_lo_freq(lo_hz)
    tx_ok = ad.set_tx_lo_freq(lo_hz)
    ad.enable_rx1_tx1()
    fb.axi_ad9361_core_enable(ol.axi_ad9361, num_channels=2)
    ad.reg_write(fb.REG_PARALLEL_PORT_CONF_1, fb.PP_CONF_1)
    ad.reg_write(fb.REG_PARALLEL_PORT_CONF_2, fb.PP_CONF_2)
    ad.reg_write(fb.REG_PARALLEL_PORT_CONF_3, fb.PP_CONF_3_LVDS_MODE)
    ad.reg_write(fb.REG_RX_CLOCK_DATA_DELAY, fb.RX_CLOCK_DATA_DELAY)
    ad.reg_write(fb.REG_TX_CLOCK_DATA_DELAY, fb.TX_CLOCK_DATA_DELAY)
    ad.reg_write(fb.REG_LVDS_BIAS_CTRL, fb.LVDS_BIAS_CTRL)
    cal = ad.analog_init(rf_rx_bw_hz=rf_bw_hz, rf_tx_bw_hz=rf_bw_hz, rx_freq_hz=lo_hz)
    ad.set_rx_manual_gain(rx_gain_index)
    ad.set_tx_atten_db(tx_atten_db)    # the requested level, only now that the calibrations are done
    ad.enable_fdd()
    coef = make_fir_coef()
    ad.load_fir_filter_coef(FIR_RX1, 0, coef)
    ad.load_fir_filter_coef(FIR_TX1, 0, coef)
    fb.axi_ad9361_core_enable(ol.axi_ad9361, num_channels=2)
    ad.rf_bw_hz = rf_bw_hz
    ad.info = {"product_id_ok": ad.product_id_ok(), "rx_lock": rx_ok, "tx_lock": tx_ok,
               "ensm": ad.ensm_state(), "calibrations": cal}
    ad.info["ok"] = bool(ad.info["product_id_ok"] and rx_ok and tx_ok and ad.info["ensm"] == 0xA)
    return ad


def settle(ad, ol, measure, min_rej_db=45, max_tries=40):
    """The AD9361's analog TX/RX state is random after each ALERT -> FDD transition (a known issue, see the bring-up report):
    repeat the transition until `measure()` (image rejection in dB of a test tone, supplied by the caller) is good.
    Returns (rejection_db, tries)."""
    for tries in range(1, max_tries + 1):
        rej = measure()
        if rej >= min_rej_db:
            break
        ad.reg_write(REG_ENSM_CONFIG_1, TO_ALERT | FORCE_ALERT_STATE)
        if tries % 8 == 0:
            ad.tx_quad_calib(ad.rf_bw_hz // 2, ad.rf_bw_hz // 2)
        ad.enable_fdd()
        fb.axi_ad9361_core_enable(ol.axi_ad9361, num_channels=2)
    return rej, tries


def loopback(ad, on):
    """AD9361 digital loopback: the TX data goes back to the RX data port inside the chip (no antennas needed)."""
    v = ad.reg_read(OBS)
    ad.reg_write(OBS, (v | 1) if on else (v & ~1))


def quiet(ad, atten_db=80):
    """Put the transmitter at a high attenuation (call after dds.off())."""
    ad.set_tx_atten_db(atten_db)
