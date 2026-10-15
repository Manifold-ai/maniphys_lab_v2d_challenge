"""Compare a CARI4D pilot's object orientation with the register-every-frame runs it was copied from (report only; runs
in the v2d_cari4d image on CPU).

Per episode, base = runs/work_fp/<ep>, pilot = runs/<pilot work>/<ep>, for CoCoNet's output (stage 06, coconet.pth
pr.pose_abs) and the post-optimization's (07, refined.pth pr.pose_abs_postopt), camera frame:
  jumps        single-frame turns over JUMP_DEG (as t3_stage_flips.py), all frames and inside the frames the pilot
               re-initialized (foundationpose/fp_init.json, t3_fp_init.py; none for other pilots);
  silhouette   the official mesh at the pose against the SAM2 object mask, person pixels removed from both, dilated IoU
               (t3_object_check.py's functions and constants). No ground truth: it scores how well each pose explains
               the video. Taken on every frame either version jumps on, every re-initialized frame, the checked frames
               and every STRIDE-th frame; frames with too few visible pixels are left out. A head-to-tail flip of a
               long thin object can keep its silhouette, so this cannot see every flip (ep04's bat);
  checked      the frames checked against the video (as t3_stage_flips.CHECKED): pilot vs base turn, and which side the
               silhouette prefers.
Written as one json per call; one line per episode is printed.

    python t3_pilot_compare.py <tier3 runs dir> <pilot work name> <mesh root> <out json> <episode name> ...
"""

import json
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from t3_object_check import MIN_VISIBLE_PX, load_mesh, rasterise, visible_iou  # noqa: E402
from t3_stage_flips import CHECKED, JUMP_DEG, angle_deg, step_deg  # noqa: E402

STRIDE = 10


def poses(c: Path) -> dict:
    co = torch.load(c / "inference" / "coconet.pth", map_location="cpu", weights_only=False)["pr"]["pose_abs"]
    re = torch.load(c / "inference" / "refined.pth", map_location="cpu", weights_only=False)["pr"]["pose_abs_postopt"]
    return {"06": np.asarray(co, np.float64), "07": np.asarray(re, np.float64)}


def jump_frames(P):
    R = P[:, :3, :3]
    ok = np.isfinite(R).all((1, 2))
    R = np.where(ok[:, None, None], R, np.eye(3))
    return set((np.flatnonzero((step_deg(R) > JUMP_DEG) & ok[1:] & ok[:-1]) + 1).tolist())


def main():
    runs, pilot, mesh_root, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
    report = {}
    for name in sys.argv[5:]:
        seq = f"episode_{int(name[2:4]):06d}"
        work_b, work_p = runs / "work_fp" / name, runs / pilot / name
        cb, cp = work_b / "cari4d" / seq, work_p / "cari4d" / seq
        base, pil = poses(cb), poses(cp)
        n = len(base["06"])
        init = cp / "foundationpose" / "fp_init.json"
        reinit = np.zeros(n, bool)
        if init.exists():
            for a, b in json.loads(init.read_text())["replaced_runs"]:
                reinit[a:b] = True
        export = json.loads((cb / "export" / seq / "wild_export.json").read_text())
        s2a = np.asarray(export["source_object_mesh_to_aligned_transform"], np.float64)
        ki = export["intrinsics"]
        k = np.array([[ki["fx"], 0, ki["cx"]], [0, ki["fy"], ki["cy"]], [0, 0, 1]]) if isinstance(ki, dict) else np.asarray(ki, np.float64).reshape(3, 3)
        obj = name[5:]
        verts, faces = load_mesh(mesh_root / obj / f"{obj}.glb")

        row = {"frames": n, "reinit_frames": int(reinit.sum())}
        jumps = {}
        for st in ("06", "07"):
            jb, jp = jump_frames(base[st]), jump_frames(pil[st])
            jumps[st] = jb | jp
            row[f"jumps_{st}_base_pilot"] = [len(jb), len(jp)]
            row[f"jumps_{st}_in_reinit_base_pilot"] = [int(sum(reinit[f] for f in jb)), int(sum(reinit[f] for f in jp))]
        chk = CHECKED.get(seq, [])
        frames = sorted(set(range(0, n, STRIDE)) | jumps["06"] | jumps["07"] | set(np.flatnonzero(reinit).tolist()) | set(chk))

        def iou_at(P, i):
            om, pm = work_b / "sam2_masks" / "1" / f"{i:06d}.png", work_b / "sam2_masks" / "0" / f"{i:06d}.png"
            if not om.exists() or not np.isfinite(P[i]).all():
                return None
            m = np.asarray(Image.open(om).convert("L")) > 0
            person = np.asarray(Image.open(pm).convert("L")) > 0 if pm.exists() else np.zeros_like(m)
            t = P[i] @ s2a
            rv, mv = rasterise(verts @ t[:3, :3].T + t[:3, 3], faces, k, *m.shape) & ~person, m & ~person
            if rv.sum() < MIN_VISIBLE_PX or mv.sum() < MIN_VISIBLE_PX:
                return None
            return visible_iou(rv, mv)

        per = {}
        for i in frames:
            b, p = iou_at(base["07"], i), iou_at(pil["07"], i)
            if b is not None and p is not None:
                per[i] = (b, p)

        def summ(sel):
            v = np.array([per[i] for i in sel if i in per])
            if not len(v):
                return None
            return {"n": len(v), "iou_base_pilot_p50": [round(float(np.median(v[:, 0])), 3), round(float(np.median(v[:, 1])), 3)],
                    "pilot_better_worse_by_0.05": [int((v[:, 1] - v[:, 0] > 0.05).sum()), int((v[:, 0] - v[:, 1] > 0.05).sum())]}

        row["iou_07_sampled"] = summ(range(0, n, STRIDE))
        row["iou_07_reinit"] = summ(np.flatnonzero(reinit).tolist())
        row["iou_07_jump_frames"] = summ(sorted(jumps["07"]))
        if chk:
            turn = angle_deg(base["07"][chk][:, :3, :3], pil["07"][chk][:, :3, :3])
            row["checked"] = {"frames": chk, "pilot_vs_base_deg": [round(float(x), 1) for x in turn],
                              "iou_base_pilot": [[round(v, 3) for v in per[i]] if i in per else None for i in chk]}
        row["turn_07_vs_base_deg_p50_p90_max"] = [round(float(x), 1) for x in np.nanpercentile(angle_deg(base["07"][:, :3, :3], pil["07"][:, :3, :3]), [50, 90, 100])]
        report[name] = row
        print(name, json.dumps(row), flush=True)
    out.write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
