"""Acceptance check of the floor correction on what the downstream reads: the assembled Tier 3 parquet. For the
floor-resting events of t3_camera_height.py (chosen from the masks, not from these poses), the lowest point of the
official mesh at the parquet's object pose, height above the released ground plane. rxzhou's Tier 3 pilot measured the
same thing after retargeting (10/9: 114.9 / 146.2 mm on ep8 / ep24 before the correction).

    python t3_floor_check.py <tier3 root> <tier dir> [<tier dir> ...]
"""

import json
import t3_inputs  # noqa: E402  (same directory: released inputs Tier 3 may read)
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import trimesh
from scipy.spatial.transform import Rotation


def main() -> None:
    root, tiers = Path(sys.argv[1]), [Path(a) for a in sys.argv[2:]]
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    events = []
    for f in sorted((root / "runs/camera_groups").glob("camera_height_*.json")):
        events += json.loads(f.read_text())["event_rows"]
    rows = []
    for tier in tiers:
        for path in sorted((tier / "data/chunk-000").glob("episode_*.parquet")):
            ep = int(path.stem.split("_")[1])
            m = metas[ep]
            name = f"ep{ep:02d}_{m['object']}"
            frames = [e["frame"] for e in events if e["episode"] == name]
            table = pq.read_table(path)
            variant = (table.schema.metadata or {}).get(b"trajectory_variant", b"").decode()
            if not frames:
                rows.append({"episode": name, "tier": tier.name, "variant": variant, "events": 0})
                continue
            pose = np.stack(table.column("observation.object.pose").to_numpy(zero_copy_only=False))[frames].astype(np.float64)
            rot = Rotation.from_quat(np.c_[pose[:, 4:7], pose[:, 3:4]]).as_matrix()
            gp = np.asarray(t3_inputs.ground_plane(root, m), np.float64)
            n, d = gp[:3] / np.linalg.norm(gp[:3]), gp[3] / np.linalg.norm(gp[:3])
            if d < 0:
                n, d = -n, -d
            hull = np.asarray(trimesh.load(root / "input" / m["mesh"], force="mesh").convex_hull.vertices, np.float64)
            h = ((np.einsum("fij,kj->fki", rot, hull) + pose[:, None, :3]) @ n + d).min(1)
            rows.append({"episode": name, "tier": tier.name, "variant": variant, "events": len(frames),
                         "depth_m_median": round(float(np.median(pose[:, 2])), 2),
                         "lowest_above_floor_m_median": round(float(np.median(h)), 4),
                         "p10_p90": np.percentile(h, [10, 90]).round(4).tolist()})
            print(json.dumps(rows[-1]), flush=True)
    hv = [r["lowest_above_floor_m_median"] for r in rows if r.get("events")]
    if hv:
        print(json.dumps({"episodes_with_events": len(hv), "abs_median_m": round(float(np.median(np.abs(hv))), 4),
                          "abs_max_m": round(float(np.max(np.abs(hv))), 4)}))


if __name__ == "__main__":
    main()
