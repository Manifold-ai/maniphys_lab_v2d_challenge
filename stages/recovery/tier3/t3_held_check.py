"""H0 checks of the held-run jump repair: silhouette IoU before and after, and byte identity of untouched frames (Tier 3 inputs only).

Plan: agent-doc/plan-t3hand-2026-10-27.md on track2/p1-training, version 2, section 1 P1 and criterion H0 (a), (d).

For every episode the repair touched (runs/<out version>.held_fix.json): the silhouette IoU of the input and the output
version on every stride-th evidence frame (t3_frame_confidence.silhouette, as t3_fix_sil.py), the medians over the whole
episode and over the replaced frames, and whether every frame outside the stretches keeps the input bytes.

    python t3_held_check.py <tier3 root> <selection json> <in version> <out version> [stride=3]
One json line per episode on stdout; last line T3_HELD_CHECK_DONE <episodes failing (a) or (d)>. CPU only.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE / "gate"), str(HERE.parents[2] / "libs" / "v2d_infra")]

TOL = 0.01


def main() -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    import h5py
    import pyarrow.parquet as pq
    from tier_guard import forbid_lower_tiers
    forbid_lower_tiers()  # Tier 3: nothing from Tier 1 or Tier 2 (Kaggle 2.8.c)
    from t3_align_check import WORK, similarity, world_pose
    from t3_frame_confidence import silhouette
    from t3_object_check import load_mesh
    from t3_track_check import MIN_MASK_PX

    args = [a for a in sys.argv[1:] if "=" not in a]
    kv = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
    root, sel, v_in, v_out = Path(args[0]), Path(args[1]), args[2], args[3]
    stride = int(kv.get("stride", 3))
    rep = {r["episode"]: r for r in json.loads((root / "runs" / f"{v_out}.held_fix.json").read_text())}
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    bad = 0
    for r in json.loads(sel.read_text()):
        ep, name, conv = r["episode_index"], r["episode"], r["convert"]
        row = rep.get(name)
        if row is None or not row["stretches"]:
            continue
        m = metas[ep]
        s, rot_, t, k, _ = similarity(root / "runs" / conv / name)
        verts, faces = load_mesh(root / "input" / m["mesh"])
        T0, T1 = world_pose(root, v_in, ep), world_pose(root, v_out, ep)
        n = len(T0)
        replaced = np.zeros(n, bool)
        for a, b in row["stretches"]:
            replaced[a + 1:b] = True
        # (d) untouched frames keep the input bytes
        same = True
        for sub in ("", "_suspect"):
            f0 = root / "runs" / (v_in + sub) / "data/chunk-000" / f"episode_{ep:06d}.parquet"
            if f0.exists():
                f1 = root / "runs" / (v_out + sub) / "data/chunk-000" / f"episode_{ep:06d}.parquet"
                p0 = np.stack(pq.read_table(f0).column("observation.object.pose").to_numpy(zero_copy_only=False))
                p1 = np.stack(pq.read_table(f1).column("observation.object.pose").to_numpy(zero_copy_only=False))
                same = bool(np.array_equal(p0[~replaced], p1[~replaced]))
        H = h5py.File(root / "runs" / WORK[conv] / name / "masks_k0.h5", "r")[f"episode_{ep:06d}"]
        iou0, iou1 = np.full(n, np.nan), np.full(n, np.nan)
        frames = sorted(set(range(0, n, stride)) | set(np.flatnonzero(replaced).tolist()))
        for f in frames:
            ok, pk = f"{f:06d}-k0.obj_rend_mask.png", f"{f:06d}-k0.person_mask.png"
            if ok not in H:
                continue
            obj = H[ok][()] > 0
            person = H[pk][()] > 0 if pk in H else np.zeros_like(obj)
            if (obj & ~person).sum() < MIN_MASK_PX:
                continue
            iou0[f] = silhouette(verts, faces, T0[f], rot_, t, s, k, obj, person)[1]
            iou1[f] = silhouette(verts, faces, T1[f], rot_, t, s, k, obj, person)[1]
        ev = np.isfinite(iou0) & np.isfinite(iou1)
        all0, all1 = float(np.median(iou0[ev])) if ev.any() else np.nan, float(np.median(iou1[ev])) if ev.any() else np.nan
        rp = ev & replaced
        rep0, rep1 = (float(np.median(iou0[rp])), float(np.median(iou1[rp])), int(rp.sum())) if rp.any() else (np.nan, np.nan, 0)
        a_ok = (all1 >= all0 - TOL) and (rp.sum() == 0 or rep1 >= rep0 - TOL)
        bad += int(not (a_ok and same))
        out = {"episode": name, "replaced_frames": int(replaced.sum()), "evidence_frames": int(ev.sum()),
               "iou_all_p50_before_after": [round(all0, 4), round(all1, 4)],
               "iou_replaced_p50_before_after": [round(rep0, 4), round(rep1, 4), rep0 and None], "replaced_evidence": int(rp.sum()),
               "a_ok": bool(a_ok), "untouched_same": same}
        out["iou_replaced_p50_before_after"] = [round(rep0, 4), round(rep1, 4)]
        print(json.dumps(out), flush=True)
    print(f"T3_HELD_CHECK_DONE {bad}")


if __name__ == "__main__":
    main()
