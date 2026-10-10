"""verifiers environment factory used by prime-rl's asynchronous scheduler."""
from datasets import Dataset

from rlm_opsd.harness.env import RLMOpsdEnv
from rlm_opsd.prompts import ChatRenderer, PromptBuilder
from rlm_opsd.tasks.build import load_tasks


class PrimeOpsdEnv(RLMOpsdEnv):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.opsd_renderer = ChatRenderer(self.prompt_config)
        self.opsd_builder = PromptBuilder.load()

    async def setup_state(self, state):
        state = await super().setup_state(state)
        pair = self.opsd_builder.build(query=state['info']['query'], context=state['info']['context'],
                                       config=self.harness_config)
        prefixes = self.opsd_renderer.prefixes(pair)
        state['info'] = {**state['info'], 'opsd_prefixes': {
            'student_ids': list(prefixes.student_ids), 'teacher_ids': list(prefixes.teacher_ids)}}
        return state


def load_environment(*, manifest_path, harness_config, prompt_config, frozen_client, frozen_model,
                     log_dir='trajectories', **kwargs):
    """Load only the decontaminated train split; correctness stays unscored."""
    if kwargs.pop('score_rollouts', False):
        raise ValueError('OPSD does not score rewards')
    forbidden = {'dataset', 'eval_dataset', 'system_prompt', 'prompt_variant', 'prompt_builder'} & kwargs.keys()
    if forbidden:
        raise ValueError('OPSD cannot override its training data or prompt construction')
    records = list(load_tasks(manifest_path, split='train'))
    if not records:
        raise ValueError('decontaminated train split is empty')
    for record in records:
        record['answer'] = ''
    return PrimeOpsdEnv(dataset=Dataset.from_list(records), config=harness_config,
        prompt_config=prompt_config, frozen_client=frozen_client, frozen_model=frozen_model,
        log_dir=log_dir, **kwargs)
