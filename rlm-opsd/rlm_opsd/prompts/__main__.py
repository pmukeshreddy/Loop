import argparse
import hashlib
import json
import sys

from rlm_opsd.harness import HarnessConfig
from . import ChatRenderer, PromptBuilder, PromptConfig, build_teacher_sequence, prepare_tokenizer


def check(config):
    renderer = ChatRenderer(config)
    pair = PromptBuilder.load().build(query='Inspect the length of context.',
        context='PRIVATE_CONTEXT_NOT_IN_PROMPT', config=HarnessConfig())
    prefixes = renderer.prefixes(pair)
    tokenizer = renderer.tokenizer
    # Preserve an intentionally unmerged 'a','b' pair plus two assistant turns
    # and an observation, exercising the dangerous decode/re-encode boundary.
    suffix = tokenizer.encode('a', add_special_tokens=False) + tokenizer.encode('b', add_special_tokens=False)
    assert suffix != tokenizer.encode('ab', add_special_tokens=False)
    suffix += tokenizer.encode('\n```repl\nprint(len(context))\n```<|im_end|>\n'
        '<|im_start|>user\n29\n<|im_end|>\n<|im_start|>assistant\nFINAL(29)', add_special_tokens=False)
    student = prefixes.student_ids + tuple(suffix)
    teacher = build_teacher_sequence(student, student_prefix=prefixes.student_ids, teacher_prefix=prefixes.teacher_ids)
    assert teacher[len(prefixes.teacher_ids):] == tuple(suffix)
    assert 'PRIVATE_CONTEXT_NOT_IN_PROMPT' not in prefixes.teacher_text
    expected_tail = '<think>\n' if config.enable_thinking else '<think>\n\n</think>\n\n'
    assert prefixes.student_text.endswith(expected_tail) and prefixes.teacher_text.endswith(expected_tail)
    return dict(model=config.model_name, revision=config.revision, manual_version=pair.manual_version,
                template_sha256=prefixes.template_sha256, enable_thinking=prefixes.enable_thinking,
                student_prefix_tokens=len(prefixes.student_ids), teacher_prefix_tokens=len(prefixes.teacher_ids),
                suffix_tokens=len(suffix), suffix_equal=True,
                suffix_sha256=hashlib.sha256(json.dumps(suffix).encode()).hexdigest())


def main():
    parser = argparse.ArgumentParser(description='Prepare/check pinned M3 tokenizer artifacts; no model execution.')
    parser.add_argument('command', choices=['prepare', 'check'])
    parser.add_argument('--config', default='configs/prompts.yaml')
    parser.add_argument('--thinking', choices=['on', 'off'], help='Explicit smoke-check override for both prefixes')
    args = parser.parse_args()
    try:
        config = PromptConfig.from_yaml(args.config)
        if args.thinking is not None:
            config = config.model_copy(update={'enable_thinking': args.thinking == 'on'})
        if args.command == 'prepare':
            prepare_tokenizer(config)
            result = dict(model=config.model_name, revision=config.revision, tokenizer_verified=True)
        else:
            result = check(config)
        print(json.dumps(result, sort_keys=True))
    except (OSError, ValueError, AssertionError) as exc:
        print(f'prompt error: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
