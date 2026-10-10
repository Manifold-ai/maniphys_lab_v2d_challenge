"""How well do t3_track_check.py's lost segments find the frames that are grossly wrong? Development measurement only:
the reference is the calibrated error from t3_world_eval.py (Tier 2 human calibration + v5.4 object), which no Tier 3
output reads.

    python t3_track_check_score.py <dir with track_check <ep>.npz> <world_eval *_frames dir> <out .json>
"""

import json
import sys
from pathlib import Path

import numpy as np

GROSS_M = (0.20, 0.50)


def main() -> None:
    checks, frames, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    rows, tot = [], {g: np.zeros(4, int) for g in GROSS_M}  # tp fp fn tn
    for f in sorted(frames.glob("*.npz")):
        c = checks / f.name
        if not c.exists():
            continue
        ref, chk = np.load(f), np.load(c)
        n = min(len(ref["err_m"]), len(chk["lost"]))
        err, lost, vis = ref["err_m"][:n], chk["lost"][:n], ref["visible"][:n]
        row = {"episode": f.stem, "frames": int(vis.sum()), "lost_frames": int(lost[vis].sum()),
               "mean_err_cm_all": round(float(np.nanmean(err)) * 100, 1),
               "mean_err_cm_kept": round(float(np.nanmean(err[vis & ~lost])) * 100, 1) if (vis & ~lost).any() else None}
        for g in GROSS_M:
            gross = vis & (err > g)
            tp, fp = int((lost & gross).sum()), int((lost & vis & ~gross).sum())
            fn, tn = int((~lost & gross).sum()), int((~lost & vis & ~gross).sum())
            tot[g] += [tp, fp, fn, tn]
            row[f"gross{int(g * 100)}"] = {"frames": int(gross.sum()), "recall": round(tp / (tp + fn), 3) if tp + fn else None,
                                           "precision": round(tp / (tp + fp), 3) if tp + fp else None}
        rows.append(row)
    summary = {f"gross{int(g * 100)}": {"recall": round(t[0] / max(1, t[0] + t[2]), 3), "precision": round(t[0] / max(1, t[0] + t[1]), 3),
                                        "tp_fp_fn_tn": t.tolist()} for g, t in tot.items()}
    out.write_text(json.dumps({"summary": summary, "episodes": rows}, indent=1))
    print(json.dumps(summary))
    for r in rows:
        print(json.dumps(r))


if __name__ == "__main__":
    main()
