from pathlib import Path

import verifiers as vf
from rlm_train import RLMTrainEnv
from verifiers.clients import resolve_client
from verifiers.types import ClientConfig
from verifiers.utils.message_utils import normalize_messages

from .config import HarnessConfig
from .episode import Episode, HarnessProxy
from rlm_opsd.prompts import PromptConfig


class RLMOpsdEnv(RLMTrainEnv):
    """SPEC §2 adapter. Inherits the pinned verifiers rollout and token pipeline."""
    def __init__(self, *, frozen_client, frozen_model, config=None,
                 log_dir="trajectories", system_prompt=None, prompt_config=None,
                 prompt_variant="student", manual_version=None, prompt_builder=None, **kwargs):
        if config is None:
            config = HarnessConfig.from_yaml(Path(__file__).resolve().parents[2] / "configs/harness.yaml")
        elif isinstance(config, (str, Path)):
            config = HarnessConfig.from_yaml(config)
        elif isinstance(config, dict):
            config = HarnessConfig.model_validate(config)
        if frozen_client is None or not frozen_model:
            raise ValueError("frozen_client and frozen_model are required")
        self.harness_config = config
        if prompt_config is None or isinstance(prompt_config, (str, Path)):
            prompt_config = PromptConfig.from_yaml(prompt_config)
        self.prompt_config, self.prompt_builder = prompt_config, prompt_builder
        if isinstance(frozen_client, dict):
            frozen_client = ClientConfig.model_validate(frozen_client)
        self._owns_frozen_client = isinstance(frozen_client, ClientConfig)
        self.frozen_client = resolve_client(frozen_client)
        self.frozen_model = frozen_model
        self.log_dir, self.system_text = log_dir, system_prompt
        self.prompt_variant, self.manual_version = prompt_variant, manual_version
        # No task correctness or other rewards in this milestone.
        kwargs["score_rollouts"] = False
        super().__init__(max_iterations=config.max_turns, rubric=vf.Rubric(), **kwargs)

    async def _ensure_proxy(self):
        # The inherited lifecycle/lock remains; select the SPEC-aware proxy class.
        import asyncio

        if self._proxy_lock is None:
            self._proxy_lock = asyncio.Lock()
        async with self._proxy_lock:
            if self._proxy is None:
                self._proxy = HarnessProxy()
                await self._proxy.start()
            return self._proxy

    async def setup_state(self, state):
        if state["client"] is self.frozen_client:
            raise ValueError("frozen_client must be separate from the root client")
        episode = Episode(config=self.harness_config, info=state["info"],
                          frozen_client=self.frozen_client, frozen_model=self.frozen_model,
                          log_dir=self.log_dir, system_prompt=self.system_text,
                          prompt_variant=self.prompt_variant, manual_version=self.manual_version,
                          prompt_builder=self.prompt_builder,
                          prompt_config=self.prompt_config,
                          proxy=await self._ensure_proxy())
        state["opsd_episode"] = episode
        args = {**self.sampling_args, **(state.get("sampling_args") or {})}
        supplied_max = args.pop("max_completion_tokens", None)
        requested = args.get("max_tokens") or supplied_max or self.harness_config.max_tokens_per_turn
        args["max_tokens"] = min(requested, self.harness_config.max_tokens_per_turn)
        state["sampling_args"] = self.prompt_config.sampling_args(args)
        await episode.__aenter__()
        state["prompt"] = normalize_messages(episode.messages)
        return state

    async def get_prompt_messages(self, state):
        return normalize_messages(state["opsd_episode"].messages)

    async def add_trajectory_step(self, state, trajectory_step):
        await super().add_trajectory_step(state, trajectory_step)
        episode = state["opsd_episode"]
        message = trajectory_step["completion"][-1]
        # Verifiers may clip its training tokens at max_seq_len. The JSON trace
        # pairs the full assistant text with the original generated token IDs.
        tokens = trajectory_step["response"].message.tokens
        observation = await episode.accept(message.content or "", tokens.completion_ids if tokens else [])
        # Keep provider reasoning/thinking fields in the next root request. Only
        # assistant content is executable; reasoning does not trigger FINAL.
        episode.messages[-2] = message.model_dump(exclude_none=True)
        if episode.done:
            state["final_env_response"] = normalize_messages([dict(role="user", content=observation)]) if observation else []
            if episode.trace.final.type != "none":
                state["rlm_final_answer"] = state["final_answer"] = episode.trace.final.value

    @vf.cleanup
    async def cleanup_rlm(self, state):
        episode = state.get("opsd_episode")
        if episode:
            error = "rollout timed out" if state.get("timed_out") else None
            if state.get("error"):
                error = str(state["error"])
            await episode.close(error=error)
            state["opsd_trajectory_path"] = str(episode.log_path)

    @vf.teardown
    async def teardown_rlm(self):
        await super().teardown_rlm()
        if self._owns_frozen_client:
            await self.frozen_client.close()
