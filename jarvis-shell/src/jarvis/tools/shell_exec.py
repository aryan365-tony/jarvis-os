import subprocess
from .registry import register


@register(
    "shell_exec",
    risk="high",
    description="Run a shell command on the local machine and return combined output.",
    parameters={
        "type": "object",
        "properties": {
            "cmd": {"type": "string", "description": "The command line to execute."},
            "cwd": {"type": "string", "description": "Optional working directory."},
            "timeout_s": {"type": "integer", "description": "Timeout in seconds (default 30)."},
        },
        "required": ["cmd"],
    },
)
def shell_exec(cmd: str, cwd: str | None = None, timeout_s: int = 30) -> str:
    # shell=True is intentional for this local kiosk single-user environment.
    proc = subprocess.run(
        cmd, shell=True, cwd=cwd, timeout=timeout_s,
        capture_output=True, text=True,
    )
    out = f"exit={proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    return out[:8000]
