"""Image alignment of versions' object poses: each version's world pose drawn back in the exo image against the SAM2 mask.

A post-process that moves the object in the world can keep it on its image position (a scale about the camera centre,
t3_depth_post.py) or move it off (a vertical shift, t3_height_post.py). This checks which, on the same frames for every
version: the world step's similarity (fitted from the episode's object_cam_focal / object_world pair in its convert dir,
residual reported) maps a version's world pose back to the camera; the official mesh is projected with that convert
dir's intrinsics; silhouette IoU against the object mask with both dilated by DILATE_PX (as t3_track_check.py), and the
silhouette centroid offset in pixels. Frames: every STRIDE-th frame where the mask has at least MIN_MASK_PX pixels.

    python t3_align_check.py <tier3 root> <selection json> <out json> <version>... [ep=convert dir ...] [only=<ep>,<ep>]
        [stride=<n>] [split=<dump dir>] [human=<SOMA assets dir>] [perframe=1]
perframe: also each version's per-frame IoU (frame, iou) and the frames under LOW_IOU, so a few flipped frames are not
averaged away (10-15: ep04's bat turned end over end on single frames while its mean IoU looked ordinary).
human: also the body. Each version's SOMA body (t3_world_probe.soma_cv, the downstream's way: frame-0 identity and scale,
OpenCV world frame) goes through the same similarity and intrinsics, and its silhouette is compared with the SAM2 person
mask the same way. Pixels inside the object mask are left out of both: the object hides the body there and the person
mask stops at it. Reported under "human" per version. CPU only (CUDA_VISIBLE_DEVICES is cleared).
split: with t3_depth_post.py's dump of where each frame's correction came from, the IoU of the first and the last
version is also reported per class of frame (held or not, x anchored / interpolated / floor clamp / support clamp).
Masks from the convert dir's work dir (convert -> work, convert_v2 -> work_v2, convert_fp -> work_fp; the pivot
version of ep19 kept fp's masks).
"""

import json
import sys
from pathlib import Path

import cv2
import h5py
import numpy as np
import pyarrow.parquet as pq
import trimesh
from scipy.spatial.transform import Rotation

STRIDE = 5
DILATE_PX = 5
MIN_MASK_PX = 200
MAX_FACES = 20000
LOW_IOU = 0.5
WORK = {"convert": "work", "convert_v2": "work_v2", "convert_fp": "work_fp", "convert_pivot": "work_fp"}


def similarity(conv: Path):
    c = np.load(conv / "object_cam_focal.npz")
    pc, pw = c["T_cam_glb"][:, :3, 3], np.load(conv / "object_world.npz")["T_world_glb"][:, :3, 3]
    mc, mw = pc.mean(0), pw.mean(0)
    u, sv, vt = np.linalg.svd((pw - mw).T @ (pc - mc))
    dd = np.diag([1, 1, np.sign(np.linalg.det(u @ vt))])
    r = u @ dd @ vt
    s = np.trace(np.diag(sv) @ dd) / ((pc - mc) ** 2).sum()
    t = mw - s * r @ mc
    return s, r, t, c["intrinsics"], float(np.abs((pc @ r.T) * s + t - pw).max())


def version_file(root: Path, version: str, ep: int) -> Path:
    for sub in ("", "_suspect"):
        f = root / "runs" / (version + sub) / "data/chunk-000" / f"episode_{ep:06d}.parquet"
        if f.exists():
            return f
    raise SystemExit(f"{version}: no episode {ep}")


HUMAN_COLUMNS = {"poses": "observation.human.pose", "transl": "observation.human.translation",
                 "identity_coeffs": "observation.human.identity_coeffs", "scale_params": "observation.human.scale_params",
                 "bone_length_flexibles": "observation.human.bone_length_flexibles"}  # as t3_physics_check.HUMAN_COLUMNS


