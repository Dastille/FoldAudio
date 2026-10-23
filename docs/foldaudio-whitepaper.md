# Modulo Folding as an Alternative to Hard Clipping in Audio and Vibration Acquisition: Recovery Conditions, Self-Diagnosing Failure Detection, and Calibration

**Technical report, version 1.8**
**Date:** 2026-10-23
**Author:** Ashlynn (GitHub: [Dastille](https://github.com/Dastille))
**Repository:** <https://github.com/Dastille/FoldAudio> (MIT License)
**Evidence class:** numerical simulation, plus software folding of public measured accelerometer recordings (Section 6.6). No hardware folding front end was built or measured for this work.

> **Revision note (v1.8, 2026-10-23).** Section 6.6 adds a second measured dataset: 12 Paderborn KAt bearing records at 64 kHz [19], [20] (144 cells). The slew rule again predicted every cell and no failure was silent, but a pre-registered prediction that fold would gain at least 7.5 dB at 64 kHz was falsified: median headroom was +0.38 dB, and 3 of 12 records had none, because their peaks are single-sample spikes. Limitation 6 and the conclusion are updated. Numbers are asserted in `tests/test_paderborn.py` (skipped unless the files are cached; required by `scripts/local_check.sh --full`).
>
> **Revision note (v1.7, 2026-10-20).** Section 6.6 adds Table 13: the one-tone calibration of Section 7 applied to the 3,000 non-ideal measured-record cells of Table 12. At 60 dB injection SNR the 57 invisible cells fall to 0 and no trusted sample is more than 0.04 % of peak off. The same run showed that an inaccurate calibration is worse than none (at 40 dB injection SNR, invisible cells rose to 216; at 20 dB, 4 kept reconstructions slipped and 9,199 overloaded samples were left trusted), so Section 7.4 adds an acceptance gate on the fit residual: a calibration whose residual RMS exceeds 0.5 % of λ is not applied. With the gate, the 50, 40 and 20 dB runs reproduce the uncalibrated Table 12 numbers exactly. Limitations 1 and 10 are updated. Numbers are asserted in `tests/test_realdata.py` and `tests/test_calibrate.py`; the measured-record ones are skipped in CI unless the CWRU files are cached, and a local run log is committed.

> **Revision note (v1.6, 2026-10-19).** Section 6.6 adds Table 12: the 13 measured CWRU records passed through the 25 non-ideal front ends of Section 3.7 and the `UNRECOVERABLE` fallback of Section 3.6 (3,000 cells). No unwrap was kept that was off by λ or more. The run found a defect in the fallback mask: with a wrap-threshold error the front end can leave a slow excursion just past λ unwrapped and clipped at the converter rail, with steps too small for the event mask, so 117 overloaded samples in 21 fallback cells were left marked trusted. The fallback now also marks every rail-clipped sample untrusted (Section 3.6), which covers all of them. Limitation 1 is updated. Numbers are asserted in `tests/test_realdata.py` (skipped in CI unless the CWRU files are cached; a local run log is committed).
>
> **Revision note (v1.5, 2026-10-17).** Recovery results are now counted over cells that were actually overloaded (input peak ≥ λ). Five of the 280 failure-map cells (6 V row; peaks 4.94–4.99 V) never reach λ, so they were "recovered" trivially and inflated the recovery, agreement and accuracy counts. Tables 4, 6, 7 and 9, the abstract and Sections 4.4, 4.5, 6.3, 6.5, 7.3 and 7.4 are restated over overloaded cells, with an explicit overloaded-cell count. Failure, flagging and false-"recoverable" counts are unchanged (every failure is an overloaded cell). The seed-7 grid (Tables 3 and 5) and all 120 CWRU cells (Table 10) were already fully overloaded. No code result changed; the new counts are printed by `python -m foldcrypt claims` and asserted in `tests/test_claims.py`.
>
> **Revision note (v1.4, 2026-10-17).** Claim audit, no new experiments. Spot numbers that no demo table prints are now reproduced by `python -m foldcrypt claims` and asserted in `tests/test_claims.py` (Sections 3.6, 4.4, 4.5, 5.3, 6.2, 7.1, 7.4). Corrected: Section 4.5 σ-estimate error (about 5 % → at most 3.6 %); Section 5.3 burst peak (0.85–0.94 A on inspected cells → 0.82–0.98 A over all 280 cells; 5 of the 40 cells in the 6 V row never exceed λ). Section 3.6 now names the seven captures and adds the full seed-7 range. Section 7.5 is marked unverified. Section 6.6 notes that it is not checked in CI.
>
> **Revision note (v1.3, 2026-10-16).** Sections 4.4–4.5 add the combined derate-plus-noise slew specification and a blind quiet-window noise estimate. No earlier result changed.
>
> **Revision note (v1.2, 2026-10-15).** Section 4.4 now states a fitted noise margin for the slew specification ($k = 5$). Section 3.6 specifies the `UNRECOVERABLE` fallback output. No earlier result changed.
>
> **Revision note (v1.1, 2026-10-14).** Adds Section 6.6: the fold, blind-unwrap and self-check chain applied to 13 measured bearing-fault accelerometer records from the CWRU Bearing Data Center. Limitations 1 and 6, Sections 9.2 and 10, and the conclusion are updated accordingly. No v1.0 result changed.
>
> **Revision note (v1.0, 2026-10-13).** This version replaces the working draft v0.1 of 2026-10-02 ("FoldAudio: Intentional Modulo Fold Instead of Hard Clip"). Changes: (i) scope widened from audio to two applications, audio recording and IEPE vibration/shock instrumentation; (ii) blind absolute-level recovery added, so the oracle original used in v0.1 is no longer needed for AC-coupled signals; (iii) new sections on recovery conditions, blind failure detection, a 280-cell failure map, ADC quantization, non-ideal front-end sweeps, one-tone front-end calibration, and a per-capture status word; (iv) introduction and related work rewritten against published instrumentation and unlimited-sensing literature; (v) all numbers re-run from the repository on 2026-10-13. Two corrections to earlier repository notes are recorded in Section 6.3 and Section 4.6.

---

## Abstract

When a signal exceeds the input range of an acquisition chain, conventional converters saturate. The samples above the rail are lost, and the loss often goes unflagged. This report evaluates a different overload behaviour: a centred modulo (fold) nonlinearity with threshold $\lambda$, applied before quantization in place of hard clipping. Recovery uses first-order difference unwrapping. The input is recovered exactly, up to one global multiple of $2\lambda$, whenever $\max_n \lvert x[n]-x[n-1]\rvert < \lambda$, that is, whenever the slew rate stays below $\lambda f_s$. For AC-coupled signals such as IEPE accelerometer outputs, the remaining offset is fixed blindly from a zero-mean or quiet-baseline prior, with no reference signal. We pair the reconstruction with three blind diagnostics (baseline slip, near-threshold step, rail contact), which combine into a four-level capture status.

On synthetic audio at 48 kHz ($\lambda = 0.45$ full scale), fold-and-unwrap reconstructs three test signals to the 120 dB metric ceiling, against 3.3–4.2 dB for hard clipping. A deliberately impulsive fourth signal fails, and does so without tripping the diagnostics. On synthetic vibration records at 51.2 kHz ($\lambda = 5$ V), a 280-cell sweep of ringing impacts, 275 of which actually overload the input, shows that the slew rule predicts the outcome in all 275 overloaded cells (109 recovered, 166 failed). All 166 failures are flagged blindly, with no silent failures and no slip false alarms. ADC resolution from 4 to 24 bits does not move this boundary. Additive noise and front-end errors (fold-step gain, threshold, offset, INL) do not produce silent unwrap failures. They do, however, introduce a bounded, unflagged peak error. A one-tone (159.2 Hz) calibration removes the part of that error that the capture cannot otherwise reveal. The calibration study also gives a design rule: trim the fold step short, never long. On 13 measured bearing-fault accelerometer records (CWRU Bearing Data Center), with overload emulated in software by lowering $\lambda$ below the record peak, the slew rule again predicts all 120 cells, and all 94 failures are flagged with no silent failures. At 48 kHz, fold recovers exactly with $\lambda$ at 0.33–0.5 of peak (7.5–9.8 dB of extra range) and preserves kurtosis and crest factor, which clipping depresses. At 12 kHz the per-sample step of these impacts exceeds their peak, so no overload is recoverable. Limitations are stated in Section 8. The main ones are that no folding hardware was built, that the measured-data study applies the fold in software to records acquired within range, and that folding at the digitizer cannot repair saturation that has already occurred inside a sensor's internal amplifier.

---

## Contents

1. Introduction and problem statement
2. Related work
3. Method
4. Recovery conditions and failure detection
5. Experimental setup
6. Results
7. Front-end calibration
8. Limitations
9. Applications and integration guidance
10. Reproducibility
11. Conclusion
12. References

Appendix A. Notation · Appendix B. Revision history

---

## 1. Introduction and problem statement

### 1.1 Overload in audio capture

A digital audio recorder maps the analog input onto a fixed code range. A sound that drives the input past full scale (a shout close to the microphone, a percussive transient, wind on the capsule) is hard-clipped. Every sample above the rail is replaced by the rail value. The information in those samples is gone. Declipping algorithms (Section 2.3) can estimate plausible peaks, but they cannot measure them. Guo and Bhandari give a recent account of this failure mode on consumer recording devices, together with a hardware-validated modulo alternative [6].

### 1.2 Overload in IEPE accelerometer measurement chains

The same problem is more consequential in vibration and shock testing, where peak amplitudes are often the quantity under test. An IEPE (ICP®) accelerometer chain can overload at two points.

* **At the sensor's internal amplifier.** Hambric notes that ICP accelerometers are typically limited to a ±5 V output swing. Signals beyond it are clipped. The resulting broadband effect on a PSD is not always visible, so time histories should be checked for flat-topped peaks [1]. PCB TN-30 describes amplifier saturation from out-of-range input or from excitation near the sensor's resonance. Its signature is a clipped peak followed by an exponential decay of the baseline voltage. TN-30 also notes that a low DAQ sample rate can attenuate peaks and mask the saturation [2]. HBK gives the maximum linear output of a DeltaTron/ICP transducer as 5 V RMS (7.07 V peak) [5].
* **At the digitizer.** When the conditioned signal exceeds the selected input range, the DAQ clips. The NI-DAQmx documentation distinguishes analog (pre-digitization) from digital (post-digitization) overloads. It notes that the driver returns all data whether or not an overload occurred, and advises applications to "discard questionable data or return a flag when the driver reports an overload" [3]. The Siemens Simcenter knowledge base describes overloads as distorting both the amplitude and the frequency content of the data. It recommends range setting with headroom (commonly 6 dB), autoranging, and overload logging [4]. HBK states the consequence directly: "An overloaded measurement is erroneous and has to be re-measured. There is no way of estimating the correct result" [5].

Current practice therefore handles digitizer overload by prevention (ranging, headroom, wide-dynamic-range inputs) and by detection followed by rejection. In both cases the overloaded transient is not measured. For one-shot events such as crash, drop, pyroshock, machine run-up or destructive tests, repeating the test can be expensive or impossible.

### 1.3 Approach

This report evaluates replacing saturation at the digitizer with a modulo (fold) characteristic. Inputs beyond $\pm\lambda$ wrap back into the converter range instead of sticking at the rail. The out-of-range information is then encoded as an integer multiple of $2\lambda$ that is not recorded but can be inferred from the sample sequence. The approach belongs to the unlimited-sensing and modulo-ADC family [7]–[11]. This work adds no new reconstruction theory. Its contribution is an engineering evaluation aimed at instrumentation use:

1. a recovery condition stated as a slew-rate specification, $\max \lvert \dot{x} \rvert < \lambda f_s$, checked against simulation;
2. blind absolute-level recovery for AC-coupled signals, with no reference recording;
3. blind failure diagnostics and a per-capture status word, assessed for silent-failure and false-alarm rates;
4. sensitivity of the recovery boundary and of peak accuracy to quantization, sensor noise, and fold-step gain, threshold, offset and INL errors;
5. a one-tone front-end calibration and a resulting fold-step design rule;
6. the same pipeline applied to audio test signals, including a deliberate failure case.

In the repository and its command-line tools, the two application configurations are called **FoldAudio** (audio recording) and **ShockDAQ** (IEPE vibration and shock acquisition). They share one implementation.

### 1.4 Scope

The evaluation is confined to software models of a folding front end driven by synthetic signals. Specific numerical settings, such as $\lambda = 5$ V for the vibration chain, are modelling assumptions and do not describe a particular product. Section 8 lists the limitations.

---

## 2. Related work

### 2.1 Modulo sampling and unlimited sensing

Bhandari, Krahmer and Raskar introduced the Unlimited Sampling Framework. A modulo nonlinearity is applied before the ADC, and a bandlimited signal is recovered from its folded samples. The guaranteed sampling density depends on bandwidth, not on the ratio of signal amplitude to threshold. The guarantees extend to bounded noise, including quantization [7]. Bhandari, Krahmer and Poskitt later demonstrated a hardware modulo ADC prototype together with a Fourier-domain (Prony) recovery method [8]. Krishna et al. proposed an unlimited-dynamic-range ADC that also records two reset bits per sample. Explicit reset information relaxes the oversampling requirement to a per-sample change below $2V_{\mathrm{ref}}$. They validated the design in 65 nm CMOS simulation and with a discrete prototype [9]. Ordentlich et al. studied modulo-based conversion for reducing quantizer resolution [10]. For audio, Guo and Bhandari present USF-Audio, a hardware-validated modulo acquisition chain with a reconstruction method that also covers classical clipping and wrap-around overflow [6]. Vaghela, Appaiah and Mulleti address symbol detection directly on folded samples for low-bit-rate modulo ADCs [11]. That is a communications problem, not waveform recovery, but it shares the folding model used here.

Relative to this literature, the present work deliberately uses the simplest recovery available: first-order unwrapping with no side information. Under that choice the per-sample limit is $\lambda$, not the $2V_{\mathrm{ref}}$ of [9], and the work does not exploit the bandwidth-only guarantees of [7]. The method is chosen because it is cheap enough for streaming firmware and because its failure boundary can be stated as a single slew-rate specification. The report's focus is what happens at and beyond that boundary.

Folding-and-interpolating ADC architectures, which use folding internally to reduce comparator count [15], are a different technique. They do not extend the input range.

### 2.2 Wide-dynamic-range and dual-range acquisition

The established alternative is to widen the linear range. HBK's Dyn-X input digitizes the signal synchronously with two 24-bit delta-sigma ADCs and merges the two streams in real time. The result is a single 10 V peak input range with no attenuator settings. HBK reports noise and spurious content below −160 dB in a 6 Hz effective noise bandwidth [5]. In professional audio, Zaxcom NeverClip likewise combines two ADCs per input, for a stated 125–137 dB of dynamic range depending on the device [16]. Dual-gain channels and dual-range sensors follow the same principle. These solutions are mature and measured. Their cost is a second conversion path per channel. Folding instead keeps one converter of fixed range and moves the range extension into reconstruction, at the price of a slew-rate limit (Section 4). It does not compete with wide-range inputs on noise floor.

### 2.3 Declipping

Audio declipping reconstructs clipped samples using sparsity, inpainting, or learned priors [12], [13]. Zaviska et al. survey and benchmark the main families [13]. Declipping works on data already lost and can only estimate the missing peaks. Folding changes the acquisition so that the peaks are measured, then reconstructs them by inverting a known nonlinearity. The two approaches are complementary: declipping still applies when a fold reconstruction is reported as unrecoverable (Section 3.6).

### 2.4 Phase unwrapping

First-order difference unwrapping is the classical Itoh procedure from interferometric phase measurement [14]. Its validity condition (absolute sample-to-sample change below half the wrap period) is the condition analysed in Section 4.

---

## 3. Method

### 3.1 Fold (modulo) capture

Let $x[n]$ be the sampled analog input and $\lambda > 0$ the fold threshold. The ideal folding front end outputs

$$
y[n] \;=\; \mathcal{M}_\lambda\big(x[n]\big) \;\triangleq\; \big((x[n] + \lambda) \bmod 2\lambda\big) - \lambda \;\in\; [-\lambda,\, \lambda),
$$

so that

$$
x[n] \;=\; y[n] + 2\lambda\, m[n], \qquad m[n] \in \mathbb{Z}.
$$

The integer sequence $m[n]$ (the wrap count) is not stored. An $N$-bit quantizer follows the fold. It is modelled as an ideal mid-riser with step $\Delta = \lambda / 2^{N-1}$ on $[-\lambda, \lambda)$.

### 3.2 Baseline: hard clipping

The reference behaviour is saturation at the same threshold:

$$
c[n] \;=\; \min\!\big(\lambda,\, \max(-\lambda,\, x[n])\big).
$$

Throughout this report, silent soft saturation in a sensor or DAQ is modelled as hard clipping at $\lambda$ with no overload flag.

### 3.3 First-order unwrapping

Define the wrapped first difference

$$
\tilde{d}[n] \;=\; \big(y[n] - y[n-1]\big) - 2\lambda\, \operatorname{round}\!\left(\frac{y[n]-y[n-1]}{2\lambda}\right) \;\in\; [-\lambda,\, \lambda],
$$

and the unwrapped estimate

$$
\hat{x}[n] \;=\; y[0] + \sum_{k=1}^{n} \tilde{d}[k].
$$

Section 4.1 shows that $\hat{x}[n] = x[n] - 2\lambda\, m[0]$ for all $n$ under the recovery condition. The estimate is therefore exact apart from a single unknown global offset.

### 3.4 Blind absolute-level recovery

IEPE sensors are AC-coupled (constant-current excitation behind a coupling capacitor), so the long-run mean of the measured signal is close to zero. The global offset is chosen as

$$
k^\star \;=\; \operatorname{round}\!\left(-\frac{\mu}{2\lambda}\right), \qquad \tilde{x}[n] = \hat{x}[n] + 2\lambda\, k^\star,
$$

where $\mu$ is either the record mean (zero-mean prior) or the mean of the minimum-variance window of length $W$ (quiet-baseline prior, $W = 2048$ samples by default). This choice is correct whenever the true level estimate lies within $\lambda$ of zero. No reference recording is used. The audio results in v0.1 picked $k$ against the original signal (an oracle). Section 6.1 reports both.

### 3.5 Blind diagnostics

Three checks use only the folded samples $y$ and the reconstruction $\tilde{x}$:

* **Slip check.** Let $\mu_{\mathrm{start}}$ and $\mu_{\mathrm{end}}$ be the quiet-window means (window 1024 samples) inside the first and last 20 % of the record. Flag if $\lvert \mu_{\mathrm{start}} - \mu_{\mathrm{end}} \rvert > \lambda$. An unwrap error during an event leaves a persistent $2\lambda$ step in the baseline, and this check detects that step.
* **Edge check.** Flag if any wrapped step satisfies $\lvert \tilde{d}[n] \rvert \ge 0.9\,\lambda$, meaning the reconstruction ran within 10 % of its limit.
* **Rail check.** Count samples with $\lvert y[n] \rvert \ge \lambda - \epsilon$ (with $\epsilon$ one LSB for a quantized capture). An ideal fold output never sits at the rail. A non-ideal fold can push values past the converter range, where they clip (Section 3.7).

### 3.6 Capture status

The checks combine into one status per capture, in priority order:

| Status | Condition | Interpretation | Recommended handling |
|---|---|---|---|
| `UNRECOVERABLE` | slip **or** edge check set | unwrap may have slipped; level may be wrong by multiples of $2\lambda$ | do not use the reconstruction; fall back to the clipped value and report an overload (see below) |
| `BOUNDED_ACCURACY` | rail count > 0 (and not `UNRECOVERABLE`) | unwrap held, but some overload samples were clipped at the converter rail | use the reconstruction; tag overload peaks with a bounded-accuracy qualifier |
| `RECOVERED` | input exceeded $\lambda$, no flag | overload reconstructed | use the reconstruction; record that an overload occurred |
| `IN_RANGE` | input never exceeded $\lambda$ | conventional linear capture | normal handling |

**Fallback output for `UNRECOVERABLE`.** The reference implementation (`shockdaq.recover_or_clip`) discards the reconstruction and emits the folded samples $y$. Wherever $\lvert x \rvert < \lambda$ these equal the input exactly. Inside an overload event they are bounded in $[-\lambda, \lambda)$. A blind event mask marks those samples as untrusted, together with every sample at the converter rail, and the peak is reported as a lower bound, $\ge \lambda$. (The rail samples were added in v1.6: on measured records a wrap-threshold error can leave a slow excursion just past $\lambda$ unwrapped and clipped at the rail, outside the event mask; Section 6.6.) This carries the same information as a clipped capture with an overload flag. Clipping the reconstruction at $\pm\lambda$ was rejected: after a slip the reconstructed baseline is offset by $2\lambda$, so the clipped tail sits at the rail. On seven failing captures (the six seed-7 failure-map bursts at 8 kHz ring with $A$ = 8–40 V, and the past-limit impact case), clipping the reconstruction gave −11 to −16 dB SNR relative to a true hard clip (the hard-clipped input as reference), against −0.9 to +1.9 dB for the folded samples. Over all 33 failing cells of the seed-7 grid the ranges are −18 to −11 dB and −1.0 to +8.7 dB. The event mask covered every $\lvert x \rvert \ge \lambda$ sample in 168 burst cells (56 cells × seeds 7–9). It shares the isolated-impulse blind spot of Section 4.6.

### 3.7 Non-ideal front-end model

To test robustness, the ideal fold is replaced by the following model. All parameters are dimensionless fractions of $\lambda$:

$$
\begin{aligned}
m[n] &= \left\lfloor \frac{x[n] + \lambda(1 - e)}{2\lambda} \right\rfloor, \\
y_0[n] &= \operatorname{clip}_{[-\lambda,\lambda)}\!\Big( x[n] - 2\lambda (1+g)\, m[n] + o\,\lambda \Big), \\
y[n] &= Q_N\!\Big( y_0[n] + a\,\lambda \sin\!\big(\pi\, y_0[n]/\lambda\big) \Big),
\end{aligned}
$$

with fold-step gain error $g$ (the front end subtracts $2\lambda(1+g)$ per wrap while recovery assumes $2\lambda$), wrap-threshold error $e$, quantizer offset $o$, a smooth INL bow of amplitude $a$, and optional $N$-bit quantization $Q_N$. Sensor and electronic noise is added before the fold as white Gaussian noise with standard deviation $\sigma = \operatorname{rms}(x)/10^{\mathrm{SNR}/20}$. In that case the ground truth is the noisy input, because folding cannot remove noise that was present before it. The offset term is excluded from the accuracy error, since a conventional ADC has the same offset.

---

## 4. Recovery conditions and failure detection

### 4.1 Exact-recovery condition

**Proposition.** If $\lvert x[n] - x[n-1] \rvert < \lambda$ for all $n \ge 1$, then $\hat{x}[n] = x[n] - 2\lambda\, m[0]$ for all $n$.

*Proof sketch.* $y[n] - y[n-1] = \big(x[n]-x[n-1]\big) - 2\lambda\big(m[n]-m[n-1]\big)$. Wrapping into $[-\lambda, \lambda]$ removes the integer multiple of $2\lambda$ and leaves the unique representative in that interval. When $\lvert x[n]-x[n-1] \rvert < \lambda$, that representative is $x[n]-x[n-1]$ itself, so $\tilde{d}[n] = x[n]-x[n-1]$. Summing gives $\hat{x}[n] = y[0] + x[n] - x[0] = x[n] - 2\lambda m[0]$. $\square$

If a single step violates the condition, $\tilde{d}[n]$ differs from the true step by a nonzero multiple of $2\lambda$. That error persists in every later sample unless a later violation happens to cancel it.

### 4.2 Slew-rate form

A sufficient continuous-time condition is a bound on the slew rate:

$$
\sup_t \lvert \dot{x}(t) \rvert \;<\; \lambda f_s .
$$

For a sinusoid $A\sin(2\pi f t)$ the maximum slew is $2\pi A f$, which gives

$$
A\, f \;<\; \frac{\lambda f_s}{2\pi}.
$$

| Configuration | $\lambda$ | $f_s$ | Slew limit $\lambda f_s$ | Pure-sine limit $A f$ |
|---|---|---|---|---|
| Vibration chain (modelled) | 5 V | 51.2 kHz | 256,000 V/s | ≈ 40,700 V·Hz (e.g. 10 V at ≈ 4.1 kHz) |
| Audio chain (modelled) | 0.45 FS | 48 kHz | 21,600 FS/s | ≈ 3,440 FS·Hz |

The limit scales linearly with $f_s$ and with $\lambda$. It does not depend on how far the signal exceeds $\lambda$, so a slow 40 V transient is recoverable while a fast 6 V transient may not be. Multi-component signals have a tighter limit. The ringing burst used in the failure map (Section 5.3) carries a 0.4× component at 2.1 f, which reduces its admissible $A f$ by a factor of about 1.8 relative to a pure sine.

### 4.3 Quantization

With an $N$-bit quantizer, each folded sample carries an error of at most $\Delta/2$. A conservative condition is $\max \lvert \Delta x \rvert < \lambda - \Delta$. Section 6.4 shows that in practice the plain condition $\max \lvert \Delta x \rvert < \lambda$ predicts the outcome at every resolution tested, while the conservative condition is slightly worse at 4 bits. The recovery boundary does not move between 4 and 24 bits. Quantization therefore limits resolution (error within one LSB of the input) and leaves the recoverable range unchanged.

### 4.4 Noise

Noise added before the fold increases sample-to-sample differences. The recovery condition still applies exactly, but it applies to the noisy input the fold actually sees, not to the noiseless signal on a specification sheet. In practice, the slew specification must be derated by a margin of several noise standard deviations (Section 6.5). Recovery introduces no error beyond the noise itself.

A fitted form of this margin is $\max \lvert \Delta x_{\mathrm{signal}} \rvert < \lambda - k\sigma$, where $\sigma$ is the front-end noise RMS and the margin is clamped to $[0, \lambda]$. The fit used the nine noise rows of the non-ideal sweep (ideal, then 60 to 0 dB SNR; 56 cells × 5 seeds, 2,520 cells). The smallest $k$ on a 0.25 grid with no case of "predicted recoverable but slipped" is 4.75, rounded up to $k = 5$. Against the noiseless specification rule ($k = 0$), false "recoverable" predictions fall from 119 to 0 and, counting only the 2,497 cells whose input actually reaches λ, agreement rises from 2,378 to 2,412 (2,401 to 2,435 of 2,520 if the 23 in-range cells, which agree trivially, are included). The cost is 85 conservative predictions, all on overloaded cells at SNR ≤ 30 dB; rows at 40 dB and above are unchanged. A fit on three seeds alone gave $k = 4$, which still left 4 false predictions on the two held-out seeds. The margin covers noise only. The residual INL-driven misses of Section 6.5 (3–4 cells per INL row) still need the derated rule; the combined form in Section 4.5 clears them.

### 4.5 Front-end errors

When the unwrap holds, each front-end error leaves a bounded peak error that follows directly from the model in Section 3.7:

* **Fold-step gain error $g$:** $\tilde{x}[n] - x[n] = -2\lambda g\, m[n]$, a staircase proportional to the wrap count. At a peak of amplitude $X_{\mathrm{pk}}$ the error is approximately $g\,X_{\mathrm{pk}}$.
* **Threshold error $e$ and offset $o$:** maximum error of about $\lvert e \rvert \lambda$ and $\lvert o \rvert \lambda$. The affected samples spill outside the converter range and clip at the rail.
* **INL bow $a$:** maximum error $a\lambda$. The bow slope at mid-scale, $1 + \pi a$, also narrows the slew limit by roughly a factor $(1 - \pi a)$.

A derated slew condition that accounts for all four is

$$
\max_n \lvert x[n] - x[n-1] \rvert \;<\; \lambda \big(1 - 2\lvert g \rvert - \lvert e \rvert - \lvert o \rvert - \pi a\big).
$$

Combining that derate with the noise margin of Section 4.4 gives the single specification used when both are present:

$$
\max_n \lvert \Delta x_{\mathrm{signal}} \rvert \;<\; \lambda D - k\sigma,
\qquad
D = \max\big(0,\, 1 - 2\lvert g \rvert - \lvert e \rvert - \lvert o \rvert - \pi\lvert a \rvert\big),
$$

with the right-hand side clamped at zero. On the INL and combined rows of the non-ideal sweep (1,400 cells, five seeds; 1,376 of them overloaded), this combined rule removes the 12 residual false-"recoverable" predictions that the noise margin alone left, at a cost of 19 additional conservative cells (14 of them on the 5 % INL row). Ideal and ≥ 40 dB rows are unchanged. For live firmware, $\sigma$ need not be known a priori: the sample standard deviation of the quietest window of the folded capture estimates it (at most 3.6 % relative error over five synthetic quiet-baseline-plus-noise records, one of them folded mid-overload).

The gain-error staircase returns to zero whenever the signal returns to baseline ($m = 0$). The slip check therefore cannot detect it, and neither can the edge check. This accuracy error is invisible to blind diagnostics and must be removed by calibration (Section 7).

### 4.6 Scope of the blind diagnostics

The slip check detects persistent level errors, and the edge check detects reconstruction close to its limit. Neither detects an isolated violation that returns the reconstruction to the correct level afterwards. The audio test signal `harsh_kick` is an example. It has single-sample spikes of 2.5 FS with $\lambda = 0.45$. The true step of about 2.5 wraps to a residual of about −0.2 ($0.44\lambda$, below the 0.9λ edge threshold). The spike then returns to baseline, so no level slip remains. The reconstruction is wrong at those samples (SNR 14.1 dB, below the 16.5 dB of hard clipping), yet both checks read clear (Section 6.1). The zero-silent-failure result of Section 6.3 therefore holds for the ringing-transient signal class tested there. It is not a general guarantee. Isolated single-sample excursions larger than $\lambda$ need either a slew-limiting anti-alias filter ahead of the fold (Section 9) or a separate impulse detector.

---

## 5. Experimental setup

### 5.1 Audio test signals ($f_s$ = 48 kHz, $\lambda$ = 0.45 FS)

| Signal | Duration | Description | Peak / $\lambda$ |
|---|---|---|---|
| `tone_burst` | 1.0 s | 440 Hz sinusoid, raised-cosine envelope, peak 1.8 | 4.0 |
| `speech_like` | 2.0 s | three tones (180/900/2100 Hz) with 3.5 Hz syllabic modulation, three Gaussian-windowed 320 Hz bursts (peak 2.15), white noise 0.01 | 4.8 |
| `music_peaks` | 2.5 s | 110–330 Hz harmonic bed, seven kick-like Gaussian bursts (60 Hz + 1.8 kHz), noise 0.008 | 7.8 |
| `harsh_kick` | 1.0 s | 220 Hz tone at 0.15 with three single-sample ±2.5 spikes (deliberate failure case) | 5.6 |

Amplitudes are in units of digital full scale before the fold, so values above 1 represent the analog headroom that a folding front end would capture. Listening WAV files are peak-normalized. All metrics use the unscaled floating-point arrays.

### 5.2 Vibration test signals ($f_s$ = 51.2 kHz, $\lambda$ = 5 V)

| Case | Description |
|---|---|
| `gearbox_startup` | 2 s linear chirp 20 → 400 Hz with second harmonic and rising envelope, three Gaussian-windowed run-up transients (85 Hz + 1.2 kHz), noise 0.1 V RMS |
| `impact_transient` | 1.5 s quiet 60/180 Hz baseline, two damped ringing impacts (850 and 970 Hz fundamentals, 0.4× component at 2.1 f; rise 1.8 ms, decay 12 ms) |
| `impact_too_fast` | as `impact_transient` with amplitude parameter 60 V. Deliberately exceeds the slew limit |
| `gearbox_fold_long` | `gearbox_startup` through a non-ideal fold with fold step 1 % long ($g = +0.01$) |

### 5.3 Failure-map grid

A single damped ringing burst (Section 5.2 envelope, 0.5 s record, impact at 40 % of the record, 60 Hz baseline at 0.4 V, white noise 0.075 V RMS) is swept over amplitude parameter $A \in \{6, 8, 10, 14, 20, 30, 40\}$ V and ring frequency $f \in \{0.5, 1, 2, 3, 4, 6, 8, 12\}$ kHz. That gives 56 cells per noise seed. Five seeds (7–11) give 280 cells. The measured peak $\lvert x \rvert$ is 0.82–0.98 A over all 280 cells, so the 6 V row sits at the threshold: its peaks are 4.94–5.87 V, and 5 of its 40 cells never exceed $\lambda$. Those 5 cells (peaks 4.94–4.99 V) are recovered trivially, because the fold is the identity below $\lambda$, so from v1.5 on all recovery, agreement and accuracy counts are stated over the 275 overloaded cells (input peak $\ge \lambda$). With sensor noise added (Section 6.5) the overloaded count per configuration is 275–280. Recovery is always blind (quiet-baseline prior).

### 5.4 Metrics and outcome definitions

* **SNR:** $10\log_{10}\big(\sum x^2 / \sum (x-\tilde{x})^2\big)$. It is reported as 120 dB when the error energy is below $10^{-12}$ (numerically exact), so 120 dB is a ceiling, not a measurement.
* **Peak error:** $\big\lvert \max\lvert x \rvert - \max\lvert \tilde{x} \rvert \big\rvert$.
* **HF spectral bias:** relative difference in RMS spectral magnitude between estimate and reference over 0.15–0.45 of Nyquist. This is a simple indicator, not a standard vibration metric.
* **Recovered (ideal front end):** blind SNR ≥ 60 dB.
* **Recovered (quantized):** every reconstructed sample within one LSB of the input.
* **Recovered (non-ideal):** no unwrap slip, i.e. maximum absolute error < $\lambda$. **Accurate:** recovered, with maximum error ≤ 1 % of the true peak.
* **Silent failure:** not recovered, with neither the slip nor the edge check set. **Slip false alarm:** recovered, with the slip check set.

### 5.5 Software

Python 3 with NumPy, CPU-only, deterministic seeds. SciPy is used only to read the MATLAB files of Section 6.6. The test suite (`python -m pytest -q`) runs in GitHub Actions CI on every push and pull request to `main` (`.github/workflows/ci.yml`, Python 3.11 and 3.12); the test count is not hardcoded here, see the CI run for the commit. The full measured-record sweep test (`tests/test_realdata.py`) is skipped unless the CWRU files have been cached by `python -m foldcrypt shockdaq-real`; a local run with the cache is logged in `artifacts/cwru-run-2026-10-17.log`. CI also runs `pip-audit`, which audits the installed third-party dependencies only: foldcrypt itself is not on PyPI, so it is excluded (`--skip-editable`).

---

## 6. Results

All values below were regenerated on 2026-10-13 (Section 6.6 on 2026-10-14) with the commands in Section 10.

### 6.1 Audio

**Table 1.** Fold-and-unwrap compared with hard clip, $\lambda = 0.45$, $f_s$ = 48 kHz. Fold fraction is the fraction of samples with $\lvert x \rvert > \lambda$.

| Signal | Peak | max $\lvert\Delta x\rvert$ | Fold fraction | SNR, fold (dB) | SNR, clip (dB) | Difference (dB) | Slew condition met |
|---|---|---|---|---|---|---|---|
| tone_burst | 1.80 | 0.10 | 71.7 % | 120.00 (ceiling) | 4.22 | +115.78 | yes |
| speech_like | 2.15 | 0.13 | 15.4 % | 120.00 (ceiling) | 4.12 | +115.88 | yes |
| music_peaks | 3.49 | 0.30 | 9.0 % | 120.00 (ceiling) | 3.32 | +116.68 | yes |
| harsh_kick | 2.50 | 2.51 | < 0.01 % (3 samples) | 14.08 | 16.48 | −2.39 | **no** |

The demo selects the global offset against the original (oracle). Applying the blind zero-mean and quiet-baseline priors of Section 3.4 instead gives identical results ($k^\star = 0$, same SNR) on all four signals. For `harsh_kick`, the slip and edge checks both read clear, which is the blind-spot described in Section 4.6.

The three signals that satisfy the slew condition are reconstructed to numerical precision. The signal that violates it is reconstructed worse than hard clipping. The difference figures (+116 dB) reflect the 120 dB ceiling and are not perceptual measures. On these synthetic signals, the meaningful result is that reconstruction is exact inside the slew condition.

### 6.2 Vibration: individual cases

**Table 2.** $\lambda = 5$ V, $f_s$ = 51.2 kHz. "Oracle" picks the global offset using the original. "Blind" uses the zero-mean prior.

| Case | Peak (V) | max $\lvert\Delta x\rvert$ (V) | Peak err., clip (V) | Peak err., fold (V) | SNR clip (dB) | SNR fold, oracle (dB) | SNR fold, blind (dB) | Blind = oracle | HF bias clip / fold | Slip/edge | Rail samples | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gearbox_startup | 12.82 | 0.94 | 7.819 | 0.000 | 13.35 | 120.00 | 120.00 | yes | 0.014 / 0.000 | — | 0 | RECOVERED |
| impact_transient | 8.27 | 1.21 | 3.267 | 0.000 | 19.35 | 120.00 | 120.00 | yes | 0.080 / 0.000 | — | 0 | RECOVERED |
| impact_too_fast | 53.47 | 7.42 | 48.466 | 303.315 | 2.22 | −31.27 | −29.70 | no | 3.012 / 16.114 | slip + edge | 0 | UNRECOVERABLE |
| gearbox_fold_long | 12.82 | 0.94 | 7.819 | 0.100 | 13.35 | 42.00 | 42.00 | yes | 0.014 / 0.001 | — | 92 | BOUNDED_ACCURACY |

Hard clipping loses 7.8 V of a 12.8 V run-up peak and 3.3 V of an 8.3 V impact, and no clipping flag is raised. Inside the slew limit, fold recovery is exact and blind level recovery matches the oracle. Past the slew limit (`impact_too_fast`, max step 7.4 V > λ), the fold reconstruction is far worse than clipping. The status word reports it as `UNRECOVERABLE`, so the clipped values plus an overload flag are used instead. With a 1 % long fold step, the unwrap holds. 92 samples clip at the rail, the peak error is 0.10 V of 12.8 V, and the capture is reported as `BOUNDED_ACCURACY`.

Blind level recovery was also tested on records that begin in the middle of an overload (the first sample already wrapped). There, trusting the first sample ($k = 0$) gives −13.8 dB (gearbox) and −24.4 dB (impact), while both blind priors select the correct offset ($k^\star = +1$ and $-1$) and reach the 120 dB ceiling. When a DC shift of $1.2\lambda$ is added to the gearbox record, so the signal is no longer AC-coupled, the zero-mean prior fails (−4.0 dB). This is the expected limit of the prior.

### 6.3 Failure map (ideal front end)

**Table 3.** Outcome grid, seed 7 (56 cells, all 56 overloaded). `ok` = recovered blind; `ok~` = recovered with edge warning; `F!` = failed and flagged; `FS` = failed silently (none occurred).

| $A$ (V) \ ring (Hz) | 500 | 1000 | 2000 | 3000 | 4000 | 6000 | 8000 | 12000 |
|---|---|---|---|---|---|---|---|---|
| 6  | ok | ok | ok | ok | ok | ok~ | F! | F! |
| 8  | ok | ok | ok | ok | ok | F! | F! | F! |
| 10 | ok | ok | ok | ok | F! | F! | F! | F! |
| 14 | ok | ok | ok | F! | F! | F! | F! | F! |
| 20 | ok | ok | F! | F! | F! | F! | F! | F! |
| 30 | ok | ok | F! | F! | F! | F! | F! | F! |
| 40 | ok | F! | F! | F! | F! | F! | F! | F! |

**Table 4.** Failure-map summary.

| | Seed 7 | Seeds 7–11 |
|---|---|---|
| Cells | 56 | 280 |
| Overloaded cells (input peak ≥ λ) | 56 | 275 |
| Recovered / failed (overloaded cells) | 23 / 33 | 109 / 166 |
| In-range cells (never reach λ; trivially "recovered") | 0 | 5 |
| Slew rule agrees with outcome (overloaded cells) | 56 / 56 | 275 / 275 |
| Failures flagged (slip or edge) | 33 / 33 | 166 / 166 |
| — caught by slip check | 33 | 157 |
| — caught by edge check | 33 | 166 |
| Silent failures | 0 | 0 |
| Slip false alarms on recovered cells | 0 | 0 |
| Edge warnings on recovered cells | 1 | 7 |

The boundary follows the slew rule exactly on every overloaded cell. Before v1.5 this table read 114 / 166 recovered / failed and 280 / 280 agreement; those counts included the 5 in-range cells. Every failure in this signal class is flagged. Correction to earlier repository notes: the slip check alone catches 157 of 166 failures over five seeds, not all of them. The edge check catches all 166, and the combined status catches all 166. The edge check also produces 7 warnings on recovered cells near the boundary. Those are conservative warnings, not missed failures.

### 6.4 Quantization

**Table 5.** The same 56-cell grid (seed 7; all 56 overloaded) through an $N$-bit modulo ADC. "Recovered" means within one LSB of the input. "Tight rule" is $\max\lvert\Delta x\rvert < \lambda - \Delta$.

| Bits | LSB (V) | Recovered | Failed | Plain rule agrees | Tight rule agrees | Flagged | Silent | Slip false alarms | Edge on recovered |
|---|---|---|---|---|---|---|---|---|---|
| ideal | — | 23 | 33 | 56 | — | 33 | 0 | 0 | 1 |
| 4 | 0.6250 | 23 | 33 | 56 | 54 | 33 | 0 | 0 | 1 |
| 6 | 0.1562 | 23 | 33 | 56 | 56 | 33 | 0 | 0 | 1 |
| 8 | 0.0391 | 23 | 33 | 56 | 56 | 33 | 0 | 0 | 1 |
| 12 | 0.0024 | 23 | 33 | 56 | 56 | 33 | 0 | 0 | 1 |
| 16 | 0.0002 | 23 | 33 | 56 | 56 | 33 | 0 | 0 | 1 |
| 24 | < 0.0001 | 23 | 33 | 56 | 56 | 33 | 0 | 0 | 1 |

The same cells fail at every resolution from 4 to 24 bits. The plain slew rule agrees with the outcome in 56 of 56 cells at every depth. The conservative rule is slightly worse at 4 bits (54/56), because worst-case rounding seldom occurs. Quantization limits accuracy to one LSB and leaves the recoverable range and the failure flagging unchanged. The quantization sweep in the CLI uses a single seed. The five-seed result is reported for the ideal front end only (Table 4).

### 6.5 Non-ideal front end

**Table 6.** 280 cells per configuration (56 cells × 5 seeds); every count except "Overloaded" and "Silent" is over the overloaded cells only (input peak ≥ λ; noise raises the count above 275 at low SNR). "Silent" is 0 over all cells. "Rule (noisy)": slew rule evaluated on the input the fold actually saw. "Rule (clean)": rule evaluated on the noiseless burst, as a specification sheet would. "Derated": rule of Section 4.5. "Unflagged > 1 %": recovered with no slip but more than 1 % of peak in error, with neither the slip nor the edge check set.

| Configuration | Overloaded | Recovered | Failed | Rule (noisy) | Rule (clean) | Derated | Flagged | Silent | Slip false alarms | Edge on recovered | Accurate | Unflagged > 1 % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ideal | 275 | 109 | 166 | 275 | 275 | 275 | 166 | 0 | 0 | 7 | 109 | 0 |
| noise 60 dB | 275 | 109 | 166 | 275 | 275 | 275 | 166 | 0 | 0 | 7 | 109 | 0 |
| noise 40 dB | 276 | 109 | 167 | 276 | 275 | 276 | 167 | 0 | 0 | 6 | 109 | 0 |
| noise 30 dB | 276 | 109 | 167 | 276 | 275 | 276 | 167 | 0 | 0 | 6 | 109 | 0 |
| noise 20 dB | 278 | 111 | 167 | 278 | 277 | 278 | 167 | 0 | 0 | 11 | 111 | 0 |
| noise 15 dB | 278 | 109 | 169 | 278 | 275 | 278 | 169 | 0 | 0 | 15 | 109 | 0 |
| noise 10 dB | 279 | 99 | 180 | 279 | 265 | 279 | 180 | 0 | 0 | 13 | 99 | 0 |
| noise 5 dB | 280 | 76 | 204 | 280 | 242 | 280 | 204 | 0 | 0 | 4 | 76 | 0 |
| noise 0 dB | 280 | 53 | 227 | 280 | 219 | 280 | 227 | 0 | 0 | 11 | 53 | 0 |
| gain −5 % | 275 | 109 | 166 | 275 | 275 | 268 | 166 | 0 | 0 | 14 | 0 | 95 |
| gain −1 % | 275 | 109 | 166 | 275 | 275 | 272 | 166 | 0 | 0 | 7 | 16 | 86 |
| gain +0.1 % | 275 | 109 | 166 | 275 | 275 | 274 | 166 | 0 | 0 | 7 | 109 | 0 |
| gain +1 % | 275 | 109 | 166 | 275 | 275 | 272 | 166 | 0 | 0 | 7 | 22 | 80 |
| gain +5 % | 275 | 109 | 166 | 275 | 275 | 268 | 166 | 0 | 0 | 7 | 2 | 100 |
| threshold −10 % | 275 | 109 | 166 | 275 | 275 | 268 | 166 | 0 | 0 | 12 | 1 | 96 |
| threshold −2 % | 275 | 109 | 166 | 275 | 275 | 272 | 166 | 0 | 0 | 7 | 59 | 47 |
| threshold +2 % | 275 | 109 | 166 | 275 | 275 | 272 | 166 | 0 | 0 | 7 | 69 | 35 |
| threshold +10 % | 275 | 109 | 166 | 275 | 275 | 268 | 166 | 0 | 0 | 8 | 0 | 101 |
| offset +2 % | 275 | 109 | 166 | 275 | 275 | 272 | 166 | 0 | 0 | 7 | 59 | 46 |
| offset +10 % | 275 | 109 | 166 | 275 | 275 | 268 | 166 | 0 | 0 | 7 | 0 | 102 |
| INL 1 % | 275 | 106 | 169 | 272 | 272 | 275 | 169 | 0 | 0 | 6 | 106 | 0 |
| INL 2 % | 275 | 106 | 169 | 272 | 272 | 274 | 169 | 0 | 0 | 7 | 40 | 59 |
| INL 5 % | 275 | 105 | 170 | 271 | 271 | 261 | 170 | 0 | 0 | 13 | 15 | 79 |
| combined, mild¹ | 275 | 108 | 167 | 274 | 274 | 274 | 167 | 0 | 0 | 6 | 108 | 0 |
| combined, severe² | 276 | 108 | 168 | 275 | 274 | 274 | 168 | 0 | 0 | 7 | 40 | 61 |

¹ 60 dB noise, $g$ = 0.1 %, $e$ = 0.5 %, $o$ = 0.5 %, INL 0.2 %, 16 bit. ² 40 dB noise, $g$ = 0.5 %, $e$ = 1 %, $o$ = 1 %, INL 1 %, 12 bit.

The in-range cells (0–5 per row) are excluded above. They still matter for accuracy: under threshold, offset and INL errors some of them are more than 1 % off without any flag (for example all 5 in-range cells of each INL row, and 5 in the +10 % threshold row). That is a plain-ADC accuracy error, not a fold effect; `python -m foldcrypt claims` lists it per row.

Findings:

1. **No silent unwrap failures and no slip false alarms in any of the 24 configurations** (6,720 non-ideal cells in total, 6,623 of them overloaded).
2. **Noise moves the boundary but does not invalidate the rule.** Evaluated on the noisy input, the rule agrees on every overloaded cell at every noise level (275–280 per row). Evaluated on the noiseless specification, agreement falls to 265 of 279 at 10 dB SNR and 219 of 280 at 0 dB. The maximum reconstruction error relative to the noisy input is zero in every noise configuration. Noise costs slew margin only.
3. **INL narrows the boundary.** In 12 of the 6,623 overloaded non-ideal cells, all in the INL and combined configurations, the plain rule predicted success but the unwrap slipped. All 12 were flagged. The derated rule of Section 4.5 never predicted success for a failing cell (0 of 6,623). In exchange it is conservative: 69 overloaded cells it rejected did in fact recover.
4. **Fold errors cost accuracy, not reliability.** Table 7 gives the observed maximum errors on recovered cells. They match the bounds of Section 4.5.

**Table 7.** Maximum absolute error on recovered overloaded cells.

| Configuration | Max error (V) | Max error / peak | Predicted |
|---|---|---|---|
| gain −5 % | 2.00 | 9.9 % | ≈ $g$ of peak |
| gain −1 % | 0.40 | 2.0 % | ≈ $g$ of peak |
| gain +1 % | 0.30 | 1.8 % | ≈ $g$ of peak |
| gain +5 % | 1.50 | 9.1 % | ≈ $g$ of peak |
| threshold ±2 % | 0.10 | 1.7–1.8 % | $\lvert e\rvert\lambda$ = 0.10 V |
| threshold ±10 % | 0.50 | 9.8–9.9 % | $\lvert e\rvert\lambda$ = 0.50 V |
| offset +2 % / +10 % | 0.10 / 0.50 | 1.8 % / 9.7 % | $\lvert o\rvert\lambda$ |
| INL 1 % / 2 % / 5 % | 0.05 / 0.10 / 0.25 | 1.0 % / 2.0 % / 5.0 % | $a\lambda$ |
| combined, mild | 0.05 | 0.9 % | — |
| combined, severe | 0.20 | 1.9 % | — |

For a peak error of 1 % or less, each of $g$, $e$, $o$ and $a$ must be held to roughly 0.5–1 %. Gain and INL errors are partly invisible to blind diagnostics (Section 4.5), which motivates the calibration in Section 7.

### 6.6 Measured bearing-fault recordings

To test the recovery condition and the blind diagnostics on measured waveforms, the chain was applied to drive-end accelerometer records (units g, 0 hp load, 1796–1797 rpm) from the Case Western Reserve University Bearing Data Center [17], a standard benchmark for rolling-element bearing diagnostics [18]. Seven records are sampled at 48 kHz (normal baseline 97; inner-race, ball and outer-race faults of 0.007 in, records 109, 122, 135, and of 0.021 in, records 213, 226, 238), and six at 12 kHz (records 105, 118, 130, 209, 222, 234, same fault types and sizes). Each 48 kHz record is also evaluated after 4:1 subsampling without an anti-alias filter, to isolate the effect of sample rate on the same physical event. The CWRU acquisition did not overload. Overload is emulated by setting $\lambda = r\cdot\max\lvert x\rvert$ with $r \in \{0.8, 0.6, 0.5, 0.4, 0.33, 0.25\}$, applying an ideal fold, and recovering blindly with the zero-mean prior. A cell is recovered when $\max\lvert\tilde{x}-x\rvert \le 10^{-6}\max\lvert x\rvert$.

**Table 10.** Outcome totals on measured records (120 cells: 20 record variants × 6 thresholds).

| Quantity | Value |
|---|---|
| overloaded cells ($\lambda = r \cdot$ peak, every $r < 1$) | 120 / 120 |
| slew rule $\max\lvert\Delta x\rvert < \lambda$ predicts outcome | 120 / 120 |
| recovered exactly | 26 (all at 48 kHz; 26 / 42 cells) |
| failed | 94 (78 / 78 cells at 12 kHz) |
| failures flagged (slip or edge) | 94 / 94 |
| silent failures | 0 |
| slip false alarms | 0 |
| edge check set on a recovered cell (conservative) | 3 |

**Table 11.** 48 kHz records. Extra range is $20\log_{10}(\max\lvert x\rvert / \max\lvert\Delta x\rvert)$, the largest overload the first-order condition permits. Clipped indicators are at $r = 0.5$; fold-recovered indicators equal the true values wherever recovery succeeds.

| Record | Condition | $\max\lvert\Delta x\rvert$ / peak | Extra range | Lowest $r$ recovered | Clip SNR ($r$=0.5) | Kurtosis true / clipped | Crest factor true / clipped |
|---|---|---|---|---|---|---|---|
| 97 | normal | 0.42 | 7.5 dB | 0.5 | 23.2 dB | 2.8 / 2.5 | 4.2 / 2.2 |
| 109 | inner race 0.007 in | 0.38 | 8.3 dB | 0.4 | 19.5 dB | 6.0 / 4.7 | 6.1 / 3.2 |
| 122 | ball 0.007 in | 0.35 | 9.0 dB | 0.4 | 24.6 dB | 3.1 / 2.8 | 4.9 / 2.5 |
| 135 | outer race 0.007 in | 0.40 | 7.9 dB | 0.5 | 15.8 dB | 6.7 / 4.9 | 5.2 / 2.8 |
| 213 | inner race 0.021 in | 0.37 | 8.7 dB | 0.4 | 21.0 dB | 4.2 / 3.4 | 5.3 / 2.7 |
| 226 | ball 0.021 in | 0.32 | 9.8 dB | 0.33 | 29.7 dB | 3.2 / 3.0 | 5.6 / 2.8 |
| 238 | outer race 0.021 in | 0.40 | 7.9 dB | 0.5 | 19.6 dB | 20.8 / 15.9 | 11.5 / 6.0 |

Three observations follow. First, the recovery condition and the blind diagnostics, developed on synthetic signals, hold on measured impact waveforms with their real noise and quantization: every failure was flagged and no recovered record raised a slip alarm. Second, the usable range extension is modest and set by the sample rate. At 48 kHz the largest per-sample step is 0.32–0.42 of the peak, which permits 7.5–9.8 dB of extra range. At 12 kHz, recorded natively or subsampled, the largest step is 1.03–1.61 times the peak. Recovery requires $\lambda > \max\lvert\Delta x\rvert$ and overload requires $\lambda < \max\lvert x\rvert$, so no overload of these waveforms can be recovered at that rate. Bearing impacts excite structural resonances in the kHz range, which is why the step is large relative to the peak. Third, clipping biases exactly the time-domain indicators used for fault detection: at $r = 0.5$, kurtosis on the 0.021 in outer-race record falls from 20.8 to 15.9 and crest factor from 11.5 to 6.0, whereas recovered records reproduce both exactly. Details and per-cell data are in `docs/shockdaq-realdata.md` and `artifacts/realdata/metrics.json`.

**Non-ideal front end and fallback on measured records (v1.6).** The same 120 record-threshold cells were passed through each of the 25 front-end configurations of Section 3.7 (ideal; additive noise at 60 to 0 dB SNR relative to the record RMS, on top of the record's own noise, fixed seeds; fold-step gain −5 to +5 %; wrap threshold ±2 and ±10 %; offset 2 and 10 %; INL 1, 2 and 5 %; the mild and severe combined rows) and then through the firmware path `shockdaq.recover_or_clip` (blind quiet-window prior, slip/edge/rail checks, fallback to the folded samples on `UNRECOVERABLE`). Error is measured against the input the fold saw, including the converter DC offset, as in Section 6.5. Two properties were tested: no kept reconstruction is off by $\lambda$ or more anywhere (no silent slip), and on fallback every overloaded sample ($\lvert x\rvert \ge \lambda$) is marked untrusted.

**Table 12.** Non-ideal front ends on the measured records (3,000 cells: 120 cells × 25 configurations). "Trusted error" is the largest error, as a fraction of the record peak, on samples the output does not mark untrusted. "Invisible" counts kept reconstructions more than 1 % off whose status is still `RECOVERED` (no slip, edge or rail indication).

| Quantity | Value |
|---|---|
| cells falling back to the folded samples (`UNRECOVERABLE`) | 2,492 (97 of 120 on the ideal front end) |
| cells keeping the reconstruction | 508 (all at 48 kHz) |
| kept reconstructions off by $\ge \lambda$ (silent slip) | 0 |
| overloaded samples left trusted on fallback, event mask only (before v1.6) | 117 in 21 cells (threshold ±2 / ±10 % and combined rows) |
| the same with event mask plus rail samples (v1.6) | 0 |
| kept cells with a trusted sample > 1 % off | 145 (gain ±1 / ±5 %, INL 2 / 5 %, severe combined) |
| of those, invisible | 57 (gain −1 % 16, gain −5 % 16, INL 2 % 11, INL 5 % 14) |
| fallback cells with a trusted sample > 1 % off | 50 (INL 2 % 7, INL 5 % 43; at most 3.9 % of peak) |
| largest trusted error | 8.0 % of peak (gain ±5 %, uncalibrated) |
| fraction of the record marked untrusted on fallback | median 100 % in every configuration (lowest single cell 6.2 %, record 238 at 48 kHz) |

The safety properties carry over to measured data once rail samples are included in the fallback mask: no kept reconstruction slipped, and no overloaded sample was left trusted. The accuracy limits are those of Sections 6.5 and 7: uncalibrated gain and INL errors give a bounded error (here up to 1.6 % of peak at $\lvert g\rvert$ = 1 %, 8.0 % at 5 %, 4.0 % at INL 5 %), and the 57 invisible cells all come from the short-fold-step and INL rows, the error types the calibration of Section 7 addresses (Table 9 on synthetic data; Table 13 below on these records). On fallback the folded samples carry the converter's INL, so INL also limits the accuracy of the samples left trusted. Finally, the fallback mask is honest but not selective on these records. On these records the suspicious steps lie closer together than the 1,024-sample merge gap, so the overload events merge and in most fallback cells the whole record is marked untrusted. Shortening the merge gap from 1,024 to 16 samples still covered every overloaded sample but marked a median 79 % of the record, so the default was not changed (`scripts/probe_fallback_mask.py`). A local run of the Table 12 sweep, the probe and the full test suite with the CWRU cache present is committed as [`artifacts/cwru-nonideal-run-2026-10-19.log`](../artifacts/cwru-nonideal-run-2026-10-19.log). For continuously impacting machines, a fallback capture is in practice a rejected capture with a correct overload flag.

**Calibration on measured records (v1.7).** The one-tone calibration of Section 7 was applied to every cell of Table 12. For each record, threshold and front-end configuration, the 159.2 Hz calibration tone was folded by the same front end at the record's $\lambda$ and sample rate, $\hat{g}$ and $\alpha_k$ were fitted, the INL correction was applied to the folded record, and `recover_or_clip` undid wraps with the calibrated step. The calibration was applied to all 25 configurations, including those whose error it does not model (noise, threshold, offset), so any harm it does there would appear in the counts. Hypothesis: at 60 dB injection SNR the 57 invisible cells fall to 0, with still no silent slip and no overloaded sample left trusted. Falsifier: any invisible cell, slip or uncovered sample after calibration.

**Table 13.** Table 12 sweep (3,000 cells) without calibration and with calibration at four injection SNRs, with and without the residual acceptance gate of Section 7.4. "Rejected" counts cells whose calibration failed the gate and was therefore not applied. Columns as in Table 12; "bad kept / bad fallback" count cells with a trusted sample more than 1 % of peak off.

| Run | Injection SNR | Gate | Rejected | Fallback | Silent slip | Uncovered samples | Bad kept / bad fallback | Invisible | Largest trusted error (% of peak) |
|---|---|---|---|---|---|---|---|---|---|
| uncalibrated (Table 12) | – | – | – | 2,492 | 0 | 0 | 145 / 50 | 57 | 8.000 |
| calibrated | 60 dB | on | 0 | 2,489 | 0 | 0 | 0 / 0 | 0 | 0.037 |
| calibrated | 60 dB | off | – | 2,489 | 0 | 0 | 0 / 0 | 0 | 0.037 |
| calibrated | 50 dB | on | 3,000 | 2,492 | 0 | 0 | 145 / 50 | 57 | 8.000 |
| calibrated | 50 dB | off | – | 2,488 | 0 | 0 | 0 / 0 | 0 | 0.467 |
| calibrated | 40 dB | on | 3,000 | 2,492 | 0 | 0 | 145 / 50 | 57 | 8.000 |
| calibrated | 40 dB | off | – | 2,476 | 0 | 0 | 524 / 19 | 216 | 4.850 |
| calibrated | 20 dB | on | 3,000 | 2,492 | 0 | 0 | 145 / 50 | 57 | 8.000 |
| calibrated | 20 dB | off | – | 2,996 | 4 | 9,199 | 4 / 2,465 | 4 | 142.371 |

The hypothesis held at 60 dB: no invisible cell, no slip, no uncovered sample, and no trusted sample more than 0.04 % of peak off in any configuration. The small error that calibration adds to the ideal and unmodelled rows (up to 0.04 % of peak, from the noise of the estimated $\hat{g}$) is far below the 1 % bar. The ungated rows show the hazard. With a noisy calibration tone, an inaccurate $\hat{g}$ and inaccurate INL coefficients are applied to every channel, including channels that had no error to correct. At 40 dB this produced more invisible errors than no calibration (216 against 57). At 20 dB the INL correction distorted the folded samples enough that 4 kept reconstructions slipped and the fallback mask missed 9,199 overloaded samples. The residual gate rejects every calibration at 50 dB or below and accepts every one at 60 dB, and a rejected calibration leaves the result identical to the uncalibrated run. The gate is conservative: ungated, the 50 dB calibration also removed all 57 invisible cells on these records (largest trusted error 0.47 % of peak), but its $\hat{g}$ misses the 10⁻³ target of Section 7.2 on the synthetic grid, so it is rejected. `python scripts/probe_cal_gate.py` reproduces Table 13; the local run is committed as [`artifacts/cwru-cal-run-2026-10-20.log`](../artifacts/cwru-cal-run-2026-10-20.log). As in the rest of this section, the front-end errors are applied in software with the same model the calibration assumes, so this shows that the calibration works on measured waveforms, not that it captures every error of a real front end.

*Reproducibility note:* every number in this section is reproducible with `python -m foldcrypt shockdaq-real --cells`, which downloads the 13 CWRU records (about 45 MB, SHA-256 checked) and needs the `[real]` extra (SciPy). Because of that download, Section 6.6 is **not checked in CI**: the matching test (`tests/test_realdata.py::test_cached_cwru_sweep_has_no_silent_failures`) is skipped unless the files are cached locally. A full local re-run on 2026-10-17 (code commit `c9b8ac5`, Python 3.13.5; command, data SHA-256 checksums, complete output, the formerly skipped test passing, and a number-by-number comparison with Tables 10–11 and this text, all matching) is committed as [`artifacts/cwru-run-2026-10-17.log`](../artifacts/cwru-run-2026-10-17.log); `python scripts/check_cwru_numbers.py` repeats that comparison for Tables 10–13 against the committed metrics files (this part runs in CI); with `--recompute` it also verifies the pinned SHA-256 checksums, re-runs the sweeps from the cached records and diffs every field against the committed files, and `--table13-all` re-runs every calibrated row of Table 13. A full local run on 2026-10-21 is committed as [`artifacts/cwru-check-run-2026-10-21.log`](../artifacts/cwru-check-run-2026-10-21.log). The raw CWRU data is not committed.

**Second dataset: Paderborn KAt at 64 kHz (v1.8).** To test whether the sample-rate finding carries to another rig and sensor chain, the same chain (Table 10 method) was run on the `vibration_1` channel of the Paderborn University KAt Bearing DataCenter [19], obtained from the Zenodo mirror [20]: bearings K001 (healthy), KA04 (outer ring, fatigue pitting) and KI04 (inner ring, fatigue pitting), measurement 1 at each of the four operating conditions, 64 kHz, 4 s, plus 4:1 subsampled copies (16 kHz); 144 cells. Four predictions were recorded before scoring (`artifacts/paderborn/prereg-2026-10-23.md`). Held: the slew rule predicted 144/144 cells; 0 silent failures (140 failures, all flagged); at 16 kHz no record had headroom (12/12). Falsified: "every 64 kHz record has headroom and the median is at least 7.5 dB". Median headroom was +0.38 dB, 3 of 12 records had none, and only the four outer-ring records at $r$ = 0.8 recovered (4/144 cells). The cause is single-sample spikes: on the healthy and inner-ring records the peak is one sample that jumps away and straight back, so $\max\lvert\Delta x\rvert \approx$ peak (49–845 such spikes per record; 0–2 on the outer-ring records, which keep 3.2–4.2 dB; 0 on the seven CWRU 48 kHz records). Whether the spikes are mechanical or electrical was not determined. The safety result therefore transfers to a second dataset; the range benefit does not, and a high sample rate is necessary but not sufficient. Reproduce with `python scripts/run_paderborn.py` (about 530 MB of archives, MD5 and SHA-256 checked; needs `unar`); details in `docs/shockdaq-paderborn.md`.

---

## 7. Front-end calibration

### 7.1 Procedure

A known sinusoid at $f_c$ = 159.2 Hz ($\omega$ = 1000 rad/s, the usual accelerometer calibration reference frequency) and amplitude $4\lambda$ is injected electrically at the digitizer input for 1 s, with the accelerometer out of the loop. The amplitude, phase and DC level are treated as unknown. The folded record is unwrapped with the nominal step $2\lambda$, and the wrap count $M[n] = \operatorname{round}\big((\hat{x}[n]-y[n])/2\lambda\big)$ is formed. Under a fold-step gain error the nominal unwrap equals $x[n] - 2\lambda g M[n]$ exactly. A single linear least-squares fit,

$$
\hat{x}[n] \;\approx\; a\sin(\omega t_n) + b\cos(\omega t_n) + c \;-\; 2\lambda\,\hat{g}\, M[n] \;+\; \sum_{k=1}^{3} \alpha_k \sin\!\big(k\pi\, y[n]/\lambda\big),
$$

over samples not at the rail, gives the gain estimate $\hat{g}$ and the INL harmonics $\alpha_k$. In operation, the INL correction $y \leftarrow y - \sum_k \alpha_k \sin(k\pi y/\lambda)$ is applied first. Wraps are still detected with the nominal rule but undone with the calibrated step $2\lambda(1+\hat{g})$. The INL terms are required. Without them, a 5 % INL bow is absorbed into $\hat{g}$ as an apparent gain error of about +4.7 %.

### 7.2 Estimator accuracy

**Table 8.** Worst-case $\lvert \hat{g} - g \rvert$ over $g \in \{\pm 0.1, \pm 1, \pm 5\}$ %, ideal/16-bit/12-bit quantization, 3 seeds. Target ≤ $10^{-3}$.

| Calibration-tone SNR | Worst $\lvert \hat{g} - g \rvert$ | Meets target |
|---|---|---|
| noiseless | 3.1 × 10⁻⁶ | yes |
| 80 dB | 1.3 × 10⁻⁵ | yes |
| 60 dB | 3.2 × 10⁻⁴ | yes |
| 40 dB | 2.8 × 10⁻² | no |
| 20 dB | 1.0 | no (unwrap fails) |

At 60 dB injection SNR, the per-configuration estimates in Table 9 are within $2.3\times10^{-4}$ of the true gain, and the INL estimates are within $2\times10^{-4}\lambda$ of the true bow.

### 7.3 Effect on the burst grid

**Table 9.** Burst grid (280 cells per row) before and after calibration at 60 dB injection SNR, counted over overloaded cells. Of the 275 overloaded ideal-front-end cells, 109 are within the slew limit, so 109 is the maximum possible "accurate" count (before v1.5 this was given as 114 by including the 5 in-range cells). "Invisible" counts recovered cells more than 1 % off with no slip, no edge, **and no rail sample**, i.e. errors the capture gives no indication of.

| Configuration | $g$ / $\hat{g}$ | Overloaded | Accurate, before → after | Unflagged > 1 %, before → after | Invisible, before → after |
|---|---|---|---|---|---|
| ideal | 0 / −0.00008 | 275 | 109 → 109 | 0 → 0 | 0 → 0 |
| gain −5 % | −0.0500 / −0.05023 | 275 | 0 → 84 | 95 → 20 | 75 → 0 |
| gain −1 % | −0.0100 / −0.01016 | 275 | 16 → **109** | 86 → 0 | 68 → 0 |
| gain +0.1 % | +0.0010 / +0.00091 | 275 | 109 → 109 | 0 → 0 | 0 → 0 |
| gain +1 % | +0.0100 / +0.00988 | 275 | 22 → 58 | 80 → 47 | 5 → 0 |
| gain +5 % | +0.0500 / +0.04980 | 275 | 2 → 0 | 100 → 102 | 0 → 0 |
| INL 1 % | 0 / −0.00008 | 275 | 106 → **109** | 0 → 0 | 0 → 0 |
| INL 2 % | 0 / −0.00007 | 275 | 40 → **109** | 59 → 0 | 59 → 0 |
| INL 5 % | 0 / +0.00003 | 275 | 15 → **109** | 79 → 0 | 79 → 0 |
| combined, mild | +0.0010 / +0.00090 | 275 | 108 → **109** | 0 → 0 | 0 → 0 |
| combined, severe | +0.0050 / +0.00488 | 276 | 40 → 35 | 61 → 67 | 2 → 0 |

Across all rows, invisible errors on overloaded cells fall from 288 to 0 (304 → 0 if the 16 in-range cells are included). After calibration, there are still no silent unwrap failures and no slip false alarms in any row.

### 7.4 Interpretation and design rule

Calibration fully corrects negative gain errors (fold step short) and INL. It cannot correct samples that a front-end error pushed past the converter rail, because their values are clipped. With a long fold step ($g > 0$), the first sample after every wrap lands outside the range, so a +5 % step stays inaccurate after calibration. The same holds for threshold and offset errors, which this calibration does not model (the severe combined row). Those residual errors are not silent. Every such capture contains rail-clipped samples and is reported as `BOUNDED_ACCURACY` (Section 3.6). The rail check is conservative, however: in the mild combined configuration it fires on 99 of the 108 recovered overloaded cells, all of which are accurate.

**Design rule.** Trim the fold step slightly short ($g \le 0$) and calibrate it. Never trim it long. Keep the wrap threshold and the converter offset within about 0.5–1 % of $\lambda$. Reject any calibration whose fit residual exceeds 0.5 % of $\lambda$.

**Acceptance gate (v1.7).** The fit residual RMS of Section 7.1 tracks the injection noise directly. Over the 25 front-end configurations of Section 3.7, at 48 and 12 kHz with three noise seeds each, it was about 0.28 % of $\lambda$ at 60 dB injection SNR (worst $\lvert\hat{g}-g\rvert$ = 5.8 × 10⁻⁴, within the 10⁻³ target) and about 0.89 % at 50 dB (worst 3.9 × 10⁻³, outside it). A calibration is therefore accepted only if its residual RMS is at most 0.5 % of $\lambda$ (`calibrate.CAL_MAX_RESID_FRAC`, `FrontEndCal.accepted`); a rejected calibration is not applied and the channel is recovered and reported as uncalibrated. The gate matters because a wrong calibration is applied to every capture of that channel: on the measured records an ungated 40 dB calibration more than tripled the invisible errors, and an ungated 20 dB calibration caused silent slips (Table 13). The threshold was set with white injection noise only.

### 7.5 Alternatives evaluated and rejected

* Estimating $g$ blindly from the impact burst itself gave a bias of about 4 %, because the signal changes too much between samples to separate gain from waveform. *(Unverified: the code for this rejected alternative is not in the repository, so the figure cannot be reproduced.)*
* Interpolating across rail-clipped samples made fast bursts worse and was not adopted. *(Unverified: code not retained.)*

---

## 8. Limitations

1. **Evidence is synthetic or software-folded.** Sections 6.1–6.5 and 7 use synthetic signals. Section 6.6 uses measured accelerometer records, but those records were acquired within range and the overload is applied in software. No measured audio has been processed. The non-ideal front-end model and the one-tone calibration were applied to the measured records only in software, with the same error model on both sides (Tables 12–13).
2. **No hardware folding front end was built or tested in this work.** The fold is applied in software to simulated sample values. Hardware modulo ADCs have been demonstrated by others [8], [9], [6]. Their analog non-idealities, such as reset transients, comparator metastability, finite reset time, and anti-alias filter interaction, are represented here only by the simplified model of Section 3.7.
3. **Folding at the digitizer cannot repair clipping inside the sensor.** If an IEPE accelerometer's internal amplifier saturates (out-of-range input or resonance excitation, [1], [2]), the signal is already clipped before it reaches the DAQ. A folding digitizer will record the clipped waveform faithfully. Only a fold inside the sensor's own amplifier (Section 9.1) could address that case.
4. **$\lambda = 5$ V is an assumption.** It approximates the ±5 V swing typical of ICP accelerometers [1]. It is not the specification of any particular sensor, signal conditioner or DAQ. Many DAQ inputs accept ±10 V [4], [5].
5. **High-end DAQs already reduce digitizer-side clipping.** Single-range wide-dynamic-range inputs, for example HBK Dyn-X with a 10 V peak range and a noise floor below −160 dB in narrowband analysis [5], largely remove the need for range selection on laboratory systems. The case for folding is strongest where such inputs are too costly, too power-hungry, or not available (Section 9).
6. **Slew-rate limit.** First-order unwrapping needs $\max\lvert\Delta x\rvert < \lambda$. Sharp high-frequency ringing, impulsive glitches, and signals near the sensor's resonance can violate this. Outside the limit, fold reconstruction is worse than clipping, and the fallback must be the clipped value. On the measured bearing records of Section 6.6, the limit permits no recoverable overload at 12 kHz and 7.5–9.8 dB of extra range at 48 kHz. On the Paderborn records (Section 6.6, v1.8), single-sample spikes set the largest step at about the peak and removed the headroom on 3 of 12 records at 64 kHz.
7. **Diagnostic blind spot.** Isolated single-sample excursions larger than $\lambda$ that return to baseline are not detected by the slip or edge checks (Section 4.6). The zero-silent-failure result applies to the ringing-transient class in the failure map.
8. **AC-coupling prior.** Blind level recovery assumes a near-zero mean, or a quiet baseline, within $\lambda$ of zero. DC-coupled measurements with offsets comparable to $\lambda$ need a different level reference.
9. **Limited signal set.** The audio set has four signals and the vibration set has four cases plus one burst family. There are no listening tests, no perceptual metrics, and no standard vibration metrics (e.g. shock response spectra or ISO severity measures).
10. **Calibration scope.** The one-tone calibration models fold-step gain and INL. It does not model threshold error, temperature drift, or frequency-dependent effects. It requires an injection SNR of 60 dB or better. An inaccurate calibration is worse than none (Table 13), so the fit-residual gate of Section 7.4 must be enforced; the 0.5 %-of-λ threshold was set from white injection noise, and a real injection path with hum or drift may need a different threshold.
11. **Statistical depth.** The failure map uses five noise seeds. The quantization sweep and the audio demo use one.

---

## 9. Applications and integration guidance

### 9.1 Sensor-integrated fold

Saturation inside the sensor (Limitation 3) is the one failure mode a digitizer-side fold cannot address. A modulo stage, or a reset-counting integrator, inside an IEPE or charge amplifier would keep the sensor's output within its ±5 V swing during shocks above range. The sensor could also report wrap events. A sensor-side implementation could use the explicit reset-bit approach of [9] rather than blind unwrapping, which raises the per-sample limit from $\lambda$ to $2\lambda$. This is a hardware research direction and has not been evaluated here.

### 9.2 Low-cost condition-monitoring nodes

Wireless or embedded condition-monitoring nodes typically pair one sensor channel with a single fixed-range ADC and a microcontroller. They have neither a second conversion path nor an operator to set ranges. Machine run-up, coast-down and impacts are the events most likely to exceed a range chosen for steady-state vibration. Unwrapping costs one subtraction, one rounding and one accumulation per sample. The blind checks need two windowed means and a running maximum. Both fit in the firmware budget of such nodes. The slew limit must be checked against the expected spectrum. A node sampling at 25.6 kHz with $\lambda$ = 5 V has a slew limit of 128,000 V/s. The measured bearing records of Section 6.6 show that this check is decisive: their impacts were recoverable at 48 kHz but not at 12 kHz. Nodes sampling between 10 and 25.6 kHz should not assume fold recovery on impact-rich signals; they still gain the status word, which reports the overload instead of passing a silently clipped record.

### 9.3 DAQ front-end firmware

On a conventional DAQ, a fold stage between the sample-and-hold and the quantizer (or an equivalent digital wrap in a converter with headroom bits) can replace "overload → discard" with the four-level status of Section 3.6. Recommended integration:

1. **State the specification as a slew rate.** Publish $\lambda f_s$, and derate it for front-end noise (several $\sigma$) and for fold-step, threshold, offset and INL tolerances (Section 4.5).
2. **Filter ahead of the fold.** The anti-alias filter limits slew. Choosing its corner with the slew specification in mind reduces the impulsive cases of Section 4.6.
3. **Trim and calibrate the fold step.** Trim short, never long. Run the one-tone calibration (Section 7) at production and service, at ≥ 60 dB injection SNR. Store $\hat{g}$ and $\alpha_k$ per channel.
4. **Export the status word with the data.** Report `UNRECOVERABLE` / `BOUNDED_ACCURACY` / `RECOVERED` / `IN_RANGE` per capture, or per block in streaming mode. Include the rail-sample count. On `UNRECOVERABLE`, fall back to the clipped value and keep the existing overload flag, consistent with current vendor guidance [3].
5. **Keep the folded raw data.** The unwrap is deterministic. Storing the folded samples lets a more capable offline reconstruction, such as higher-order methods [7], [8], be applied later to captures that failed the first-order check.

### 9.4 Audio recorders

Field recorders, camera audio and phone recording paths face the same unattended-gain problem. Speech and music at 48 kHz satisfied the slew condition in the tests above at peaks up to 7.8 λ. Single-sample clicks did not. A recorder implementation would need the same status reporting, plus a fallback to conventional declipping [13] for blocks flagged unrecoverable. For audio, this work offers no evidence beyond the synthetic results of Section 6.1. The hardware-validated audio results of [6] are the relevant reference for feasibility.

---

## 10. Reproducibility

All results in this report are produced by the repository at the commit that introduces this version, except the two rejected alternatives of Section 7.5, which are marked unverified. Commands:

```bash
git clone https://github.com/Dastille/FoldAudio
cd FoldAudio
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,real]"

python -m pytest -q                               # full test suite (count: see CI)
python -m foldcrypt audio-demo                    # Table 1   -> artifacts/foldaudio/metrics.json  (FoldAudio)
python -m foldcrypt shockdaq-demo                 # Table 2   -> artifacts/shockdaq/metrics.json   (ShockDAQ)
python -m foldcrypt shockdaq-failmap              # Tables 3-4 (seed 7) -> failmap.json, failmap.svg
python -m foldcrypt shockdaq-failmap --quant      # Table 5   -> quantmap.json
python -m foldcrypt shockdaq-failmap --nonideal   # Table 6   -> nonidealmap.json (~25 s)
python -m foldcrypt shockdaq-calibrate            # Tables 8-9 -> calibration.json (~25 s)
python -m foldcrypt claims                        # spot numbers of Sections 3.6-7.4 + overloaded-only Tables 4, 6, 7, 9 (~45 s; asserted in tests/test_claims.py)
python -m foldcrypt shockdaq-real --cells         # Tables 10-11 (not run in CI) -> artifacts/realdata/metrics.json (downloads ~45 MB of CWRU data, SHA-256 checked)
python -m foldcrypt shockdaq-real --nonideal      # Table 12 (not run in CI; needs the CWRU cache) -> artifacts/realdata/nonideal-metrics.json (~25 s)
python scripts/probe_fallback_mask.py             # Table 12 event-mask-only row and merge-gap sensitivity (~40 s)
python -m foldcrypt shockdaq-real --nonideal --calibrated  # Table 13 60 dB gated row -> artifacts/realdata/nonideal-cal-metrics.json (~40 s)
python scripts/probe_cal_gate.py                  # Table 13, all rows (not run in CI; needs the CWRU cache; ~6 min)
python scripts/run_paderborn.py                   # Section 6.6 Paderborn paragraph (v1.8) -> artifacts/paderborn/metrics.json (~530 MB download, needs unar)
```

(The Python package directory is named `foldcrypt` for historical reasons.)

Five-seed failure-map totals (Table 4, right column) and the blind audio check (Section 6.1):

```bash
python - <<'PY'
import collections
from foldcrypt.failmap import run_failmap, summarize
tot = collections.Counter()
for seed in (7, 8, 9, 10, 11):
    tot.update(summarize(run_failmap(seed=seed)))
print(dict(tot))

from foldcrypt import foldaudio as fa
from foldcrypt.blind_level import recover_blind, slip_flag, edge_flag
lam = fa.DEFAULT_LAM
for name, x in {"tone_burst": fa.gen_tone_burst(), "speech_like": fa.gen_speech_like(),
                "music_peaks": fa.gen_music_peaks(), "harsh_kick": fa.gen_harsh_kick()}.items():
    y = fa.fold_capture(x, lam)
    r, k = recover_blind(y, lam)
    print(name, k, round(fa.snr_db(x, r), 2), slip_flag(r, lam), edge_flag(y, lam))
PY
```

Table 7 and the derated-rule counts in Section 6.5 come from the per-cell records returned by `foldcrypt.failmap.run_nonideal_sweep()` (fields `err_peak_V`, `peak_err_frac`, `predicted_ok`, `derated_ok`, `recovered_ok`, `rail_hits`).

Source modules: `modulo.py` (fold, quantizer), `unfold_detect.py` (first-order unwrap), `foldaudio.py` (audio signals and metrics), `shockdaq.py` (vibration cases and status word), `blind_level.py` (blind level, slip/edge/rail checks, INL inverse), `failmap.py` (grid, quantization and non-ideal sweeps), `calibrate.py` (one-tone calibration), `realdata.py` (CWRU download, checksum and measured-record sweep). Environment: Python 3, NumPy (SciPy for Section 6.6), CPU only. All random generators are seeded.

---

## 11. Conclusion

In simulation, replacing hard clipping with a modulo fold turns an irreversible, often unflagged loss into an invertible encoding that is valid under one condition: the sample-to-sample change must stay below the fold threshold, equivalently a slew rate below $\lambda f_s$. Inside that condition, first-order unwrapping with a blind AC-coupling prior reconstructs the overload exactly, for synthetic audio and vibration signals alike. Outside it, reconstruction is worse than clipping. For the ringing-transient class studied, however, every failure was flagged blindly, with no false alarms. The flagging held across ADC resolutions of 4–24 bits, across sensor noise, and across fold-step, threshold, offset and INL errors. The front-end errors introduce one effect that blind checks cannot see: a bounded peak error proportional to the wrap count. A one-tone calibration removes it whenever the fold step is trimmed short. On measured bearing-fault records with software-applied overload, the same condition predicted every outcome and every failure was flagged, but the condition also bounds the benefit: about 8–10 dB of extra range at 48 kHz, and none at 12 kHz. On a second dataset at 64 kHz the safety result held again (144/144 cells predicted, no silent failure), but single-sample spikes left a median of only 0.4 dB of extra range, so a high sample rate alone does not guarantee a benefit. The remaining limitations are significant: no hardware, no measured overload event, no protection against saturation inside the sensor, and a diagnostic blind spot for isolated impulses. The next required step is a measurement on a physical folding front end with real accelerometer and microphone signals, sampled at 48 kHz or faster for impact-rich machinery, with the origin of single-sample spikes understood.

---

## 12. References

URLs were accessed on 2026-10-13.

1. S. A. Hambric, *Signal Processing Impacts of ICP® Accelerometer Limit Violations*, PCB Piezotronics white paper WPL-96, Nov. 2023. <https://www.pcb.com/contentstore/mktgcontent/whitepapers/WPL_96_Signal_Processing_Impacts.pdf>
2. M. Lindstrom, *What's Wrong With My Piezoelectric Accelerometer?*, PCB Piezotronics Technical Note TN-30. <https://www.pcb.com/contentstore/mktgcontent/linkeddocuments/technotes/tn-30-what's_wrong_lowres.pdf>
3. National Instruments, "Overload Detection," *NI-DAQmx User Manual*. <https://www.ni.com/docs/en-US/bundle/ni-daqmx/page/overloaddetection.html>
4. Siemens Digital Industries Software, "Overloads," Simcenter Community knowledge article. <https://community.sw.siemens.com/s/article/overloads>
5. O. Thorhauge and N.-J. Jacobsen, "Dyn-X Technology: 160 dB Input Range," Hottinger Brüel & Kjær. <https://www.hbkworld.com/en/knowledge/resource-center/articles/dyn-x-technology>
6. R. Guo and A. Bhandari, "Digital Audio via Unlimited Sensing: Overflow Overcomes Clipping and Overflow," *Proc. EUSIPCO 2026*. <https://eurasip.org/Proceedings/Eusipco/Eusipco2026/pdfs/0000411.pdf>
7. A. Bhandari, F. Krahmer, and R. Raskar, "On Unlimited Sampling and Reconstruction," *IEEE Trans. Signal Process.*, vol. 69, pp. 3827–3839, 2021. arXiv:1905.03901. (Conference version: "On unlimited sampling," *Proc. SampTA*, 2017.)
8. A. Bhandari, F. Krahmer, and T. Poskitt, "Unlimited Sampling from Theory to Practice: Fourier-Prony Recovery and Prototype ADC," *IEEE Trans. Signal Process.*, 2022. arXiv:2105.05818.
9. A. Krishna, S. Rudresh, V. Shaw, H. R. Sabbella, C. S. Seelamantula, and C. S. Thakur, "Unlimited Dynamic Range Analog-to-Digital Conversion," arXiv:1911.09371, 2019. <https://arxiv.org/abs/1911.09371>
10. O. Ordentlich, G. Tabak, P. K. Hanumolu, A. C. Singer, and G. W. Wornell, "A Modulo-Based Architecture for Analog-to-Digital Conversion," *IEEE J. Sel. Topics Signal Process.*, vol. 12, no. 5, pp. 825–840, 2018.
11. K. Vaghela, K. Appaiah, and S. Mulleti, "Fold First, Detect Directly: Communication Symbol Detection Without Unfolding for Low-Bitrate Modulo-ADCs," arXiv:2609.11298, 2026.
12. A. Adler, V. Emiya, M. G. Jafari, M. Elad, R. Gribonval, and M. D. Plumbley, "Audio Inpainting," *IEEE Trans. Audio, Speech, Lang. Process.*, vol. 20, no. 3, pp. 922–932, 2012.
13. P. Záviška, P. Rajmic, A. Ozerov, and L. Rencker, "A Survey and an Extensive Evaluation of Popular Audio Declipping Methods," *IEEE J. Sel. Topics Signal Process.*, vol. 15, no. 1, pp. 5–24, 2021.
14. K. Itoh, "Analysis of the phase unwrapping algorithm," *Applied Optics*, vol. 21, no. 14, p. 2470, 1982.
15. W. Kester, "ADC Architectures VI: Folding ADCs," Analog Devices tutorial MT-025, 2009.
16. Zaxcom, "NeverClip Explained." <https://zaxcom.com/learn/what-is-neverclip/>
17. Case Western Reserve University Bearing Data Center, seeded-fault test data (records 97, 105, 109, 118, 122, 130, 135, 209, 213, 222, 226, 234, 238). <https://engineering.case.edu/bearingdatacenter> (accessed 2026-10-14)
18. W. A. Smith and R. B. Randall, "Rolling element bearing diagnostics using the Case Western Reserve University data: A benchmark study," *Mechanical Systems and Signal Processing*, vol. 64–65, pp. 100–131, 2015.
19. C. Lessmeier, J. K. Kimotho, D. Zimmer, and W. Sextro, "Condition Monitoring of Bearing Damage in Electromechanical Drive Systems by Using Motor Current Signals of Electric Motors: A Benchmark Data Set for Data-Driven Classification," *PHM Society European Conference*, vol. 3, no. 1, 2016. doi:10.36001/phme.2016.v3i1.1577
20. J. van den Hoogen, "Paderborn Bearing Dataset" (mirror of the KAt Bearing DataCenter archives), Zenodo, 2025. doi:10.5281/zenodo.15845309 (accessed 2026-10-23)

---

## Appendix A. Notation

| Symbol | Meaning |
|---|---|
| $x[n]$ | true input sample |
| $y[n]$ | folded (recorded) sample |
| $\lambda$ | fold threshold; converter range $[-\lambda, \lambda)$ |
| $m[n]$ | wrap count (integer), $x = y + 2\lambda m$ |
| $f_s$ | sample rate |
| $\hat{x}, \tilde{x}$ | unwrapped estimate; estimate after level correction |
| $N$, $\Delta$ | quantizer bits; LSB $= \lambda/2^{N-1}$ |
| $g, e, o, a$ | fold-step gain error, threshold error, offset, INL bow (fractions of $\lambda$ or of the step) |
| $\hat{g}, \alpha_k$ | calibrated gain error and INL harmonic coefficients |

## Appendix B. Revision history

| Version | Date | Changes |
|---|---|---|
| 0.1 | 2026-10-02 | Working draft: audio-only, oracle level selection, four-signal SNR table. |
| 1.0 | 2026-10-13 | Retitled and rewritten as a technical report. Added vibration application, blind level recovery, recovery-condition analysis, blind diagnostics and capture status, 280-cell failure map, quantization and non-ideal front-end sweeps, one-tone calibration, limitations and integration guidance. All figures re-run. Corrected slip-check coverage (157/166, not 166/166) and documented the impulsive-signal diagnostic blind spot. |
| 1.1 | 2026-10-14 | Added Section 6.6 (Tables 10–11): measured CWRU bearing-fault records with software-applied overload; 120/120 rule agreement, 0 silent failures; sample-rate finding (48 kHz recoverable, 12 kHz not). Updated abstract, Limitations 1 and 6, Section 9.2, reproducibility, conclusion and references. |
| 1.2 | 2026-10-15 | Section 4.4: fitted noise margin $\lambda - k\sigma$, $k = 5$ (false "recoverable" 119 → 0 of 2,520 noise cells). Section 3.6: `UNRECOVERABLE` fallback output (folded samples plus untrusted mask; peak reported as $\ge \lambda$). |
| 1.3 | 2026-10-16 | Sections 4.4–4.5: combined derate + noise slew rule (INL/combo false "recoverable" 12 → 0 of 1,400 cells; +19 conservative); blind quiet-window $\sigma$ estimate for live $\lambda - k\sigma$. |
| 1.4 | 2026-10-17 | Claim audit: spot numbers reproduced by `python -m foldcrypt claims` and asserted in `tests/test_claims.py`. Corrected §4.5 σ-estimate error (≈ 5 % → ≤ 3.6 %) and §5.3 burst peak range (0.85–0.94 A → 0.82–0.98 A; 5 of 40 cells in the 6 V row stay below λ). §3.6 names its seven captures and adds the full seed-7 range. §7.5 marked unverified. §6.6 noted as not checked in CI. |
| 1.6 | 2026-10-19 | Section 6.6, Table 12: CWRU records through the 25 non-ideal front ends and the `recover_or_clip` fallback (3,000 cells; 0 silent slips). Fallback mask now includes rail-clipped samples (117 overloaded samples in 21 cells were left trusted before). §3.6 and Limitation 1 updated. |
| 1.5 | 2026-10-17 | Recovery counted over overloaded cells only (input peak ≥ λ). Failure map 114/166 recovered/failed and 280/280 agreement → 109/166 and 275/275 overloaded cells (5 in-range cells removed). Tables 6, 7 and 9 restated with an "Overloaded" column; Table 9 accurate ceiling 114 → 109, invisible 304 → 288 → 0; §7.4 rail check 101/113 → 99/108; §4.4 agreement 2,401 → 2,435 of 2,520 → 2,378 → 2,412 of 2,497. Table 7 max error/peak: gain +1 % 1.9 → 1.8 %, threshold ±2 % 1.8–1.9 → 1.7–1.8 %, offset 1.9/9.9 → 1.8/9.7 %, INL 5 % 5.1 → 5.0 %. Failure and flag counts unchanged; CWRU cells all overloaded by construction. |
| 1.7 | 2026-10-20 | Section 6.6, Table 13: one-tone calibration applied to the 3,000 measured-record cells of Table 12; at 60 dB injection SNR the 57 invisible cells fall to 0 (max trusted error 0.04 % of peak). Ungated noisy calibration found harmful (40 dB: 216 invisible; 20 dB: 4 silent slips, 9,199 uncovered samples); §7.4 adds a fit-residual acceptance gate (≤ 0.5 % of λ). Limitations 1 and 10 updated. |
| 1.8 | 2026-10-23 | Section 6.6: second measured dataset (Paderborn KAt, 64 kHz, 12 records, 144 cells). Rule 144/144, 0 silent; pre-registered ≥ 7.5 dB headroom prediction falsified (median +0.38 dB; single-sample spikes). Limitation 6, conclusion, references 19–20 updated. |
