"""Package management via pacman (offline image).

Design note
-----------
The image is offline, so package operations act against the local pacman DB /
cache. Tiering:

* ``pkg_query`` (low)    — read-only: -Q / -Qi / -Ss against local db.
* ``pkg_manage`` (high)  — state-changing: install (-S), remove (-R), or a full
                           upgrade (-Syu). All go through ``sudo pacman`` (the
                           sudoers drop-in scopes NOPASSWD to /usr/bin/pacman).
                           High tier => registry snapshots before running, so a
                           bad upgrade/removal is one rollback away.

Never pass a raw command string to pacman; only fixed flags + validated package
names, so the agent cannot smuggle shell metacharacters.
"""

from __future__ import annotations

import re
import subprocess

from .registry import register

_PKG_RE = re.compile(r"^[A-Za-z0-9@._+-]+$")


def _valid_pkgs(pkgs: list[str]) -> bool:
    return bool(pkgs) and all(_PKG_RE.match(p) for p in pkgs)


def _run(args: list[str], timeout: int = 300) -> str:
    proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    out = (proc.stdout or "") + (proc.stderr or "")
    return f"exit={proc.returncode}\n{out}"[:8000]


@register(
    "pkg_query",
    risk="low",
    description="Query installed or available packages (read-only pacman -Q/-Qi/-Ss).",
    parameters={
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["installed", "info", "search"]},
            "name": {"type": "string", "description": "Package name or search term."},
        },
        "required": ["mode"],
    },
)
def pkg_query(mode: str, name: str = "") -> str:
    if name and not _PKG_RE.match(name):
        return "error: invalid package name"
    if mode == "installed":
        return _run(["pacman", "-Q"] + ([name] if name else []), timeout=30)
    if mode == "info":
        if not name:
            return "error: info needs a name"
        return _run(["pacman", "-Qi", name], timeout=30)
    if mode == "search":
        if not name:
            return "error: search needs a term"
        return _run(["pacman", "-Ss", name], timeout=30)
    return f"error: unknown mode {mode}"


@register(
    "pkg_manage",
    risk="high",
    description=(
        "Install, remove, or upgrade packages via pacman. High risk: a "
        "pre-action system snapshot is taken so the change can be rolled back."
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["install", "remove", "upgrade"]},
            "packages": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Package names (not needed for upgrade).",
            },
        },
        "required": ["action"],
    },
)
def pkg_manage(action: str, packages: list[str] | None = None) -> str:
    packages = packages or []
    if action == "upgrade":
        return _run(["sudo", "-n", "pacman", "-Syu", "--noconfirm"], timeout=1800)
    if not _valid_pkgs(packages):
        return "error: invalid or empty package list"
    if action == "install":
        return _run(["sudo", "-n", "pacman", "-S", "--noconfirm", *packages], timeout=1800)
    if action == "remove":
        return _run(["sudo", "-n", "pacman", "-R", "--noconfirm", *packages], timeout=600)
    return f"error: unknown action {action}"
