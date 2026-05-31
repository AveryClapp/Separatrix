"""Replay harness (prereg §1 contract).

`replay(trace, step_idx, sub_value, ...)` splices a substituted output into one
step and re-executes everything downstream. Value recomputation is deterministic
and API-free (the outcome channel), so `outcome_flip` can replay thousands of
counterfactuals cheaply. Narration is regenerated only when `regen_text=True`
(the text channel `cascade_divergence` needs).
"""
import copy

import testbed


def replay(trace, step_idx, sub_value=None, sub_output=None, regen_text=False):
    """Return a new trace with step_idx's value/output substituted and all
    downstream steps re-executed. Retriever values are independent of upstream
    (a real lookup), so only Calculator/Reporter values propagate."""
    new = copy.deepcopy(trace)
    if sub_value is not None:
        new[step_idx]["value"] = sub_value
    if sub_output is not None:
        new[step_idx]["output"] = sub_output

    for j in range(step_idx + 1, len(new)):
        s = new[j]
        if s["op"] in ("mul", "add", "sub"):
            clean = testbed.tool_calc(s["op"], new[s["refs"][0]]["value"], new[s["refs"][1]]["value"])
            s["value"] = testbed.corrupt_value(clean, s["fault"]) if s.get("fault") else clean
        elif s["agent"] == "Reporter":
            clean = new[s["refs"][0]]["value"]
            s["value"] = testbed.corrupt_value(clean, s["fault"]) if s.get("fault") else clean
        # Retriever: value is an independent lookup -> unchanged unless it is the
        # substituted step itself (handled above) or it carries a standing fault
        # (its corrupted value is left in place, never recomputed clean here).
        if regen_text:
            ctx = testbed._context_str(new[:j])
            if s["agent"] == "Reporter":
                s["output"] = testbed._reporter_turn(s["value"], ctx)
            elif s["op"] in ("mul", "add", "sub") or s["agent"] == "Calculator":
                s["output"] = testbed._value_turn("Calculator", s["subtask"], s["value"], ctx)
            else:
                s["output"] = testbed._value_turn("Retriever", s["subtask"], s["value"], ctx)
    return new


def replay_outcome(trace, step_idx, sub_value, task):
    """Cheap: substitute a value, recompute downstream values, return outcome."""
    return testbed.outcome(replay(trace, step_idx, sub_value=sub_value), task)
