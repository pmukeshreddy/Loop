"""User-selected teacher-gate settings. No implicit acceptance thresholds."""
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import yaml


class GateModel(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True)


class GateCriterion(GateModel):
    metric: str = Field(pattern=r'^(D(?:[1-9]|1[0-8])|task_tag_match)$')
    dimension: Literal['overall','family','size_bucket','domain']
    group: str = Field(min_length=1)
    direction: Literal['min','max']
    threshold: float = Field(ge=0,le=1,allow_inf_nan=False)
    min_known: int = Field(gt=0)
    max_unknown_fraction: float = Field(ge=0,le=1,allow_inf_nan=False)

    @model_validator(mode='after')
    def overall_group(self):
        if self.dimension == 'overall' and self.group != 'all':
            raise ValueError('overall group must be all')
        return self


class EndpointConfig(GateModel):
    base_url: str = Field(min_length=1)
    served_model: str = Field(min_length=1)
    api_key_var: str | None

    @field_validator('base_url')
    @classmethod
    def plain_http_url(cls,value):
        url=urlsplit(value)
        if url.scheme not in ('http','https') or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError('endpoint must be HTTP(S), without credentials, query or fragment')
        return value.rstrip('/')

    @field_validator('api_key_var')
    @classmethod
    def env_name(cls,value):
        if value is not None and not value.isidentifier():
            raise ValueError('api_key_var must be an environment-variable name, never a secret')
        return value


class GateConfig(GateModel):
    base_model: str = Field(min_length=1)
    revision: str = Field(pattern=r'^[0-9a-f]{40}$')
    run_label: str = Field(min_length=1)
    root_endpoint: EndpointConfig
    frozen_endpoint: EndpointConfig
    manifest_path: Path
    harness_config: Path
    prompt_config: Path
    detector_config: Path
    temperature: float = Field(ge=0,allow_inf_nan=False)
    seed: int = Field(ge=0)
    request_timeout_s: float = Field(gt=0,allow_inf_nan=False)
    episode_timeout_s: float = Field(gt=0,allow_inf_nan=False)
    criteria: list[GateCriterion] = Field(min_length=1)

    @classmethod
    def from_yaml(cls,path):
        path=Path(path).resolve()
        values=yaml.safe_load(path.read_text())
        if not isinstance(values,dict):
            raise ValueError('gate config must be a YAML mapping')
        for key in ('manifest_path','harness_config','prompt_config','detector_config'):
            if isinstance(values.get(key),str):
                values[key]=(path.parent/values[key]).resolve()
        return cls.model_validate(values)
