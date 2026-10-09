"""M3 contracts. Expected outputs use hand-written text/IDs, not another builder."""
import asyncio
import hashlib
import json
from pathlib import Path
import shutil

import pytest


def test_named_render_preserves_code_braces_and_never_expands_inserted_text():
    from rlm_opsd.prompts import render_named

    source = '{max_turns}|{context_prefix}|{"id": 3}|{}|{buyer}|{0,80}'
    assert render_named(source, {'max_turns': 7, 'context_prefix': '{max_turns}'}) == (
        '7|{max_turns}|{"id": 3}|{}|{buyer}|{0,80}')
    with pytest.raises(ValueError, match='stdout_max_chars'):
        render_named('{stdout_max_chars}', {})


@pytest.mark.parametrize('context,description', [
    ('abcHIDDEN', 'str with 9 total characters'),
    (['ab', 'cHIDDEN'], 'list with 9 total characters, split into 2 chunks with lengths [2, 7]'),
    ([], 'list with 0 total characters, split into 0 chunks with lengths []'),
])
def test_x_y_are_exact_api_plus_manual_and_identical_query(context, description):
    from rlm_opsd.harness import HarnessConfig
    from rlm_opsd.prompts import PromptBuilder

    pair = PromptBuilder.load().build(query='Find {query} 🦉', context=context,
        config=HarnessConfig(prefix_chars=3, max_turns=7))
    student, teacher = pair.messages('student'), pair.messages('teacher')
    assert student[1] == teacher[1] == {'role': 'user', 'content': 'Find {query} 🦉'}
    assert len(student) == len(teacher) == 2
    assert student[0]['role'] == teacher[0]['role'] == 'system'
    assert teacher[0]['content'] == student[0]['content'] + '\n\n' + pair.manual
    assert description in student[0]['content']
    assert 'at most 7 turns' in student[0]['content']
    assert 'HIDDEN' not in str(teacher)
    assert 'chunk_chars = 16000' in pair.manual
    assert '{"id": idx, "text": text}' in pair.manual
    assert '{"id": 3, "label": "location"}' in pair.manual
    assert '{buyer}' in pair.manual and '{0,80}' in pair.manual
    for name in ('context_type', 'context_total_length', 'chunk_info', 'context_prefix',
                 'subcall_max_chars', 'subcall_chunk_chars', 'stdout_max_chars', 'max_turns'):
        assert '{' + name + '}' not in teacher[0]['content']
    assert pair.manual_version == 'manual_v1'
    with pytest.raises(ValueError, match='variant'):
        pair.messages('invalid')


def test_privileged_manual_is_task_independent_and_contains_no_task_answers():
    from rlm_opsd.harness import HarnessConfig
    from rlm_opsd.prompts import PromptBuilder

    builder, cfg = PromptBuilder.load(), HarnessConfig(prefix_chars=0)
    examples = [dict(query='QUERY_UNIQUE_A', context='CONTEXT_A', answer='ANSWER_PRIVATE_A'),
                dict(query='QUERY_UNIQUE_B', context=['CONTEXT_B'], answer='ANSWER_PRIVATE_B')]
    pairs = [builder.build(query=row['query'], context=row['context'], config=cfg) for row in examples]
    assert pairs[0].manual == pairs[1].manual
    for row, pair in zip(examples, pairs):
        assert row['answer'] not in str(pair.messages('teacher'))
        assert row['query'] not in pair.manual
        assert 'CONTEXT_' not in str(pair.messages('teacher'))
    with pytest.raises(TypeError):
        builder.build(**examples[0], config=cfg)


def test_prompt_sources_are_versioned_and_tampering_cannot_keep_the_version(tmp_path):
    from rlm_opsd.prompts import PromptBuilder

    shutil.copytree('prompts', tmp_path / 'prompts', symlinks=False)
    source = tmp_path / 'prompts'
    original = PromptBuilder.load(source)
    assert original.manual_version == 'manual_v1'
    (source / 'teacher_manual.md').write_text('changed without version bump')
    with pytest.raises(ValueError, match='checksum'):
        PromptBuilder.load(source)
    shutil.copyfile('prompts/teacher_manual.md', source / 'teacher_manual.md')
    (source / 'versions/manual_v1.md').write_text('corrupt archived manual')
    with pytest.raises(ValueError, match='checksum'):
        PromptBuilder.load(source)


