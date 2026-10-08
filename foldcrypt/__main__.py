"""CLI: python -m foldcrypt shockdaq-demo | shockdaq-failmap | audio-demo | shares-demo | demo | ser | defect-demo | block-demo"""

from __future__ import annotations

import argparse
import sys

import numpy as np

from .channel import build_H, transmit_with_OF
from .constellation import injective_8pam
from .defect_mask import defect_decrypt, defect_encrypt, flip_bits
from .recovery_shares import PARAMS, corrupt_share, recover_secret, split_secret
from .foldaudio import DEFAULT_LAM, format_snr_table, run_audio_demo
from .shockdaq import DEFAULT_LAM_V, format_shockdaq_table, run_shockdaq_demo
from .failmap import format_failmap, run_failmap_report
from .simulate import format_ser_table, run_ser_table
from .unfold_detect import unfold_then_detect
from .wrapcancel import wrapcancel_detect, block_mahalanobis_detect


def cmd_demo(args: argparse.Namespace) -> int:
    """Single-shot WrapCancel vs unfold on one random draw."""
    lam = 1.0
    OF = args.OF
    ratio = args.ratio
    Ns = args.Ns
    bits = args.bits
    seed = args.seed
    sigma = lam / ratio
    rng = np.random.default_rng(seed)
    alphabet = injective_8pam(lam)
    H = build_H(Ns, OF)
    a = alphabet[rng.integers(0, 8, size=Ns)]
    y_q, Sigma_w, sigma_q2, _y_unc = transmit_with_OF(a, H, OF, lam, sigma, bits, rng)

    a_wc, m_wc = wrapcancel_detect(y_q, H, alphabet, lam, Sigma_w, sigma_q2)
    a_un, m_un = unfold_then_detect(y_q, H, alphabet, lam, Sigma_w, sigma_q2)

    ok_wc = np.array_equal(a_wc, a)
    ok_un = np.array_equal(a_un, a)

    print("FoldCrypt WrapCancel demo (arXiv:2609.11298 toy)")
    print(f"  OF={OF}  λ/σ={ratio}  Ns={Ns}  R={bits} bits  seed={seed}")
    print(f"  true a     = {np.array2string(a, precision=4)}")
    print(f"  WrapCancel = {np.array2string(a_wc, precision=4)}  metric={m_wc:.4f}  {'OK' if ok_wc else 'FAIL'}")
    print(f"  Unfold     = {np.array2string(a_un, precision=4)}  metric={m_un:.4f}  {'OK' if ok_un else 'FAIL'}")
    print(f"  roundtrip_wrapcancel={'OK' if ok_wc else 'FAIL'}")
    return 0 if ok_wc else 1


def cmd_ser(args: argparse.Namespace) -> int:
    rows = run_ser_table(
        OFs=(2, 4, 8),
        ratios=(2.0, 3.0),
        Ns=args.Ns,
        bits=args.bits,
        n_trials=args.trials,
        seed=args.seed,
    )
    print("Synthetic SER table — WrapCancel vs unfold vs unclipped-oracle")
    print(f"  Ns={args.Ns}  R={args.bits}  trials/point={args.trials}  seed={args.seed}")
    print("  Oracle = ML on y_unc=Ha+w (no fold, no quant; σ_q²=0) — ADC lower bound")
    print(format_ser_table(rows))
    # Score lead summary
    wins = sum(1 for r in rows if r.ser_wrapcancel < r.ser_unfold - 1e-12)
    ties = sum(1 for r in rows if abs(r.ser_wrapcancel - r.ser_unfold) <= 1e-12)
    print(f"\nWrapCancel lower-SER count: {wins}/{len(rows)}  (ties={ties})")
    return 0


