"""Penetration against collision hulls: what PhysX would actually resolve.

Each mesh (the official one and every placed candidate, all in the official mesh's local frame) is split into convex
hulls with CoACD, the decomposition the official mesh_to_usd also uses for dynamic objects. A human vertex is inside
if it is inside any hull. Per contact frame the candidate's count is compared with the official mesh's count; the
difference is the penetration the swap adds. Hull containment is well defined for open meshes, which voxel filling
was not (pilot v2: every official mesh is open).

    python hull_check.py <pilot out dir of one episode>
"""

import json
import sys
from pathlib import Path

import coacd
import numpy as np
import trimesh
from scipy.spatial import ConvexHull

PEN_VERTS = 50
PEN_SHARE = 0.1
THRESHOLD = 0.05


def hulls(path: Path) -> list[np.ndarray]:
    mesh = trimesh.load(path, force="mesh", process=False)
    parts = coacd.run_coacd(coacd.Mesh(np.asarray(mesh.vertices), np.asarray(mesh.faces)), threshold=THRESHOLD)
    return [ConvexHull(np.asarray(v)).equations for v, _ in parts if len(v) >= 4]


def inside(eqs: list[np.ndarray], pts: np.ndarray) -> np.ndarray:
    hit = np.zeros(len(pts), bool)
    for e in eqs:
        hit |= np.all(pts @ e[:, :3].T + e[:, 3] <= 1e-4, axis=1)
    return hit


def main() -> None:
    out = Path(sys.argv[1])
    z = np.load(out / "contact_human_local.npz")
    pts, frame = z["points"], z["frame"]
    frames = np.unique(frame)
    def per_frame(eqs):
        hit = inside(eqs, pts)
        return np.array([int(hit[frame == f].sum()) for f in frames])
    base = per_frame(hulls(out / "official_local.glb"))
    report = json.loads((out / "swap_report.json").read_text())
    for row in report["candidates"]:
        glb = next(out.glob(f"*_{row['uid']}_{row['variant']}.glb"))
        extra = per_frame(hulls(glb)) - base
        row["hull_penetrating_share"] = round(float((extra > PEN_VERTS).mean()), 3) if len(extra) else None
        row["hull_extra_inside_p50"] = int(np.median(extra)) if len(extra) else None
        row["pass_hull"] = row["kept_contact_share"] >= 0.9 and (row["hull_penetrating_share"] or 0) <= PEN_SHARE
    report["hull_baseline_inside_p50"] = int(np.median(base)) if len(base) else None
    report["candidates"].sort(key=lambda r: (not r["pass_hull"], r["hull_penetrating_share"] or 0, -r["kept_contact_share"]))
    (out / "swap_report.json").write_text(json.dumps(report, indent=1))
    print("hull baseline inside p50:", report["hull_baseline_inside_p50"])
    for r in report["candidates"]:
        print(f"{'PASS' if r['pass_hull'] else 'fail'} {r['variant']:6s} keep={r['kept_contact_share']} hull_pen={r['hull_penetrating_share']} "
              f"extra={r['hull_extra_inside_p50']} chamfer={r['chamfer_to_official_cm']}cm {r['name']!r}")


if __name__ == "__main__":
    main()
