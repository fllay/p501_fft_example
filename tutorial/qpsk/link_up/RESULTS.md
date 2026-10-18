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