def cmd_defect_demo(args: argparse.Namespace) -> int:
    key = b"foldcrypt-structure-salt-v0"
    msg = [1, 0, 1, 1]
    ct = defect_encrypt(msg, key)
    noisy = flip_bits(ct.mask, [2])  # 1 flip ≤ t=1
    got = defect_decrypt(ct, key, noisy)
    print("Defect-mask stub demo (Hamming [7,4,3], t=1)")
    print(f"  msg={msg}  mask={ct.mask}  noisy={noisy}  recovered={got}")
    print(f"  clean_roundtrip={'OK' if got == msg else 'FAIL'}")
    try:
        defect_decrypt(ct, b"wrong-key", noisy)
        print("  wrong_key_reject=FAIL (should have raised)")
        return 1
    except ValueError:
        print("  wrong_key_reject=OK")
    return 0


def cmd_block_demo(args: argparse.Namespace) -> int:
    """Ns=16 block detect — exhaustive 8^{16} is not runnable.

    Defaults use Nb=4, edge_discard=1, OF=16 so the light demo usually
    recovers (paper Fig. 11: Alg. 1 wants adequate oversampling).
    """
    lam = 1.0
    OF = args.OF
    ratio = args.ratio
    Ns = args.Ns
    bits = args.bits
    seed = args.seed
    Nb = args.Nb
    eta = args.eta
    K = args.K
    edge_discard = args.edge_discard
    sigma = lam / ratio
    rng = np.random.default_rng(seed)
    alphabet = injective_8pam(lam)
    H = build_H(Ns, OF)
    a = alphabet[rng.integers(0, 8, size=Ns)]
    y_q, Sigma_w, sigma_q2, _y_unc = transmit_with_OF(a, H, OF, lam, sigma, bits, rng)

    stats: dict = {}
    a_bl, m_bl = block_mahalanobis_detect(
        y_q, H, alphabet, lam, Sigma_w, sigma_q2,
        Nb=Nb, eta=eta, K=K, edge_discard=edge_discard, OF=OF,
        init="residue", stats=stats,
    )
    n_match = int(np.sum(a_bl == a))
    print("FoldCrypt block-Mahalanobis demo (arXiv:2609.11298 Alg. 1)")
    print(f"  OF={OF}  λ/σ={ratio}  Ns={Ns}  R={bits} bits  "
          f"Nb={Nb} η={eta} K={K} edge_discard={edge_discard}  seed={seed}")
    print(f"  blocks={stats['n_blocks']}  passes={stats['n_passes']}  "
          f"eval_count={stats['eval_count']}  early_stop={stats['early_stop']}")
    print(f"  exhaustive would need 8^{Ns} = {8**Ns:.3e} candidates — not run")
    print(f"  symbol_match={n_match}/{Ns}  metric={m_bl:.4f}")
    print(f"  roundtrip_block={'OK' if n_match == Ns else 'PARTIAL' if n_match >= int(0.75*Ns) else 'FAIL'}")
    return 0 if n_match >= int(0.75 * Ns) else 1


def cmd_shares_demo(args: argparse.Namespace) -> int:
    """Product demo: split → corrupt ≤t → recover OK; wrong passphrase FAIL."""
    secret = args.secret.encode("utf-8")
    passphrase = args.passphrase
    # Fixed salt so the demo is reproducible without looking random-flaky.
    salt = b"foldcrypt-share-demo"
    bundle = split_secret(secret, passphrase, salt=salt, iterations=50_000)
    print("FoldCrypt recovery-shares demo (product lane)")
    print(f"  code={PARAMS.code}  n={PARAMS.n} shares  k={PARAMS.k}  t={PARAMS.t}")
    print(f"  secret={secret!r}  blocks={bundle.n_blocks}  salt=fixed-demo")
    print(f"  shares: {[f'#{s.index}:{len(s.bits)}b' for s in bundle.shares]}")

    # Path A: flip all bits on one share (≤t=1 fully-corrupted share).
    shares_flip = list(bundle.shares)
    shares_flip[2] = corrupt_share(shares_flip[2], list(range(bundle.n_blocks)))
    got = recover_secret(bundle, passphrase, shares_flip)
    ok_flip = got == secret
    print(f"  corrupt_share#2_all_bits → recovered={got!r}  {'OK' if ok_flip else 'FAIL'}")

    # Path B: one missing share.
    shares_miss: list = list(bundle.shares)
    shares_miss[4] = None
    got2 = recover_secret(bundle, passphrase, shares_miss)
    ok_miss = got2 == secret
    print(f"  missing_share#4 → recovered={got2!r}  {'OK' if ok_miss else 'FAIL'}")

    # Path C: wrong passphrase fail-closed.
    try:
        recover_secret(bundle, "definitely-wrong")
        print("  wrong_passphrase_reject=FAIL (should have raised)")
        return 1
    except ValueError:
        print("  wrong_passphrase_reject=OK")

    if ok_flip and ok_miss:
        print("  shares_demo=OK")
        return 0
    print("  shares_demo=FAIL")
    return 1




