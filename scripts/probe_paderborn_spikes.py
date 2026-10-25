"""Paderborn spike-origin probe (NOTES #8h) -> artifacts/paderborn/spike-probe-metrics.json.

Usage: python scripts/probe_paderborn_spikes.py [--download]

Reads the 12 SHA-256-pinned Paderborn records from the cache (see
``foldcrypt/paderborn.py``; ``--download`` fetches missing ones as
``scripts/run_paderborn.py`` does). Applies the decision rules fixed in
``artifacts/paderborn/prereg-2026-10-25.md`` and prints HELD / FALSIFIED /
INCONCLUSIVE for H1 (electrical), H2 (mechanical) and H3 (pre-fold filter).
Exit status is 0 whenever the probe ran; verdicts are results, not errors.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from foldcrypt import paderborn_spikes as ps  # noqa: E402

BAND_ORDER = ("pwm16k", "fr", "bpfo", "bpfi", "decoy1", "decoy2", "decoy3", "fe", "6fe")


def _fmt_band(b: ps.BandTest) -> str:
    star = "*" if b.significant else " "
    return f"{b.name}{star} R={b.r_max:.3f}@{b.f_at_max:.2f}Hz p={b.p:.1e}"


def main() -> int:
    probes = ps.run_probe(download="--download" in sys.argv)
    print(
        f"bands: pwm16k = {ps.PWM_HZ:.0f} Hz ±{ps.PWM_BAND_FRAC:.0%}; kinematic ±{ps.KIN_BAND_FRAC:.0%}; "
        f"BPFO = {ps.BPFO_X:.4f} f_r, BPFI = {ps.BPFI_X:.4f} f_r; decoys {ps.DECOY_X} f_r; alpha {ps.ALPHA:g}"
    )
    for p in probes:
        print()
        print(
            f"{p.record}  spikes {p.n_spikes}  f_r {p.fr_hz:.2f} Hz  "
            f"raw headroom {p.raw['headroom_db']:+.2f} dB  kurt {p.raw['kurtosis']:.1f}"
            + (
                f"  fault line {p.raw['line_snr_db']:.1f} dB"
                if p.raw["line_snr_db"] is not None
                else ""
            )
        )
        if p.spiky:
            print("  " + "  ".join(_fmt_band(p.bands[k]) for k in BAND_ORDER[:4]))
            print("  " + "  ".join(_fmt_band(p.bands[k]) for k in BAND_ORDER[4:]))
            ex = p.exploratory
            print(
                "  EXPLORATORY (post hoc): "
                + "  ".join(_fmt_band(ex[k]) for k in ps.EXPLORATORY_BANDS)
                + f"  index mod 4 {ex['mod4']}"
            )
            c = p.current
            print(
                f"  current coincidence {c['frac']:.3f} (null {c['null_frac']:.3f}) "
                f"evidence={c['evidence']}  shape {p.shape}  current spikes {p.current_spikes}"
            )
            print(
                f"  H1 evidence={p.h1_evidence}  H2 evidence={p.h2_evidence}  "
                f"decoy-contaminated={p.decoy_contaminated}"
            )
        for name, f in p.filters.items():
            extra = (
                f"  cells {f['cells']} rec {f['recovered']} silent {f['silent_fail']} "
                f"rule {f['rule_correct']}/{f['cells']}"
                if "cells" in f
                else ""
            )
            line = (
                f"  line {f['line_snr_db']:.1f} dB"
                if f["line_snr_db"] is not None
                else ""
            )
            print(
                f"  {name:<4} headroom {f['headroom_db']:+.2f} dB  kurt {f['kurtosis']:.1f}  "
                f"spikes left {f['spikes_left']}{line}{extra}"
            )
    v = ps.verdicts(probes)
    print()
    print(
        f"spiky records {v['spiky_records']}; H1 evidence {v['h1_evidence']}/8, "
        f"H2 evidence {v['h2_evidence']}/8, decoy-contaminated {v['decoy_contaminated']}/8"
    )
    print(
        f"  breakdown: H1a 16 kHz band {v['h1a_pwm_band']}/8, H1b current {v['h1b_current']}/8, "
        f"H2 ignoring decoy rule {v['h2_ignoring_decoys']}/8"
    )
    for name, f in v["filters"].items():
        print(f"  {name}: {f}")
    for h in ("H1", "H2", "H3"):
        print(f"{v[h]:>12}  {h}")
    sp = [p for p in probes if p.spiky]
    m100 = [p.exploratory["mains100"] for p in sp]
    hf = [p.exploratory[k] for p in sp for k in ("ctl8k", "ctl12k", "ctl20k", "ctl24k")]
    print(
        f"EXPLORATORY (post hoc): 100 Hz locked in {sum(b.significant for b in m100)}/{len(sp)} "
        f"(R {min(b.r_max for b in m100):.2f}-{max(b.r_max for b in m100):.2f}); "
        f"HF control bands significant {sum(b.significant for b in hf)}/{len(hf)} "
        f"(min p {min(b.p for b in hf):.1e})"
    )
    out = ROOT / "artifacts" / "paderborn" / "spike-probe-metrics.json"
    doc = {
        "source": "Paderborn KAt via Zenodo 15845309 (CC BY 4.0); vibration_1 + phase_current_1/2, 64 kHz",
        "prereg": "artifacts/paderborn/prereg-2026-10-25.md",
        "verdicts": v,
        "records": [
            {
                **{
                    k: val
                    for k, val in asdict(p).items()
                    if k not in ("bands", "exploratory")
                },
                "bands": {
                    k: asdict(b) | {"significant": b.significant}
                    for k, b in p.bands.items()
                },
                "exploratory_post_hoc": {
                    k: (asdict(b) | {"significant": b.significant})
                    if isinstance(b, ps.BandTest)
                    else b
                    for k, b in p.exploratory.items()
                },
                "h1_evidence": p.h1_evidence,
                "h2_evidence": p.h2_evidence,
                "decoy_contaminated": p.decoy_contaminated if p.spiky else None,
            }
            for p in probes
        ],
    }
    out.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
