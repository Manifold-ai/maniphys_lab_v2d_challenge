"""Re-solve the hands for a swapped asset, so the reference still grasps the new object.

What the policy is held to (FlashCHORD ReconBody, G1 FlashSAC recipe): 29 body joints, pelvis, both palm poses
(episode ends when a palm is 0.15 m off) and the object; the 14 Dex3 finger joints are not imitated, they are only
rewarded through force closure on frames the reference labels as contact. The reference palm poses and contact
labels both come out of the official soma_to_g1.py: IK on the SOMA joints (it never looks at the object), then a
side is in contact when its palm link or a SOMA fingertip joint is within 0.02 m of an object mesh vertex. So a
swapped asset needs a human whose hands meet the new surface; fingers are left to the policy.

This step moves each hand rigidly, in the object's local frame, per grasp segment:
  1. SOMA forward on the episode's soma_params.npz (OpenCV camera frame -> SOMA frame, as t3_convert_ep.py);
  2. per side, contact frames under the official mesh (Hand joint + five fingertip joints within CONTACT_M),
     merged into segments;
  3. per segment, one translation t of the hand (vertices skinned to the hand and finger joints) found by grid
     search: hand vertices near the official surface keep their distance to the new surface, contact points stay
     within CONTACT_M, palm vertices do not enter the new mesh's collision hulls (CoACD, as hull_check.py), and t
     stays small;
  4. t blends in and out over BLEND frames around each segment.
Screen first: a candidate whose surface is farther than MAX_OFFSET_M (median over contact frames) from a hand's
contact points has no grasp site there and is skipped. Gate per candidate and side: contact kept on >= KEEP_SHARE of the original contact frames, palm penetration beyond
the official baseline on <= PEN_SHARE of them, |t| <= MAX_OFFSET_M (a reach heuristic, not a measured limit).
Rotation of the hand is not solved yet. The arm is not re-solved here: the edited hand joints are the input of the
next step (refit SOMA, then the official retarget with the new mesh).

The official mesh runs through the same solver as a control: it must come out with t = 0 and pass.

Two steps, CPU only:
    forward  (v2d_cari4d image, has soma):   python palm_resolve.py forward <convert dir> <soma assets> <out dir>
    solve    (augment venv, has coacd):      python palm_resolve.py solve <convert dir> <pilot dir> <out dir>
forward writes hand_forward.npz (hand and palm vertices, joints, per side); solve reads it. The pilot dir holds
official_local.glb and the placed candidates (swap_pilot.py).
"""

import json
import os
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import ConvexHull, cKDTree

F_CV_TO_SOMA = np.diag([1.0, -1.0, -1.0])
CONTACT_M = 0.02  # soma_to_g1.py --contact-threshold default
NEAR_M = 0.015
MERGE_GAP = 5
MIN_RUN = 5
BLEND = 10
FRAMES_PER_SEG = 12
COARSE = (0.10, 0.02)  # half range, step
FINE = (0.02, 0.005)
KEEP_SHARE = 0.9
PEN_VERTS = 10
PEN_SHARE = 0.1
MAX_OFFSET_M = 0.10
SURFACE_SAMPLES = 30000
HULL_THRESHOLD = 0.05
CHUNK = 64
SIDES = ("Left", "Right")
TIPS = ("ThumbEnd", "IndexEnd", "MiddleEnd", "RingEnd", "PinkyEnd")


