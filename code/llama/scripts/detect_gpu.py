#!/usr/bin/env python3
import subprocess

def detect_gpu():
    try:
        lspci_output = subprocess.check_output("lspci", shell=True, text=True).lower()
        if "nvidia" in lspci_output:
            return "cuda"
        elif "amd" in lspci_output or "radeon" in lspci_output:
            return "vulkan"
        else:
            return "cpu"
    except Exception:
        return "cpu"

if __name__ == "__main__":
    print(detect_gpu())
