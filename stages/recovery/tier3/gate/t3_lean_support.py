"""Lean supports: what an object rests against when it cannot stand on its own, added to a set's support usda (gate env, L40S).

Our supports (t3_support.py) are the horizontal surfaces an object stands on. An object can also stand leaning on
something: ep01's vacuum and ep28's squeegee lean on a bar stool's seat while nobody holds them (10-21). The support
files have nothing there, so in simulation they fall at the first step (rxzhou's 10-15 onset analysis: ep1 off by 49 cm
and turned 84 deg by frame 51).

Which runs lean. An unheld run (held from t3_dynamics_check.check, the gate's definition) of at least MIN_RUN frames,
its object pose toppled quasi-statically on the plane of its lowest point: while the centre of mass is not over the base
(contacts within CONTACT_TOL), the hull turns about the base edge or point nearest the centre of mass, towards it, until
the next vertex reaches the plane; the sum of the turns is the settle tilt. A reconstructed pose is a degree or two off,
which leaves a legged stool on one leg; it settles within a few degrees (gb5: every run not leaning settles within 8.6
deg). A run leans when the settle tilt at its middle frame exceeds LEAN_DEG; past MAX_DEG the object falls (inf).

What it leans on, from the scene. MoGe's horizontal points on the people-free plate (t3_support.moge_world, the same
points and the same map to g1_retarget_world as the horizontal supports, through t3_support_usda.chain), restricted to
the topple side (beyond the pivot along the topple direction), between MOGE_MIN_H_M and the object's top, within
NEAR_XY_M of the object's own surface at about the same height (HEIGHT_BAND_M). NEAR_XY_M is wide because MoGe's
placement is not the reconstruction's: ep01's stool seat (0.628 m, 3934 horizontal points) reads 0.23 m from the vacuum
that leans on it (10-21). Their modal height (1 cm bins, at least MIN_POINTS within SURF_BAND_M of it) is the surface's
top; those points are its patch. No such surface: the run is reported (no_surface) and gets nothing; it is not guessed.

The box. Axis-aligned like every support the importer builds (translate and scale only), THICK_M thick, top at the
surface height, the patch's size (clipped to MIN_SIZE_M..MAX_SIZE_M) but not its place: its near face sits on the
object's surface points between the box's bottom and top along the topple direction's dominant axis (touching, not
through), centred on that section across. MoGe's height is off by a few cm (one round table: 0.748-0.789 m from objects,
0.775-0.845 m from MoGe, t3_support); that only moves the contact along the object. Each box is checked against the
run's pose: surface points inside the box at most PEN_M deep, nearest gap at most GAP_M; failing either, it is not
written and the run is reported. Overlapping boxes merge. Every box is then checked against the object's hull over the
whole episode: the object entering it deeper than EPISODE_PEN_M anywhere means the box is not where the real thing
stands (a stool is not passed through), so it is not written. ep28's squeegee, a failed reconstruction (hands 20-40 cm
off), gives three boxes up to a metre apart, each crossed by the squeegee elsewhere in the episode: none written (10-21).

    [T3_FLOOR_FIT=<runs/floor file>] [T3_REGISTER=<runs/floor file>] python t3_lean_support.py <gate repo> <set> <tier3 root> <usda dir> [--dry]
<usda dir> is t3_support_usda.py's output for the set; its usda get `support_lean_<i>` cubes appended and its
support_usda.json a `lean` entry per episode (runs, settle tilts, boxes, checks). --dry reports and writes nothing.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np

MIN_RUN = 15
CONTACT_TOL = 0.001
LEAN_DEG, MAX_DEG = 10.0, 45.0
MOGE_MIN_H_M = 0.15
NEAR_XY_M = 0.35
HEIGHT_BAND_M = 0.05
SURF_BAND_M = 0.02
MIN_POINTS = 100
THICK_M = 0.04
MIN_SIZE_M, MAX_SIZE_M = 0.10, 0.60
PEN_M, GAP_M = 0.003, 0.005
EPISODE_PEN_M = 0.01
SAMPLES = 20000


def settle_tilt(w: np.ndarray, c: np.ndarray):
    """Quasi-static topple of hull points w (world, z up) with centre of mass c; (total turn deg or inf, first pivot, direction)."""
    from scipy.spatial import ConvexHull, Delaunay
    from scipy.spatial.transform import Rotation

    total, first = 0.0, None
    for _ in range(50):
        z0 = w[:, 2].min()
        w, c = w - [0, 0, z0], c - [0, 0, z0]
        b2, c2 = w[w[:, 2] < CONTACT_TOL][:, :2], c[:2]
        piv = None
        if len(b2) >= 3:
            try:
                poly = b2[ConvexHull(b2).vertices]
                if Delaunay(poly).find_simplex(c2) >= 0:
                    return total, first
                best = None
                for i in range(len(poly)):
                    e0, ev = poly[i], poly[(i + 1) % len(poly)] - poly[i]
                    q = e0 + np.clip((c2 - e0) @ ev / (ev @ ev), 0, 1) * ev
                    if best is None or np.linalg.norm(c2 - q) < best[0]:
                        best = (np.linalg.norm(c2 - q), q)
                piv = best[1]
            except Exception:  # collinear contacts: fall back to the nearest one
                piv = None
        if piv is None:
            piv = b2[np.argmin(np.linalg.norm(b2 - c2, axis=1))]
        d = c2 - piv
        if np.linalg.norm(d) < 1e-6:
            return total, first
        d = d / np.linalg.norm(d)
        if first is None:
            first = (piv.copy(), d.copy())
        P = np.array([piv[0], piv[1], 0.0])
        u, h = (w - P)[:, :2] @ d, (w - P)[:, 2]
        cand = (u > 1e-4) & (h > CONTACT_TOL)
        if not cand.any():
            return float("inf"), first
        phi = np.arctan2(h[cand], u[cand]).min()
        total += np.degrees(phi)
        if total > MAX_DEG:
            return float("inf"), first
        T = Rotation.from_rotvec(phi * np.array([-d[1], d[0], 0.0]))  # z x d: tips +z towards d
        w, c = T.apply(w - P) + P, T.apply(c - P) + P
    return float("inf"), first


def box_inside(pts: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """Depth of each point inside the box (<= 0 outside)."""
    return np.minimum(pts - lo, hi - pts).min(1)


def main() -> None:
    gate, name, t3, udir = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
    dry = "--dry" in sys.argv[5:]
    here = Path(__file__).resolve().parent
    sys.path[:0] = [str(gate / "stages/retarget"), str(gate / "libs/v2d_infra"), str(here.parent), str(here)]
    import pyarrow.parquet as pq
    import t3_dynamics_check as dc
    import t3_inputs
    import torch
    import trimesh
    from paths import UPSTREAM
    from robotic_grounding.retarget.robot_config import load_robot_config
    from scipy.spatial.transform import Rotation
    from soma_flex import SOMAWithFlex, load_official_soma_to_g1
    from t3_support import FLOOR_FIT, REGISTER, basis, main_basis, moge_world
    from t3_support_usda import chain

    mod = load_official_soma_to_g1(UPSTREAM)
    soma = SOMAWithFlex(data_root=None, identity_model_type="mhr", device=torch.device("cpu"))
    config = load_robot_config("g1")
    o_m, u_m, v_m = main_basis(t3)
    fit = json.loads((t3 / "runs/floor" / FLOOR_FIT).read_text())["episodes"]
    regs = json.loads((t3 / "runs/floor" / REGISTER).read_text())["groups"]
    rep_path = udir / "support_usda.json"
    rep = json.loads(rep_path.read_text())
    rows = {r["sequence_id"]: r for r in rep["episodes"]}
    root = gate / f"runs/tier3/root_{name}"
    written = 0
    for m in map(json.loads, (root / "meta/episodes_metadata.jsonl").read_text().splitlines()):
        ep, seq = m["episode_index"], m["sequence_id"]
        tag = f"ep{ep:02d}_{m['object']}"
        part = gate / f"runs/motion/tier3_{name}/whole_body/soma/sequence_id={seq}/robot_name=g1"
        usda = udir / Path(m["support_surface"]).name
        e = dc.check(part, dc.supports_of(usda), feet=bool(dc.FOOT_TASK.search(m["task"])), frames=True)
        held = np.asarray(e["per_frame"]["held"], bool)
        r = pq.read_table(part / "data.parquet", columns=["object_body_position", "object_body_wxyz"]).to_pylist()[0]
        pos, quat = np.array(r["object_body_position"])[:, 0], np.array(r["object_body_wxyz"])[:, 0]
        mesh = trimesh.load(part.parent / "object" / "textured_mesh.obj", force="mesh", process=False)
        hull = np.asarray(mesh.convex_hull.vertices)
        com = np.asarray((mesh if mesh.is_watertight else mesh.convex_hull).center_mass)
        surf = np.asarray(mesh.sample(SAMPLES, seed=0) if "seed" in mesh.sample.__code__.co_varnames else mesh.sample(SAMPLES))
        R = lambda f: Rotation.from_quat(quat[f, [1, 2, 3, 0]])  # noqa: E731
        runs = []
        for a, b in dc.runs(~held):  # b exclusive
            if b - a < MIN_RUN:
                continue
            k = (a + b - 1) // 2
            tilt, first = settle_tilt(R(k).apply(hull) + pos[k], R(k).apply(com) + pos[k])
            if tilt > LEAN_DEG:
                runs.append({"frames": [int(a), int(b - 1)], "pose_frame": int(k), "settle_tilt_deg": tilt, "first": first})
        if not runs:
            continue
        plane = t3_inputs.ground_plane(t3, m)
        n, d, _, _, _ = basis(plane)
        T = chain(mod, soma, config, plane, gate / f"runs/motion_src/tier3_{name}/{seq}" / "soma_params.npz")
        mg = moge_world(t3 / "dev/walls", tag, plane, regs.get(str(fit[tag]["group"] if tag in fit else 0)))
        W = None
        if mg is not None:
            p, hg = mg
            P = o_m + p[:, :1] * u_m + p[:, 1:2] * v_m
            P = P - (P @ n + d)[:, None] * n + hg[:, None] * n
            W = P @ T[:3, :3].T + T[:3, 3]
        boxes, out_runs = [], []
        for run in runs:
            k = run["pose_frame"]
            piv, dirn = run.pop("first")
            sk = R(k).apply(surf) + pos[k]
            top = float(sk[:, 2].max())
            res = {**run, "settle_tilt_deg": None if np.isinf(run["settle_tilt_deg"]) else round(run["settle_tilt_deg"], 1)}
            if W is None:
                out_runs.append({**res, "result": "no_moge"})
                continue
            side = (W[:, :2] - piv) @ dirn > 0
            box_xy = (W[:, :2] > sk[:, :2].min(0) - NEAR_XY_M).all(1) & (W[:, :2] < sk[:, :2].max(0) + NEAR_XY_M).all(1)
            band = (W[:, 2] > MOGE_MIN_H_M) & (W[:, 2] < top + HEIGHT_BAND_M) & side & box_xy
            near = np.zeros(len(W), bool)
            for i in np.flatnonzero(band):
                s = sk[np.abs(sk[:, 2] - W[i, 2]) < HEIGHT_BAND_M]
                near[i] = len(s) > 0 and np.min(np.linalg.norm(s[:, :2] - W[i, :2], axis=1)) < NEAR_XY_M
            cand = W[near]
            if len(cand) < MIN_POINTS:
                out_runs.append({**res, "result": "no_surface", "points": int(len(cand))})
                continue
            hist, edges = np.histogram(cand[:, 2], bins=np.arange(MOGE_MIN_H_M, top + HEIGHT_BAND_M + 0.01, 0.01))
            mode = float(edges[np.argmax(hist)] + 0.005)
            patch = cand[np.abs(cand[:, 2] - mode) < SURF_BAND_M]
            if len(patch) < MIN_POINTS:
                out_runs.append({**res, "result": "no_surface", "points": int(len(patch))})
                continue
            h = float(np.median(patch[:, 2]))
            ax, other = int(np.argmax(np.abs(dirn))), 1 - int(np.argmax(np.abs(dirn)))
            sec = sk[(sk[:, 2] >= h - THICK_M) & (sk[:, 2] <= h)]
            if not len(sec):
                out_runs.append({**res, "result": "no_section", "surface_m": round(h, 4)})
                continue
            # MoGe gives the surface's height and size, not its place: ep01's stool seat reads 0.23 m from the vacuum
            # that leans on it. So the box is the patch's size, its near face on the object's section between the box's
            # bottom and top (along the topple direction's dominant axis), centred on the section across.
            size = np.clip(np.ptp(patch[:, :2], axis=0), MIN_SIZE_M, MAX_SIZE_M)
            lo, hi = np.zeros(3), np.zeros(3)
            lo[2], hi[2] = h - THICK_M, h
            if dirn[ax] > 0:
                lo[ax] = sec[:, ax].max()
                hi[ax] = lo[ax] + size[ax]
            else:
                hi[ax] = sec[:, ax].min()
                lo[ax] = hi[ax] - size[ax]
            mid, half = (sec[:, other].min() + sec[:, other].max()) / 2, max(size[other], np.ptp(sec[:, other])) / 2
            lo[other], hi[other] = mid - half, mid + half
            pen = float(box_inside(sk, lo, hi).max())
            gap = float(np.min(np.linalg.norm(np.maximum(np.maximum(lo - sk, sk - hi), 0), axis=1)))
            chk = {"surface_m": round(h, 4), "patch_points": int(len(patch)), "penetration_m": round(max(pen, 0.0), 4),
                   "gap_m": round(gap, 4), "lo": np.round(lo, 4).tolist(), "hi": np.round(hi, 4).tolist()}
            ok = pen <= PEN_M and gap <= GAP_M
            out_runs.append({**res, "result": "box" if ok else "refused", **chk})
            if ok:
                boxes.append((lo, hi))
        # merge boxes that overlap (one stool seen from several runs), then check each against the whole episode
        merged: list[list[np.ndarray]] = []
        for lo, hi in boxes:
            for mb in merged:
                if np.all(lo <= mb[1]) and np.all(hi >= mb[0]):
                    mb[0], mb[1] = np.minimum(mb[0], lo), np.maximum(mb[1], hi)
                    break
            else:
                merged.append([lo.copy(), hi.copy()])
        checks = []
        for lo, hi in merged:
            deep, at = 0.0, None
            for f in range(len(pos)):
                v = box_inside(R(f).apply(hull) + pos[f], lo, hi).max()
                if v > deep:
                    deep, at = float(v), f
            lean_pen = max(float(box_inside(R(rn["pose_frame"]).apply(surf) + pos[rn["pose_frame"]], lo, hi).max()) for rn in out_runs if rn["result"] == "box")
            ok = deep <= EPISODE_PEN_M and lean_pen <= PEN_M
            checks.append({"lo": np.round(lo, 4).tolist(), "hi": np.round(hi, 4).tolist(), "episode_max_hull_penetration_m": round(deep, 4),
                           "at_frame": at, "lean_runs_max_penetration_m": round(max(lean_pen, 0.0), 4), "written": bool(ok)})
        print(json.dumps({"episode": tag, "runs": out_runs, "boxes": checks}), flush=True)
        checks_ok = [c for c in checks if c["written"]]
        if dry or not checks_ok:
            if not dry and checks:
                rows[seq]["lean"] = {"runs": out_runs, "boxes": checks}
            continue
        txt = usda.read_text()
        assert txt.rstrip().endswith("}") and "support_lean_" not in txt, f"{usda.name}: unexpected or already has lean boxes"
        body = ""
        for i, c in enumerate(checks_ok):
            lo, hi = np.array(c["lo"]), np.array(c["hi"])
            ctr, size = (lo + hi) / 2, hi - lo
            body += (f'    def Cube "support_lean_{i}" (\n        prepend apiSchemas = ["PhysicsCollisionAPI"]\n    )\n    {{\n'
                     f'        double size = 1\n'
                     f'        double3 xformOp:translate = ({ctr[0]:.4f}, {ctr[1]:.4f}, {ctr[2]:.4f})\n'
                     f'        double3 xformOp:scale = ({size[0]:.4f}, {size[1]:.4f}, {size[2]:.4f})\n'
                     f'        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]\n    }}\n')
        new = txt.rstrip()[:-1] + body + "}\n"
        usda.write_text(new)
        assert usda.read_text() == new and new.count("support_lean_") == len(checks_ok)
        rows[seq]["lean"] = {"runs": out_runs, "boxes": checks}
        written += 1
    if not dry:
        rep["lean_support"] = {"script": "t3_lean_support.py", "episodes_with_boxes": written,
                               "thresholds": {k: v for k, v in globals().items() if re.fullmatch(r"[A-Z_]+", k) and isinstance(v, (int, float))}}
        rep_path.write_text(json.dumps(rep, indent=1))
    print(f"LEAN_SUPPORT_DONE episodes with boxes: {written}{' (dry)' if dry else ''}", flush=True)


if __name__ == "__main__":
    main()
