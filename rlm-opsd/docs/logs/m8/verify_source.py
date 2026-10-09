"""M8 pinned source/API checks, no network and no pretrained model run."""
import hashlib
import inspect
import json
from importlib.metadata import distribution,version
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
import torch
from verifiers.envs.environment import Environment
from verifiers.clients import OpenAIChatCompletionsClient
from rlm_opsd.prompts.chat import PromptConfig,load_tokenizer
from rlm_opsd.eval.monitor_config import MonitorConfig,ExitConfig
from rlm_opsd.eval.scoring import load_adapter,token_offsets,score_samples

for package,commit,relatives,subdir in (
    ('prime-rl','09e11c7527a242b9f150c7c4c71b1b96da66cb75',
     ['trainer/model.py','trainer/models/layers/lora/base.py','trainer/models/layers/lora/multi_linear.py'], 'src/prime_rl'),
    ('verifiers','58b119fa1b24eff85b74a75ccf3e132523b3c6c3',
     ['envs/environment.py','clients/openai_chat_completions_client.py'],'verifiers')):
    source=ROOT/'.deps'/package
    actual=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    assert actual==commit
    installed=Path(distribution(package).locate_file('prime_rl' if package=='prime-rl' else package))
    print('PIN',package,actual)
    for relative in relatives:
        path=source/subdir/relative;data=path.read_bytes()
        assert data==(installed/relative).read_bytes()
        print('PINNED_SOURCE',path.relative_to(ROOT),hashlib.sha256(data).hexdigest(),'installed bytes identical')
for obj in (Environment.rollout,OpenAIChatCompletionsClient.get_response,torch.load,load_adapter,token_offsets,score_samples):
    path=Path(inspect.getfile(obj))
    print('API',obj.__qualname__,inspect.signature(obj),path,hashlib.sha256(path.read_bytes()).hexdigest())
tokenizer=load_tokenizer(PromptConfig.from_yaml())
for obj in (tokenizer.decode,tokenizer.__call__):print('TOKENIZER_API',obj.__qualname__,inspect.signature(obj),inspect.getfile(obj))
ids=tokenizer.encode('Hi é 🌍 FINAL(x)<|im_end|>',add_special_tokens=False)
print('EXECUTED_OFFSET_FIXTURE',json.dumps(token_offsets(tokenizer,ids),ensure_ascii=False))
for cls in (MonitorConfig,ExitConfig):
    print('CONFIG_KEYS',cls.__name__,sorted(cls.model_fields))
for name in ('torch','transformers','verifiers','prime-rl'):print('LOCAL_VERSION',name,version(name))
print('RUNTIME',sys.platform,'CUDA',torch.cuda.is_available())
print('GPU/pretrained monitoring and retention NOT RUN; no performance claims.')
