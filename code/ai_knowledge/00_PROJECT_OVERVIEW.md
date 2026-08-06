# Project Overview

## What is Jarvis-OS?
Jarvis-OS is a specialized, offline-first, voice-native operating system built on Arch Linux. Its primary purpose is to boot directly into a highly restricted, kiosk-like Wayland shell (powered by Cage) where a local AI (powered by `llama.cpp`) serves as an ever-present, system-level conversational agent.

Unlike traditional desktop operating systems, Jarvis-OS abandons the conventional desktop environment paradigm. The OS *is* the AI shell.

## Key Goals
1. **Offline-First AI**: Bundles `llama.cpp` and GGUF models directly onto the ISO, ensuring the AI can function without any internet connection out-of-the-box.
2. **Kiosk-Mode UX**: Uses `cage` to launch a single, immersive Qt/QML Wayland application taking over `tty1`. The user does not interact with a traditional bash shell unless they drop to a TTY.
3. **Privilege-Bounded Agent**: The LLM agent executes on the OS but is sandboxed. It interacts with the filesystem through explicitly allowed, highly-restricted sudo commands (e.g. `jarvis-fsop`) and systemd's sandbox settings (`ProtectSystem=strict`).
4. **Seamless Local/Remote Transition**: A pre-OS `dialog` setup allows the user to switch seamlessly between a baked-in CPU/GPU backend or a remote OpenAI-compatible API without changing the LLM client logic.

## Audience for this Knowledge Base
This AI Knowledge Base (`ai_knowledge/`) is constructed specifically for Large Language Models (LLMs) to ingest so they can quickly orient themselves when tasked with contributing to, debugging, or planning architecture for Jarvis-OS. 

Instead of reading the raw codebase line-by-line, LLMs should refer to the architectural diagrams and design documents here, and use `graphify` (see `08_KNOWLEDGE_GRAPH`) to query the live AST and function signatures.
