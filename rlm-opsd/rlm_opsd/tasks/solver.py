"""Reference executions through the project's RLM harness (SPEC §2).

The root turn loop mirrors `Episode._recursive_query`: the root model's text is
handed to `Episode.accept`, which executes ```repl``` blocks in the sandboxed
worker, routes `llm_query` to the sub-call client and parses FINAL/FINAL_VAR.
The system prompt is the OPSD teacher variant (student API + task-independent
manual) followed by the solver skill. None of this enters the student prompt
or the teacher manual used for OPSD.
"""
from pathlib import Path
import re

from rlm_opsd.harness.config import HarnessConfig
from rlm_opsd.harness.episode import Episode
from rlm_opsd.harness.sandbox import SandboxBackend
from rlm_opsd.prompts import PromptBuilder, PromptConfig

from .llm import HarnessClient

_FIRST_BLOCK = re.compile(r'^ {0,3}```repl[^\n]*\n.*?^ {0,3}```[ \t]*$', re.S | re.M)


def single_step(text):
    """Keep prose and the first ```repl``` block; drop later blocks and any finish.

    Reference executions must observe each block's output before acting on it,
    so a finish counts only in a message without unexecuted code.
    """
    match = _FIRST_BLOCK.search(text)
    return (text[:match.end()], True) if match and text[match.end():].strip() else (text, False)


# Reference executions run many episodes concurrently on one event loop; the
# limits are unchanged, only checked less often than in training rollouts.
REFERENCE_POLL_INTERVAL_S = 0.5


async def solve(*, task_id, family, tags, query, context, llm, root_effort, subcall_effort,
                harness_config, solver_skill, log_dir, role='solver', root_model=None):
    SandboxBackend.poll_interval_s = REFERENCE_POLL_INTERVAL_S
    config = harness_config if isinstance(harness_config, HarnessConfig) else HarnessConfig.from_yaml(harness_config)
    builder = PromptBuilder.load()
    info = dict(task_id=task_id, family=family, domain='deepswe', tags=list(tags), query=query, context=context)
    subcalls = HarnessClient(llm, effort=subcall_effort, role=role + '_subcall')
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    async with Episode(config=config, info=info, frozen_client=subcalls, frozen_model=llm.model, log_dir=log_dir,
                       prompt_variant='teacher', prompt_builder=builder,
                       prompt_config=PromptConfig.from_yaml()) as episode:
        episode.messages[0] = dict(role='system', content=episode.messages[0]['content'] + '\n\n' + solver_skill)
        truncated = 0
        while not episode.done:
            result = await llm.acomplete(list(episode.messages), effort=root_effort, role=role + '_root',
                                         model=root_model)
            text, cut = single_step(result.text)
            truncated += cut
            await episode.accept(text, [])
    trace = episode.trace
    return dict(trajectory_path=str(episode.log_path), final_type=trace.final.type, final_value=trace.final.value,
                final_error=trace.final.error, turns=len(trace.turns), truncated_turns=truncated,
                subcalls=sum(len(t.subcalls) for t in trace.turns), budget_hits=trace.budget_hits,
                manual_version=trace.manual_version, root_model=root_model or llm.model, subcall_model=llm.model)
