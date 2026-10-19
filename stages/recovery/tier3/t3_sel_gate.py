"""Gate of the timeline-selection pilot (t3_sel_pilot.sh, 10-19; criteria registered in the Tier 3 handoff before the run).

    python t3_sel_gate.py <tier3 root> <review dir> <selection work dir, e.g. work_sel> <episode>...   (v2d_cari4d image)

Versions: ctrl = runs/work_fp (FoundationPose's own pick), sel = runs/work_sel (t3_fp_select.py), init = runs/work_init
(the 10-16 slerp pilot, the reference on the frames the user judged it right). Rotations are CoCoNet's output after
stage 07 (rotation frozen there, so = stage 06), pose_abs @ S2A, camera frame, official mesh frame; angles over the
object's symmetry rotations (gate/t3_symmetry.py).

G1 orientation, against the user's answers in checked_frames.json (evaluation only): sel within 30 deg of init on
   ep04 313/509/669 and ep03 451 (init judged right there), within 30 deg of ctrl on ep03 117/131/345 (judged right).
G2 jumps: frames whose orientation turns > 24 deg from the previous frame, fewer in sel than in ctrl, every episode.
G3 position: Y stage (after dr2s + dyn7), frames where sel turns > 24 deg from ctrl, pooled: median iou_vis
   difference sel - ctrl >= -0.01 (t3_sel_iou.py rows in <review dir>/report/iou_<episode>.jsonl).
Last line: SEL_GATE_PASS or SEL_GATE_FAIL <failed criteria>; the full record goes to <review dir>/gate.json.
"""

import json
import sys
from pathlib import Path

import numpy as np
import torch
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "gate"))
from t3_fp_select import sym_angle_deg  # noqa: E402
from t3_symmetry import Shape, symmetries  # noqa: E402

CHECKS = {"ep04_baseball_bat": {"init": [313, 509, 669]}, "ep03_contigo_coffee_mug": {"init": [451], "ctrl": [117, 131, 345]}}
TOL_DEG, JUMP_DEG, CHANGED_DEG, IOU_MIN = 30.0, 24.0, 24.0, -0.01


def rotations(ep_dir: Path) -> np.ndarray:
    pr = torch.load(ep_dir / "inference" / "refined.pth", map_location="cpu", weights_only=False)["pr"]
    (export_dir,) = [d for d in (ep_dir / "export").iterdir() if d.is_dir()]
    s2a = np.asarray(json.loads((export_dir / "wild_export.json").read_text())["source_object_mesh_to_aligned_transform"], np.float64)
    return (np.asarray(pr["pose_abs"], np.float64) @ s2a)[:, :3, :3]


def main():
    root, review, sel_work, eps = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4:]
    meta = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    out, fails, pooled = {}, [], []
    for name in eps:
        ep = int(name[2:4])
        seq = f"episode_{ep:06d}"
        mesh = trimesh.load(root / "input" / meta[ep]["mesh"], force="mesh")
        body = mesh if mesh.is_watertight else mesh.convex_hull
        G, axis = symmetries(Shape(mesh, np.asarray(body.center_mass)), body.moment_inertia)
        R = {v: rotations(root / "runs" / w / name / "cari4d" / seq) for v, w in (("ctrl", "work_fp"), ("sel", sel_work), ("init", "work_init"))
             if (root / "runs" / w / name / "cari4d" / seq / "inference" / "refined.pth").exists()}
        ang = lambda a, b, f: float(sym_angle_deg(R[a][f:f + 1], R[b][f:f + 1], G, axis)[0, 0])
        g1 = {}
        for ref, frames in CHECKS.get(name, {}).items():
            for f in frames:
                g1[f"{f}_vs_{ref}"] = round(ang("sel", ref, f), 1)
        n = len(R["sel"])
        jumps = {v: int(sum(sym_angle_deg(R[v][f:f + 1], R[v][f + 1:f + 2], G, axis)[0, 0] > JUMP_DEG for f in range(n - 1))) for v in ("ctrl", "sel")}
        changed = np.array([ang("sel", "ctrl", f) > CHANGED_DEG for f in range(n)])
        rows = [json.loads(l) for l in (review / "report" / f"iou_{name}.jsonl").read_text().splitlines() if l.strip()]
        d = [r["Y_sel"]["vis"] - r["Y_ctrl"]["vis"] for r in rows if changed[r["frame"]] and r["Y_sel"]["vis"] is not None and r["Y_ctrl"]["vis"] is not None]
        pooled += d
        out[name] = {"G1_deg": g1, "G1_ok": all(v < TOL_DEG for v in g1.values()), "jumps_ctrl_sel": [jumps["ctrl"], jumps["sel"]],
                     "G2_ok": jumps["sel"] < jumps["ctrl"], "changed_frames": int(changed.sum()),
                     "Y_iou_vis_diff_changed": {"n": len(d), "median": round(float(np.median(d)), 4) if d else None,
                                                "good": int(sum(x > 0.05 for x in d)), "bad": int(sum(x < -0.05 for x in d))}}
        print(name, json.dumps(out[name]), flush=True)
        if not out[name]["G1_ok"]:
            fails.append(f"G1:{name}")
        if not out[name]["G2_ok"]:
            fails.append(f"G2:{name}")
    med = float(np.median(pooled)) if pooled else None
    out["G3"] = {"n": len(pooled), "median": None if med is None else round(med, 4), "ok": med is not None and med >= IOU_MIN}
    if not out["G3"]["ok"]:
        fails.append("G3")
    out["verdict"] = "PASS" if not fails else "FAIL"
    out["fails"] = fails
    (review / "gate.json").write_text(json.dumps(out, indent=1))
    print("G3", json.dumps(out["G3"]))
    print("SEL_GATE_PASS" if not fails else "SEL_GATE_FAIL " + " ".join(fails))


if __name__ == "__main__":
    main()
