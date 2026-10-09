import asyncio
import json
from pathlib import Path
import time
import uuid

from aiohttp import web
from rlm_train import ClientHandle, SubLLMProxy
from verifiers.types import UserMessage
from verifiers.utils.message_utils import normalize_messages

from rlm_opsd.prompts import PromptBuilder, PromptConfig

from .config import HarnessConfig
from .protocol import context_metadata, parse_turn, truncate_output
from .sandbox import SandboxBackend, SandboxLimit
from .trajectory import EpisodeTrace, FinalTrace, SubcallTrace, TurnTrace


class HarnessProxy(SubLLMProxy):
    async def _completion(self, handle, prompt, model):
        # The request's model field can never select the trainable/root endpoint.
        return await handle.state_ref.query(prompt), {}

    async def _handle_single(self, request):
        body = await request.json()
        if body.get("recursive"):
            handle = self._handles.get(request.match_info["rollout_id"])
            if handle is None:
                return web.json_response(dict(error="unknown rollout"), status=404)
            return web.json_response(dict(response=await handle.state_ref.query(body.get("prompt"), recursive=True)))
        return await super()._handle_single(request)


class SubcallBudget:
    def __init__(self, config):
        self.config = config
        self.used = 0
        self.semaphore = asyncio.Semaphore(config.subcall_concurrency)
        self.hits = set()

    def reserve(self, prompt):
        if not isinstance(prompt, str):
            raise ValueError("subcall prompt must be str")
        if len(prompt) > self.config.max_subcall_chars:
            self.hits.add("max_subcall_chars")
            raise ValueError("max_subcall_chars exceeded")
        if self.used >= self.config.max_subcalls:
            self.hits.add("max_subcalls")
            raise ValueError("max_subcalls exceeded")
        # No await between checking and reserving: atomic on this event loop.
        self.used += 1


