"""FoldCrypt — ShockDAQ company bet + FoldAudio public proof + archived toys.

Company bet: ShockDAQ — fold inside IEPE/vibration DAQ front-ends.
Public proof: FoldAudio — intentional modulo fold beats hard clip on loud peaks.
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
from .shockdaq import DEFAULT_LAM_V, run_shockdaq_demo

__all__ = [
    "DEFAULT_LAM",
    "DEFAULT_LAM_V",
    "fold_capture",
    "hard_clip",
    "recover_itoh",
    "run_audio_demo",
    "run_shockdaq_demo",
    "snr_db",
    "__version__",
]
