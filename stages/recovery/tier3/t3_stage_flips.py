"""Which CARI4D stage puts the per-frame orientation jumps in (diagnosis, report only; runs in the v2d_cari4d image).

Per episode dir (<work>/<ep>/cari4d/episode_NNNNNN): single-frame turns over JUMP_DEG (OMEGA_MAX / fps of
gate/t3_dynamics_check.py), camera frame, in FoundationPose's output (stage 05), CoCoNet's (06) and the
post-optimization's (07); and on the frames checked against the video (handoff 10-15: ep03 117/131/345/451 and ep01
223/238/301 right in best_hm, ep04 313/509/669 head and tail swapped) how far each stage is from the final pose.
10-15 on runs/work_fp: 05 had 3/39/31/13 jumps on ep03/02/28/13, 06 and 07 35/112/88/54 (equal to best_hm's).

    docker run ... v2d_cari4d:latest python t3_stage_flips.py <episode dir> ... [--out <json>]
"""

import json
import pickle
import sys

import numpy as np
import torch

JUMP_DEG = 24.0
CHECKED = {"episode_000003": [117, 131, 345, 451], "episode_000001": [223, 238, 301], "episode_000004": [313, 509, 669]}


def step_deg(R):
    d = np.einsum("tij,tkj->tik", R[1:], R[:-1])
    return np.degrees(np.arccos(np.clip((np.trace(d, axis1=1, axis2=2) - 1) / 2, -1, 1)))


def angle_deg(a, b):
    return np.degrees(np.arccos(np.clip((np.einsum("tij,tij->t", a, b) - 1) / 2, -1, 1)))


def main():
    args = sys.argv[1:]
    out = args[args.index("--out") + 1] if "--out" in args else None
    dirs = [a for i, a in enumerate(args) if a != "--out" and (i == 0 or args[i - 1] != "--out")]
    report = {}
    for c in dirs:
        seq = c.rstrip("/").split("/")[-1]
        fp = pickle.load(open(f"{c}/foundationpose/{seq}.pkl", "rb"))
        n = len(fp["frames"])
        stages = {"05_foundationpose": fp["fp_poses_cam"].reshape(n, 4, 4)[:, :3, :3]}
        stages["06_coconet"] = np.asarray(torch.load(f"{c}/inference/coconet.pth", map_location="cpu", weights_only=False)["pr"]["pose_abs"], np.float64)[:, :3, :3]
        stages["07_refined"] = np.asarray(torch.load(f"{c}/inference/refined.pth", map_location="cpu", weights_only=False)["pr"]["pose_abs_postopt"], np.float64)[:, :3, :3]
        row = {}
        for k, R in stages.items():
            ok = np.isfinite(R).all((1, 2))
            R = np.where(ok[:, None, None], R, np.eye(3))
            j = np.flatnonzero((step_deg(R) > JUMP_DEG) & ok[1:] & ok[:-1]) + 1
            row[k] = {"jumps": len(j), "frames": j.tolist()}
        d = angle_deg(stages["06_coconet"], stages["07_refined"])
        row["07_vs_06_deg_p50_p99_max"] = [round(float(x), 2) for x in np.percentile(d, [50, 99, 100])]
        if seq in CHECKED:
            fr = CHECKED[seq]
            row["checked"] = {k: [round(float(angle_deg(R[fr], stages["07_refined"][fr])[i]), 1) for i in range(len(fr))]
                              for k, R in stages.items() if k != "07_refined"} | {"frames": fr}
        report[seq] = row
        print(seq, {k: v["jumps"] for k, v in row.items() if isinstance(v, dict) and "jumps" in v},
              "07 vs 06 deg p50/p99/max", row["07_vs_06_deg_p50_p99_max"], row.get("checked", ""), flush=True)
    if out:
        json.dump(report, open(out, "w"), indent=1)


if __name__ == "__main__":
    main()
