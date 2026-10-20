"""gb6: per part, the stage-05 initialization of gb4 (runs/work_fp) or of gb5 (runs/work_b050), whichever gives the lower
cost of the stitched sequence; then CoCoNet 06-08 and the chain re-run on the stitched initialization (10-21, user;
registered in agent-doc/handoff-tier3-rotation-2026-10-21-attr.md "gb6 登记" before any part was computed).

Why: gb5's timeline selection is right on some segments and wrong on others (attribution of the gb5 gate, user's
verdicts on ep01/02/17), so taking or keeping gb5 per batch loses right segments either way. Only the initialization is
stitched: the two versions' CoCoNet runs differ in the human too (identity 0.02-0.05, translation up to 20 cm), so
stitching the finished outputs would change the body mid-episode.

Rule (registered):
  1. changed frames: the delivered layer's (<version>_dr2s_dyn7, world) object orientations of gb4 and gb5 more than
     JUMP_DEG apart, symmetry-aware; runs merged across gaps shorter than MERGE frames.
  2. cuts: in each gap between consecutive changed runs, the frame c where the two stage-05 initializations are closest
     (symmetry-aware); the cut lies between c and c+1. Parts: episode start .. first cut, .., last cut + 1 .. end.
     An episode without a changed run takes gb5 whole.
  3. cost of part p under version v: sum over its frames of V_v (the dynamics check's object_any, as the gb5 gate's M2,
     each version on its own gate set and supports) plus J_v (CoCoNet's step f -> f+1 turns more than JUMP_DEG,
     symmetry-aware, counted at f, as M6).
  4. junction: neighbouring parts on different versions whose stitched initialization turns more than JUMP_DEG across
     the cut cost P = 1 + round(WINDOW_S * fps): the jump itself, and the dynamics check's local quadratic fit spreads
     it over up to WINDOW_S * fps frames of violations.
  5. per episode the least total cost over the part choices (dynamic programming along the chain); ties go to the
     combination with the most gb5 frames (the selector has appearance evidence; the physics check cannot tell an
     orientation on a resting frame).
  6. --write=<work dir>: the stitched stage-05 pkl (fp_poses_cam, obj_pose_world from each part's version; the other
     keys from gb5's, as t3_fp_select.py writes) with the stage-05 marker updated and 06-08 outputs removed, so
     t3_sel_full.sh runs 06-08 on it; foundationpose/fp_select.json carries this report (t3_sel_full.sh takes its
     presence as "selected"). An episode whose parts all take one version is a hard-linked copy of that version's
     work dir (the same initialization; its 06-08 are reused, not re-run).

    python t3_seg_mix.py <tier3 root> <gate dir> <out json> [--write=<work dir name>] <episode>...   (gate venv, T3_GATE set)
"""

import json
import os
import pickle
import shutil
import sys
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "gate"))
from t3_align_check import world_pose  # noqa: E402
from t3_dynamics_check import FOOT_TASK, WINDOW_S, check, supports_of  # noqa: E402
from t3_fp_select import sym_angle_deg  # noqa: E402
from t3_sel_gate import rotations  # noqa: E402
from t3_symmetry import Shape, symmetries  # noqa: E402

JUMP_DEG = 24.0
MERGE = 15
VERSIONS = {"gb4": ("tier3_cari4d_gb4_best_dr2s_dyn7", "gb4dyn7", "work_fp"),
            "gb5": ("tier3_cari4d_gb5_best_dr2s_dyn7", "gb5dyn7", "work_b050")}
STAGE678 = [".stages/06_*.json", ".stages/07_*.json", ".stages/08_*.json", "inference/coconet.pth",
            "inference/materialized_inputs.h5", "inference/refined.pth", "inference/refinement_checkpoint.pth",
            "inference/*.mp4", "pipeline_report.json"]


def runs(m):
    d = np.diff(np.r_[0, np.asarray(m, int), 0])
    return [[int(s), int(e - 1)] for s, e in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1))]


def per_frame_angle(Ra, Rb, G, axis):
    return np.array([sym_angle_deg(Ra[f:f + 1], Rb[f:f + 1], G, axis)[0, 0] for f in range(len(Ra))])


def stage05(ep_dir):
    (pkl,) = sorted((ep_dir / "foundationpose").glob("episode_*.pkl"))
    d = pickle.load(open(pkl, "rb"))
    s2a = np.asarray(json.loads((ep_dir / "export" / pkl.stem / "wild_export.json").read_text())["source_object_mesh_to_aligned_transform"], np.float64)
    return pkl, d, s2a


