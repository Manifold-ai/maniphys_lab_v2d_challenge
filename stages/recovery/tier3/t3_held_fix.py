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
  unwrap     inside a free run, the output is the measured orientation times a body-frame correction that is constant
             between jumps; at a turn above JUMP_DEG the correction is reset so the output continues the previous frame's
             motion (the branch switch is an artifact, the motion measured on the new branch is kept, re-expressed);
  match      the rebuilt run then ends D away from the next rest's robust mean, taken modulo the shape's symmetry group
             (plan-t3flip13 review: a rest on an equivalent branch is what the dynamics post-process would turn anyway). D is spread
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
from scipy.spatial.transform import Rotation, Slerp

FPS = 30.0
GAP = 5  # frames, as t3_dynamics_post.GAP
JUMP_DEG = float(np.degrees(4 * np.pi) / FPS)  # 24 deg per frame, as t3_fix_units.JUMP_DEG
MAX_SPREAD_DEG = 3.0  # per frame
STORM_GAP = 5  # frames: jumps closer than this form one storm
RETURN_RATE_DEG = 6.0  # per frame: a storm whose two ends (modulo the symmetry group) are reachable at this rate is bridged by slerp
RETURN_MAX_DEG = 90.0
MAX_D_DEG = 20.0  # as t3_dynamics_post.MAX_OFFSET_DEG
MIN_RUN = 3  # frames, as t3_dynamics_post.MIN_RUN
WINDOW = 8  # frames, for the windowed turn report


def angle(a, b) -> float:
    return float(np.arccos(np.clip((np.trace(a.T @ b) - 1) / 2, -1, 1)))


def turn_deg(R: np.ndarray) -> np.ndarray:
    """Turn between frame t-1 and t (deg); 0 at frame 0."""
    return np.r_[0.0, [np.degrees(angle(R[t - 1], R[t])) for t in range(1, len(R))]]


def runs(mask) -> list[tuple[int, int]]:
    m = np.r_[False, np.asarray(mask, bool), False]
    d = np.flatnonzero(m[1:] != m[:-1])
    return list(zip(d[::2].tolist(), d[1::2].tolist()))


def so3(M: np.ndarray) -> np.ndarray:
    """Nearest rotation to M (polar decomposition), so products of many rotations stay orthonormal."""
    U, _, Vt = np.linalg.svd(M)
    Rm = U @ Vt
    if np.linalg.det(Rm) < 0:
        U[:, -1] *= -1
        Rm = U @ Vt
    return Rm


