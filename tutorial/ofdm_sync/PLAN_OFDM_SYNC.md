# Plan: tutorial 7 - which preamble does an OFDM link need? Short and long training sequences compared

Tutorial 6 built one OFDM modem twice (a Schmidl-and-Cox symbol, or a 128-sample short training field, followed by two long training symbols) and made it work. It did not ask whether the preamble is the right one. This project does what chapters 4d and 4e did for the QPSK loops: **several synchronisation methods, one study, the same measurements, then a decision** before anything is built in the FPGA.

The trigger was a question: *would a longer training sequence help the fine carrier estimate?* The honest answer is "it depends on what the carrier error costs and on what else the longer sequence buys", and that needs numbers.

## What has to be synchronised in an OFDM link

| | what | needs | current design (tutorial 6) |
|---|---|---|---|
| 1 | **frame detection** (is there a frame?) | a field with a repeat that survives noise: a plateau of the delay-and-correlate metric | S&C: period 32 (17-sample plateau); STS: period 16 (65-sample plateau) |
| 2 | **coarse timing** (where does it start, to within the prefix) | the plateau; or a cross-correlation with a known sequence | plateau centre, 6 samples of tolerance (`BACK`) |
| 3 | **coarse carrier** (up to +-120 kHz) | a short period: the phase of the correlation at lag 16 or 32 | lag 16 (STS) or 32 (S&C) |
| 4 | **fine carrier** (to well below 1 % of the 60 kHz spacing) | a long lag: the same samples one long symbol later | two long symbols, lag 64 (STS) or 80 (S&C), 64 products |
| 5 | **channel** (one tap per subcarrier) | known symbols on every used subcarrier | the two long symbols, averaged |
| 6 | **residual phase and gain**, symbol by symbol | pilots | 4 pilots, complex gain per symbol |
| 7 | **residual carrier over the frame** | the phase of the pilot gain against the symbol number | not used (item 6 absorbs it) |

## The question, and what is known before the study

* The fine carrier is estimated from **64 products** of two training symbols. At a link SNR of 20 to 23 dB the theory (error variance `1 / (N SNR)` in phase) gives 130 to 190 Hz rms; the B210 link showed a scatter of about 290 Hz frame to frame.
* A carrier error `df` costs inter-carrier interference of about `(pi df / 60 kHz)^2 / 3`: **-41 dB at 290 Hz**, against a link noise of -23 dB. On a recording of the real link the model receiver decoded 2800 frames with no symbol error although the estimate scattered by 290 Hz (the pilots remove the phase drift symbol by symbol).
* So the carrier accuracy is probably **not** what limits this link. The study has to show **where it starts to matter** (which error, which SNR) and whether the longer sequence earns its overhead somewhere else: the **channel estimate** (T1 alone gave EVM -24.0 dB, T1 and T2 averaged -25.5 dB: a real gain from averaging), the **timing**, or the **detection** of weak frames.

## The frames under study

All frames: 64-point FFT, prefix 16, 44 data symbols (24 x 16-QAM, 4 pilots), 32 idle samples; the preamble changes. `L` long training symbols follow a guard interval of 32 samples (a prefix of the long symbol, so the field is periodic with 64 over its whole length).

