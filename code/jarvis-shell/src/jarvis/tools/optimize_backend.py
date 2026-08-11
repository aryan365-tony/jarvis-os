import subprocess
from .registry import register
from ..paths import repo_root

# BUG-011: no timeout meant a stuck/killed build_script left orphaned
# compiler/linker child processes running indefinitely. start_new_session
# puts the child in its own process group so a timeout kill can take the
# whole group down via os.killpg, not just the immediate shell process.
_BUILD_TIMEOUT_S = 1800


@register(
    "optimize_backend",
    risk="high",
    description=(
        "Detect the GPU and, if supported, build and switch the LLM backend to a "
        "hardware-accelerated build, then restart the inference server."
    ),
    parameters={"type": "object", "properties": {}},
)
def optimize_backend() -> str:
    """Detect hardware and optimize the LLM backend for the local GPU.

    Confirmation for this irreversible action is handled by the tool registry
    before this function is ever called, so it takes no ``confirm`` argument
    (fixing the previous signature bug where ``confirm_async`` was expected as a
    parameter but never injected).
    """
    base_dir = repo_root()
    script_path = base_dir / "llama" / "scripts" / "detect_gpu.py"

    try:
        backend = subprocess.check_output(
            ["python3", str(script_path)], text=True
        ).strip()
    except Exception as e:
        return f"Failed to detect hardware: {e}"

    if backend == "cpu":
        return "You are already using the optimal backend (CPU). No supported GPU was detected."

    build_script = base_dir / "llama" / "scripts" / "build_backend.sh"
    proc = None
    try:
        proc = subprocess.Popen(
            [str(build_script), backend], text=True, start_new_session=True
        )
        try:
            code = proc.wait(timeout=_BUILD_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            import os
            import signal

            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            proc.wait()
            return f"Optimization failed: build timed out after {_BUILD_TIMEOUT_S}s"
        if code != 0:
            return f"Optimization failed: build_backend.sh exited {code}"

        subprocess.run(
            ["sudo", "systemctl", "restart", "llama-server.service"],
            check=True, timeout=60,
        )
        return (
            f"Optimization for {backend.upper()} complete. "
            "The inference server was restarted to use the new backend."
        )
    except subprocess.CalledProcessError as e:
        return f"Optimization failed: {e}"
    except Exception as e:
        return f"Optimization failed: {e}"
