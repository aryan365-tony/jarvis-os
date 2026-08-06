# Architecture

## The Jarvis-OS Core Architecture

The architecture of Jarvis-OS is split into three main layers: The OS/Init layer, the Wayland Compositor/Shell layer, and the AI Backend layer.

### 1. OS & Init Layer (`systemd`)
The OS is built on Arch Linux via `mkarchiso`.
- **`jarvis-live-prompt.service`**: A `oneshot` blocker service that runs early in the boot sequence (`Before=jarvis-shell.service`) on the live ISO. It uses `dialog` on `tty1` to prompt the user to configure Local or Remote LLM modes, guaranteeing the AI is correctly pointed before the UI loads.
- **`jarvis-shell.service`**: The main persistent daemon. It runs as `jarvisuser` (uid 1000). It establishes the PAM session and launches `cage` (the Wayland compositor) directly on `tty1`, entirely bypassing display managers like GDM/SDDM.

### 2. Wayland Compositor & Shell
- **Cage Compositor**: `cage-jarvis.session` boots a single Qt/QML graphical application in full-screen mode.
- **`jarvis-shell`**: The Python application orchestrating the UI and the conversational logic. It acts as the orchestration layer:
  - Takes voice/text input.
  - Sends it via SSE (Server-Sent Events) to the LLM backend via the `AsyncLLMClient`.
  - Can trigger sandboxed OS capabilities (via `jarvis-fsop` and strictly scoped sudo rules) when the LLM issues tool commands.

### 3. AI Backend Layer (`llama.cpp`)
- Managed by `ReadinessService` inside `jarvis-shell`, which acts as a process supervisor.
- The system attempts to run a local `llama.cpp` instance as the LLM provider.
- It exposes a standard `/v1/chat/completions` OpenAI-compatible REST API on localhost.
- The backend handles GGUF inference completely offline. If configured in remote mode, `jarvis-shell` simply points its requests to an external IP/Hostname.

## Security Boundary
The defining architectural trait of Jarvis is the **Privilege Boundary**. 
The system daemon runs with `ProtectSystem=strict` and `ProtectHome=read-only`. The LLM has zero direct root access. To mutate the system, the LLM must emit tool calls that map to `jarvis-fsop`, a locked-down, root-owned binary that enforces a strict denylist.
