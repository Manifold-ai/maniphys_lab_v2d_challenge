"""Choose one metric mesh per episode from the per-frame SAM 3D Objects runs.

Reads <sam3d_out>/fNNNNNN/scale_report.json for every picked frame. Candidates that fail their own
self-check (t3_scale_mesh.py) are dropped. Among the rest the one with the largest bounding-box diagonal is
kept: a partial view can only make the object smaller (ep14: a table seen top-on became a 4.8 cm disk),
while every candidate already matches its own frame in projection and depth. If the kept diagonals differ by
more than MAX_SPREAD of the largest, the views disagree and the episode is flagged (consistent=false) rather
than silently trusted.

Writes <sam3d_out>/object_scaled.glb (copy of the chosen candidate) and <sam3d_out>/scale_report.json.

    python t3_select_mesh.py <sam3d_out>
"""

import json
import shutil
import sys
from pathlib import Path

MAX_SPREAD = 0.3


def main() -> None:
    out = Path(sys.argv[1])
    cands = []
    for rep in sorted(out.glob("f*/scale_report.json")):
        r = json.loads(rep.read_text())
        r["dir"] = rep.parent.name
        r["diagonal_m"] = round(sum(e * e for e in r["extents_m"]) ** 0.5, 4)
        cands.append(r)
    passing = [c for c in cands if c["ok"]]
    report = {"candidates": [{k: c[k] for k in ("dir", "frame_index", "extents_m", "diagonal_m", "projected_box_iou", "depth_ratio", "ok", "why")} for c in cands]}
    if not passing:
        report.update({"ok": False, "why": f"none of {len(cands)} frames passed the self-check", "consistent": False})
    else:
        best = max(passing, key=lambda c: c["diagonal_m"])
        diags = [c["diagonal_m"] for c in passing]
        spread = (max(diags) - min(diags)) / max(diags)
        consistent = spread <= MAX_SPREAD
        shutil.copy(out / best["dir"] / "object_scaled.glb", out / "object_scaled.glb")
        report.update({"ok": True, "why": "" if consistent else f"passing views disagree: diagonal spread {spread:.0%}",
                       "consistent": consistent, "spread": round(spread, 3), "chosen": best["dir"], "frame_index": best["frame_index"],
                       "extents_m": best["extents_m"], "projected_box_iou": best["projected_box_iou"], "depth_ratio": best["depth_ratio"],
                       "n_passing": len(passing), "n_frames": len(cands)})
    (out / "scale_report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps({k: v for k, v in report.items() if k != "candidates"}))


if __name__ == "__main__":
    main()
