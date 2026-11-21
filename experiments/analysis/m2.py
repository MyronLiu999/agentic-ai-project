"""Milestone 2's numbers that the summarizer does not print (owner: myron, M9). analyze.py calls it per arm.

From the committed run records and the traces beside them, never from executable agent code:

  duplicates          sum of every duplicate_* count the checks returned (read from the sandbox)
  re-asks, facts used the checks' re_asks and facts_used counts (memory and long-session tasks)
  asks                approvals put up (the runner's approvals.asked) plus escalation packets sent, per run;
                      asks by action class (hook_decision lines answered "ask")
  approvals           decisions by action class: approved / decided, median seconds, split by who decided
                      (a person at the console, or a scripted answer, which takes no time)
  escalations         escalation lines per run, and how many were over the daily cap; irreversible writes after
                      a signal (the checks' irreversible_after_signal)
  malformed calls     tool calls rejected at the registry's boundary as invalid_arguments, per run
  input tokens        per model call (uncached + cached input), mean
  tools per call      with tools.loading = deferred, the definitions each request carried (search_tools lines'
                      `offered`); with all, every definition (scripts/definition_cost.py --milestone 2 --estimate)
  search misses       search_tools lines that matched nothing
  model calls         per run
  compactions         compaction lines, per run
  code calls          code_call lines and the calls their programs made
  hook decisions      allow / ask / deny counts
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict


def _lines(record: dict, kind: str) -> list[dict]:
    return [x for x in record.get("_trace") or [] if x.get("type") == kind]


def _mean(xs):
    return statistics.mean(xs) if xs else None


def _median(xs):
    return statistics.median(xs) if xs else None


def arm_numbers(records: list[dict]) -> dict:
    runs = len(records)
    measures = Counter()
    for r in records:
        for k, v in (r.get("measures") or {}).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                measures[k] += v
    approvals_asked = sum(int((r.get("approvals") or {}).get("asked") or 0) for r in records)
    escalations = [x for r in records for x in _lines(r, "escalation")]
    packets = sum(1 for x in escalations if not x.get("over_cap"))
    asks_by_class = Counter(x.get("action_class") for r in records for x in _lines(r, "hook_decision")
                            if x.get("answer") == "ask")
    decisions = defaultdict(lambda: {"decided": 0, "approved": 0, "seconds": []})
    by_who = Counter()
    for r in records:
        for x in _lines(r, "approval_decision"):
            who = "person" if x.get("who") == "operator" else "scripted"
            by_who[who] += 1
            row = decisions[(x.get("action_class"), who)]
            row["decided"] += 1
            row["approved"] += x.get("decision") == "approved"
            if isinstance(x.get("seconds"), (int, float)):
                row["seconds"].append(float(x["seconds"]))
    by_class = {f"{cls} ({who})": {"decided": row["decided"], "approved": row["approved"],
                                   "rate": row["approved"] / row["decided"] if row["decided"] else None,
                                   "median_seconds": _median(row["seconds"])}
                for (cls, who), row in sorted(decisions.items(), key=lambda kv: (str(kv[0][0]), kv[0][1]))}
    tool_calls = [x for r in records for x in _lines(r, "tool_call")]
    malformed = sum(1 for x in tool_calls if x.get("error_type") == "invalid_arguments")
    model_calls = [x for r in records for x in _lines(r, "model_call")]
    input_tokens = [int((x.get("usage") or {}).get("input_tokens") or 0)
                    + int((x.get("usage") or {}).get("cache_read_input_tokens") or 0) for x in model_calls]
    searches = [x for r in records for x in _lines(r, "search_tools")]
    offered = [int(x["offered"]) for x in searches if isinstance(x.get("offered"), int)]
    code = [x for r in records for x in _lines(r, "code_call")]
    hook = Counter(x.get("answer") for r in records for x in _lines(r, "hook_decision"))
    loading = Counter(str((r.get("switches") or {}).get("tools.loading", "unrecorded")) for r in records)
    per_run = lambda n: (n / runs) if runs else None
    return {
        "runs": runs,
        "duplicates": sum(v for k, v in measures.items() if k.startswith("duplicate")),
        "re_asks": measures.get("re_asks", 0), "facts_used": measures.get("facts_used", 0),
        "asks": approvals_asked + packets, "asks_per_run": per_run(approvals_asked + packets),
        "approvals_asked": approvals_asked, "asks_by_class": dict(asks_by_class),
        "approval_decisions": by_class, "decisions_by_who": dict(by_who),
        "escalations": len(escalations), "escalations_per_run": per_run(len(escalations)),
        "escalations_over_cap": len(escalations) - packets,
        "irreversible_after_signal": measures.get("irreversible_after_signal", 0),
        "malformed_calls": malformed, "malformed_per_run": per_run(malformed),
        "model_calls": len(model_calls), "model_calls_per_run": per_run(len(model_calls)),
        "input_tokens_per_call": _mean(input_tokens),
        "tools_loading": dict(loading), "tools_per_call_after_search": _mean(offered),
        "searches": len(searches), "search_misses": sum(1 for x in searches if not x.get("matches")),
        "compactions": sum(len(_lines(r, "compaction")) for r in records),
        "code_calls": len(code), "code_inner_calls": sum(int(x.get("calls") or 0) for x in code),
        "hook_decisions": dict(hook),
    }


def _fmt(x, digits=2):
    if x is None:
        return "n/a"
    return f"{x:.{digits}f}" if isinstance(x, float) else str(x)


def report_lines(m: dict) -> list[str]:
    classes = "; ".join(f"{k}: {v['approved']}/{v['decided']} approved, median {_fmt(v['median_seconds'])} s"
                        for k, v in m["approval_decisions"].items()) or "none"
    return [
        "Milestone 2:",
        f"  duplicates (checks) {m['duplicates']}; re-asks {m['re_asks']}; facts used {m['facts_used']}",
        f"  asks {m['asks']} ({_fmt(m['asks_per_run'])} per run): approvals {m['approvals_asked']}, "
        f"escalation packets {m['asks'] - m['approvals_asked']}; by class {m['asks_by_class'] or 'none'}",
        f"  approval decisions: {classes}",
        f"  escalations {m['escalations']} ({_fmt(m['escalations_per_run'])} per run, {m['escalations_over_cap']} over the cap); "
        f"irreversible writes after a signal {m['irreversible_after_signal']}",
        f"  malformed calls {m['malformed_calls']} ({_fmt(m['malformed_per_run'])} per run); "
        f"model calls per run {_fmt(m['model_calls_per_run'])}; input tokens per call {_fmt(m['input_tokens_per_call'], 0)}",
        f"  tools.loading {m['tools_loading']}; tools per call after a search {_fmt(m['tools_per_call_after_search'])}; "
        f"searches {m['searches']}, misses {m['search_misses']}",
        f"  compactions {m['compactions']}; code calls {m['code_calls']} ({m['code_inner_calls']} inner calls); "
        f"hook decisions {m['hook_decisions'] or 'none'}",
    ]
