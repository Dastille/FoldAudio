"""FoldCrypt — FoldAudio product trial + archived research toys.

Product trial: FoldAudio — intentional modulo fold beats hard clip on loud peaks.
Engine: central modulo + Itoh unwrap (WrapCancel family).
Parked: recovery-shares seed/backup (Sigil constellation overlaps).
Archived: WrapCancel symbol-detect SER toys.
"""

__version__ = "0.1.0"

from .foldaudio import (
    DEFAULT_LAM,
    fold_capture,
    hard_clip,
    recover_itoh,
    run_audio_demo,
    snr_db,
)

__all__ = [
    "DEFAULT_LAM",
    "fold_capture",
    "hard_clip",
    "recover_itoh",
    "run_audio_demo",
    "snr_db",
    "__version__",
]