def cmd_shockdaq_demo(args: argparse.Namespace) -> int:
    """ShockDAQ v0 company bet: IEPE fold-vs-clip on synthetic vibration."""
    rows = run_shockdaq_demo(lam=args.lam, sr=args.sr)
    print("ShockDAQ v0 — IEPE / vibration fold vs silent soft-clip")
    print(f"  λ={args.lam} V (ASSUMPTION ±5 V soft-sat rail)  sr={args.sr}")
    print(format_shockdaq_table(rows))
    print("  artifacts → /workspace/foldcrypt/artifacts/shockdaq/")
    wins = sum(1 for r in rows if r.snr_gain_db > 5.0 and r.peak_error_fold < r.peak_error_clip)
    print(f"  cases_fold_beats_clip(>5dB+better_peak)={wins}/{len(rows)}")
    bad = [r for r in rows if r.snr_blind_db < 60.0]
    silent = [r.name for r in bad if not r.overload_unrecoverable]
    false_alarm = [r.name for r in rows if r.snr_blind_db >= 60.0 and r.slip_flag]
    print(f"  UNREC = blind self-check (no original): SLIP = unwrap slip, EDGE = step within 10% of λ")
    print(f"  unrecoverable_cases={len(bad)} flagged={len(bad) - len(silent)} silent={silent or 'none'} "
          f"slip_false_alarms={false_alarm or 'none'}")
    ok = wins >= 1 and not silent and not false_alarm
    print(f"  shockdaq_demo={'OK' if ok else 'WEAK'}")
    return 0 if ok else 1


def cmd_shockdaq_failmap(args: argparse.Namespace) -> int:
    """Where blind fold recovery breaks (peak V x ring Hz) and whether it flags itself."""
    cells, summ = run_failmap_report(lam=args.lam, sr=args.sr)
    print("ShockDAQ fail map — blind recovery vs ringing impact (peak V x ring Hz)")
    print(f"  λ={args.lam} V  sr={args.sr}  rule: max slew < λ·sr = {args.lam*args.sr:,.0f} V/s")
    print(format_failmap(cells))
    print(f"  summary={summ}")
    print("  artifacts → artifacts/shockdaq/failmap.json, failmap.svg")
    ok = summ["fails_silent"] == 0 and summ["slip_false_alarms_on_ok"] == 0
    print(f"  failmap={'OK (every failure flagged, no false alarms)' if ok else 'SILENT FAILS PRESENT'}")
    return 0 if ok else 1