| name | short field | long field | preamble samples | overhead |
|---|---|---|---|---|
| **A** (tutorial 6, STS) | STS, 128 samples | L = 2 | 288 | 7.5 % |
| **B** (S&C) | S&C symbol, 80 samples (period 32) | L = 2 after a guard interval of 32 (tutorial 6's S&C frame gives each training symbol its own 16-sample prefix: 240 samples too, lag 80; the lab uses the one long field of all frames) | 240 | 6.3 % |
| C1, C2 | STS, 64 and 192 samples | L = 2 | 224, 352 | |
| D1 .. D3 | STS, 128 samples | L = 1, 4, 8 | 224 .. 672 | up to 15 % |
| E | **none** | L = 2, 4, 8 (detection on the long field itself, lag 64) | 160 .. 544 | |
| F | STS 128 | L = 1 (the guard interval gives a second lag-64 pair) | 224 | |

(The study varies the short and the long field independently; the table lists the points that matter.)

## The methods under study

**Detection and coarse carrier** (`detect_short`): delay-and-correlate with lag 16 (STS) or 32 (S&C) or 64 (long field only); plateau rule; the angle of the correlation gives the coarse carrier.

**Timing** : (a) the plateau centre (tutorial 6); (b) **cross-correlation with the known long symbol**, searched around the plateau estimate (a known-sequence method like the m-sequence of chapter 4e).

**Fine carrier** (`periodic_cfo`):

| method | what | needs |
|---|---|---|
| `none` | coarse only | |
| `orig` | the tutorial-6 estimate: lag 64 between the first two long symbols, 64 products | L >= 2 |
| `lag1` | lag 64 over the **whole long field**, the guard interval included | L >= 1 |
| `multi` | lags 64, 128, ... up to `L x 64`, each refined from the one before (Kay-style unwrapping): the error falls with the lag | L >= 2 |
| `short_multi` | **no long field**: lags 16, 32, ..., 112 inside the short field | the short field only |
| `pilot_slope` | the slope of the phase of the pilot gain over the 44 data symbols (a baseline of 3520 samples, for free) | any frame; a residual after the others |
| `average` | a one-pole average of the estimate over frames (the true carrier does not move in milliseconds) | a stable oscillator |

**Channel estimate**: average over `L` long symbols (L = 1, 2, 4, 8).

**Data**: per-symbol pilot gain as in tutorial 6 (the study uses the pilot-equalizer method; the decision-directed stock equalizer is a separate topic).

## The measurements

| id | question | output |
|---|---|---|
| E1 | how accurate is each fine-carrier method? | rms error of the carrier vs SNR, per method and per `L` |
| E2 | **how accurate must it be?** | EVM and symbol error rate against an injected carrier error (0 to 6 kHz), per SNR |
| E3 | what does the short field buy? | detection probability and timing error vs SNR and vs its length |
| E4 | what does the long field buy? | the channel estimate (EVM) and the fine carrier vs `L` |
| E5 | **the whole link**: frames A to F | symbol error rate and EVM vs SNR, with the overhead; a table of "dB gained per percent of overhead" |
| E6 | robustness | a 2-tap echo, a large carrier offset (the coarse range), a fractional delay |

Conditions: AWGN (and a 2-tap channel in E6), carrier offset uniform in the range of the field, a random fractional delay, a random carrier phase, 150 to 300 frames per point. Everything in floating point: this is the stage-1 model of the design flow (`tutorial/DESIGN_FLOW.md`); the integer model and the RTL come only for the winner.

## Files (the same kind as the QPSK chapters)

| file | what |
|---|---|
| `ofdm_sync_lab.py` | the frame builder (`Cfg`, `build`), the channel, the detectors, the carrier and timing estimators, the receiver (`receive`) |
| `study_cfo.py` | E1, E2 |
| `study_frames.py` | E3, E4, E5, E6 |
| `results_*.txt` | what each study printed |
| `README.md` | the chapter: what was found and what to build |

## Order of work

1. The lab with both kinds of sequence (this step), checked against tutorial 6: frame A through the lab reproduces the numbers of `ofdm_model.receive` (same EVM at the same SNR).
2. E1 and E2 (the question that started it).
3. E3 to E6.
4. A decision, written down with the numbers; only then the integer model, the RTL (as in tutorial 6) and a board test of the winner.

## Risks

* The model has no oscillator phase noise, no IQ imbalance, no sampling clock offset (it has an optional ppm): the B210 and the AD9361 have all three. The carrier error the real link sees may be larger than the lab's, and a long sequence also integrates **phase noise** (a long baseline is not free).
* The real link showed a **14 dB swing of the received level between runs**: a method that wins only above 25 dB SNR is not a winner.
* More training means fewer data symbols per millisecond: the overhead column is part of every comparison.
