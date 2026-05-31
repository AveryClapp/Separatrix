"""Task 4: run BOTH signals over the FROZEN manifest and score separation.

Reads manifest.json (the locked eval set), recomputes each instance's trace
deterministically, ranks every candidate step with outcome_flip and with
cascade_divergence, and reports the prereg §5 quantities: aggregate Δ_MRR + both
MRRs/top-1s, the tie-corrected one-sided Wilcoxon p, the GO decision, AND the
mandatory per-position breakdown. Writes results.json. No bar is read from here;
this only produces the numbers Task 5 judges against PREREGISTRATION.md.
"""
import json

import faults
import score
import signals
import testbed

PUBLISHED_STEP_LEVEL = 0.142   # Who&When best published step-level acc (external context only)


def run():
    man = json.load(open("manifest.json"))
    kb = testbed.build_kb(man["kb_seed"])
    flip_inst, div_inst, positions, rows = [], [], [], []
    for rec in man["instances"]:
        task = testbed.make_task(kb, rec["task_seed"])
        base = testbed.run_baseline(task)
        corr, inj = faults.inject(base, rec["position"], rec["fault_type"])
        assert inj == rec["injected_idx"], (inj, rec)
        fm = signals.rank_signal(corr, task, signals.outcome_flip)
        dm = signals.rank_signal(corr, task, signals.cascade_divergence)
        fs, ft = signals.to_instance(fm, inj)
        ds, dt = signals.to_instance(dm, inj)
        flip_inst.append((fs, ft))
        div_inst.append((ds, dt))
        positions.append(rec["position"])
        rows.append({"task_seed": rec["task_seed"], "position": rec["position"],
                     "fault_type": rec["fault_type"], "injected_idx": inj,
                     "flip_rank": score.rank_of(fs, ft), "div_rank": score.rank_of(ds, dt)})

    sep = score.separation(flip_inst, div_inst)
    by_pos = score.separation_by_position(flip_inst, div_inst, positions)
    go = score.go_decision(sep)
    results = {
        "n_instances": len(flip_inst),
        "separation": sep,
        "by_position": {str(k): v for k, v in by_pos.items()},
        "flip_top1": score.top1_accuracy(flip_inst),
        "div_top1": score.top1_accuracy(div_inst),
        "flip_mean_exam": score.mean_exam(flip_inst),
        "div_mean_exam": score.mean_exam(div_inst),
        "published_step_level_ref": PUBLISHED_STEP_LEVEL,
        "GO_bar": {"dmrr_margin": 0.20, "alpha": 0.05},
        "GO": bool(go),
        "rows": rows,
    }
    with open("results.json", "w") as f:
        json.dump(results, f, indent=2)
    return results


def _fmt(results):
    s = results["separation"]
    out = [f"n = {results['n_instances']} instances",
           "",
           f"               MRR     top-1",
           f"  outcome_flip  {s['mrr_flip']:.3f}   {results['flip_top1']:.3f}",
           f"  cascade_div   {s['mrr_div']:.3f}   {results['div_top1']:.3f}",
           f"  (published step-level ref: {results['published_step_level_ref']:.3f})",
           "",
           f"  Δ_MRR = {s['delta_mrr']:.3f}  (bar >= 0.20)",
           f"  Wilcoxon one-sided p = {s['wilcoxon_p']:.4f}  (bar < 0.05)",
           f"  ==> GO = {results['GO']}",
           "",
           "  per-position Δ_MRR (confound legibility):"]
    for k in sorted(results["by_position"]):
        v = results["by_position"][k]
        out.append(f"    pos {k}: Δ_MRR={v['delta_mrr']:.3f}  "
                   f"(flip {v['mrr_flip']:.3f} vs div {v['mrr_div']:.3f}, n={v['n']})")
    return "\n".join(out)


if __name__ == "__main__":
    r = run()
    print(_fmt(r))
