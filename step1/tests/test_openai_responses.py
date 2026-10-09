"""Exercise the real SDK and RLM; replace only OpenAI's HTTP transport."""

import asyncio
import json

import httpx
import openai
import pytest
from rlm import RLM
from rlm.clients import get_client
from rlm.logger import RLMLogger


@pytest.fixture
def responses_api(monkeypatch):
    requests, replies = [], []
    constructor = openai.OpenAI

    def respond(request):
        assert request.url == "https://api.openai.com/v1/responses"
        payload = json.loads(request.content)
        requests.append(payload)
        assert replies, "Unexpected model request"
        reply = replies.pop(0)
        if isinstance(reply, list):
            events = reply
        elif isinstance(reply, dict):
            events = [reply]
        else:
            events = [
                {
                    "type": "response.completed",
                    "response": {
                        "id": "resp_test",
                        "object": "response",
                        "created_at": 0,
                        "model": payload["model"],
                        "status": "completed",
                        "output": [
                            {
                                "id": "msg_test",
                                "type": "message",
                                "role": "assistant",
                                "status": "completed",
                                "content": [
                                    {
                                        "type": "output_text",
                                        "text": reply,
                                        "annotations": [],
                                    }
                                ],
                            }
                        ],
                        "usage": {
                            "input_tokens": 10,
                            "output_tokens": 5,
                            "total_tokens": 15,
                        },
                    },
                }
            ]
        body = "".join("data: " + json.dumps(event) + "\n\n" for event in events)
        return httpx.Response(
            200, text=body, headers={"content-type": "text/event-stream"}
        )

    def create(**kwargs):
        return constructor(
            **kwargs, http_client=httpx.Client(transport=httpx.MockTransport(respond))
        )

    monkeypatch.setattr(openai, "OpenAI", create)
    return requests, replies


def client():
    return get_client(
        "openai_responses", {"model_name": "test-model", "api_key": "test-token"}
    )


def test_responses_preserves_history_and_returns_model_text(responses_api):
    requests, replies = responses_api
    replies.append("```repl\nprint(context)\n```")
    history = [
        {"role": "system", "content": "Use the REPL."},
        {"role": "user", "content": "Inspect."},
        {"role": "assistant", "content": "Earlier response"},
        {"role": "user", "content": "Real feedback"},
    ]
    model = client()
    assert model.completion(history) == "```repl\nprint(context)\n```"
    assert history[0]["role"] == "system"  # Conversion must not mutate RLM history.
    assert requests[0]["input"] == [
        {"role": "developer", "content": "Use the REPL."},
        *history[1:],
    ]
    assert requests[0]["store"] is False and requests[0]["stream"] is True
    assert "tools" not in requests[0]
    assert model.get_last_usage().total_output_tokens == 5


@pytest.mark.parametrize(
    "event",
    [
        {"type": "response.output_text.delta", "delta": "unfinished"},
        {"type": "response.failed", "response": {"status": "failed"}},
        {"type": "response.incomplete", "response": {"status": "incomplete"}},
    ],
)
def test_unfinished_response_is_not_a_completion(responses_api, event):
    _, replies = responses_api
    replies.append(event)
    with pytest.raises(RuntimeError, match="complet|failed|incomplete"):
        client().completion("Return a value")


def test_async_completion_preserves_usage_for_the_calling_handler(responses_api):
    _, replies = responses_api
    replies.append("42")
    model = client()
    assert asyncio.run(model.acompletion("Compute")) == "42"
    assert model.get_last_usage().total_input_tokens == 10


def test_subcall_cannot_silently_switch_comparison_model(responses_api):
    _, replies = responses_api
    replies.append("This must not be requested")
    with pytest.raises(ValueError, match="model"):
        client().completion("Check the patch", model="different-model")


def test_recursive_client_clone_cannot_change_fixed_model():
    with pytest.raises(ValueError, match="model"):
        get_client(
            "openai_responses",
            {
                "api_key": "test",
                "model_name": "different-model",
                "fixed_model": "test-model",
            },
        )


def test_usage_audit_includes_official_depth_capped_recursive_call(
    responses_api, tmp_path
):
    _, replies = responses_api
    replies.extend(
        [
            "```repl\nprint(context)\ncheck = rlm_query('Return 42')\nprint(check)\n```",
            "42",
            "```repl\nanswer['content'] = check\nanswer['ready'] = True\n```",
        ]
    )
    path = tmp_path / "usage.jsonl"
    with RLM(
        backend="openai_responses",
        backend_kwargs={
            "model_name": "test-model",
            "api_key": "test",
            "usage_log_path": str(path),
        },
        environment="local",
        max_depth=1,
        max_iterations=3,
    ) as rlm:
        assert rlm.completion("fixture").response == "42"
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(records) == 3
    assert sum(row["input_tokens"] for row in records) == 30
    assert sum(row["output_tokens"] for row in records) == 15


def test_completed_oauth_stream_uses_text_deltas_when_final_output_is_empty(
    responses_api,
):
    _, replies = responses_api
    replies.append(
        [
            {"type": "response.output_text.delta", "output_index": 0, "delta": "4"},
            {"type": "response.output_text.delta", "output_index": 0, "delta": "2"},
            {
                "type": "response.completed",
                "response": {
                    "id": "resp_test",
                    "object": "response",
                    "created_at": 0,
                    "model": "test-model",
                    "status": "completed",
                    "output": [],
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "total_tokens": 15,
                    },
                },
            },
        ]
    )
    assert client().completion("Return 42") == "42"


