"""FS-1: hybrid QTT structure + coded residual vs a fair quantized baseline.

Pre-registered in ``docs/folding-math-scout.md`` §4 and
``artifacts/folding-scout/prereg-2026-11-04-fs1.md``. This module holds the
encoder and decoder for both streams. Every byte count it reports is the
length of a stream that :func:`decode` turns back into samples, so headers
cannot be left out by accident.

Nothing here is cryptography; "folding" means reshaping a length-2^d signal
into a 2×2×…×2 tensor (quantized tensor train, QTT; Khoromskij 2011,
Oseledets 2011).
"""

from __future__ import annotations

import bz2
import gzip
import lzma
import struct
from dataclasses import dataclass

import numpy as np

try:  # zstd is required by the prereg; import lazily so the package still imports
    import zstandard as _zstd
except ImportError:  # pragma: no cover - depends on environment
    _zstd = None

#: coder ids stored in streams
CODERS = ("zstd22", "xz9e", "gzip9", "bz2_9")
#: integer transforms stored in streams
TRANSFORMS = ("raw", "diff1", "lpc2")
NO_PREDICTOR = ("raw", "diff1")
WIDTHS = (1, 2, 4)
LPC_SHIFT = 14
MAGIC_BASE = b"FS1B"
MAGIC_HYB = b"FS1H"
_HEAD = struct.Struct("<4sIdd")  # magic, n, mean, q


def zstd_version() -> str:
    """Version string of the zstd binding and library, or ``missing``."""
    if _zstd is None:
        return "missing"
    return f"zstandard {_zstd.__version__}, libzstd {'.'.join(map(str, _zstd.ZSTD_VERSION))}"


def _compress(coder: int, data: bytes) -> bytes:
    name = CODERS[coder]
    if name == "zstd22":
        if _zstd is None:
            raise ImportError("FS-1 needs zstd: pip install zstandard")
        return _zstd.ZstdCompressor(level=22).compress(data)
    if name == "xz9e":
        return lzma.compress(data, preset=9 | lzma.PRESET_EXTREME)
    if name == "gzip9":
        return gzip.compress(data, 9, mtime=0)
    return bz2.compress(data, 9)


def _decompress(coder: int, data: bytes) -> bytes:
    name = CODERS[coder]
    if name == "zstd22":
        if _zstd is None:
            raise ImportError("FS-1 needs zstd: pip install zstandard")
        return _zstd.ZstdDecompressor().decompress(data)
    if name == "xz9e":
        return lzma.decompress(data)
    if name == "gzip9":
        return gzip.decompress(data)
    return bz2.decompress(data)


def best_blob(data: bytes) -> bytes:
    """Smallest of the four coders: 1 coder byte + payload."""
    outs = [bytes([c]) + _compress(c, data) for c in range(len(CODERS))]
    return min(outs, key=len)


def unblob(blob: bytes) -> bytes:
    """Inverse of :func:`best_blob`."""
    return _decompress(blob[0], blob[1:])


def _lpc2_coefs(k: np.ndarray) -> tuple[int, int]:
    if k.size < 4:
        return 0, 0
    a = np.stack([k[1:-1], k[:-2]], axis=1).astype(float)
    b = k[2:].astype(float)
    sol, *_ = np.linalg.lstsq(a, b, rcond=None)
    lim = 2**31 - 1
    a1, a2 = (int(np.clip(np.round(c * (1 << LPC_SHIFT)), -lim, lim)) for c in sol)
    return a1, a2


def _lpc2_pred(prev1: np.ndarray, prev2: np.ndarray, a1: int, a2: int) -> np.ndarray:
    acc = a1 * prev1 + a2 * prev2 + (1 << (LPC_SHIFT - 1))
    return acc >> LPC_SHIFT


def _transform(k: np.ndarray, t: str) -> tuple[np.ndarray, bytes]:
    if t == "raw":
        return k, b""
    if t == "diff1":
        return np.diff(k, prepend=0), b""
    a1, a2 = _lpc2_coefs(k)
    e = k.copy()
    if k.size > 2:
        e[2:] = k[2:] - _lpc2_pred(k[1:-1], k[:-2], a1, a2)
    return e, struct.pack("<ii", a1, a2)


def _untransform(e: np.ndarray, t: str, extra: bytes) -> np.ndarray:
    if t == "raw":
        return e
    if t == "diff1":
        return np.cumsum(e)
    a1, a2 = struct.unpack("<ii", extra)
    k = [int(v) for v in e[:2]]
    sh, rnd = LPC_SHIFT, 1 << (LPC_SHIFT - 1)
    for i in range(2, e.size):
        k.append(int(e[i]) + ((a1 * k[-1] + a2 * k[-2] + rnd) >> sh))
    return np.asarray(k, dtype=np.int64)


