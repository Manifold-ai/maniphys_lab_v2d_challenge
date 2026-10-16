"""ep29 (10-16): per frame, the human layer's nearest foot to the luggage surface, by sole vertices and by foot joints
(best_hm, as t3_physics_check.py builds them). Runs in the v2d_cari4d image like t3_physics_check check.
    python ep29_human_feet.py <tier3 root> <npz> <soma assets> <out npz>"""
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

sys.path.insert(0, "/s")
from soma import SOMALayer  # noqa: E402
from soma.units import Unit  # noqa: E402
from t3_physics_check import HUMAN_COLUMNS  # noqa: E402
from t3_world_probe import soma_cv, soma_joint_names  # noqa: E402

root, npz, assets, out = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
layer = SOMALayer(data_root=assets, identity_model_type="mhr", device="cpu", output_unit=Unit.METERS, enable_procedural_transforms=False)
names = [str(x) for x in layer._public_joint_names]
w = np.asarray(layer.skinning_weights, np.float64)
z = np.load(npz)
mesh = trimesh.load(root / "input/mesh/rolling_luggage/rolling_luggage.glb", force="mesh")
surface = np.asarray(trimesh.sample.sample_surface_even(mesh, 20000, seed=0)[0], np.float64)
tree = cKDTree(surface)
pose = z["object_pose"]
n = len(pose)
rot = Rotation.from_quat(np.c_[pose[:, 4:7], pose[:, 3:4]]).as_matrix()
pos = pose[:, :3]
joints, verts = soma_cv({k: z[k] for k in HUMAN_COLUMNS}, layer)
jn = soma_joint_names(layer, joints.shape[1])
res = {}
for side in ("Left", "Right"):
    idx = np.nonzero(w[:, [names.index(f"{side}Foot"), names.index(f"{side}ToeBase"), names.index(f"{side}ToeEnd")]].sum(1) >= 0.5)[0]
    v = np.einsum("nji,nkj->nki", rot, verts[:, idx] - pos[:, None])
    res[f"{side}_vert"] = tree.query(v.reshape(-1, 3))[0].reshape(n, -1).min(1)
    ji = [jn.index(f"{side}{p}") for p in ("Foot", "ToeBase", "ToeEnd")]
    j = np.einsum("nji,nkj->nki", rot, joints[:, ji] - pos[:, None])
    res[f"{side}_joint"] = tree.query(j.reshape(-1, 3))[0].reshape(n, -1).min(1)
hj = [i for i, nm in enumerate(jn) if "Hand" in nm]
hv = np.einsum("nji,nkj->nki", rot, joints[:, hj] - pos[:, None])
res["hand_joint"] = tree.query(hv.reshape(-1, 3))[0].reshape(n, -1).min(1)
np.savez(out, **res)
for k, v in res.items():
    print(k, "p10/p50 cm", np.round(np.percentile(v, [10, 50]) * 100, 1))
