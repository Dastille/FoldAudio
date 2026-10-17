"""Reproduce the whitepaper's spot numbers that no demo table prints.

Every function here is deterministic (fixed seeds) and maps to one sentence in
docs/foldaudio-whitepaper.md; tests/test_claims.py asserts each value at the
precision the report states it, so a code change that moves a number fails CI
instead of silently leaving a stale claim. `python -m foldcrypt claims` prints
them all (the noise-k fit runs a 2,520-cell sweep, ~10 s).

Nothing here tunes anything: it only re-runs the existing library code.
"""

from __future__ import annotations

import numpy as np

from .blind_level import estimate_noise_sigma, naive_k0, recover_blind
from .calibrate import cal_tone, estimate_front_end
from .failmap import (
    DEFAULT_AMPS,
    DEFAULT_FREQS,
    NONIDEAL_SEEDS,
    NonIdeal,
    default_nonideal_configs,
    fit_noise_k,
    noise_configs,
    nonideal_fold,
    ring_burst,
    run_nonideal_sweep,
)
from .foldaudio import fold_capture, hard_clip, snr_db
from .shockdaq import (
    DEFAULT_LAM_V,
    DEFAULT_SR,
    gen_gearbox_startup,
    gen_impact_transient,
    overload_event_mask,
    recover_or_clip,
)

LAM = DEFAULT_LAM_V
SR = DEFAULT_SR

# §3.6: the "seven failing captures" = the six seed-7 grid bursts at 8 kHz ring
# with A = 8…40 V + the past-limit impact case of the shockdaq demo. The
# 2026-10-15 run did not record which six bursts it used; this set reproduces
# the stated ranges, and fallback_vs_clip_grid() gives the full-grid range so
# the selection is not hidden.
FALLBACK_BURSTS = tuple((a, 8000.0) for a in DEFAULT_AMPS if a >= 8.0)


def fallback_vs_clip() -> list[dict]:
    """§3.6: SNR of clip(unwrap) and of the folded fallback, with a true hard clip
    of the input as the reference signal (dB)."""
    caps = [
        (f"burst {a:g} V @ {f / 1000:g} kHz", ring_burst(SR, amp=a, f_ring=f, lam=LAM))
        for a, f in FALLBACK_BURSTS
    ]
    caps.append(
        ("impact_too_fast", gen_impact_transient(sr=SR, lam=LAM, peak_amp=60.0))
    )
    rows = []
    for name, x in caps:
        y = fold_capture(x, LAM)
        out = recover_or_clip(y, LAM)
        rec, _ = recover_blind(y, LAM, prior="quiet_window")
        clip = hard_clip(x, LAM)
        rows.append(
            {
                "capture": name,
                "fallback": out.fallback,
                "clip_unwrap_db": snr_db(clip, np.clip(rec, -LAM, LAM)),
                "folded_db": snr_db(clip, out.signal),
            }
        )
    return rows


def fallback_vs_clip_grid(seed: int = 7) -> dict:
    """§3.6: same two SNRs over every failing cell (SNR < 60 dB) of one seed's grid."""
    cu, fo = [], []
    for a in DEFAULT_AMPS:
        for f in DEFAULT_FREQS:
            x = ring_burst(SR, amp=a, f_ring=f, lam=LAM, seed=seed)
            y = fold_capture(x, LAM)
            rec, _ = recover_blind(y, LAM, prior="quiet_window")
            if snr_db(x, rec) >= 60.0:
                continue
            clip = hard_clip(x, LAM)
            cu.append(snr_db(clip, np.clip(rec, -LAM, LAM)))
            fo.append(snr_db(clip, recover_or_clip(y, LAM).signal))
    return {
        "cells": len(cu),
        "clip_unwrap_min": min(cu),
        "clip_unwrap_max": max(cu),
        "folded_min": min(fo),
        "folded_max": max(fo),
    }


def mask_coverage(seeds=(7, 8, 9)) -> dict:
    """§3.6: grid cells where overload_event_mask misses an |x| ≥ λ sample."""
    cells = missed = 0
    for sd in seeds:
        for a in DEFAULT_AMPS:
            for f in DEFAULT_FREQS:
                x = ring_burst(SR, amp=a, f_ring=f, lam=LAM, seed=sd)
                m = overload_event_mask(fold_capture(x, LAM), LAM)
                cells += 1
                missed += bool(np.any((np.abs(x) >= LAM) & ~m))
    return {"cells": cells, "missed": missed}


