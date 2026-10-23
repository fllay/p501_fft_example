# 16-QAM over the air: the B210 -> P501 link, what we measured and what it costs (2026-10-23)

Everything learned while the 16-QAM link (`PLAN_QAM16.md`) was taken from the digital loopback to the air, in one place: the hardware of both radios, every measurement with its numbers, the structure of the remaining error, the power budget of 16-QAM against QPSK, and the options (hardware and signal processing) to close the gap. Raw numbers: `results_board_*.txt`, `results_b210_diagnosis.txt`, `results_link_budget.txt`. Scripts are listed in section 9.

## 1. Summary

* **Receiver and transmitter are fine.** Digital loopback EVM -30 dB, 0 errors in 1.75 M symbols; P501 TX -> P501 RX over the air EVM -22.8 dB (SER 0 at 20 dB TX attenuation); P501 TX -> B210 (GNU Radio receiver) EVM -19.6 dB, SER 0.
* **The B210 -> P501 link is limited by the received level, not by a fault.** At the antenna distance of the live notebook the P501's ADC sees the B210 at 137 counts rms (RMS 0.5, gain 76 dB), about 23 dB above a flat noise floor, with no spur and no interferer; the receiver model on that raw capture gives EVM -16.1 dB, SER 1.2e-3, 0 bad frames in 405. At RMS 0.3 (84 counts) it gives -13.5 dB, SER 4.9e-2, and the live notebook's -10.1 dB (SER 0.18) was at about 55 counts. EVM follows the level.
* **The B210's own transmission is clean at gain 76 dB / RMS 0.5**: averaging the soft symbols over 8 frames (the B210 repeats one frame) gives -30 dB, so anything that is the same in every frame (TX non-linearity, static ISI) is below -30 dB. Above about 78 dB gain the B210 compresses (section 4).
* **In a bad link state a multiplicative modulation limits 16-QAM at about -19 dB EVM** (sections 5, 5c); **in a good state it is absent and EVM is thermal-limited (-22 dB at 110 counts, SER 1e-6, section 5c).** What switches between the states is not yet known (not the TX frequency, not the P501 bring-up, not IQ imbalance, not an interferer).
* **Power budget (section 6): 16-QAM needs 7.3 dB more received power than QPSK in theory, 8.4 dB on this link for SER 1e-3, and about 15 dB for EVM -18 dB.** That is why the same B210 power works for QPSK and not for 16-QAM.
* **The P501's transmitter is 15 to 20 dB stronger than the B210's** (it has a PA, section 2): P501 -> B210 is stable at long distance, B210 -> P501 is the weak direction. An LNA on the P501 gains 2.5 to 4 dB (not 1 to 2 dB, an earlier answer undercounted); a PA on the B210 is the bigger lever.
* **Signal processing:** forward error correction (simulated: 7 to 10 dB in Es/N0 for the same frame error rate at half the rate, section 10), a QPSK fallback (7 to 8 dB), frame combining (shown on captures), see section 7.

## 2. The two RF front ends

**P501** (`/home/pi/projects/2_ADI_IIO/P501.pdf`, "PZSDR P401 P501" schematic V1.0, sheet 25 of 25 "AD9361 TX/RX", the PDF is page 23):

* TX1: AD9361 TX1A -> 18 pF caps -> TCM1-63AX+ balun (10 MHz to 6 GHz) -> amplifier **U42, labelled "22dbm"** -> RF switch U41 (control `TRX1-nTX-RX`) -> **TRX1** SMB.
* RX1: AD9361 RX1A <- balun TCM1-63AX+ <- switch **U43** (control `RX1-TRX-nRX`): RF2 -> **RX1** SMB; RF1 -> U41 RF2 -> TRX1 SMB. So **RX1 is behind one switch, TRX1 behind two** (and the PA branch is isolated by U41).
* **No LNA and no filter** in the receive path, nothing between the connector and the AD9361 but a switch (two on TRX1), a balun and DC-block capacitors. The sheet gives no part numbers for the switches and the amplifier (generic symbols): the loss is an estimate, **1 to 2 dB**, so the receive noise figure is about **3 to 5 dB** (AD9361 about 2 to 3 dB at high gain plus the loss).
* RX2/TRX2 exist the same way on the second channel (not used).

