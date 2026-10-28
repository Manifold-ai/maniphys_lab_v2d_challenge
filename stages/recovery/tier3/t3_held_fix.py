"""Orientation jumps of a Tier 3 object trajectory outside its resting runs, unwrapped and redistributed (Tier 3 inputs only).

Plan: agent-doc/plan-t3hand-2026-10-27.md on track2/p1-training, version 3, section 1 P1 and criterion H0.

The rollouts of ep13, ep15, ep19 and ep27 lose the object at the frames where the reference orientation turns 24-170 deg
in one frame while the object is held or in the air (results/ml40/t3hand/probe2_ml40.txt, held_fix records). The recipe
terminates a rollout at an orientation error of 0.6 rad, so a jump the simulated object cannot make ends the episode.
t3_dynamics_post.py keeps those frames on purpose (its outliers rule). This step runs on the input of the dynamics
post-process (the dr2s layer) and only touches the frames the dynamics post-process does not lock:
  symmetry   as the dynamics post-process: frame by frame the orientation equivalent (gate/t3_symmetry.py) closest to the
             previous frame, about the centre of mass, so turns between equivalent poses do not count as jumps;
  locked     unheld frames inside the input's resting anchors (runs/<version>.depth_post.json, as the dynamics
             post-process reads them; held from the physics check, closed over GAP frames). Everything else is one or
             more "free" runs: held, or unheld in the air;
  unwrap     inside a free run, the orientation is rebuilt from the measured frame-to-frame turns, except that a turn
             above JUMP_DEG is dropped (the branch switch is an artifact, the motion measured after it is kept);
  match      the rebuilt run then ends D away from the measured last frame (and from the locked run after it). D is spread
             over the run as a slow twist about the centre of mass with a cosine weight from 0 at the run's first frame
             to 1 at its last, so both ends meet their neighbours and no frame turns faster than the measured motion plus
             angle(D) / length. A run at the episode's end has no neighbour after it and keeps D = 0.
  caps       a run whose spread would exceed MAX_SPREAD_DEG per frame is left as it is (reported as skipped); an episode
             is refused only if a processed run still turns above JUMP_DEG somewhere.
The centre of mass keeps its own path (pos = com - R @ com_b), so only the orientation target changes. Frames the step does
not change keep the input bytes (also the ones the symmetry step would have turned: the dynamics post-process redoes it).
Writes runs/<out version>{,_suspect}/ with the same layout and meta as the input, copies the input's depth_post.json
under the output name (positions and anchors are unchanged), runs/<out version>.held_fix.json and .provenance.json.

    python t3_held_fix.py <tier3 root> <version> <physics dir> <out version> [episode,...]
One json line per episode on stdout. CPU only.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_closing
from scipy.spatial.transform import Rotation

FPS = 30.0
GAP = 5  # frames, as t3_dynamics_post.GAP
JUMP_DEG = float(np.degrees(4 * np.pi) / FPS)  # 24 deg per frame, as t3_fix_units.JUMP_DEG
MAX_SPREAD_DEG = 3.0  # per frame


def angle(a, b) -> float:
    return float(np.arccos(np.clip((np.trace(a.T @ b) - 1) / 2, -1, 1)))


def turn_deg(R: np.ndarray) -> np.ndarray:
    """Turn between frame t-1 and t (deg); 0 at frame 0."""
    return np.r_[0.0, [np.degrees(angle(R[t - 1], R[t])) for t in range(1, len(R))]]


def runs(mask) -> list[tuple[int, int]]:
    m = np.r_[False, np.asarray(mask, bool), False]
    d = np.flatnonzero(m[1:] != m[:-1])
    return list(zip(d[::2].tolist(), d[1::2].tolist()))


def unwrap_run(R: np.ndarray, s: int, e: int, jump_deg: float = JUMP_DEG, match_end: bool = True) -> tuple[np.ndarray, list[int], float]:
    """(R with frames s..e-1 rebuilt, the jump frames dropped, angle(D) in deg). match_end spreads the end mismatch D."""
    out = R.copy()
    jumps = []
    for t in range(s + 1, e):
        rel = R[t - 1].T @ R[t]
        if np.degrees(angle(R[t - 1], R[t])) > jump_deg:
            jumps.append(t)
            rel = np.eye(3)
        out[t] = out[t - 1] @ rel
    if not jumps:
        return R.copy(), [], 0.0
    D = out[e - 1].T @ R[e - 1]  # body-frame twist that brings the rebuilt end back onto the measured end
    ang = np.degrees(angle(out[e - 1], R[e - 1]))
    if match_end and e - s > 1:
        rv = Rotation.from_matrix(D).as_rotvec()
        w = 0.5 - 0.5 * np.cos(np.pi * np.arange(e - s) / (e - s - 1))
        for i, t in enumerate(range(s, e)):
            out[t] = out[t] @ Rotation.from_rotvec(rv * w[i]).as_matrix()
    return out, jumps, float(ang)


def main() -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq
    import trimesh

    here = Path(__file__).resolve().parent
    sys.path[:0] = [str(here), str(here / "gate"), str(here.parents[2] / "libs" / "v2d_infra")]
    from tier_guard import forbid_lower_tiers
    forbid_lower_tiers()  # Tier 3: nothing from Tier 1 or Tier 2 (Kaggle 2.8.c)
    import t3_provenance
    from t3_dynamics_post import to_q, to_R
    from t3_symmetry import SYM_M, Shape, nearest_equivalent, symmetries

    root, version, phys, out_v = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), sys.argv[4]
    only = {int(x) for x in sys.argv[5].split(",")} if len(sys.argv) > 5 else None
    rn = root / "runs"
    if (rn / out_v).exists() or (rn / f"{out_v}_suspect").exists():
        raise SystemExit(f"runs/{out_v} exists; pick a new name")
    prov = t3_provenance.stamp([root / "input", rn / version, rn / f"{version}_suspect", phys])
    metas = {m["episode_index"]: m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    rec = rn / f"{version}.height_post.json"
    rec = rec if rec.exists() else rn / f"{version}.depth_post.json"
    anchors = {row["episode"]: [(a["start"], a["end"]) for a in row["anchors"]] for row in json.loads(rec.read_text())}
    report = []
    for src_v, dst_v in ((version, out_v), (f"{version}_suspect", f"{out_v}_suspect")):
        for f in sorted((rn / src_v / "data" / "chunk-000").glob("episode_*.parquet")):
            table = pq.read_table(f)
            ep = int(table.column("episode_index")[0].as_py())
            if only and ep not in only:
                continue
            m = metas[ep]
            name = f"ep{ep:02d}_{m['object']}"
            pose = np.stack(table.column("observation.object.pose").to_numpy(zero_copy_only=False)).astype(np.float64)
            pos, R = pose[:, :3], to_R(pose[:, 3:7])
            n = len(pos)
            mesh = trimesh.load(root / "input" / m["mesh"], force="mesh")
            body = mesh if mesh.is_watertight else mesh.convex_hull
            com_b = np.asarray(body.center_mass)
            shape = Shape(mesh, com_b)
            G, sym_axis = symmetries(shape, body.moment_inertia)
            com = pos + R @ com_b
            Rc = R.copy()
            if len(G) > 1 or sym_axis is not None:
                for t in range(1, n):
                    Rc[t] = nearest_equivalent(R[t], Rc[t - 1], G, sym_axis)
            for t in range(n):
                if angle(R[t], Rc[t]) > 1e-6 and shape.shift(R[t].T @ Rc[t]) > SYM_M:
                    raise SystemExit(f"{name}: frame {t}'s symmetric turn moves the surface {shape.shift(R[t].T @ Rc[t]):.4f} m")
            held = np.load(phys / "out" / f"{name}.npz")["held"].astype(bool)
            if len(held) != n:
                raise SystemExit(f"{name}: {len(held)} held flags for {n} frames")
            held = binary_closing(held, np.ones(2 * GAP + 1, bool)) | held
            resting = np.zeros(n, bool)
            for a, b in anchors.get(name, []):
                resting[a:b] = True
            locked = ~held & resting
            td0 = turn_deg(Rc)
            new_R = Rc.copy()
            rows_runs, skipped, reasons = [], [], []
            processed = np.zeros(n, bool)
            for s, e in runs(~locked):
                match_end = e < n
                rr, jumps, dang = unwrap_run(new_R, s, e, match_end=match_end)
                if not jumps:
                    continue
                spread = dang / max(1, e - s - 1) if match_end else 0.0
                if spread > MAX_SPREAD_DEG:
                    skipped.append({"start": s, "end": e, "jumps": jumps, "end_mismatch_deg": round(dang, 1), "spread_deg_per_frame": round(spread, 2)})
                    continue
                new_R = rr
                processed[s:e] = True
                rows_runs.append({"start": s, "end": e, "held_share": round(float(held[s:e].mean()), 2), "jumps": jumps,
                                  "end_mismatch_deg": round(dang, 1), "spread_deg_per_frame": round(spread, 2)})
            td1 = turn_deg(new_R)
            left = [t for t in range(1, n) if processed[t] and processed[t - 1] and td1[t] > JUMP_DEG + 1e-6]
            if left:
                reasons.append(f"{len(left)} processed frames still turn above {JUMP_DEG:.0f} deg ({left[:6]})")
            refused = bool(reasons)
            if refused:
                new_R, rows_runs = Rc.copy(), []
            changed = np.array([angle(Rc[t], new_R[t]) > 1e-6 for t in range(n)])  # frames only the symmetry step turned keep the input bytes
            new_pos = com - new_R @ com_b
            out = pose.copy()
            out[changed, :3] = new_pos[changed]
            out[changed, 3:7] = to_q(new_R[changed])
            col = pa.FixedSizeListArray.from_arrays(pa.array(out.astype(np.float32).ravel(), pa.float32()), 7)
            i = table.schema.get_field_index("observation.object.pose")
            out_t = table.set_column(i, table.schema.field(i), col)
            md = dict(out_t.schema.metadata or {})
            md[b"held_fix"] = json.dumps({"from": version, "runs": rows_runs, "skipped": skipped, "refused": reasons}).encode()
            out_t = out_t.replace_schema_metadata(md)
            dst = rn / dst_v / "data" / "chunk-000" / f.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(out_t, dst)
            (rn / dst_v / "meta").mkdir(exist_ok=True)
            mf = rn / src_v / "meta" / f"episode_{ep:06d}.metadata.json"
            (rn / dst_v / "meta" / mf.name).write_bytes(mf.read_bytes())
            free = ~locked
            jumps0 = int(sum(td0[t] > JUMP_DEG for t in range(1, n) if free[t] and free[t - 1]))
            jumps1 = int(sum(td1[t] > JUMP_DEG for t in range(1, n) if free[t] and free[t - 1]))
            row = {"episode": name, "tier": dst_v, "frames": n, "symmetries": len(G), "continuous_axis": sym_axis is not None,
                   "held_share": round(float(held.mean()), 3), "locked_share": round(float(locked.mean()), 3),
                   "free_jump_frames_before_after": [jumps0, jumps1], "runs": rows_runs, "skipped_runs": skipped,
                   "changed_frames": int(changed.sum()), "changed_share": round(float(changed.mean()), 3),
                   "max_turn_from_input_deg": round(float(max([np.degrees(angle(R[t], new_R[t])) for t in np.flatnonzero(changed)], default=0.0)), 1),
                   "max_turn_per_frame_before_after_deg": [round(float(td0.max()), 1), round(float(td1.max()), 1)],
                   "refused": reasons}
            report.append(row)
            print(json.dumps(row), flush=True)
    shutil.copy2(rec, rn / f"{out_v}.{rec.name.split('.', 1)[1]}")
    (rn / f"{out_v}.held_fix.json").write_text(json.dumps(report, indent=1))
    t3_provenance.write(rn / f"{out_v}.provenance.json", prov | {"made_by": "t3_held_fix.py", "from_version": version})


if __name__ == "__main__":
    main()
