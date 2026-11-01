# Tutorial 7 (study): which preamble does an OFDM link need? Short and long training sequences compared

Status: **floating-point study done** (E1 to E6 of [the plan](PLAN_OFDM_SYNC.md)); no RTL yet. Nothing here is measured on the board: the lab has AWGN, a fractional delay, a carrier offset, an optional echo, and **no oscillator phase noise, no IQ imbalance**.

The question that started it: *would a longer training sequence help the fine carrier estimate?* The answer, with the numbers below, is **no for the carrier, a little for the channel estimate, and the frame can lose its short field only at a price**.

```bash
python3 ofdm_sync_lab.py          # frame A of the lab = frame A of tutorial 6 (same samples, same EVM)
python3 study_cfo.py 150  | tee results_cfo.txt       # E1, E1b, E2
python3 study_frames.py 150 | tee results_frames.txt  # E3, E4, E5, E5b, E6
```

| file | what |
|---|---|
| `ofdm_sync_lab.py` | frame builder (`Cfg`: short field STS / S&C / none, `L` long symbols, pilot set), channel, detectors, carrier and timing estimators, receiver, Monte Carlo (`run`, `summary`) |
| `study_cfo.py`, `results_cfo.txt` | E1 accuracy of the carrier methods, E1b the pilots as a carrier estimator, E2 what a carrier error costs |
| `study_frames.py`, `results_frames.txt` | E3 detection and timing, E4 the long field, E5 the whole link and the pilots, E6 robustness |

## What the study found

**1. The carrier accuracy does not limit the link (E2).** At 23 dB SNR a carrier error of 300 Hz costs 0.09 dB of EVM, 1 kHz costs 0.8 dB, 3 kHz costs 4.5 dB and a symbol error rate of 6e-3. The carrier estimate of tutorial 6 scatters by 130 to 290 Hz. The pilots remove the phase the error causes, symbol by symbol; what is left is inter-carrier interference (about -41 dB at 290 Hz).

**2. A longer long field does make the carrier estimate more accurate (E1), but the estimator matters more than the length.**

| rms carrier error (Hz), SNR 23 dB | coarse only (STS lag 16) | `orig` (T1 and T2, 64 products: tutorial 6) | `lag1` (lag 64 over the **whole long field, guard interval included**) |
|---|---|---|---|
| L = 2 | 131 | 171 | **105** |
| L = 4 | 121 | 126 | 46 |
| L = 8 | 141 | 135 | 25 |

* Using the **guard interval and every pair** (`lag1`) is **free** (no extra samples) and about 40 % more accurate than the two-symbol estimate. The tutorial-6 fine estimate is not better than the coarse one from the STS alone at 23 dB.
* The multi-lag estimator (`multi`) of the lab uses only the last, shortest-overlap lag and is **not** a good implementation; its numbers understate what a weighted multi-lag estimator reaches. It does not change the conclusion.

**3. The pilots measure the carrier far better than any preamble (E1b).** The slope of the phase of the pilot gain over the 44 data symbols (a baseline of 3520 samples) gives the residual carrier to **2.3 Hz at 23 dB, 4 Hz at 18 dB, 12 Hz at 10 dB** (matches the theory). It is only available after the frame has been decoded, so it can correct the **next** frame: a feed-forward carrier tracker, like the frame tracker of chapter 4e. It is not needed for the error rate (finding 1), but it would make a long field useless for the carrier.

**4. The long field earns its place in the channel estimate (E4), not in the carrier.**

| L | overhead | EVM 23 dB | 18 dB | 14 dB | symbol error rate at 18 dB |
|---|---|---|---|---|---|
| 1 | 6.8 % | -19.06 | -14.00 | -10.09 | 3e-2 |
| 2 (tutorial 6) | 8.3 % | -20.28 | -15.27 | -11.21 | 1e-2 |
| 4 | 11.3 % | -21.08 | -15.98 | -11.98 | 6e-3 |
| 8 | 16.7 % | -21.52 | -16.47 | -12.46 | 4e-3 |

