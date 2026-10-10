"""Tier 3: one CARI4D episode -> one Track 2 episode in the Tier 2 schema.

Three steps, each where its dependencies live:

  decode    v2d_cari4d image, CPU. Human: CARI4D's MHR parameters with the identity (shape, scale) fixed to its
            per-episode median, decoded to vertices in the OpenCV camera frame (metres) plus the 204-d MHR model
            parameters export_soma reads. CARI4D lets shape/scale drift per frame, while retargeting reads only
            frame 0's identity (read_soma.py), so a constant identity is what the downstream actually uses.
            Object: T_cam<-glb = pose_abs @ S2A (S2A from wild_export.json): pose of the official mesh's own
            local frame, which is the frame the scorer compares.
  soma      v2d_cari4d image, GPU, minutes. export_soma Path A (vertices -> SOMA-X by PoseInversion) with the
            parameters of the official multi-view workflow and an offline SOMA asset directory. Its own fit error
            (mean/median/max vertex error) goes to the log.
  residual  v2d_cari4d image, CPU. Independent of the optimiser: rebuilds the SOMA mesh from the saved
            soma_params.npz the way the downstream reads it (frame-0 identity, per-frame bone flexibles, no
            correctives) and measures it against the MHR target mesh. The two meshes have different topologies
            (SOMA 18056 vs MHR 18439 vertices), so the distance is a symmetric nearest-vertex (chamfer) distance.
  world     v2d_cari4d image, CPU. The floor correction from t3_floor_fit.py (per exo camera; rotation about the camera
            origin that puts our floor normal on the released one, then a scale of positions by released / our
            floor offset), applied to the object (position rotated and scaled, orientation rotated, mesh untouched)
            and the human (root orientation rotated, pelvis position rotated and scaled, body untouched). Writes
            object_world.npz, soma_params_world.npz and world_calib.json.
  assemble  host venv (pyarrow). One parquet with the Tier 2 columns and one episodes_metadata row, from the world step's
            files only.

World frame: the exo camera's OpenCV frame with the floor correction. Without it, floor-resting objects sit 0.11-0.22 m
above the released ground plane, more the farther they are (rxzhou's Tier 3 pilot, 10/9: 114.9 / 146.2 mm after
retargeting). Yaw and horizontal position are not observable from a floor and are left as reconstructed. Only Tier 3
inputs enter (no Tier 2 trajectory; user decision 10/10).

    python t3_convert_ep.py decode   <cari4d episode dir> <weights/cari4d dir> <out dir>
    python t3_convert_ep.py soma     <out dir> <soma assets dir>
    python t3_convert_ep.py residual <out dir> <soma assets dir>
    python t3_convert_ep.py world    <out dir> <floor_fit.json> <soma assets dir>
    python t3_convert_ep.py assemble <out dir> <tier3 input dir> <episode index> <tier dir to write>
"""

import json
import sys
from pathlib import Path

import numpy as np

CHUNK = 64
SOMA_ARGS = {  # reconstruction/workflows/mv_hoi/osmo/mv_hoi_reconstruction.yaml:453-469
    "body_iters": 2, "finger_iters": 0, "full_iters": 1, "lie_iters": 0, "autograd_iters": 400, "autograd_lr": 0.0025,
    "autograd_translation_lr_scale": 5.0, "autograd_pose_prior": 1.0, "autograd_pose_prior_weights": "heel_contact",
    "autograd_hand_weight": 5.0, "autograd_foot_weight": 20.0,
}
FPS = 30
F_CV_TO_SOMA = np.diag([1.0, -1.0, -1.0])
WORLD_BODY_TOL_M = 1e-3


