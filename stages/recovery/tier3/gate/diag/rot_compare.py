"""work_fp (rotation frozen) vs work_rot (--optimize_object_rotation): final-pose jumps by size, change vs CoCoNet, checked frames."""
import sys, numpy as np, torch
CHECKED = {"episode_000003": ([117, 131, 345, 451], "hm right"), "episode_000001": ([223, 238, 301], "hm right"), "episode_000004": ([313, 509, 669], "hm flipped")}
def R_of(p): return np.asarray(torch.load(p, map_location="cpu", weights_only=False)["pr"]["pose_abs_postopt" if "refined" in p else "pose_abs"], np.float64)[:, :3, :3]
def steps(R):
    d = np.einsum("tij,tkj->tik", R[1:], R[:-1]); return np.degrees(np.arccos(np.clip((np.trace(d, axis1=1, axis2=2) - 1) / 2, -1, 1)))
def ang(a, b): return np.degrees(np.arccos(np.clip((np.einsum("tij,tij->t", a, b) - 1) / 2, -1, 1)))
for name in sys.argv[1:]:
    seq = "episode_%06d" % int(name[2:4])
    co = R_of(f"/fp/{name}/cari4d/{seq}/inference/coconet.pth")
    old = R_of(f"/fp/{name}/cari4d/{seq}/inference/refined.pth")
    new = R_of(f"/rot/{name}/cari4d/{seq}/inference/refined.pth")
    row = []
    for k, R in (("frozen", old), ("rotopt", new)):
        s = steps(R); row.append(f"{k}: >24 {int((s>24).sum())} >60 {int((s>60).sum())} >90 {int((s>90).sum())}")
    d = ang(co, new)
    line = f"{name[:4]} | " + " | ".join(row) + f" | rotopt vs coconet deg p50 {np.median(d):.1f} p99 {np.percentile(d,99):.1f} max {d.max():.1f}"
    if seq in CHECKED:
        fr, note = CHECKED[seq]
        line += f" | checked ({note}) rotopt-vs-coconet {[round(float(x),1) for x in d[fr]]}"
    print(line, flush=True)
