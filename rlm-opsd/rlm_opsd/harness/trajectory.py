from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TraceModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


_NonnegativeInt = Annotated[int, Field(strict=True, ge=0)]


class ContextMetadataTrace(TraceModel):
    """Coverage geometry only: context contents and prefix are never fields."""

    context_type: Literal["str", "list"]
    context_total_length: _NonnegativeInt
    context_lengths: list[_NonnegativeInt]

    @model_validator(mode="after")
    def check_geometry(self):
        if self.context_type == "str" and self.context_lengths:
            raise ValueError("str context_lengths must be empty")
        if self.context_type == "list" and sum(self.context_lengths) != self.context_total_length:
            raise ValueError("context_lengths sum must equal context_total_length")
        return self


class SubcallTrace(TraceModel):
    prompt_chars: int = Field(ge=0)
    output_chars: int = Field(default=0, ge=0)
    latency_s: float = Field(default=0, ge=0)
    turn_index: int = Field(ge=0)
    depth: int = Field(default=1, ge=1)
    kind: Literal["llm_query", "rlm_query"] = "llm_query"
    error: str | None = None


class TurnTrace(TraceModel):
    assistant_text: str
    assistant_token_ids: list[int]
    code_blocks: list[str] = Field(default_factory=list)
    stdout_raw_chars: int = Field(default=0, ge=0)
    stderr_raw_chars: int = Field(default=0, ge=0)
    stdout_truncated: str = ""
    error: str | None = None
    finish_error: str | None = None
    ignored_after_finish: str = ""
    subcalls: list[SubcallTrace] = Field(default_factory=list)


class FinalTrace(TraceModel):
    type: Literal["FINAL", "FINAL_VAR", "none"] = "none"
    value: str = ""
    error: str | None = None


class EpisodeTrace(TraceModel):
    task_id: str
    family: str
    domain: str
    tags: list[str]
    context_metadata: ContextMetadataTrace | None = None
    size_bucket: _NonnegativeInt | None = None
    prompt_variant: Literal["student", "teacher"] = "student"
    manual_version: str = "manual_v1"
    turns: list[TurnTrace] = Field(default_factory=list)
    final: FinalTrace = Field(default_factory=FinalTrace)
    budget_hits: dict[str, bool] = Field(default_factory=lambda: dict(
        max_turns=False, max_subcalls=False, max_subcall_chars=False,
        wall_time=False, memory=False, cpu_time=False, max_depth=False))
    timings: dict[str, float] = Field(default_factory=dict)
