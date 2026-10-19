"""Judge of the BETA A/B (t3_beta_ab.sh; rule registered in the Tier 3 handoff before the run), then the evaluation.

Judge: per episode the mean of the Y-stage full-silhouette IoU of sel (Y_sel.all) over the sampled frames, the
episodes weighted equally; highest wins; among values within TIE of the highest, fewest sel rotation jumps summed over
the episodes (gate.json jumps_ctrl_sel), then the smaller BETA. The checked frames (gate G1) are printed after the
verdict as evaluation only.

    python t3_beta_ab_summary.py <review root> <beta>=<tag>...
"""

import json
import sys
from pathlib import Path

import numpy as np

TIE = 0.005
root, runs = Path(sys.argv[1]), [(float(a.split("=")[0]), a.split("=")[1]) for a in sys.argv[2:]]
rows = []
for beta, tg in runs:
    gate = json.loads((root / tg / "gate.json").read_text())
    eps = sorted(k for k in gate if k.startswith("ep"))
    per = {}
    for name in eps:
        r = [json.loads(l) for l in (root / tg / "report" / f"iou_{name}.jsonl").read_text().splitlines() if l.strip()]
        sel = [x["Y_sel"]["all"] for x in r if x["Y_sel"]["all"] is not None]
        ctrl = [x["Y_ctrl"]["all"] for x in r if x["Y_ctrl"]["all"] is not None]
        per[name] = {"Y_sel_all_mean": float(np.mean(sel)), "Y_ctrl_all_mean": float(np.mean(ctrl)), "n": len(sel),
                     "jumps_ctrl_sel": gate[name]["jumps_ctrl_sel"], "changed": gate[name]["changed_frames"], "G1_deg": gate[name]["G1_deg"]}
    rows.append({"beta": beta, "tag": tg, "score": float(np.mean([p["Y_sel_all_mean"] for p in per.values()])),
                 "jumps": int(sum(p["jumps_ctrl_sel"][1] for p in per.values())), "per": per, "gate": gate["verdict"], "fails": gate["fails"]})
best = max(r["score"] for r in rows)
win = sorted((r for r in rows if r["score"] >= best - TIE), key=lambda r: (r["jumps"], r["beta"]))[0]
print("judge: mean over episodes of mean Y_sel.all; tie", TIE, "-> fewest jumps -> smaller BETA")
for r in rows:
    eps = " ".join(f"{n[:4]} {p['Y_sel_all_mean']:.4f} (ctrl {p['Y_ctrl_all_mean']:.4f}, jumps {p['jumps_ctrl_sel'][1]}, changed {p['changed']})"
                   for n, p in r["per"].items())
    print(f"BETA {r['beta']:<5} score {r['score']:.4f} jumps {r['jumps']:3d} | {eps}")
print(f"WINNER BETA {win['beta']} ({win['tag']})")
print("evaluation only (checked frames, gate G1 deg; < 30 is right):")
for r in rows:
    print(f"BETA {r['beta']:<5} gate {r['gate']} {r['fails']} | " + " ".join(f"{n[:4]} {json.dumps(p['G1_deg'])}" for n, p in r["per"].items()))
json.dump({"tie": TIE, "winner": win["beta"], "rows": rows}, open(root / "summary.json", "w"), indent=1)
