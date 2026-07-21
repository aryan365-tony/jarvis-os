"""Entry point: ``python -m jarvis.main`` (and the ``jarvis`` console script).

Boots a QGuiApplication with a QML engine. The ``qasync`` event loop bridges
Qt's event loop with Python's asyncio so the existing async Runtime, EventBus,
ReadinessService, VoiceService, and ConversationAgent work without modification.

The QML UI appears immediately; backend services initialise in the background
(preserving the progressive-availability design).
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path


def _configure_logging() -> None:
    level = os.environ.get("JARVIS_LOG", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main() -> int:
    _configure_logging()
    log = logging.getLogger("jarvis.main")

    # Force Wayland when running under cage/seatd; fallback to xcb for dev.
    if "WAYLAND_DISPLAY" in os.environ:
        os.environ.setdefault("QT_QPA_PLATFORM", "wayland")

    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtQml import QQmlApplicationEngine
    from PyQt6.QtCore import QUrl

    app = QGuiApplication(sys.argv)
    app.setApplicationName("Jarvis")
    app.setOrganizationName("JarvisOS")

    # Set up the qasync event loop so asyncio works inside Qt.
    # If qasync is missing, keep the UI alive in degraded mode instead of
    # exiting to a blinking cursor.
    degraded_mode = False
    loop = None
    try:
        import qasync
        loop = qasync.QEventLoop(app)
        asyncio.set_event_loop(loop)
    except ModuleNotFoundError:
        degraded_mode = True
        asyncio.set_event_loop(asyncio.new_event_loop())
        log.error(
            "qasync not installed; starting in degraded UI-only mode "
            "(backend async services disabled)"
        )

    # Create the bridge (Python ↔ QML conduit).
    from .ui_bridge import JarvisBridge
    bridge = JarvisBridge()

    # Load the QML UI.
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("jarvis", bridge)

    qml_dir = Path(__file__).parent / "qml"
    engine.load(QUrl.fromLocalFile(str(qml_dir / "Main.qml")))

    if not engine.rootObjects():
        log.error("QML failed to load")
        return 1

    # Start backend services after QML is painted (unless degraded mode).
    # bridge.start() creates asyncio tasks (readiness/voice pollers) via
    # asyncio.create_task(), which requires a *running* event loop. Setting the
    # loop with set_event_loop() is not sufficient: create_task() calls
    # get_running_loop() and raises "RuntimeError: no running event loop" when
    # invoked before loop.run_forever(). Scheduling it with call_soon() makes it
    # fire the instant the qasync loop starts, when a running loop exists.
    if not degraded_mode:
        loop.call_soon(bridge.start)

    # Graceful shutdown on SIGTERM/SIGINT (systemd sends SIGTERM).
    def _shutdown_handler(*_):
        if loop is not None:
            loop.create_task(bridge.shutdown())
        app.quit()

    signal.signal(signal.SIGTERM, _shutdown_handler)
    signal.signal(signal.SIGINT, _shutdown_handler)

    if loop is None:
        app.exec()
    else:
        with loop:
            loop.run_forever()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
