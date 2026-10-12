# Representative released tasks

## jmespath-jmespath-py-r03-04 (train)

- Family: `inspect_locate`; established behaviors: inspect_locate, combine_verify_finish
- Setting: `multi_module_fix`; answer: `patch` / `unified_diff`
- Repository: jmespath/jmespath.py@1.1.0; context 253,730 chars in 49 files
- Verification: `tests`; hidden tests 6
- Reference execution: 5 turns, 0 sub-calls

**Question**

> Correct equality for nested JSON values. The `==` and `!=` operators must distinguish booleans from numbers at every depth, not just for scalar operands: for example, `[0]` must not equal `[false]`. Arrays compare positionally; objects compare by identical key sets and recursively equal values, independent of key order. Integer and floating-point representations of the same number must still compare equal.
> 
> Array-subject `contains` must use this same equality rule when testing membership, including for nested arrays and objects. String-subject `contains` must retain its current substring behavior. Apply the rule through ordinary searches, compiled searches, and filter predicates, without changing unrelated ordering or truth-value behavior. Return a unified diff against production files only.

**Behavior rationale**

- `combine_verify_finish`: The resulting production changes must consistently implement the same recursive rule in both public entry paths and be assembled into an applicable diff.
  - Execution evidence: finish FINAL_VAR; final value computed in code: True; inspected after construction: True
- `inspect_locate`: Equality operators and array membership currently enter different modules and use different equality mechanisms.
  - Execution evidence: context 253730 chars; 14 code searches over context; 0 whole-context prints

**Verified reference answer**

```diff
--- a/jmespath/_utils.py
+++ b/jmespath/_utils.py
@@ -0,0 +1,17 @@
+def equals(x, y):
+    """Compare JSON values without treating booleans as numbers."""
+    if isinstance(x, bool) or isinstance(y, bool):
+        return isinstance(x, bool) and isinstance(y, bool) and x == y
+    if isinstance(x, list) or isinstance(y, list):
+        return (
+            isinstance(x, list) and isinstance(y, list)
+            and len(x) == len(y)
+            and all(equals(a, b) for a, b in zip(x, y))
+        )
+    if isinstance(x, dict) or isinstance(y, dict):
+        return (
+            isinstance(x, dict) and isinstance(y, dict)
+            and set(x) == set(y)
+            and all(equals(x[key], y[key]) for key in x)
+        )
+    return x == y
--- a/jmespath/visitor.py
+++ b/jmespath/visitor.py
@@ -1,38 +1,9 @@
 import operator
 
 from jmespath import functions
+from jmespath._utils import equals as _equals
 from jmespath.compat import string_type
 from numbers import Number
-
-
-def _equals(x, y):
-    if _is_special_number_case(x, y):
-        return False
-    else:
-        return x == y
-
-
-def _is_special_number_case(x, y):
-    # We need to special case comparing 0 or 1 to
-    # True/False.  While normally comparing any
-    # integer other than 0/1 to True/False will always
-    # return False.  However 0/1 have this:
-    # >>> 0 == True
-    # False
-    # >>> 0 == False
-    # True
-    # >>> 1 == True
-    # True
-    # >>> 1 == False
-    # False
-    #
-    # Also need to consider that:
-    # >>> 0 in [True, False]
-    # True
-    if _is_actual_number(x) and x in (0, 1):
-        return isinstance(y, bool)
-    elif _is_actual_number(y) and y in (0, 1):
-        return isinstance(x, bool)
 
 
 def _is_comparable(x):
--- a/jmespath/functions.py
+++ b/jmespath/functions.py
@@ -2,6 +2,7 @@
 import json
 
 from jmespath import exceptions
+from jmespath._utils import equals
 from jmespath.compat import string_type as STRING_TYPE
 from jmespath.compat import get_methods
 
@@ -212,6 +213,8 @@
 
     @signature({'types': ['array', 'string']}, {'types': []})
     def _func_contains(self, subject, search):
+        if isinstance(subject, list):
+            return any(equals(element, search) for element in subject)
         return search in subject
 
     @signature({'types': ['string', 'array', 'object']})

```

**Reviewer:** The task is a natural, repository-dependent behavioral change with a precise production-only diff format. Its requirements form one coherent equality policy, rather than unrelated checks. It does not disclose defective implementation symbols or prescribe solver operations, and it is distinct from the accepted tasks. The supplied tests cover nested boolean/number distinctions, numeric equivalence, object key order, filters, compiled searches, and membership.