**B210** (Ettus spec sheet and UHD manual, `b200-b210_spec_sheet.pdf`, `page_usrp_b200`): AD9361 RFIC, 70 MHz to 6 GHz, receive noise figure **< 8 dB**, output power **> +10 dBm**, IIP3 -20 dBm, maximum RX input -15 dBm, connector maximum TX +20 dBm, RX gain 73 dB, TX gain 89.5 dB, separate TX/RX and RX2 connectors per channel. The Ettus pages we could read do not describe its filter banks or say whether it has an external LNA or PA (the knowledge base answered 403); we do not state them.

| | P501 | B210 |
|---|---|---|
| TX power | PA "22dbm" (up to about +20 dBm at the connector) | > +10 dBm at the maximum gain, but compresses above about 78 dB gain; at 76 dB much less (not measured, about 0 dBm is a guess) |
| RX noise figure | about 3 to 5 dB (estimated from the schematic) | < 8 dB (spec) |
| RX protection | none (a strong out-of-band signal reaches the AD9361) | not known |

Consequence: **P501 TX is 15 to 20 dB above the B210's, the receivers are comparable or the P501's is better.** The asymmetry of the link is transmit power.

## 3. Measurements (all with this receiver, 960 ksym/s, 915 MHz)

| Test | Result |
|---|---|
| Digital loopback (AD9361 internal), amp 0.15 / 0.25 / 0.40 | lock in 23 ms, 0 errors in 1.75 M symbols, EVM -30 dB |
| P501 TX -> P501 RX, antennas a few cm apart | SER 0 at TX attenuation 20 dB (EVM -22.8 dB); 5.7e-6 at 22; 6e-3 at 26; the PLL loses the carrier from about 32 dB; the synchroniser still finds every frame to 44 to 46 dB and fails at 52 dB and more |
| P501 TX -> B210 with the GNU Radio receiver | SER 0 at 20 dB (EVM -19.6 dB), 2.6e-5 at 26 dB |
| B210 -> P501, first session (strong link), B210 gain 80 to 86, RMS 0.35 | SER 2.7e-6 at 80 dB, 0 errors in 2.6 M symbols at 82, 84, 86; EVM -18 to -24 dB |
| B210 -> P501, weak-link session (6 to 9 dB less received power at the same settings) | the receiver locks and decodes only down to AGC gain 55 to 60; EVM -10 to -12 dB at the live notebook's setting |
| B210 -> P501, live notebook, B210 76 dB / RMS 0.42, antennas apart | EVM -10.1 dB, SER 0.18, AGC gain 14.4 (about 55 counts), clock -42 ppm |
| B210 -> P501, live notebook, antennas very close | EVM -22.7 dB, SER 0 in the last frames, AGC gain 1.58 (about 500 counts), clock -16.5 ppm |
| B210 TX only, recorded by the B210 itself (`test_b210_record.py`, `analyse_rec.py`) | clean to 70 dB gain (out-of-band -44 to -51 dB, EVM -17.1 dB = the floor of the B210 -> B210 path); regrowth at 80 dB (-29 dB, EVM -15.6, SER 1e-2) and 86 dB (-21 dB, EVM -12.3, SER 0.6): **use B210 gain <= 76 dB** |

**Correction of `PLAN_QAM16.md` section 15.** It concluded that the -10 dB EVM "does not depend on the received level". That conclusion is wrong: those sweeps held the received level constant (TX gain against RMS) or changed only the P501's RX gain, which the AGC compensates, so none of them changed the SNR. The earlier "good session" (-18 to -24 dB) was a stronger link: the received level drifted by 6 to 9 dB between sessions.

## 4. What the P501's ADC sees (`p501_adc_capture.py`, `analyse_adc.py`, `analyse_adc_ls.py`, `analyse_avg.py`)

Overlay `p501_fft` (has the ADC DMA), AD9361 at 915 MHz, RX gain 76, one contiguous DMA transfer of 1.57 M samples (0.41 s, 405 frames). **Capture caution:** separate 8192-sample transfers leave gaps between the blocks and break any receiver run on them (an early analysis of such a capture gave EVM -11 dB and was discarded).

