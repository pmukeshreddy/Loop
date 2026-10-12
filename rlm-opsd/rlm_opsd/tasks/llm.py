"""OpenAI Responses access for generation roles and the reference RLM solver.

Credentials come from the project's step-1 OAuth module (`step1.auth`); no token
is read from or written to this package. Every completed request is appended to
a usage log so generation cost is auditable.
"""
import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
import random
import re
import sys
import threading
import time
from types import SimpleNamespace

import openai

PROJECT_ROOT = Path(__file__).resolve().parents[3]
_token_lock = threading.Lock()


def _credential(auth):
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.append(str(PROJECT_ROOT))
    from step1.auth import credential
    # Refreshing rewrites the session file; serialize it across worker threads.
    with _token_lock:
        return credential(auth, min_validity=900)


@dataclass(frozen=True)
class Completion:
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    latency_s: float


class TransientError(RuntimeError):
    pass


class ResponsesLLM:
    """Thread-safe synchronous client; `acomplete` runs it in a worker thread."""

    def __init__(self, *, model, reasoning_effort='medium', auth='chatgpt', timeout_s=600,
                 max_attempts=6, usage_log=None):
        self.model, self.reasoning_effort, self.auth = model, reasoning_effort, auth
        self.timeout_s, self.max_attempts = timeout_s, max_attempts
        self.usage_log = Path(usage_log) if usage_log else None
        self._log_lock = threading.Lock()

    def _inputs(self, messages):
        if isinstance(messages, str):
            messages = [dict(role='user', content=messages)]
        inputs = []
        for message in messages:
            role, content = message['role'], message['content']
            # ChatGPT-plan inference accepts developer instructions, not system items.
            inputs.append(dict(role='developer' if role == 'system' else role, content=content))
        return inputs

    def _once(self, inputs, effort, model):
        start = time.perf_counter()
        client = openai.OpenAI(api_key=_credential(self.auth), base_url='https://api.openai.com/v1',
                               timeout=self.timeout_s, max_retries=0)
        try:
            with client.responses.create(model=model, input=inputs, store=False, stream=True,
                                         reasoning={'effort': effort}) as stream:
                deltas = {}
                for event in stream:
                    if event.type == 'response.output_text.delta':
                        deltas.setdefault(getattr(event, 'output_index', 0), []).append(event.delta)
                    elif event.type in ('response.failed', 'response.incomplete', 'error'):
                        raise TransientError(f'response did not complete: {event.type}')
                    elif event.type == 'response.completed':
                        response = event.response
                        if not deltas:
                            for index, item in enumerate(response.output):
                                if item.type == 'message':
                                    deltas[index] = [p.text for p in item.content if p.type == 'output_text']
                        text = '\n\n'.join(''.join(deltas[i]) for i in sorted(deltas) if ''.join(deltas[i]))
                        if response.status != 'completed' or not text or response.usage is None:
                            raise TransientError('response completed without usable text or usage')
                        return Completion(text, response.usage.input_tokens, response.usage.output_tokens,
                                          model, time.perf_counter() - start)
        finally:
            client.close()
        raise TransientError('stream ended before response.completed')

    def complete(self, messages, *, effort=None, model=None, role='unspecified'):
        inputs = self._inputs(messages)
        effort, model = effort or self.reasoning_effort, model or self.model
        delay = 5.0
        for attempt in range(1, self.max_attempts + 1):
            try:
                result = self._once(inputs, effort, model)
                self._log(role, result, attempt)
                return result
            except (TransientError, openai.APIConnectionError, openai.APITimeoutError,
                    openai.RateLimitError, openai.InternalServerError) as exc:
                if attempt == self.max_attempts:
                    raise RuntimeError(f'{role}: model request failed after {attempt} attempts: '
                                       f'{type(exc).__name__}') from exc
                retry_after = None
                response = getattr(exc, 'response', None)
                if response is not None:
                    try:
                        retry_after = float(response.headers.get('retry-after', ''))
                    except ValueError:
                        retry_after = None
                time.sleep(retry_after or delay * (1 + random.random()))
                delay = min(delay * 2, 120)
            except openai.APIStatusError as exc:
                # 4xx other than rate limits is a request bug; do not retry blindly.
                raise RuntimeError(f'{role}: model request rejected with HTTP {exc.status_code}') from exc
            except openai.APIError as exc:
                # Errors reported inside a stream (e.g. "servers are overloaded") carry no status code.
                if attempt == self.max_attempts:
                    raise RuntimeError(f'{role}: model stream failed after {attempt} attempts: {exc}') from exc
                time.sleep(delay * (1 + random.random()))
                delay = min(delay * 2, 120)

    async def acomplete(self, messages, **kwargs):
        return await asyncio.to_thread(self.complete, messages, **kwargs)

    def _log(self, role, result, attempt):
        if self.usage_log is None:
            return
        row = dict(time=time.time(), role=role, model=result.model, input_tokens=result.input_tokens,
                   output_tokens=result.output_tokens, latency_s=round(result.latency_s, 3), attempt=attempt)
        with self._log_lock:
            self.usage_log.parent.mkdir(parents=True, exist_ok=True)
            with self.usage_log.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(row) + '\n')


class HarnessClient:
    """Minimal verifiers-client surface used by `rlm_opsd.harness.Episode` sub-calls."""

    def __init__(self, llm, *, effort, role):
        self.llm, self.effort, self.role = llm, effort, role

    async def get_response(self, *, prompt, model, tools=None, sampling_args=None, state=None):
        messages = [dict(role=getattr(m, 'role', None) or m['role'],
                         content=getattr(m, 'content', None) if not isinstance(m, dict) else m['content'])
                    for m in prompt]
        result = await self.llm.acomplete(messages, effort=self.effort, model=model, role=self.role)
        return SimpleNamespace(message=SimpleNamespace(content=result.text, tokens=None))

    async def close(self):
        return None


_FENCE = re.compile(r'```(?:json)?\s*\n(.*?)\n```', re.S)


def parse_json_block(text):
    """Return the last fenced JSON value, or the whole text when it is bare JSON."""
    blocks = _FENCE.findall(text)
    for candidate in reversed(blocks or [text.strip()]):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise ValueError('response contains no parseable JSON block')