def noise_k_fit() -> dict:
    """§4.4: k fit on the 9 noise rows × 5 seeds, plus the 3-seed/held-out check."""
    cells = run_nonideal_sweep(noise_configs())["cells"]
    full = fit_noise_k(cells)
    by_k = {r["k"]: r for r in full["rows"]}
    train = [c for c in cells if c.seed in (7, 8, 9)]
    held = [c for c in cells if c.seed in (10, 11)]
    k3 = fit_noise_k(train)["k_min_safe"]
    held_row = fit_noise_k(held, ks=[k3])["rows"][0]
    fno = [c for c in cells if c.recovered_ok and not c.noise_aware_ok]
    snr_of = {c.name: c.noise_snr_db for c in noise_configs()}
    return {
        "cells": len(cells),
        "k_min_safe": full["k_min_safe"],
        "k0": by_k[0.0],
        "k5": by_k[5.0],
        "k_three_seeds": k3,
        "held_out_false_ok": held_row["false_ok"],
        "false_no_max_snr_db": max(snr_of[c.config] for c in fno) if fno else None,
    }


def sigma_estimate_errors() -> list[float]:
    """§4.5: relative error of estimate_noise_sigma on the five synthetic records
    of tests/test_blind_level.py (quiet baseline + noise + burst; folded case)."""
    errs = []
    rng = np.random.default_rng(42)
    n = 20_000
    for sigma in (0.01, 0.05, 0.2, 1.0):
        y = sigma * rng.standard_normal(n)
        burst = np.zeros(n)
        burst[n // 2 : n // 2 + 500] = 4.0 * np.sin(np.linspace(0, 20 * np.pi, 500))
        errs.append(abs(estimate_noise_sigma(y + burst, win=2048) - sigma) / sigma)
    rng = np.random.default_rng(7)
    n = 16_384
    sigma = 0.08 * LAM
    x = sigma * rng.standard_normal(n)
    t = np.arange(800) / 800.0
    x[6000:6800] += 3.0 * LAM * np.exp(-3 * t) * np.sin(2 * np.pi * 12 * t)
    errs.append(
        abs(estimate_noise_sigma(fold_capture(x, LAM), win=2048) - sigma) / sigma
    )
    return [float(e) for e in errs]


def burst_peaks() -> dict:
    """§5.3: measured peak / A over all 280 grid cells, and the 6 V row's peaks."""
    ratios, six = [], []
    for sd in NONIDEAL_SEEDS:
        for a in DEFAULT_AMPS:
            for f in DEFAULT_FREQS:
                pk = float(
                    np.max(np.abs(ring_burst(SR, amp=a, f_ring=f, lam=LAM, seed=sd)))
                )
                ratios.append(pk / a)
                if a == 6.0:
                    six.append(pk)
    return {
        "cells": len(ratios),
        "ratio_min": min(ratios),
        "ratio_max": max(ratios),
        "six_v_min": min(six),
        "six_v_max": max(six),
        "six_v_below_lam": sum(p < LAM for p in six),
        "six_v_cells": len(six),
    }


def mid_overload_and_dc() -> dict:
    """§6.2: records starting mid-overload (naive k=0 vs blind priors) + DC shift."""
    out = {}
    for name, gen in (
        ("gearbox", gen_gearbox_startup),
        ("impact", gen_impact_transient),
    ):
        x = gen(lam=LAM)
        x = x[int(np.argmax(np.abs(x))) :]
        y = fold_capture(x, LAM)
        out[name] = {"naive_db": snr_db(x, naive_k0(y, LAM))}
        for prior in ("zero_mean", "quiet_window"):
            rec, k = recover_blind(y, LAM, prior=prior)
            out[name][prior] = {"k": int(k), "snr_db": snr_db(x, rec)}
    x = gen_gearbox_startup(lam=LAM) + 1.2 * LAM
    rec, _ = recover_blind(fold_capture(x, LAM), LAM, prior="zero_mean")
    out["dc_shift_zero_mean_db"] = snr_db(x, rec)
    return out


def inl_leak_into_gain() -> float:
    """§7.1: apparent ĝ from a 5 % INL bow when the fit has no INL terms
    (calibration tone at 60 dB, seed 0 — the calibrate_config defaults)."""
    x = cal_tone(LAM, SR, noise_snr_db=60.0, seed=0)
    y = nonideal_fold(x, LAM, NonIdeal(inl=0.05))
    return estimate_front_end(y, LAM, sr=SR, inl_harmonics=0).g_hat


def rail_on_recovered(config: str = "combo-mild") -> dict:
    """§7.4: recovered cells of a config whose capture has ≥ 1 rail sample."""
    ni = next(c for c in default_nonideal_configs() if c.name == config)
    cells = run_nonideal_sweep([ni])["cells"]
    ok = [c for c in cells if c.recovered_ok]
    return {
        "recovered": len(ok),
        "rail_on_recovered": sum(c.rail_hits > 0 for c in ok),
        "rail_on_recovered_and_accurate": sum(
            c.rail_hits > 0 and c.accurate for c in ok
        ),
    }


def format_claims() -> str:
    L = ["Whitepaper spot claims (reproduced; asserted in tests/test_claims.py)"]
    rows = fallback_vs_clip()
    cu = [r["clip_unwrap_db"] for r in rows]
    fo = [r["folded_db"] for r in rows]
    L.append("§3.6 fallback vs true hard clip (SNR, hard clip as reference):")
    for r in rows:
        L.append(
            f"   {r['capture']:<22} clip(unwrap) {r['clip_unwrap_db']:6.1f} dB   folded {r['folded_db']:+5.1f} dB"
        )
    L.append(
        f"   range: clip(unwrap) {min(cu):.1f} … {max(cu):.1f} dB; folded {min(fo):+.1f} … {max(fo):+.1f} dB"
    )
    g = fallback_vs_clip_grid()
    L.append(
        f"   all {g['cells']} failing seed-7 grid cells: clip(unwrap) {g['clip_unwrap_min']:.1f} … "
        f"{g['clip_unwrap_max']:.1f} dB; folded {g['folded_min']:+.1f} … {g['folded_max']:+.1f} dB"
    )
    mc = mask_coverage()
    L.append(
        f"§3.6 event mask: missed |x|≥λ samples in {mc['missed']} of {mc['cells']} cells (seeds 7–9)"
    )
    nk = noise_k_fit()
    L.append(
        f"§4.4 noise k: {nk['cells']} cells, smallest safe k {nk['k_min_safe']}; k=0 false-ok {nk['k0']['false_ok']} "
        f"agree {nk['k0']['agrees']}; k=5 false-ok {nk['k5']['false_ok']} agree {nk['k5']['agrees']} "
        f"false-no {nk['k5']['false_no']} (max SNR {nk['false_no_max_snr_db']:g} dB); "
        f"seeds 7–9 fit k={nk['k_three_seeds']} → held-out false-ok {nk['held_out_false_ok']}"
    )
    se = sigma_estimate_errors()
    L.append(
        f"§4.5 σ estimate rel. error: max {100 * max(se):.1f} % ({', '.join(f'{100 * e:.1f}' for e in se)} %)"
    )
    bp = burst_peaks()
    L.append(
        f"§5.3 burst peak/A over {bp['cells']} cells: {bp['ratio_min']:.2f}–{bp['ratio_max']:.2f}; 6 V row peaks "
        f"{bp['six_v_min']:.2f}–{bp['six_v_max']:.2f} V, {bp['six_v_below_lam']} of {bp['six_v_cells']} below λ"
    )
    mo = mid_overload_and_dc()
    for nm in ("gearbox", "impact"):
        d = mo[nm]
        L.append(
            f"§6.2 mid-overload {nm}: naive k=0 {d['naive_db']:.1f} dB; zero-mean k={d['zero_mean']['k']:+d} "
            f"{d['zero_mean']['snr_db']:.1f} dB; quiet-window k={d['quiet_window']['k']:+d} {d['quiet_window']['snr_db']:.1f} dB"
        )
    L.append(
        f"§6.2 DC shift 1.2λ, zero-mean prior: {mo['dc_shift_zero_mean_db']:.1f} dB"
    )
    L.append(
        f"§7.1 5 % INL with no INL terms → ĝ = {100 * inl_leak_into_gain():+.1f} %"
    )
    ro = rail_on_recovered()
    L.append(
        f"§7.4 combo-mild: rail check on {ro['rail_on_recovered']} of {ro['recovered']} recovered cells "
        f"({ro['rail_on_recovered_and_accurate']} of them accurate)"
    )
    return "\n".join(L)