* **B210 off:** flat floor, 13.9 counts rms over the 3.84 MHz (8.1 counts in the 1.3 MHz of the signal), a small DC line, no interferer, no spur.
* **B210 on, gain 76, RMS 0.5:** 137 counts rms, peak 295; the signal occupies +-650 kHz about 23 dB above the floor and **nothing else changes** (the floor outside the band is identical: no regrowth, no spur, no wideband TX noise). RMS 0.3: 84 counts. Carrier offset +9.71 kHz, clock -10.6 ppm, gain stable to 0.8 %.
* **Receiver model (bit-exact integer model of the FPGA, FLL cold start) on the raw capture:** RMS 0.5: EVM **-16.1 dB**, SER 1.2e-3, 405 frames, 0 bad. RMS 0.3: **-13.5 dB**, SER 4.9e-2, 0 bad.
* **Least-squares fit of the known repeated frame** (FIR at 3.84 MSPS): residual -12.7 dB with one tap, -15.3 dB with 3 or more taps (RMS 0.5); the taps are a fractional-delay tail, there is no multipath echo. A linear channel (equaliser) is worth 1 to 2.5 dB at most.
* **Structure of the error** (soft symbols after the PLL, RMS 0.5): averaging N consecutive frames gives EVM -16.1 (1), -17.3 (2), -20.9 (4), -29.8 (8), -31.8 dB (32); RMS 0.3: -13.3, -14.8, -17.9, -26.3, -28.9 dB. The part that does not average away is below -30 dB (so the B210 transmitter and a static channel are clean). The error is **proportional to the symbol magnitude** (rms 0.28 / 0.49 / 0.64 level units for inner / mid / outer symbols), radial = tangential (-19.1 / -19.2 dB), the same in all 14 blocks of the frame, and **correlated from frame to frame** (normalised correlation +0.55 at lag 1, -0.69 at lag 3, -0.73 at lag 4, +0.67 at lag 8: a modulation near 137 Hz as sampled at the frame rate of 993 Hz). The complex gain of the capture does show lines at 137 Hz and its aliases (2122, 5101 Hz) but only 2 % / 2 degrees rms, too small to explain -16 dB.
* **Ruled out:** the timing loop (bandwidth 2pi/400 to 2pi/1600 give the same EVM), the receiver's clock-offset handling (synthetic signal at 40 dB SNR, 0 to 42 ppm: EVM -31 dB), TX compression at gain 76, a wideband or out-of-band interferer, the FLL/PLL settings (earlier sweeps).

## 5. The model of the link level (`link_budget_qam16.py`)