def forward(conv: Path, assets: Path, out: Path) -> None:
    import torch
    from soma import SOMALayer
    from soma.units import Unit

    sp = np.load(conv / "soma_params.npz", allow_pickle=True)
    n = len(sp["poses"])
    layer = SOMALayer(data_root=str(assets), identity_model_type="mhr", device="cpu", output_unit=Unit.METERS,
                      enable_procedural_transforms=False)
    verts, joints = [], []
    for s in range(0, n, CHUNK):
        sl = slice(s, min(n, s + CHUNK))
        with torch.no_grad():
            got = layer(torch.tensor(sp["poses"][sl], dtype=torch.float32),
                        torch.tensor(sp["identity_coeffs"][sl], dtype=torch.float32),
                        scale_params=torch.tensor(sp["scale_params"][sl], dtype=torch.float32),
                        transl=torch.tensor(sp["transl"][sl], dtype=torch.float32), apply_correctives=False,
                        kwargs={"bone_length_flexibles": torch.tensor(sp["bone_length_flexibles"][sl], dtype=torch.float32)})
        verts.append(got["vertices"].numpy())
        joints.append(got["joints"].numpy())
    verts, joints = np.concatenate(verts), np.concatenate(joints)
    weights = np.asarray(layer.skinning_weights, np.float64)
    wnames = [str(x) for x in layer._public_joint_names]
    jnames = [str(x) for x in sp["joint_names"]]
    saved = {"joints": joints.astype(np.float32), "joint_names": np.array(jnames)}
    for side in SIDES:
        hand_w = weights[:, [k for k, nm in enumerate(wnames) if nm.startswith(f"{side}Hand")]].sum(axis=1)
        hand = np.nonzero(hand_w >= 0.5)[0]
        palm = np.nonzero(weights[:, wnames.index(f"{side}Hand")] >= 0.5)[0]
        saved |= {f"{side}_hand_idx": hand, f"{side}_palm_idx": palm, f"{side}_hand_verts": verts[:, hand].astype(np.float32),
                  f"{side}_palm_verts": verts[:, palm].astype(np.float32), f"{side}_hand_weight": hand_w.astype(np.float32)}
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / "hand_forward.npz", **saved)
    print(json.dumps({"frames": len(verts), **{f"{s}_hand": int(len(saved[f'{s}_hand_idx'])) for s in SIDES},
                      **{f"{s}_palm": int(len(saved[f'{s}_palm_idx'])) for s in SIDES}}))


def load_mesh(path: Path) -> trimesh.Trimesh:
    mesh = trimesh.load(path, force="mesh", process=False)
    return trimesh.Trimesh(np.asarray(mesh.vertices, np.float64), np.asarray(mesh.faces), process=False)


def hulls(mesh: trimesh.Trimesh, cache: Path) -> list[np.ndarray]:
    if cache.exists():
        z = np.load(cache)
        return [z[k] for k in sorted(z.files, key=int)]
    import coacd

    parts = coacd.run_coacd(coacd.Mesh(mesh.vertices, mesh.faces), threshold=HULL_THRESHOLD)
    eqs = [ConvexHull(np.asarray(v)).equations for v, _ in parts if len(v) >= 4]
    np.savez_compressed(cache, **{str(i): e for i, e in enumerate(eqs)})
    return eqs


def inside(eqs: list[np.ndarray], pts: np.ndarray) -> np.ndarray:
    hit = np.zeros(pts.shape[:-1], bool)
    for e in eqs:
        hit |= np.all(pts @ e[:, :3].T + e[:, 3] <= 1e-4, axis=-1)
    return hit


def segments(active: np.ndarray) -> list[tuple[int, int]]:
    runs, start = [], None
    for i, a in enumerate(np.append(active, False)):
        if a and start is None:
            start = i
        elif not a and start is not None:
            runs.append([start, i])
            start = None
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] <= MERGE_GAP:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    return [(a, b) for a, b in merged if b - a >= MIN_RUN]


class Surface:
    def __init__(self, mesh: trimesh.Trimesh, cache: Path):
        np.random.seed(0)
        self.tree = cKDTree(mesh.sample(SURFACE_SAMPLES))
        self.hulls = hulls(mesh, cache)

    def dist(self, pts: np.ndarray) -> np.ndarray:
        return self.tree.query(pts.reshape(-1, 3))[0].reshape(pts.shape[:-1])


