"""Resolve the repo root containing the ``llama/`` directory.

Design note
-----------
readiness.py and optimize_backend.py each independently computed this path
via ``Path(__file__).parents[N]``, at two different, easy-to-miscount depths
(readiness.py is one directory shallower than tools/optimize_backend.py).
That divergence is exactly how optimize_backend.py's path ended up wrong
(BUG-011/RISK-010: verified broken even in the current dev layout, not just
theoretically fragile under a pip install). Centralising it here means the
depth is computed once, correctly, and an installed package (where the
parents-based guess cannot work at all — site-packages has no ``llama/``
sibling) can be pointed at the real location via ``JARVIS_REPO_ROOT``.
"""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    env = os.environ.get("JARVIS_REPO_ROOT")
    if env:
        return Path(env)
    # This file lives at <repo>/jarvis-shell/src/jarvis/paths.py.
    return Path(__file__).resolve().parents[3]


def llama_dir() -> Path:
    return repo_root() / "llama"