Two captures fit EVM(S) = A (137/S)^2 + B with S the received rms in counts, **A = 0.0115** (a fixed floor equivalent to about 15 counts rms in the signal band, of which 8 counts are the receiver's own thermal noise: **5 dB more than the TX-off floor, unexplained**) and **B = 0.013** (-18.9 dB, scales with the signal: the multiplicative part above). It predicts -10.7 dB at 55 counts (live notebook: -10.1 dB). **It does not reproduce the close-range point** (500 counts: -22.7 dB measured, -18.6 dB predicted), so B is not a constant of the radios: it depends on the setup. Treat the numbers below as indicative; the mechanism is open (section 8).

### 5b. Half the bandwidth (`qam16_frame_tx.py --symbol-rate`, `analyse_rate.py`, 2026-10-23, second session)

Same B210 gain 76 / RMS 0.5, same antennas, B210 at 914.995 MHz (carrier offset +4.7 kHz), captures back to back; the 480 ksym/s transmission plays the same 4-sps frame at 1.92 MS/s, the P501 sees 8 samples per symbol and the capture is filtered and decimated by 2 for the receiver model.

| | level | EVM | SER | thermal part (8.1 counts in 1.3 MHz, 5.7 counts in 650 kHz) | rest |
|---|---|---|---|---|---|
| 960 ksym/s | 96 counts | **-17.5 dB** | 5.6e-4 (404 frames, 0 bad) | 0.0071 | 0.0107 (-19.7 dB) |
| 480 ksym/s | 80 counts | **-17.3 dB** | 2.5e-4 (202 frames, 0 bad) | 0.0050 | 0.0136 (-18.7 dB) |

* **Halving the bandwidth does not improve the EVM** (-17.5 -> -17.3 dB; pure noise would have given about +1.4 dB net after the 1.6 dB lower received level). What is left after the thermal noise is about -19 dB at both rates: **the signal-proportional floor does not depend on the bandwidth**, so it is not a tracking-speed problem and neither a lower symbol rate nor OFDM would remove it. Lowering the rate only buys the thermal 3 dB per halving, at half the data rate.
* **The "fixed floor 5 dB above the TX-off noise" of section 5 is not constant:** in this session (915 MHz LO of the B210 shifted by 5 kHz, 96 counts) EVM is the thermal part plus B = 0.013 with no excess (predicted -17.0 dB, measured -17.5 dB), whereas the first session (B210 at 915.000 MHz, offset +9.7 kHz) had an excess of about 0.008 at 137 counts and 0.022 at 84 counts. A digital frequency shift of +-5 kHz applied to the captures does not change the EVM of the receiver model (-16.3 / -16.3 and -17.5 / -17.5 dB), so the carrier offset handling of the receiver is not the cause: the difference is in the link between the sessions (the TX frequency, the antennas, the environment). Open.

### 5c. Why the sessions differ: good and bad states (`analyse_hop.py`, `analyse_struct.py`, `analyse_resid.py`, `analyse_image.py`; captures in `sim/hop/`, `sim/bu/`)

Two more experiments in a third session, same antennas, B210 at gain 76 / RMS 0.5, 960 ksym/s, levels 92 to 122 counts:

* **TX frequency hop** (915.000, 914.995, 915.005 MHz every 8 s, 18 captures in one P501 bring-up): EVM **-20.9 to -23.0 dB at all three frequencies** (means -21.6 / -22.0 / -22.2 dB), SER 0 to 1e-3 in single captures. **The TX frequency is not the cause.**
* **Eight separate P501 bring-ups** (the AD9361 configuration is redone before every capture): EVM -21.9 to -22.8 dB, mean **-22.4 dB** at 115 counts, SER 4e-7. **The P501's random analog state after a bring-up is not the cause.**
* **IQ imbalance** (widely linear least-squares fit with the mirrored frame as a regressor): the image is **-41 to -43 dB** in all captures of all sessions, and removing it changes the residual by 0.1 dB. Not the cause.
* **Interferer or bursts:** the residual after removing the known frame has a white-like power against time (std/mean 0.057 against 0.051 for white noise in 100 us windows) in every session: no burst, no periodic interferer.

| session | EVM at level | error / |s| (inner, mid, outer) | frame-to-frame correlation of the error (lag 1, 2, 4, 8) | residual spectrum |
|---|---|---|---|---|
| A (c1, c2): B210 915.000 MHz | -16.3 dB at 137, -14.1 dB at 83 counts | 0.19 / 0.15 / 0.15 | +0.56 -0.11 -0.77 +0.69 (period 8 frames) | signal-shaped hump 5 to 12 dB above the floor |
| B (r960): 914.995 MHz | -17.5 dB at 96 counts | 0.21 / 0.13 / 0.12 | -0.14 -0.48 +0.32 -0.25 (other period) | hump, 8 dB |
| C (hop, bu): 914.995 and others | **-22 dB at 92 to 122 counts** | 0.16 / **0.07 / 0.06** | **0.0 (none)** | nearly flat, 1 to 3 dB |

* **In the bad states (A, B) the received signal carries a multiplicative modulation** (the residual has the signal's own spectral shape: hump over +-550 kHz; the error grows with the symbol magnitude; averaging 8 frames removes it, which means it varies from frame to frame with a period of a few frames and with a different period in each session). **In the good state (C) it is absent and the EVM is the thermal part alone:** at 115 counts the thermal noise (8.1 counts in 1.3 MHz) gives -23.0 dB, measured -22.4 dB.
* **So the "fixed floor" and the "-19 dB signal-proportional floor" of section 5 describe the bad states, not the link.** In a good state the 16-QAM link reaches EVM -22 dB at about 110 counts, SER about 1e-6, with no coding. The earlier "-10 dB at every setting" and the first-session "-16 dB at 137 counts" were bad states.
* **Not yet identified:** what changes between sessions. The remaining candidates are a time-varying state of the B210 transmitter (LO phase noise of its synthesiser, which is set again at every start of the transmitter), the antenna or cable arrangement (a loose or moving connector gives exactly a multiplicative modulation, at the frequency of the vibration), the PC (load, USB), and the environment. The modulation is slow compared with the symbol rate (it is not corrected by a faster loop) and independent of the symbol rate (section 5b), the TX frequency, and the P501 bring-up.
* **Practical:** treat the EVM of a first capture as a health check of the link state; do not touch antennas or cables during a measurement; repeat a measurement after restarting the transmitter before concluding.

### 5d. Restarting the B210 transmitter (`rs` captures: one P501 bring-up, 50 records of 0.2 s every 2.5 s while a shell loop restarted `qam16_frame_tx.py` six times for 20 s each)

33 of the records contain the transmitter (the others are the gaps between restarts, rms 18 counts), all at +4.45 kHz:

| run (records) | level | EVM | SER (per 0.2 s record) |
|---|---|---|---|
| 1 (00 to 04) | 103 to 120 counts | -20.2 to -23.1 dB (-22.4 at 117 counts) | 0 |
| 2 (06 to 12) | 111 to 122 | -22.0 to -22.7 | 0 |
| 3 (14 to 20) | 117 in the first record, then **83 to 95** | -22.6, then **-18.5 to -20.0** | up to 1.3e-4 |
| 4 (22 to 28) | 78 to 110 (rising) | -17.8 to -19.8 | up to 6.8e-4 |
| 5 (30 to 36) | 109 to 118 | **-19.0 to -20.6** (at the level where runs 1 and 2 gave -22.5) | up to 3.3e-5 |

* **The P501 did not change during this test** (one bring-up for all the records), so the variation comes from the B210's transmission or the air path. Same settings, same antennas, nobody touched anything.
* **The B210's output level wanders by 3 dB within a run** (117 -> 86 counts a few seconds after a start; 78 -> 110 within 7 records) **and the quality changes with it and independently of it**: at the same level (about 117 counts) EVM is -22.5 dB in runs 1 and 2 and -19 to -20.6 dB in run 5. Over all the sessions the EVM at 90 to 137 counts has been anywhere between -16 and -23 dB.
* Summary of the three sessions and this test: **the B210 transmitter has a time- and restart-dependent state (output level +-3 dB, multiplicative modulation present or absent) that the P501 receiver sees; the P501 side is stable** (bring-up, TX frequency, IQ image, interferers excluded). Candidates unchanged: the B210's AD9361 TX analog state (random after each start, as the P501's is after each ALERT -> FDD transition) and its LO, thermal drift, cables and connectors.
* **Consequences:** (1) every measurement of the B210 link needs the EVM (or level) logged with it and several restarts; (2) a monitor on the P501 side (EVM, level) can tell a good state from a bad one and the transmitter can be restarted until it is good; (3) FEC is worth having for exactly this reason: the coded link survives the bad states (EVM -17 dB) with a margin of more than 10 dB (section 10); (4) a good state gives EVM -22 dB uncoded.

### 5e. Is there anything a band-pass filter would remove? (`p501_scan.py`, `analyse_scan.py`, `scan_s1.png`, 2026-10-23)

The P501 as a spectrum scanner: RX gain index 76 (the highest), LO stepped from 830 to 980 MHz in 3 MHz steps, 0.07 s of ADC data per step, slices of +-1.5 MHz joined on an absolute frequency axis; transmitter off (maximum attenuation). Levels are dB above the receiver's own noise floor, which is about -105 dBm in 3.84 MHz (an estimate: thermal -108 dBm plus a noise figure of about 3 dB).

* **No strong signal anywhere.** Apart from the B210 itself (910 to 920 MHz, 22 to 26 dB above the floor, the transmitter was still on) the strongest features are narrow lines up to 32 dB above the floor (about -73 dBm at the most) and a few weak cellular downlink carriers: 4 to 9 dB over 935 to 960 MHz, lines of 20 dB at 939.5 and 959 MHz. **The GSM900/B8 uplink band (880 to 915 MHz) is empty** in these 70 ms windows (a handset burst every 4.6 ms would have been seen), and the LTE B5 uplink as well.
* **Narrow lines at 833, 840.0, 850, 867, 875, 880.0, 900, 917.8, 939.5, 959 MHz** (5 to 32 dB): several are on round frequencies (840.0 and 880.0 are multiples of 40 MHz), so they are probably the receiver's own clock spurs; a scan with a 50 ohm load on RX1 would tell. None is inside the +-1.9 MHz window around 915 MHz (the nearest, 917.8 MHz, is outside it and is rejected by the AD9361's baseband filter).
* **Conclusion:** at this location and time there is no blocker that a 902 to 928 MHz band-pass filter would remove, and the filter's insertion loss (1 to 2 dB) would add to the noise figure. It is not needed for this link; an LNA's value is the 2.5 to 4 dB of section 6 and only if the link is thermal-limited (the good state, section 5c). Repeat the scan where the P501 will be used if the site is different (a base station nearby changes it).