def decide(n, segs, init_ang, cost, junction):
    """Parts and the least-cost choice. cost[v] per frame (V + J); junction(c, a, b) -> stitched turn across cut c."""
    cuts = []
    for (_, e0), (s1, _) in zip(segs, segs[1:]):
        gap = np.arange(e0 + 1, s1)
        cuts.append(int(gap[np.argmin(init_ang[gap])]))
    bounds = [0] + [c + 1 for c in cuts] + [n]
    parts = [[bounds[i], bounds[i + 1] - 1] for i in range(len(bounds) - 1)]
    P = 1 + round(WINDOW_S * FPS)
    vs = ("gb4", "gb5")
    pc = [{v: int(cost[v][a:b + 1].sum()) for v in vs} for a, b in parts]
    # DP over parts; key (total cost, -gb5 frames) minimised lexicographically
    best = {v: ((pc[0][v], -(parts[0][1] - parts[0][0] + 1) * (v == "gb5")), [v]) for v in vs}
    junc = []
    for i in range(1, len(parts)):
        c = cuts[i - 1]
        nxt = {}
        for b in vs:
            cand = []
            for a in vs:
                (k0, k1), path = best[a]
                pen = P if a != b and junction(c, a, b) > JUMP_DEG else 0
                cand.append(((k0 + pen + pc[i][b], k1 - (parts[i][1] - parts[i][0] + 1) * (b == "gb5")), path + [b]))
            nxt[b] = min(cand, key=lambda x: x[0])
        best = nxt
    (total, neg5), choice = min(best.values(), key=lambda x: x[0])
    for i in range(1, len(parts)):
        a, b = choice[i - 1], choice[i]
        if a != b:
            junc.append({"cut": cuts[i - 1], "from": a, "to": b, "turn_deg": round(float(junction(cuts[i - 1], a, b)), 1)})
    return parts, pc, choice, int(total), -neg5, junc


