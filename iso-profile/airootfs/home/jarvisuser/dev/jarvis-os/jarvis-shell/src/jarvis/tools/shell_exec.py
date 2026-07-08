import subprocess
from .registry import register

@register("shell_exec", risk="irreversible")
def shell_exec(cmd: str, cwd: str | None = None, timeout_s: int = 30) -> str:
    # shell=True is intentional for this local kiosk single-user environment.
    proc = subprocess.run(
        cmd, shell=True, cwd=cwd, timeout=timeout_s,
        capture_output=True, text=True,
    )
    out = f"exit={proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    return out[:8000]