## tkem-cachetools-r02-01 (train)

- Family: `direct_solve`; established behaviors: direct_solve
- Setting: `implementation`; answer: `patch` / `unified_diff`
- Repository: tkem/cachetools@v7.2.1; context 3,306 chars in 1 files
- Verification: `tests`; hidden tests 4
- Reference execution: 3 turns, 0 sub-calls

**Question**

> Add a keyword-only `getsizeof=None` option to `cachetools.func.ttl_cache`, allowing callers to use weighted TTL memoization. Forward it to the underlying TTL cache in all three construction forms: a configured bounded decorator, the callable-first form with its default capacity, and `maxsize=None`. Unbounded TTL caches must continue expiring entries and reporting `maxsize=None`, but their `currsize` must now reflect the supplied sizing function. Keep `cache_parameters()` limited to its existing `maxsize` and `typed` fields, preserve the current behavior when `getsizeof` is omitted, and retain the existing handling of results too large to cache. Deliver a unified diff against production files only.

**Behavior rationale**

- `direct_solve`: All construction paths requiring changes are in the small func.py module. The bounded, callable, and specialized unbounded branches can be understood directly without repository-wide investigation.
  - Execution evidence: context 3306 chars; 0 sub-calls

**Verified reference answer**

```diff
--- a/src/cachetools/func.py
+++ b/src/cachetools/func.py
@@ -11,8 +11,8 @@
 
 
 class _UnboundTTLCache(TTLCache):
-    def __init__(self, ttl, timer):
-        TTLCache.__init__(self, math.inf, ttl, timer)
+    def __init__(self, ttl, timer, getsizeof=None):
+        TTLCache.__init__(self, math.inf, ttl, timer, getsizeof=getsizeof)
 
     @property
     def maxsize(self):  # type: ignore
@@ -88,15 +88,17 @@
         return _cache(RRCache(maxsize, choice), maxsize, typed)
 
 
-def ttl_cache(maxsize=128, ttl=600, timer=time.monotonic, typed=False):
+def ttl_cache(maxsize=128, ttl=600, timer=time.monotonic, typed=False, *, getsizeof=None):
     """Decorator to wrap a function with a memoizing callable that saves
     up to `maxsize` results based on a Least Recently Used (LRU)
-    algorithm with a per-item time-to-live (TTL) value.
+    algorithm with a per-item time-to-live (TTL) value. If `getsizeof`
+    is supplied, `maxsize` limits the total size of the cached results
+    as determined by this function, rather than their number.
 
     """
     if maxsize is None:
-        return _cache(_UnboundTTLCache(ttl, timer), None, typed)
+        return _cache(_UnboundTTLCache(ttl, timer, getsizeof=getsizeof), None, typed)
     elif callable(maxsize):
-        return _cache(TTLCache(128, ttl, timer), 128, typed)(maxsize)
+        return _cache(TTLCache(128, ttl, timer, getsizeof=getsizeof), 128, typed)(maxsize)
     else:
-        return _cache(TTLCache(maxsize, ttl, timer), maxsize, typed)
+        return _cache(TTLCache(maxsize, ttl, timer, getsizeof=getsizeof), maxsize, typed)

```

**Reviewer:** This is a natural, narrowly scoped feature request with a precise production-only unified-diff deliverable. Naming the public option and its required semantics defines the requested API rather than leaking a defective implementation. The verified patch forwards sizing through all three branches, and the supplied tests cover weighted accounting, expiration, metadata, and oversized results. The task is distinct from the existing accounting-regression and insertion-error-propagation tasks.

## jd-tenacity-r01-03 (train)

- Family: `chunked_subcalls`; established behaviors: inspect_locate, chunked_subcalls
- Setting: `change_impact`; answer: `test_ids` / `set`
- Repository: jd/tenacity@9.2.1; context 280,980 chars in 87 files
- Verification: `impact`; impact set 17
- Reference execution: 7 turns, 1 sub-calls

**Question**

> We are reviewing a change to make the controller's `statistics["attempt_number"]` counter zero-based. Specifically, BaseRetrying.begin() would initialize that statistics entry to 0 instead of 1. Subsequent increments, RetryCallState.attempt_number, Future.attempt_number, stop-policy inputs, and actual retry execution would remain unchanged. Which existing pytest tests would newly fail under precisely this change? Return a JSON list of complete pytest node IDs, with no duplicates.