def main():
    global FPS
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    write = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--write=")), None)
    T, G, out, eps = Path(args[0]), Path(args[1]), Path(args[2]), args[3:]
    metas = {m["episode_index"]: m for m in map(json.loads, (T / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}
    res = {"rule": "agent-doc/handoff-tier3-rotation-2026-10-21-attr.md, gb6 登记", "JUMP_DEG": JUMP_DEG, "MERGE": MERGE, "episodes": {}}
    for name in eps:
        ep = int(name[2:4])
        mesh = trimesh.load(T / "input" / metas[ep]["mesh"], force="mesh")
        body = mesh if mesh.is_watertight else mesh.convex_hull
        Gs, axis = symmetries(Shape(mesh, np.asarray(body.center_mass)), body.moment_inertia)
        final, init, cost, src = {}, {}, {}, {}
        for v, (ver, gset, work) in VERSIONS.items():
            final[v] = world_pose(T, ver, ep)[:, :3, :3]
            cdir = T / "runs" / work / name / "cari4d" / f"episode_{ep:06d}"
            pkl, d, s2a = stage05(cdir)
            src[v] = (cdir, pkl, d)
            init[v] = (np.asarray(d["fp_poses_cam"], np.float64)[:, 0] @ s2a)[:, :3, :3]
            gm = next(m for m in map(json.loads, open(G / f"repo/runs/tier3/root_{gset}/meta/episodes_metadata.jsonl")) if m["episode_index"] == ep)
            seq = gm["sequence_id"]
            part = G / f"repo/runs/motion/tier3_{gset}/whole_body/soma/sequence_id={seq}/robot_name=g1"
            dyn = check(part, supports_of(G / f"support_usda_{gset}" / f"{seq}_support.usda"), feet=bool(FOOT_TASK.search(gm["task"])), frames=True)
            FPS = dyn["fps"]
            R = rotations(cdir)
            J = np.zeros(len(R), int)
            J[:-1] = [sym_angle_deg(R[f:f + 1], R[f + 1:f + 2], Gs, axis)[0, 0] > JUMP_DEG for f in range(len(R) - 1)]
            cost[v] = np.asarray(dyn["per_frame"]["object_any"], int) + J
        n = len(final["gb4"])
        lens = {k: len(x) for k, x in [("final4", final["gb4"]), ("final5", final["gb5"]), ("init4", init["gb4"]),
                                      ("init5", init["gb5"]), ("cost4", cost["gb4"]), ("cost5", cost["gb5"])]}
        if len(set(lens.values())) != 1:
            raise SystemExit(f"{name}: frame counts differ {lens}")
        if list(src["gb4"][2]["frames"]) != list(src["gb5"][2]["frames"]):
            raise SystemExit(f"{name}: stage-05 frames differ between gb4 and gb5")
        changed = per_frame_angle(final["gb4"], final["gb5"], Gs, axis) > JUMP_DEG
        segs = []
        for s, e in runs(changed):
            if segs and s - segs[-1][1] - 1 < MERGE:
                segs[-1][1] = e
            else:
                segs.append([s, e])
        init_ang = per_frame_angle(init["gb4"], init["gb5"], Gs, axis)
        if not segs:
            parts, pc, choice, total, n5, junc = [[0, n - 1]], [{v: int(cost[v].sum()) for v in ("gb4", "gb5")}], ["gb5"], int(cost["gb5"].sum()), n, []
        else:
            parts, pc, choice, total, n5, junc = decide(n, segs, init_ang, cost,
                                                        lambda c, a, b: sym_angle_deg(init[a][c:c + 1], init[b][c + 1:c + 2], Gs, axis)[0, 0])
        e = {"frames": n, "segments": segs,
             "parts": [{"frames": p, "cost_gb4_gb5": [c["gb4"], c["gb5"]], "choice": ch} for p, c, ch in zip(parts, pc, choice)],
             "junctions": junc, "total_cost": total, "gb5_frames": n5,
             "all_gb4_cost": int(cost["gb4"].sum()), "all_gb5_cost": int(cost["gb5"].sum())}
        res["episodes"][name] = e
        print(name, "segments", len(segs), "choice", "".join("4" if c == "gb4" else "5" for c in choice),
              "cost", total, "| all gb4", e["all_gb4_cost"], "all gb5", e["all_gb5_cost"], "| gb5 frames", n5, "/", n,
              "| junctions", [(j["cut"], j["turn_deg"]) for j in junc], flush=True)
        if write:
            dst = T / "runs" / write / name
            if dst.exists():
                raise SystemExit(f"{dst} exists")
            one = set(choice)
            base = "gb4" if one == {"gb4"} else "gb5"
            # a reused episode is hard-linked (nothing below writes into its files: fp_select.json is unlinked first, and
            # t3_sel_full.sh mounts it read-only); a stitched one is a real copy, since 06-08 may rewrite files in place
            shutil.copytree(T / "runs" / VERSIONS[base][2] / name, dst, symlinks=True,
                            copy_function=os.link if len(one) == 1 else shutil.copy2)
            cdir = dst / "cari4d" / f"episode_{ep:06d}"
            (cdir / "foundationpose" / "fp_select.json").unlink(missing_ok=True)
            report = {"seg_mix": e, "reused_06_08_of": base if len(one) == 1 else None}
            if len(one) > 1:
                for pat in STAGE678:
                    for f in cdir.glob(pat):
                        f.unlink()
                pkl, d, _ = stage05(cdir)
                d4 = src["gb4"][2]
                W, C = np.array(d["obj_pose_world"]), np.array(d["fp_poses_cam"])
                W4, C4 = np.asarray(d4["obj_pose_world"]), np.asarray(d4["fp_poses_cam"])
                c2w5 = np.asarray(W, np.float64) @ np.linalg.inv(np.asarray(C, np.float64)[:, 0])
                c2w4 = np.asarray(W4, np.float64) @ np.linalg.inv(np.asarray(C4, np.float64)[:, 0])
                if not np.allclose(c2w4, c2w5, atol=1e-5):
                    raise SystemExit(f"{name}: gb4 and gb5 stage-05 camera-to-world differ")
                for (a, b), ch in zip(parts, choice):
                    if ch == "gb4":
                        W[a:b + 1], C[a:b + 1] = W4[a:b + 1], C4[a:b + 1]
                d["obj_pose_world"], d["fp_poses_cam"] = W, C
                with open(pkl, "wb") as fh:
                    pickle.dump(d, fh, protocol=4)
                st = os.stat(pkl)
                marker = cdir / ".stages" / "05_object_pose.json"
                m = json.load(open(marker))
                hit = [o for o in m["outputs"] if Path(o["path"]).name == pkl.name]
                assert len(hit) == 1, f"stage-05 marker does not list {pkl.name} once"
                hit[0].update(size=int(st.st_size), mtime_ns=int(st.st_mtime_ns))
                json.dump(m, open(marker, "w"))
                chk = (np.asarray(pickle.load(open(pkl, "rb"))["fp_poses_cam"], np.float64)[:, 0])
                n4 = sum(b - a + 1 for (a, b), ch in zip(parts, choice) if ch == "gb4")
                same4 = sum(np.allclose(chk[f], np.asarray(C4, np.float64)[f, 0]) for f in range(n))
                if same4 < n4:
                    raise SystemExit(f"{name}: stitched pkl holds gb4's pose on {same4} frames, expected at least {n4}")
                report["frames_from_gb4"] = n4
            json.dump(report, open(cdir / "foundationpose" / "fp_select.json", "w"), indent=1)
    out.write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
