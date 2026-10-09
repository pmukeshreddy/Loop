"""Plain model completions via OpenAI's public streaming Responses API."""

import asyncio
import json
import threading
from collections import defaultdict
from typing import Any

import openai

from rlm.clients.base_lm import BaseLM
from rlm.core.types import ModelUsageSummary, UsageSummary


class OpenAIResponsesClient(BaseLM):
    def __init__(
        self,
        model_name: str,
        api_key: str,
        timeout: float = 60,
        reasoning_effort: str = "medium",
        fixed_model: str | None = None,
        usage_log_path: str | None = None,
    ):
        if fixed_model is not None and model_name != fixed_model:
            raise ValueError("Recursive calls must use the fixed comparison model")
        super().__init__(model_name=model_name, timeout=timeout)
        self.api_key = api_key
        self.reasoning_effort = reasoning_effort
        self.usage_log_path = usage_log_path
        self.usage: dict[str, ModelUsageSummary] = defaultdict(lambda: ModelUsageSummary(0, 0, 0))
        self.lock = threading.Lock()
        self.last = threading.local()
        self.response_messages: dict[str, list[dict[str, str]]] = {}

    def completion(self, prompt: str | list[dict[str, Any]], model: str | None = None) -> str:
        if model is not None and model != self.model_name:
            raise ValueError("All phase-one calls must use the selected model")
        messages = [{"role": "user", "content": prompt}] if isinstance(prompt, str) else prompt
        # ChatGPT-plan inference accepts developer instructions, not system items.
        inputs = []
        for message in messages:
            item = dict(message)
            if item["role"] == "system":
                item["role"] = "developer"
            elif item["role"] == "assistant" and item["content"] in self.response_messages:
                inputs.extend(self.response_messages[item["content"]])
                continue
            inputs.append(item)
        selected = model or self.model_name
        with openai.OpenAI(
            api_key=self.api_key,
            base_url="https://api.openai.com/v1",
            timeout=self.timeout,
            max_retries=0,
        ) as client:
            with client.responses.create(
                model=selected,
                input=inputs,
                store=False,
                stream=True,
                reasoning={"effort": self.reasoning_effort},
            ) as stream:
                deltas: dict[int, list[str]] = defaultdict(list)
                phases: dict[int, str | None] = {}
                for event in stream:
                    if event.type == "response.output_text.delta":
                        deltas[getattr(event, "output_index", 0)].append(event.delta)
                    if event.type in {"response.output_item.added", "response.output_item.done"}:
                        phases[event.output_index] = getattr(event.item, "phase", None)
                    if event.type in {"response.failed", "response.incomplete", "error"}:
                        raise RuntimeError(f"OpenAI response did not complete: {event.type}")
                    if event.type == "response.completed":
                        response = event.response
                        if not deltas:
                            for index, item in enumerate(response.output):
                                if item.type == "message":
                                    phases[index] = getattr(item, "phase", None)
                                    deltas[index] = [
                                        p.text for p in item.content if p.type == "output_text"
                                    ]
                        # BaseLM returns text; retain message boundaries and phases
                        # separately so RLM's next history replay is lossless.
                        output_messages = []
                        for index in sorted(deltas):
                            content = "".join(deltas[index])
                            if content:
                                item = {"role": "assistant", "content": content}
                                if phases.get(index) is not None:
                                    item["phase"] = phases[index]
                                output_messages.append(item)
                        text = "\n\n".join(item["content"] for item in output_messages)
                        if response.status != "completed" or not text:
                            raise RuntimeError("OpenAI response completed without usable text")
                        if response.usage is None:
                            raise RuntimeError("OpenAI response completed without usage")
                        last = ModelUsageSummary(
                            1, response.usage.input_tokens, response.usage.output_tokens
                        )
                        self.last.usage = last
                        if self.usage_log_path:
                            with open(self.usage_log_path, "a") as log:
                                log.write(
                                    json.dumps(
                                        {
                                            "model": selected,
                                            "input_tokens": last.total_input_tokens,
                                            "output_tokens": last.total_output_tokens,
                                        }
                                    )
                                    + "\n"
                                )
                        with self.lock:
                            self.response_messages[text] = output_messages
                            total = self.usage[selected]
                            total.total_calls += 1
                            total.total_input_tokens += last.total_input_tokens
                            total.total_output_tokens += last.total_output_tokens
                        return text
        raise RuntimeError("OpenAI stream ended before response.completed")

    async def acompletion(
        self, prompt: str | list[dict[str, Any]], model: str | None = None
    ) -> str:
        def run():
            text = self.completion(prompt, model)
            return text, self.get_last_usage()

        text, usage = await asyncio.to_thread(run)
        self.last.usage = usage
        return text

    def get_usage_summary(self) -> UsageSummary:
        with self.lock:
            return UsageSummary(
                {model: ModelUsageSummary(**vars(usage)) for model, usage in self.usage.items()}
            )

    def get_last_usage(self) -> ModelUsageSummary:
        return getattr(self.last, "usage", ModelUsageSummary(0, 0, 0))