Averaging the channel estimate gains 0.8 dB of EVM at L = 4 and 1.2 dB at L = 8 (the theory's best case is 3 and 6 dB: the data noise itself is not reduced by the estimate). **In goodput of uncoded 16-QAM the longer field loses** (A 4.22, L = 4 4.09, L = 8 3.84 Mbit/s at 23 dB; at 14 dB L = 4 only breaks even): the extra symbols cost more samples than the fewer errors give back. A **coded** link, where a dB is worth more than uncoded, may think otherwise; that was not studied.

**5. The short field is needed less than assumed for detection, more for the carrier range (E3, E6).**

* Detection at 8 dB SNR (frames found): STS 64 0.87, STS 128 0.99, STS 160 (802.11a) 1.00, STS 192 1.00, S&C 0.91, **no short field, long field only: 0.95 (L = 2), 1.00 (L = 4)**. At 4 dB nothing is found at the threshold used (0.5), a lower threshold was not tried.
* The long field alone detects as well as a short field, but its coarse carrier range is the lag-64 range, **+-30 kHz**: at +-50 kHz the frame without a short field loses 44 % of the frames, the frames with an STS or S&C symbol none. (The real offsets of the P501 and the B210 are about +-10 kHz.)
* A short field is also what real receivers use for the AGC; the lab has none.
* **Timing by cross-correlation with the known long symbol is the most valuable single change:** the fraction of frames whose symbol windows stay inside their prefix at 8 dB goes **0.61 -> 0.93 (STS 128), 0.77 -> 0.91 (S&C), 0.51 -> 0.83 (STS 192)**; at 14 dB both are above 0.97. The plateau of a longer short field does not improve the start estimate (it gets worse with the length: 0.77, 0.61, 0.61, 0.51 for STS 64 to 192 at 8 dB; a wider, flatter plateau is my guess, I did not check).

**6. Pilots (E5b): four are a good compromise.** Two pilots give 8 % more goodput at 23 dB but 22 % bad frames at 14 dB; six or eight pilots gain only 0.3 to 0.5 dB of EVM and lose 8 to 17 % of the data subcarriers.

**7. Robustness (E6).** An echo of -6 dB inside the prefix costs every frame the same 2 dB of EVM; an echo beyond the prefix breaks every frame: no preamble helps with that.

## What I would build

| change | gain | cost | verdict |
|---|---|---|---|
| carrier from the whole long field (`lag1`) instead of T1/T2 | 40 % less carrier error | none (the guard interval is already sent) | **do it**: free, but note that finding 1 says it does not change the error rate |
| timing by cross-correlation with the long symbol | 0.61 -> 0.93 frames with a safe start at 8 dB | a 64-tap correlator searched over about 40 positions (a DSP block and some clocks: the symbol time is 20.8 us, the transform 9 us) | **worth it if the link is to work near 8 to 10 dB**; no gain at 14 dB and above |
| a shorter short field (STS 64) | 64 samples (1.7 % of the frame), detection 0.87 against 0.99 at 8 dB | the metric window has to shrink | only together with the cross-correlation |
| L = 4 | 0.8 dB EVM, 40 % fewer errors at 18 dB | 3 % goodput | **no for the uncoded link**, maybe for a coded one |
| pilot carrier tracker (feed-forward) | the carrier to a few Hz | a loop around the frame; the pilot phase slope | not needed for the error rate; useful if the oscillators drift or to drop `lag1` |
| drop the short field | 4 % overhead | carrier range +-30 kHz, no AGC time | **no** |
| more pilots | 0.3 dB EVM | 8 % of the data | no |

None of these is a large effect at the SNR of the lab link (23 to 28 dB). **The frame of tutorial 6 is not wrong; it is conservative in the short field and a little wasteful in the long one**, and the one robust improvement is the timing at low SNR.

## What this study cannot say

* **Phase noise.** A long baseline integrates oscillator phase noise: the real carrier error of an estimate over 4 or 8 long symbols may be worse than the lab's, and the common-phase tracking of the pilots has to follow it.
* **A coded link** (convolutional code, interleaving) changes the value of a dB; the study counts uncoded 16-QAM errors.
* **The AD9361 and the B210** have an IQ image and a DC offset, and the level at the ADC swung by 14 dB between runs of the same setting (tutorial 6, C.8): a detector threshold that works at 8 dB in the lab needs the real level.
* Only the carrier, the timing and the channel estimate of the OFDM symbols were studied; the sampling clock offset (ppm) was left at zero.

## Next

Pick one: the timing by cross-correlation (a chapter with an integer model, RTL and a board test, as in tutorial 6), or the pilot tracker, or measure the same study on a recording of the real link (a phase noise check first). See the verdict column.
