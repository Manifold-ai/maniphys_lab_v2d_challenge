"""Format probe: feed one Tier 3 episode through rxzhou's stages/retarget/challenge_to_soma.py unchanged.

The converter is imported as is; only its tier root and runs root are pointed at a temporary layout, because
libs/v2d_infra/paths.py has no Tier 3 yet. support_surface is not decided for Tier 3, so a missing support file is
recorded instead of failing. Checks the soma_params.npz and poses.npy it writes against the parquet.

    python probe_rx_format.py <repo root> <tier3 dir> <tier3 input dir> <episode> <soma assets> <scratch dir>
"""

import json
import os
import shutil
import sys
from pathlib import Path

import numpy as np


def main() -> None:
    repo, tier_dir, inp, ep, assets, scratch = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]), Path(sys.argv[5]), Path(sys.argv[6])
    root = scratch / "tier_root"
    shutil.rmtree(scratch, ignore_errors=True)
    (root / "meta").mkdir(parents=True)
    meta = json.loads((tier_dir / "meta" / f"episode_{ep:06d}.metadata.json").read_text())
    (root / "meta" / "episodes_metadata.jsonl").write_text(json.dumps(meta) + "\n")
    os.symlink(tier_dir / "data", root / "data")
    for d in ("mesh", "ground_plane"):
        os.symlink(inp / d, root / d)

    sys.path.insert(0, str(repo / "libs" / "v2d_infra"))
    import paths

    paths.SOMA_ASSETS = assets
    paths.tier = lambda n: root
    sys.path.insert(0, str(repo / "stages" / "retarget"))
    import challenge_to_soma as c2s

    c2s.tier = lambda n: root
    missing = []
    real_copy = shutil.copyfile

    def copy_or_record(src, dst, *a, **k):
        if not Path(src).exists() and "support_surface" in str(src):
            missing.append(str(src))
            return dst
        return real_copy(src, dst, *a, **k)

    c2s.shutil.copyfile = copy_or_record
    out = c2s.convert(3, ep, runs_root=scratch / "runs")
    src = Path(out["data_folder"])
    sp = np.load(src / "soma_params.npz")
    poses = np.load(src / "poses.npy")
    checks = {
        "frames": out["frames"], "source_fps": out["source_fps"], "invisible_filled": out["invisible_filled"],
        "soma_poses_shape": list(sp["poses"].shape), "flex_shape": list(sp["bone_length_flexibles"].shape),
        "poses_npy_shape": list(poses.shape), "poses_rigid_err": float(np.abs(poses[:, :3, :3] @ poses[:, :3, :3].transpose(0, 2, 1) - np.eye(3)).max()),
        "joint_names_n": len(sp["joint_names"]), "mesh_copied": (src / "reconstructed_mesh" / "output_aligned.glb").exists(),
        "ground_plane_copied": (src / "ground_plane.json").exists(), "support_missing": missing,
    }
    print(json.dumps(checks))


if __name__ == "__main__":
    main()