def cmd_audio_demo(args: argparse.Namespace) -> int:
    """FoldAudio product trial: fold capture vs hard clip on synthetic WAVs."""
    rows = run_audio_demo(lam=args.lam, sr=args.sr)
    print("FoldAudio v0 — intentional fold vs hard clip")
    print(f"  λ={args.lam}  sr={args.sr}  engine=Itoh+central_modulo (WrapCancel family)")
    print(format_snr_table(rows))
    print("  artifacts → /workspace/foldcrypt/artifacts/foldaudio/")
    print("  testdata  → /workspace/foldcrypt/testdata/")
    # Soft gate: main trials (exclude deliberate harsh_kick fail) beat clip
    main = [r for r in rows if r.name != "harsh_kick"]
    wins = sum(1 for r in main if r.snr_gain_db > 3.0)
    fails = [r.name for r in rows if r.snr_gain_db <= 3.0]
    print(f"  main_trials_beating_clip(>3dB)={wins}/{len(main)}")
    if fails:
        print(f"  weak_or_fail_trials={fails}  (harsh_kick is intentional fail case)")
    print(f"  audio_demo={'OK' if wins >= 2 else 'WEAK'}")
    return 0 if wins >= 2 else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="foldcrypt", description="FoldCrypt — ShockDAQ company bet + FoldAudio proof + WrapCancel archive")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("demo", help="one-shot WrapCancel vs unfold")
    d.add_argument("--OF", type=int, default=4)
    d.add_argument("--ratio", type=float, default=3.0, help="λ/σ")
    d.add_argument("--Ns", type=int, default=2)
    d.add_argument("--bits", type=int, default=4)
    d.add_argument("--seed", type=int, default=0)
    d.set_defaults(func=cmd_demo)

    s = sub.add_parser("ser", help="synthetic SER table")
    s.add_argument("--Ns", type=int, default=2)
    s.add_argument("--bits", type=int, default=4)
    s.add_argument("--trials", type=int, default=60)
    s.add_argument("--seed", type=int, default=42)
    s.set_defaults(func=cmd_ser)

    dm = sub.add_parser("defect-demo", help="thin defect-mask stub")
    dm.set_defaults(func=cmd_defect_demo)

    bd = sub.add_parser("block-demo", help="Alg. 1 block detect for long Ns")
    bd.add_argument("--OF", type=int, default=16)
    bd.add_argument("--ratio", type=float, default=3.0, help="λ/σ")
    bd.add_argument("--Ns", type=int, default=16)
    bd.add_argument("--bits", type=int, default=4)
    bd.add_argument("--Nb", type=int, default=4)
    bd.add_argument("--eta", type=int, default=2)
    bd.add_argument("--K", type=int, default=5)
    bd.add_argument("--edge-discard", type=int, default=1, dest="edge_discard")
    bd.add_argument("--seed", type=int, default=1)
    bd.set_defaults(func=cmd_block_demo)

    sh = sub.add_parser("shares-demo", help="recovery shares: split/corrupt/recover")
    sh.add_argument("--secret", default="backup-seed-demo")
    sh.add_argument("--passphrase", default="ashlynn-test-pass")
    sh.set_defaults(func=cmd_shares_demo)


    sd = sub.add_parser("shockdaq-demo", help="ShockDAQ: IEPE fold vs silent soft-clip (company bet)")
    sd.add_argument("--lam", type=float, default=DEFAULT_LAM_V, help="soft-sat rail λ in volts (default 5.0)")
    sd.add_argument("--sr", type=int, default=51200, help="sample rate (51.2 kHz-style default)")
    sd.set_defaults(func=cmd_shockdaq_demo)

    fm = sub.add_parser("shockdaq-failmap", help="ShockDAQ: map where fold recovery fails and whether it flags it")
    fm.add_argument("--lam", type=float, default=DEFAULT_LAM_V, help="soft-sat rail λ in volts (default 5.0)")
    fm.add_argument("--sr", type=int, default=51200, help="sample rate (51.2 kHz-style default)")
    fm.set_defaults(func=cmd_shockdaq_failmap)

    au = sub.add_parser("audio-demo", help="FoldAudio: fold vs hard-clip SNR on synthetic WAVs")
    au.add_argument("--lam", type=float, default=DEFAULT_LAM, help="fold threshold λ")
    au.add_argument("--sr", type=int, default=48000, help="sample rate for generated WAVs")
    au.set_defaults(func=cmd_audio_demo)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
