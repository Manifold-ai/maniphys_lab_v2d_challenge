"""Foot slip in a retargeted reference: how fast a sole moves along the floor while it stands on it (robot layer).

A sole is on the floor when its lowest collision point (G1's sole cylinders, by forward kinematics of the training URDF,
see t3_dynamics_check.limb_points) is within SUPPORT_TOL_M of the floor (z = 0 in g1_retarget_world). Its horizontal
velocity is the sole points' centroid, differentiated by the same local quadratic over WINDOW_S the dynamics check
uses. A standing sole moving faster than REST_MPS slides: the one rest/motion threshold of the dynamics check.

Per episode, the support: on frames with a sole on the floor, the slowest such sole. If it moves faster than REST_MPS
no foot stands still, so the whole body glides along the floor: share of those frames, the support's speed p50/p95,
and the longest glide (contiguous gliding frames, horizontal travel of the gliding sole's centroid summed). This is
the number to read: a 3 cm height test cannot tell a stance from a low swing (Tier 1 reads 92-96 % of frames on the
floor per foot), so per-foot numbers below count swings too and are kept only for reference.

Per foot: frames on the floor, share of them sliding, horizontal speed p50/p95 on the floor.

Usage: t3_foot_slip.py <motion set dir> <episodes_metadata.jsonl> <out.json> [episode,...]
"""

import json
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from scipy.signal import savgol_filter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from t3_dynamics_check import HELD_COLS, REST_MPS, SUPPORT_TOL_M, WINDOW_S, limb_points, runs  # noqa: E402

def slip(part: Path) -> dict:
    r = pq.read_table(part / "data.parquet", columns=["fps"] + HELD_COLS).to_pylist()[0]
    fps = r["fps"]
    win = int(round(WINDOW_S * fps)) | 1
    soles = limb_points(r, feet=True, hands=False, split=True)
    out, speeds, ons = {}, [], []
    for name, P in soles.items():
        side = name.split("_")[0]
        low = P[..., 2].min(1)
        c = P.mean(1)[:, :2]
        v = np.linalg.norm(savgol_filter(c, win, 2, deriv=1, delta=1 / fps, axis=0, mode="interp"), axis=1)
        on = low <= SUPPORT_TOL_M
        speeds.append(np.where(on, v, np.inf))
        ons.append(on)
        out[side] = {"on_floor": round(float(on.mean()), 3), "sliding_share": round(float((v[on] > REST_MPS).mean()), 3) if on.any() else None,
                     "speed_on_floor_p50_p95": pct(v[on], [50, 95])}
    sup = np.min(speeds, 0)
    grounded = np.isfinite(sup)
    glide = grounded & (sup > REST_MPS)
    lens = [float((sup[a:b] / fps).sum()) for a, b in runs(glide)]
    out["support"] = {"grounded": round(float(grounded.mean()), 3), "gliding_share": round(float(glide[grounded].mean()), 3) if grounded.any() else None,
                      "speed_p50_p95": pct(sup[grounded], [50, 95]), "longest_glide_m": round(max(lens), 3) if lens else 0.0,
                      "glide_m_total": round(sum(lens), 3)}
    return out


def pct(x, q):
    return [round(float(y), 4) for y in np.percentile(x, q)] if len(x) else None


def main():
    mset, meta, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    only = {int(x) for x in sys.argv[4].split(",")} if len(sys.argv) > 4 else None
    res = {"set": str(mset), "episodes": {}}
    for m in map(json.loads, open(meta)):
        ep, seq = m["episode_index"], m["sequence_id"]
        if only and ep not in only:
            continue
        part = mset / "whole_body/soma" / f"sequence_id={seq}" / "robot_name=g1"
        if not (part / "data.parquet").exists():
            continue
        e = res["episodes"][f"ep{ep:02d}"] = slip(part)
        s = e["support"]
        print(f"ep{ep:02d} grounded {s['grounded']:.2f} gliding {s['gliding_share']} support v {s['speed_p50_p95']} "
              f"longest glide {s['longest_glide_m']} m total {s['glide_m_total']} m", flush=True)
    if not res["episodes"]:
        raise SystemExit(f"no episode found under {mset}")
    out.write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
