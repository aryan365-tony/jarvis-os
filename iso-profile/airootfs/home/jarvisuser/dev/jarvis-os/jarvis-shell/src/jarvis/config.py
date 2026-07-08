import tomli
from dataclasses import dataclass
from pathlib import Path

@dataclass
class LLMConfig:
    endpoint: str
    model_name: str
    max_context: int
    request_timeout_s: int

@dataclass
class MemoryConfig:
    db_path: str
    core_memory_max_tokens: int

@dataclass
class PolicyConfig:
    network_allowlist_path: str
    irreversible_requires_confirm: bool
    max_tool_calls_per_turn: int
    max_turns_per_session_task: int

@dataclass
class Config:
    llm: LLMConfig
    memory: MemoryConfig
    policy: PolicyConfig

def load_config(path="config/jarvis.toml") -> Config:
    p = Path(path)
    if not p.exists():
        # Fallback to local execution relative path
        p = Path(__file__).parent.parent.parent.parent / "config" / "jarvis.toml"
        
    with open(p, "rb") as f:
        data = tomli.load(f)
        
    return Config(
        llm=LLMConfig(**data.get("llm", {})),
        memory=MemoryConfig(**data.get("memory", {})),
        policy=PolicyConfig(**data.get("policy", {}))
    )