## 6. Power budget: 16-QAM against QPSK (`results_link_budget.txt`)

**Theory (AWGN):** Es/N0 for SER 1e-3: QPSK 10.3 dB, 16-QAM 17.6 dB; for 1e-5: 12.9 dB and 20.1 dB. **16-QAM needs 7.1 to 7.4 dB more** at any SER from 1e-2 to 1e-6 (the same average power; the inner points are 6 dB closer).

**On this link** (levels in ADC counts rms at RX gain 76, B210 at 76 dB gain, antennas at the live-notebook distance):

| Target | Received level needed | Relative to QPSK SER 1e-3 |
|---|---|---|
| QPSK SER 1e-3 (EVM -10.3 dB) | 52 counts | 0 dB |
| QPSK SER 1e-5 (EVM -12.9 dB) | 75 counts | +3.2 dB |
| 16-QAM SER 1.2e-3 (measured, EVM -16.1 dB) | 137 counts | **+8.4 dB** |
| 16-QAM EVM -17 dB | 176 counts | +10.6 dB |
| 16-QAM EVM -18 dB | 275 counts | **+14.5 dB** |
| 16-QAM EVM -20 dB | not reachable with more power (floor B -18.9 dB) | - |

So to give 16-QAM the margin QPSK has at the same distance: **+8 dB for a usable link (SER about 1e-3), +15 dB for a clean one (EVM -18 dB)**. In free space +8.4 dB means 0.38 times the range (QPSK range x 0.38), +15 dB means 0.18 times. The QPSK numbers are the AWGN theory at the SNR the model predicts; **we did not measure QPSK on these captures** (the user reports that QPSK works at the same B210 power, consistent with 52 counts against the 55 to 137 counts seen).

