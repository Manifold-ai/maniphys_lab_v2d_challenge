"""Foot slip, human layer against robot layer: does the glide come from the reconstruction or from retargeting?

t3_foot_slip.py reads the robot layer only. Here both layers get one definition that needs no common frame: per foot,
the 3D speed of a sole centroid (robot: G1 sole collision points, see t3_dynamics_check.limb_points; human: the mean
of the SOMA Foot, ToeBase and ToeEnd joints), differentiated by the same local quadratic over WINDOW_S. The support is
the slower foot; a frame glides when the support moves faster than REST_MPS. No floor test (the human layer has no
floor in its own frame), so swing phases where both feet are in the air count too; the two layers are read
side by side, not against t3_foot_slip.py's numbers. 3D speed is invariant to the rigid source-to-robot transform,
but retargeting rescales the body to G1, so robot speeds read lower than the human's by about that ratio.

The human layer is the retargeter's own input: each robot parquet's raw_motion_file (soma_params.npz), run through
robotic_grounding's SOMA reader the way soma_to_g1.py does.

Usage: t3_foot_slip_layers.py <motion set dir> <episodes_metadata.jsonl> <SOMA assets dir> <out.json> [episode,...]
"""

import json
import os
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from scipy.signal import savgol_filter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from t3_dynamics_check import HELD_COLS, REST_MPS, WINDOW_S, limb_points, runs  # noqa: E402

FOOT_JOINTS = ("Foot", "ToeBase", "ToeEnd")


def support(cents: list[np.ndarray], fps: float) -> dict:
    """cents: per foot (T, 3) centroid -> support summary."""
    win = int(round(WINDOW_S * fps)) | 1
    v = np.min([np.linalg.norm(savgol_filter(c, win, 2, deriv=1, delta=1 / fps, axis=0, mode="interp"), axis=1) for c in cents], 0)
    glide = v > REST_MPS
    lens = [float((v[a:b] / fps).sum()) for a, b in runs(glide)]
    return {"gliding_share": round(float(glide.mean()), 3), "speed_p50_p95": [round(float(x), 4) for x in np.percentile(v, [50, 95])],
            "longest_glide_m": round(max(lens), 3) if lens else 0.0, "glide_m_total": round(sum(lens), 3)}


def main():
    mset, meta, assets, out = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
    only = {int(x) for x in sys.argv[5].split(",")} if len(sys.argv) > 5 else None
    gate = Path(os.environ["T3_GATE"])
    sys.path.insert(0, str(gate / "repo/third_party/video_to_data/robotic_grounding/source/robotic_grounding"))
    from robotic_grounding.retarget.read_soma import SOMA  # noqa: PLC0415

    soma = SOMA(assets)
    feet = {s: [soma.rig_joint_names.index(f"{s}{j}") for j in FOOT_JOINTS] for s in ("Left", "Right")}
    res = {"set": str(mset), "episodes": {}}
    for m in map(json.loads, open(meta)):
        ep, seq = m["episode_index"], m["sequence_id"]
        if only and ep not in only:
            continue
        part = mset / "whole_body/soma" / f"sequence_id={seq}" / "robot_name=g1"
        if not (part / "data.parquet").exists():
            continue
        r = pq.read_table(part / "data.parquet", columns=["fps", "raw_motion_file"] + HELD_COLS).to_pylist()[0]
        fps = r["fps"]
        soles = [P.mean(1) for P in limb_points(r, feet=True, hands=False, split=True).values()]
        J = soma.load_motion(r["raw_motion_file"])["joints"]
        if len(J) != len(soles[0]):
            raise SystemExit(f"ep{ep:02d}: human {len(J)} frames, robot {len(soles[0])}")
        robot = support(soles, fps)
        human = support([J[:, idx].mean(1) for idx in feet.values()], fps)
        res["episodes"][f"ep{ep:02d}"] = {"human": human, "robot": robot}
        print(f"ep{ep:02d} gliding human {human['gliding_share']} robot {robot['gliding_share']} | support v p50 human "
              f"{human['speed_p50_p95'][0]} robot {robot['speed_p50_p95'][0]} | total glide human {human['glide_m_total']} "
              f"robot {robot['glide_m_total']} m", flush=True)
    if not res["episodes"]:
        raise SystemExit(f"no episode found under {mset}")
    out.write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
