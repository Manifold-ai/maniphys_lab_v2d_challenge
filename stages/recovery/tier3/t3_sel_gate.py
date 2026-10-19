"""Gate of the timeline-selection pilot (t3_sel_pilot.sh, 10-19; criteria registered in the Tier 3 handoff before the run).

    python t3_sel_gate.py <tier3 root> <review dir> <selection work dir, e.g. work_sel> <episode>...   (v2d_cari4d image)

Versions: ctrl = runs/work_fp (FoundationPose's own pick), sel = runs/work_sel (t3_fp_select.py), init = runs/work_init
(the 10-16 slerp pilot, the reference on the frames the user judged it right). Rotations are CoCoNet's output after
stage 07 (rotation frozen there, so = stage 06), pose_abs @ S2A, camera frame, official mesh frame; angles over the
object's symmetry rotations (gate/t3_symmetry.py).

G1 orientation, against the user's answers in checked_frames.json (evaluation only): sel within 30 deg of the version
   judged right. 10-20 answers: init on ep04 313/509/669; ctrl on ep03 117/131/345; pilot (runs/work_sel, the 10-19
   selection pilot) on ep03 451 (was init until the user's 10-20 re-check); on ep13 (held out for the ctrl-anchored
   selection) the evaluated run's own stage-05 pose ("stage05", judged on the FP layer) on 40/120/800/860/915 and ctrl
   on 226 (196/766 both wrong, not checked). G1 compares CoCoNet's output, so "stage05" asks that 06-07 kept it.
G2 jumps: frames whose orientation turns > 24 deg from the previous frame, fewer in sel than in ctrl, every episode.
G3 position: Y stage (after dr2s + dyn7), frames where sel turns > 24 deg from ctrl, pooled: median iou_vis
   difference sel - ctrl >= -0.01 (t3_sel_iou.py rows in <review dir>/report/iou_<episode>.jsonl). Reported beside it,
   not part of the verdict (10-20, user's choice b): the same on full-silhouette IoU ("all"), since iou_vis is empty
   on most hand-held frames (ep03: 284 of 391 rows) and so G3 sees mostly the rest segments.
Last line: SEL_GATE_PASS or SEL_GATE_FAIL <failed criteria>; the full record goes to <review dir>/gate.json.
"""

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import torch
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "gate"))
from t3_fp_select import sym_angle_deg  # noqa: E402
from t3_symmetry import Shape, symmetries  # noqa: E402

CHECKS = {"ep04_baseball_bat": {"init": [313, 509, 669]}, "ep03_contigo_coffee_mug": {"pilot": [451], "ctrl": [117, 131, 345]},
          "ep13_snack_box": {"stage05": [40, 120, 800, 860, 915], "ctrl": [226]}}
TOL_DEG, JUMP_DEG, CHANGED_DEG, IOU_MIN = 30.0, 24.0, 24.0, -0.01


def s2a_of(ep_dir: Path) -> np.ndarray:
    (export_dir,) = [d for d in (ep_dir / "export").iterdir() if d.is_dir()]
    return np.asarray(json.loads((export_dir / "wild_export.json").read_text())["source_object_mesh_to_aligned_transform"], np.float64)


def rotations(ep_dir: Path) -> np.ndarray:
    pr = torch.load(ep_dir / "inference" / "refined.pth", map_location="cpu", weights_only=False)["pr"]
    return (np.asarray(pr["pose_abs"], np.float64) @ s2a_of(ep_dir))[:, :3, :3]


def stage05_rotations(ep_dir: Path) -> np.ndarray:
    (pkl,) = sorted((ep_dir / "foundationpose").glob("episode_*.pkl"))
    with open(pkl, "rb") as fh:
        C = np.asarray(pickle.load(fh)["fp_poses_cam"], np.float64)[:, 0]
    return (C @ s2a_of(ep_dir))[:, :3, :3]


def main():
    root, review, sel_work, eps = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4:]
    meta = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    out, fails, pooled, pooled_all = {}, [], [], []
    for name in eps:
        ep = int(name[2:4])
        seq = f"episode_{ep:06d}"
        mesh = trimesh.load(root / "input" / meta[ep]["mesh"], force="mesh")
        body = mesh if mesh.is_watertight else mesh.convex_hull
        G, axis = symmetries(Shape(mesh, np.asarray(body.center_mass)), body.moment_inertia)
        R = {v: rotations(root / "runs" / w / name / "cari4d" / seq)
             for v, w in (("ctrl", "work_fp"), ("sel", sel_work), ("init", "work_init"), ("pilot", "work_sel"))
             if (root / "runs" / w / name / "cari4d" / seq / "inference" / "refined.pth").exists()}
        R["stage05"] = stage05_rotations(root / "runs" / sel_work / name / "cari4d" / seq)
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
        d_all = [r["Y_sel"]["all"] - r["Y_ctrl"]["all"] for r in rows if changed[r["frame"]] and r["Y_sel"]["all"] is not None and r["Y_ctrl"]["all"] is not None]
        pooled_all += d_all
        out[name] = {"G1_deg": g1, "G1_ok": all(v < TOL_DEG for v in g1.values()), "jumps_ctrl_sel": [jumps["ctrl"], jumps["sel"]],
                     "G2_ok": jumps["sel"] < jumps["ctrl"], "changed_frames": int(changed.sum()),
                     "Y_iou_vis_diff_changed": {"n": len(d), "median": round(float(np.median(d)), 4) if d else None,
                                                "good": int(sum(x > 0.05 for x in d)), "bad": int(sum(x < -0.05 for x in d))},
                     "Y_iou_all_diff_changed_info": {"n": len(d_all), "median": round(float(np.median(d_all)), 4) if d_all else None,
                                                     "good": int(sum(x > 0.05 for x in d_all)), "bad": int(sum(x < -0.05 for x in d_all))}}
        print(name, json.dumps(out[name]), flush=True)
        if not out[name]["G1_ok"]:
            fails.append(f"G1:{name}")
        if not out[name]["G2_ok"]:
            fails.append(f"G2:{name}")
    med = float(np.median(pooled)) if pooled else None
    out["G3"] = {"n": len(pooled), "median": None if med is None else round(med, 4), "ok": med is not None and med >= IOU_MIN}
    out["G3_all_info"] = {"n": len(pooled_all), "median": round(float(np.median(pooled_all)), 4) if pooled_all else None}
    if not out["G3"]["ok"]:
        fails.append("G3")
    out["verdict"] = "PASS" if not fails else "FAIL"
    out["fails"] = fails
    (review / "gate.json").write_text(json.dumps(out, indent=1))
    print("G3", json.dumps(out["G3"]))
    print("G3_all_info (not in the verdict)", json.dumps(out["G3_all_info"]))
    print("SEL_GATE_PASS" if not fails else "SEL_GATE_FAIL " + " ".join(fails))


if __name__ == "__main__":
    main()
