import contextvars
import json
import warnings

import structlog
from structlog import contextvars as cv
from structlog import threadlocal as tl
from structlog.testing import ReturnLogger


def assemble(context_class, processors, **values):
    return structlog.wrap_logger(
        ReturnLogger(),
        wrapper_class=structlog.BoundLogger,
        context_class=context_class,
        processors=processors,
        cache_logger_on_first_use=False,
    ).bind(**values)


def keyword_snapshot(result):
    args, kwargs = result
    assert args == ()
    return dict(kwargs)


def context_snapshot(logger):
    return dict(structlog.get_context(logger).copy())


def run_ambient(clear, bind, scoped, merge):
    clear()
    bind(account="ambient", region="west")
    base = assemble(dict, [merge], account="bound", user="u0")

    with scoped(account="scope", request="r1"):
        derived = base.bind(user="u1")
        during = keyword_snapshot(derived.info("during", account="call"))
        bind(region="east", extra="kept")

    after = keyword_snapshot(base.info("after"))
    result = {
        "during": during,
        "after": after,
        "base_context": context_snapshot(base),
        "derived_context": context_snapshot(derived),
    }
    clear()
    return result


def run_wrapped():
    context_class = tl.wrap_dict(dict)
    context_class().clear()
    base = assemble(
        context_class, [], account="bound", region="west", user="u0"
    )

    with tl.tmp_bind(base, account="scope", request="r1") as scoped:
        derived = scoped.bind(user="u1")
        during = keyword_snapshot(derived.info("during", account="call"))
        scoped.bind(region="east", extra="kept")

    after = keyword_snapshot(base.info("after"))
    result = {
        "during": during,
        "after": after,
        "base_context": context_snapshot(base),
        "derived_context": context_snapshot(derived),
    }
    context_class().clear()
    return result


def main():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        answer = {
            "contextvars": contextvars.Context().run(
                run_ambient,
                cv.clear_contextvars,
                cv.bind_contextvars,
                cv.bound_contextvars,
                cv.merge_contextvars,
            ),
            "threadlocal": run_ambient(
                tl.clear_threadlocal,
                tl.bind_threadlocal,
                tl.bound_threadlocal,
                tl.merge_threadlocal,
            ),
            "wrapped_dict": run_wrapped(),
        }
    print(json.dumps({"answer": answer}, sort_keys=True))


if __name__ == "__main__":
    main()