**Behavior rationale**

- `chunked_subcalls`: The two supplied main test modules exceed a single bounded read. Determining failures requires understanding assertions and execution bodies, including tests that inspect statistics during a call, not simply listing occurrences of attempt_number.
  - Execution evidence: 1 sub-calls (0 failed); 1 call sites on selected context, 0 on the whole context; max prompt 16673 chars
- `inspect_locate`: Statistics consumers are distributed among decorator tests, explicit-retry tests, direct statistics tests, and asynchronous tests rather than grouped under one test class.
  - Execution evidence: context 280980 chars; 18 code searches over context; 0 whole-context prints

**Verified reference answer**

```json
["tests/test_asyncio.py::TestAsyncio::test_statistics_visible_through_outer_decorator", "tests/test_asyncio.py::TestContextManager::test_reraise_try_again_with_cause", "tests/test_asyncio.py::TestDecoratorWrapper::test_retry_function_attributes", "tests/test_tenacity.py::TestRetryConditions::test_retry_try_again_forever", "tests/test_tenacity.py::TestRetryConditions::test_retry_try_again_with_cause_reraise", "tests/test_tenacity.py::TestRetryConditions::test_retry_try_again_from_cause_reraise", "tests/test_tenacity.py::TestRetryConditions::test_retry_try_again_forever_reraise", "tests/test_tenacity.py::TestDecoratorWrapper::test_retry_until_exception_of_type_attempt_number", "tests/test_tenacity.py::TestDecoratorWrapper::test_retry_until_exception_of_type_no_type", "tests/test_tenacity.py::TestDecoratorWrapper::test_retry_if_not_exception_message", "tests/test_tenacity.py::TestDecoratorWrapper::test_retry_if_not_exception_message_delay", "tests/test_tenacity.py::TestDecoratorWrapper::test_retry_if_not_exception_message_match", "tests/test_tenacity.py::TestDecoratorWrapper::test_retry_function_attributes", "tests/test_tenacity.py::TestStatisticsKeys::test_statistics_visible_through_outer_decorator", "tests/test_tenacity.py::TestStatistics::test_stats", "tests/test_tenacity.py::TestStatistics::test_stats_failing", "tests/test_tenacity.py::TestStatistics::test_retry_object_statistics_during_execution"]
```

**Reviewer:** This is a natural, repository-dependent change-impact request with a precisely scoped mutation and an explicit output format. It requires distinguishing controller statistics from retry-state and stop-policy inputs across distributed tests. The question does not reveal the failing tests or prescribe solver operations, and it is distinct from the previously accepted tasks.

## alecthomas-voluptuous-r01-01 (train)

- Family: `persistent_state`; established behaviors: inspect_locate, persistent_state, combine_verify_finish
- Setting: `scattered_evidence_debugging`; answer: `patch` / `unified_diff`
- Repository: alecthomas/voluptuous@0.16.0; context 203,562 chars in 16 files, logs: ['pytest run on the current branch']
- Verification: `tests`; fail-to-pass 1
- Reference execution: 8 turns, 0 sub-calls

**Question**

> The attached CI output exposes a mapping-validation regression: a field with its own literal-key schema can escape that schema's value validation when a broader key validator is also present. Repair the regression without weakening complex Required-key presence checks or changing Remove's existing fallback semantics. Return a unified diff against the repository's non-test files; leave tests unchanged.

**Behavior rationale**

- `combine_verify_finish`: The deliverable is an exact unified diff whose context and replacement must be checked against the extracted mapping closure, while preserving the separate Remove fallback behavior.
  - Execution evidence: finish FINAL_VAR; final value computed in code: True; inspected after construction: True
- `inspect_locate`: The public failure involves a complex Required key and a specific field validator, while the control-flow defect is in the mapping engine shared by dictionaries and objects.
  - Execution evidence: context 203562 chars; 23 code searches over context; 0 whole-context prints
- `persistent_state`: The solver must retain the relationship between literal-key indexing, additional candidates, removal sentinels, and required-key accounting while tracing the failing schema and preparing an edit.
  - Execution evidence: 8 turns; variables reused across turns: ['files', 'sb', 'start', 'tests']; hand-copied literals 0

**Verified reference answer**

```diff
--- a/voluptuous/schema_builder.py
+++ b/voluptuous/schema_builder.py
@@ -363,7 +363,7 @@
                         exception_errors.append(e)
 
                     if exception_errors:
-                        if is_remove or remove_key or (additional_candidates and skey in candidates_by_key):
+                        if is_remove or remove_key:
                             continue
                         for err in exception_errors:
                             if len(err.path) <= len(key_path):

```

