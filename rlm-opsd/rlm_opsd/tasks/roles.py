"""Generation roles. Each role's instructions are its SKILL.md, hashed for provenance."""
import hashlib
import json
from pathlib import Path
import re

from pydantic import ValidationError

from .llm import parse_json_block
from .models import BEHAVIOR_DESCRIPTIONS, CandidateSpec

SKILLS_DIR = Path(__file__).resolve().parents[2] / 'skills'
SKILL_NAMES = ('source-analysis', 'question-generation', 'variation-suggester', 'variation-editor', 'solver', 'verifier')


def load_skills(root=SKILLS_DIR):
    skills = {}
    for name in SKILL_NAMES:
        text = (Path(root) / name / 'SKILL.md').read_text(encoding='utf-8')
        if not text.startswith('---\nname: ' + name + '\n'):
            raise ValueError(f'{name}/SKILL.md needs frontmatter naming the skill')
        skills[name] = dict(text=text, sha256=hashlib.sha256(text.encode()).hexdigest())
    return skills


def files_block(documents, limit):
    parts, total = [], 0
    for path, text in documents:
        piece = f'# File: {path}\n{text}\n'
        if total + len(piece) > limit:
            parts.append(f'# File: {path}\n[omitted: {len(text)} characters; over the request budget]\n')
            continue
        parts.append(piece)
        total += len(piece)
    return '\n'.join(parts)


def _tasks(payload):
    raw = payload.get('tasks') if isinstance(payload, dict) else None
    if not isinstance(raw, list):
        raise ValueError('expected {"tasks": [...]}')
    specs, invalid = [], []
    for index, item in enumerate(raw):
        try:
            specs.append(CandidateSpec.model_validate(item))
        except ValidationError as exc:
            errors = '; '.join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()[:6])
            invalid.append(dict(index=index, error=errors, question=str(item.get('question', ''))[:300]
                                if isinstance(item, dict) else ''))
    return specs, invalid


class Roles:
    def __init__(self, llm, skills, efforts):
        self.llm, self.skills, self.efforts = llm, skills, efforts

    async def _json(self, role, skill, user, *, extra_system=''):
        system = self.skills[skill]['text'] + (('\n\n' + extra_system) if extra_system else '')
        messages = [dict(role='system', content=system), dict(role='user', content=user)]
        result = await self.llm.acomplete(messages, effort=self.efforts[role], role=role)
        try:
            return parse_json_block(result.text)
        except ValueError:
            messages += [dict(role='assistant', content=result.text),
                         dict(role='user', content='Your reply had no parseable fenced json block. '
                                                   'Reply again with only the required json block.')]
            retry = await self.llm.acomplete(messages, effort=self.efforts[role], role=role + '_retry')
            return parse_json_block(retry.text)

    async def analyze(self, *, repo, facts_digest, source_text, baseline_summary):
        user = (f'Repository: {repo.name} at {repo.ref} ({repo.commit}), license {repo.license}.\n\n'
                f'## Facts digest\n{facts_digest}\n\n## Baseline tests\n{baseline_summary}\n\n'
                f'## Source text\n{source_text}\n\nProduce the dossier.')
        dossier = await self._json('source_analysis', 'source-analysis', user)
        if not isinstance(dossier, dict) or not isinstance(dossier.get('mechanisms'), list):
            raise ValueError('dossier must contain a mechanisms list')
        return dossier

    async def generate(self, *, repo, dossier, files_text, count, quotas, avoid, settings):
        behaviors = '\n'.join(f'- `{k}`: {v}' for k, v in BEHAVIOR_DESCRIPTIONS.items())
        user = (f'Repository: {repo.name} at {repo.ref}.\n\n## Dossier\n```json\n{json.dumps(dossier, indent=1)}\n```\n\n'
                f'## Behavior coverage still needed for this repository\n{quotas}\n\n'
                f'## Available settings\n{", ".join(settings)}\n\n## Behaviors\n{behaviors}\n\n'
                f'## Questions already written for this repository (do not repeat or paraphrase them)\n'
                + ('\n'.join(f'- {q}' for q in avoid) or '- none yet') +
                f'\n\n## Repository files for this round\n{files_text}\n\n'
                f'Write {count} new tasks. Vary settings, answer kinds and behaviors, and ground every patch in the '
                f'exact file text above.')
        return _tasks(await self._json('question_generation', 'question-generation', user))

    async def suggest(self, *, task_summary, files_text, count):
        user = (f'## Accepted task\n```json\n{json.dumps(task_summary, indent=1)}\n```\n\n'
                f'## Relevant repository files\n{files_text}\n\nPropose {count} substantive variations.')
        payload = await self._json('variation_suggester', 'variation-suggester', user)
        suggestions = payload.get('suggestions') if isinstance(payload, dict) else None
        if not isinstance(suggestions, list):
            raise ValueError('expected {"suggestions": [...]}')
        return [s for s in suggestions if isinstance(s, dict) and s.get('description')][:count]

    async def edit(self, *, task_summary, suggestion, files_text):
        user = (f'## Original accepted task\n```json\n{json.dumps(task_summary, indent=1)}\n```\n\n'
                f'## Suggestion to implement\n```json\n{json.dumps(suggestion, indent=1)}\n```\n\n'
                f'## Repository files\n{files_text}\n\nImplement the suggestion as one complete task.')
        return _tasks(await self._json('variation_editor', 'variation-editor', user,
                                       extra_system='# Question-generation rules\n\n'
                                                    + self.skills['question-generation']['text']))

    async def oracle(self, *, repo, question, answer_kind, answer_format, files_text, file_list):
        system = self.skills['verifier']['text'] + '\n\nYou are in Mode A (oracle).'
        user = (f'Repository: {repo.name}. Answer kind: {answer_kind}; answer format: {answer_format}.\n\n'
                f'## Question\n{question}\n\n## Repository paths\n{file_list}\n\n## Relevant files\n{files_text}\n\n'
                'Write the oracle program.')
        messages = [dict(role='system', content=system), dict(role='user', content=user)]
        result = await self.llm.acomplete(messages, effort=self.efforts['oracle'], role='oracle')
        blocks = re.findall(r'```python\s*\n(.*?)\n```', result.text, re.S)
        if not blocks:
            raise ValueError('oracle reply has no python block')
        return blocks[-1]

    async def review(self, payload):
        user = f'## Task under review\n```json\n{json.dumps(payload, indent=1)}\n```\n\nYou are in Mode B (review).'
        verdict = await self._json('review', 'verifier', user)
        if not isinstance(verdict, dict) or verdict.get('verdict') not in ('accept', 'reject'):
            raise ValueError('review must return verdict accept or reject')
        return verdict

    async def baseline(self, *, repo, question):
        messages = [
            dict(role='system', content='You are an experienced Python engineer. You do NOT have access to the '
                                        'repository files, logs or tests. Answer from what you know, in exactly the '
                                        'requested format, with no explanation. If unsure, give your best guess.'),
            dict(role='user', content=f'Repository: {repo.name} (release {repo.ref}).\n\n{question}')]
        result = await self.llm.acomplete(messages, effort=self.efforts['baseline'], role='baseline')
        return result.text