**In a good link state** (section 5c: no multiplicative modulation, EVM = the thermal part, 8.1 counts rms in the 1.3 MHz of the signal at RX gain 76) the budget is the theory plus the thermal noise: level = 8.1 counts x 10^(Es/N0 / 20): **QPSK SER 1e-3 needs 27 counts, QPSK 1e-5 needs 36 counts, 16-QAM SER 1e-3 needs 61 counts, 16-QAM EVM -20 dB needs 81 counts, -22 dB needs 102 counts**; the 16-QAM penalty against QPSK is the theoretical 7.3 dB, and a 16-QAM link at the distance of the sessions A to C (92 to 137 counts) works uncoded. The 8.4 dB and 15 dB of the table above are for the bad state, in which the extra dB come from the modulation.

**Where the dB can come from** (estimates unless noted):

| Measure | Gain | Cost / note |
|---|---|---|
| PA on the B210 TX/RX output (20 to 25 dB gain, P1dB about +30 dBm for +20 dBm average with 16-QAM's 6.5 to 7 dB peak-to-average ratio) plus a harmonic filter | up to 15 to 20 dB (P501's PA level) | best lever; drive the B210 at 65 to 70 dB gain (clean); local rules for 915 MHz and amplified output apply; the B210 has a separate RX2 port, so no transmit/receive switch is needed |
| LNA + 902 to 928 MHz SAW on the P501 RX1 | 2.5 to 4 dB with the LNA first (NF about 1 dB), 1 to 2.5 dB with the SAW first (NF about 2 to 2.5 dB) | does not touch the -19 dB signal-proportional floor; the SAW protects against the cellular bands next to 915 MHz; keep the gain at 15 to 20 dB; use RX1 (TRX1 shares the path with the PA) and mind the P501's own TX close to the antenna; test with a bought module first |
| LNA + SAW on the B210 RX2 (P501 -> B210 direction) | 3 to 5 dB (B210 NF < 8 dB) | gain limited to 10 to 15 dB (IIP3 -20 dBm, maximum input -15 dBm) |
| Better antennas (gain, directivity) | dBi per side | plain |
| Forward error correction (rate 1/2) | **polar CA-SCL L=8: works 12.6 dB below the level the uncoded link needs for SER 1e-3 (simulation, model link); 6 dB better than uncoded QPSK at the same data rate in AWGN**; convolutional 3 dB | halves the throughput relative to uncoded 16-QAM; section 10 |
| QPSK payload as a fallback | 7.3 dB | the header would signal the mode |
| Frame combining (repeat and average the soft symbols) | measured: 4 frames take -13.3 dB to -17.9 dB and -16.1 to -20.9 dB | 4 times the throughput; works because the error is not white |
| Half the symbol rate | 3 dB | needs a front-end rebuild (the FPGA front end is built for 4 samples per symbol at 3.84 MS/s) |
| P501 receive RX gain / RMS above 0.5 | none / below 1 dB | the AGC makes RX gain irrelevant to SNR; the TX peaks are already about 0.9 of full scale |

## 7. Signal processing to improve robustness (before any hardware)

