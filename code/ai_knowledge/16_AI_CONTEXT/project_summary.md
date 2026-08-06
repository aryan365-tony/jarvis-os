# Project Summary (For LLM Context)

## What You Need to Know

You are contributing to **Jarvis-OS**, an Arch Linux-based operating system designed to run a local LLM agent in kiosk mode natively on the metal. 

If you are tasked with fixing a bug or building a feature, keep the following context in mind:
1. **No Desktop Environment**: There is no GNOME or KDE. The UI is a Python/Qt/QML application running natively on Wayland via `cage` (launched by `systemd/jarvis-shell.service`). Do not suggest traditional X11 tools or desktop-specific configurations.
2. **Offline-First Principle**: Avoid adding dependencies on cloud services or external package downloads that run on first boot. The ISO (`mkarchiso`) must bake everything in (via `setup.sh`).
3. **Graphify Integration**: You must rely on `graphify` (the local knowledge graph) for discovering functions, files, and relationships. If you need to know how a module works internally, run `graphify query "module name"`.
4. **Sandboxed LLM**: The shell (and by extension the LLM agent) runs as `jarvisuser` under strict systemd protections (`ProtectSystem=strict`, `ProtectHome=read-only`). The LLM cannot mutate the OS directly except through explicitly defined tool wrappers (like `jarvis-fsop`). Do not widen root permissions without user consent.
5. **Config & States**: Global configuration is handled via `jarvis.toml`, typically loaded via `jarvis-shell/src/jarvis/config.py`.

## Boot Flow Reference
`Firmware` -> `GRUB/Systemd-boot` -> `Linux Kernel` -> `systemd` -> `jarvis-live-prompt.service` (if live ISO) -> `jarvis-shell.service` -> `cage` -> `jarvis-shell UI` -> `ReadinessService (starts llama.cpp)`.

## Where things live
- `jarvis-shell/`: The main Python application (UI, LLM client, orchestration).
- `llama/`: The backend inference engine (`llama.cpp` scripts and models).
- `iso-profile/`: Archiso configuration for building the actual `.iso` image.
- `ops/`: Administrative and CLI scripts (e.g., `live-llm-prompt.sh`, `set-llm-mode.sh`).
- `systemd/`: The systemd unit files governing the OS lifecycle.
