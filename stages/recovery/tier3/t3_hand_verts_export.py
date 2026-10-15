"""Export per-frame hand surface points of a Tier 3 version's human (SOMA), for the hand-geometry flip probe (10-15).

Runs in v2d_cari4d (SOMA) on the physics check's extract npz (runs/physics/<version>/npz/episode_*.npz: the human
columns and the object pose). Hand vertices are those whose skinning weight on the joints named *Hand* (wrist and
finger joints of each side) sums to at least 0.5; HAND_PTS of each side are kept (fixed seed), in the world (OpenCV)
frame as t3_world_probe.soma_cv gives them. CPU only.

    python t3_hand_verts_export.py <npz dir> <soma assets> <out dir> <episode,...>
Writes <out dir>/epNN_hands.npz: left, right (T, HAND_PTS, 3) and object_pose (T, 7, xyz + wxyz).
"""

import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["CUDA_VISIBLE_DEVICES"] = ""
HAND_PTS = 150


def main() -> None:
    from soma import SOMALayer
    from soma.units import Unit

    from t3_physics_check import HUMAN_COLUMNS
    from t3_world_probe import soma_cv

    npz_dir, assets, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
    eps = {int(x) for x in sys.argv[4].split(",")}
    out.mkdir(parents=True, exist_ok=True)
    layer = SOMALayer(data_root=assets, identity_model_type="mhr", device="cpu", output_unit=Unit.METERS,
                      enable_procedural_transforms=False)
    names = [str(x) for x in layer._public_joint_names]  # with Root, as the skinning weights' columns
    w = np.asarray(layer.skinning_weights, np.float64)
    rng = np.random.default_rng(0)
    pick = {}
    for side in ("Left", "Right"):
        cols = [i for i, nm in enumerate(names) if nm.startswith(side) and "Hand" in nm]
        idx = np.flatnonzero(w[:, cols].sum(1) >= 0.5)
        pick[side.lower()] = np.sort(rng.choice(idx, min(HAND_PTS, len(idx)), replace=False))
    for f in sorted(npz_dir.glob("episode_*.npz")):
        z = np.load(f)
        ep = int(z["episode_index"])
        if ep not in eps:
            continue
        _, verts = soma_cv({k: z[k] for k in HUMAN_COLUMNS}, layer)
        np.savez_compressed(out / f"ep{ep:02d}_hands.npz", left=verts[:, pick["left"]], right=verts[:, pick["right"]],
                            object_pose=z["object_pose"])
        print(f"ep{ep:02d} frames {len(verts)} hand points {len(pick['left'])}+{len(pick['right'])}", flush=True)


if __name__ == "__main__":
    main()
