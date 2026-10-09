# Teacher gate

TEST HTTP FIXTURE; NOT MODEL RESULTS

Status: **passed**

[Behavior report](behavior.md) · [CSV](behavior.csv) · [Run provenance](run.json) · [Requests](requests.jsonl)

Completed episodes: 12 / 12

Thresholds apply to teacher-as-policy evidence. Baseline metrics remain in the behavior report.

| Metric | Dimension / group | Rule | Value | Known / unknown | Status |
| --- | --- | --- | ---: | ---: | --- |
| task_tag_match | overall / all | min 0.9 | 1.0 | 6 / 0 | passed |

Source trajectories:

- before: [fixture-0](trajectories/before/88f27047a31b48648bcc823ee8c17745.json)
- teacher: [fixture-0](trajectories/teacher/99cf2b864e3f4837b8679b332f75b6b5.json)
- before: [fixture-1](trajectories/before/22fc17a259084466874b9cab3a334a59.json)
- teacher: [fixture-1](trajectories/teacher/7843130edb04483a963245e0451be66a.json)
- before: [fixture-2](trajectories/before/d3d23f29757048a7bf14097de269f72d.json)
- teacher: [fixture-2](trajectories/teacher/c4f3c6cedfe845738af05945d4bf5a5e.json)
- before: [fixture-3](trajectories/before/429028e50d0b4930afce1e19ffb4ef20.json)
- teacher: [fixture-3](trajectories/teacher/c4524353bef84494b6fea9c215a1453d.json)
- before: [fixture-4](trajectories/before/1ba247b654cb4a2186b609f5e695347e.json)
- teacher: [fixture-4](trajectories/teacher/1455a5d265994d5bb3ae98b35a8ec42f.json)
- before: [fixture-5](trajectories/before/d6959a0ec9334f5c99f344c82320478e.json)
- teacher: [fixture-5](trajectories/teacher/8bf0b3de7d37493b9418b4467df4a788.json)

After/checkpoint phase: not run. Task success is not scored by this gate.
Endpoint weights/template identity is operator-declared; response model aliases are checked.
