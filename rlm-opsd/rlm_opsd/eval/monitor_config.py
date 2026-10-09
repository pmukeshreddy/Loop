"""M8 settings; exit tolerances are user-required, with no acceptance defaults."""
from pydantic import Field
from .config import GateModel


class ExitRules(GateModel):
    behavior_tolerance: float=Field(ge=0,le=1,allow_inf_nan=False)
    min_known: int=Field(gt=0)
    max_unknown_fraction: float=Field(ge=0,le=1,allow_inf_nan=False)
    retention_tolerance: float=Field(ge=0,le=1,allow_inf_nan=False)

from pathlib import Path
from typing import Literal
from pydantic import model_validator
import yaml
from .config import EndpointConfig


class RetentionItem(GateModel):
    id: str=Field(min_length=1)
    prompt: str=Field(min_length=1)
    answer: str | int | float | list[str | int | float]
    answer_type: Literal['exact','multiple_choice','numeric','list_f1']

    @model_validator(mode='after')
    def evaluable_gold(self):
        import ast
        from decimal import Decimal,InvalidOperation
        import math
        value=self.answer
        if self.answer_type=='numeric':
            try:
                if isinstance(value,list) or not Decimal(str(value).strip()).is_finite():
                    raise ValueError('numeric gold must be a finite scalar')
            except InvalidOperation:
                raise ValueError('numeric gold must be a finite scalar') from None
        elif self.answer_type=='list_f1':
            if isinstance(value,str):
                try:value=ast.literal_eval(value)
                except (ValueError,SyntaxError):raise ValueError('list_f1 gold must be a valid list') from None
            if not isinstance(value,list) or any(type(x) not in (str,int,float)
                    or (type(x) is float and not math.isfinite(x)) for x in value):
                raise ValueError('list_f1 gold must contain strings or finite numbers')
        elif isinstance(value,list) or (type(value) is float and not math.isfinite(value)):
            raise ValueError('exact/multiple_choice gold must be a finite scalar or string')
        return self


class MonitorConfig(GateModel):
    training_config: Path
    checkpoint: Path
    checkpoint_sha256: str=Field(pattern=r'^[0-9a-f]{64}$')
    checkpoint_step: int=Field(ge=0)
    eval_interval: int=Field(gt=0)
    run_label: str=Field(min_length=1)
    student_endpoint: EndpointConfig
    endpoint_checkpoint_sha256: str=Field(pattern=r'^[0-9a-f]{64}$')
    review_per_family: int=Field(gt=0)
    kl_top_k: int=Field(ge=0)
    temperature: float=Field(gt=0,allow_inf_nan=False)
    seed: int=Field(ge=0)

    @model_validator(mode='after')
    def consistency(self):
        if self.checkpoint_sha256!=self.endpoint_checkpoint_sha256:
            raise ValueError('generation endpoint must declare the same checkpoint hash as local scoring')
        return self

    @classmethod
    def from_yaml(cls,path):
        path=Path(path).resolve();values=yaml.safe_load(path.read_text())
        if not isinstance(values,dict):raise ValueError('monitor settings must be a mapping')
        for key in ('training_config','checkpoint'):
            if isinstance(values.get(key),str):values[key]=(path.parent/values[key]).resolve()
        return cls.model_validate(values)


class ExitConfig(GateModel):
    retention_path: Path
    retention_max_tokens: int=Field(default=512,gt=0)
    evaluation_dir: Path
    expected_checkpoint_sha256: str=Field(pattern=r'^[0-9a-f]{64}$')
    rules: ExitRules

    @classmethod
    def from_yaml(cls,path):
        path=Path(path).resolve();values=yaml.safe_load(path.read_text())
        if not isinstance(values,dict):raise ValueError('exit settings must be a mapping')
        for key in ('evaluation_dir','retention_path'):
            if isinstance(values.get(key),str):values[key]=(path.parent/values[key]).resolve()
        return cls.model_validate(values)
