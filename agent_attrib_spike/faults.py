"""Neutral, programmatic fault injection (prereg §2).

Faults are fixed deterministic transforms applied at pre-fixed fractional
positions {0.25, 0.50, 0.75}; they are NOT hand-picked for findability. In this
numeric testbed all three fault types manifest as a corrupted scalar via three
DISTINCT mechanisms (documented honestly — see README): value scaling, a dropped
sub-result, and an additive tool-arg-style skew. Each is repairable by correct
re-execution, and the injected step is the clean ground-truth decisive step.
"""
import copy

import replay as replay_mod
import testbed

FAULT_TYPES = ["F1_value", "F2_drop", "F3_toolarg"]
POSITIONS = [0.25, 0.50, 0.75]


def candidate_steps(trace):
    """Value-bearing steps eligible for injection/attribution: everything between
    the Planner (idx 0) and the Reporter (last)."""
    return list(range(1, len(trace) - 1))


def _inject_index(trace, position):
    cands = candidate_steps(trace)
    return cands[round(position * (len(cands) - 1))]


def inject(trace, position, fault_type):
    """Return (corrupted_trace, injected_idx). Tags the step at `position` with a
    standing fault, then re-executes downstream so the failure propagates. The
    `fault` tag makes the corruption survive replay (re-applied unless repaired)."""
    idx = _inject_index(trace, position)
    cv = testbed.corrupt_value(trace[idx]["value"], fault_type)
    corrupted = copy.deepcopy(trace)
    corrupted[idx]["value"] = cv
    corrupted[idx]["fault"] = fault_type
    if fault_type == "F2_drop":
        # drop the required sub-result line from the narration
        corrupted[idx]["output"] = corrupted[idx]["output"].split("VALUE:")[0].rstrip() + "\n(VALUE missing)"
    else:
        ctx = testbed._context_str(corrupted[:idx])
        corrupted[idx]["output"] = testbed._value_turn(corrupted[idx]["agent"], corrupted[idx]["subtask"], cv, ctx)
    corrupted = replay_mod.replay(corrupted, idx, sub_value=cv,
                                  sub_output=corrupted[idx]["output"], regen_text=True)
    return corrupted, idx


def flips_to_fail(corrupted_trace, task):
    """Neutral inclusion filter: keep only instances whose injected fault
    actually flips the outcome success->fail (a genuinely decisive error)."""
    return testbed.outcome(corrupted_trace, task) == "fail"
