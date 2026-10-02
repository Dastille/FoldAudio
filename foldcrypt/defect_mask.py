"""Thin defect-mask stub (SECONDARY — not the v0 lead).

Digital sketch of defect-subtraction DNA-origami crypto ideas
(Jiang et al. Small 2024; Wisna et al. Nat. Commun. 2025). Chem yield /
folding-path key lengths from those papers are **context only** — this stub
does not claim to match wet-lab numbers.

v0 status: stub API + Hamming-[7,4,3] round-trip so imports/tests stay green.
Full PinSketch / structure-hash gate / PRF site-permutation → see NOTES.md.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


# --- tiny binary Hamming [7,4,3], t=1 ---------------------------------
# Generator G (systematic): columns for u0..u3 then p0..p2
# Parity: p0=u0+u1+u3, p1=u0+u2+u3, p2=u1+u2+u3  (mod 2)

_G_PARITY = [
    (0, 1, 3),  # p0
    (0, 2, 3),  # p1
    (1, 2, 3),  # p2
]


def _hamming74_encode(msg4: list[int]) -> list[int]:
    if len(msg4) != 4 or any(b not in (0, 1) for b in msg4):
        raise ValueError("need 4 bits")
    p = [sum(msg4[i] for i in idxs) % 2 for idxs in _G_PARITY]
    return list(msg4) + p  # length 7 codeword = defect mask bits


def _hamming74_syndrome(r: list[int]) -> int:
    """Return error position 1..7 (0 = no error). Positions use 1-based Hamming numbering."""
    # Bits arranged as positions 1..7 in Hamming order is awkward with systematic
    # form; use parity-check on our layout [u0 u1 u2 u3 p0 p1 p2].
    # H rows check (p0), (p1), (p2) consistency.
    u0, u1, u2, u3, p0, p1, p2 = r
    s0 = (u0 + u1 + u3 + p0) % 2
    s1 = (u0 + u2 + u3 + p1) % 2
    s2 = (u1 + u2 + u3 + p2) % 2
    # Map syndrome bits to which of the 7 positions flipped (0 = none)
    table = {
        (0, 0, 0): 0,
        (1, 1, 0): 1,  # u0
        (1, 0, 1): 2,  # u1
        (0, 1, 1): 3,  # u2
        (1, 1, 1): 4,  # u3
        (1, 0, 0): 5,  # p0
        (0, 1, 0): 6,  # p1
        (0, 0, 1): 7,  # p2
    }
    return table[(s0, s1, s2)]


def _hamming74_decode(r: list[int]) -> list[int]:
    pos = _hamming74_syndrome(r)
    fixed = list(r)
    if pos:
        fixed[pos - 1] ^= 1
    return fixed[:4]


@dataclass
class DefectCiphertext:
    mask: list[int]  # length n=7 defect bits
    tag: str  # hex structure-hash gate
    n: int = 7
    k: int = 4
    t: int = 1


def structure_hash(key: bytes, message_bits: list[int]) -> str:
    """H(K, m) — gate recovery; wrong key ⇒ fail closed."""
    payload = key + bytes(message_bits)
    return hashlib.sha256(payload).hexdigest()[:16]


def defect_encrypt(message_bits: list[int], key: bytes) -> DefectCiphertext:
    """Encode 4 bits → weight-related defect mask + structure-hash tag."""
    cw = _hamming74_encode(message_bits)
    tag = structure_hash(key, message_bits)
    return DefectCiphertext(mask=cw, tag=tag)


def defect_decrypt(
    ct: DefectCiphertext,
    key: bytes,
    noisy_mask: list[int] | None = None,
) -> list[int]:
    """Syndrome-decode ≤t flips; reject if structure hash mismatches."""
    mask = noisy_mask if noisy_mask is not None else ct.mask
    if len(mask) != 7:
        raise ValueError("mask length must be 7")
    msg = _hamming74_decode(mask)
    if structure_hash(key, msg) != ct.tag:
        raise ValueError("structure-hash gate rejected (wrong key or >t errors)")
    return msg


def flip_bits(mask: list[int], positions: list[int]) -> list[int]:
    out = list(mask)
    for p in positions:
        out[p] ^= 1
    return out
