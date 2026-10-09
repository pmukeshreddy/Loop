<!-- rlm-opsd:offline-behavior-report:v1 -->
# Offline behavior report

Hand-labelled fixtures; not model results

Aggregated from supplied analyses; this writer performs no model runs. Rates describe supplied detector evidence, including its unknowns. Task success is tracked only when explicitly supplied.

Known/unknown count trajectories. Boolean rates and coverage means use known trajectories; syntax-error rates pool erroneous blocks over code blocks. Prompt means weight by actual subcall counts; prompt maxima use observed calls. Coverage lower bounds remain separate from exact coverage. Missing runs are marked `not run`; zero code blocks or subcalls give no rate or prompt statistic. D19 category proportions use known categories.


## before / overall: all

<a id="sources-1"></a>

Source trajectories:

- [before.json](../../../../tests/fixtures/detectors/before.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-1) |
| D2 — no_raw_dump | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-1) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-1) |
| D4 — search_refinement | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-1) |
| D5 — windowed_reads | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-1) |
| D6 — chained_search | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-1) |
| D7 — verify_hit | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-1) |
| D8 — subcalls_on_chunks | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-1) |
| D9 — subcalls_in_loop | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-1) |
| D10 — batching_ok | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-1) |
| D11 — buffer_store | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-1) |
| D12 — vars_reused | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-1) |
| D13 — no_hand_copy | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-1) |
| D14 — aggregate_in_code | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-1) |
| D15 — clean_finish | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-1) |
| D16 — syntax_error_rate | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-1) |
| D17 — error_recovery | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-1) |
| D18 — coverage | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-1) |
| D19 — first_decomposition: direct_read | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-1) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-1) |
| D19 — first_decomposition: chunk_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-1) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-1) |
| D19 — first_decomposition: other | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-1) |
| task_tag_match | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-1) |
| task_success | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-1) |
| coverage_lower_bound | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-1) |
| subcall_count | 0 | — | — | 1 | 0 | measured | [logs](#sources-1) |
| subcall_mean_count | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-1) |
| subcall_mean_prompt_chars | — | 0 | 0 | 1 | 0 | no observations | [logs](#sources-1) |
| subcall_max_prompt_chars | — | — | 0 | 1 | 0 | no observations | [logs](#sources-1) |
| truncation_events | 0 | — | — | 1 | 0 | measured | [logs](#sources-1) |

## before / family: fixture

<a id="sources-2"></a>

Source trajectories:

- [before.json](../../../../tests/fixtures/detectors/before.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D2 — no_raw_dump | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-2) |
| D4 — search_refinement | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-2) |
| D5 — windowed_reads | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D6 — chained_search | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-2) |
| D7 — verify_hit | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-2) |
| D8 — subcalls_on_chunks | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-2) |
| D9 — subcalls_in_loop | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-2) |
| D10 — batching_ok | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-2) |
| D11 — buffer_store | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-2) |
| D12 — vars_reused | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D13 — no_hand_copy | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D14 — aggregate_in_code | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D15 — clean_finish | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D16 — syntax_error_rate | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D17 — error_recovery | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-2) |
| D18 — coverage | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D19 — first_decomposition: direct_read | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D19 — first_decomposition: chunk_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| D19 — first_decomposition: other | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| task_tag_match | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| task_success | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| coverage_lower_bound | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| subcall_count | 0 | — | — | 1 | 0 | measured | [logs](#sources-2) |
| subcall_mean_count | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-2) |
| subcall_mean_prompt_chars | — | 0 | 0 | 1 | 0 | no observations | [logs](#sources-2) |
| subcall_max_prompt_chars | — | — | 0 | 1 | 0 | no observations | [logs](#sources-2) |
| truncation_events | 0 | — | — | 1 | 0 | measured | [logs](#sources-2) |

## before / size_bucket: 128

<a id="sources-3"></a>

Source trajectories:

- [before.json](../../../../tests/fixtures/detectors/before.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D2 — no_raw_dump | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-3) |
| D4 — search_refinement | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-3) |
| D5 — windowed_reads | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D6 — chained_search | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-3) |
| D7 — verify_hit | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-3) |
| D8 — subcalls_on_chunks | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-3) |
| D9 — subcalls_in_loop | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-3) |
| D10 — batching_ok | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-3) |
| D11 — buffer_store | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-3) |
| D12 — vars_reused | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D13 — no_hand_copy | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D14 — aggregate_in_code | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D15 — clean_finish | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D16 — syntax_error_rate | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D17 — error_recovery | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-3) |
| D18 — coverage | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D19 — first_decomposition: direct_read | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D19 — first_decomposition: chunk_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| D19 — first_decomposition: other | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| task_tag_match | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| task_success | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| coverage_lower_bound | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| subcall_count | 0 | — | — | 1 | 0 | measured | [logs](#sources-3) |
| subcall_mean_count | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-3) |
| subcall_mean_prompt_chars | — | 0 | 0 | 1 | 0 | no observations | [logs](#sources-3) |
| subcall_max_prompt_chars | — | — | 0 | 1 | 0 | no observations | [logs](#sources-3) |
| truncation_events | 0 | — | — | 1 | 0 | measured | [logs](#sources-3) |

## before / domain: hand_labelled_fixture

<a id="sources-4"></a>

Source trajectories:

- [before.json](../../../../tests/fixtures/detectors/before.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D2 — no_raw_dump | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-4) |
| D4 — search_refinement | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-4) |
| D5 — windowed_reads | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D6 — chained_search | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-4) |
| D7 — verify_hit | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-4) |
| D8 — subcalls_on_chunks | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-4) |
| D9 — subcalls_in_loop | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-4) |
| D10 — batching_ok | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-4) |
| D11 — buffer_store | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-4) |
| D12 — vars_reused | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D13 — no_hand_copy | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D14 — aggregate_in_code | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D15 — clean_finish | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D16 — syntax_error_rate | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D17 — error_recovery | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-4) |
| D18 — coverage | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D19 — first_decomposition: direct_read | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D19 — first_decomposition: chunk_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| D19 — first_decomposition: other | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| task_tag_match | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| task_success | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| coverage_lower_bound | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| subcall_count | 0 | — | — | 1 | 0 | measured | [logs](#sources-4) |
| subcall_mean_count | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-4) |
| subcall_mean_prompt_chars | — | 0 | 0 | 1 | 0 | no observations | [logs](#sources-4) |
| subcall_max_prompt_chars | — | — | 0 | 1 | 0 | no observations | [logs](#sources-4) |
| truncation_events | 0 | — | — | 1 | 0 | measured | [logs](#sources-4) |

## teacher / overall: all

<a id="sources-5"></a>

Source trajectories:

- [teacher.json](../../../../tests/fixtures/detectors/teacher.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D2 — no_raw_dump | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-5) |
| D4 — search_refinement | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-5) |
| D5 — windowed_reads | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-5) |
| D6 — chained_search | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-5) |
| D7 — verify_hit | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-5) |
| D8 — subcalls_on_chunks | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-5) |
| D9 — subcalls_in_loop | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-5) |
| D10 — batching_ok | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-5) |
| D11 — buffer_store | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-5) |
| D12 — vars_reused | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D13 — no_hand_copy | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D14 — aggregate_in_code | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D15 — clean_finish | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D16 — syntax_error_rate | 0 | 0 | 2 | 1 | 0 | measured | [logs](#sources-5) |
| D17 — error_recovery | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-5) |
| D18 — coverage | 0.1 | 0.1 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D19 — first_decomposition: direct_read | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D19 — first_decomposition: chunk_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| D19 — first_decomposition: other | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| task_tag_match | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| task_success | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-5) |
| coverage_lower_bound | 0.1 | 0.1 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| subcall_count | 0 | — | — | 1 | 0 | measured | [logs](#sources-5) |
| subcall_mean_count | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-5) |
| subcall_mean_prompt_chars | — | 0 | 0 | 1 | 0 | no observations | [logs](#sources-5) |
| subcall_max_prompt_chars | — | — | 0 | 1 | 0 | no observations | [logs](#sources-5) |
| truncation_events | 0 | — | — | 1 | 0 | measured | [logs](#sources-5) |

## teacher / family: fixture

<a id="sources-6"></a>

Source trajectories:

- [teacher.json](../../../../tests/fixtures/detectors/teacher.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D2 — no_raw_dump | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-6) |
| D4 — search_refinement | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-6) |
| D5 — windowed_reads | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-6) |
| D6 — chained_search | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-6) |
| D7 — verify_hit | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-6) |
| D8 — subcalls_on_chunks | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-6) |
| D9 — subcalls_in_loop | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-6) |
| D10 — batching_ok | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-6) |
| D11 — buffer_store | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-6) |
| D12 — vars_reused | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D13 — no_hand_copy | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D14 — aggregate_in_code | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D15 — clean_finish | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D16 — syntax_error_rate | 0 | 0 | 2 | 1 | 0 | measured | [logs](#sources-6) |
| D17 — error_recovery | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-6) |
| D18 — coverage | 0.1 | 0.1 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D19 — first_decomposition: direct_read | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D19 — first_decomposition: chunk_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| D19 — first_decomposition: other | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| task_tag_match | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| task_success | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-6) |
| coverage_lower_bound | 0.1 | 0.1 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| subcall_count | 0 | — | — | 1 | 0 | measured | [logs](#sources-6) |
| subcall_mean_count | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-6) |
| subcall_mean_prompt_chars | — | 0 | 0 | 1 | 0 | no observations | [logs](#sources-6) |
| subcall_max_prompt_chars | — | — | 0 | 1 | 0 | no observations | [logs](#sources-6) |
| truncation_events | 0 | — | — | 1 | 0 | measured | [logs](#sources-6) |

## teacher / size_bucket: 128

<a id="sources-7"></a>

Source trajectories:

- [teacher.json](../../../../tests/fixtures/detectors/teacher.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D2 — no_raw_dump | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-7) |
| D4 — search_refinement | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-7) |
| D5 — windowed_reads | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-7) |
| D6 — chained_search | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-7) |
| D7 — verify_hit | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-7) |
| D8 — subcalls_on_chunks | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-7) |
| D9 — subcalls_in_loop | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-7) |
| D10 — batching_ok | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-7) |
| D11 — buffer_store | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-7) |
| D12 — vars_reused | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D13 — no_hand_copy | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D14 — aggregate_in_code | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D15 — clean_finish | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D16 — syntax_error_rate | 0 | 0 | 2 | 1 | 0 | measured | [logs](#sources-7) |
| D17 — error_recovery | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-7) |
| D18 — coverage | 0.1 | 0.1 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D19 — first_decomposition: direct_read | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D19 — first_decomposition: chunk_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| D19 — first_decomposition: other | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| task_tag_match | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| task_success | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-7) |
| coverage_lower_bound | 0.1 | 0.1 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| subcall_count | 0 | — | — | 1 | 0 | measured | [logs](#sources-7) |
| subcall_mean_count | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-7) |
| subcall_mean_prompt_chars | — | 0 | 0 | 1 | 0 | no observations | [logs](#sources-7) |
| subcall_max_prompt_chars | — | — | 0 | 1 | 0 | no observations | [logs](#sources-7) |
| truncation_events | 0 | — | — | 1 | 0 | measured | [logs](#sources-7) |

## teacher / domain: hand_labelled_fixture

<a id="sources-8"></a>

Source trajectories:

- [teacher.json](../../../../tests/fixtures/detectors/teacher.json)

| Metric | Value | Numerator | Denominator | Known | Unknown | Status | Sources |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| D1 — probe_first | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-8) |
| D2 — no_raw_dump | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-8) |
| D3 — code_search_before_read | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-8) |
| D4 — search_refinement | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-8) |
| D5 — windowed_reads | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-8) |
| D6 — chained_search | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-8) |
| D7 — verify_hit | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-8) |
| D8 — subcalls_on_chunks | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-8) |
| D9 — subcalls_in_loop | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-8) |
| D10 — batching_ok | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-8) |
| D11 — buffer_store | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-8) |
| D12 — vars_reused | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-8) |
| D13 — no_hand_copy | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-8) |
| D14 — aggregate_in_code | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-8) |
| D15 — clean_finish | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-8) |
| D16 — syntax_error_rate | 0 | 0 | 2 | 1 | 0 | measured | [logs](#sources-8) |
| D17 — error_recovery | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-8) |
| D18 — coverage | 0.1 | 0.1 | 1 | 1 | 0 | measured | [logs](#sources-8) |
| D19 — first_decomposition: direct_read | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-8) |
| D19 — first_decomposition: regex_filter | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-8) |
| D19 — first_decomposition: chunk_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-8) |
| D19 — first_decomposition: whole_subcall | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-8) |
| D19 — first_decomposition: other | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-8) |
| task_tag_match | 1 | 1 | 1 | 1 | 0 | measured | [logs](#sources-8) |
| task_success | — | 0 | 0 | 0 | 1 | unknown | [logs](#sources-8) |
| coverage_lower_bound | 0.1 | 0.1 | 1 | 1 | 0 | measured | [logs](#sources-8) |
| subcall_count | 0 | — | — | 1 | 0 | measured | [logs](#sources-8) |
| subcall_mean_count | 0 | 0 | 1 | 1 | 0 | measured | [logs](#sources-8) |
| subcall_mean_prompt_chars | — | 0 | 0 | 1 | 0 | no observations | [logs](#sources-8) |
| subcall_max_prompt_chars | — | — | 0 | 1 | 0 | no observations | [logs](#sources-8) |
| truncation_events | 0 | — | — | 1 | 0 | measured | [logs](#sources-8) |

## after / overall: all

<a id="sources-9"></a>

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

## after / family: fixture

<a id="sources-10"></a>

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

<a id="sources-11"></a>

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

## after / domain: hand_labelled_fixture

<a id="sources-12"></a>

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