**Injected defect (hidden from the solver)**

```diff
--- a/voluptuous/schema_builder.py
+++ b/voluptuous/schema_builder.py
@@ -390,7 +390,7 @@
                         exception_errors.append(e)
 
                     if exception_errors:
-                        if is_remove or remove_key:
+                        if is_remove or remove_key or (additional_candidates and skey in candidates_by_key):
                             continue
                         for err in exception_errors:
                             if len(err.path) <= len(key_path):

```

**Reviewer:** This is a natural, repository-dependent repair request with a precise output format. It describes the observable failure without exposing the defective symbol or replacement. Preserving Required and Remove behavior meaningfully constrains the repair. The previously accepted task concerns locating a required-key compilation defect, not repairing value-validation fallback behavior.

## marshmallow-code-marshmallow-r02-03 (train)

- Family: `combine_verify_finish`; established behaviors: inspect_locate, combine_verify_finish
- Setting: `implementation`; answer: `patch` / `unified_diff`
- Repository: marshmallow-code/marshmallow@4.3.1; context 803,113 chars in 88 files
- Verification: `tests`; hidden tests 4
- Reference execution: 7 turns, 0 sub-calls

**Question**

> Allow a `pre_load(pass_collection=True)` hook to filter or expand a `many=True` input collection when item-level `validates_schema` methods do not request original input. Those validators must run exactly once for each deserialized output item, in output order, and validation errors must use that item's output index subject to the existing `Meta.index_errors` setting. This must work through both `load` and `validate`, without requiring the processed collection to have the original input's length. Keep collection-level validators and `skip_on_field_errors` behavior unchanged. Item-level validators declared with `pass_original=True` must retain the existing strict positional pairing and length-mismatch behavior. Send a unified diff against production files only.

**Behavior rationale**

- `combine_verify_finish`: The final patch must combine cardinality-independent validation for one metadata mode with unchanged strict original pairing for the other, checking that validator arguments and index handling are preserved in both branches.
  - Execution evidence: finish FINAL_VAR; final value computed in code: True; inspected after construction: True
- `inspect_locate`: The behavior crosses collection preprocessing, deserialization, validator metadata, and validator dispatch; the public load method alone does not explain the failure.
  - Execution evidence: context 803113 chars; 16 code searches over context; 0 whole-context prints

**Verified reference answer**

```diff
--- a/src/marshmallow/schema.py
+++ b/src/marshmallow/schema.py
@@ -1192,9 +1192,14 @@
             pass_original = validator_kwargs.get("pass_original", False)
 
             if many and not pass_collection:
-                for idx, (item, orig) in enumerate(
+                # Only pair with the input when the validator requests it.
+                # Collection preprocessors may change the number of output items.
+                items = (
                     zip(data, original_data, strict=True)
-                ):
+                    if pass_original
+                    else ((item, None) for item in data)
+                )
+                for idx, (item, orig) in enumerate(items):
                     self._run_validator(
                         validator,
                         item,
@@ -1203,7 +1208,7 @@
                         many=many,
                         partial=partial,
                         unknown=unknown,
-                        index=idx,
+                        index=idx if self.opts.index_errors else None,
                         pass_original=pass_original,
                     )
             else:

```

**Reviewer:** This is a natural, repository-dependent implementation request with a precise production-only unified-diff format. It specifies observable contracts without identifying the defective internal dispatcher or prescribing solver operations. It is distinct from the accepted tasks. The supplied tests do not explicitly cover index_errors=False or skip_on_field_errors, but that coverage limitation does not make the task ambiguous or invalidate its stated behaviors.

## wtforms-wtforms-r02-00 (train)

- Family: `recursive_decomposition`; established behaviors: inspect_locate, chunked_subcalls, recursive_decomposition, combine_verify_finish
- Setting: `change_impact`; answer: `test_ids` / `set`
- Repository: wtforms/wtforms@3.2.2; context 366,896 chars in 99 files
- Verification: `impact`; impact set 13
- Reference execution: 9 turns, 7 sub-calls

**Question**