def decode(ep_dir: Path, weights: Path, out: Path) -> None:
    import torch
    from lib_mhr import MHR_PARAM_DIMS, MHRLayer

    out.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(8)
    bundle = torch.load(ep_dir / "inference" / "refined.pth", map_location="cpu", weights_only=False)
    pr = bundle["pr"]
    n = len(bundle["frames"])

    # object: official-mesh local frame in the camera frame
    (export_dir,) = [d for d in (ep_dir / "export").iterdir() if d.is_dir()]
    export = json.loads((export_dir / "wild_export.json").read_text())
    s2a = np.asarray(export["source_object_mesh_to_aligned_transform"], np.float64)
    poses = np.asarray(pr["pose_abs"], np.float64) @ s2a
    rot = poses[:, :3, :3]
    orth = float(np.abs(rot @ rot.transpose(0, 2, 1) - np.eye(3)).max())
    if orth > 1e-4 or not np.isfinite(poses).all():
        raise SystemExit(f"object poses are not finite rigid transforms (orthogonality error {orth:.2e})")
    np.savez(out / "object_cam.npz", T_cam_glb=poses, intrinsics=np.asarray(export["intrinsics"], np.float64))

    # human: constant identity, decoded in chunks
    raw = {k: np.asarray(pr[k], np.float32) for k in MHR_PARAM_DIMS}
    fixed = {k: np.median(raw[k], axis=0, keepdims=True) for k in ("mhr_shape", "mhr_scale")}
    layer = MHRLayer.from_mhr_assets(mhr_assets_root=str(weights / "sam3d_body"), device="cpu")
    be = layer.backend
    verts, model_params, shift = [], [], []
    with torch.no_grad():
        for s in range(0, n, CHUNK):
            sl = slice(s, min(n, s + CHUNK))
            m = sl.stop - sl.start
            params = {k: torch.as_tensor(np.repeat(fixed[k], m, 0) if k in fixed else raw[k][sl]) for k in MHR_PARAM_DIMS}
            ctx = be._vertices_context(params, detach_fixed=False)
            trans, body, shape, scale = be._mutable_vertices_inputs(params, ctx)
            res = ctx.head.mhr_forward(global_trans=torch.zeros_like(trans), global_rot=ctx.global_rot, body_pose_params=body,
                                       hand_pose_params=ctx.hand, scale_params=scale, shape_params=shape, expr_params=ctx.face,
                                       return_model_params=True)
            v = res[0] * ctx.flip + trans[:, None, :]
            original = layer.mhr_forward({k: torch.as_tensor(raw[k][sl]) for k in MHR_PARAM_DIMS}).vertices
            shift.append((v - original).norm(dim=-1).numpy())
            verts.append(v.float())
            model_params.append(res[-1].float())
    verts_t = torch.cat(verts)
    torch.save({"pred_vertices": verts_t, "faces": torch.as_tensor(np.asarray(bundle["faces"], np.int64))}, out / "mhr_mesh.pt")
    torch.save({"shape_params": torch.as_tensor(np.repeat(fixed["mhr_shape"], n, 0)), "mhr_model_params": torch.cat(model_params)},
               out / "mhr_params.pt")
    shift_cm = np.concatenate(shift) * 100.0
    report = {"frames": n, "object_orthogonality_error": orth,
              "identity_shift_cm": {"mean": round(float(shift_cm.mean()), 3), "p99": round(float(np.percentile(shift_cm, 99)), 3),
                                    "max": round(float(shift_cm.max()), 3)},
              "shape_std_max": round(float(raw["mhr_shape"].std(0).max()), 4), "scale_std_max": round(float(raw["mhr_scale"].std(0).max()), 4)}
    (out / "decode_report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report))


def soma(out: Path, assets: Path) -> None:
    import logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    sys.path.insert(0, "/workspace/v2d_sam3d_body/lib")
    import export_soma as es
    from soma import SOMALayer
    from soma.units import Unit

    def offline_layer(device: str) -> SOMALayer:  # same settings as es.create_soma_layer, assets from disk
        return SOMALayer(data_root=str(assets), identity_model_type="mhr", device=device, mode="warp",
                         output_unit=Unit.CENTIMETERS, enable_procedural_transforms=False)

    es.create_soma_layer = offline_layer
    es.export_soma(params_path=out / "mhr_params.pt", output_path=out / "soma_params.npz", mesh_path=out / "mhr_mesh.pt",
                   weights_dir=None, device="cuda", output_unit="meters", **SOMA_ARGS)


def residual(out: Path, assets: Path) -> None:
    import torch
    from scipy.spatial import cKDTree
    from soma import SOMALayer
    from soma.units import Unit

    sp = np.load(out / "soma_params.npz", allow_pickle=True)
    target = torch.load(out / "mhr_mesh.pt", map_location="cpu", weights_only=True)["pred_vertices"].numpy()
    target = target @ F_CV_TO_SOMA  # OpenCV camera frame -> SOMA frame, metres
    n = len(sp["poses"])
    layer = SOMALayer(data_root=str(assets), identity_model_type="mhr", device="cpu", output_unit=Unit.METERS,
                      enable_procedural_transforms=False)
    ident = torch.tensor(np.repeat(sp["identity_coeffs"].reshape(-1, 45)[:1], n, 0), dtype=torch.float32)
    scale = torch.tensor(np.repeat(sp["scale_params"].reshape(-1, 68)[:1], n, 0), dtype=torch.float32)
    per_frame = np.empty(n)
    per_frame_p95 = np.empty(n)
    for s in range(0, n, CHUNK):
        sl = slice(s, min(n, s + CHUNK))
        with torch.no_grad():
            got = layer(torch.tensor(sp["poses"][sl], dtype=torch.float32), ident[sl], scale_params=scale[sl],
                        transl=torch.tensor(sp["transl"][sl], dtype=torch.float32), apply_correctives=False,
                        kwargs={"bone_length_flexibles": torch.tensor(sp["bone_length_flexibles"][sl], dtype=torch.float32)}).vertices.numpy()
        for i, (a, b) in enumerate(zip(got, target[sl], strict=True)):
            d_ab = cKDTree(b).query(a)[0]
            d_ba = cKDTree(a).query(b)[0]
            d = np.concatenate([d_ab, d_ba]) * 100.0
            per_frame[s + i] = d.mean()
            per_frame_p95[s + i] = np.percentile(d, 95)
    worst = np.argsort(per_frame)[-5:][::-1]
    report = {"frames": n, "chamfer_cm": {"mean": round(float(per_frame.mean()), 3), "p50": round(float(np.median(per_frame)), 3),
                                          "p95_frame": round(float(np.percentile(per_frame, 95)), 3), "max_frame": round(float(per_frame.max()), 3)},
              "within_frame_p95_cm_median": round(float(np.median(per_frame_p95)), 3),
              "worst_frames": [{"frame": int(i), "chamfer_cm": round(float(per_frame[i]), 3)} for i in worst]}
    (out / "residual_report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report))


def world(out: Path, floor_fit: Path, assets: Path) -> None:
    import hashlib

    import torch
    from scipy.spatial.transform import Rotation
    from soma import SOMALayer
    from soma.units import Unit

    name = out.name
    fit_bytes = floor_fit.read_bytes()
    entry = json.loads(fit_bytes)["episodes"].get(name)
    if entry is None:
        raise SystemExit(f"{floor_fit}: no floor correction for {name}")
    rot, s = np.asarray(entry["rotation"], np.float64), float(entry["scale"])
    if abs(np.linalg.det(rot) - 1) > 1e-6 or np.abs(rot @ rot.T - np.eye(3)).max() > 1e-6 or not 0.8 < s < 1.25:
        raise SystemExit(f"floor correction for {name} is not a rotation with a plausible scale (scale {s})")

    oc = dict(np.load(out / "object_cam.npz"))
    t_cam = oc["T_cam_glb"].astype(np.float64)
    t_w = t_cam.copy()
    t_w[:, :3, :3] = np.einsum("ij,njk->nik", rot, t_cam[:, :3, :3])
    t_w[:, :3, 3] = s * t_cam[:, :3, 3] @ rot.T
    np.savez(out / "object_world.npz", T_world_glb=t_w, intrinsics=oc["intrinsics"])

    # human, in the SOMA frame (OpenCV @ F): rotate the root, move the pelvis to s * R * pelvis, keep the body
    sp = dict(np.load(out / "soma_params.npz", allow_pickle=True))
    rot_s = F_CV_TO_SOMA @ rot @ F_CV_TO_SOMA
    n = len(sp["poses"])
    layer = SOMALayer(data_root=str(assets), identity_model_type="mhr", device="cpu", output_unit=Unit.METERS,
                      enable_procedural_transforms=False)

    def joints(params: dict) -> np.ndarray:
        ident = torch.tensor(np.repeat(np.asarray(params["identity_coeffs"]).reshape(n, -1)[:1], n, 0), dtype=torch.float32)
        scale = torch.tensor(np.repeat(np.asarray(params["scale_params"]).reshape(n, -1)[:1], n, 0), dtype=torch.float32)
        got = []
        for a in range(0, n, CHUNK):
            sl = slice(a, min(n, a + CHUNK))
            with torch.no_grad():
                got.append(layer(torch.tensor(np.asarray(params["poses"][sl]).reshape(-1, 77, 3), dtype=torch.float32), ident[sl],
                                 scale_params=scale[sl], transl=torch.tensor(np.asarray(params["transl"][sl]), dtype=torch.float32),
                                 apply_correctives=False,
                                 kwargs={"bone_length_flexibles": torch.tensor(np.asarray(params["bone_length_flexibles"][sl]), dtype=torch.float32)})["joints"].numpy())
        return np.concatenate(got).astype(np.float64)

    j0 = joints(sp)
    pelvis = j0[:, 0]
    poses = np.asarray(sp["poses"]).copy()
    shape = poses.shape
    pv = poses.reshape(n, 77, 3)
    pv[:, 0] = (Rotation.from_matrix(rot_s) * Rotation.from_rotvec(pv[:, 0].astype(np.float64))).as_rotvec()
    rotated = {**sp, "poses": pv.reshape(shape).astype(poses.dtype)}
    j1 = joints(rotated)
    target_pelvis = s * pelvis @ rot_s.T
    transl = np.asarray(sp["transl"]).astype(np.float64) + (target_pelvis - j1[:, 0])
    new = {**rotated, "transl": transl.astype(np.asarray(sp["transl"]).dtype)}
    j2 = joints(new)
    want = np.einsum("ij,nkj->nki", rot_s, j0 - pelvis[:, None]) + target_pelvis[:, None]
    err = float(np.abs(j2 - want).max())
    if err > WORLD_BODY_TOL_M:
        raise SystemExit(f"{name}: corrected body is off the rigid target by {err * 1000:.2f} mm")
    for key in sp:
        if key not in ("poses", "transl") and not np.array_equal(np.asarray(sp[key]), np.asarray(new[key])):
            raise SystemExit(f"{name}: {key} changed in the world step")
    if not np.array_equal(np.asarray(sp["poses"]).reshape(n, 77, 3)[:, 1:], np.asarray(new["poses"]).reshape(n, 77, 3)[:, 1:]):
        raise SystemExit(f"{name}: a non-root joint changed in the world step")
    np.savez(out / "soma_params_world.npz", **new)
    calib = {"episode": name, "floor_fit": str(floor_fit), "floor_fit_sha256": hashlib.sha256(fit_bytes).hexdigest(),
             "camera_group": entry["group"], "how": entry["how"], "own_floor_events": entry["own_events"],
             "rotation": rot.tolist(), "scale": s, "tilt_deg": entry["tilt_deg"], "body_rigid_max_err_mm": round(err * 1000, 4)}
    (out / "world_calib.json").write_text(json.dumps(calib, indent=1))
    print(json.dumps(calib))


def _quat_wxyz(rot: np.ndarray) -> np.ndarray:
    from scipy.spatial.transform import Rotation

    xyzw = Rotation.from_matrix(rot).as_quat()
    return np.concatenate([xyzw[:, 3:], xyzw[:, :3]], axis=1)


def assemble(out: Path, inp: Path, ep: int, tier_dir: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    info = json.loads((inp / "meta" / "info.json").read_text())
    meta = next(m for m in map(json.loads, (inp / "meta" / "episodes_metadata.jsonl").read_text().splitlines()) if m["episode_index"] == ep)
    lengths = {json.loads(line)["episode_index"]: json.loads(line)["length"] for line in (inp / "meta" / "episodes.jsonl").read_text().splitlines()}
    tasks = {json.loads(line)["task"]: json.loads(line)["task_index"] for line in (inp / "meta" / "tasks.jsonl").read_text().splitlines()}
    n = int(meta["frames"])

    for f in ("soma_params_world.npz", "object_world.npz", "world_calib.json"):
        if not (out / f).exists():
            raise SystemExit(f"{out / f} missing: run the world step first (the camera frame is not the released world)")
    calib = json.loads((out / "world_calib.json").read_text())
    sp = np.load(out / "soma_params_world.npz", allow_pickle=True)
    joint_names = [str(j) for j in sp["joint_names"]]
    want = info["features"]["observation.human.pose"]["names"]  # "Hips.rx", "Hips.ry", ...
    want_joints = list(dict.fromkeys(name.rsplit(".", 1)[0] for name in want))
    if joint_names != want_joints:
        raise SystemExit(f"SOMA joint order differs from info.json: {joint_names[:3]}... ({len(joint_names)}) vs {want_joints[:3]}... ({len(want_joints)})")
    poses = np.asarray(sp["poses"], np.float32).reshape(n, -1)
    transl = np.asarray(sp["transl"], np.float32)
    ident = np.asarray(sp["identity_coeffs"], np.float32)
    scale = np.asarray(sp["scale_params"], np.float32)
    flex = np.asarray(sp["bone_length_flexibles"], np.float32)
    # retargeting reads frame 0 only (read_soma.py); Tier 2 stores the identity as a per-frame constant
    ident = np.repeat(ident.reshape(-1, 45)[:1], n, 0)
    scale = np.repeat(scale.reshape(-1, 68)[:1], n, 0)
    obj = np.load(out / "object_world.npz")["T_world_glb"]
    obj_pose = np.concatenate([obj[:, :3, 3], _quat_wxyz(obj[:, :3, :3])], axis=1).astype(np.float32)
    for name, arr, width in (("pose", poses, 231), ("translation", transl, 3), ("identity", ident, 45), ("scale", scale, 68),
                             ("flex", flex, 6), ("object", obj_pose, 7)):
        if arr.shape != (n, width) or not np.isfinite(arr).all():
            raise SystemExit(f"{name}: shape {arr.shape} (want {(n, width)}) or non-finite values")

    offset = sum(lengths[e] for e in lengths if e < ep)
    frame = np.arange(n, dtype=np.int64)
    fixed = lambda dtype, width: pa.list_(dtype, width)
    table = pa.table({
        "observation.human.pose": pa.array(list(poses), type=fixed(pa.float32(), 231)),
        "observation.human.translation": pa.array(list(transl), type=fixed(pa.float32(), 3)),
        "observation.human.identity_coeffs": pa.array(list(np.ascontiguousarray(ident)), type=fixed(pa.float32(), 45)),
        "observation.human.scale_params": pa.array(list(np.ascontiguousarray(scale)), type=fixed(pa.float32(), 68)),
        "observation.human.bone_length_flexibles": pa.array(list(flex), type=fixed(pa.float32(), 6)),
        "observation.object.pose": pa.array(list(obj_pose), type=fixed(pa.float32(), 7)),
        "observation.object.visible": pa.array(np.ones(n, bool)),
        "timestamp": pa.array((frame / FPS).astype(np.float32)),
        "frame_index": pa.array(frame),
        "episode_index": pa.array(np.full(n, ep, np.int64)),
        "index": pa.array(frame + offset),
        "task_index": pa.array(np.full(n, tasks[meta["task"]], np.int64)),
        "next.done": pa.array(frame == n - 1),
    })
    table = table.replace_schema_metadata({
        "objects": json.dumps([meta["object"]]), "pose_convention": "world_T_object",
        "trajectory_variant": "tier3_cari4d_official_mesh_floor_calib",
        "source": json.dumps({"reconstruction": "CARI4D", "object_mesh": meta["mesh"],
                              "world_frame": "exo camera OpenCV frame, rotated and scaled about the camera origin so the "
                                             "reconstructed floor lies on the released ground plane; yaw and horizontal "
                                             "position as reconstructed",
                              "floor_correction": {k: calib[k] for k in ("camera_group", "how", "tilt_deg", "scale", "floor_fit_sha256")}}),
    })
    dst = tier_dir / "data" / "chunk-000" / f"episode_{ep:06d}.parquet"
    dst.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, dst)
    (tier_dir / "meta").mkdir(exist_ok=True)
    (tier_dir / "meta" / f"episode_{ep:06d}.metadata.json").write_text(json.dumps(meta))
    print(json.dumps({"written": str(dst), "frames": n, "index_offset": offset}))


if __name__ == "__main__":
    cmd, args = sys.argv[1], [Path(a) for a in sys.argv[2:]]
    if any("tier_1" in str(a) for a in args):
        raise SystemExit("refusing a Tier 1 path")
    if cmd == "decode":
        decode(*args)
    elif cmd == "soma":
        soma(*args)
    elif cmd == "residual":
        residual(*args)
    elif cmd == "world":
        world(*args)
    elif cmd == "assemble":
        assemble(args[0], args[1], int(sys.argv[4]), args[3])
    else:
        raise SystemExit(f"unknown step {cmd}")