def human_verts(root: Path, version: str, ep: int, frames: list[int], layer) -> np.ndarray:
    """(len(frames), V, 3) body vertices in the world (OpenCV) frame."""
    from t3_world_probe import soma_cv
    t = pq.read_table(version_file(root, version, ep), columns=list(HUMAN_COLUMNS.values()))
    sp = {k: np.stack(t.column(c).to_numpy(zero_copy_only=False)).astype(np.float64) for k, c in HUMAN_COLUMNS.items()}
    first = {k: sp[k][:1] for k in ("identity_coeffs", "scale_params")}  # soma_cv takes frame 0's; keep it frame 0
    sp = {k: v[frames] for k, v in sp.items()}
    sp.update({k: np.repeat(v, len(frames), 0) for k, v in first.items()})
    return soma_cv(sp, layer)[1]


def silhouette(V, F, rot, t, s, K, shape):
    X = (V - t) @ rot / s  # rot.T @ (V - t) / s, row-wise
    if (X[:, 2] <= 0.05).any():
        return None
    uv = X @ K.T
    uv = (uv[:, :2] / uv[:, 2:]).astype(np.int32)
    sil = np.zeros(shape, np.uint8)
    cv2.fillPoly(sil, list(uv[F]), 1)
    return sil


def world_pose(root: Path, version: str, ep: int) -> np.ndarray:
    for sub in ("", "_suspect"):
        f = root / "runs" / (version + sub) / "data/chunk-000" / f"episode_{ep:06d}.parquet"
        if f.exists():
            p = np.stack(pq.read_table(f).column("observation.object.pose").to_numpy(zero_copy_only=False)).astype(float)
            T = np.tile(np.eye(4), (len(p), 1, 1))
            T[:, :3, :3] = Rotation.from_quat(np.c_[p[:, 4:7], p[:, 3:4]]).as_matrix()
            T[:, :3, 3] = p[:, :3]
            return T
    raise SystemExit(f"{version}: no episode {ep}")


