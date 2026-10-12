"""Our supports (t3_support.py) as the support usda the retarget and training read, in g1_retarget_world (gate env, L40S).

Tier 3 does not use the released support_surface files: they exist only in the Tier 1 / Tier 2 directories, Tier 3 has
no input of its own (kit tracks.json: input_path None), and Kaggle rule 2.8.c forbids a Tier 3 submission produced from
an easier tier's input; their placement also comes from the clean capture (under each rest position of the clean
object, in the world anchored on the released human's frame 0). So the files are written from our supports.

g1_retarget_world is the frame soma_to_g1 (v0.4.0) builds per episode, the same rigid map for every frame:
  OpenCV -> SOMA axes (_R_CV_TO_SOMA), anchor on the human's frame-0 root (SOMA.load_motion's first_frame_transl,
  first_frame_R_inv), level the floor plane onto z = 0 (load_ground_plane_robot_frame, compute_plane_leveling_transform),
  source -> robot axes (config.r_world).  soma_to_g1.py 359-466; the object alone then gets a frame-0 ground lift, which
  a support does not.
It is computed here with the upstream functions themselves (and rxzhou's SOMAWithFlex, which the gate's retarget uses), so
no retarget run is needed. When the gate's retarget output for the episode exists, the same map applied to the object's
frame-0 pose must reproduce it (lift removed) within CHECK_M, or the episode is refused.

A support's top: its patch (t3_support's main-floor coordinates) projected onto the episode's released floor plane
(read through t3_inputs, plane only), raised by height_m along the floor normal, mapped as above. Written as the released
files are written: one Cube slab per support (size 1, translate, scale, no rotation; the patch's axis-aligned box in
world xy, SLAB_M thick, top at the mapped height). Episodes without supports get the released files' empty stage.

    python t3_support_usda.py <gate repo> <set> <support dir> <tier3 root> <out dir>
<gate repo>/runs/motion_src/tier3_<set>/<sequence>/ must hold the converter's output (soma_params.npz, poses.npy) for
the version the supports go with: the frame depends on that version's human. Writes <out dir>/<sequence>_support.usda
and <out dir>/support_usda.json (per episode: supports, tops, check residual).
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

import numpy as np

SLAB_M = 0.02
CHECK_M = 1e-4
EMPTY = ('#usda 1.0\n(\n    defaultPrim = "support_surfaces"\n    metersPerUnit = 1\n    upAxis = "Z"\n)\n\n'
         'def Xform "support_surfaces"\n{\n')


def chain(mod, soma, config, plane: list[float], params: Path):
    """4x4 map from the source OpenCV frame to g1_retarget_world for one episode (soma_to_g1.py 359-466)."""
    from robotic_grounding.retarget.ground_alignment import compute_plane_leveling_transform, load_ground_plane_robot_frame

    motion = soma.load_motion(params_path=str(params), normalize=True)
    anchor = np.eye(4)
    anchor[:3, :3] = motion["first_frame_R_inv"]
    anchor[:3, 3] = -motion["first_frame_R_inv"] @ motion["first_frame_transl"]
    r_world = np.asarray(config.r_world, dtype=np.float64)
    with tempfile.TemporaryDirectory() as d:
        gp = Path(d) / "ground_plane.json"
        gp.write_text(json.dumps({"plane": plane}))
        ref = load_ground_plane_robot_frame(gp, cv_to_source=mod._R_CV_TO_SOMA, first_frame_anchor=anchor, source_to_robot=r_world)
    rot_r, trans_r = compute_plane_leveling_transform(ref)
    level = np.eye(4)
    level[:3, :3] = r_world.T @ rot_r @ r_world
    level[:3, 3] = r_world.T @ trans_r
    robot = np.eye(4)
    robot[:3, :3] = r_world
    return robot @ level @ anchor @ mod._R_CV_TO_SOMA


def main() -> None:
    gate, name, sup_dir, t3, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4]), Path(sys.argv[5])
    sys.path[:0] = [str(gate / "stages/retarget"), str(gate / "libs/v2d_infra"), str(t3 / "code/stages/recovery/tier3")]
    import pyarrow.parquet as pq
    import t3_inputs
    import torch
    from paths import UPSTREAM
    from robotic_grounding.retarget.robot_config import load_robot_config
    from scipy.spatial.transform import Rotation
    from soma_flex import SOMAWithFlex, load_official_soma_to_g1
    from t3_support import basis, main_basis

    mod = load_official_soma_to_g1(UPSTREAM)
    soma = SOMAWithFlex(data_root=None, identity_model_type="mhr", device=torch.device("cpu"))
    config = load_robot_config("g1")
    o_m, u_m, v_m = main_basis(t3)
    out.mkdir(parents=True, exist_ok=True)
    root = gate / f"runs/tier3/root_{name}"
    report, bad = [], []
    for m in map(json.loads, (root / "meta/episodes_metadata.jsonl").read_text().splitlines()):
        ep, seq = m["episode_index"], m["sequence_id"]
        tag = f"ep{ep:02d}_{m['object']}"
        src = gate / f"runs/motion_src/tier3_{name}/{seq}"
        plane = t3_inputs.ground_plane(t3, m)
        T = chain(mod, soma, config, plane, src / "soma_params.npz")
        row = {"episode": tag, "sequence_id": seq}
        part = gate / f"runs/motion/tier3_{name}/whole_body/soma/sequence_id={seq}/robot_name=g1/data.parquet"
        log = gate / f"runs/logs/batch/t3_{name}_ep{ep:02d}.log"
        if part.exists() and log.exists():  # check against the gate's own retarget of this version
            r = pq.read_table(part).to_pylist()[0]
            lift = float(re.findall(r"frame-0 ground correction: .*applied=([+-]\d+\.\d+) m", log.read_text(errors="replace"))[-1])
            want = np.eye(4)
            want[:3, :3] = Rotation.from_quat(np.array(r["object_body_wxyz"][0][0])[[1, 2, 3, 0]]).as_matrix()
            want[:3, 3] = np.array(r["object_body_position"][0][0]) - [0.0, 0.0, lift]
            got = T @ np.load(src / "poses.npy")[0]
            row["check_m"] = round(float(max(np.abs(got[:3, 3] - want[:3, 3]).max(), np.abs(got[:3, :3] - want[:3, :3]).max())), 7)
            if row["check_m"] > CHECK_M:
                bad.append(tag)
        f = sup_dir / f"{tag}.json"
        sups = json.loads(f.read_text())["supports"] if f.exists() else []
        n, d, _, _, _ = basis(plane)
        body, tops = "", []
        for s in sups:
            poly = np.asarray(s["patch_xy_m"], np.float64)
            if len(poly) < 3:
                continue
            P = o_m + poly[:, :1] * u_m + poly[:, 1:2] * v_m
            P = P - (P @ n + d)[:, None] * n + s["height_m"] * n
            W = P @ T[:3, :3].T + T[:3, 3]
            lo, hi = W[:, :2].min(0), W[:, :2].max(0)
            top = float(W[:, 2].mean())
            tops.append({"support": s["support"], "height_m": s["height_m"], "top_z_m": round(top, 4),
                         "xy_min_m": np.round(lo, 4).tolist(), "xy_max_m": np.round(hi, 4).tolist()})
            body += (f'    def Cube "support_{s["support"]}" (\n        prepend apiSchemas = ["PhysicsCollisionAPI"]\n    )\n    {{\n'
                     f'        double size = 1\n'
                     f'        double3 xformOp:translate = ({(lo[0] + hi[0]) / 2:.4f}, {(lo[1] + hi[1]) / 2:.4f}, {top - SLAB_M / 2:.4f})\n'
                     f'        double3 xformOp:scale = ({hi[0] - lo[0]:.4f}, {hi[1] - lo[1]:.4f}, {SLAB_M})\n'
                     f'        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]\n    }}\n')
        (out / Path(m["support_surface"]).name).write_text(EMPTY + body + "}\n")
        row["supports"] = tops
        report.append(row)
        print(json.dumps(row), flush=True)
    (out / "support_usda.json").write_text(json.dumps({"set": name, "support_dir": str(sup_dir), "episodes": report}, indent=1))
    if bad:
        raise SystemExit(f"frame check failed (> {CHECK_M} m): {bad}")


if __name__ == "__main__":
    main()