def _width(e: np.ndarray) -> int:
    lo, hi = (int(e.min()), int(e.max())) if e.size else (0, 0)
    for w in WIDTHS:
        if -(2 ** (8 * w - 1)) <= lo and hi < 2 ** (8 * w - 1):
            return w
    raise OverflowError("integer stream does not fit in int32")


def encode_ints(k: np.ndarray, transforms: tuple[str, ...] = TRANSFORMS) -> bytes:
    """Smallest integer stream over ``transforms`` × widths × coders.

    Layout: transform id, width, coder id (3 bytes), 8 LPC bytes if
    ``lpc2``, then the compressed payload."""
    k = np.asarray(k, dtype=np.int64)
    best: bytes | None = None
    for t in transforms:
        e, extra = _transform(k, t)
        w = _width(e)
        raw = e.astype(f"<i{w}").tobytes()
        blob = best_blob(raw)
        out = bytes([TRANSFORMS.index(t), w, blob[0]]) + extra + blob[1:]
        if best is None or len(out) < len(best):
            best = out
    if best is None:
        raise ValueError("no transform given")
    return best


def decode_ints(blob: bytes, n: int) -> np.ndarray:
    """Inverse of :func:`encode_ints` for a stream of ``n`` integers."""
    t, w, c = TRANSFORMS[blob[0]], blob[1], blob[2]
    off = 3 + (8 if t == "lpc2" else 0)
    extra = blob[3:off]
    e = np.frombuffer(_decompress(c, blob[off:]), dtype=f"<i{w}").astype(np.int64)
    if e.size != n:
        raise ValueError(f"integer stream has {e.size} values, expected {n}")
    return _untransform(e, t, extra)


def int_stream_choice(blob: bytes) -> str:
    """Human-readable choice of an integer stream, e.g. ``lpc2/i2/xz9e``."""
    return f"{TRANSFORMS[blob[0]]}/i{blob[1]}/{CODERS[blob[2]]}"


def rel_err(x: np.ndarray, y: np.ndarray) -> float:
    """``‖x − y‖ / ‖x − mean(x)‖``."""
    den = float(np.linalg.norm(x - x.mean()))
    return float(np.linalg.norm(x - y)) / den if den > 0 else float("inf")


def bisect_step(
    target_rel: float, tol: float, err_of_q, scale: float, steps: int = 80
) -> float | None:
    """Bisect log q until ``err_of_q(q)`` is within ``target·(1 ± tol)``.

    Returns ``None`` if no step inside the window is found."""
    lo, hi = np.log(scale * 1e-9), np.log(scale * 10.0)
    for _ in range(steps):
        mid = 0.5 * (lo + hi)
        e = err_of_q(float(np.exp(mid)))
        if abs(e - target_rel) <= tol * target_rel:
            return float(np.exp(mid))
        if e < target_rel:
            lo = mid
        else:
            hi = mid
    return None


# --- QTT ------------------------------------------------------------------


def tt_svd_rank(v: np.ndarray, d: int, max_rank: int) -> list[np.ndarray]:
    """TT-SVD (Oseledets 2011, Alg. 1) of ``v`` reshaped to ``(2,)*d``,
    truncated only by ``max_rank``."""
    if v.size != 2**d:
        raise ValueError(f"need 2**{d} samples, got {v.size}")
    cores, r, c = [], 1, np.asarray(v, dtype=float).reshape(-1)
    for _ in range(d - 1):
        c = c.reshape(r * 2, -1)
        u, s, vt = np.linalg.svd(c, full_matrices=False)
        keep = max(1, min(max_rank, int(np.sum(s > 0))))
        cores.append(u[:, :keep].reshape(r, 2, keep))
        c = s[:keep, None] * vt[:keep]
        r = keep
    cores.append(c.reshape(r, 2, 1))
    return cores


def tt_full(cores: list[np.ndarray]) -> np.ndarray:
    """Contract TT cores back to a vector."""
    out = np.asarray(cores[0], dtype=float).reshape(2, -1)
    for g in cores[1:]:
        r = g.shape[0]
        out = (out.reshape(-1, r) @ np.asarray(g, dtype=float).reshape(r, -1)).reshape(
            -1
        )
    return out.reshape(-1)


# --- streams --------------------------------------------------------------


@dataclass
class Encoded:
    """One encoded stream plus what the encoder chose."""

    stream: bytes
    rel: float
    max_abs: float
    choice: str

    @property
    def nbytes(self) -> int:
        """Total stream length in bytes (everything the decoder reads)."""
        return len(self.stream)


