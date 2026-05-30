"""The two ranking signals (prereg §4).

outcome_flip (causal/primary): for each step, ask a capable model — BLIND to the
gold final answer — for plausible alternative outputs, replay each, score =
fraction that flip fail->success. Blindness rule: the alt-generator sees the
question, the prior (corrupted) trace, the step's sub-task, and the step's own
TOOL reading (the agent's legitimate tool output is part of its inputs, NOT
leakage). It never sees the task's ground-truth answer.

cascade_divergence (confound null): neutrally perturb a step (a non-repair value
edit), replay, score = summed embedding distance over the downstream narrations.
Earlier perturbations touch more downstream steps -> higher divergence, so this
ranks early/high-cascade steps high regardless of where the fault is.
"""
import json
import re

import numpy as np

import faults
import llm
import replay as replay_mod
import testbed


def correct_tool_value(trace, step_idx, task):
    """The agent's legitimate tool output at this step given the current trace."""
    s = trace[step_idx]
    if s["agent"] == "Retriever":
        return testbed.tool_lookup(task["kb"], s["station"], s["attr"])
    if s["op"] in ("mul", "add", "sub"):
        return testbed.tool_calc(s["op"], trace[s["refs"][0]]["value"], trace[s["refs"][1]]["value"])
    if s["agent"] == "Reporter":
        return trace[s["refs"][0]]["value"]
    return s["value"]


def _gen_distractors(subtask, toolval, k):
    """Blind LOCAL distractor values from the capable model.

    Deliberately given ONLY this step's sub-task and its tool reading — NOT the
    overall task or trace. Without the global context the model cannot compute
    the task's final answer, which structurally prevents the oracle-leakage
    degeneracy (a capable model otherwise "repairs" any late aggregation step by
    emitting the globally-correct total). The causal signal lives in the repair
    candidate (the locally-correct tool output, added by the caller); these are
    just plausible-but-wrong local perturbations.
    """
    msg = [{"role": "system", "content": "A single step of a calculation produced a number from "
            f"a tool. Return ONLY a JSON array of {k} integers that are plausible MISREADINGS of "
            "that number (e.g. off-by-a-bit, digit transposition, doubled/halved). Stay close to "
            "the given number; do not compute anything else."},
           {"role": "user", "content": f"Sub-task: {subtask}\nTool reading: {toolval}\n"
            f"Give {k} plausible misread integers as a JSON array."}]
    txt = llm.chat(msg, model=llm.ALT_MODEL, temperature=0.7, max_tokens=80)
    return _parse_ints(txt, k)


def _parse_ints(txt, n_alts):
    try:
        arr = json.loads(txt[txt.index("["):txt.rindex("]") + 1])
        vals = [int(round(float(x))) for x in arr]
    except Exception:
        vals = [int(x) for x in re.findall(r"-?\d+", txt)]
    return vals[:n_alts] if vals else []


def outcome_flip(trace, step_idx, task, n_alts=5):
    """Fraction of n_alts plausible alternatives that flip the outcome to success.

    The candidate set is the step's locally-correct tool output (the canonical
    counterfactual repair) plus capable-model local distractors. Only at the
    faulted step does the local repair differ from the corrupted value and flip
    the task; correct steps' repair is a no-op and distractors stay wrong.
    """
    toolval = correct_tool_value(trace, step_idx, task)
    distractors = _gen_distractors(trace[step_idx]["subtask"], toolval, n_alts - 1)
    alts, seen = [], set()
    for a in [toolval] + distractors:        # repair first, then distractors
        if a not in seen:
            seen.add(a)
            alts.append(a)
    alts = alts[:n_alts]
    flips = sum(replay_mod.replay_outcome(trace, step_idx, a, task) == "success" for a in alts)
    return flips / len(alts)


def _cosine(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


def cascade_divergence(trace, step_idx, task):
    """Summed downstream narration divergence under a neutral (non-repair) edit."""
    nv = trace[step_idx]["value"] + 7   # neutral perturbation, not the repair
    new = replay_mod.replay(trace, step_idx, sub_value=nv, regen_text=True)
    div = 0.0
    for j in range(step_idx + 1, len(trace)):
        div += 1.0 - _cosine(llm.embed(trace[j]["output"]), llm.embed(new[j]["output"]))
    return div


def rank_signal(trace, task, signal_fn, **kw):
    """Map each candidate step -> its signal score."""
    return {i: signal_fn(trace, i, task, **kw) for i in faults.candidate_steps(trace)}


def to_instance(score_map, injected_idx):
    """Convert a {step: score} map into (scores_list, target_pos) for score.py."""
    cands = sorted(score_map)
    return [score_map[i] for i in cands], cands.index(injected_idx)
