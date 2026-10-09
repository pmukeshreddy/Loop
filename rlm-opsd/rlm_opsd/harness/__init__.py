"""Public M1 harness API. Lazy imports keep the subprocess startup small."""
from .config import HarnessConfig
from .protocol import context_metadata, parse_turn
from .trajectory import EpisodeTrace

__all__ = ["HarnessConfig", "context_metadata", "parse_turn", "EpisodeTrace", "Episode", "RLMOpsdEnv"]


def __getattr__(name):
    if name == "Episode":
        from .episode import Episode
        return Episode
    if name == "RLMOpsdEnv":
        from .env import RLMOpsdEnv
        return RLMOpsdEnv
    raise AttributeError(name)
