"""Synthetic replayable multi-agent testbed (prereg §1).

A 4-role pipeline — Planner -> {Retriever, Calculator}* -> Reporter — solves a
multi-hop numeric question over a FIXED, FICTIONAL knowledge base. Fictional
entities/numbers are deliberate: the agents cannot shortcut a lookup from prior
knowledge nor silently repair a corrupted value from memory, so an injected
fault propagates cleanly downstream.

The computation is a SEQUENTIAL FOLD: running = running OP lookup, one lookup
turn and one calc turn per hop. This gives both step-depth (>= 12 turns) AND
dependency-depth: perturbing step k propagates through EVERY later calc, so the
cascade position-gradient genuinely exists (without it the confound — and thus
the kill-test — is vacuous).

Two parallel channels per step:
  * `value`  — canonical number, deterministic via tools/operands (outcome flows
               through values -> deterministic, API-free to replay).
  * `output` — the agent's LLM narration (what `cascade_divergence` embeds).
"""
import random

import llm

ATTRS = ["alpha", "beta", "gamma"]
# fixed op pattern after the start hop; +/- keeps magnitudes bounded while every
# step still depends on the previous one (deep chain).
OP_PATTERN = ["add", "sub", "add", "sub", "add"]


def build_kb(seed):
    """Fixed fictional KB: 6 stations, each with integer alpha/beta/gamma."""
    rng = random.Random(seed)
    names = ["Zorin", "Ylex", "Qualt", "Brux", "Vand", "Threll"]
    return {n: {a: rng.randint(2, 19) for a in ATTRS} for n in names}


def make_task(kb, seed):
    """A sequential-fold task over distinct (station, attr) hops.

    ops[0] = ('start', station, attr) seeds the running value; each later op is
    ('add'|'sub', station, attr) folding in a fresh lookup. Ground truth is the
    exact fold result.
    """
    rng = random.Random(seed + 1000)
    stations = rng.sample(list(kb), len(OP_PATTERN) + 1)
    attrs = [rng.choice(ATTRS) for _ in stations]
    ops = [("start", stations[0], attrs[0])]
    for i, opname in enumerate(OP_PATTERN, start=1):
        ops.append((opname, stations[i], attrs[i]))
    gt = _fold(kb, ops)
    return {"ops": ops, "question": _render_question(ops), "ground_truth": gt, "kb": kb}


def _fold(kb, ops):
    running = None
    for opname, st, attr in ops:
        v = kb[st][attr]
        running = v if opname == "start" else tool_calc(opname, running, v)
    return running


def _render_question(ops):
    parts = [f"start with the {ops[0][2]} of {ops[0][1]}"]
    for opname, st, attr in ops[1:]:
        word = "add" if opname == "add" else "subtract"
        parts.append(f"{word} the {attr} of {st}")
    return ("Using ONLY the station database, compute a running total: "
            + ", then ".join(parts) + ". Report the final integer.")


# ---- deterministic tools ----
def tool_lookup(kb, station, attr):
    return kb[station][attr]


def tool_calc(op, a, b):
    if op == "mul":
        return a * b
    if op == "sub":
        return a - b
    return a + b


def corrupt_value(clean, fault_type):
    """Persistent fault transform applied to a step's otherwise-clean value.

    A fault is a standing miscomputation, not a one-off value: replay re-applies
    it whenever the faulted step is recomputed, so the failure survives unless
    that exact step is repaired (substituted).
    """
    if fault_type == "F1_value":
        return clean * 2 + 1            # wrong scaled value
    if fault_type == "F2_drop":
        return 0                         # sub-result dropped
    if fault_type == "F3_toolarg":
        return clean + max(1, clean // 2)  # additive skew (wrong tool args)
    raise ValueError(fault_type)


# ---- agent turns (LLM narration; canonical value passed in) ----
def _planner_turn(question):
    msg = [{"role": "system", "content": "You are Planner in a multi-agent solver. "
            "Briefly list the ordered sub-steps (lookups and running arithmetic) to solve "
            "the task. Plain text, no preamble."},
           {"role": "user", "content": question}]
    return llm.chat(msg, max_tokens=250)


def _value_turn(agent, subtask, value, context):
    msg = [{"role": "system", "content": f"You are {agent} in a multi-agent solver. "
            "State the result of your sub-step in one short sentence, then on a new line "
            "write exactly 'VALUE: <number>'. Use the provided number verbatim."},
           {"role": "user", "content": f"Context so far:\n{context}\n\nYour sub-step: "
            f"{subtask}\nThe tool returned: {value}"}]
    return llm.chat(msg, max_tokens=80)


def _reporter_turn(value, context):
    msg = [{"role": "system", "content": "You are Reporter. Give the final answer in one line "
            "as exactly 'ANSWER: <number>', using the provided total verbatim."},
           {"role": "user", "content": f"Context so far:\n{context}\n\nFinal total: {value}"}]
    return llm.chat(msg, max_tokens=40)


def _context_str(steps):
    return "\n".join(f"[{s['idx']}] {s['agent']}: {s['output']}" for s in steps) or "(none)"


def _step(idx, agent, subtask, refs, op, value, output, station=None, attr=None):
    return {"idx": idx, "agent": agent, "subtask": subtask, "refs": refs, "op": op,
            "value": value, "output": output, "station": station, "attr": attr, "fault": None}


def run_baseline(task):
    """Execute the fold end to end, returning the trace (list of step dicts)."""
    kb = task["kb"]
    steps = [_step(0, "Planner", "plan", [], None, None, _planner_turn(task["question"]))]
    running_idx = None
    for opname, st, attr in task["ops"]:
        # 1) lookup turn
        idx = len(steps)
        lv = tool_lookup(kb, st, attr)
        out = _value_turn("Retriever", f"look up {attr} of {st}", lv, _context_str(steps))
        steps.append(_step(idx, "Retriever", f"look up {attr} of {st}", [], None, lv, out, st, attr))
        look_idx = idx
        if opname == "start":
            running_idx = look_idx
            continue
        # 2) calc turn folding the lookup into the running total
        idx = len(steps)
        rv = tool_calc(opname, steps[running_idx]["value"], lv)
        subtask = f"{opname} step[{look_idx}] into running step[{running_idx}]"
        out = _value_turn("Calculator", subtask, rv, _context_str(steps))
        steps.append(_step(idx, "Calculator", subtask, [running_idx, look_idx], opname, rv, out))
        running_idx = idx
    total = steps[running_idx]["value"]
    idx = len(steps)
    steps.append(_step(idx, "Reporter", "report", [running_idx], None, total,
                       _reporter_turn(total, _context_str(steps))))
    return steps


def outcome(trace, task):
    """success iff the Reporter's value equals the task ground truth."""
    return "success" if trace[-1]["value"] == task["ground_truth"] else "fail"
