"""Project smoke settings, mapped explicitly to the pinned prime-rl APIs."""
from pathlib import Path
import tomllib
from typing import Literal

from pydantic import Field, model_validator
from rlm_opsd.eval.config import GateModel


MODEL_PINS={
    'small':('Qwen/Qwen3.5-0.8B','2fc06364715b967f1860aea9cf38778875588b17'),
    '27b':('Qwen/Qwen3.5-27B','fc05daec18b0a78c049392ed2e771dde82bdf654'),
}


class OpsdConfig(GateModel):
    stage: Literal['small','27b']
    base_model: str
    revision: str
    prompt_config: Path
    gate_config: Path
    gate_dir: Path | None=None
    small_smoke_dir: Path | None=None
    max_seq_len: int=Field(default=4096,gt=0)
    max_tokens: int=Field(default=256,gt=0)
    temperature: float=Field(default=1.0,gt=0,allow_inf_nan=False)
    # Operator declaration of the generation server's logprob convention.
    logprobs_mode: Literal['processed_logprobs']
    seed: int=Field(default=417,ge=0)
    learning_rate: float=Field(default=2e-5,gt=0,allow_inf_nan=False)
    max_grad_norm: float=Field(default=1.0,gt=0,allow_inf_nan=False)
    lora_rank: int=Field(default=16,gt=0)
    lora_alpha: float=Field(default=32.0,gt=0,allow_inf_nan=False)
    jsd_beta: Literal[0.5]=0.5
    jsd_chunk_size: int=Field(default=64,gt=0)
    token_gate: bool=False
    token_gate_k: float=Field(default=1.0,gt=0,allow_inf_nan=False)

    @model_validator(mode='after')
    def pinned_model(self):
        if (self.base_model,self.revision)!=MODEL_PINS[self.stage]:
            raise ValueError('model/revision must match the pinned smoke stage')
        return self

    @classmethod
    def from_toml(cls,path):
        path=Path(path).resolve()
        values=tomllib.loads(path.read_text())
        for key in ('prompt_config','gate_config','gate_dir','small_smoke_dir'):
            if isinstance(values.get(key),str):values[key]=(path.parent/values[key]).resolve()
        return cls.model_validate(values)
