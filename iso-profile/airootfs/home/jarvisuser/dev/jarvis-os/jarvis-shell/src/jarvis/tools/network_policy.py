from pathlib import Path
from urllib.parse import urlparse

def _load_allowlist(path: str) -> set[str]:
    p = Path(path)
    if not p.exists():
        return set()
    return {line.strip() for line in p.read_text().splitlines() if line.strip() and not line.startswith("#")}

def is_allowed_host(url: str, allowlist_path: str) -> bool:
    host = urlparse(url).hostname or ""
    allowlist = _load_allowlist(allowlist_path)
    return host in allowlist