> We are considering making choice selection submission-only. In both `SelectField` and `SelectMultipleField`, each generated choice would be marked selected only when `self.raw_data` is truthy and its existing coerced-value comparison succeeds. Processing data, membership checks, choice grouping, and the widgets would otherwise remain unchanged. Which existing pytest tests would newly fail under this change? Return a JSON list of pytest node IDs, with no duplicates.

**Behavior rationale**

- `chunked_subcalls`: The select, multiple-select, and radio suites contain numerous cases involving defaults, Python data, submissions, grouped choices, and rendering. Determining failures requires semantic review of these suites rather than collecting symbol references.
  - Execution evidence: 7 sub-calls (0 failed); 3 call sites on selected context, 0 on the whole context; max prompt 14381 chars
- `combine_verify_finish`: The deliverable is an exact, deduplicated set of pytest node IDs assembled from the independently assessed rendering and validation effects.
  - Execution evidence: finish FINAL_VAR; final value computed in code: True; inspected after construction: True
- `inspect_locate`: The choice generators are shared by validation, native select rendering, and iterable option rendering, so relevant tests are not limited to direct calls to iter_choices.
  - Execution evidence: context 366896 chars; 14 code searches over context; 0 whole-context prints
- `recursive_decomposition`: Single-select validation, multiple-select membership validation, and radio option rendering are independent impact investigations whose results must be reconciled.
  - Execution evidence: 7 sub-calls (0 failed); results stored at 3 sites; sub-call results reach the final answer: True

**Verified reference answer**

```json
["tests/fields/test_radio.py::test_callable_choices", "tests/fields/test_radio.py::test_radio_field", "tests/fields/test_radio.py::test_required_validator", "tests/fields/test_select.py::test_callable_choices", "tests/fields/test_select.py::test_defaults", "tests/fields/test_select.py::test_iterable_options", "tests/fields/test_select.py::test_optgroup", "tests/fields/test_select.py::test_optgroup_option_render_kw", "tests/fields/test_select.py::test_optgroup_shortcut", "tests/fields/test_select.py::test_option_render_kw", "tests/fields/test_selectmultiple.py::test_callable_choices", "tests/fields/test_selectmultiple.py::test_optgroup_option_render_kw", "tests/fields/test_selectmultiple.py::test_option_render_kw"]
```

**Reviewer:** This is a natural, repository-dependent change-impact request with a precise proposed change and clear output format. Identifying the affected tests requires tracing selection state through validation and rendering, not merely locating the named classes. The question does not reveal failing tests or prescribe solver operations, and the investigation is distinct from the existing field-processing and checked-attribute tasks.

## python-jsonschema-jsonschema-r02-00-v1 (train)

- Family: `inspect_locate`; established behaviors: inspect_locate, combine_verify_finish
- Setting: `implementation`; answer: `patch` / `unified_diff`
- Repository: python-jsonschema/jsonschema@v4.26.0; context 1,199,778 chars in 194 files
- Verification: `tests`; hidden tests 7
- Reference execution: 7 turns, 0 sub-calls
- Variation of `python-jsonschema-jsonschema-r02-00`: dependency — The affected draft, keyword branch, and repair all change. The legacy helper currently treats keys inside a schema-valued additionalProperties schema as instance property names instead of determining which additional values successfully validate. Restoring the modern applicator validity guard cannot

**Question**

> Correct Draft 2019-09 handling of schema-valued `additionalProperties` when `unevaluatedProperties` is present. In this checkout, `Draft201909Validator` rejects `{"x": 1}` against `{"additionalProperties": {"type": "integer"}, "unevaluatedProperties": false}`, even though the additional value passes its schema.
> 
> Successfully validated additional properties must count as evaluated; values that fail that schema must remain uncovered and still be checked by `unevaluatedProperties`. This must also hold when an instance property happens to be named like a schema keyword, such as `type`. Properties declared in `properties` or matched by `patternProperties` must remain excluded from additional-property validation, including regex matches that do not cover the entire property name. Preserve the existing behavior when `additionalProperties` is absent or boolean, preserve ordinary validation errors, and leave Draft 2020-12 behavior unchanged.
> 
> Return a unified diff against production files only, without changing tests.

**Behavior rationale**

- `combine_verify_finish`: The production diff must reconcile successful and unsuccessful additional-property coverage, exclusions for declared and pattern-matched names, boolean additionalProperties behavior, and isolation from Draft 2020-12. Its hunks must be checked against the exact legacy implementation.
  - Execution evidence: finish FINAL_VAR; final value computed in code: True; inspected after construction: True
