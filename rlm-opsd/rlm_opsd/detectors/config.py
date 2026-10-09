"""Explicit detector thresholds, independent of gate/exit acceptance criteria."""
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict, Field


class DetectorConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True)

    probe_max_chars: int = Field(ge=0)
    dump_threshold: int = Field(ge=0)
    read_threshold: int = Field(ge=0)
    many_hits: int = Field(ge=0)
    subcall_max_chars: int = Field(gt=0)
    min_batch_chars: int = Field(ge=0)
    max_subcalls_expected: dict[str, Annotated[int, Field(ge=0)]]
    hand_copy_min_chars: int = Field(gt=0)
    dense_coverage_min: float = Field(ge=0, le=1, allow_inf_nan=False)

    @classmethod
    def from_yaml(cls, path: str | Path):
        return cls.model_validate(yaml.safe_load(Path(path).read_text()))
