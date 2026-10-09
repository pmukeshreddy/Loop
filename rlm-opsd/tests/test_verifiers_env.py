import asyncio
import json

import pytest


@pytest.mark.parametrize("max_seq_len,trainer_ids", [(None, [91, 92]), (2, [91])])
def test_real_verifiers_rollout_processes_last_turn_and_preserves_ids(tmp_path, max_seq_len, trainer_ids):
    from datasets import Dataset
    from rlm_train import RLMTrainEnv
    from verifiers.clients import OpenAIChatCompletionsClient
    from verifiers.types import ClientConfig, Response, ResponseMessage, ResponseTokens
    from rlm_opsd.harness import HarnessConfig, RLMOpsdEnv

    class RootClient(OpenAIChatCompletionsClient):
        def __init__(self):
            super().__init__(ClientConfig(api_base_url="http://127.0.0.1:1/v1", max_retries=0))
            self.requests = []

        async def get_response(self, **request):
            self.requests.append(request)
            return Response(id="fixture", created=0, model=request["model"], message=ResponseMessage(
                content='```repl\nresult = len(context)\n```\nFINAL_VAR(result)',
                finish_reason="stop", is_truncated=False,
                tokens=ResponseTokens(prompt_ids=[1], prompt_mask=[0],
                                      completion_ids=[91, 92], completion_mask=[1, 1],
                                      completion_logprobs=[-0.1, -0.2])))

    async def run():
        root = RootClient()
        frozen = RootClient()
        cfg = HarnessConfig(max_turns=1, max_tokens_per_turn=96, prefix_chars=0)
        env = RLMOpsdEnv(config=cfg, frozen_client=frozen, frozen_model="initial",
                         log_dir=tmp_path, max_seq_len=max_seq_len,
                         dataset=Dataset.from_list([dict(question="query", answer="")]))
        assert isinstance(env, RLMTrainEnv) and not env.score_rollouts
        try:
            state = await env.rollout(input=dict(example_id=0, prompt=[dict(role="user", content="query")],
                 info=dict(task_id="one", family="test", domain="test", tags=[],
                           context="SUPER_SECRET", query="query")), client=root, model="trainable",
                 sampling_args=dict(max_tokens=10000, temperature=0.0))
            assert len(root.requests) == 1 and not frozen.requests
            request = root.requests[0]
            assert request["sampling_args"]["max_tokens"] == 96
            assert request["sampling_args"]["extra_body"]["chat_template_kwargs"]["enable_thinking"] is True
            assert request["prompt"][1].content == "query"
            assert "You are answering a query using a Python REPL." in request["prompt"][0].content
            assert "SUPER_SECRET" not in str(request["prompt"])
            assert state["final_answer"] == "12"
            assert state["trajectory"][0]["tokens"]["completion_ids"] == trainer_ids
            raw = json.loads(next(tmp_path.glob("*.json")).read_text())
            assert raw["turns"][0]["assistant_token_ids"] == [91, 92]
            assert raw["manual_version"] == "manual_v1"
            assert raw["final"]["value"] == "12" and not raw["budget_hits"]["max_turns"]
        finally:
            await env.teardown_rlm()
            await root.close()
            await frozen.close()
    asyncio.run(run())


def test_loader_http_frozen_client_and_multiturn_reasoning(tmp_path):
    from aiohttp import web
    from datasets import Dataset
    import verifiers as vf
    from verifiers.clients import OpenAIChatCompletionsClient
    from verifiers.types import ClientConfig, Response, ResponseMessage

    class Root(OpenAIChatCompletionsClient):
        def __init__(self):
            super().__init__(ClientConfig(api_base_url="http://127.0.0.1:1/v1", max_retries=0))
            self.requests = []

        async def get_response(self, **request):
            self.requests.append(request)
            if len(self.requests) == 1:
                text, reasoning = '```repl\nanswer = llm_query("classify this")\nprint(answer)\n```', "Inspect then delegate."
            else:
                text, reasoning = 'FINAL_VAR(answer)', "Use the stored result."
            return Response(id="root", created=0, model=request["model"], message=ResponseMessage(
                content=text, reasoning_content=reasoning, finish_reason="stop", is_truncated=False))

    async def run():
        requests = []
        async def respond(request):
            body = await request.json()
            requests.append(body)
            return web.json_response(dict(id="leaf", object="chat.completion", created=0,
                model=body["model"], choices=[dict(index=0, finish_reason="stop",
                                                 message=dict(role="assistant", content="class-A"))]))
        app = web.Application()
        app.router.add_post("/v1/chat/completions", respond)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        root = Root()
        env = None
        try:
            env = vf.load_environment("rlm_opsd", config=dict(max_turns=2, prefix_chars=0),
                frozen_client=dict(api_base_url=f"http://127.0.0.1:{port}/v1", api_key_var="M1_TEST_UNUSED_KEY", max_retries=0),
                frozen_model="frozen-v0", log_dir=tmp_path,
                dataset=Dataset.from_list([dict(question="query", answer="")]))
            state = await env.rollout(input=dict(example_id=0, prompt=[dict(role="user", content="query")],
                info=dict(task_id="http", family="test", domain="test", tags=[], context="SECRET", query="query")),
                client=root, model="trainable")
            assert state["final_answer"] == "class-A"
            assert len(requests) == 1 and requests[0]["model"] == "frozen-v0"
            assert requests[0]["messages"] == [dict(role="user", content="classify this")]
            previous = next(m for m in root.requests[1]["prompt"] if m.role == "assistant")
            assert previous.reasoning_content == "Inspect then delegate."
            assert "SECRET" not in str(root.requests[1]["prompt"])
        finally:
            if env:
                await env.teardown_rlm()
            await root.close()
            await runner.cleanup()
    asyncio.run(run())