def solve_segment(new: Surface, hand: np.ndarray, d_old: np.ndarray, near: np.ndarray, tips: np.ndarray,
                  palm: np.ndarray, palm_in_old: np.ndarray, was_active: np.ndarray) -> tuple[np.ndarray, dict, dict]:
    """hand (f,h,3), d_old (f,h), near (f,h), tips (f,6,3), palm (f,p,3), palm_in_old (f,), was_active (f,): object-local.

    The distance and contact terms only count frames that were in contact under the official mesh: a segment merges
    contact runs across short gaps, and pulling the hand onto the surface in those gaps would edit the motion where
    the original had no contact (the official-mesh control caught exactly this: 2 cm for the left hand)."""
    near = near & was_active[:, None]
    def terms(t: np.ndarray) -> dict:
        c = {"dist": 0.0, "contact": 0.0}
        if near.any():
            c["dist"] = float(np.mean((new.dist(hand[near] + t) - d_old[near]) ** 2)) / 0.01**2
        if was_active.any():
            c["contact"] = 5.0 * float(np.mean(new.dist(tips[was_active] + t).min(axis=1) >= CONTACT_M))
        extra = inside(new.hulls, palm + t).sum(axis=1) - palm_in_old
        c["pen"] = 10.0 * float(np.mean(np.maximum(extra, 0) / palm.shape[1]))
        c["reg"] = 0.1 * float(t @ t) / 0.05**2
        return c
    zero = terms(np.zeros(3))
    best_t, best_e = np.zeros(3), sum(zero.values())
    centre = np.zeros(3)
    for half, step in (COARSE, FINE):
        axis = np.arange(-half, half + 1e-9, step)
        for dx in axis:
            for dy in axis:
                for dz in axis:
                    t = centre + np.array([dx, dy, dz])
                    e = sum(terms(t).values())
                    if e < best_e:
                        best_t, best_e = t, e
        centre = best_t
    return best_t, {k: round(v, 4) for k, v in zero.items()}, {k: round(v, 4) for k, v in terms(best_t).items()}


def blend_weights(n: int, a: int, b: int) -> np.ndarray:
    w = np.zeros(n)
    w[a:b] = 1.0
    for k in range(1, BLEND + 1):
        s = 0.5 - 0.5 * np.cos(np.pi * (BLEND - k + 1) / (BLEND + 1))  # smooth ramp, 1 at the segment edge
        if a - k >= 0:
            w[a - k] = max(w[a - k], s)
        if b - 1 + k < n:
            w[b - 1 + k] = max(w[b - 1 + k], s)
    return w


