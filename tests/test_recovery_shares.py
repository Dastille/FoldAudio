"""Recovery-shares product tests (Hamming [7,4,3], n=7 k=4 t=1)."""

from __future__ import annotations

import pytest

from foldcrypt.recovery_shares import (
    PARAMS,
    Share,
    corrupt_share,
    derive_key,
    recover_secret,
    split_secret,
)


PASS = "correct horse battery"
SECRET = b"seed-demo-32bytes-not-prod!!!!!!!!"[:32]  # 32 bytes


def test_params_named():
    assert PARAMS.n == 7
    assert PARAMS.k == 4
    assert PARAMS.t == 1


def test_roundtrip_all_shares():
    bundle = split_secret(SECRET, PASS, salt=b"0123456789abcdef")
    got = recover_secret(bundle, PASS)
    assert got == SECRET


def test_recover_with_one_bitflip_share():
    """Flip every block bit on one share (= 1 flip per codeword) → still OK."""
    bundle = split_secret(SECRET, PASS, salt=b"0123456789abcdef")
    shares = list(bundle.shares)
    shares[3] = corrupt_share(shares[3], list(range(bundle.n_blocks)))
    got = recover_secret(bundle, PASS, shares)
    assert got == SECRET


def test_recover_with_one_missing_share():
    bundle = split_secret(SECRET, PASS, salt=b"fedcba9876543210")
    shares: list[Share | None] = list(bundle.shares)
    shares[5] = None
    got = recover_secret(bundle, PASS, shares)
    assert got == SECRET


def test_fail_closed_wrong_passphrase():
    bundle = split_secret(SECRET, PASS, salt=b"0123456789abcdef")
    with pytest.raises(ValueError, match="integrity tag|wrong passphrase"):
        recover_secret(bundle, "wrong passphrase")


def test_fail_two_missing_shares():
    bundle = split_secret(SECRET, PASS, salt=b"0123456789abcdef")
    shares: list[Share | None] = list(bundle.shares)
    shares[1] = None
    shares[2] = None
    with pytest.raises(ValueError, match="too many missing"):
        recover_secret(bundle, PASS, shares)


def test_fail_two_fully_corrupted_shares():
    """Two fully flipped shares ⇒ 2 errors/block ⇒ uncorrectable or tag fail."""
    bundle = split_secret(SECRET, PASS, salt=b"0123456789abcdef")
    shares = list(bundle.shares)
    blocks = list(range(bundle.n_blocks))
    shares[0] = corrupt_share(shares[0], blocks)
    shares[1] = corrupt_share(shares[1], blocks)
    with pytest.raises(ValueError):
        recover_secret(bundle, PASS, shares)


def test_derive_key_deterministic():
    salt = b"0123456789abcdef"
    assert derive_key(PASS, salt, iterations=1000) == derive_key(
        PASS, salt, iterations=1000
    )
    assert derive_key(PASS, salt, iterations=1000) != derive_key(
        "other", salt, iterations=1000
    )


def test_short_secret():
    secret = b"hi"
    bundle = split_secret(secret, PASS, salt=b"0123456789abcdef")
    assert recover_secret(bundle, PASS) == secret