def tiny_tokenizer():
    """Real BPE with a merge; decoding/re-encoding [a,b] loses its segmentation."""
    from tokenizers import Tokenizer, models, pre_tokenizers, trainers, decoders
    from transformers import PreTrainedTokenizerFast

    backend = Tokenizer(models.BPE(unk_token='[UNK]'))
    backend.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    backend.decoder = decoders.ByteLevel()
    backend.train_from_iterator(['ab ab ab hello world system user assistant think'],
        trainers.BpeTrainer(vocab_size=300, initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),
                            special_tokens=['[UNK]', '<|im_start|>', '<|im_end|>', '<think>', '</think>']))
    return PreTrainedTokenizerFast(tokenizer_object=backend, unk_token='[UNK]')


@pytest.mark.parametrize('thinking,tail', [
    (True, '<|im_start|>assistant\n<think>\n'),
    (False, '<|im_start|>assistant\n<think>\n\n</think>\n\n'),
])
def test_same_pinned_chat_template_and_thinking_setting_for_both_prefixes(thinking, tail):
    from rlm_opsd.harness import HarnessConfig
    from rlm_opsd.prompts import PromptBuilder, ChatRenderer, PromptConfig

    config = PromptConfig.from_yaml('configs/prompts.yaml').model_copy(update={'enable_thinking': thinking})
    tokenizer = tiny_tokenizer()
    renderer = ChatRenderer(config, tokenizer=tokenizer)
    pair = PromptBuilder.load().build(query='QUESTION', context='SECRET', config=HarnessConfig())
    prefixes = renderer.prefixes(pair)
    # The pinned Qwen template applies |trim to message content.
    expected_start = '<|im_start|>system\n' + pair.student_system.strip() + '<|im_end|>\n'
    expected_rest = '<|im_start|>user\nQUESTION<|im_end|>\n' + tail
    assert prefixes.student_text == expected_start + expected_rest
    assert prefixes.teacher_text == '<|im_start|>system\n' + pair.teacher_system.strip() + '<|im_end|>\n' + expected_rest
    assert prefixes.student_ids == tuple(tokenizer.encode(prefixes.student_text, add_special_tokens=False))
    assert prefixes.teacher_ids == tuple(tokenizer.encode(prefixes.teacher_text, add_special_tokens=False))
    assert prefixes.enable_thinking is thinking
    assert prefixes.template_sha256 == config.template_sha256
    # Actual noncanonical segmentation plus role markers and another turn.
    suffix = [tokenizer.convert_tokens_to_ids('a'), tokenizer.convert_tokens_to_ids('b')]
    assert tokenizer.encode(tokenizer.decode(suffix), add_special_tokens=False) != suffix
    suffix += tokenizer.encode('<|im_end|>\n<|im_start|>user\nobservation\n<|im_end|>\n<|im_start|>assistant\nFINAL(7)', add_special_tokens=False)
    from rlm_opsd.prompts import build_teacher_sequence
    student = list(prefixes.student_ids) + suffix
    teacher = build_teacher_sequence(student, student_prefix=prefixes.student_ids, teacher_prefix=prefixes.teacher_ids)
    assert teacher == prefixes.teacher_ids + tuple(suffix)
    assert student == list(prefixes.student_ids) + suffix


@pytest.mark.parametrize('suffix', [[], [0, 11, 11, 65536, 7]])
def test_alignment_copies_ids_without_a_tokenizer_or_mutating_input(suffix):
    from rlm_opsd.prompts import build_teacher_sequence

    student = [10, 20] + suffix
    result = build_teacher_sequence(student, student_prefix=[10, 20], teacher_prefix=[30, 40, 50])
    assert result == (30, 40, 50, *suffix)
    assert student == [10, 20] + suffix


@pytest.mark.parametrize('student,sp,tp', [
    ([10], [10, 20], [30]), ([10, 99, 3], [10, 20], [30]),
    ([10, 20], [], [30]), ([10, 20], [10, 20], []),
    ([10, -1], [10], [30]), ([10, True], [10], [30]), ([10, '20'], [10], [30]),
])
def test_alignment_rejects_wrong_prefixes_and_invalid_ids(student, sp, tp):
    from rlm_opsd.prompts import build_teacher_sequence

    with pytest.raises(ValueError):
        build_teacher_sequence(student, student_prefix=sp, teacher_prefix=tp)


