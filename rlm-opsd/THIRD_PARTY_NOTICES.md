# RLM reference implementation

The harness subclasses and adapts the worker/proxy/backend interfaces from
alexzhang13/rlm, commit d04208afbad29ca675ab13478c40ee8bebc84bfe.

MIT License

Copyright (c) 2026 Alex Zhang

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

# Source repositories for generated DeepSWE tasks

Generated task contexts contain file text from the following permissively
licensed repositories at the pinned commits in `configs/tasks.yaml`
(recorded with tree digests in each pool's build report). Each repository
remains under its own license; task contexts reproduce its files unmodified,
except where a task's documented setup patch introduces a defect.

| Repository | License |
|---|---|
| pallets/click, pallets/jinja, andialbrecht/sqlparse, lepture/mistune, pytoolz/toolz, theskumar/python-dotenv, mahmoud/glom, alecthomas/voluptuous, wtforms/wtforms | BSD-3-Clause |
| mkdocs/mkdocs | BSD-2-Clause |
| marshmallow-code/marshmallow, pyparsing/pyparsing, jmespath/jmespath.py, lark-parser/lark, python-hyper/h11, tkem/cachetools, python-attrs/attrs, python-jsonschema/jsonschema | MIT |
| jd/tenacity | Apache-2.0 |
| hynek/structlog | Apache-2.0 OR MIT |

None of these repositories is an upstream project of the DeepSWE-113
evaluation tasks.

# DeepSWE-113 decontamination index

The local held-out index includes the instructions and upstream repository
names of the 113 DeepSWE tasks under `../data/deep-swe/tasks` (Apache-2.0 task
specifications by Datacurve AI). They are used only for exclusion checks and
never enter generation prompts or training data.

# OOLONG-Pairs public question index

The local decontamination index includes question templates from
[mit-oasys/oolong-pairs](https://huggingface.co/datasets/mit-oasys/oolong-pairs/tree/d1e1522b86ac0c169bbc890b0471408aaa29e8fa),
revision `d1e1522b86ac0c169bbc890b0471408aaa29e8fa`, `questions.json`.
The source dataset card declares the MIT license. These questions are reserved
for exclusion checks and are not included in generated training prompts.
The query index does not contain the full benchmark's source contexts or answers.

# Qwen3.5-27B tokenizer and chat template

M3 uses the tokenizer artifacts and unmodified `chat_template.jinja` from
[Qwen/Qwen3.5-27B](https://huggingface.co/Qwen/Qwen3.5-27B/tree/fc05daec18b0a78c049392ed2e771dde82bdf654),
revision `fc05daec18b0a78c049392ed2e771dde82bdf654`, published by the Qwen team.
The source declares Apache License 2.0; the exact downloaded license is retained
in [prompts/QWEN_LICENSE](prompts/QWEN_LICENSE). The template is vendored in
`prompts/chat_template.jinja`; tokenizer JSON files are checksum-verified local
cache artifacts. No source template modification or model-weight redistribution
is made by this project.
