"""Orientation jumps inside held runs of a Tier 3 object trajectory, repaired by slerp across the jump stretch (Tier 3 inputs only).

Plan: agent-doc/plan-t3hand-2026-10-27.md on track2/p1-training, version 2, section 1 P1 and criterion H0.

The rollouts of ep13, ep19 and ep27 lose the object at the frames where the reference orientation turns 24-170 deg in one
frame inside a held run (results/ml40/t3hand/probe2_ml40.txt). A held rigid body cannot do that; it is the reconstruction
switching branches. t3_dynamics_post.py keeps those frames on purpose (its outliers rule, set for ep03's rest). This step
runs on the input of the dynamics post-process (the dr2s layer) and only touches held runs:
  symmetry  as the dynamics post-process: frame by frame the orientation equivalent (gate/t3_symmetry.py) closest to the
            previous frame, about the centre of mass, so turns between equivalent poses do not count as jumps;
  held      the physics check's held flags of the input version, closed over GAP frames (as the dynamics post-process);
  jumps     inside a held run, a frame whose turn from the previous frame exceeds JUMP_DEG. The stretch starts at the last
            frame a before the jump and ends at the first frame b >= jump with angle(R_a, R_b) <= JUMP_DEG * (b - a) and
            no jump in the GOOD_RUN frames after b; if none, b is the run's last frame. Frames a < t < b get the slerp
            between R_a and R_b (about the centre of mass; the centre of mass keeps its own path, so only the position
            column changes by the turn of the mesh origin about it). A stretch that would still leave a turn above
            JUMP_DEG, or an episode whose replaced frames exceed MAX_SHARE, is refused (the episode is left as it is).
Writes runs/<out version>{,_suspect}/ with the same layout and meta as the input (only observation.object.pose
differs, and only on replaced frames), runs/<out version>.held_fix.json and runs/<out version>.provenance.json.

    python t3_held_fix.py <tier3 root> <version> <physics dir> <out version> [episode,...]
One json line per episode on stdout. CPU only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import binary_closing
from scipy.spatial.transform import Rotation, Slerp

FPS = 30.0
GAP = 5  # frames, as t3_dynamics_post.GAP
JUMP_DEG = float(np.degrees(4 * np.pi) / FPS)  # 24 deg per frame, as t3_fix_units.JUMP_DEG
GOOD_RUN = 5  # frames
MAX_SHARE = 0.20


def angle(a, b) -> float:
    return float(np.arccos(np.clip((np.trace(a.T @ b) - 1) / 2, -1, 1)))


def turn_deg(R: np.ndarray) -> np.ndarray:
    """Turn between frame t-1 and t (deg); 0 at frame 0."""
    return np.r_[0.0, [np.degrees(angle(R[t - 1], R[t])) for t in range(1, len(R))]]


def runs(mask) -> list[tuple[int, int]]:
    m = np.r_[False, np.asarray(mask, bool), False]
    d = np.flatnonzero(m[1:] != m[:-1])
    return list(zip(d[::2].tolist(), d[1::2].tolist()))


def stretches(R: np.ndarray, held: np.ndarray, jump_deg: float = JUMP_DEG, good_run: int = GOOD_RUN) -> list[tuple[int, int]]:
    """[a, b] pairs to interpolate across, inside held runs; a and b keep their orientation."""
    td = turn_deg(R)
    out = []
    for s, e in runs(held):
        t = s + 1
        while t < e:
            if td[t] <= jump_deg:
                t += 1
                continue
            a = t - 1
            b = None
            for c in range(t, e):
                if np.degrees(angle(R[a], R[c])) <= jump_deg * (c - a) and all(td[u] <= jump_deg for u in range(c + 1, min(c + 1 + good_run, e))):
                    b = c
                    break
            if b is None:
                b = e - 1
            if b > a + 1:
                out.append((a, b))
            t = b + 1
    return out


def slerp_fill(R: np.ndarray, a: int, b: int) -> np.ndarray:
    """R with frames a < t < b replaced by the slerp between R[a] and R[b]."""
    out = R.copy()
    if b - a < 2:
        return out
    s = Slerp([a, b], Rotation.from_matrix(np.stack([R[a], R[b]])))
    out[a + 1:b] = s(np.arange(a + 1, b)).as_matrix()
    return out


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
            td0 = turn_deg(Rc)
            st = stretches(Rc, held)
            new_R = Rc.copy()
            for a, b in st:
                new_R = slerp_fill(new_R, a, b)
            replaced = np.zeros(n, bool)
            for a, b in st:
                replaced[a + 1:b] = True
            td1 = turn_deg(new_R)
            reasons = []
            if replaced.mean() > MAX_SHARE:
                reasons.append(f"replaced share {replaced.mean():.2f} > {MAX_SHARE}")
            left = [t for t in range(1, n) if held[t] and held[t - 1] and td1[t] > JUMP_DEG + 1e-6]
            if left:
                reasons.append(f"{len(left)} held frames still turn above {JUMP_DEG:.0f} deg ({left[:6]})")
            refused = bool(reasons)
            if refused:
                new_R, replaced = Rc.copy(), np.zeros(n, bool)
            new_pos = com - new_R @ com_b  # the centre of mass keeps its path
            out = pose.copy()
            out[replaced, :3] = new_pos[replaced]
            out[replaced, 3:7] = to_q(new_R[replaced])
            # frames not replaced keep the input bytes (also the ones the symmetry step would have turned)
            col = pa.FixedSizeListArray.from_arrays(pa.array(out.astype(np.float32).ravel(), pa.float32()), 7)
            i = table.schema.get_field_index("observation.object.pose")
            out_t = table.set_column(i, table.schema.field(i), col)
            md = dict(out_t.schema.metadata or {})
            md[b"held_fix"] = json.dumps({"from": version, "stretches": st, "refused": reasons}).encode()
            out_t = out_t.replace_schema_metadata(md)
            dst = rn / dst_v / "data" / "chunk-000" / f.name
            dst.parent.mkdir(parents=True, exist_ok=True)
            pq.write_table(out_t, dst)
            (rn / dst_v / "meta").mkdir(exist_ok=True)
            mf = rn / src_v / "meta" / f"episode_{ep:06d}.metadata.json"
            (rn / dst_v / "meta" / mf.name).write_bytes(mf.read_bytes())
            held_jumps0 = int(sum(td0[t] > JUMP_DEG for t in range(1, n) if held[t] and held[t - 1]))
            held_jumps1 = int(sum(td1[t] > JUMP_DEG for t in range(1, n) if held[t] and held[t - 1]))
            row = {"episode": name, "tier": dst_v, "frames": n, "symmetries": len(G), "continuous_axis": sym_axis is not None,
                   "held_share": round(float(held.mean()), 3), "held_jump_frames_before_after": [held_jumps0, held_jumps1],
                   "stretches": [[int(a), int(b)] for a, b in st], "replaced_frames": int(replaced.sum()),
                   "replaced_share": round(float(replaced.mean()), 3),
                   "max_turn_replaced_from_input_deg": round(float(max([np.degrees(angle(R[t], new_R[t])) for t in np.flatnonzero(replaced)], default=0.0)), 1),
                   "refused": reasons}
            report.append(row)
            print(json.dumps(row), flush=True)
    (rn / f"{out_v}.held_fix.json").write_text(json.dumps(report, indent=1))
    t3_provenance.write(rn / f"{out_v}.provenance.json", prov | {"made_by": "t3_held_fix.py", "from_version": version})


if __name__ == "__main__":
    main()
