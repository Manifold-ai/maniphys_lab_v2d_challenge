"""Silhouette orientation choice on a delivered Tier 3 version, t3fix part A, scoring step (Tier 3 inputs only).

Plan: agent-doc/plan-t3fix-2026-10-27.md on track2/p1-training, version 2, section 1 A1-A5 and criterion G0.

Per episode, on the delivered layer (the version's world pose mapped back to the exo camera by the world step's
similarity, as t3_frame_confidence.py), every stride-th frame with mask evidence gets the silhouette IoU of the current
pose, of each candidate turn and of each null turn (t3_fix_units.candidates / null_candidates, turned about the centre
of mass). The units come from the version's orientation and the held flags of the physics check of the version the
dynamics post-process read (closed over GAP frames as t3_dynamics_post.py does). Decisions are made for every
MIN_GAIN on the registered ladder, for the real candidates and for the null control, so the choice of MIN_GAIN (G0)
reads one file per episode. Nothing is written into the version; the apply step is separate.

    python t3_fix_sil.py <tier3 root> <selection json> <version> <physics dir> <out dir> [stride=3] [only=<ep>,..]
Writes <out>/epNN.npz (frame index, and one IoU array per pose name, nan without evidence) and <out>/epNN.json.
One json line per episode on stdout. CPU only.
"""

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_closing

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE / "gate"), str(HERE.parents[2] / "libs" / "v2d_infra")]

GAP = 5  # frames, as t3_dynamics_post.GAP


def main() -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    import h5py
    import trimesh
    from tier_guard import forbid_lower_tiers
    forbid_lower_tiers()  # Tier 3: nothing from Tier 1 or Tier 2 (Kaggle 2.8.c)
    from t3_align_check import WORK, similarity, world_pose
    from t3_fix_units import MIN_GAIN_LADDER, about_com, candidates, decide, null_candidates, principal, units
    from t3_frame_confidence import silhouette
    from t3_object_check import load_mesh
    from t3_sil_choose import choose_pose
    from t3_symmetry import SYM_M, Shape, symmetries

    args = [a for a in sys.argv[1:] if "=" not in a]
    kv = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
    root, sel, version, phys, out = Path(args[0]), Path(args[1]), args[2], Path(args[3]), Path(args[4])
    stride = int(kv.get("stride", 3))
    only = {int(x) for x in kv.get("only", "").split(",") if x}
    out.mkdir(parents=True, exist_ok=True)
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    for r in json.loads(sel.read_text()):
        ep, name, conv = r["episode_index"], r["episode"], r["convert"]
        if only and ep not in only:
            continue
        t0 = time.time()
        m = metas[ep]
        s, rot_, t, k, _ = similarity(root / "runs" / conv / name)
        verts, faces = load_mesh(root / "input" / m["mesh"])
        mesh = trimesh.load(root / "input" / m["mesh"], force="mesh")
        body = mesh if mesh.is_watertight else mesh.convex_hull
        com_b = np.asarray(body.center_mass, np.float64)
        shape = Shape(mesh, com_b)
        group, cont = symmetries(shape, body.moment_inertia)
        moments, axes = principal(body.moment_inertia)
        cand = candidates(moments, axes, shape.shift, SYM_M, group, cont)
        null = null_candidates(axes, group, cont)
        Tw = world_pose(root, version, ep)
        n = len(Tw)
        held = np.load(phys / "out" / f"{name}.npz")["held"].astype(bool)
        if len(held) != n:
            raise SystemExit(f"{name}: {len(held)} held flags for {n} frames")
        held = binary_closing(held, np.ones(2 * GAP + 1, bool)) | held
        unit_list = units(Tw[:, :3, :3], held)
        turns = {"current": np.eye(4), **{x: about_com(g, com_b) for x, g in {**cand, **null}.items()}}
        iou = {x: np.full(n, np.nan) for x in turns}
        H = h5py.File(root / "runs" / WORK[conv] / name / "masks_k0.h5", "r")[f"episode_{ep:06d}"]
        for f in range(0, n, stride):
            ok, pk = f"{f:06d}-k0.obj_rend_mask.png", f"{f:06d}-k0.person_mask.png"
            if ok not in H:
                continue
            obj = H[ok][()] > 0
            person = H[pk][()] > 0 if pk in H else np.zeros_like(obj)
            for x, G in turns.items():
                iou[x][f] = silhouette(verts, faces, Tw[f] @ G, rot_, t, s, k, obj, person)[1]
        real = {x: iou[x] for x in ("current", *cand)}
        nul = {x: iou[x] for x in ("current", *null)}
        dec = {f"{mg:.2f}": {"real": decide(real, unit_list, choose_pose, mg), "null": decide(nul, unit_list, choose_pose, mg)}
               for mg in MIN_GAIN_LADDER}
        np.savez_compressed(out / f"ep{ep:02d}.npz", **iou)
        row = {"episode": name, "frames": n, "stride": stride, "measured": int(np.isfinite(iou["current"]).sum()),
               "faces": int(len(faces)), "com_b_m": [round(float(x), 4) for x in com_b], "symmetries": len(group),
               "continuous_axis": cont is not None, "candidates": sorted(cand), "null": sorted(null),
               "units": len(unit_list), "held_share": round(float(held.mean()), 3),
               "iou_current_p50": round(float(np.nanmedian(iou["current"])), 4) if np.isfinite(iou["current"]).any() else None,
               "accepts": {mg: {kind: sum(rw["decision"] == "accept" for rw in d[kind]) for kind in ("real", "null")} for mg, d in dec.items()},
               "seconds": round(time.time() - t0, 1)}
        (out / f"ep{ep:02d}.json").write_text(json.dumps({**row, "decisions": dec}, indent=1))
        print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
