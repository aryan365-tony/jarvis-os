"""Jarvis-OS shell package.

The shell is an AI-first, voice-first kiosk interface built with PyQt6 and QML.
Its guiding principle is *progressive availability*: the UI must appear and
accept input immediately, then gain capabilities (model, voice, memory) as
background services come online. Nothing in the interface may block on a backend
being ready.

The ``qml/`` directory contains the declarative UI components. The Python
backend (agent, eventbus, runtime, memory, tools) is connected to QML via
``ui_bridge.py`` which exposes signals and properties.
"""

__version__ = "0.3.0"