def encode_baseline(
    x: np.ndarray,
    eps: float,
    tol: float = 0.01,
    transforms: tuple[str, ...] = TRANSFORMS,
    q: float | None = None,
) -> Encoded | None:
    """Uniform quantizer at relative error ``eps ± tol`` + best integer coder.

    Pass ``q`` to reuse a step already found (e.g. for the no-predictor
    variant at the same quantizer)."""
    x = np.asarray(x, dtype=float)
    m = float(x.mean())
    xc = x - m
    rms = float(np.sqrt(np.mean(xc**2)))
    if q is None:
        q = bisect_step(eps, tol, lambda s: rel_err(x, m + np.round(xc / s) * s), rms)
        if q is None:
            return None
    k = np.round(xc / q).astype(np.int64)
    ints = encode_ints(k, transforms)
    stream = _HEAD.pack(MAGIC_BASE, x.size, m, q) + ints
    y = decode(stream)
    return Encoded(
        stream, rel_err(x, y), float(np.max(np.abs(x - y))), int_stream_choice(ints)
    )


def _hyb_structure(xc: np.ndarray, d: int, r: int, prec: int):
    cores = [g.astype(f"<f{prec}") for g in tt_svd_rank(xc, d, r)]
    if not all(np.all(np.isfinite(g)) for g in cores):
        return None
    ranks = [g.shape[2] for g in cores[:-1]]
    s = tt_full([g.astype(float) for g in cores])
    blob = best_blob(b"".join(g.tobytes() for g in cores))
    return cores, ranks, s, blob


def encode_hybrid(
    x: np.ndarray,
    d: int,
    target_rel: float,
    ranks: tuple[int, ...] = (4, 8, 16),
    precs: tuple[int, ...] = (2, 4),
    tol: float = 0.02,
) -> Encoded | None:
    """Smallest hybrid stream over (max rank, core precision), residual
    quantizer bisected to ``target_rel ± tol``. ``None`` if no configuration
    reaches the window."""
    x = np.asarray(x, dtype=float)
    m = float(x.mean())
    xc = x - m
    best: Encoded | None = None
    for r in ranks:
        for p in precs:
            st = _hyb_structure(xc, d, r, p)
            if st is None:
                continue
            _cores, rk, s, cblob = st
            res = xc - s
            scale = float(np.sqrt(np.mean(xc**2)))
            q = bisect_step(
                target_rel,
                tol,
                lambda qq, s=s, res=res: rel_err(x, m + s + np.round(res / qq) * qq),
                scale,
            )
            if q is None:
                continue
            k = np.round(res / q).astype(np.int64)
            ints = encode_ints(k)
            stream = (
                _HEAD.pack(MAGIC_HYB, x.size, m, q)
                + bytes([d, p])
                + bytes(rk + [0] * (16 - len(rk)))
                + struct.pack("<I", len(cblob))
                + cblob
                + ints
            )
            y = decode(stream)
            enc = Encoded(
                stream,
                rel_err(x, y),
                float(np.max(np.abs(x - y))),
                f"R{r}/f{8 * p}/cores {CODERS[cblob[0]]} {len(cblob)} B/"
                f"max rank {max(rk)}/res {int_stream_choice(ints)}",
            )
            if best is None or enc.nbytes < best.nbytes:
                best = enc
    return best


def stream_step(stream: bytes) -> float:
    """Quantizer step q stored in a baseline or hybrid stream header."""
    return float(_HEAD.unpack_from(stream)[3])


def decode(stream: bytes) -> np.ndarray:
    """Decode a baseline or hybrid stream back to samples."""
    magic, n, m, q = _HEAD.unpack_from(stream)
    off = _HEAD.size
    if magic == MAGIC_BASE:
        return m + decode_ints(stream[off:], n) * q
    if magic != MAGIC_HYB:
        raise ValueError("not an FS-1 stream")
    d, p = stream[off], stream[off + 1]
    if d - 1 > 16:
        raise ValueError("rank header holds at most 16 bonds")
    rk = list(stream[off + 2 : off + 2 + 16])[: d - 1]
    off += 18
    (clen,) = struct.unpack_from("<I", stream, off)
    off += 4
    raw = np.frombuffer(unblob(stream[off : off + clen]), dtype=f"<f{p}")
    off += clen
    dims = [1] + rk + [1]
    cores, pos = [], 0
    for i in range(d):
        size = dims[i] * 2 * dims[i + 1]
        cores.append(raw[pos : pos + size].reshape(dims[i], 2, dims[i + 1]))
        pos += size
    if pos != raw.size:
        raise ValueError("core blob size does not match the rank header")
    s = tt_full([g.astype(float) for g in cores])
    return m + s + decode_ints(stream[off:], n) * q
