"""Recovery shares — FoldCrypt product lane (2026-10-02 pivot).

Plain story: split a short secret into N shares (phones / USBs / paper).
Recover if ≤t shares are bit-flipped or one share is missing. Wrong
passphrase → fail closed.

Code: Hamming [7, 4, 3] over GF(2). Params named in ShareParams below.
Builds on foldcrypt.defect_mask (same encoder / syndrome table).

Assumptions (read these):
1. Passphrase → 32-byte key via PBKDF2-HMAC-SHA256 (stdlib hashlib only).
   Default iterations=100_000; salt stored with the share bundle.
2. Secret is XOR-masked with a SHA256 keystream so a wrong passphrase
   does not yield the plaintext even if someone skips the tag check.
3. Integrity tag = SHA256(key || secret)[:16 hex chars] — fail closed.
4. n=7 shares: share i holds bit i of every Hamming codeword.
   k=4 message bits per block; t=1 correctable error (or 1 erasure) per block.
5. NOT production crypto: no memory-hard KDF, no side-channel hardening,
   Hamming is tiny, no audited review. Lab / weekday toy only.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field

from .defect_mask import (
    _hamming74_decode,
    _hamming74_encode,
)


# --- named ECC params -------------------------------------------------

@dataclass(frozen=True)
class ShareParams:
    """Hamming binary code parameters used for every block."""

    n: int = 7  # share count (= codeword length)
    k: int = 4  # message bits per block
    t: int = 1  # correctable bit errors — or 1 erasure — per block
    code: str = "Hamming[7,4,3]"


PARAMS = ShareParams()

_DEFAULT_PBKDF2_ITERS = 100_000
_TAG_HEX_LEN = 16  # 8 bytes of SHA-256, hex-encoded


@dataclass
class Share:
    """One physical share: index in 0..n-1 and one bit per codeword block."""

    index: int
    bits: list[int]  # length = number of Hamming blocks


@dataclass
class ShareBundle:
    """All N shares plus salt + tag needed to recover."""

    salt: bytes
    tag: str
    shares: list[Share]
    secret_bit_len: int  # original secret length in bits (no pad)
    pbkdf2_iterations: int = _DEFAULT_PBKDF2_ITERS
    params: ShareParams = field(default_factory=ShareParams)

    @property
    def n_blocks(self) -> int:
        return len(self.shares[0].bits) if self.shares else 0


# --- passphrase → key -------------------------------------------------

def derive_key(
    passphrase: str,
    salt: bytes,
    iterations: int = _DEFAULT_PBKDF2_ITERS,
    dklen: int = 32,
) -> bytes:
    """PBKDF2-HMAC-SHA256. Assumption: passphrase is str (UTF-8)."""
    if not isinstance(passphrase, str):
        raise TypeError("passphrase must be str")
    if len(salt) < 8:
        raise ValueError("salt must be at least 8 bytes")
    return hashlib.pbkdf2_hmac(
        "sha256",
        passphrase.encode("utf-8"),
        salt,
        iterations,
        dklen=dklen,
    )


def _integrity_tag(key: bytes, secret: bytes) -> str:
    return hashlib.sha256(key + secret).hexdigest()[:_TAG_HEX_LEN]


def _keystream(key: bytes, n_bytes: int) -> bytes:
    """SHA-256 counter mode keystream (toy — not AES-CTR)."""
    out = bytearray()
    counter = 0
    while len(out) < n_bytes:
        block = hashlib.sha256(key + b"ks" + counter.to_bytes(4, "big")).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:n_bytes])


def _xor_bytes(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b, strict=True))


# --- bit packing ------------------------------------------------------

def _bytes_to_bits(data: bytes) -> list[int]:
    bits: list[int] = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return bits


def _bits_to_bytes(bits: list[int], bit_len: int) -> bytes:
    """Pack bits back to bytes; use only the first bit_len bits."""
    use = bits[:bit_len]
    # pad to full bytes for packing
    pad = (-len(use)) % 8
    use = use + [0] * pad
    out = bytearray()
    for i in range(0, len(use), 8):
        byte = 0
        for b in use[i : i + 8]:
            byte = (byte << 1) | b
        out.append(byte)
    n_bytes = (bit_len + 7) // 8
    return bytes(out[:n_bytes])


def _pad_msg_bits(bits: list[int], k: int = 4) -> list[int]:
    pad = (-len(bits)) % k
    return bits + [0] * pad


# --- erasure-aware Hamming decode -------------------------------------

def _syndrome_bits(r: list[int]) -> tuple[int, int, int]:
    u0, u1, u2, u3, p0, p1, p2 = r
    s0 = (u0 + u1 + u3 + p0) % 2
    s1 = (u0 + u2 + u3 + p1) % 2
    s2 = (u1 + u2 + u3 + p2) % 2
    return s0, s1, s2


# Map codeword index 0..6 → expected syndrome for a single flip there.
_INDEX_TO_SYNDROME: dict[int, tuple[int, int, int]] = {
    0: (1, 1, 0),  # u0
    1: (1, 0, 1),  # u1
    2: (0, 1, 1),  # u2
    3: (1, 1, 1),  # u3
    4: (1, 0, 0),  # p0
    5: (0, 1, 0),  # p1
    6: (0, 0, 1),  # p2
}


def _hamming74_decode_erasure(r: list[int | None]) -> list[int]:
    """Decode one codeword with at most one erasure (None) and ≤t errors total.

    - 0 erasures: standard syndrome decode (≤1 flip).
    - 1 erasure: fill so syndrome is consistent with that position (or clean).
    - >1 erasure: reject.
    """
    if len(r) != 7:
        raise ValueError("codeword length must be 7")
    erasures = [i for i, b in enumerate(r) if b is None]
    if len(erasures) > 1:
        raise ValueError("too many erasures (>t) for Hamming[7,4,3]")
    if not erasures:
        bits = [int(b) for b in r]
        # still allow ≤1 flip via normal decode; caller verifies tag
        return _hamming74_decode(bits)

    e = erasures[0]
    # Try bit=0 at erasure; read syndrome.
    trial = [0 if b is None else int(b) for b in r]
    syn = _syndrome_bits(trial)
    expected = _INDEX_TO_SYNDROME[e]
    if syn == (0, 0, 0):
        # erasure was 0 and no other errors
        filled = trial
    elif syn == expected:
        # erasure should be 1 (single-error syndrome points at e when we put 0)
        filled = list(trial)
        filled[e] = 1
    else:
        # Extra error beyond the erasure — cannot correct with t=1.
        raise ValueError("uncorrectable: erasure plus additional error")
    return filled[:4]


# --- split / recover --------------------------------------------------

def split_secret(
    secret: bytes,
    passphrase: str,
    *,
    salt: bytes | None = None,
    iterations: int = _DEFAULT_PBKDF2_ITERS,
) -> ShareBundle:
    """Encode secret → N=7 shares. Passphrase binds the integrity tag + mask."""
    if not secret:
        raise ValueError("secret must be non-empty")
    if salt is None:
        salt = os.urandom(16)
    key = derive_key(passphrase, salt, iterations=iterations)
    tag = _integrity_tag(key, secret)

    masked = _xor_bytes(secret, _keystream(key, len(secret)))
    msg_bits = _pad_msg_bits(_bytes_to_bits(masked), PARAMS.k)
    n_blocks = len(msg_bits) // PARAMS.k

    # shares[i].bits[b] = bit i of codeword for block b
    share_bits: list[list[int]] = [[] for _ in range(PARAMS.n)]
    for b in range(n_blocks):
        block = msg_bits[b * PARAMS.k : (b + 1) * PARAMS.k]
        cw = _hamming74_encode(block)
        for i in range(PARAMS.n):
            share_bits[i].append(cw[i])

    shares = [Share(index=i, bits=share_bits[i]) for i in range(PARAMS.n)]
    return ShareBundle(
        salt=salt,
        tag=tag,
        shares=shares,
        secret_bit_len=len(secret) * 8,
        pbkdf2_iterations=iterations,
        params=PARAMS,
    )


def recover_secret(
    bundle: ShareBundle,
    passphrase: str,
    shares: list[Share | None] | None = None,
) -> bytes:
    """Reassemble from shares (None = missing). Wrong passphrase → ValueError.

    Accepts ≤t=1 missing share (erasure) or ≤t bit-flips per codeword block
    across the present shares. Combinations that exceed Hamming capability
    fail closed (decode error or tag mismatch).
    """
    if shares is None:
        shares = list(bundle.shares)
    if len(shares) != PARAMS.n:
        raise ValueError(f"need {PARAMS.n} share slots (use None for missing)")

    present = [s for s in shares if s is not None]
    if len(present) < PARAMS.n - PARAMS.t:
        raise ValueError(
            f"too many missing shares: need ≥{PARAMS.n - PARAMS.t}, got {len(present)}"
        )

    n_blocks = bundle.n_blocks
    for s in present:
        if len(s.bits) != n_blocks:
            raise ValueError("share block count mismatch")
        if not (0 <= s.index < PARAMS.n):
            raise ValueError("share index out of range")

    # Build codeword per block: None where that share is missing.
    by_index: dict[int, Share] = {s.index: s for s in present}
    msg_bits: list[int] = []
    for b in range(n_blocks):
        cw: list[int | None] = []
        for i in range(PARAMS.n):
            if i in by_index:
                cw.append(by_index[i].bits[b])
            else:
                cw.append(None)
        try:
            msg4 = _hamming74_decode_erasure(cw)
        except ValueError as exc:
            raise ValueError(
                f"recover failed at block {b}: {exc}"
            ) from exc
        msg_bits.extend(msg4)

    key = derive_key(
        passphrase, bundle.salt, iterations=bundle.pbkdf2_iterations
    )
    masked = _bits_to_bytes(msg_bits, bundle.secret_bit_len)
    secret = _xor_bytes(masked, _keystream(key, len(masked)))

    if _integrity_tag(key, secret) != bundle.tag:
        raise ValueError(
            "integrity tag rejected (wrong passphrase or uncorrectable damage)"
        )
    return secret


def corrupt_share(share: Share, block_indices: list[int]) -> Share:
    """Flip listed block bits on a copy of the share (demo / tests)."""
    bits = list(share.bits)
    for b in block_indices:
        bits[b] ^= 1
    return Share(index=share.index, bits=bits)