def test_template_checksum_and_boolean_thinking_cannot_silently_drift(tmp_path):
    from rlm_opsd.prompts import ChatRenderer, PromptConfig

    cfg = PromptConfig.from_yaml('configs/prompts.yaml')
    altered = tmp_path / 'template.jinja'
    altered.write_text('{{ messages }}')
    with pytest.raises(ValueError, match='checksum'):
        ChatRenderer(cfg.model_copy(update={'template_path': altered}), tokenizer=tiny_tokenizer())
    with pytest.raises(ValueError):
        PromptConfig.model_validate({**cfg.model_dump(), 'enable_thinking': 'false'})


@pytest.mark.parametrize('variant', ['student', 'teacher'])
def test_episode_uses_authoritative_prompts_and_logs_actual_manual(tmp_path, variant):
    from rlm_opsd.harness import Episode, HarnessConfig
    from rlm_opsd.prompts import PromptBuilder

    async def run():
        cfg = HarnessConfig(max_turns=1)
        info = dict(task_id='m3', family='fixture', domain='test', tags=[], query='QUERY',
                    context='SECRET_CONTEXT', answer='DO_NOT_INJECT_ANSWER')
        pair = PromptBuilder.load().build(query='QUERY', context='SECRET_CONTEXT', config=cfg)
        async with Episode(config=cfg, info=info, frozen_client=object(), frozen_model='frozen',
                           log_dir=tmp_path, prompt_variant=variant) as ep:
            assert ep.messages == pair.messages(variant)
            assert 'DO_NOT_INJECT_ANSWER' not in str(ep.messages)
            await ep.accept('FINAL(done)', [31, 32])
        trace = json.loads(ep.log_path.read_text())
        assert trace['manual_version'] == 'manual_v1'
        assert trace['prompt_variant'] == variant
    asyncio.run(run())


def test_chunk_budget_remains_a_configured_fraction_of_subcall_limit():
    from rlm_opsd.harness import HarnessConfig

    assert HarnessConfig(max_subcall_chars=100).subcall_chunk_chars == 50
    assert HarnessConfig(max_subcall_chars=100, subcall_chunk_chars=40).subcall_chunk_chars == 40
    with pytest.raises(ValueError, match='subcall_chunk_chars'):
        HarnessConfig(max_subcall_chars=100, subcall_chunk_chars=101)


def test_custom_prompts_require_explicit_provenance_and_cannot_claim_registered_manual(tmp_path):
    from rlm_opsd.harness import Episode, HarnessConfig

    args = dict(config=HarnessConfig(), info=dict(task_id='custom', family='test', domain='test', tags=[],
                query='query', context='PRIVATE'), frozen_client=object(), frozen_model='frozen', log_dir=tmp_path)
    for version in (None, 'manual_v1'):
        with pytest.raises(ValueError, match='custom'):
            Episode(**args, system_prompt='Custom API', manual_version=version)
    ep = Episode(**args, system_prompt='Custom API', manual_version='custom_experiment_1')
    assert ep.trace.manual_version == 'custom_experiment_1'
    assert ep.messages[1]['content'] == 'query'
    assert 'PRIVATE' not in str(ep.messages)


def test_thinking_request_overrides_are_checked_and_do_not_mutate_input():
    from rlm_opsd.prompts import PromptConfig

    cfg = PromptConfig.from_yaml('configs/prompts.yaml')
    supplied = {'temperature': 0.3, 'extra_body': {'top_k': 17, 'chat_template_kwargs': {'other': 'value'}}}
    result = cfg.sampling_args(supplied)
    assert result == {'temperature': 0.3, 'extra_body': {'top_k': 17,
        'chat_template_kwargs': {'other': 'value', 'enable_thinking': True}}}
    assert 'enable_thinking' not in supplied['extra_body']['chat_template_kwargs']
    for value in (False, 'true', 1):
        with pytest.raises(ValueError, match='thinking'):
            cfg.sampling_args({'extra_body': {'chat_template_kwargs': {'enable_thinking': value}}})