def solve(conv: Path, pilot: Path, out: Path) -> None:
    (out / "hulls").mkdir(parents=True, exist_ok=True)
    fw = np.load(out / "hand_forward.npz")
    joints = fw["joints"].astype(np.float64)
    jnames = [str(x) for x in fw["joint_names"]]
    n = len(joints)
    cam = np.load(conv / "object_cam.npz")["T_cam_glb"]
    rot = np.einsum("ij,njk->nik", F_CV_TO_SOMA, cam[:, :3, :3])
    trans = cam[:, :3, 3] @ F_CV_TO_SOMA.T
    to_local = lambda p, i: (p - trans[i]) @ rot[i]  # noqa: E731 - SOMA frame -> object local, frame i

    tips_idx = {s: [jnames.index(f"{s}Hand")] + [jnames.index(f"{s}Hand{t}") for t in TIPS] for s in SIDES}

    official = load_mesh(pilot / "official_local.glb")
    off = Surface(official, out / "hulls" / "official.npz")
    local_hand = {s: np.stack([to_local(fw[f"{s}_hand_verts"][i].astype(np.float64), i) for i in range(n)]) for s in SIDES}
    local_palm = {s: np.stack([to_local(fw[f"{s}_palm_verts"][i].astype(np.float64), i) for i in range(n)]) for s in SIDES}
    local_tips = {s: np.stack([to_local(joints[i, tips_idx[s]], i) for i in range(n)]) for s in SIDES}
    active = {s: off.dist(local_tips[s]).min(axis=1) < CONTACT_M for s in SIDES}
    segs = {s: segments(active[s]) for s in SIDES}
    d_old = {s: off.dist(local_hand[s]) for s in SIDES}
    palm_in_old = {s: inside(off.hulls, local_palm[s]).sum(axis=1) for s in SIDES}
    print(json.dumps({"frames": n, "contact_frames": {s: int(active[s].sum()) for s in SIDES}, "segments": segs}), flush=True)

    cands = [("official", pilot / "official_local.glb")] + [(p.stem, p) for p in sorted(pilot.glob("*_bbox.glb")) + sorted(pilot.glob("*_height.glb"))]
    only = [c for c in os.environ.get("PALM_CANDIDATES", "").split(",") if c]
    if only:
        cands = [c for c in cands if c[0] == "official" or any(o in c[0] for o in only)]
    results = (out / "results.jsonl").open("a")
    rows = []
    for name, path in cands:
        if name != "official":
            # screen before the expensive part (CoACD + grid search): a hand whose contact points sit farther than the
            # largest allowed offset from the new surface has no grasp site there; moving it is a different grasp
            mesh = load_mesh(path)
            np.random.seed(0)
            tree = cKDTree(mesh.sample(SURFACE_SAMPLES))
            gap = {s: float(np.median(tree.query(local_tips[s][active[s]].reshape(-1, 3))[0].reshape(-1, len(TIPS) + 1).min(axis=1)))
                   for s in SIDES if active[s].any()}
            if max(gap.values(), default=0.0) > MAX_OFFSET_M:
                row = {"candidate": name, "pass": False, "no_grasp_site": {s: round(g * 100, 1) for s, g in gap.items()}}
                rows.append(row)
                results.write(json.dumps(row) + "\n")
                results.flush()
                continue
        new = off if name == "official" else Surface(mesh, out / "hulls" / f"{name}.npz")
        row = {"candidate": name, "sides": {}}
        offsets = {}
        for s in SIDES:
            off_local = np.zeros((n, 3))
            wsum = np.zeros(n)
            seg_rows = []
            for a, b in segs[s]:
                pick = np.linspace(a, b - 1, min(FRAMES_PER_SEG, b - a)).round().astype(int)
                t, e0, e = solve_segment(new, local_hand[s][pick], d_old[s][pick], d_old[s][pick] < NEAR_M,
                                         local_tips[s][pick], local_palm[s][pick], palm_in_old[s][pick], active[s][pick])
                w = blend_weights(n, a, b)
                off_local += w[:, None] * t
                wsum += w
                seg_rows.append({"frames": [a, b], "t_cm": [round(float(x) * 100, 2) for x in t],
                                 "norm_cm": round(float(np.linalg.norm(t)) * 100, 2), "terms_at_zero": e0, "terms": e,
                                 "at_search_edge": bool(np.abs(t).max() >= COARSE[0] + FINE[0] - 1e-6)})
            off_local /= np.maximum(wsum, 1.0)[:, None]
            offsets[s] = off_local
            act = np.nonzero(active[s])[0]
            if len(act):
                kept = new.dist(local_tips[s][act] + off_local[act, None]).min(axis=1) < CONTACT_M
                extra = inside(new.hulls, local_palm[s][act] + off_local[act, None]).sum(axis=1) - palm_in_old[s][act]
                raw_kept = new.dist(local_tips[s][act]).min(axis=1) < CONTACT_M
                raw_extra = inside(new.hulls, local_palm[s][act]).sum(axis=1) - palm_in_old[s][act]
                max_off = max([r["norm_cm"] for r in seg_rows], default=0.0) / 100
                ok = (kept.mean() >= KEEP_SHARE and (extra > PEN_VERTS).mean() <= PEN_SHARE and max_off <= MAX_OFFSET_M)
                row["sides"][s] = {"contact_frames": int(len(act)), "segments": seg_rows,
                                   "kept_share": round(float(kept.mean()), 3), "palm_pen_share": round(float((extra > PEN_VERTS).mean()), 3),
                                   "palm_extra_p90": int(np.percentile(extra, 90)),
                                   "before": {"kept_share": round(float(raw_kept.mean()), 3),
                                              "palm_pen_share": round(float((raw_extra > PEN_VERTS).mean()), 3)},
                                   "ok": bool(ok)}
        row["pass"] = all(v["ok"] for v in row["sides"].values()) and bool(row["sides"])
        rows.append(row)
        np.savez_compressed(out / f"offsets_{name}.npz", **{f"{s}_local": offsets[s] for s in SIDES},
                            **{f"{s}_world_soma": np.einsum("nij,nj->ni", rot, offsets[s]) for s in SIDES})
        results.write(json.dumps(row) + "\n")
        results.flush()
    report = {"convert_dir": str(conv), "pilot_dir": str(pilot), "frames": n, "segments": segs,
              "gate": {"keep_share": KEEP_SHARE, "pen_verts": PEN_VERTS, "pen_share": PEN_SHARE, "max_offset_m": MAX_OFFSET_M},
              "candidates": rows}
    (out / "palm_report.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "forward":
        forward(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
    elif sys.argv[1] == "solve":
        solve(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
    else:
        sys.exit(__doc__)
