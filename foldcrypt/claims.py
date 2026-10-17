"""Reproduce the whitepaper's spot numbers that no demo table prints.

Every function here is deterministic (fixed seeds) and maps to one sentence in
docs/foldaudio-whitepaper.md; tests/test_claims.py asserts each value at the
precision the report states it, so a code change that moves a number fails CI
instead of silently leaving a stale claim. `python -m foldcrypt claims` prints
them all (the noise-k fit runs a 2,520-cell sweep, ~10 s).

Nothing here tunes anything: it only re-runs the existing library code.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from .blind_level import estimate_noise_sigma, naive_k0, recover_blind
from .calibrate import (
    cal_tone,
    calibrate_config,
    default_cal_configs,
    estimate_front_end,
)
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
    run_failmap,
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


@lru_cache(maxsize=1)
def nonideal_cells() -> tuple:
    """All 25 default non-ideal configs × 280 cells (the --nonideal sweep, ~20 s)."""
    return tuple(run_nonideal_sweep()["cells"])


def _cells_of(config: str) -> list:
    return [c for c in nonideal_cells() if c.config == config]


def noise_k_fit() -> dict:
    """§4.4: k fit on the 9 noise rows × 5 seeds, plus the 3-seed/held-out check."""
    names = {c.name for c in noise_configs()}
    cells = [c for c in nonideal_cells() if c.config in names]
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
    ok = [c for c in _cells_of(config) if c.recovered_ok]
    oo = [c for c in ok if c.overloaded]
    return {
        "recovered": len(ok),
        "rail_on_recovered": sum(c.rail_hits > 0 for c in ok),
        "rail_on_recovered_and_accurate": sum(
            c.rail_hits > 0 and c.accurate for c in ok
        ),
        "recovered_overloaded": len(oo),
        "rail_on_recovered_overloaded": sum(c.rail_hits > 0 for c in oo),
        "rail_on_recovered_overloaded_and_accurate": sum(
            c.rail_hits > 0 and c.accurate for c in oo
        ),
    }


# ---------------------------------------------------------------------------
# Overloaded-only counts (whitepaper v1.5). A cell is "overloaded" iff the input
# the fold saw reached λ (max|x| ≥ λ). Cells that never reach λ are recovered
# trivially (the fold is the identity there), so they must not count toward
# fold-recovery results. Failures are always overloaded, so failure, flag and
# false-ok counts do not change; recovered / agreement / accuracy counts are
# restated over overloaded cells.
# ---------------------------------------------------------------------------


def failmap_overloaded() -> dict:
    """Tables 3–4: ideal-front-end grid, seed 7 and seeds 7–11."""
    out = {}
    per_seed = {sd: run_failmap(seed=sd) for sd in NONIDEAL_SEEDS}
    for key, cells in (
        ("seed7", per_seed[7]),
        ("seeds7_11", [c for sd in NONIDEAL_SEEDS for c in per_seed[sd]]),
    ):
        o = [c for c in cells if c.overloaded]
        ok = [c for c in o if c.recovered_ok]
        fails = [c for c in cells if not c.recovered_ok]
        out[key] = {
            "cells": len(cells),
            "overloaded": len(o),
            "in_range_recovered": sum(
                c.recovered_ok for c in cells if not c.overloaded
            ),
            "recovered": len(ok),
            "failed": len(fails),
            "failed_overloaded": sum(c.overloaded for c in fails),
            "rule_agrees": sum(c.predicted_ok == c.recovered_ok for c in o),
            "flagged": sum(c.slip_flag or c.edge_flag for c in fails),
            "slip": sum(c.slip_flag for c in fails),
            "edge": sum(c.edge_flag for c in fails),
            "slip_false_alarms": sum(c.slip_flag for c in ok),
            "edge_on_recovered": sum(c.edge_flag for c in ok),
        }
    out["in_range_cells"] = [
        (c.amp_V, c.f_ring_Hz, sd, c.peak_V)
        for sd in NONIDEAL_SEEDS
        for c in per_seed[sd]
        if not c.overloaded
    ]
    return out


QUANT_CHECK_BITS = (3, 4, 6, 8, 12, 16, 24)


def quant_overloaded(bits=QUANT_CHECK_BITS) -> dict:
    """Table 5 (seed 7) overloaded count + the 5-seed bit-depth check of
    docs/shockdaq-failmap.md: plain-rule agreement, all cells and overloaded."""
    seed7 = sum(c.overloaded for c in run_failmap(bits=16, seed=7))
    rows = {}
    for b in bits:
        cells = [c for sd in NONIDEAL_SEEDS for c in run_failmap(bits=b, seed=sd)]
        o = [c for c in cells if c.overloaded]
        rows[b] = {
            "cells": len(cells),
            "rule_agrees": sum(c.predicted_ok == c.recovered_ok for c in cells),
            "overloaded": len(o),
            "rule_agrees_overloaded": sum(c.predicted_ok == c.recovered_ok for c in o),
            "silent": sum(c.silent_fail for c in cells),
        }
    return {"seed7_overloaded": seed7, "five_seed": rows}


def _row(cells) -> dict:
    o = [c for c in cells if c.overloaded]
    ok = [c for c in o if c.recovered_ok]
    fails = [c for c in o if not c.recovered_ok]
    inr = [c for c in cells if not c.overloaded]
    return {
        "cells": len(cells),
        "overloaded": len(o),
        "recovered": len(ok),
        "failed": len(fails),
        "failed_all": sum(not c.recovered_ok for c in cells),
        "rule": sum(c.predicted_ok == c.recovered_ok for c in o),
        "clean": sum(c.clean_rule_ok == c.recovered_ok for c in o),
        "derated": sum(c.derated_ok == c.recovered_ok for c in o),
        "flagged": sum(c.slip_flag or c.edge_flag for c in fails),
        "silent": sum(c.silent_fail for c in cells),
        "slip_fa": sum(c.slip_flag for c in ok),
        "edge_on_ok": sum(c.edge_flag for c in ok),
        "accurate": sum(c.accurate for c in o),
        "unflagged": sum(c.silent_inaccurate for c in o),
        "invisible": sum(c.silent_inaccurate_no_rail for c in o),
        "n_aware": sum(c.noise_aware_ok == c.recovered_ok for c in o),
        "combined": sum(c.combined_ok == c.recovered_ok for c in o),
        "n_aware_false_ok": sum(c.noise_aware_ok and not c.recovered_ok for c in o),
        "combined_false_ok": sum(c.combined_ok and not c.recovered_ok for c in o),
        "n_aware_false_no": sum((not c.noise_aware_ok) and c.recovered_ok for c in o),
        "combined_false_no": sum((not c.combined_ok) and c.recovered_ok for c in o),
        "derated_false_ok": sum(c.derated_ok and not c.recovered_ok for c in o),
        "derated_false_no": sum((not c.derated_ok) and c.recovered_ok for c in o),
        "plain_false_ok": sum(c.predicted_ok and not c.recovered_ok for c in o),
        "max_err_V": max((c.err_peak_V for c in ok), default=0.0),
        "max_err_frac": max((c.peak_err_frac for c in ok), default=0.0),
        "in_range": len(inr),
        "in_range_inaccurate": sum(not c.accurate for c in inr),
        "in_range_unflagged": sum(c.silent_inaccurate for c in inr),
        "in_range_invisible": sum(c.silent_inaccurate_no_rail for c in inr),
    }


def nonideal_overloaded() -> dict:
    """Tables 6–7, §4.4/§4.5/§6.5 counts over overloaded cells, per config."""
    return {ni.name: _row(_cells_of(ni.name)) for ni in default_nonideal_configs()}


def noise_fit_overloaded(ks=(0.0, 3.0, 4.0, 4.75, 5.0)) -> dict:
    """§4.4 k table restricted to overloaded noise-row cells."""
    names = {c.name for c in noise_configs()}
    cells = [c for c in nonideal_cells() if c.config in names and c.overloaded]
    rows = {r["k"]: r for r in fit_noise_k(cells, ks=list(ks))["rows"]}
    return {"cells": len(cells), "rows": rows}


@lru_cache(maxsize=1)
def calibration_overloaded() -> dict:
    """Table 9 over overloaded cells: before = uncalibrated sweep, after = ĝ + INL cal."""
    cfgs = default_cal_configs()
    cals = {ni.name: calibrate_config(ni) for ni in cfgs}
    after = run_nonideal_sweep(
        cfgs,
        gain_cal={k: v.g_hat for k, v in cals.items()},
        inl_cal={k: v.inl_coefs for k, v in cals.items()},
    )["cells"]
    rows = {}
    for ni in cfgs:
        b = _row(_cells_of(ni.name))
        a = _row([c for c in after if c.config == ni.name])
        rows[ni.name] = {
            "overloaded": b["overloaded"],
            "accurate": (b["accurate"], a["accurate"]),
            "unflagged": (b["unflagged"], a["unflagged"]),
            "invisible": (b["invisible"], a["invisible"]),
            "in_range_invisible_before": b["in_range_invisible"],
            "silent_after": a["silent"],
            "slip_fa_after": a["slip_fa"],
        }
    return rows


def cwru_all_overloaded() -> bool:
    """§6.6: λ = r · record peak with every r < 1, so every CWRU cell overloads."""
    from .realdata import RATIOS

    return max(RATIOS) < 1.0


def format_overloaded() -> str:
    L = ["", "Overloaded-only counts (cell overloaded iff max|x| ≥ λ):"]
    fmo = failmap_overloaded()
    for k, lab in (("seed7", "seed 7"), ("seeds7_11", "seeds 7–11")):
        d = fmo[k]
        L.append(
            f"  Tables 3–4 {lab}: {d['overloaded']}/{d['cells']} overloaded; recovered {d['recovered']}, "
            f"failed {d['failed']}; rule agrees {d['rule_agrees']}/{d['overloaded']}; flagged {d['flagged']} "
            f"(slip {d['slip']}, edge {d['edge']}); edge on recovered {d['edge_on_recovered']}; "
            f"slip FA {d['slip_false_alarms']}"
        )
    L.append(
        "  in-range cells: "
        + ", ".join(
            f"{a:g} V/{f:g} Hz seed {sd} ({pk:.2f} V)"
            for a, f, sd, pk in fmo["in_range_cells"]
        )
    )
    q = quant_overloaded()
    L.append(f"  Table 5 (seed 7): {q['seed7_overloaded']}/56 overloaded")
    for b, r in q["five_seed"].items():
        L.append(
            f"   5-seed {b:>2} bit: rule {r['rule_agrees']}/{r['cells']} all, "
            f"{r['rule_agrees_overloaded']}/{r['overloaded']} overloaded, silent {r['silent']}"
        )
    L.append("  Table 6 (overloaded cells only):")
    L.append(
        "   config         ovl  rec fail rule clean derat flag sil slipFA edge  acc unfl inv |"
        " n-aw comb nFO cFO nFN cFN | maxerr V   /pk | in-range: n unfl"
    )
    nio = nonideal_overloaded()
    for name, r in nio.items():
        L.append(
            f"   {name:<13} {r['overloaded']:4} {r['recovered']:4} {r['failed']:4} {r['rule']:4} {r['clean']:5} "
            f"{r['derated']:5} {r['flagged']:4} {r['silent']:3} {r['slip_fa']:6} {r['edge_on_ok']:4} "
            f"{r['accurate']:4} {r['unflagged']:4} {r['invisible']:3} | {r['n_aware']:4} {r['combined']:4} "
            f"{r['n_aware_false_ok']:3} {r['combined_false_ok']:3} {r['n_aware_false_no']:3} "
            f"{r['combined_false_no']:3} | {r['max_err_V']:7.3f} {100 * r['max_err_frac']:5.1f}% | "
            f"{r['in_range']:3} {r['in_range_unflagged']:3}"
        )
    non = [r for n, r in nio.items() if n != "ideal"]
    L.append(
        f"   non-ideal configs: {sum(r['overloaded'] for r in non)} overloaded of "
        f"{sum(r['cells'] for r in non)} cells; plain false-ok {sum(r['plain_false_ok'] for r in non)}, "
        f"derated false-ok {sum(r['derated_false_ok'] for r in non)}, "
        f"derated false-no {sum(r['derated_false_no'] for r in non)}"
    )
    nf = noise_fit_overloaded()
    L.append(f"  §4.4 k table, overloaded noise cells ({nf['cells']}):")
    for k, r in nf["rows"].items():
        L.append(
            f"   k={k:<5g} agree {r['agrees']} false-ok {r['false_ok']} false-no {r['false_no']}"
        )
    L.append(
        "  Table 9 (overloaded only): accurate / unflagged >1 % / invisible, before → after"
    )
    cal_rows = calibration_overloaded()
    for name, r in cal_rows.items():
        L.append(
            f"   {name:<13} ovl {r['overloaded']}  acc {r['accurate'][0]} → {r['accurate'][1]}  "
            f"unfl {r['unflagged'][0]} → {r['unflagged'][1]}  inv {r['invisible'][0]} → "
            f"{r['invisible'][1]}  silent after {r['silent_after']}, slip FA after {r['slip_fa_after']}"
        )
    L.append(
        f"   invisible total: {sum(r['invisible'][0] for r in cal_rows.values())} → "
        f"{sum(r['invisible'][1] for r in cal_rows.values())} (in-range cells before: "
        f"{sum(r['in_range_invisible_before'] for r in cal_rows.values())})"
    )
    L.append(
        f"  §6.6 CWRU: every cell overloaded by construction (all r < 1): {cwru_all_overloaded()}"
    )
    return "\n".join(L)


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
        f"({ro['rail_on_recovered_and_accurate']} of them accurate); overloaded only: "
        f"{ro['rail_on_recovered_overloaded']} of {ro['recovered_overloaded']} "
        f"({ro['rail_on_recovered_overloaded_and_accurate']} accurate)"
    )
    return "\n".join(L) + format_overloaded()