def main() -> None:
    args = [a for a in sys.argv[1:] if "=" not in a]
    kv = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
    only = {int(x) for x in kv.pop("only", "").split(",") if x}
    stride = int(kv.pop("stride", STRIDE))
    split = Path(kv.pop("split")) if "split" in kv else None
    perframe = kv.pop("perframe", "0") == "1"
    layer = None
    if "human" in kv:
        import os
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
        from soma import SOMALayer
        from soma.units import Unit
        layer = SOMALayer(data_root=kv.pop("human"), identity_model_type="mhr", device="cpu", output_unit=Unit.METERS,
                          enable_procedural_transforms=False)
        HF = np.asarray(layer.faces)
    root, sel, out, versions = Path(args[0]), Path(args[1]), Path(args[2]), args[3:]
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    kern = np.ones((2 * DILATE_PX + 1, 2 * DILATE_PX + 1), np.uint8)
    rows = []
    for r in json.loads(sel.read_text()):
        ep, name = r["episode_index"], r["episode"]
        if only and ep not in only:
            continue
        conv = kv.get(name, r["convert"])
        s, rot, t, K, res = similarity(root / "runs" / conv / name)
        mesh = trimesh.load(root / "input" / metas[ep]["mesh"], force="mesh")
        if len(mesh.faces) > MAX_FACES:  # silhouette only; needs fast_simplification
            mesh = mesh.simplify_quadric_decimation(face_count=MAX_FACES)
        V, F = np.asarray(mesh.vertices), np.asarray(mesh.faces)
        H = h5py.File(root / "runs" / WORK[conv] / name / "masks_k0.h5", "r")[f"episode_{ep:06d}"]
        poses = {v: world_pose(root, v, ep) for v in versions}
        n = min(len(p) for p in poses.values())
        res_v = {v: {"iou": [], "off": [], "frame": []} for v in versions}
        if layer is not None:
            hres = {v: [] for v in versions}
            frames = list(range(0, n, stride))
            hv = {v: human_verts(root, v, ep, frames, layer) for v in versions}
            for i, f in enumerate(frames):
                pm = (H[f"{f:06d}-k0.person_mask.png"][()] > 0).astype(np.uint8)
                if pm.sum() < MIN_MASK_PX:
                    continue
                keep = (H[f"{f:06d}-k0.obj_rend_mask.png"][()] == 0)
                md = (cv2.dilate(pm, kern) > 0) & keep
                for v in versions:
                    sil = silhouette(hv[v][i], HF, rot, t, s, K, pm.shape)
                    if sil is None:
                        continue
                    sd = (cv2.dilate(sil, kern) > 0) & keep
                    hres[v].append(float((sd & md).sum() / max(1, (sd | md).sum())))
        for f in range(0, n, stride):
            om = (H[f"{f:06d}-k0.obj_rend_mask.png"][()] > 0).astype(np.uint8)
            if om.sum() < MIN_MASK_PX:
                continue
            md = cv2.dilate(om, kern) > 0
            mc = np.argwhere(om)[:, ::-1].mean(0)
            for v in versions:
                Tw = poses[v][f]
                R_c = rot.T @ Tw[:3, :3]
                p_c = rot.T @ (Tw[:3, 3] - t) / s
                X = V @ R_c.T + p_c
                if (X[:, 2] <= 0.05).any():
                    continue
                uv = X @ K.T
                uv = (uv[:, :2] / uv[:, 2:]).astype(np.int32)
                sil = np.zeros(om.shape, np.uint8)
                cv2.fillPoly(sil, list(uv[F]), 1)
                res_v[v]["frame"].append(f)
                if not sil.any():
                    res_v[v]["iou"].append(0.0)
                    res_v[v]["off"].append(np.nan)
                    continue
                sd = cv2.dilate(sil, kern) > 0
                res_v[v]["iou"].append(float((sd & md).sum() / (sd | md).sum()))
                res_v[v]["off"].append(float(np.linalg.norm(np.argwhere(sil)[:, ::-1].mean(0) - mc)))
        row = {"episode": name, "convert": conv, "similarity_fit_m": round(res, 5)}
        for v in versions:
            iou, off = np.array(res_v[v]["iou"]), np.array(res_v[v]["off"])
            row[v] = {"frames": len(iou), "iou_p50": round(float(np.median(iou)), 4) if len(iou) else None,
                      "iou_mean": round(float(iou.mean()), 4) if len(iou) else None,
                      "centroid_px_p50": round(float(np.nanmedian(off)), 2) if len(off) else None}
            fr = np.array(res_v[v]["frame"])
            row[v]["low_iou_frames"] = int((iou < LOW_IOU).sum()) if len(iou) else 0
            if perframe:
                row[v]["per_frame"] = {"frame": fr.tolist(), "iou": [round(float(x), 3) for x in iou]}
            if layer is not None:
                h = np.array(hres[v])
                row[v]["human"] = {"frames": len(h), "iou_p50": round(float(np.median(h)), 4) if len(h) else None,
                                   "iou_mean": round(float(h.mean()), 4) if len(h) else None}
        if split is not None and (split / f"{name}.npz").exists():
            z = np.load(split / f"{name}.npz")
            a, b = versions[0], versions[-1]
            ia = dict(zip(res_v[a]["frame"], res_v[a]["iou"], strict=True))
            ib = dict(zip(res_v[b]["frame"], res_v[b]["iou"], strict=True))
            common = sorted(set(ia) & set(ib))
            src = np.where(z["support_clamped"], "support_clamp", np.where(z["floor_clamped"], "floor_clamp",
                                                                           np.where(z["anchored"], "anchored", "interpolated")))
            move = np.linalg.norm(z["delta"], axis=1)
            classes = {}
            for f in common:
                key = ("held_" if z["held"][f] else "free_") + str(src[f])
                classes.setdefault(key, []).append((ia[f], ib[f], move[f]))
            row["split"] = {k: {"frames": len(v), f"iou_{a}": round(float(np.mean([x[0] for x in v])), 4),
                                f"iou_{b}": round(float(np.mean([x[1] for x in v])), 4),
                                "iou_drop_sum": round(float(sum(x[0] - x[1] for x in v)), 3),
                                "move_cm_mean": round(float(np.mean([x[2] for x in v])) * 100, 2)} for k, v in sorted(classes.items())}
        rows.append(row)
        print(json.dumps(row), flush=True)
    out.write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
