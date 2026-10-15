"""Can FoundationPose's scorer tell an object's flips apart on our frames? (Plan A pilot, 10-15; runs in v2d_cari4d.)

The reconstruction flips orientations in runs of frames (a mug's handle jumps sides, a vacuum stands up), and a
trajectory-only smoother cannot tell which side is right. FoundationPose's ScorePredictor renders each candidate pose
and compares it with the frame (attention across the candidates of one frame). This probe takes a frame's selected pose
(fp_poses_cam of the episode's FoundationPose output), builds candidates by turning it about the mesh's principal axes
(through its centre) in STEP_DEG steps, optionally refines them as FoundationPose's register does, scores all of them
in one call, and reports the rank of the input pose and the turn of the top candidate; the scorer's own visualisation
is saved for checking against the video by eye.

Inside the container, the episode's CARI4D work dir mounted at /data/video_path:
    python t3_fp_score_probe.py <episode index> <frame,frame,...> <out dir> [refine_iter]
"""

import json
import pickle
import sys
from pathlib import Path

import cv2
import numpy as np
from scipy.spatial.transform import Rotation

sys.path.insert(0, "/workspace/v2d_cari4d/lib/cari4d/prep")
STEP_DEG = 60


def main() -> None:
    import torch
    import run_foundationpose_mhr_export as rf

    ep, frames, out = int(sys.argv[1]), [int(x) for x in sys.argv[2].split(",")], Path(sys.argv[3])
    refine_iter = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    rgb_only = len(sys.argv) > 5 and sys.argv[5] == "rgbonly"  # score with zero depth (the wrapper's rgb_only_score idea)
    out.mkdir(parents=True, exist_ok=True)
    root = Path("/data/video_path/cari4d") / f"episode_{ep:06d}"
    export_seq = root / "export" / f"episode_{ep:06d}"
    fp = pickle.load(open(root / "foundationpose" / f"episode_{ep:06d}.pkl", "rb"))
    depth_root = Path(fp["metadata"]["depth_root"])
    camera_id = int(fp["camera_id"])
    names = list(fp["frames"])
    edex = rf.load_edex(export_seq)
    K, _ = rf.camera_calibration(edex, camera_id)
    mesh = rf.load_export_object_mesh(export_seq)
    est = rf._pose_estimator(mesh, out / "debug")
    if est.glctx is None:
        import nvdiffrast.torch as dr
        est.glctx = dr.RasterizeCudaContext()
    to_c = est.get_tf_to_centered_mesh().cpu().numpy()  # pose_original = pose_centered @ to_c
    _, axes = np.linalg.eigh(np.asarray(mesh.convex_hull.moment_inertia))
    turns = [("none", np.eye(3))]
    for k in range(3):
        for deg in range(STEP_DEG, 360, STEP_DEG):
            turns.append((f"ax{k}_{deg}", Rotation.from_rotvec(axes[:, k] * np.deg2rad(deg)).as_matrix()))
    rows = []
    for f in frames:
        _, rgb, depth, _, mask_o, Kf = rf._read_foundationpose_frame(export_seq, depth_root, camera_id, names[f], K)
        P = np.asarray(fp["fp_poses_cam"][f, 0], np.float64)
        Pc = P @ np.linalg.inv(to_c)  # pose of the centred mesh
        cands = []
        for _, Rt in turns:
            C = Pc.copy()
            C[:3, :3] = Pc[:3, :3] @ Rt  # turn about the centred mesh's origin, in its own frame
            cands.append(C)
        cands = np.asarray(cands, np.float32)
        depth_f = rf.Utils.erode_depth(depth, radius=2, device="cuda")
        depth_f = rf.Utils.bilateral_filter_depth(depth_f, radius=2, device="cuda")
        if refine_iter:
            xyz = rf.Utils.depth2xyzmap(depth_f, Kf)
            cands, _ = est.refiner.predict(mesh=est.mesh, mesh_tensors=est.mesh_tensors, rgb=rgb, depth=depth_f, K=Kf,
                                           ob_in_cams=cands, normal_map=None, xyz_map=xyz, glctx=est.glctx,
                                           mesh_diameter=est.diameter, iteration=refine_iter, get_vis=False)
            cands = cands.data.cpu().numpy() if torch.is_tensor(cands) else np.asarray(cands)
        depth_s = torch.zeros_like(depth_f) if (rgb_only and torch.is_tensor(depth_f)) else (np.zeros_like(depth_f) if rgb_only else depth_f)
        scores, vis = est.scorer.predict(mesh=est.mesh, rgb=rgb, depth=depth_s, K=Kf, ob_in_cams=cands, normal_map=None,
                                         mesh_tensors=est.mesh_tensors, glctx=est.glctx, mesh_diameter=est.diameter, get_vis=True)
        s = np.asarray(scores.data.cpu().numpy() if torch.is_tensor(scores) else scores, np.float64).ravel()
        order = np.argsort(-s)
        prob = np.exp(s - s.max())
        prob /= prob.sum()
        rank_none = int(np.flatnonzero(order == 0)[0])
        top = int(order[0])
        rows.append({"episode": ep, "frame": f, "object_pixels": int(mask_o.sum()), "rank_of_input": rank_none,
                     "top": turns[top][0], "p_top": round(float(prob[top]), 3), "p_input": round(float(prob[0]), 3),
                     "top5": [(turns[i][0], round(float(prob[i]), 3)) for i in order[:5]]})
        print(json.dumps(rows[-1]), flush=True)
        if vis is not None:
            cv2.imwrite(str(out / f"ep{ep:02d}_f{f:04d}_score_vis.jpg"), cv2.cvtColor(np.asarray(vis), cv2.COLOR_RGB2BGR))
        np.save(out / f"ep{ep:02d}_f{f:04d}_cands.npy", np.stack([c @ to_c for c in cands]))
    (out / f"ep{ep:02d}_probe.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
