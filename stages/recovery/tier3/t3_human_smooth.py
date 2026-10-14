"""Human temporal smoothing: remove the per-frame jitter of the reconstructed body (Tier 3 inputs only).

CARI4D estimates the body frame by frame. Its root moves about 3 cm at high frequency (root acceleration p99 2.5-8
m/s^2 over a 0.3 s window, 10-14); all three tiers are scored against Tier 1's clean trajectories, and that noise is
not motion a policy can learn anything from. Every frame is replaced by a local quadratic fit over WINDOW_S, the window
the dynamics check differentiates with and the dynamics post-process smooths held objects with, so hand and object get
the same low-pass:

  translation   observation.human.translation, per axis (savgol, polyorder 2).
  rotations     observation.human.pose, 77 joints x axis-angle (the SOMA layer input): per joint, to
                quaternions, each made to agree in sign with the previous frame's, smoothed per component, normalised,
                back to axis-angle.

Identity, scale and bone-length columns are copied (the downstream reads frame 0's identity and scale). The object is
copied too. Feet are not pinned: the retargeted reference is measured afterwards (gate/t3_foot_slip.py) to see what
smoothing alone does to them.

    python t3_human_smooth.py <tier3 root> <version> <out version> [episode,...]
Writes runs/<out version>{,_suspect}/ (same split as the input) and runs/<out version>.human_smooth.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.signal import savgol_filter
from scipy.spatial.transform import Rotation

FPS = 30.0
WINDOW_S = 0.3
JOINTS = 77


def smooth_rotvecs(rv: np.ndarray, win: int) -> np.ndarray:
    """(T, 3) axis-angle -> smoothed (T, 3)."""
    q = Rotation.from_rotvec(rv).as_quat()
    for t in range(1, len(q)):
        if q[t] @ q[t - 1] < 0:
            q[t] = -q[t]
    q = savgol_filter(q, win, 2, axis=0, mode="interp")
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    return Rotation.from_quat(q).as_rotvec()


def main() -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    root, version, out_v = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    only = {int(x) for x in sys.argv[4].split(",")} if len(sys.argv) > 4 else None
    rn = root / "runs"
    if (rn / out_v).exists() or (rn / f"{out_v}_suspect").exists():
        raise SystemExit(f"runs/{out_v} exists; pick a new name")
    win = int(round(WINDOW_S * FPS)) | 1
    report = []
    for src_v, dst_v in ((version, out_v), (f"{version}_suspect", f"{out_v}_suspect")):
        for f in sorted((rn / src_v / "data" / "chunk-000").glob("episode_*.parquet")):
            table = pq.read_table(f)
            ep = int(table.column("episode_index")[0].as_py())
            if only and ep not in only:
                continue
            tr = np.stack(table.column("observation.human.translation").to_numpy(zero_copy_only=False)).astype(np.float64)
            pose = np.stack(table.column("observation.human.pose").to_numpy(zero_copy_only=False)).astype(np.float64)
            n = len(tr)
            if pose.shape[1] != JOINTS * 3:
                raise SystemExit(f"ep{ep:02d}: pose has {pose.shape[1]} values, expected {JOINTS * 3}")
            if n <= win:
                raise SystemExit(f"ep{ep:02d}: {n} frames, not more than the {win}-frame window")
            tr_s = savgol_filter(tr, win, 2, axis=0, mode="interp")
            rv = pose.reshape(n, JOINTS, 3)
            rv_s = np.stack([smooth_rotvecs(rv[:, j], win) for j in range(JOINTS)], 1)
            turn = np.stack([(Rotation.from_rotvec(rv_s[:, j]) * Rotation.from_rotvec(rv[:, j]).inv()).magnitude()
                             for j in range(JOINTS)], 1)

            out_t = table
            for col, val, width in (("observation.human.translation", tr_s, 3), ("observation.human.pose", rv_s.reshape(n, -1), JOINTS * 3)):
                arr = pa.FixedSizeListArray.from_arrays(pa.array(val.astype(np.float32).ravel(), pa.float32()), width)
                i = out_t.schema.get_field_index(col)
                out_t = out_t.set_column(i, out_t.schema.field(i), arr)
            md = dict(table.schema.metadata or {})
            md[b"human_smooth"] = json.dumps({"from": version, "window_s": WINDOW_S, "polyorder": 2}).encode()
            out_t = out_t.replace_schema_metadata(md)
            dst = rn / dst_v / "data" / "chunk-000" / f.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(out_t, dst)
            (rn / dst_v / "meta").mkdir(exist_ok=True)
            mf = rn / src_v / "meta" / f"episode_{ep:06d}.metadata.json"
            (rn / dst_v / "meta" / mf.name).write_bytes(mf.read_bytes())

            r4 = lambda x: round(float(x), 4)
            row = {"episode": ep, "tier": dst_v, "frames": n,
                   "root_shift_m_p50_p95_max": [r4(x) for x in np.percentile(np.linalg.norm(tr_s - tr, axis=1), [50, 95, 100])],
                   "joint_turn_rad_p50_p95_max": [r4(x) for x in np.percentile(turn, [50, 95, 100])]}
            report.append(row)
            print(json.dumps(row), flush=True)
    if not report:
        raise SystemExit(f"no episode under runs/{version}")
    (rn / f"{out_v}.human_smooth.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