def test_cli_checks_pinned_local_tokenizer_and_rejects_corruption(tmp_path):
    import subprocess
    import sys
    import yaml

    cfg = yaml.safe_load(Path('configs/prompts.yaml').read_text())
    tokenizer_path = tmp_path / 'tokenizer.json'
    tiny_tokenizer().backend_tokenizer.save(str(tokenizer_path))
    options = tmp_path / 'tokenizer_config.json'
    options.write_text('{"unk_token":"[UNK]"}')
    cfg.update(template_path=str(Path('prompts/chat_template.jinja').resolve()),
        tokenizer_path=str(tokenizer_path), tokenizer_sha256=hashlib.sha256(tokenizer_path.read_bytes()).hexdigest(),
        tokenizer_config_path=str(options), tokenizer_config_sha256=hashlib.sha256(options.read_bytes()).hexdigest())
    path = tmp_path / 'prompts.yaml'
    path.write_text(yaml.safe_dump(cfg))
    def run(command):
        return subprocess.run([sys.executable, '-m', 'rlm_opsd.prompts', command, '--config', str(path)],
                              text=True, capture_output=True)
    assert run('prepare').returncode == 0
    result = run('check')
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report['manual_version'] == 'manual_v1'
    assert report['suffix_equal'] is True and report['suffix_tokens'] > 0
    tokenizer_path.write_text('corrupted cache')
    result = run('prepare')
    assert result.returncode != 0 and 'checksum' in result.stderr


def test_registered_builder_cannot_be_forged_or_render_task_metadata_in_manual(tmp_path):
    from rlm_opsd.prompts import PromptBuilder

    with pytest.raises(TypeError):
        PromptBuilder('UNREGISTERED_API', 'TASK_ANSWER={context_prefix}', 'manual_v1')
    shutil.copytree('prompts', tmp_path / 'prompts', symlinks=False)
    source = tmp_path / 'prompts'
    changed = b'TASK_ANSWER={context_prefix}'
    (source / 'teacher_manual.md').write_bytes(changed)
    (source / 'versions/manual_v1.md').write_bytes(changed)
    registry = json.loads((source / 'versions.json').read_text())
    registry['manuals']['manual_v1']['sha256'] = hashlib.sha256(changed).hexdigest()
    (source / 'versions.json').write_text(json.dumps(registry))
    with pytest.raises(ValueError, match='task-independent'):
        PromptBuilder.load(source)


@pytest.mark.parametrize('thinking', [True, False])
def test_recursive_roots_preserve_prompt_settings_manual_and_reasoning(tmp_path, thinking):
    from rlm_opsd.harness import Episode, HarnessConfig
    from rlm_opsd.prompts import PromptConfig
    from verifiers.types import Response, ResponseMessage

    class RecursiveClient:
        def __init__(self):
            self.requests = []

        async def get_response(self, **request):
            self.requests.append(request)
            text = '```repl\nresult = 3\nprint(result)\n```' if len(self.requests) == 1 else 'FINAL_VAR(result)'
            return Response(id='child', created=0, model=request['model'], message=ResponseMessage(
                content=text, reasoning_content='keep-child-reasoning', finish_reason='stop', is_truncated=False))

    async def run():
        client = RecursiveClient()
        cfg = HarnessConfig(enable_recursion=True, max_depth=2, max_turns=3, max_subcalls=3)
        pcfg = PromptConfig.from_yaml().model_copy(update={'enable_thinking': thinking})
        async with Episode(config=cfg, prompt_config=pcfg, prompt_variant='teacher',
            info=dict(task_id='parent', family='fixture', domain='test', tags=[], query='query', context='SECRET'),
            frozen_client=client, frozen_model='initial', log_dir=tmp_path) as ep:
            await ep.accept('```repl\nresult = rlm_query("Return three")\n```\nFINAL_VAR(result)', [1])
            assert ep.trace.final.value == '3'
        assert len(client.requests) == 2
        for request in client.requests:
            assert request['sampling_args']['extra_body']['chat_template_kwargs']['enable_thinking'] is thinking
            assert '# How to work in this REPL' in request['prompt'][0].content
        assistant = next(m for m in client.requests[1]['prompt'] if m.role == 'assistant')
        assert assistant.reasoning_content == 'keep-child-reasoning'
        traces = [json.loads(p.read_text()) for p in tmp_path.glob('*.json')]
        assert len(traces) == 2
        assert all(t['manual_version'] == 'manual_v1' and t['prompt_variant'] == 'teacher' for t in traces)
    asyncio.run(run())


def test_request_cannot_override_pinned_chat_template():
    from rlm_opsd.prompts import PromptConfig

    with pytest.raises(ValueError, match='template'):
        PromptConfig.from_yaml().sampling_args({'extra_body': {'chat_template': '{{ messages }}'}})
