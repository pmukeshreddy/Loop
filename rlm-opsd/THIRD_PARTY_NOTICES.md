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

# BANKING77 task data

Generated `linear_aggregation` and `quadratic_pairs` contexts contain utterances
from BANKING77 by PolyAI. Source: [PolyAI task-specific datasets](https://github.com/PolyAI-LDN/task-specific-datasets/tree/57ec275d8078af65b7731c2a98be812d844a6d6b/banking_data),
revision `57ec275d8078af65b7731c2a98be812d844a6d6b`, `train.csv` and `test.csv`.
Dataset license: [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/),
with the [source license text](https://github.com/PolyAI-LDN/task-specific-datasets/blob/57ec275d8078af65b7731c2a98be812d844a6d6b/LICENSE).

Credit: Iñigo Casanueva, Tadas Temčinas, Daniela Gerz, Matthew Henderson, and Ivan
Vulić. 2020. [Efficient Intent Detection with Dual Sentence Encoders](https://arxiv.org/abs/2003.04807).

Project changes: select configured intents; remove ambiguous normalized-text
labels; deduplicate repeated text; sample/repeat utterances; add synthetic user
IDs and dates; serialize and shuffle records. Utterance wording is preserved.
Labels stay in the offline verification corpus and are omitted from contexts.
Source checksums and import counts are recorded in
[M2 progress](docs/PROGRESS.md) and each pool's build report.

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
