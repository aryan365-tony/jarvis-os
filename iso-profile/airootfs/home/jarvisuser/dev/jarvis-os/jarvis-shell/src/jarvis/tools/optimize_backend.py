import subprocess
import os
from .registry import register

@register("optimize_backend", risk="irreversible")
def optimize_backend(confirm_async) -> str:
    """
    Detects hardware, prompts the user to optimize the LLM backend for their GPU,
    and runs the build process if confirmed.
    """
    # Run the hardware detection script
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    script_path = os.path.join(base_dir, "llama", "scripts", "detect_gpu.py")
    
    try:
        backend = subprocess.check_output(f"python3 {script_path}", shell=True, text=True).strip()
    except Exception as e:
        return f"Failed to detect hardware: {e}"

    if backend == "cpu":
        return "You are already using the optimal backend (CPU). No supported GPU was detected."
    
    # Prompt user
    prompt = {
        "action": "Optimize Backend",
        "detected_gpu": backend.upper(),
        "warning": "This will download dependencies and compile a new backend. It may take a few minutes."
    }
    
    # Actually `confirm_async` is passed into `execute` inside registry.py, 
    # but the tool functions themselves might not directly have it unless injected or we rely on the registry's wrapper.
    # The registry wrapper currently checks risk="irreversible" and calls confirm_async(name, args).
    # We will assume this function executes only if the user confirmed it via the registry wrapper.
    
    build_script = os.path.join(base_dir, "llama", "scripts", "build_backend.sh")
    try:
        # Run build
        subprocess.run([build_script, backend], check=True, text=True)
        
        # Restart service
        subprocess.run(["sudo", "systemctl", "restart", "llama-server.service"], check=True)
        return f"Optimization for {backend.upper()} complete. The service has been restarted to use the new backend."
    except subprocess.CalledProcessError as e:
        return f"Optimization failed: {e}"
