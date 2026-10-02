"""Monte Carlo SER comparison: WrapCancel vs unfold vs unclipped-oracle.

Grid (per task brief):
  OF ∈ {2, 4, 8}
  λ/σ ∈ {2, 3}
  8-PAM injective-mod-λ
  Ns small (default 2) so exhaustive 8^{Ns} is cheap

Oracle column: ML on y_unc = Ha + w (no fold, no quant; σ_q²=0) — ADC lower bound.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .channel import build_H, transmit_with_OF
from .constellation import constellation_energy, injective_8pam
from .unfold_detect import unfold_then_detect
from .wrapcancel import oracle_unclipped_detect, wrapcancel_detect


@dataclass
class SerRow:
    OF: int
    lam_over_sigma: float
    ser_wrapcancel: float
    ser_unfold: float
    ser_oracle: float  # unclipped ADC ML (y_unc=Ha+w, σ_q²=0)
    n_trials: int
    Ns: int
    bits: int
    snr_db: float


def _draw_symbols(alphabet: np.ndarray, Ns: int, rng: np.random.Generator) -> np.ndarray:
    idx = rng.integers(0, len(alphabet), size=Ns)
    return alphabet[idx]


def run_ser_point(
    OF: int,
    lam_over_sigma: float,
    *,
    lam: float = 1.0,
    Ns: int = 2,
    bits: int = 4,
    n_trials: int = 80,
    seed: int = 0,
) -> SerRow:
    """Estimate SER at one (OF, λ/σ) operating point."""
    rng = np.random.default_rng(seed)
    alphabet = injective_8pam(lam)
    sigma = lam / lam_over_sigma
    H = build_H(Ns, OF)
    Es = constellation_energy(alphabet)
    snr_db = 10.0 * np.log10(Es / (sigma**2))

    err_wc = 0
    err_un = 0
    err_or = 0
    symbols_total = 0
    for _ in range(n_trials):
        a = _draw_symbols(alphabet, Ns, rng)
        y_q, Sigma_w, sigma_q2, y_unc = transmit_with_OF(a, H, OF, lam, sigma, bits, rng)
        a_wc, _ = wrapcancel_detect(y_q, H, alphabet, lam, Sigma_w, sigma_q2)
        a_un, _ = unfold_then_detect(y_q, H, alphabet, lam, Sigma_w, sigma_q2)
        # Oracle: unclipped Ha+w, no quantization noise term.
        a_or, _ = oracle_unclipped_detect(y_unc, H, alphabet, Sigma_w, sigma_q2=0.0)
        err_wc += int(np.sum(a_wc != a))
        err_un += int(np.sum(a_un != a))
        err_or += int(np.sum(a_or != a))
        symbols_total += Ns

    return SerRow(
        OF=OF,
        lam_over_sigma=lam_over_sigma,
        ser_wrapcancel=err_wc / symbols_total,
        ser_unfold=err_un / symbols_total,
        ser_oracle=err_or / symbols_total,
        n_trials=n_trials,
        Ns=Ns,
        bits=bits,
        snr_db=snr_db,
    )


def run_ser_table(
    *,
    OFs: tuple[int, ...] = (2, 4, 8),
    ratios: tuple[float, ...] = (2.0, 3.0),
    Ns: int = 2,
    bits: int = 4,
    n_trials: int = 80,
    seed: int = 42,
    lam: float = 1.0,
) -> list[SerRow]:
    """Full synthetic SER table over the brief's grid."""
    rows: list[SerRow] = []
    k = 0
    for ratio in ratios:
        for OF in OFs:
            row = run_ser_point(
                OF,
                ratio,
                lam=lam,
                Ns=Ns,
                bits=bits,
                n_trials=n_trials,
                seed=seed + k,
            )
            rows.append(row)
            k += 1
    return rows


def format_ser_table(rows: list[SerRow]) -> str:
    # SER_Oracle: unclipped ADC ML on y_unc=Ha+w (no fold/quant; σ_q²=0).
    lines = [
        f"{'OF':>4} {'λ/σ':>6} {'SNR_dB':>8} {'SER_WrapCancel':>16} "
        f"{'SER_Unfold':>12} {'SER_Oracle':>12} {'trials':>7}",
        "-" * 74,
    ]
    for r in rows:
        lines.append(
            f"{r.OF:4d} {r.lam_over_sigma:6.1f} {r.snr_db:8.2f} "
            f"{r.ser_wrapcancel:16.4f} {r.ser_unfold:12.4f} "
            f"{r.ser_oracle:12.4f} {r.n_trials:7d}"
        )
    return "\n".join(lines)