def test_all_message_text_reaches_rlm_and_original_phases_are_replayed(responses_api):
    requests, replies = responses_api
    commentary = "```repl\nprint('inspect first')\n```"
    final = "```repl\nprint(context)\n```"
    replies.append(
        [
            {
                "type": "response.output_item.added",
                "output_index": 0,
                "item": {
                    "id": "commentary",
                    "type": "message",
                    "role": "assistant",
                    "phase": "commentary",
                    "content": [],
                },
            },
            {
                "type": "response.output_text.delta",
                "output_index": 0,
                "delta": commentary,
            },
            {
                "type": "response.output_item.added",
                "output_index": 1,
                "item": {
                    "id": "final",
                    "type": "message",
                    "role": "assistant",
                    "phase": "final_answer",
                    "content": [],
                },
            },
            {"type": "response.output_text.delta", "output_index": 1, "delta": final},
            {
                "type": "response.completed",
                "response": {
                    "id": "resp_test",
                    "object": "response",
                    "created_at": 0,
                    "model": "test-model",
                    "status": "completed",
                    "output": [],
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "total_tokens": 15,
                    },
                },
            },
        ]
    )
    model = client()
    response = model.completion("Inspect")
    assert response == commentary + "\n\n" + final
    replies.append("42")
    model.completion(
        [
            {"role": "assistant", "content": response},
            {"role": "user", "content": "Feedback"},
        ]
    )
    assert requests[1]["input"] == [
        {"role": "assistant", "content": commentary, "phase": "commentary"},
        {"role": "assistant", "content": final, "phase": "final_answer"},
        {"role": "user", "content": "Feedback"},
    ]


def test_commentary_only_program_keeps_its_phase_in_the_next_turn(responses_api):
    requests, replies = responses_api
    code = "```repl\nprint(context)\n```"
    replies.extend(
        [
            [
                {
                    "type": "response.output_item.added",
                    "output_index": 0,
                    "item": {
                        "id": "commentary",
                        "type": "message",
                        "role": "assistant",
                        "phase": "commentary",
                        "content": [],
                    },
                },
                {
                    "type": "response.output_text.delta",
                    "output_index": 0,
                    "delta": code,
                },
                {
                    "type": "response.output_item.added",
                    "output_index": 1,
                    "item": {
                        "id": "empty_final",
                        "type": "message",
                        "role": "assistant",
                        "phase": "final_answer",
                        "content": [],
                    },
                },
                {"type": "response.output_text.delta", "output_index": 1, "delta": ""},
                {
                    "type": "response.completed",
                    "response": {
                        "id": "resp_test",
                        "object": "response",
                        "created_at": 0,
                        "model": "test-model",
                        "status": "completed",
                        "output": [],
                        "usage": {
                            "input_tokens": 10,
                            "output_tokens": 5,
                            "total_tokens": 15,
                        },
                    },
                },
            ],
            "42",
        ]
    )
    model = client()
    response = model.completion("Inspect")
    assert response == code
    assert (
        model.completion(
            [
                {"role": "assistant", "content": response},
                {"role": "user", "content": "Real output"},
            ]
        )
        == "42"
    )
    assert requests[1]["input"][0]["phase"] == "commentary"


def test_phase1_runner_submits_and_verifies_a_real_rlm_patch(responses_api, tmp_path):
    from step1 import run_eval

    _, replies = responses_api
    patch = "--- a/total.py\n+++ b/total.py\n@@ -1,2 +1,2 @@\n def total(values):\n-    return sum(values)\n+    return sum(v for v in values if v is not None)\n"
    replies.extend(
        [
            "```repl\nsource = context['total.py']\nprint(llm_query(source))\n```",
            "Ignore None entries.",
            "```repl\nreview = rlm_query('Check the None filtering approach')\nprint(review)\n```",
            "```repl\nanswer['content'] = 'Valid'\nanswer['ready'] = True\n```",
            f"```repl\nassert source.startswith('def total')\nanswer['content'] = {patch!r}\nanswer['ready'] = True\n```",
        ]
    )
    actual, evidence = run_eval.complete_rlm("test-model", "test", tmp_path, 30)
    assert actual == patch
    assert all(
        evidence[k]
        for k in ["repl_executed", "llm_query_called", "rlm_query_called", "submitted"]
    )
    assert run_eval.verify_patch(actual, tmp_path / "grade")[0]


def test_official_rlm_executes_state_feedback_and_both_subcalls(
    responses_api, tmp_path
):
    requests, replies = responses_api
    replies.extend(
        [
            "```repl\nn = context['start']\nprint(n)\n```",
            "```repl\nprint(1 / 0)\n```",
            "```repl\nplain = llm_query('Return 2')\nprint(plain)\n```",
            "2",
            "```repl\nchild = rlm_query('Return 3')\nprint(child)\n```",
            "```repl\nassert context == 'Return 3'\nanswer['content'] = '3'\nanswer['ready'] = True\n```",
            "```repl\nanswer['content'] = str(n + int(plain) + int(child))\nanswer['ready'] = True\n```",
        ]
    )
    with RLM(
        backend="openai_responses",
        backend_kwargs={"model_name": "test-model", "api_key": "test"},
        environment="local",
        max_depth=2,
        max_iterations=6,
        logger=RLMLogger(log_dir=str(tmp_path)),
    ) as rlm:
        result = rlm.completion({"start": 37}, root_prompt="Exercise the connection")
    assert result.response == "42"
    assert not replies
    assert {r["model"] for r in requests} == {"test-model"}
    assert requests[3]["input"] == [{"role": "user", "content": "Return 2"}]
    assert "ZeroDivisionError" in json.dumps(requests[2]["input"])
    assert result.metadata["iterations"][-1]["final_answer"] == "42"
