from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SandboxConfig(StrictConfig):
    wall_time_s: float = Field(default=120, gt=0, allow_inf_nan=False)
    memory_mb: int = Field(default=1024, gt=0)
    cpu_time_s: float = Field(default=30, gt=0, allow_inf_nan=False)


class HarnessConfig(StrictConfig):
    max_turns: int = Field(default=20, gt=0)
    max_tokens_per_turn: int = Field(default=4096, gt=0)
    max_subcalls: int = Field(default=32, ge=0)
    max_subcall_chars: int = Field(default=32000, gt=0)
    subcall_concurrency: int = Field(default=4, gt=0)
    subcall_timeout_s: float = Field(default=60, gt=0, allow_inf_nan=False)
    subcall_max_tokens: int = Field(default=4096, gt=0)
    subcall_chunk_chars: int = Field(default=16000, gt=0)
    prefix_chars: int = Field(default=0, ge=0)
    stdout_max_chars: int = Field(default=20000, gt=0)
    enable_recursion: bool = False
    max_depth: int = Field(default=1, ge=1)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)

    @model_validator(mode="before")
    @classmethod
    def derive_chunk_size(cls, values):
        if isinstance(values, dict) and 'subcall_chunk_chars' not in values and 'max_subcall_chars' in values:
            limit = values['max_subcall_chars']
            if type(limit) is int and limit > 0:
                values = {**values, 'subcall_chunk_chars': max(1, limit // 2)}
        return values

    @model_validator(mode="after")
    def check_recursion(self):
        if self.subcall_chunk_chars > self.max_subcall_chars:
            raise ValueError("subcall_chunk_chars must not exceed max_subcall_chars")
        if not self.enable_recursion and self.max_depth != 1:
            raise ValueError("max_depth > 1 requires enable_recursion")
        if self.enable_recursion and self.max_depth < 2:
            raise ValueError("enable_recursion requires max_depth >= 2")
        return self

    @classmethod
    def from_yaml(cls, path: str | Path):
        return cls.model_validate(yaml.safe_load(Path(path).read_text()))
