"""Decision units and candidate turns for the silhouette orientation choice, t3fix part A (Tier 3 inputs only).

Plan: agent-doc/plan-t3fix-2026-10-27.md on track2/p1-training, version 2, section 1 A2-A5 and criterion G0.

A unit is a run of frames that gets one decision. Every run of unheld frames is one unit, whole: an untouched object
must not change its orientation, so a rest that a jump splits is judged once over all its frames. A held run is split
at single-frame turns above JUMP_DEG, because a flip of the reconstruction inside a grasp starts or ends there.
A unit with fewer than MIN_EVIDENCE frames that have mask evidence is not judged and keeps its orientation.

Candidates turn the object about its centre of mass in its own frame (body-frame turn g, so the pose becomes
T @ about_com(g, com_b)): 180 deg about each principal axis of inertia, plus STEP_DEG steps about a near-symmetry
axis (two moments within NEAR_SYM_REL of each other, the third apart). A turn that moves no surface point by more than
SYM_M is a symmetry of the shape; the silhouette cannot see it, so it is not a candidate here (part B handles it).
The null control uses only turns the silhouette cannot see (the symmetry group, a turn about the continuous axis, or
NULL_DEG about the axis of least inertia); any accept among them is a false accept caused by mask noise.
"""

import numpy as np
from scipy.spatial.transform import Rotation

FPS = 30
JUMP_DEG = float(np.degrees(4 * np.pi) / FPS)  # gate/t3_dynamics_check.py OMEGA_MAX per frame: 24 deg
MIN_EVIDENCE = 10
NEAR_SYM_REL = 0.10
STEP_DEG = 30
NULL_DEG = 5.0
MIN_GAIN_LADDER = (0.05, 0.08, 0.10, 0.15)


def runs(mask) -> list[tuple[int, int]]:
    """[start, end) of each run of True."""
    m = np.r_[False, np.asarray(mask, bool), False]
    d = np.flatnonzero(m[1:] != m[:-1])
    return list(zip(d[::2].tolist(), d[1::2].tolist()))


def turn_deg(R: np.ndarray) -> np.ndarray:
    """Angle between frame t-1 and frame t (deg); 0 for frame 0. R is (n, 3, 3)."""
    rel = np.einsum("nji,njk->nik", R[:-1], R[1:])
    ang = np.degrees(np.arccos(np.clip((np.trace(rel, axis1=1, axis2=2) - 1) / 2, -1, 1)))
    return np.r_[0.0, ang]


def units(R: np.ndarray, held: np.ndarray, jump_deg: float = JUMP_DEG) -> list[dict]:
    """Decision units in frame order: {"start", "end", "held"}; together they cover every frame once."""
    held = np.asarray(held, bool)
    if len(held) != len(R):
        raise ValueError(f"{len(held)} held flags for {len(R)} frames")
    step = turn_deg(R)
    out = []
    for a, b in runs(~held):
        out.append({"start": a, "end": b, "held": False})
    for a, b in runs(held):
        cuts = [a] + [t for t in range(a + 1, b) if step[t] > jump_deg] + [b]
        out.extend({"start": s, "end": e, "held": True} for s, e in zip(cuts[:-1], cuts[1:]))
    return sorted(out, key=lambda u: u["start"])


def rot(axis, deg: float) -> np.ndarray:
    axis = np.asarray(axis, np.float64)
    return Rotation.from_rotvec(axis / np.linalg.norm(axis) * np.deg2rad(deg)).as_matrix()


def about_com(g: np.ndarray, com_b) -> np.ndarray:
    """4x4 body-frame transform that turns by g about the body-frame point com_b."""
    com_b = np.asarray(com_b, np.float64)
    G = np.eye(4)
    G[:3, :3] = g
    G[:3, 3] = com_b - g @ com_b
    return G


