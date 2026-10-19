"""Probe: does the UNRECOVERABLE fallback mask cover every overloaded sample on
the measured CWRU records under the non-ideal front ends? (NOTES #8c, 2026-10-19)

Prints, over all fallback cells of realdata.run_real_nonideal_sweep's grid:
  - overloaded samples left outside overload_event_mask alone (the pre-fix mask),
  - the same for event mask OR rail mask (what recover_or_clip now emits),
  - mask coverage and masked fraction for smaller event-merge gaps (sensitivity
    only; the default gap is unchanged).
Needs the CWRU files cached (python -m foldcrypt shockdaq-real) and SciPy.
Usage: python scripts/probe_fallback_mask.py
"""

from __future__ import annotations

import numpy as np

from foldcrypt import realdata as rd
from foldcrypt.blind_level import rail_mask
from foldcrypt.failmap import default_nonideal_configs, nonideal_fold
from foldcrypt.shockdaq import overload_event_mask, recover_or_clip

GAPS = (1024, 256, 64, 16)


def main() -> None:
    cfgs = default_nonideal_configs()
    ev_only = [0, 0]  # cells, samples uncovered by the event mask alone
    both = [0, 0]  # same for event | rail
    gap_stats = {g: [0, 0, []] for g in GAPS}
    n_fb = 0
    for fid in rd.CWRU_FILES:
        for _name, _label, v, _sr in rd._variants(fid, None, False, True):
            peak = float(np.max(np.abs(v)))
            rms = float(np.sqrt(np.mean(v**2)))
            for r in rd.RATIOS:
                lam = r * peak
                for ci, ni in enumerate(cfgs):
                    x = v
                    if ni.noise_snr_db is not None:
                        rng = np.random.default_rng(
                            rd.NONIDEAL_NOISE_SEED + fid * 31 + ci
                        )
                        x = v + rms / 10 ** (ni.noise_snr_db / 20.0) * (
                            rng.standard_normal(len(v))
                        )
                    y = nonideal_fold(x, lam, ni)
                    out = recover_or_clip(y, lam, bits=ni.bits)
                    if not out.fallback:
                        continue
                    n_fb += 1
                    over = np.abs(x) >= lam
                    rm = rail_mask(y, lam, bits=ni.bits)
                    u1 = over & ~overload_event_mask(y, lam)
                    u2 = over & ~out.untrusted
                    ev_only[0] += int(u1.any())
                    ev_only[1] += int(u1.sum())
                    both[0] += int(u2.any())
                    both[1] += int(u2.sum())
                    for g in GAPS:
                        m = overload_event_mask(y, lam, gap=g, pad=min(32, g)) | rm
                        uu = over & ~m
                        st = gap_stats[g]
                        st[0] += int(uu.any())
                        st[1] += int(uu.sum())
                        st[2].append(float(m.mean()))
    print(f"fallback cells: {n_fb}")
    print(f"event mask only : uncovered cells={ev_only[0]} samples={ev_only[1]}")
    print(f"event | rail    : uncovered cells={both[0]} samples={both[1]}")
    for g in GAPS:
        c, s, fr = gap_stats[g]
        print(
            f"gap={g:<5} (event|rail) uncovered cells={c} samples={s} "
            f"masked median={np.median(fr):.4f} p25={np.quantile(fr, 0.25):.4f}"
        )


if __name__ == "__main__":
    main()
