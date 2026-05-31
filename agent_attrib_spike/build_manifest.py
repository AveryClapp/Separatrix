"""Freeze the pre-registered evaluation manifest (prereg §2-§3).

Deterministically enumerates {N_TASKS tasks} x {3 positions} x {3 fault types}
under the locked KB seed, keeps only instances whose injected fault flips the
outcome success->fail (the neutral inclusion filter), verifies the trace-depth
build gate (median >= 12), and reports the retained-set composition by
position x fault type. Writes manifest.json — the EXACT set both signals are
scored on in Task 4. Run once; commit before any signal is scored.
"""
import json
import statistics

import faults
import testbed

KB_SEED = 20260530      # locked
N_TASKS = 12            # locked (prereg §3)
DEPTH_GATE = 12         # locked (prereg §1)


def build():
    kb = testbed.build_kb(KB_SEED)
    instances, depths = [], []
    for task_seed in range(N_TASKS):
        task = testbed.make_task(kb, task_seed)
        base = testbed.run_baseline(task)
        depths.append(len(base))
        assert testbed.outcome(base, task) == "success", f"baseline {task_seed} not success"
        for pos in faults.POSITIONS:
            for ft in faults.FAULT_TYPES:
                corr, inj = faults.inject(base, pos, ft)
                if faults.flips_to_fail(corr, task):
                    instances.append({"task_seed": task_seed, "position": pos,
                                      "fault_type": ft, "injected_idx": inj,
                                      "trace_depth": len(base)})
    median_depth = statistics.median(depths)
    comp = {}
    for inst in instances:
        key = f"{inst['position']}|{inst['fault_type']}"
        comp[key] = comp.get(key, 0) + 1
    return {
        "kb_seed": KB_SEED, "n_tasks": N_TASKS, "depth_gate": DEPTH_GATE,
        "depth_min": min(depths), "depth_median": median_depth, "depth_max": max(depths),
        "depth_gate_pass": median_depth >= DEPTH_GATE,
        "n_instances": len(instances),
        "composition_by_position_x_fault": comp,
        "instances": instances,
    }


if __name__ == "__main__":
    m = build()
    with open("manifest.json", "w") as f:
        json.dump(m, f, indent=2)
    print(f"depth: min={m['depth_min']} median={m['depth_median']} max={m['depth_max']} "
          f"gate(>= {m['depth_gate']})={'PASS' if m['depth_gate_pass'] else 'FAIL'}")
    print(f"retained instances: {m['n_instances']} (of {N_TASKS*9} candidate)")
    print("composition (position|fault -> count):")
    for k in sorted(m["composition_by_position_x_fault"]):
        print(f"  {k}: {m['composition_by_position_x_fault'][k]}")
