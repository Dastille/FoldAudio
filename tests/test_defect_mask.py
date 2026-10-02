"""Defect-mask stub tests."""

from __future__ import annotations

import pytest

from foldcrypt.defect_mask import (
    defect_decrypt,
    defect_encrypt,
    flip_bits,
)


KEY = b"test-structure-salt"


def test_roundtrip_clean():
    msg = [1, 0, 1, 0]
    ct = defect_encrypt(msg, KEY)
    assert defect_decrypt(ct, KEY) == msg


def test_roundtrip_with_t_noise():
    msg = [0, 1, 1, 1]
    ct = defect_encrypt(msg, KEY)
    noisy = flip_bits(ct.mask, [4])  # one parity flip, t=1
    assert defect_decrypt(ct, KEY, noisy) == msg


def test_fail_on_wrong_key():
    msg = [1, 1, 0, 0]
    ct = defect_encrypt(msg, KEY)
    with pytest.raises(ValueError, match="structure-hash"):
        defect_decrypt(ct, b"other-key")


def test_fail_on_over_t_errors():
    """Two flips can decode to wrong message → hash gate rejects."""
    msg = [1, 0, 0, 1]
    ct = defect_encrypt(msg, KEY)
    noisy = flip_bits(ct.mask, [0, 1])  # 2 flips > t=1
    with pytest.raises(ValueError, match="structure-hash"):
        defect_decrypt(ct, KEY, noisy)


def test_deterministic_encrypt():
    msg = [0, 0, 1, 1]
    ct1 = defect_encrypt(msg, KEY)
    ct2 = defect_encrypt(msg, KEY)
    assert ct1.mask == ct2.mask
    assert ct1.tag == ct2.tag
