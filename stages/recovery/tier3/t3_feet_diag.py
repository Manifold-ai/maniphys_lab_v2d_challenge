"""Where do the feet go below the floor? Sole height before and after the world step (diagnostic, Tier 3 inputs only).

The physics check found the lower sole point 1-10 cm under the released plane on most episodes. Per episode, medians
over frames:
  - focal stage (camera frame, soma_params_focal.npz) against our own floor for that exo camera (floor_fit groups:
    n_ours, d_ours): feet and pelvis height;
  - world stage (soma_params_world.npz) against the released plane: feet height;
  - predicted world feet if the world step scales the pelvis position by s about the camera and leaves the body as is:
    feet_focal + (s - 1) * pelvis_focal. Heights over a plane through the camera-side offset d scale by s with the
    positions, legs do not.

    python t3_feet_diag.py <tier3 root> <floor_fit.json> <soma assets> <out .json>
"""

import json
import t3_inputs  # noqa: E402  (same directory: released inputs Tier 3 may read)
import sys
from pathlib import Path

import numpy as np


def main() -> None:
    from soma import SOMALayer
    from soma.units import Unit

    from t3_world_probe import soma_cv

    root, fit_path, assets, out = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
    fit = json.loads(fit_path.read_text())
    groups = {g["group"]: g for g in fit["groups"]}
    metas = {f"ep{m['episode_index']:02d}_{m['object']}": m
             for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    layer = SOMALayer(data_root=assets, identity_model_type="mhr", device="cpu", output_unit=Unit.METERS,
                      enable_procedural_transforms=False)
    names = [str(x) for x in layer._public_joint_names]
    pelvis = names.index("Hips") if "Hips" in names else 0
    w = np.asarray(layer.skinning_weights, np.float64)
    soles = [np.nonzero(w[:, [names.index(f"{s}Foot"), names.index(f"{s}ToeBase"), names.index(f"{s}ToeEnd")]].sum(1) >= 0.5)[0]
             for s in ("Left", "Right")]

    def plane(n, d):
        n, d = np.asarray(n, np.float64), float(d)
        k = np.linalg.norm(n)
        n, d = n / k, d / k
        return (n, d) if d > 0 else (-n, -d)

    keys = ("poses", "transl", "identity_coeffs", "scale_params", "bone_length_flexibles")
    rows = []
    for conv in sorted((root / "runs/convert").glob("ep*")):
        name = conv.name
        entry = fit["episodes"].get(name)
        if entry is None or not (conv / "soma_params_world.npz").exists():
            continue
        g = groups[entry["group"]]
        n_o, d_o = plane(g["n_ours"], g["d_ours_m"])
        gp = np.asarray(t3_inputs.ground_plane(root, metas[name]), np.float64)
        n_r, d_r = plane(gp[:3], gp[3])
        out_row = {"episode": name, "group": entry["group"], "scale": entry["scale"]}
        for stage, f, (n, d) in (("focal", "soma_params_focal.npz", (n_o, d_o)), ("world", "soma_params_world.npz", (n_r, d_r))):
            sp = dict(np.load(conv / f, allow_pickle=True))
            joints, verts = soma_cv({k: sp[k] for k in keys}, layer)
            feet = np.stack([(verts[:, idx] @ n + d).min(1) for idx in soles], 1).min(1)
            out_row[f"feet_{stage}_m"] = round(float(np.median(feet)), 4)
            out_row[f"pelvis_{stage}_m"] = round(float(np.median(joints[:, pelvis] @ n + d)), 4)
        out_row["feet_world_predicted_m"] = round(out_row["feet_focal_m"] + (entry["scale"] - 1) * out_row["pelvis_focal_m"], 4)
        rows.append(out_row)
        print(json.dumps(out_row), flush=True)
    out.write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