- `inspect_locate`: The public Draft201909Validator entry point dispatches ordinary additional-property validation and unevaluated-property validation to different modules. Locating those registrations and following the coverage helper is necessary to distinguish successful instance-value validation from interpretation of schema keys.
  - Execution evidence: context 1199778 chars; 22 code searches over context; 0 whole-context prints

**Verified reference answer**

```diff
--- a/jsonschema/_legacy_keywords.py
+++ b/jsonschema/_legacy_keywords.py
@@ -371,6 +371,20 @@
             schema_value = schema[keyword]
             if validator.is_type(schema_value, "boolean") and schema_value:
                 evaluated_keys += instance.keys()
+
+            elif (
+                keyword == "additionalProperties"
+                and validator.is_type(schema_value, "object")
+            ):
+                evaluated_keys += (
+                    property
+                    for property in _utils.find_additional_properties(
+                        instance, schema,
+                    )
+                    if _utils.is_valid(
+                        validator.descend(instance[property], schema_value),
+                    )
+                )
 
             elif validator.is_type(schema_value, "object"):
                 for property in schema_value:

```

**Reviewer:** This is a natural, repository-dependent bug-fix request with a precise production-only unified-diff format. The behavioral requirements do not reveal the defective helper or prescribe its implementation. Unlike the parent task, it concerns schema-valued additionalProperties in Draft 2019-09 rather than unsuccessful applicator branches in Draft 2020-12, so it is a substantive variation and not a duplicate of the listed tasks.

## pallets-click-r02-04-v1 (train)

- Family: `inspect_locate`; established behaviors: inspect_locate
- Setting: `implementation`; answer: `patch` / `unified_diff`
- Repository: pallets/click@8.5.0; context 147,871 chars in 1 files
- Verification: `tests`; hidden tests 8
- Reference execution: 8 turns, 0 sub-calls
- Variation of `pallets-click-r02-04`: failure_condition — The defect is duplicate dispatch to extension hooks, not execution of callable defaults. The original change modifies Option.get_help_extra; this repair instead changes the section-selection logic in two Command methods and must establish that custom help-record implementations are neither called tw

**Question**

> Custom Option and Argument subclasses can perform observable work in get_help_record, but rendering command help currently invokes these hooks more than once. Make Command.get_help request each parameter's help record exactly once per render, during its own section. Calling format_arguments or format_options independently must request records only for that section, once per call; subsequent renders must request fresh records rather than reuse cached results. Preserve positional arguments before options, declaration order within each section, automatic help output, hidden-option behavior, and omission of records returning None. Hidden options must still receive their one option-section hook call, leaving visibility to the hook. Custom argument records must work even when the argument has no help attribute value. Callable defaults must remain unevaluated during help rendering, whether show_default is enabled or disabled. Deliver a unified diff against production files only, leaving tests unchanged.

**Behavior rationale**

- `inspect_locate`: The supplied core module exceeds the direct-solve context limit. The relevant evidence is confined to the command help-rendering sequence, its section formatters, and the Option and Argument extension hooks. Locating and connecting those definitions establishes the dispatch contract without requiring delegation over unrelated parsing and context-management code.
  - Execution evidence: context 147871 chars; 12 code searches over context; 0 whole-context prints

**Verified reference answer**

```diff
--- a/src/click/core.py
+++ b/src/click/core.py
@@ -1296,8 +1296,11 @@
         """Writes all the options into the formatter if they exist."""
         opts = []
         for param in self.get_params(ctx):
+            if isinstance(param, Argument):
+                continue
+
             rv = param.get_help_record(ctx)
-            if rv is not None and not isinstance(param, Argument):
+            if rv is not None:
                 opts.append(rv)
 
         if opts:
@@ -1308,8 +1311,11 @@
         """Writes the arguments that have a help record into the formatter."""
         args = []
         for param in self.get_params(ctx):
+            if not isinstance(param, Argument):
+                continue
+
             rv = param.get_help_record(ctx)
-            if rv is not None and isinstance(param, Argument):
+            if rv is not None:
                 args.append(rv)
 
         if args:

```

**Reviewer:** This is a natural, repository-dependent implementation request with a precise patch format. The behavioral requirements form a coherent help-rendering contract, including section-local dispatch and preservation of existing visibility and default handling. Naming the affected public APIs does not disclose the defective statements or prescribe the fix. The verified patch addresses the dispatch issue directly, and the task differs substantively from both its parent variation and the accepted tasks.

