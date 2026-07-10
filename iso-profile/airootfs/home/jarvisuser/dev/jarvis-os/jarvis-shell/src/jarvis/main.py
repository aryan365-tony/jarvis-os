"""Entry point: ``python -m jarvis.main`` (and the ``jarvis`` console script).

This module existed nowhere before — the compositor launched
``python -m jarvis.main`` against a missing module, causing the kiosk to
crash-loop. It now builds the runtime and hands control to the Textual UI, which
appears immediately while services initialise in the background.
"""

from __future__ import annotations

import logging
import os

from .runtime import Runtime


def _configure_logging() -> None:
    # Logs go to journald via stderr (systemd captures them); the in-app status
    # panel gets its own event stream, so keep console logging terse.
    level = os.environ.get("JARVIS_LOG", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> int:
    _configure_logging()
    runtime = Runtime()
    # Imported here so a headless/CI import of the package doesn't require Textual.
    from .ui.app import JarvisApp

    app = JarvisApp(runtime)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
