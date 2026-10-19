"""Object half of t3_convert_ep.decode only: refined.pth pose_abs @ S2A -> object_cam.npz (pilot review, 10-16;
moved here 10-19 for t3_sel_pilot.sh from dev/init_pilot/decode_object.py, unchanged otherwise).

    python decode_object.py <cari4d episode dir> <out dir>
"""

import json
import sys
from pathlib import Path

import numpy as np
import torch

ep_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
pr = torch.load(ep_dir / "inference" / "refined.pth", map_location="cpu", weights_only=False)["pr"]
(export_dir,) = [d for d in (ep_dir / "export").iterdir() if d.is_dir()]
export = json.loads((export_dir / "wild_export.json").read_text())
s2a = np.asarray(export["source_object_mesh_to_aligned_transform"], np.float64)
poses = np.asarray(pr["pose_abs"], np.float64) @ s2a
rot = poses[:, :3, :3]
orth = float(np.abs(rot @ rot.transpose(0, 2, 1) - np.eye(3)).max())
if orth > 1e-4 or not np.isfinite(poses).all():
    raise SystemExit(f"object poses are not finite rigid transforms (orthogonality error {orth:.2e})")
old = np.load(out / "object_cam.npz")
if old["T_cam_glb"].shape != poses.shape:
    raise SystemExit(f"frame count differs: {old['T_cam_glb'].shape} vs {poses.shape}")
d = np.einsum("tij,tkj->tik", poses[:, :3, :3], old["T_cam_glb"][:, :3, :3])
turn = np.degrees(np.arccos(np.clip((np.trace(d, axis1=1, axis2=2) - 1) / 2, -1, 1)))
np.savez(out / "object_cam.npz", T_cam_glb=poses, intrinsics=np.asarray(export["intrinsics"], np.float64))
print(json.dumps({"frames": len(poses), "changed_frames": int((turn > 1e-3).sum()), "turn_deg_max": round(float(turn.max()), 1)}))
