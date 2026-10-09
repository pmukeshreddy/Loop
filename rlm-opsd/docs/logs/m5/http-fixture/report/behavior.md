<!-- rlm-opsd:offline-behavior-report:v1 -->
# Offline behavior report

TEST HTTP FIXTURE; NOT MODEL RESULTS

Aggregated from supplied analyses; this writer performs no model runs. Rates describe supplied detector evidence, including its unknowns. Task success is tracked only when explicitly supplied.

Known/unknown count trajectories. Boolean rates and coverage means use known trajectories; syntax-error rates pool erroneous blocks over code blocks. Prompt means weight by actual subcall counts; prompt maxima use observed calls. Coverage lower bounds remain separate from exact coverage. Missing runs are marked `not run`; zero code blocks or subcalls give no rate or prompt statistic. D19 category proportions use known categories.


## before / overall: all

<a id="sources-1"></a>

Source trajectories:

- [88f27047a31b48648bcc823ee8c17745.json](trajectories/before/88f27047a31b48648bcc823ee8c17745.json)
- [22fc17a259084466874b9cab3a334a59.json](trajectories/before/22fc17a259084466874b9cab3a334a59.json)
- [d3d23f29757048a7bf14097de269f72d.json](trajectories/before/d3d23f29757048a7bf14097de269f72d.json)
- [429028e50d0b4930afce1e19ffb4ef20.json](trajectories/before/429028e50d0b4930afce1e19ffb4ef20.json)
- [1ba247b654cb4a2186b609f5e695347e.json](trajectories/before/1ba247b654cb4a2186b609f5e695347e.json)
- [d6959a0ec9334f5c99f344c82320478e.json](trajectories/before/d6959a0ec9334f5c99f344c82320478e.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-1) |
| D2 — no_raw_dump | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-1) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-1) |
| D4 — search_refinement | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-1) |
| D5 — windowed_reads | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-1) |
| D6 — chained_search | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-1) |
| D7 — verify_hit | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-1) |
| D8 — subcalls_on_chunks | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-1) |
| D9 — subcalls_in_loop | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-1) |
| D10 — batching_ok | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-1) |
| D11 — buffer_store | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-1) |
| D12 — vars_reused | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-1) |
| D13 — no_hand_copy | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-1) |
| D14 — aggregate_in_code | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-1) |
| D15 — clean_finish | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-1) |
| D16 — syntax_error_rate | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-1) |
| D17 — error_recovery | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-1) |
| D18 — coverage | 0.33333333 | 2 | 6 | 6 | 0 | measured | [logs](#sources-1) |
| D19 — first_decomposition: direct_read | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-1) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-1) |
| D19 — first_decomposition: chunk_subcall | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-1) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-1) |
| D19 — first_decomposition: other | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-1) |
| task_tag_match | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-1) |
| task_success | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-1) |
| coverage_lower_bound | 0.33333333 | 2 | 6 | 6 | 0 | measured | [logs](#sources-1) |
| subcall_count | 6 | — | — | 6 | 0 | measured | [logs](#sources-1) |
| subcall_mean_count | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-1) |
| subcall_mean_prompt_chars | 5 | 30 | 6 | 6 | 0 | measured | [logs](#sources-1) |
| subcall_max_prompt_chars | 5 | — | 6 | 6 | 0 | measured | [logs](#sources-1) |
| truncation_events | 0 | — | — | 6 | 0 | measured | [logs](#sources-1) |

## before / family: linear_aggregation

<a id="sources-2"></a>

Source trajectories:

- [d3d23f29757048a7bf14097de269f72d.json](trajectories/before/d3d23f29757048a7bf14097de269f72d.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D2 — no_raw_dump | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-2) |
| D4 — search_refinement | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-2) |
| D5 — windowed_reads | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-2) |
| D6 — chained_search | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-2) |
| D7 — verify_hit | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-2) |
| D8 — subcalls_on_chunks | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D9 — subcalls_in_loop | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D10 — batching_ok | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D11 — buffer_store | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D12 — vars_reused | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D13 — no_hand_copy | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D14 — aggregate_in_code | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D15 — clean_finish | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D16 — syntax_error_rate | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D17 — error_recovery | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-2) |
| D18 — coverage | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D19 — first_decomposition: direct_read | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D19 — first_decomposition: chunk_subcall | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D19 — first_decomposition: other | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| task_tag_match | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| task_success | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-2) |
| coverage_lower_bound | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| subcall_count | 1 | — | — | 1 | 0 | measured | [logs](#sources-2) |
| subcall_mean_count | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| subcall_mean_prompt_chars | 5 | 5 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| subcall_max_prompt_chars | 5 | — | 1 | 1 | 0 | measured | [logs](#sources-2) |
| truncation_events | 0 | — | — | 1 | 0 | measured | [logs](#sources-2) |

## before / family: multi_hop

<a id="sources-3"></a>

Source trajectories:

- [22fc17a259084466874b9cab3a334a59.json](trajectories/before/22fc17a259084466874b9cab3a334a59.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D2 — no_raw_dump | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-3) |
| D4 — search_refinement | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-3) |
| D5 — windowed_reads | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-3) |
| D6 — chained_search | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-3) |
| D7 — verify_hit | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-3) |
| D8 — subcalls_on_chunks | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D9 — subcalls_in_loop | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D10 — batching_ok | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D11 — buffer_store | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D12 — vars_reused | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D13 — no_hand_copy | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D14 — aggregate_in_code | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D15 — clean_finish | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D16 — syntax_error_rate | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D17 — error_recovery | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-3) |
| D18 — coverage | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D19 — first_decomposition: direct_read | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D19 — first_decomposition: chunk_subcall | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D19 — first_decomposition: other | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| task_tag_match | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| task_success | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-3) |
| coverage_lower_bound | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| subcall_count | 1 | — | — | 1 | 0 | measured | [logs](#sources-3) |
| subcall_mean_count | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| subcall_mean_prompt_chars | 5 | 5 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| subcall_max_prompt_chars | 5 | — | 1 | 1 | 0 | measured | [logs](#sources-3) |
| truncation_events | 0 | — | — | 1 | 0 | measured | [logs](#sources-3) |

## before / family: quadratic_pairs

<a id="sources-4"></a>

Source trajectories:

- [429028e50d0b4930afce1e19ffb4ef20.json](trajectories/before/429028e50d0b4930afce1e19ffb4ef20.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D2 — no_raw_dump | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-4) |
| D4 — search_refinement | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-4) |
| D5 — windowed_reads | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-4) |
| D6 — chained_search | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-4) |
| D7 — verify_hit | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-4) |
| D8 — subcalls_on_chunks | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D9 — subcalls_in_loop | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D10 — batching_ok | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D11 — buffer_store | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D12 — vars_reused | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D13 — no_hand_copy | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D14 — aggregate_in_code | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D15 — clean_finish | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D16 — syntax_error_rate | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D17 — error_recovery | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-4) |
| D18 — coverage | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D19 — first_decomposition: direct_read | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D19 — first_decomposition: chunk_subcall | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D19 — first_decomposition: other | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| task_tag_match | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| task_success | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-4) |
| coverage_lower_bound | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| subcall_count | 1 | — | — | 1 | 0 | measured | [logs](#sources-4) |
| subcall_mean_count | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| subcall_mean_prompt_chars | 5 | 5 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| subcall_max_prompt_chars | 5 | — | 1 | 1 | 0 | measured | [logs](#sources-4) |
| truncation_events | 0 | — | — | 1 | 0 | measured | [logs](#sources-4) |

## before / family: repo_qa

<a id="sources-5"></a>

Source trajectories:

- [1ba247b654cb4a2186b609f5e695347e.json](trajectories/before/1ba247b654cb4a2186b609f5e695347e.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D2 — no_raw_dump | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-5) |
| D4 — search_refinement | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-5) |
| D5 — windowed_reads | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-5) |
| D6 — chained_search | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-5) |
| D7 — verify_hit | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-5) |
| D8 — subcalls_on_chunks | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D9 — subcalls_in_loop | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D10 — batching_ok | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D11 — buffer_store | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D12 — vars_reused | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D13 — no_hand_copy | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D14 — aggregate_in_code | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D15 — clean_finish | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D16 — syntax_error_rate | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D17 — error_recovery | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-5) |
| D18 — coverage | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D19 — first_decomposition: direct_read | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D19 — first_decomposition: chunk_subcall | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D19 — first_decomposition: other | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| task_tag_match | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| task_success | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-5) |
| coverage_lower_bound | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| subcall_count | 1 | — | — | 1 | 0 | measured | [logs](#sources-5) |
| subcall_mean_count | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| subcall_mean_prompt_chars | 5 | 5 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| subcall_max_prompt_chars | 5 | — | 1 | 1 | 0 | measured | [logs](#sources-5) |
| truncation_events | 0 | — | — | 1 | 0 | measured | [logs](#sources-5) |

## before / family: small_context_control

<a id="sources-6"></a>

Source trajectories:

- [d6959a0ec9334f5c99f344c82320478e.json](trajectories/before/d6959a0ec9334f5c99f344c82320478e.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D2 — no_raw_dump | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-6) |
| D4 — search_refinement | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-6) |
| D5 — windowed_reads | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-6) |
| D6 — chained_search | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-6) |
| D7 — verify_hit | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-6) |
| D8 — subcalls_on_chunks | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D9 — subcalls_in_loop | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D10 — batching_ok | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D11 — buffer_store | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D12 — vars_reused | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D13 — no_hand_copy | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D14 — aggregate_in_code | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D15 — clean_finish | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D16 — syntax_error_rate | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D17 — error_recovery | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-6) |
| D18 — coverage | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D19 — first_decomposition: direct_read | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D19 — first_decomposition: chunk_subcall | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D19 — first_decomposition: other | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| task_tag_match | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| task_success | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-6) |
| coverage_lower_bound | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| subcall_count | 1 | — | — | 1 | 0 | measured | [logs](#sources-6) |
| subcall_mean_count | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| subcall_mean_prompt_chars | 5 | 5 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| subcall_max_prompt_chars | 5 | — | 1 | 1 | 0 | measured | [logs](#sources-6) |
| truncation_events | 0 | — | — | 1 | 0 | measured | [logs](#sources-6) |

## before / family: sparse_retrieval

<a id="sources-7"></a>

Source trajectories:

- [88f27047a31b48648bcc823ee8c17745.json](trajectories/before/88f27047a31b48648bcc823ee8c17745.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D2 — no_raw_dump | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-7) |
| D4 — search_refinement | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-7) |
| D5 — windowed_reads | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-7) |
| D6 — chained_search | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-7) |
| D7 — verify_hit | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-7) |
| D8 — subcalls_on_chunks | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D9 — subcalls_in_loop | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D10 — batching_ok | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D11 — buffer_store | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D12 — vars_reused | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D13 — no_hand_copy | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D14 — aggregate_in_code | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D15 — clean_finish | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D16 — syntax_error_rate | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D17 — error_recovery | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-7) |
| D18 — coverage | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D19 — first_decomposition: direct_read | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D19 — first_decomposition: chunk_subcall | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D19 — first_decomposition: other | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| task_tag_match | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| task_success | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-7) |
| coverage_lower_bound | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| subcall_count | 1 | — | — | 1 | 0 | measured | [logs](#sources-7) |
| subcall_mean_count | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| subcall_mean_prompt_chars | 5 | 5 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| subcall_max_prompt_chars | 5 | — | 1 | 1 | 0 | measured | [logs](#sources-7) |
| truncation_events | 0 | — | — | 1 | 0 | measured | [logs](#sources-7) |

## before / size_bucket: 128

<a id="sources-8"></a>

Source trajectories:

- [88f27047a31b48648bcc823ee8c17745.json](trajectories/before/88f27047a31b48648bcc823ee8c17745.json)
- [22fc17a259084466874b9cab3a334a59.json](trajectories/before/22fc17a259084466874b9cab3a334a59.json)
- [d3d23f29757048a7bf14097de269f72d.json](trajectories/before/d3d23f29757048a7bf14097de269f72d.json)
- [429028e50d0b4930afce1e19ffb4ef20.json](trajectories/before/429028e50d0b4930afce1e19ffb4ef20.json)
- [1ba247b654cb4a2186b609f5e695347e.json](trajectories/before/1ba247b654cb4a2186b609f5e695347e.json)
- [d6959a0ec9334f5c99f344c82320478e.json](trajectories/before/d6959a0ec9334f5c99f344c82320478e.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-8) |
| D2 — no_raw_dump | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-8) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-8) |
| D4 — search_refinement | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-8) |
| D5 — windowed_reads | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-8) |
| D6 — chained_search | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-8) |
| D7 — verify_hit | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-8) |
| D8 — subcalls_on_chunks | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-8) |
| D9 — subcalls_in_loop | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-8) |
| D10 — batching_ok | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-8) |
| D11 — buffer_store | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-8) |
| D12 — vars_reused | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-8) |
| D13 — no_hand_copy | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-8) |
| D14 — aggregate_in_code | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-8) |
| D15 — clean_finish | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-8) |
| D16 — syntax_error_rate | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-8) |
| D17 — error_recovery | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-8) |
| D18 — coverage | 0.33333333 | 2 | 6 | 6 | 0 | measured | [logs](#sources-8) |
| D19 — first_decomposition: direct_read | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-8) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-8) |
| D19 — first_decomposition: chunk_subcall | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-8) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-8) |
| D19 — first_decomposition: other | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-8) |
| task_tag_match | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-8) |
| task_success | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-8) |
| coverage_lower_bound | 0.33333333 | 2 | 6 | 6 | 0 | measured | [logs](#sources-8) |
| subcall_count | 6 | — | — | 6 | 0 | measured | [logs](#sources-8) |
| subcall_mean_count | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-8) |
| subcall_mean_prompt_chars | 5 | 30 | 6 | 6 | 0 | measured | [logs](#sources-8) |
| subcall_max_prompt_chars | 5 | — | 6 | 6 | 0 | measured | [logs](#sources-8) |
| truncation_events | 0 | — | — | 6 | 0 | measured | [logs](#sources-8) |

## before / domain: long_context

<a id="sources-9"></a>

Source trajectories:

- [88f27047a31b48648bcc823ee8c17745.json](trajectories/before/88f27047a31b48648bcc823ee8c17745.json)
- [22fc17a259084466874b9cab3a334a59.json](trajectories/before/22fc17a259084466874b9cab3a334a59.json)
- [d3d23f29757048a7bf14097de269f72d.json](trajectories/before/d3d23f29757048a7bf14097de269f72d.json)
- [429028e50d0b4930afce1e19ffb4ef20.json](trajectories/before/429028e50d0b4930afce1e19ffb4ef20.json)
- [1ba247b654cb4a2186b609f5e695347e.json](trajectories/before/1ba247b654cb4a2186b609f5e695347e.json)
- [d6959a0ec9334f5c99f344c82320478e.json](trajectories/before/d6959a0ec9334f5c99f344c82320478e.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-9) |
| D2 — no_raw_dump | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-9) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-9) |
| D4 — search_refinement | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-9) |
| D5 — windowed_reads | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-9) |
| D6 — chained_search | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-9) |
| D7 — verify_hit | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-9) |
| D8 — subcalls_on_chunks | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-9) |
| D9 — subcalls_in_loop | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-9) |
| D10 — batching_ok | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-9) |
| D11 — buffer_store | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-9) |
| D12 — vars_reused | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-9) |
| D13 — no_hand_copy | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-9) |
| D14 — aggregate_in_code | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-9) |
| D15 — clean_finish | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-9) |
| D16 — syntax_error_rate | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-9) |
| D17 — error_recovery | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-9) |
| D18 — coverage | 0.33333333 | 2 | 6 | 6 | 0 | measured | [logs](#sources-9) |
| D19 — first_decomposition: direct_read | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-9) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-9) |
| D19 — first_decomposition: chunk_subcall | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-9) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-9) |
| D19 — first_decomposition: other | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-9) |
| task_tag_match | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-9) |
| task_success | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-9) |
| coverage_lower_bound | 0.33333333 | 2 | 6 | 6 | 0 | measured | [logs](#sources-9) |
| subcall_count | 6 | — | — | 6 | 0 | measured | [logs](#sources-9) |
| subcall_mean_count | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-9) |
| subcall_mean_prompt_chars | 5 | 30 | 6 | 6 | 0 | measured | [logs](#sources-9) |
| subcall_max_prompt_chars | 5 | — | 6 | 6 | 0 | measured | [logs](#sources-9) |
| truncation_events | 0 | — | — | 6 | 0 | measured | [logs](#sources-9) |

## teacher / overall: all

<a id="sources-10"></a>

Source trajectories:

- [99cf2b864e3f4837b8679b332f75b6b5.json](trajectories/teacher/99cf2b864e3f4837b8679b332f75b6b5.json)
- [7843130edb04483a963245e0451be66a.json](trajectories/teacher/7843130edb04483a963245e0451be66a.json)
- [c4f3c6cedfe845738af05945d4bf5a5e.json](trajectories/teacher/c4f3c6cedfe845738af05945d4bf5a5e.json)
- [c4524353bef84494b6fea9c215a1453d.json](trajectories/teacher/c4524353bef84494b6fea9c215a1453d.json)
- [1455a5d265994d5bb3ae98b35a8ec42f.json](trajectories/teacher/1455a5d265994d5bb3ae98b35a8ec42f.json)
- [8bf0b3de7d37493b9418b4467df4a788.json](trajectories/teacher/8bf0b3de7d37493b9418b4467df4a788.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-10) |
| D2 — no_raw_dump | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-10) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-10) |
| D4 — search_refinement | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-10) |
| D5 — windowed_reads | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-10) |
| D6 — chained_search | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-10) |
| D7 — verify_hit | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-10) |
| D8 — subcalls_on_chunks | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-10) |
| D9 — subcalls_in_loop | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-10) |
| D10 — batching_ok | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-10) |
| D11 — buffer_store | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-10) |
| D12 — vars_reused | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-10) |
| D13 — no_hand_copy | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-10) |
| D14 — aggregate_in_code | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-10) |
| D15 — clean_finish | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-10) |
| D16 — syntax_error_rate | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-10) |
| D17 — error_recovery | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-10) |
| D18 — coverage | 0.33333333 | 2 | 6 | 6 | 0 | measured | [logs](#sources-10) |
| D19 — first_decomposition: direct_read | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-10) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-10) |
| D19 — first_decomposition: chunk_subcall | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-10) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-10) |
| D19 — first_decomposition: other | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-10) |
| task_tag_match | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-10) |
| task_success | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-10) |
| coverage_lower_bound | 0.33333333 | 2 | 6 | 6 | 0 | measured | [logs](#sources-10) |
| subcall_count | 6 | — | — | 6 | 0 | measured | [logs](#sources-10) |
| subcall_mean_count | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-10) |
| subcall_mean_prompt_chars | 5 | 30 | 6 | 6 | 0 | measured | [logs](#sources-10) |
| subcall_max_prompt_chars | 5 | — | 6 | 6 | 0 | measured | [logs](#sources-10) |
| truncation_events | 0 | — | — | 6 | 0 | measured | [logs](#sources-10) |

## teacher / family: linear_aggregation

<a id="sources-11"></a>

Source trajectories:

- [c4f3c6cedfe845738af05945d4bf5a5e.json](trajectories/teacher/c4f3c6cedfe845738af05945d4bf5a5e.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-11) |
| D2 — no_raw_dump | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-11) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-11) |
| D4 — search_refinement | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-11) |
| D5 — windowed_reads | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-11) |
| D6 — chained_search | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-11) |
| D7 — verify_hit | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-11) |
| D8 — subcalls_on_chunks | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-11) |
| D9 — subcalls_in_loop | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-11) |
| D10 — batching_ok | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-11) |
| D11 — buffer_store | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-11) |
| D12 — vars_reused | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-11) |
| D13 — no_hand_copy | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-11) |
| D14 — aggregate_in_code | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-11) |
| D15 — clean_finish | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-11) |
| D16 — syntax_error_rate | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-11) |
| D17 — error_recovery | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-11) |
| D18 — coverage | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-11) |
| D19 — first_decomposition: direct_read | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-11) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-11) |
| D19 — first_decomposition: chunk_subcall | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-11) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-11) |
| D19 — first_decomposition: other | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-11) |
| task_tag_match | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-11) |
| task_success | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-11) |
| coverage_lower_bound | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-11) |
| subcall_count | 1 | — | — | 1 | 0 | measured | [logs](#sources-11) |
| subcall_mean_count | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-11) |
| subcall_mean_prompt_chars | 5 | 5 | 1 | 1 | 0 | measured | [logs](#sources-11) |
| subcall_max_prompt_chars | 5 | — | 1 | 1 | 0 | measured | [logs](#sources-11) |
| truncation_events | 0 | — | — | 1 | 0 | measured | [logs](#sources-11) |

## teacher / family: multi_hop

<a id="sources-12"></a>

Source trajectories:

- [7843130edb04483a963245e0451be66a.json](trajectories/teacher/7843130edb04483a963245e0451be66a.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-12) |
| D2 — no_raw_dump | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-12) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-12) |
| D4 — search_refinement | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-12) |
| D5 — windowed_reads | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-12) |
| D6 — chained_search | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-12) |
| D7 — verify_hit | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-12) |
| D8 — subcalls_on_chunks | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-12) |
| D9 — subcalls_in_loop | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-12) |
| D10 — batching_ok | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-12) |
| D11 — buffer_store | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-12) |
| D12 — vars_reused | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-12) |
| D13 — no_hand_copy | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-12) |
| D14 — aggregate_in_code | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-12) |
| D15 — clean_finish | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-12) |
| D16 — syntax_error_rate | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-12) |
| D17 — error_recovery | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-12) |
| D18 — coverage | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-12) |
| D19 — first_decomposition: direct_read | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-12) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-12) |
| D19 — first_decomposition: chunk_subcall | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-12) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-12) |
| D19 — first_decomposition: other | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-12) |
| task_tag_match | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-12) |
| task_success | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-12) |
| coverage_lower_bound | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-12) |
| subcall_count | 1 | — | — | 1 | 0 | measured | [logs](#sources-12) |
| subcall_mean_count | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-12) |
| subcall_mean_prompt_chars | 5 | 5 | 1 | 1 | 0 | measured | [logs](#sources-12) |
| subcall_max_prompt_chars | 5 | — | 1 | 1 | 0 | measured | [logs](#sources-12) |
| truncation_events | 0 | — | — | 1 | 0 | measured | [logs](#sources-12) |

## teacher / family: quadratic_pairs

<a id="sources-13"></a>

Source trajectories:

- [c4524353bef84494b6fea9c215a1453d.json](trajectories/teacher/c4524353bef84494b6fea9c215a1453d.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-13) |
| D2 — no_raw_dump | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-13) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-13) |
| D4 — search_refinement | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-13) |
| D5 — windowed_reads | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-13) |
| D6 — chained_search | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-13) |
| D7 — verify_hit | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-13) |
| D8 — subcalls_on_chunks | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-13) |
| D9 — subcalls_in_loop | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-13) |
| D10 — batching_ok | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-13) |
| D11 — buffer_store | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-13) |
| D12 — vars_reused | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-13) |
| D13 — no_hand_copy | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-13) |
| D14 — aggregate_in_code | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-13) |
| D15 — clean_finish | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-13) |
| D16 — syntax_error_rate | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-13) |
| D17 — error_recovery | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-13) |
| D18 — coverage | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-13) |
| D19 — first_decomposition: direct_read | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-13) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-13) |
| D19 — first_decomposition: chunk_subcall | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-13) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-13) |
| D19 — first_decomposition: other | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-13) |
| task_tag_match | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-13) |
| task_success | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-13) |
| coverage_lower_bound | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-13) |
| subcall_count | 1 | — | — | 1 | 0 | measured | [logs](#sources-13) |
| subcall_mean_count | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-13) |
| subcall_mean_prompt_chars | 5 | 5 | 1 | 1 | 0 | measured | [logs](#sources-13) |
| subcall_max_prompt_chars | 5 | — | 1 | 1 | 0 | measured | [logs](#sources-13) |
| truncation_events | 0 | — | — | 1 | 0 | measured | [logs](#sources-13) |

## teacher / family: repo_qa

<a id="sources-14"></a>

Source trajectories:

- [1455a5d265994d5bb3ae98b35a8ec42f.json](trajectories/teacher/1455a5d265994d5bb3ae98b35a8ec42f.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-14) |
| D2 — no_raw_dump | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-14) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-14) |
| D4 — search_refinement | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-14) |
| D5 — windowed_reads | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-14) |
| D6 — chained_search | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-14) |
| D7 — verify_hit | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-14) |
| D8 — subcalls_on_chunks | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-14) |
| D9 — subcalls_in_loop | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-14) |
| D10 — batching_ok | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-14) |
| D11 — buffer_store | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-14) |
| D12 — vars_reused | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-14) |
| D13 — no_hand_copy | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-14) |
| D14 — aggregate_in_code | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-14) |
| D15 — clean_finish | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-14) |
| D16 — syntax_error_rate | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-14) |
| D17 — error_recovery | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-14) |
| D18 — coverage | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-14) |
| D19 — first_decomposition: direct_read | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-14) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-14) |
| D19 — first_decomposition: chunk_subcall | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-14) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-14) |
| D19 — first_decomposition: other | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-14) |
| task_tag_match | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-14) |
| task_success | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-14) |
| coverage_lower_bound | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-14) |
| subcall_count | 1 | — | — | 1 | 0 | measured | [logs](#sources-14) |
| subcall_mean_count | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-14) |
| subcall_mean_prompt_chars | 5 | 5 | 1 | 1 | 0 | measured | [logs](#sources-14) |
| subcall_max_prompt_chars | 5 | — | 1 | 1 | 0 | measured | [logs](#sources-14) |
| truncation_events | 0 | — | — | 1 | 0 | measured | [logs](#sources-14) |

## teacher / family: small_context_control

<a id="sources-15"></a>

Source trajectories:

- [8bf0b3de7d37493b9418b4467df4a788.json](trajectories/teacher/8bf0b3de7d37493b9418b4467df4a788.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-15) |
| D2 — no_raw_dump | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-15) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-15) |
| D4 — search_refinement | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-15) |
| D5 — windowed_reads | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-15) |
| D6 — chained_search | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-15) |
| D7 — verify_hit | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-15) |
| D8 — subcalls_on_chunks | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-15) |
| D9 — subcalls_in_loop | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-15) |
| D10 — batching_ok | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-15) |
| D11 — buffer_store | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-15) |
| D12 — vars_reused | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-15) |
| D13 — no_hand_copy | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-15) |
| D14 — aggregate_in_code | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-15) |
| D15 — clean_finish | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-15) |
| D16 — syntax_error_rate | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-15) |
| D17 — error_recovery | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-15) |
| D18 — coverage | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-15) |
| D19 — first_decomposition: direct_read | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-15) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-15) |
| D19 — first_decomposition: chunk_subcall | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-15) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-15) |
| D19 — first_decomposition: other | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-15) |
| task_tag_match | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-15) |
| task_success | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-15) |
| coverage_lower_bound | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-15) |
| subcall_count | 1 | — | — | 1 | 0 | measured | [logs](#sources-15) |
| subcall_mean_count | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-15) |
| subcall_mean_prompt_chars | 5 | 5 | 1 | 1 | 0 | measured | [logs](#sources-15) |
| subcall_max_prompt_chars | 5 | — | 1 | 1 | 0 | measured | [logs](#sources-15) |
| truncation_events | 0 | — | — | 1 | 0 | measured | [logs](#sources-15) |

## teacher / family: sparse_retrieval

<a id="sources-16"></a>

Source trajectories:

- [99cf2b864e3f4837b8679b332f75b6b5.json](trajectories/teacher/99cf2b864e3f4837b8679b332f75b6b5.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-16) |
| D2 — no_raw_dump | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-16) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-16) |
| D4 — search_refinement | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-16) |
| D5 — windowed_reads | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-16) |
| D6 — chained_search | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-16) |
| D7 — verify_hit | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-16) |
| D8 — subcalls_on_chunks | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-16) |
| D9 — subcalls_in_loop | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-16) |
| D10 — batching_ok | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-16) |
| D11 — buffer_store | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-16) |
| D12 — vars_reused | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-16) |
| D13 — no_hand_copy | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-16) |
| D14 — aggregate_in_code | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-16) |
| D15 — clean_finish | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-16) |
| D16 — syntax_error_rate | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-16) |
| D17 — error_recovery | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-16) |
| D18 — coverage | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-16) |
| D19 — first_decomposition: direct_read | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-16) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-16) |
| D19 — first_decomposition: chunk_subcall | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-16) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-16) |
| D19 — first_decomposition: other | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-16) |
| task_tag_match | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-16) |
| task_success | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-16) |
| coverage_lower_bound | 0.33333333 | 0.33333333 | 1 | 1 | 0 | measured | [logs](#sources-16) |
| subcall_count | 1 | — | — | 1 | 0 | measured | [logs](#sources-16) |
| subcall_mean_count | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-16) |
| subcall_mean_prompt_chars | 5 | 5 | 1 | 1 | 0 | measured | [logs](#sources-16) |
| subcall_max_prompt_chars | 5 | — | 1 | 1 | 0 | measured | [logs](#sources-16) |
| truncation_events | 0 | — | — | 1 | 0 | measured | [logs](#sources-16) |

## teacher / size_bucket: 128

<a id="sources-17"></a>

Source trajectories:

- [99cf2b864e3f4837b8679b332f75b6b5.json](trajectories/teacher/99cf2b864e3f4837b8679b332f75b6b5.json)
- [7843130edb04483a963245e0451be66a.json](trajectories/teacher/7843130edb04483a963245e0451be66a.json)
- [c4f3c6cedfe845738af05945d4bf5a5e.json](trajectories/teacher/c4f3c6cedfe845738af05945d4bf5a5e.json)
- [c4524353bef84494b6fea9c215a1453d.json](trajectories/teacher/c4524353bef84494b6fea9c215a1453d.json)
- [1455a5d265994d5bb3ae98b35a8ec42f.json](trajectories/teacher/1455a5d265994d5bb3ae98b35a8ec42f.json)
- [8bf0b3de7d37493b9418b4467df4a788.json](trajectories/teacher/8bf0b3de7d37493b9418b4467df4a788.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-17) |
| D2 — no_raw_dump | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-17) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-17) |
| D4 — search_refinement | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-17) |
| D5 — windowed_reads | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-17) |
| D6 — chained_search | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-17) |
| D7 — verify_hit | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-17) |
| D8 — subcalls_on_chunks | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-17) |
| D9 — subcalls_in_loop | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-17) |
| D10 — batching_ok | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-17) |
| D11 — buffer_store | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-17) |
| D12 — vars_reused | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-17) |
| D13 — no_hand_copy | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-17) |
| D14 — aggregate_in_code | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-17) |
| D15 — clean_finish | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-17) |
| D16 — syntax_error_rate | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-17) |
| D17 — error_recovery | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-17) |
| D18 — coverage | 0.33333333 | 2 | 6 | 6 | 0 | measured | [logs](#sources-17) |
| D19 — first_decomposition: direct_read | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-17) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-17) |
| D19 — first_decomposition: chunk_subcall | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-17) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-17) |
| D19 — first_decomposition: other | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-17) |
| task_tag_match | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-17) |
| task_success | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-17) |
| coverage_lower_bound | 0.33333333 | 2 | 6 | 6 | 0 | measured | [logs](#sources-17) |
| subcall_count | 6 | — | — | 6 | 0 | measured | [logs](#sources-17) |
| subcall_mean_count | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-17) |
| subcall_mean_prompt_chars | 5 | 30 | 6 | 6 | 0 | measured | [logs](#sources-17) |
| subcall_max_prompt_chars | 5 | — | 6 | 6 | 0 | measured | [logs](#sources-17) |
| truncation_events | 0 | — | — | 6 | 0 | measured | [logs](#sources-17) |

## teacher / domain: long_context

<a id="sources-18"></a>

Source trajectories:

- [99cf2b864e3f4837b8679b332f75b6b5.json](trajectories/teacher/99cf2b864e3f4837b8679b332f75b6b5.json)
- [7843130edb04483a963245e0451be66a.json](trajectories/teacher/7843130edb04483a963245e0451be66a.json)
- [c4f3c6cedfe845738af05945d4bf5a5e.json](trajectories/teacher/c4f3c6cedfe845738af05945d4bf5a5e.json)
- [c4524353bef84494b6fea9c215a1453d.json](trajectories/teacher/c4524353bef84494b6fea9c215a1453d.json)
- [1455a5d265994d5bb3ae98b35a8ec42f.json](trajectories/teacher/1455a5d265994d5bb3ae98b35a8ec42f.json)
- [8bf0b3de7d37493b9418b4467df4a788.json](trajectories/teacher/8bf0b3de7d37493b9418b4467df4a788.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-18) |
| D2 — no_raw_dump | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-18) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-18) |
| D4 — search_refinement | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-18) |
| D5 — windowed_reads | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-18) |
| D6 — chained_search | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-18) |
| D7 — verify_hit | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-18) |
| D8 — subcalls_on_chunks | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-18) |
| D9 — subcalls_in_loop | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-18) |
| D10 — batching_ok | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-18) |
| D11 — buffer_store | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-18) |
| D12 — vars_reused | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-18) |
| D13 — no_hand_copy | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-18) |
| D14 — aggregate_in_code | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-18) |
| D15 — clean_finish | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-18) |
| D16 — syntax_error_rate | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-18) |
| D17 — error_recovery | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-18) |
| D18 — coverage | 0.33333333 | 2 | 6 | 6 | 0 | measured | [logs](#sources-18) |
| D19 — first_decomposition: direct_read | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-18) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-18) |
| D19 — first_decomposition: chunk_subcall | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-18) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-18) |
| D19 — first_decomposition: other | 0 | 0 | 6 | 6 | 0 | measured | [logs](#sources-18) |
| task_tag_match | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-18) |
| task_success | — | 0 | 0 | 0 | 6 | unknown | [logs](#sources-18) |
| coverage_lower_bound | 0.33333333 | 2 | 6 | 6 | 0 | measured | [logs](#sources-18) |
| subcall_count | 6 | — | — | 6 | 0 | measured | [logs](#sources-18) |
| subcall_mean_count | 1 | 6 | 6 | 6 | 0 | measured | [logs](#sources-18) |
| subcall_mean_prompt_chars | 5 | 30 | 6 | 6 | 0 | measured | [logs](#sources-18) |
| subcall_max_prompt_chars | 5 | — | 6 | 6 | 0 | measured | [logs](#sources-18) |
| truncation_events | 0 | — | — | 6 | 0 | measured | [logs](#sources-18) |

## after / overall: all

<a id="sources-19"></a>

Source trajectories:

not run

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | — | — | — | 0 | 0 | not run | not run |
| D2 — no_raw_dump | — | — | — | 0 | 0 | not run | not run |
| D3 — code_search_before_read | — | — | — | 0 | 0 | not run | not run |
| D4 — search_refinement | — | — | — | 0 | 0 | not run | not run |
| D5 — windowed_reads | — | — | — | 0 | 0 | not run | not run |
| D6 — chained_search | — | — | — | 0 | 0 | not run | not run |
| D7 — verify_hit | — | — | — | 0 | 0 | not run | not run |
| D8 — subcalls_on_chunks | — | — | — | 0 | 0 | not run | not run |
| D9 — subcalls_in_loop | — | — | — | 0 | 0 | not run | not run |
| D10 — batching_ok | — | — | — | 0 | 0 | not run | not run |
| D11 — buffer_store | — | — | — | 0 | 0 | not run | not run |
| D12 — vars_reused | — | — | — | 0 | 0 | not run | not run |
| D13 — no_hand_copy | — | — | — | 0 | 0 | not run | not run |
| D14 — aggregate_in_code | — | — | — | 0 | 0 | not run | not run |
| D15 — clean_finish | — | — | — | 0 | 0 | not run | not run |
| D16 — syntax_error_rate | — | — | — | 0 | 0 | not run | not run |
| D17 — error_recovery | — | — | — | 0 | 0 | not run | not run |
| D18 — coverage | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: direct_read | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: regex_filter | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: chunk_subcall | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: whole_subcall | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: other | — | — | — | 0 | 0 | not run | not run |
| task_tag_match | — | — | — | 0 | 0 | not run | not run |
| task_success | — | — | — | 0 | 0 | not run | not run |
| coverage_lower_bound | — | — | — | 0 | 0 | not run | not run |
| subcall_count | — | — | — | 0 | 0 | not run | not run |
| subcall_mean_count | — | — | — | 0 | 0 | not run | not run |
| subcall_mean_prompt_chars | — | — | — | 0 | 0 | not run | not run |
| subcall_max_prompt_chars | — | — | — | 0 | 0 | not run | not run |
| truncation_events | — | — | — | 0 | 0 | not run | not run |

## after / family: linear_aggregation

<a id="sources-20"></a>

Source trajectories:

not run

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | — | — | — | 0 | 0 | not run | not run |
| D2 — no_raw_dump | — | — | — | 0 | 0 | not run | not run |
| D3 — code_search_before_read | — | — | — | 0 | 0 | not run | not run |
| D4 — search_refinement | — | — | — | 0 | 0 | not run | not run |
| D5 — windowed_reads | — | — | — | 0 | 0 | not run | not run |
| D6 — chained_search | — | — | — | 0 | 0 | not run | not run |
| D7 — verify_hit | — | — | — | 0 | 0 | not run | not run |
| D8 — subcalls_on_chunks | — | — | — | 0 | 0 | not run | not run |
| D9 — subcalls_in_loop | — | — | — | 0 | 0 | not run | not run |
| D10 — batching_ok | — | — | — | 0 | 0 | not run | not run |
| D11 — buffer_store | — | — | — | 0 | 0 | not run | not run |
| D12 — vars_reused | — | — | — | 0 | 0 | not run | not run |
| D13 — no_hand_copy | — | — | — | 0 | 0 | not run | not run |
| D14 — aggregate_in_code | — | — | — | 0 | 0 | not run | not run |
| D15 — clean_finish | — | — | — | 0 | 0 | not run | not run |
| D16 — syntax_error_rate | — | — | — | 0 | 0 | not run | not run |
| D17 — error_recovery | — | — | — | 0 | 0 | not run | not run |
| D18 — coverage | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: direct_read | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: regex_filter | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: chunk_subcall | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: whole_subcall | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: other | — | — | — | 0 | 0 | not run | not run |
| task_tag_match | — | — | — | 0 | 0 | not run | not run |
| task_success | — | — | — | 0 | 0 | not run | not run |
| coverage_lower_bound | — | — | — | 0 | 0 | not run | not run |
| subcall_count | — | — | — | 0 | 0 | not run | not run |
| subcall_mean_count | — | — | — | 0 | 0 | not run | not run |
| subcall_mean_prompt_chars | — | — | — | 0 | 0 | not run | not run |
| subcall_max_prompt_chars | — | — | — | 0 | 0 | not run | not run |
| truncation_events | — | — | — | 0 | 0 | not run | not run |

## after / family: multi_hop

<a id="sources-21"></a>

Source trajectories:

not run

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | — | — | — | 0 | 0 | not run | not run |
| D2 — no_raw_dump | — | — | — | 0 | 0 | not run | not run |
| D3 — code_search_before_read | — | — | — | 0 | 0 | not run | not run |
| D4 — search_refinement | — | — | — | 0 | 0 | not run | not run |
| D5 — windowed_reads | — | — | — | 0 | 0 | not run | not run |
| D6 — chained_search | — | — | — | 0 | 0 | not run | not run |
| D7 — verify_hit | — | — | — | 0 | 0 | not run | not run |
| D8 — subcalls_on_chunks | — | — | — | 0 | 0 | not run | not run |
| D9 — subcalls_in_loop | — | — | — | 0 | 0 | not run | not run |
| D10 — batching_ok | — | — | — | 0 | 0 | not run | not run |
| D11 — buffer_store | — | — | — | 0 | 0 | not run | not run |
| D12 — vars_reused | — | — | — | 0 | 0 | not run | not run |
| D13 — no_hand_copy | — | — | — | 0 | 0 | not run | not run |
| D14 — aggregate_in_code | — | — | — | 0 | 0 | not run | not run |
| D15 — clean_finish | — | — | — | 0 | 0 | not run | not run |
| D16 — syntax_error_rate | — | — | — | 0 | 0 | not run | not run |
| D17 — error_recovery | — | — | — | 0 | 0 | not run | not run |
| D18 — coverage | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: direct_read | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: regex_filter | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: chunk_subcall | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: whole_subcall | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: other | — | — | — | 0 | 0 | not run | not run |
| task_tag_match | — | — | — | 0 | 0 | not run | not run |
| task_success | — | — | — | 0 | 0 | not run | not run |
| coverage_lower_bound | — | — | — | 0 | 0 | not run | not run |
| subcall_count | — | — | — | 0 | 0 | not run | not run |
| subcall_mean_count | — | — | — | 0 | 0 | not run | not run |
| subcall_mean_prompt_chars | — | — | — | 0 | 0 | not run | not run |
| subcall_max_prompt_chars | — | — | — | 0 | 0 | not run | not run |
| truncation_events | — | — | — | 0 | 0 | not run | not run |

## after / family: quadratic_pairs

<a id="sources-22"></a>

Source trajectories:

not run

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | — | — | — | 0 | 0 | not run | not run |
| D2 — no_raw_dump | — | — | — | 0 | 0 | not run | not run |
| D3 — code_search_before_read | — | — | — | 0 | 0 | not run | not run |
| D4 — search_refinement | — | — | — | 0 | 0 | not run | not run |
| D5 — windowed_reads | — | — | — | 0 | 0 | not run | not run |
| D6 — chained_search | — | — | — | 0 | 0 | not run | not run |
| D7 — verify_hit | — | — | — | 0 | 0 | not run | not run |
| D8 — subcalls_on_chunks | — | — | — | 0 | 0 | not run | not run |
| D9 — subcalls_in_loop | — | — | — | 0 | 0 | not run | not run |
| D10 — batching_ok | — | — | — | 0 | 0 | not run | not run |
| D11 — buffer_store | — | — | — | 0 | 0 | not run | not run |
| D12 — vars_reused | — | — | — | 0 | 0 | not run | not run |
| D13 — no_hand_copy | — | — | — | 0 | 0 | not run | not run |
| D14 — aggregate_in_code | — | — | — | 0 | 0 | not run | not run |
| D15 — clean_finish | — | — | — | 0 | 0 | not run | not run |
| D16 — syntax_error_rate | — | — | — | 0 | 0 | not run | not run |
| D17 — error_recovery | — | — | — | 0 | 0 | not run | not run |
| D18 — coverage | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: direct_read | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: regex_filter | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: chunk_subcall | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: whole_subcall | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: other | — | — | — | 0 | 0 | not run | not run |
| task_tag_match | — | — | — | 0 | 0 | not run | not run |
| task_success | — | — | — | 0 | 0 | not run | not run |
| coverage_lower_bound | — | — | — | 0 | 0 | not run | not run |
| subcall_count | — | — | — | 0 | 0 | not run | not run |
| subcall_mean_count | — | — | — | 0 | 0 | not run | not run |
| subcall_mean_prompt_chars | — | — | — | 0 | 0 | not run | not run |
| subcall_max_prompt_chars | — | — | — | 0 | 0 | not run | not run |
| truncation_events | — | — | — | 0 | 0 | not run | not run |

## after / family: repo_qa

<a id="sources-23"></a>

Source trajectories:

not run

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | — | — | — | 0 | 0 | not run | not run |
| D2 — no_raw_dump | — | — | — | 0 | 0 | not run | not run |
| D3 — code_search_before_read | — | — | — | 0 | 0 | not run | not run |
| D4 — search_refinement | — | — | — | 0 | 0 | not run | not run |
| D5 — windowed_reads | — | — | — | 0 | 0 | not run | not run |
| D6 — chained_search | — | — | — | 0 | 0 | not run | not run |
| D7 — verify_hit | — | — | — | 0 | 0 | not run | not run |
| D8 — subcalls_on_chunks | — | — | — | 0 | 0 | not run | not run |
| D9 — subcalls_in_loop | — | — | — | 0 | 0 | not run | not run |
| D10 — batching_ok | — | — | — | 0 | 0 | not run | not run |
| D11 — buffer_store | — | — | — | 0 | 0 | not run | not run |
| D12 — vars_reused | — | — | — | 0 | 0 | not run | not run |
| D13 — no_hand_copy | — | — | — | 0 | 0 | not run | not run |
| D14 — aggregate_in_code | — | — | — | 0 | 0 | not run | not run |
| D15 — clean_finish | — | — | — | 0 | 0 | not run | not run |
| D16 — syntax_error_rate | — | — | — | 0 | 0 | not run | not run |
| D17 — error_recovery | — | — | — | 0 | 0 | not run | not run |
| D18 — coverage | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: direct_read | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: regex_filter | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: chunk_subcall | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: whole_subcall | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: other | — | — | — | 0 | 0 | not run | not run |
| task_tag_match | — | — | — | 0 | 0 | not run | not run |
| task_success | — | — | — | 0 | 0 | not run | not run |
| coverage_lower_bound | — | — | — | 0 | 0 | not run | not run |
| subcall_count | — | — | — | 0 | 0 | not run | not run |
| subcall_mean_count | — | — | — | 0 | 0 | not run | not run |
| subcall_mean_prompt_chars | — | — | — | 0 | 0 | not run | not run |
| subcall_max_prompt_chars | — | — | — | 0 | 0 | not run | not run |
| truncation_events | — | — | — | 0 | 0 | not run | not run |

## after / family: small_context_control

<a id="sources-24"></a>

Source trajectories:

not run

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | — | — | — | 0 | 0 | not run | not run |
| D2 — no_raw_dump | — | — | — | 0 | 0 | not run | not run |
| D3 — code_search_before_read | — | — | — | 0 | 0 | not run | not run |
| D4 — search_refinement | — | — | — | 0 | 0 | not run | not run |
| D5 — windowed_reads | — | — | — | 0 | 0 | not run | not run |
| D6 — chained_search | — | — | — | 0 | 0 | not run | not run |
| D7 — verify_hit | — | — | — | 0 | 0 | not run | not run |
| D8 — subcalls_on_chunks | — | — | — | 0 | 0 | not run | not run |
| D9 — subcalls_in_loop | — | — | — | 0 | 0 | not run | not run |
| D10 — batching_ok | — | — | — | 0 | 0 | not run | not run |
| D11 — buffer_store | — | — | — | 0 | 0 | not run | not run |
| D12 — vars_reused | — | — | — | 0 | 0 | not run | not run |
| D13 — no_hand_copy | — | — | — | 0 | 0 | not run | not run |
| D14 — aggregate_in_code | — | — | — | 0 | 0 | not run | not run |
| D15 — clean_finish | — | — | — | 0 | 0 | not run | not run |
| D16 — syntax_error_rate | — | — | — | 0 | 0 | not run | not run |
| D17 — error_recovery | — | — | — | 0 | 0 | not run | not run |
| D18 — coverage | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: direct_read | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: regex_filter | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: chunk_subcall | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: whole_subcall | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: other | — | — | — | 0 | 0 | not run | not run |
| task_tag_match | — | — | — | 0 | 0 | not run | not run |
| task_success | — | — | — | 0 | 0 | not run | not run |
| coverage_lower_bound | — | — | — | 0 | 0 | not run | not run |
| subcall_count | — | — | — | 0 | 0 | not run | not run |
| subcall_mean_count | — | — | — | 0 | 0 | not run | not run |
| subcall_mean_prompt_chars | — | — | — | 0 | 0 | not run | not run |
| subcall_max_prompt_chars | — | — | — | 0 | 0 | not run | not run |
| truncation_events | — | — | — | 0 | 0 | not run | not run |

## after / family: sparse_retrieval

<a id="sources-25"></a>

Source trajectories:

not run

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | — | — | — | 0 | 0 | not run | not run |
| D2 — no_raw_dump | — | — | — | 0 | 0 | not run | not run |
| D3 — code_search_before_read | — | — | — | 0 | 0 | not run | not run |
| D4 — search_refinement | — | — | — | 0 | 0 | not run | not run |
| D5 — windowed_reads | — | — | — | 0 | 0 | not run | not run |
| D6 — chained_search | — | — | — | 0 | 0 | not run | not run |
| D7 — verify_hit | — | — | — | 0 | 0 | not run | not run |
| D8 — subcalls_on_chunks | — | — | — | 0 | 0 | not run | not run |
| D9 — subcalls_in_loop | — | — | — | 0 | 0 | not run | not run |
| D10 — batching_ok | — | — | — | 0 | 0 | not run | not run |
| D11 — buffer_store | — | — | — | 0 | 0 | not run | not run |
| D12 — vars_reused | — | — | — | 0 | 0 | not run | not run |
| D13 — no_hand_copy | — | — | — | 0 | 0 | not run | not run |
| D14 — aggregate_in_code | — | — | — | 0 | 0 | not run | not run |
| D15 — clean_finish | — | — | — | 0 | 0 | not run | not run |
| D16 — syntax_error_rate | — | — | — | 0 | 0 | not run | not run |
| D17 — error_recovery | — | — | — | 0 | 0 | not run | not run |
| D18 — coverage | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: direct_read | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: regex_filter | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: chunk_subcall | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: whole_subcall | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: other | — | — | — | 0 | 0 | not run | not run |
| task_tag_match | — | — | — | 0 | 0 | not run | not run |
| task_success | — | — | — | 0 | 0 | not run | not run |
| coverage_lower_bound | — | — | — | 0 | 0 | not run | not run |
| subcall_count | — | — | — | 0 | 0 | not run | not run |
| subcall_mean_count | — | — | — | 0 | 0 | not run | not run |
| subcall_mean_prompt_chars | — | — | — | 0 | 0 | not run | not run |
| subcall_max_prompt_chars | — | — | — | 0 | 0 | not run | not run |
| truncation_events | — | — | — | 0 | 0 | not run | not run |

## after / size_bucket: 128

<a id="sources-26"></a>

Source trajectories:

not run

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | — | — | — | 0 | 0 | not run | not run |
| D2 — no_raw_dump | — | — | — | 0 | 0 | not run | not run |
| D3 — code_search_before_read | — | — | — | 0 | 0 | not run | not run |
| D4 — search_refinement | — | — | — | 0 | 0 | not run | not run |
| D5 — windowed_reads | — | — | — | 0 | 0 | not run | not run |
| D6 — chained_search | — | — | — | 0 | 0 | not run | not run |
| D7 — verify_hit | — | — | — | 0 | 0 | not run | not run |
| D8 — subcalls_on_chunks | — | — | — | 0 | 0 | not run | not run |
| D9 — subcalls_in_loop | — | — | — | 0 | 0 | not run | not run |
| D10 — batching_ok | — | — | — | 0 | 0 | not run | not run |
| D11 — buffer_store | — | — | — | 0 | 0 | not run | not run |
| D12 — vars_reused | — | — | — | 0 | 0 | not run | not run |
| D13 — no_hand_copy | — | — | — | 0 | 0 | not run | not run |
| D14 — aggregate_in_code | — | — | — | 0 | 0 | not run | not run |
| D15 — clean_finish | — | — | — | 0 | 0 | not run | not run |
| D16 — syntax_error_rate | — | — | — | 0 | 0 | not run | not run |
| D17 — error_recovery | — | — | — | 0 | 0 | not run | not run |
| D18 — coverage | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: direct_read | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: regex_filter | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: chunk_subcall | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: whole_subcall | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: other | — | — | — | 0 | 0 | not run | not run |
| task_tag_match | — | — | — | 0 | 0 | not run | not run |
| task_success | — | — | — | 0 | 0 | not run | not run |
| coverage_lower_bound | — | — | — | 0 | 0 | not run | not run |
| subcall_count | — | — | — | 0 | 0 | not run | not run |
| subcall_mean_count | — | — | — | 0 | 0 | not run | not run |
| subcall_mean_prompt_chars | — | — | — | 0 | 0 | not run | not run |
| subcall_max_prompt_chars | — | — | — | 0 | 0 | not run | not run |
| truncation_events | — | — | — | 0 | 0 | not run | not run |

## after / domain: long_context

<a id="sources-27"></a>

Source trajectories:

not run

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | — | — | — | 0 | 0 | not run | not run |
| D2 — no_raw_dump | — | — | — | 0 | 0 | not run | not run |
| D3 — code_search_before_read | — | — | — | 0 | 0 | not run | not run |
| D4 — search_refinement | — | — | — | 0 | 0 | not run | not run |
| D5 — windowed_reads | — | — | — | 0 | 0 | not run | not run |
| D6 — chained_search | — | — | — | 0 | 0 | not run | not run |
| D7 — verify_hit | — | — | — | 0 | 0 | not run | not run |
| D8 — subcalls_on_chunks | — | — | — | 0 | 0 | not run | not run |
| D9 — subcalls_in_loop | — | — | — | 0 | 0 | not run | not run |
| D10 — batching_ok | — | — | — | 0 | 0 | not run | not run |
| D11 — buffer_store | — | — | — | 0 | 0 | not run | not run |
| D12 — vars_reused | — | — | — | 0 | 0 | not run | not run |
| D13 — no_hand_copy | — | — | — | 0 | 0 | not run | not run |
| D14 — aggregate_in_code | — | — | — | 0 | 0 | not run | not run |
| D15 — clean_finish | — | — | — | 0 | 0 | not run | not run |
| D16 — syntax_error_rate | — | — | — | 0 | 0 | not run | not run |
| D17 — error_recovery | — | — | — | 0 | 0 | not run | not run |
| D18 — coverage | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: direct_read | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: regex_filter | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: chunk_subcall | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: whole_subcall | — | — | — | 0 | 0 | not run | not run |
| D19 — first_decomposition: other | — | — | — | 0 | 0 | not run | not run |
| task_tag_match | — | — | — | 0 | 0 | not run | not run |
| task_success | — | — | — | 0 | 0 | not run | not run |
| coverage_lower_bound | — | — | — | 0 | 0 | not run | not run |
| subcall_count | — | — | — | 0 | 0 | not run | not run |
| subcall_mean_count | — | — | — | 0 | 0 | not run | not run |
| subcall_mean_prompt_chars | — | — | — | 0 | 0 | not run | not run |
| subcall_max_prompt_chars | — | — | — | 0 | 0 | not run | not run |
| truncation_events | — | — | — | 0 | 0 | not run | not run |
