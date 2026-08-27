"""Rule condition AST evaluator.

Conditions are stored as a small JSON tree (see SYSTEM_ARCHITECTURE.md section 11.1)
rather than executable code, deliberately:
  1. Security — never eval() text or code coming out of the Rules database.
  2. Editability — a future visual Rule Builder maps 1:1 onto this AST.
  3. Testability — every node is a pure function over a plain dict context.

Evaluation context shape (built per atomic interval by the Timeline Engine):
    {
        "events": [SOFEvent, ...],       # active events for this interval
        "context": {...},                # derived scalars: hours_since_nor, etc.
        "voyage": {...},                 # voyage-level flags: via_sealine, etc.
        "params": {...},                 # the evaluating RuleVersion's own parameters
    }

Field references:
    "event.<attr>"   -> true if ANY active event has <attr> matching (op, value)
    "context.<key>"  -> scalar lookup in context["context"]
    "voyage.<key>"   -> scalar lookup in context["voyage"]
"""
from __future__ import annotations

from typing import Any


class ConditionError(ValueError):
    pass


def _apply_op(op: str, actual: Any, expected: Any) -> bool:
    if op == "eq":
        return actual == expected
    if op == "neq":
        return actual != expected
    if op == "lt":
        return actual is not None and actual < expected
    if op == "lte":
        return actual is not None and actual <= expected
    if op == "gt":
        return actual is not None and actual > expected
    if op == "gte":
        return actual is not None and actual >= expected
    if op == "in":
        return actual in expected
    if op == "not_in":
        return actual not in expected
    if op == "between":
        lo, hi = expected
        return actual is not None and lo <= actual <= hi
    raise ConditionError(f"Unknown operator: {op!r}")


def _resolve_value(value: Any, context: dict) -> Any:
    if isinstance(value, dict) and "param" in value:
        return context.get("params", {}).get(value["param"])
    return value


def _evaluate_leaf(node: dict, context: dict) -> bool:
    field = node["field"]
    op = node["op"]
    value = _resolve_value(node.get("value"), context)

    if field.startswith("event."):
        attr = field.split(".", 1)[1]
        events = context.get("events") or []
        if not events:
            return False
        return any(_apply_op(op, getattr(ev, attr, None), value) for ev in events)

    namespace, _, key = field.partition(".")
    if namespace not in context:
        raise ConditionError(f"Unknown field namespace: {field!r}")
    actual = context[namespace].get(key) if isinstance(context[namespace], dict) else None
    return _apply_op(op, actual, value)


def evaluate_condition_tree(node: dict | None, context: dict) -> bool:
    """Evaluate a condition AST node against an evaluation context.

    node is None => vacuously true (used for rules with no exceptions clause).
    """
    if node is None:
        return True
    if "all" in node:
        return all(evaluate_condition_tree(n, context) for n in node["all"])
    if "any" in node:
        return any(evaluate_condition_tree(n, context) for n in node["any"])
    if "not" in node:
        return not evaluate_condition_tree(node["not"], context)
    if "field" in node:
        return _evaluate_leaf(node, context)
    raise ConditionError(f"Malformed condition node: {node!r}")
