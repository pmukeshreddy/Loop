"""Official RLM/verifiers rollout loop with shared-checkout recursive workers."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
from pathlib import Path
import uuid

from datasets import Dataset
import verifiers as vf
from rlm_train import RLMTrainEnv
from verifiers.utils.message_utils import normalize_messages

from rlm_opsd.harness.protocol import parse_turn
from rlm_opsd.prompts import PromptConfig
from rlm_opsd.prompts.templates import render_named
from .runtime import DockerReplBackend, TaskRuntime
from .tasks import load_pool

PROMPT = Path(__file__).resolve().parents[2] / "student_system.md"


@dataclass
class Episode:
    runtime: TaskRuntime
    max_subcalls: int
    subcalls: int = 0
    semaphores: dict = field(default_factory=dict)


async def verifier_reward(state):
    return float(state["info"].get("grpo_reward", -1.0))


async def solved(state):
    return float(state["info"].get("grpo_reward") == 1)


async def eligible(state):
    return float(state["info"].get("grpo_eligible", False))


class RepositoryEnv(RLMTrainEnv):
    def __init__(self, *, tasks, artifact_dir, max_iterations=30, child_iterations=12,
                 max_subcalls=24, max_depth=2, subcall_concurrency=4, max_subcall_chars=48_000,
                 exec_timeout=120, rollout_timeout=3600, child_timeout=900,
                 session=None, depth=0, **kwargs):
        self.tasks, self.artifact_dir = tasks, Path(artifact_dir)
        self.child_iterations, self.max_subcalls, self.max_depth = child_iterations, max_subcalls, max_depth
        self.subcall_concurrency, self.max_subcall_chars = subcall_concurrency, max_subcall_chars
        self.exec_timeout, self.child_timeout = exec_timeout, child_timeout
        self.session, self.depth = session, depth
        self.prompt_config = PromptConfig.from_yaml()
        if min(max_iterations, child_iterations, max_subcalls, max_depth, subcall_concurrency,
               max_subcall_chars, exec_timeout, rollout_timeout, child_timeout) <= 0:
            raise ValueError("GRPO rollout budgets must be positive")
        rubric = vf.Rubric(funcs=[verifier_reward]) if session is None else vf.Rubric()
        if session is None:
            rubric.add_metric(solved)
            rubric.add_metric(eligible)
        kwargs["score_rollouts"] = session is None
        kwargs.setdefault("timeout_seconds", rollout_timeout if session is None else child_timeout)
        # No alternate agent loop: setup, per-turn execution, and cleanup are hooks
        # on the pinned RLMTrainEnv -> MultiTurnEnv.rollout lifecycle.
        super().__init__(max_iterations=max_iterations, rubric=rubric, **kwargs)

    async def setup_state(self, state):
        state["info"] = dict(state["info"])
        state["grpo_children"] = []
        state["grpo_submitted"] = False
        state["rlm_final_answer"] = None
        state["sampling_args"] = self.prompt_config.sampling_args(
            {**self.sampling_args, **(state.get("sampling_args") or {})})
        try:
            if self.session is None:
                task = self.tasks[state["info"]["task_id"]]
                runtime = TaskRuntime(task, self.artifact_dir / f"{uuid.uuid4().hex}")
                session = Episode(runtime, self.max_subcalls)
                state["grpo_session"] = session
                await runtime.start()
            else:
                session = self.session
                state["grpo_session"] = session
                task = session.runtime.task
            context = dict(repository=task.repo_path, base_commit=task.base_commit,
                           repository_url=task.repository_url, task_id=task.task_id)
            backend = DockerReplBackend(session.runtime,
                lambda path, payload: self.delegate(state, path, payload),
                request_timeout=self.timeout_seconds, exec_timeout=self.exec_timeout)
            state["rlm_backend"] = backend
            await backend.start()
            await backend.load_context(context)
            system = PROMPT.read_text()
            substitutions = dict(context_type="dict", context_total_length=len(json.dumps(context)),
                chunk_info="", context_prefix=json.dumps(context), subcall_max_chars=self.max_subcall_chars,
                stdout_max_chars=20_000, max_turns=self._max_iterations)
            system = render_named(system, substitutions)
            system += ("\n\nThe complete repository and its past Git history are available on disk at "
                       f"{task.repo_path}, checked out at {task.base_commit}. "
                       "Use Python (pathlib, subprocess, etc.) in REPL blocks to inspect, search, edit, "
                       "and run repository commands. Each worker has persistent Python variables.\n"
                       "llm_query(prompt) starts a child RLM with its own REPL and the SAME checkout. "
                       "llm_query_batched(prompts) runs focused children concurrently and returns "
                       "their findings in input order. Pass each child the context and scope it needs; "
                       "coordinate edits to shared files. All children use the current policy.\n"
                       "Store and combine child results in REPL variables. Recover from execution "
                       "errors, check the integrated work, and finish only when ready.\n"
                       "You may also submit using answer['content'] = your_summary followed by "
                       "answer['ready'] = True in a REPL block. ")
            system += ("Your final response returns findings to your parent; edits remain in the shared checkout."
                       if self.depth else
                       "Submission captures the actual repository changes automatically, including new files. "
                       "A separate verifier runs the required tests; success requires all of them to pass.")
            instruction = state["info"].get("child_instruction", task.instruction)
            # Include an episode/branch ID so identical child prompts cannot be
            # accidentally merged by Prime-RL's multi-prefix token interleaver.
            instruction += f"\n\nWorker session: {uuid.uuid4().hex}; depth: {self.depth}."
            state["grpo_history"] = normalize_messages([
                dict(role="system", content=system), dict(role="user", content=instruction)])
            state["prompt"] = list(state["grpo_history"])
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            state["info"]["grpo_infrastructure_error"] = f"{type(exc).__name__}: {exc}"
            state["final_env_response"] = []
        return state

    async def get_prompt_messages(self, state):
        # A trajectory's prompt is immutable after generation. Later REPL
        # observations must not mutate the list retained by that trajectory step.
        return list(state.get("grpo_history", state["prompt"]))

    async def add_trajectory_step(self, state, trajectory_step):
        await super().add_trajectory_step(state, trajectory_step)
        # Execute here, before verifiers checks the turn limit, including the
        # final allowed assistant response. Do not generate a throwaway next turn.
        tokens = trajectory_step.get("tokens")
        if tokens is None or len(tokens["completion_ids"]) != len(tokens["completion_logprobs"]):
            state["info"]["grpo_infrastructure_error"] = "Missing original model token IDs/logprobs"
            state["final_env_response"] = []
            return
        tokens["prompt_mask"] = [False] * len(tokens["prompt_ids"])
        if trajectory_step.get("is_truncated"):
            state["is_truncated"] = True
            state["final_env_response"] = []
            return
        message = trajectory_step["completion"][-1]
        parsed = parse_turn(message.content or "")
        history = state["grpo_history"]
        history.append(message)
        outputs = []
        backend = state["rlm_backend"]
        final = None
        try:
            for code in parsed.code_blocks:
                result = await backend.execute(code)
                outputs.append(result.stdout + ("\n" + result.stderr if result.stderr else ""))
                if result.final_answer is not None:
                    final = result.final_answer
                    break
            if final is None and parsed.finish_type:
                result = await backend.finish(
                    variable=parsed.finish_argument.strip("\"'") if parsed.finish_type == "FINAL_VAR" else None,
                    value=parsed.finish_argument)
                final = result["final_answer"]
            if parsed.finish_error:
                outputs.append(parsed.finish_error)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # A missing FINAL_VAR is recoverable; a dead worker is not.
            if "FINAL_VAR requires" in str(exc):
                outputs.append(f"Protocol error: {exc}")
            else:
                state["info"]["grpo_infrastructure_error"] = f"REPL transport: {exc}"
                state["final_env_response"] = []
                return
        observation = "\n\n".join(outputs)[-40_000:]
        if not observation:
            observation = "Continue with REPL code or submit when finished."
        response = normalize_messages([dict(role="user", content=observation)])
        history.extend(response)
        if final is not None:
            state["grpo_submitted"] = True
            state["rlm_final_answer"] = state["final_answer"] = final
            state["final_env_response"] = response

    async def delegate(self, state, path, payload):
        session = state["grpo_session"]
        if self.depth >= self.max_depth:
            return dict(error="Maximum delegation depth reached; finish this assigned task directly")
        prompts = payload.get("prompts") if path == "llm_query_batched" else [payload.get("prompt")]
        if not isinstance(prompts, list) or any(not isinstance(p, str) or not p.strip() for p in prompts):
            return dict(error="Delegation requires nonempty string prompts")
        if any(len(p) > self.max_subcall_chars for p in prompts):
            return dict(error="Child prompt exceeds max_subcall_chars; select smaller context")
        # Reserve the entire batch before the first await, across all branches.
        if session.subcalls + len(prompts) > session.max_subcalls:
            return dict(error="Episode subcall budget exhausted")
        session.subcalls += len(prompts)
        sem = session.semaphores.setdefault(self.depth, asyncio.Semaphore(self.subcall_concurrency))

        async def run(prompt):
            async with sem:
                child = RepositoryEnv(tasks=self.tasks, artifact_dir=self.artifact_dir,
                    max_iterations=self.child_iterations, child_iterations=self.child_iterations,
                    max_subcalls=self.max_subcalls, max_depth=self.max_depth,
                    subcall_concurrency=self.subcall_concurrency, max_subcall_chars=self.max_subcall_chars,
                    exec_timeout=self.exec_timeout, child_timeout=self.child_timeout,
                    session=session, depth=self.depth + 1, max_seq_len=self.max_seq_len,
                    dataset=lambda: self.get_dataset())
                child_state = await child.rollout(
                    input=dict(prompt=[dict(role="user", content=prompt)], answer="",
                               info=dict(task_id=session.runtime.task.task_id, child_instruction=prompt)),
                    client=state["client"], model=state["model"], sampling_args=state["sampling_args"])
                if child_state["info"].get("grpo_eligible"):
                    state["grpo_children"].extend(child_state["trajectory"])
                    return str(child_state["final_answer"])
                return "Child did not submit within its budgets; inspect the shared files before retrying."

        # TaskGroup cancels and drains siblings if one fails. No editing child
        # remains alive while the parent captures its submission.
        async with asyncio.TaskGroup() as group:
            pending = [group.create_task(run(prompt)) for prompt in prompts]
        results = [task.result() for task in pending]
        return dict(responses=results) if path == "llm_query_batched" else dict(response=results[0])

    @vf.cleanup
    async def cleanup_rlm(self, state):
        info = state["info"]
        session = state.get("grpo_session")
        info["grpo_eligible"] = bool(state.get("grpo_submitted") and not (
            state.get("timed_out") or state.get("is_truncated") or state.get("prompt_too_long")
            or state.get("error") or info.get("grpo_infrastructure_error")))
        info["grpo_reward"] = -1.0
        try:
            if self.session is None and info["grpo_eligible"]:
                try:
                    # Quiesce every worker/process group before taking the patch,
                    # including background commands launched by generated Python.
                    await asyncio.gather(*(backend.stop() for backend in list(session.runtime.backends)))
                    patch = await session.runtime.snapshot()
                    grade = await session.runtime.grade(patch)
                    info["grpo_reward"] = 1.0 if grade["reward"] == 1 else -1.0
                    info["grpo_grade"] = grade
                except ValueError as exc:
                    # A submitted over-size patch is an invalid model solution.
                    info["grpo_invalid_submission"] = str(exc)
                except Exception as exc:
                    info["grpo_eligible"] = False
                    info["grpo_infrastructure_error"] = f"{type(exc).__name__}: {exc}"
            if info["grpo_eligible"]:
                state["trajectory"].extend(state.get("grpo_children", []))
            else:
                # Keep rollout metadata for monitoring, but no token contributes
                # to training or the valid-rollout advantage baseline.
                for step in state.get("trajectory", []):
                    if step.get("tokens"):
                        step["tokens"]["completion_mask"] = [False] * len(step["tokens"]["completion_ids"])
            if self.session is None and session:
                info["grpo_subcalls"] = session.subcalls
                info["grpo_artifact_dir"] = str(session.runtime.artifact_dir)
                (session.runtime.artifact_dir / "result.json").write_text(
                    json.dumps(dict(info=info, submitted=state.get("grpo_submitted", False)), indent=2) + "\n")
        finally:
            if self.session is None and session:
                await session.runtime.close()
            elif state.get("rlm_backend"):
                await state["rlm_backend"].stop()
            state["rlm_backend"] = None


def load_environment(*, manifest_path, split="train", artifact_dir="reports/grpo/trajectories", **kwargs):
    if split not in {"train", "dev"}:
        raise ValueError("Only the explicit train/dev pool may be used by the GRPO environment")
    forbidden = {"dataset", "eval_dataset", "system_prompt", "rubric", "session", "depth",
                 "sub_model", "sub_llm_fn", "sub_llm_fn_batched", "custom_system_prompt"} & kwargs.keys()
    if forbidden:
        raise ValueError(f"Cannot override the shared-policy GRPO contract: {sorted(forbidden)}")
    if kwargs.pop("score_rollouts", True) is not True:
        raise ValueError("GRPO requires verifier scoring")
    tasks = [task for task in load_pool(manifest_path) if task.split == split]
    if not tasks:
        raise ValueError(f"GRPO pool has no {split} tasks")
    return RepositoryEnv(tasks={task.task_id: task for task in tasks}, artifact_dir=artifact_dir,
        dataset=Dataset.from_list([task.row(i) for i, task in enumerate(tasks)]), **kwargs)