Nothing in the receiver loops is left to tune (PLL within 1.2 to 1.5 times of the ideal SER from 12 dB, timing and clock handling verified, AGC rounded). What remains:

1. **FEC with soft decisions.** Candidates for one frame (882 payload symbols, 3528 coded bits with Gray-mapped 16-QAM, 1 ms per frame): K=7 rate-1/2 convolutional with Viterbi (simplest), 5G NR LDPC, polar with CRC-aided list decoding (CA-SCL). Time budget: a serial successive-cancellation polar decoder for N = 4096 needs about 8,200 steps (about 40 us at 200 MHz), CA-SCL with list 8 about 330 us if run sequentially: a small decoder in the PL fits in the 1 ms frame. The error is multiplicative and frame-correlated, not Gaussian, so the real gain must be checked on the measured error; **simulated in section 10**.
2. A QPSK fallback mode in the header (the QPSK receiver already works at this B210 power).
3. Frame combining (a repetition code) as the trivial form of 1.
4. Not worth it: TX predistortion (static distortion below -30 dB), an equaliser (1 to 2.5 dB), raising the TX RMS above 0.5 (peaks are about 0.9 of full scale), retuning the loops.

## 8. Open questions

0. Why the multiplicative modulation of section 5c appears in some sessions and not in others (TX frequency, P501 bring-up, IQ image, interferer ruled out): the B210's state at each start, cables / antennas, the PC, the environment.
1. **Origin of the signal-proportional error of about -19 dB with a 137 Hz (frame-aliased) structure in the bad states.** Not the TX (clean at -30 dB when averaged), not timing, not clock offset, not the FLL/PLL settings tried. Candidates: a phase/amplitude modulation of the carrier by the radios' references or supplies (a 137 Hz line is in the gain of the capture, but only 2 %), the AD9361 RX analog path, a near-field coupling that changes with the setup (the close-range point -22.7 dB does not fit the model).
2. **The 5 dB excess of the fixed floor over the TX-off noise** (about 15 counts rms in the band against 8).
3. Whether QPSK on the same B210 transmission reaches the EVM the model predicts (needs a B210 QPSK transmission recorded by the P501 ADC).
4. P501's own estimated noise figure (3 to 5 dB) is from the schematic; a measurement with a noise source or a known signal would confirm it.
5. Open points of the receiver itself (`PLAN_QAM16.md` section 8): lock one symbol off near 6 kHz at low SNR; 3 to 4 bad frames after a gap.

## 9. How to reproduce

```bash
# B210 transmitter in the CLI (no GNU Radio Companion), keep the gain at 76 dB or less, one process owns the B210
cd /home/pi/projects/p501_fft_example && source tools/gnuradio_env.sh
python3 tutorial/qam16/qam16_frame_tx.py --tx-gain 76 --rms 0.5 --seconds 600     # --freq 914.9904e6 cancels the natural +9.6 kHz

# P501 ADC capture (the notebook kernel must be shut down; run as root on the board)
scp tutorial/qam16/p501_adc_capture.py xilinx@192.168.2.1:/tmp/
ssh xilinx@192.168.2.1 "echo xilinx | sudo -S bash -c 'source /etc/profile.d/xrt_setup.sh; source /etc/profile.d/pynq_venv.sh; python3 /tmp/p501_adc_capture.py <tag> 76 915e6 192'"
scp xilinx@192.168.2.1:/tmp/adc_<tag>.npy tutorial/qam16/sim/

# analysis (host)
cd tutorial/qam16; source ../../tools/gnuradio_env.sh
python3 analyse_adc.py off <tag>                       # spectrum and floor -> sim/adc_spectrum.png
python3 analyse_adc_ls.py sim/adc_<tag>.npy            # least-squares channel fit (PYTHONPATH=.)
python3 -c "import numpy as np; np.load('sim/adc_<tag>.npy').astype(np.complex64).tofile('sim/adc_<tag>.c64')"
python3 analyse_rec.py sim/adc_<tag>.c64 0.42          # the integer receiver model on the capture
python3 analyse_avg.py sim/adc_<tag>.c64               # frame averaging, structure of the error
python3 link_budget_qam16.py > results_link_budget.txt # power budget
gcc -O3 -march=native -shared -fPIC -o libfec.so fec_core.c -lm   # FEC study
python3 fec_sim.py selftest; python3 fec_run.py 800; python3 fec_extra.py   # -> results_fec.txt, fec_curves.png
```

