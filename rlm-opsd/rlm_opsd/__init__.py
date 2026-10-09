"""RLM-OPSD environment entry point (SPEC §2)."""


def load_environment(**kwargs):
    from .harness import RLMOpsdEnv

    return RLMOpsdEnv(**kwargs)