def turn_poses(T: np.ndarray, g: np.ndarray, com_b) -> np.ndarray:
    """T (n, 4, 4) object poses, each turned by g in its own frame about com_b. The centre of mass stays put."""
    return T @ about_com(g, com_b)


def principal(inertia) -> tuple[np.ndarray, np.ndarray]:
    """(moments ascending, axes as columns) of a 3x3 inertia tensor."""
    w, v = np.linalg.eigh(np.asarray(inertia, np.float64))
    return w, v


def near_sym_axis(moments, axes, rel: float = NEAR_SYM_REL):
    """The principal axis whose two partners have moments within rel of each other while it stands apart, else None."""
    w = np.asarray(moments, np.float64)
    hits = []
    for k in range(3):
        i, j = [x for x in range(3) if x != k]
        close = abs(w[i] - w[j]) <= rel * max(w[i], w[j])
        apart = min(abs(w[k] - w[i]), abs(w[k] - w[j])) > rel * max(w[k], w[i], w[j])
        if close and apart:
            hits.append(k)
    return axes[:, hits[0]] if len(hits) == 1 else None


def _same(a: np.ndarray, b: np.ndarray, tol_deg: float = 1.0) -> bool:
    return float(np.degrees(np.arccos(np.clip((np.trace(a.T @ b) - 1) / 2, -1, 1)))) <= tol_deg


def candidates(moments, axes, shift, sym_m: float, group=(), cont_axis=None) -> dict[str, np.ndarray]:
    """Body-frame turns the silhouette may see. shift(g) is the largest surface-point move of turn g (m)."""
    out = {}
    for k in range(3):
        out[f"flip_a{k}"] = rot(axes[:, k], 180)
    ax = near_sym_axis(moments, axes)
    if ax is not None and (cont_axis is None or abs(float(np.dot(ax, cont_axis))) < 0.99):
        for d in range(STEP_DEG, 360, STEP_DEG):
            out[f"turn{d:03d}"] = rot(ax, d)
    keep = {}
    for name, g in out.items():
        if any(_same(g, h) for h in group):
            continue
        if shift(g) <= sym_m:
            continue
        if any(_same(g, h) for h in keep.values()):
            continue
        keep[name] = g
    return keep


def null_candidates(axes, group=(), cont_axis=None) -> dict[str, np.ndarray]:
    """Turns the silhouette cannot see: the non-identity symmetry rotations, a 90 deg turn about the continuous axis,
    and NULL_DEG about the axis of least inertia (the first column of axes)."""
    out = {f"null_g{i}": np.asarray(g, np.float64) for i, g in enumerate(group) if i > 0}
    if cont_axis is not None:
        out["null_cont090"] = rot(cont_axis, 90)
    out[f"null_{NULL_DEG:g}deg"] = rot(axes[:, 0], NULL_DEG)
    return out


def unit_scores(scores: dict[str, np.ndarray], unit: dict) -> dict[str, list[float]]:
    """Per-candidate scores on the unit's frames where every candidate has a finite score."""
    a, b = unit["start"], unit["end"]
    stack = np.stack([np.asarray(v, np.float64)[a:b] for v in scores.values()])
    ok = np.isfinite(stack).all(0)
    return {name: stack[i][ok].tolist() for i, name in enumerate(scores)}


def decide(scores: dict[str, np.ndarray], unit_list: list[dict], choose, min_gain: float) -> list[dict]:
    """One row per unit: the unit, the evidence count and choose(...)'s result, or reason "evidence" when too few."""
    rows = []
    for u in unit_list:
        s = unit_scores(scores, u)
        n = len(s["current"])
        if n < MIN_EVIDENCE:
            rows.append({**u, "evidence": n, "decision": "refuse", "name": None, "reason": "evidence", "median": {}})
            continue
        res = choose(s, min_gain=min_gain)
        rows.append({**u, "evidence": n, **{k: res[k] for k in ("decision", "name", "reason")},
                     "median": {k: float(v) for k, v in res["median"].items()}})
    return rows