class Episode:
    def __init__(self, *, config: HarnessConfig, info, frozen_client, frozen_model,
                 log_dir, system_prompt=None, prompt_variant="student",
                 manual_version=None, prompt_builder=None, prompt_config=None, depth=1, budget=None, proxy=None,
                 infrastructure_errors=None):
        if frozen_client is None or not frozen_model:
            raise ValueError("a separate frozen_client and frozen_model are required")
        self.config, self.info = config, info
        self.prompt_config = prompt_config if prompt_config is not None else PromptConfig.from_yaml()
        self.metadata = context_metadata(info["context"], config.prefix_chars)
        self.system_prompt = system_prompt
        self.prompt_builder = prompt_builder
        if system_prompt is None:
            self.prompt_builder = prompt_builder or PromptBuilder.load(manual_version=manual_version)
            pair = self.prompt_builder.build(query=info['query'], context=info['context'], config=config)
            if manual_version is not None and manual_version != pair.manual_version:
                raise ValueError('manual version differs from prompt builder')
            manual_version = pair.manual_version
            self.messages = pair.messages(prompt_variant)
        else:
            if prompt_builder is not None or not manual_version or not manual_version.startswith('custom_'):
                raise ValueError('custom system prompts require a custom_ version and no prompt builder')
            self.messages = [dict(role='system', content=system_prompt + '\n\nContext metadata:\n' + json.dumps(self.metadata)),
                             dict(role='user', content=info['query'])]
        self.frozen_client, self.frozen_model = frozen_client, frozen_model
        self.depth = depth
        self.budget = budget or SubcallBudget(config)
        self.proxy = proxy or HarnessProxy()
        self._owns_proxy = proxy is None
        self.rollout_id = uuid.uuid4().hex
        self.backend = SandboxBackend(config)
        self.trace = EpisodeTrace(**{k: info[k] for k in ("task_id", "family", "domain", "tags")},
                                  prompt_variant=prompt_variant, manual_version=manual_version,
                                  context_metadata={k: self.metadata[k] for k in (
                                      "context_type", "context_total_length", "context_lengths")},
                                  size_bucket=info.get("size_bucket"))
        self.log_path = Path(log_dir) / f"{self.rollout_id}.json"
        self.done = self._closed = False
        self._active_queries = set()
        self._started = time.perf_counter()
        # Shared across recursive children; a recovered parent cannot conceal a
        # broken worker. Store only types and source paths, not exception text.
        self.infrastructure_errors = [] if infrastructure_errors is None else infrastructure_errors

    def _record_infrastructure_error(self, stage, exc):
        self.infrastructure_errors.append(dict(task_id=self.trace.task_id, stage=stage,
            error_type=type(exc).__name__, trajectory_path=str(self.log_path)))

    async def __aenter__(self):
        try:
            await self.proxy.start()
            self.proxy.register(self.rollout_id, ClientHandle(
                client=self.frozen_client, model=self.frozen_model,
                max_concurrent=self.config.subcall_concurrency, state_ref=self))
            await self.backend.start(self.proxy.url, self.rollout_id, self.depth)
            await self.backend.load_context(self.info["context"])
            return self
        except BaseException as exc:
            self._record_infrastructure_error("setup", exc)
            await self.close(error=f"setup failed: {type(exc).__name__}: {exc}")
            raise

    async def __aexit__(self, exc_type, exc, tb):
        error = None if exc is None else f"{type(exc).__name__}: {exc}"
        await self.close(error=error)

    async def query(self, prompt, recursive=False):
        task = asyncio.current_task()
        self._active_queries.add(task)
        start = time.perf_counter()
        # Calls after the worker died must not spend the model budget.
        call = SubcallTrace(prompt_chars=len(prompt) if isinstance(prompt, str) else 0,
                            turn_index=max(0, len(self.trace.turns) - 1), depth=self.depth,
                            kind="rlm_query" if recursive else "llm_query")
        if self.trace.turns:
            self.trace.turns[-1].subcalls.append(call)
        try:
            if self.done or self._closed:
                raise ValueError("episode finished")
            if recursive and (not self.config.enable_recursion or self.depth >= self.config.max_depth):
                self.budget.hits.add("max_depth")
                raise ValueError("max_depth exceeded or recursion disabled")
            self.budget.reserve(prompt)
            async with asyncio.timeout(self.config.subcall_timeout_s):
                if recursive:
                    value = await self._recursive_query(prompt)
                else:
                    async with self.budget.semaphore:
                        response = await self.frozen_client.get_response(
                            prompt=[UserMessage(content=prompt)], model=self.frozen_model,
                            tools=None, sampling_args=dict(max_tokens=self.config.subcall_max_tokens),
                            state={"trajectory": []})
                    value = response.message.content
                    if not isinstance(value, str):
                        raise TypeError("frozen client must return text content")
            call.output_chars = len(value)
            return value
        except asyncio.CancelledError:
            call.error = "cancelled"
            raise
        except Exception as exc:
            call.error = f"{type(exc).__name__}: {exc}"
            return f"Error: {call.error}"
        finally:
            call.latency_s = time.perf_counter() - start
            self._active_queries.discard(task)
            for hit in self.budget.hits:
                self.trace.budget_hits[hit] = True

    async def _recursive_query(self, prompt):
        # The caller's subcall reservation covers the first child-root request.
        # Additional child-root turns and all leaves share the same global budget.
        child_info = {**self.info, "task_id": self.info["task_id"] + "/recursive",
                      "context": prompt, "query": "Resolve the task described in context."}
        async with Episode(config=self.config, info=child_info, frozen_client=self.frozen_client,
                           frozen_model=self.frozen_model, log_dir=self.log_path.parent,
                           depth=self.depth + 1, budget=self.budget, proxy=self.proxy,
                           prompt_variant=self.trace.prompt_variant,
                           manual_version=self.trace.manual_version,
                           prompt_builder=self.prompt_builder, system_prompt=self.system_prompt,
                           prompt_config=self.prompt_config,
                           infrastructure_errors=self.infrastructure_errors) as child:
            while not child.done:
                if child.trace.turns:
                    self.budget.reserve(prompt)
                async with self.budget.semaphore:
                    response = await self.frozen_client.get_response(
                        prompt=normalize_messages(child.messages, field_name="recursive.prompt"),
                        model=self.frozen_model, tools=None,
                        sampling_args=self.prompt_config.sampling_args(dict(max_tokens=self.config.max_tokens_per_turn)),
                        state={"trajectory": []})
                tokens = response.message.tokens
                await child.accept(response.message.content or "", tokens.completion_ids if tokens else [])
                child.messages[-2] = response.message.model_dump(exclude_none=True)
            if child.trace.final.error:
                raise ValueError(child.trace.final.error)
            return child.trace.final.value

    async def accept(self, assistant_text, assistant_token_ids):
        if self.done or self._closed:
            raise RuntimeError("episode finished")
        parsed = parse_turn(assistant_text)
        turn = TurnTrace(assistant_text=assistant_text, assistant_token_ids=list(assistant_token_ids),
                         finish_error=parsed.finish_error, ignored_after_finish=parsed.ignored_after_finish)
        self.trace.turns.append(turn)
        prefixes = []
        stage = "execute"
        try:
            for code in parsed.code_blocks:
                turn.code_blocks.append(code)
                result = await self.backend.execute(code)
                details = self.backend.last_details
                remaining = max(0, self.config.stdout_max_chars - sum(map(len, prefixes)))
                prefixes.append(result.stdout[:remaining])
                turn.stdout_raw_chars += details["stdout_raw_chars"]
                turn.stderr_raw_chars += details["stderr_raw_chars"]
                turn.error = turn.error or details.get("error")
            if parsed.finish_type:
                value = parsed.finish_argument
                if parsed.finish_type == "FINAL_VAR":
                    stage = "resolve"
                    resolved = await self.backend.resolve(value)
                    if not resolved["found"]:
                        turn.finish_error = f"protocol-error: FINAL_VAR must name an existing variable: {value!r}"
                    else:
                        value = resolved["value"]
                if not turn.finish_error:
                    self.trace.final = FinalTrace(type=parsed.finish_type, value=value)
                    self.done = True
        except SandboxLimit as exc:
            turn.error = str(exc)
            self.trace.budget_hits[exc.kind] = True
            self.trace.final.error = str(exc)
            self.done = True
        except asyncio.CancelledError:
            turn.error = self.trace.final.error = "cancelled"
            self.done = True
            raise
        except Exception as exc:
            self._record_infrastructure_error(stage, exc)
            turn.error = f"worker error: {type(exc).__name__}: {exc}"
            self.trace.final.error = turn.error
            self.done = True
        observation = truncate_output("".join(prefixes), turn.stdout_raw_chars, self.config.stdout_max_chars)
        turn.stdout_truncated = observation
        if turn.finish_error:
            observation += ("\n" if observation else "") + turn.finish_error
        if self.done and self.trace.final.error:
            observation += ("\n" if observation else "") + self.trace.final.error
        if not self.done and len(self.trace.turns) >= self.config.max_turns:
            self.trace.budget_hits["max_turns"] = True
            self.trace.final.error = "max_turns exceeded without a valid finish"
            self.done = True
        for hit in self.budget.hits:
            self.trace.budget_hits[hit] = True
        self.messages.append(dict(role="assistant", content=assistant_text))
        self.messages.append(dict(role="user", content=observation or "No REPL output. Continue or finish with FINAL / FINAL_VAR."))
        return observation

    async def close(self, error=None):
        if self._closed:
            return
        self._closed = True
        if error:
            self.trace.final.error = self.trace.final.error or error
        elif not self.done:
            self.trace.final.error = self.trace.final.error or "episode closed before finish"
        try:
            await self.backend.stop()
        except BaseException as exc:
            self._record_infrastructure_error("cleanup", exc)
            raise
        finally:
            queries = list(self._active_queries)
            for task in queries:
                task.cancel()
            if queries:
                await asyncio.gather(*queries, return_exceptions=True)
            self.proxy.unregister(self.rollout_id)
            if self._owns_proxy:
                await self.proxy.stop()
            self.trace.timings["episode_s"] = time.perf_counter() - self._started
            for hit in self.budget.hits:
                self.trace.budget_hits[hit] = True
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.log_path.with_suffix(".tmp")
            temporary.write_text(self.trace.model_dump_json(indent=2) + "\n")
            temporary.replace(self.log_path)
