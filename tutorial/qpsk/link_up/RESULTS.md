# Link-up measurement P501 -> B210 (chapter 4.0, first part)

Setup: antennas on both radios, close together; LO 915.0 MHz on both; 3.84 MSPS on both; B210 RX2, gain 45 dB; P501 DDS tone at +500 kHz,
amplitude 0.5, TX attenuation 80 / 70 / 60 dB, 6 s on and 3 s off for each step. The P501 starts with the TX attenuation at its maximum
(`p501_radio.bring_up` does that before the calibrations) and ends with the DDS off and 89.75 dB.

Survey before transmitting (B210 receive only, gain 40 dB, 3.84 MHz windows): 915.0 MHz was the quietest of the candidates (strongest
signal only 3 dB over the median), 868 MHz similar, 433.92 MHz had weak activity, 922.5 MHz and 2.4 GHz had strong signals. Whether a
frequency and power may be used is a question of the rules where you are, not of the measurement.

| phase | n | tone (kHz) | std (Hz) | SNR in the best bin (dB) |
|---|---|---|---|---|
| TX attenuation 80 dB | 37 | 490.4854 | 0.5 | 27.3 |
| TX attenuation 70 dB | 37 | 490.4903 | 0.8 | 37.0 |
| TX attenuation 60 dB | 37 | 490.4951 | 0.9 | 48.0 |
| silence (three gaps) | 15 each | noise | - | 15.6 - 16.8 (noise peak in the search band) |

Result: the B210 sees the tone at **490.49 kHz instead of 500 kHz**: the two radios are **-9.51 kHz = -10.4 ppm at 915 MHz apart**
(the P501's LO is below the B210's, or equivalently the B210's reference is higher). The level follows the attenuation in 10 dB steps and
the tone is stable to under 1 Hz within a step, with a slow drift of about +0.5 Hz/s while both radios warm up (490.4854 -> 490.4951 kHz over 20 s).

What it means for the QPSK link: the offset is more than a few ppm TCXOs should have, so one of the references is off (the P501's is the
first suspect: unknown part and no calibration) and **the receivers need a frequency loop that pulls in about +-10 kHz = 1 % of the symbol rate**
(FLL band-edge before the Costas loop in GNU Radio, or a coarse estimate from a preamble tone with the P501's FFT chain). Symbol timing has the
same ppm offset: about 10 symbols of slip per second at 960 ksym/s.

A second line at 617.7 kHz (25 dB over the floor) is present without any P501 transmission: a spur of the B210 or an outside signal,
not ours; the tone search band is therefore limited to 440 - 560 kHz.

---

# The other direction: B210 -> P501

Setup: antenna on the B210's **TX/RX** port (transmit) and one on RX2, antennas of both radios a few centimetres apart; B210 TX gain 0/10/20/30 dB (6 s on, 3 s off,
tone +500 kHz, amplitude 0.5), P501 receive only with **RX gain index 70**, TX fully attenuated and DDS off. Scripts: `b210_tx_tone.py`, `p501_listen_tone.py`.

What had to be fixed before the P501 heard anything:

| finding | consequence |
|---|---|
| the B210's TX/RX port had no antenna (it was on RX2, receive only) | nothing was radiated: the antenna must be on TX/RX to transmit |
| the B210 does transmit the tone (checked on its own RX2 antenna: 57 dB over the floor at TX gain 0, +10 dB per 10 dB of gain) | the B210 side is fine |
| with RX gain index 45 the FFT floor of the P501 is exactly 0 dB (noise below one ADC count): weak signals vanish in quantisation | use RX gain 70 for weak-signal tests (the floor is then noise-limited, 12.7 dB median) |
| the P501 hears its own tone through its antennas at TX attenuation 80 / 70 / 60 / 50 dB with 3 / 13 / 24 / 33 dB over the floor | the P501 receive path works |
| antennas far apart: nothing at B210 TX gain 30 dB; antennas a few cm apart: the tone appears | the antenna-to-antenna path loss decides |

Result with the antennas close:

| B210 TX gain | tone at the P501 | SNR |
|---|---|---|
| 0, 10 dB | not seen | - |
| 20 dB | 509.48 kHz, in 44 of 62 readings | about 14.5 dB in a 58 Hz bin (marginal, noise peaks reach about 14 dB) |
| 30 dB | **509.4725 kHz**, std 3.3 Hz (68 readings) | **24 dB** in the raw 64k-point FFT; the **FPGA FFT chain** shows it in the 510 kHz bin, 5 dB over its floor |

Offset: the tone arrives 9.473 kHz above the 500 kHz that was sent: **B210 LO - P501 LO = +9473 Hz = +10.35 ppm at 915 MHz.**
The first test (P501 -> B210) gave -9510 Hz = -10.39 ppm: the same offset with the opposite sign, as it must be when the roles swap; the two
measurements, minutes apart, agree to 37 Hz (0.04 ppm), of the order of the warm-up drift. **Both directions confirm that the two radios are about 10.4 ppm apart.**

## B210 TX gain up to 60 dB (antennas a few centimetres apart)

Steps of 5 s with 3 s of silence, P501 RX gain index 70, the P501 ADC peak monitored (full scale 2047; the script stops raising the gain above 1500).

| B210 TX gain | FPGA FFT chain (bin / SNR) | raw 64k FFT: tone (kHz) | std (Hz) | SNR (dB) | P501 ADC peak |
|---|---|---|---|---|---|
| 30 dB | 510.0 kHz / 6.2 dB | 509.4684 | 3.3 | 24.7 | 37 |
| 40 dB | 510.0 kHz / 15.2 dB | 509.4683 | 1.0 | 34.6 | 37 |
| 50 dB | 510.0 kHz / 25.2 dB | 509.4680 | 0.4 | 44.9 | 41 |
| 60 dB | 510.0 kHz / 35.1 dB | 509.4676 | 0.3 | 54.9 | 53 |

The level rises by exactly 10 dB per 10 dB of gain in both receivers (the FPGA chain and the raw capture), the receiver is nowhere near clipping (peak 53 of 2047
at 60 dB), and the frequency estimate gets better with the SNR (std 0.3 Hz). Offset: **B210 LO - P501 LO = +9468 Hz = +10.35 ppm** at 915 MHz, the same as at 30 dB and
as the P501 -> B210 measurement (-9510 Hz). Between the first and the last step, 24 s apart, the tone moved by 0.8 Hz.
