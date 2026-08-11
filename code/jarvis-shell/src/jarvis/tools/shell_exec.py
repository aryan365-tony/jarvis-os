import os
import signal
import subprocess

from .registry import register
from ..audit.chain import audit_log


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
    # RISK-008: `cmd = "long_running_cmd &"` detaches a child that outlives
    # this call, satisfying timeout_s while leaving an untracked orphan.
    # start_new_session puts the whole command (and anything it backgrounds)
    # in one process group, so: (a) a real timeout kills every descendant,
    # not just the shell, and (b) we can detect and report any process the
    # command itself backgrounded, instead of silently losing track of it.
    proc = subprocess.Popen(
        cmd, shell=True, cwd=cwd, start_new_session=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    # start_new_session makes this process the session/group leader, so its
    # pgid equals its own pid — capture it now. Once the process exits and is
    # reaped (by communicate() below), os.getpgid(proc.pid) fails even though
    # backgrounded descendants sharing that pgid may still be alive.
    pgid = proc.pid
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
        returncode = proc.returncode
    except subprocess.TimeoutExpired:
        try:
            os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        stdout, stderr = proc.communicate()
        return (
            f"error: command timed out after {timeout_s}s "
            f"(process group killed)\nstdout:\n{stdout}\nstderr:\n{stderr}"
        )[:8000]

    out = f"exit={returncode}\nstdout:\n{stdout}\nstderr:\n{stderr}"

    # Detect processes the command backgrounded (still alive in its group
    # after the foreground command exited) and surface them rather than
    # letting them run untracked.
    try:
        os.killpg(pgid, 0)  # raises if the group is empty
        out += f"\nnote: command left background process(es) running (pgid={pgid})"
        audit_log("shell_exec_background_leak", {"cmd": cmd[:200], "pgid": pgid})
    except (ProcessLookupError, PermissionError):
        pass

    return out[:8000]
