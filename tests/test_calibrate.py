import numpy as np

from foldcrypt import blind_level as bl
from foldcrypt import calibrate as cal
from foldcrypt import failmap as fm

LAM = 5.0
SR = 51200
AMPS = (8.0, 14.0, 20.0)
FREQS = (500.0, 1000.0, 2000.0)


def _tone_fold(g=0.0, inl=0.0, bits=None, snr=60.0, seed=1):
    x = cal.cal_tone(LAM, SR, noise_snr_db=snr, seed=seed)
    return fm.nonideal_fold(x, LAM, fm.NonIdeal(gain_err=g, inl=inl, bits=bits))


def test_gain_estimate_meets_target_at_60db_all_signs_and_depths():
    for g in (-0.05, -0.01, 0.001, 0.01, 0.05):
        for bits in (None, 16, 12):
            c = cal.estimate_front_end(_tone_fold(g, bits=bits), LAM, sr=SR, bits=bits)
            assert abs(c.g_hat - g) <= cal.CAL_TARGET_ABS_ERR, (g, bits, c)
            assert c.wraps > 100


def test_inl_terms_stop_inl_leaking_into_gain():
    y = _tone_fold(inl=0.05)
    with_inl = cal.estimate_front_end(y, LAM, sr=SR)
    without = cal.estimate_front_end(y, LAM, sr=SR, inl_harmonics=0)
    assert abs(without.g_hat) > 0.02  # the bias we found
    assert abs(with_inl.g_hat) < 1e-3
    assert abs(with_inl.inl_coefs[0] / LAM - 0.05) < 2e-3


def test_noisy_cal_tone_is_reported_as_missing_target():
    rows = cal.run_cal_snr_limit(
        snrs=(60.0, 20.0), gains=(0.01,), bits=(None,), seeds=(1,)
    )
    assert rows[0]["meets_target"] and not rows[1]["meets_target"]


def test_fold_gain_zero_is_identical_to_uncalibrated():
    x = fm.ring_burst(SR, amp=14.0, f_ring=1000.0, lam=LAM)
    y = fm.nonideal_fold(x, LAM, fm.NonIdeal(gain_err=0.01))
    a, ka = bl.recover_blind(y, LAM, prior="quiet_window")
    b, kb = bl.recover_blind(y, LAM, prior="quiet_window", fold_gain=0.0)
    assert ka == kb and np.array_equal(a, b)


def test_calibration_fixes_negative_gain_and_inl_and_leaves_nothing_invisible():
    cfgs = [
        fm.NonIdeal("gain -1.0%", gain_err=-0.01),
        fm.NonIdeal("inl 5%", inl=0.05),
        fm.NonIdeal("gain +5.0%", gain_err=0.05),
    ]
    sw = cal.run_calibration_sweep(cfgs, AMPS, FREQS, seeds=(7,), lam=LAM, sr=SR)
    by = {r["config"]: r for r in sw["rows"]}
    for name in ("gain -1.0%", "inl 5%"):
        assert by[name]["accurate_after"] > by[name]["accurate_before"]
        assert by[name]["silent_inaccurate_after"] == 0
    for r in sw["rows"]:
        assert (
            r["invisible_inaccurate_after"] == 0
        )  # anything still off shows rail-clipped samples
        assert r["fails_silent_after"] == 0 and r["slip_false_alarms_after"] == 0
    assert "inl 5%" in cal.format_calibration(sw)


def test_inl_inverse_undoes_bow_to_first_order():
    y = np.linspace(-LAM, LAM - 1e-6, 1001)
    bowed = y + 0.01 * LAM * np.sin(np.pi * y / LAM)
    back = bl.inl_inverse(bowed, LAM, (0.01 * LAM,))
    assert np.max(np.abs(back - y)) < 0.01 * LAM * 0.05