def unwrap_run(R: np.ndarray, s: int, e: int, jump_deg: float = JUMP_DEG, match_end: bool = True, R_target=None, group=(), storms_out=None) -> tuple[np.ndarray, list[int], float]:
    """(R with frames s..e-1 rebuilt, the jump frames, angle(D) in deg). Inside the run the output is R[t] @ C with a
    body-frame correction C that is constant between jumps; at a jump C is reset so that the output continues the previous
    frame's motion (R[t] @ C = out[t-1] @ rel_prev), i.e. the branch switch is removed and the motion measured on the new
    branch is kept. match_end spreads the end mismatch D (output end vs measured end) over the run as a cosine twist."""
    out = R.copy()
    jumps = []
    # storms: clusters of jumps (no mask evidence inside, the reconstruction is lost there). A storm whose two ends agree
    # modulo the symmetry group is a returning glitch and is bridged by slerp; a storm that ends on another branch is left
    # to the constant-correction pass below (the branch switch is removed there).
    td = turn_deg(out[s:e])
    jf = [s + t for t in range(1, e - s) if td[t] > jump_deg]
    storms, i = [], 0
    while i < len(jf):
        j = i
        while j + 1 < len(jf) and jf[j + 1] - jf[j] <= STORM_GAP:
            j += 1
        storms.append((jf[i] - 1, min(e - 1, jf[j])))
        i = j + 1
    bridged, switched = [], []
    for a, b in storms:
        if b - a < 2:
            continue
        g_best = min([np.eye(3), *group], key=lambda g: angle(out[a], out[b] @ np.asarray(g)))
        if np.degrees(angle(out[a], out[b] @ np.asarray(g_best))) <= min(RETURN_MAX_DEG, RETURN_RATE_DEG * (b - a)):
            key = Rotation.from_matrix(np.stack([out[a], so3(out[b] @ np.asarray(g_best))]))
            sl = Slerp([a, b], key)
            out[a + 1:b] = sl(np.arange(a + 1, b)).as_matrix()
            out[b] = so3(out[b] @ np.asarray(g_best))
            bridged.append((a, b))
        else:
            # a branch switch: the frames inside the storm carry no usable motion (the reconstruction is lost there),
            # so they hold the last good pose and the switch becomes one jump at b, removed by the pass below
            out[a + 1:b] = out[a]
            switched.append((a, b))
    inside = {}
    for a_, b_ in bridged:
        for t in range(a_ + 1, b_ + 1):
            inside[t] = ("bridged", a_, b_)
    for a_, b_ in switched:
        for t in range(a_ + 1, b_ + 1):
            inside[t] = ("switched", a_, b_)
    C = np.eye(3)
    for t in range(s + 1, e):
        if t in inside:
            kind, a_, b_ = inside[t]
            if t < b_:
                continue  # interior of a storm: already held (switched) or interpolated (bridged)
            if kind == "switched":
                rel_prev = out[a_ - 1].T @ out[a_] if a_ - 1 >= s else np.eye(3)
                C = so3(R[t].T @ out[a_] @ rel_prev)
                out[t] = so3(R[t] @ C)
            else:
                C = so3(R[t].T @ out[t])  # out[b] was already turned onto the returning branch
            continue
        cand = so3(R[t] @ C)
        if np.degrees(angle(out[t - 1], cand)) > jump_deg:
            jumps.append(t)
            rel_prev = out[t - 2].T @ out[t - 1] if t - 2 >= s else np.eye(3)
            C = so3(R[t].T @ out[t - 1] @ rel_prev)
            cand = so3(R[t] @ C)
        out[t] = cand
    if storms_out is not None:
        storms_out.extend([("bridged", a, b) for a, b in bridged] + [("switched", a, b) for a, b in switched])
    if not jumps and not bridged and not switched:
        return R.copy(), [], 0.0
    jumps = sorted(set(jumps) | {a + 1 for a, b in bridged} | {a + 1 for a, b in switched})
    tgt = R[e - 1] if R_target is None else R_target
    # the target modulo the shape's symmetry group: the rest after the run may sit on an equivalent branch, which the
    # dynamics post-process would turn onto this run's branch anyway (its symmetry step is a continuity rule)
    best = min([np.eye(3), *group], key=lambda g: angle(out[e - 1], tgt @ np.asarray(g)))
    tgt = so3(tgt @ np.asarray(best))
    D = so3(out[e - 1].T @ tgt)  # body-frame twist that brings the rebuilt end onto the target
    ang = np.degrees(angle(out[e - 1], tgt))
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
    from t3_dynamics_post import robust_mean, to_q, to_R
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
    win = WINDOW
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
            bad = [t for t in range(n) if abs(np.linalg.det(R[t]) - 1) > 1e-3 or np.abs(R[t] @ R[t].T - np.eye(3)).max() > 1e-3]
            if bad:
                raise SystemExit(f"{name}: {len(bad)} frames are not rotations (first {bad[:5]})")
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
            if name not in anchors:
                raise SystemExit(f"{name}: no anchors in {rec.name} (the dynamics post-process would stop too)")
            resting = np.zeros(n, bool)
            for a, b in anchors[name]:
                resting[a:b] = True
            locked = ~held & resting
            for a, b in runs(locked):  # as the dynamics post-process: a rest shorter than MIN_RUN is not locked
                if b - a < MIN_RUN:
                    locked[a:b] = False
            td0 = turn_deg(Rc)
            new_R = Rc.copy()
            rows_runs, skipped, reasons = [], [], []
            processed = np.zeros(n, bool)
            lock_runs = runs(locked)
            for s, e in runs(~locked):
                match_end = e < n
                tgt = None
                if match_end:
                    nxt = next(((a, b) for a, b in lock_runs if a == e), None)
                    if nxt is not None:
                        tgt = robust_mean(Rc[nxt[0]:nxt[1]])[0]
                st_ = []
                rr, jumps, dang = unwrap_run(new_R, s, e, match_end=match_end, R_target=tgt, group=[np.asarray(g) for g in G[1:]], storms_out=st_)
                if not jumps:
                    continue
                spread = dang / max(1, e - s - 1) if match_end else 0.0
                if dang > MAX_D_DEG or spread > MAX_SPREAD_DEG:
                    skipped.append({"start": s, "end": e, "jumps": jumps, "storms": st_, "end_mismatch_deg": round(dang, 1), "spread_deg_per_frame": round(spread, 2),
                                    "why": "D above cap" if dang > MAX_D_DEG else "spread above cap"})
                    continue
                new_R = rr
                processed[s:e] = True
                rows_runs.append({"start": s, "end": e, "held_share": round(float(held[s:e].mean()), 2), "jumps": jumps, "storms": st_,
                                  "end_mismatch_deg": round(dang, 1), "spread_deg_per_frame": round(spread, 2)})
            td1 = turn_deg(new_R)
            left = [t for t in range(1, n) if processed[t] and processed[t - 1] and td1[t] > JUMP_DEG + 1e-6]
            if left:
                reasons.append(f"{len(left)} processed frames still turn above {JUMP_DEG:.0f} deg ({left[:6]})")
            refused = bool(reasons)
            if refused:
                new_R, rows_runs = Rc.copy(), []
            changed = np.array([angle(Rc[t], new_R[t]) > 1e-6 for t in range(n)])  # frames only the symmetry step turned keep the input bytes
            wt0 = np.array([np.degrees(angle(Rc[t], Rc[min(n - 1, t + win)])) for t in range(n)])
            wt1 = np.array([np.degrees(angle(new_R[t], new_R[min(n - 1, t + win)])) for t in range(n)])
            free = ~locked
            bnd0, bnd1 = [], []
            for r_ in rows_runs:
                for t in (r_["start"], r_["end"]):
                    if 1 <= t < n:
                        bnd0.append(td0[t]); bnd1.append(td1[t])
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
            jumps0 = int(sum(td0[t] > JUMP_DEG for t in range(1, n) if free[t] and free[t - 1]))
            jumps1 = int(sum(td1[t] > JUMP_DEG for t in range(1, n) if free[t] and free[t - 1]))
            row = {"episode": name, "tier": dst_v, "frames": n, "symmetries": len(G), "continuous_axis": sym_axis is not None,
                   "held_share": round(float(held.mean()), 3), "locked_share": round(float(locked.mean()), 3),
                   "free_jump_frames_before_after": [jumps0, jumps1], "runs": rows_runs, "skipped_runs": skipped,
                   "changed_frames": int(changed.sum()), "changed_share": round(float(changed.mean()), 3),
                   "max_turn_from_input_deg": round(float(max([np.degrees(angle(R[t], new_R[t])) for t in np.flatnonzero(changed)], default=0.0)), 1),
                   "max_turn_per_frame_before_after_deg": [round(float(td0.max()), 1), round(float(td1.max()), 1)],
                   "free_window8_turn_max_before_after_deg": [round(float(wt0[free].max()), 1) if free.any() else 0.0, round(float(wt1[free].max()), 1) if free.any() else 0.0],
                   "processed_boundary_turn_max_before_after_deg": [round(float(max(bnd0, default=0.0)), 1), round(float(max(bnd1, default=0.0)), 1)],
                   "changed": np.flatnonzero(changed).tolist(),
                   "refused": reasons}
            report.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != "changed"}), flush=True)
    shutil.copy2(rec, rn / f"{out_v}.{rec.name.split('.', 1)[1]}")
    (rn / f"{out_v}.held_fix.json").write_text(json.dumps(report, indent=1))
    t3_provenance.write(rn / f"{out_v}.provenance.json", prov | {"made_by": "t3_held_fix.py", "from_version": version})


if __name__ == "__main__":
    main()