## 10. FEC simulation (`fec_core.c`, `fec_sim.py`, `fec_run.py`, `fec_extra.py`, `results_fec.txt`, `fec_curves.png`)

**Set-up.** One codeword per 16-QAM frame: 882 payload symbols = 3528 coded bits (Gray mapping, random bit interleaver, max-log soft demapper), K = 1758 information bits (rate 0.498, 2 bits per symbol: the throughput of uncoded QPSK). Codes: K=7 convolutional code (133, 171) with soft Viterbi; polar code N = 4096 shortened to 3528 (design by Gaussian approximation, shortening checked against the encoder), plain successive cancellation (SC) and CRC-16-aided list decoding (CA-SCL, min-sum, list L). 600 to 1500 frames per point. The decoders are noiseless-checked and need 1 to 20 ms per frame on the host (C).

**AWGN, Es/N0 for a frame error rate of 1e-2 (uncoded 16-QAM would need 20.1 dB for the same FER, uncoded QPSK 12.9 dB):**

| Code | Es/N0 | gain over uncoded QPSK at the same data rate | memory per frame (estimate) |
|---|---|---|---|
| K=7 convolutional, Viterbi | 9.7 dB | 3.2 dB | 64 states x 1764 steps of survivor bits |
| polar SC | 7.8 dB | 5.1 dB | one path, about 24 KB |
| polar CA-SCL L=2 / 4 | 7.45 / 7.2 dB | 5.5 / 5.7 dB | L paths |
| **polar CA-SCL L=8** | **7.0 dB (6.8 dB designed at Eb/N0 1.5 to 2 dB)** | **5.9 to 6.1 dB** | 8 paths, about 200 KB (about 44 BRAM36 of 144) |
| polar CA-SCL L=16 / 32 | 6.9 / 6.7 dB (6.7 dB designed at 1.5 dB for L=16) | 6.0 to 6.2 dB | 16 / 32 paths |

* The polar design point matters a little: Eb/N0 1.5 to 2 dB is best (L=8: 6.8 dB), 4 to 5 dB loses 0.3 to 0.7 dB.
* The decoders are scale invariant, so no noise estimate is needed for the LLRs.
* The waterfall is steep: SC goes from FER 0.65 at 6.75 dB to 0.003 at 8 dB; the receiver needs to be above the threshold, not near it.

**On the measured link** (level model of section 5, the slow part of the multiplicative error replayed from the capture, the rest of it taken as white, so this is a model, not a measurement): received level for FER 1e-2: **convolutional 48 counts, polar SC 32 counts, polar CA-SCL L=8 about 32 counts** (AWGN-equivalent mapping through the EVM model gives 48 / 38 / 33 counts), against 137 counts for the uncoded link at SER 1e-3 and 52 counts for uncoded QPSK at SER 1e-3 (75 counts at 1e-5): **the coded 16-QAM link works at a level 12 dB below the uncoded 16-QAM link, 4 dB below QPSK at SER 1e-3 and 7 dB below QPSK at 1e-5.** In the live notebook's weak-link case (about 50 counts, EVM -10 dB, uncoded SER 0.2), polar SC and CA-SCL decode with FER 0 and the convolutional code with FER 5e-3.

**Caveats.** The part of the error that is not reproducible from the capture (variance B = 0.013, section 5) was taken as white Gaussian; the real one is proportional to the symbol magnitude and frame-to-frame correlated, so the real FEC gain can differ (a hardware test with an encoded frame through the B210 is the check). The bit interleaver spreads the symbol errors, but a burst longer than the frame would not be helped by any one-frame code. LLRs here are floating point; a decoder with 6 to 8 bit LLRs loses about 0.1 to 0.2 dB.

**Recommendation.** Polar code, N = 4096 shortened to 3528, CRC-16, **CA-SCL L=8 designed at Eb/N0 1.5 to 2 dB** (7.0 to 6.8 dB, 0.9 to 1.0 dB better than SC and 2.7 to 2.9 dB better than convolutional). Order of work: (1) transmitter encoder in the host/Python (and later the PL) and the frame format with the codeword in the payload; (2) decode frames pulled from the P501 receiver in software on the PS or the host (21 ms per frame on the host for L=8, so about 50 frames/s: enough for pictures and tests, not for 1000 frames/s); (3) a PL decoder, SC first (one path, about 8,200 steps, a few BRAM), the list later if the 1 dB is needed. Fallback if the polar rate matching or the decoder is too much: the convolutional code (smallest, 2.9 dB behind).

