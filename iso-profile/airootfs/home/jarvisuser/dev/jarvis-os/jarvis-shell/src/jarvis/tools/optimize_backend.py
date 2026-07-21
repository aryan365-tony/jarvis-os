import subprocess
import os
from .registry import register


@register(
    "optimize_backend",
    risk="irreversible",
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
    base_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    script_path = os.path.join(base_dir, "llama", "scripts", "detect_gpu.py")

    try:
        backend = subprocess.check_output(
            ["python3", script_path], text=True
        ).strip()
    except Exception as e:
        return f"Failed to detect hardware: {e}"

    if backend == "cpu":
        return "You are already using the optimal backend (CPU). No supported GPU was detected."

    build_script = os.path.join(base_dir, "llama", "scripts", "build_backend.sh")
    try:
        subprocess.run([build_script, backend], check=True, text=True)
        subprocess.run(
            ["sudo", "systemctl", "restart", "llama-server.service"], check=True
        )
        return (
            f"Optimization for {backend.upper()} complete. "
            "The inference server was restarted to use the new backend."
        )
    except subprocess.CalledProcessError as e:
        return f"Optimization failed: {e}"
