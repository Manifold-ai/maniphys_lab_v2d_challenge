"""Asset-swap pilot: can a public replacement asset take the place of an episode's object without losing contact?

For one episode, every candidate asset is placed in the official mesh's local frame so that the episode's object
trajectory applies to it unchanged:
  - up: the object's up axis comes from its frame-0 pose and the released ground plane (world up in the camera frame);
    glTF candidates are +Y up;
  - scale: uniform, matching the official mesh's height (and, as a second variant, its full bounding box);
  - yaw: candidate footprint axes mapped onto the official footprint axes (PCA); of the proper rotations left, the one
    closest to the official mesh (chamfer) is kept;
  - placement: footprint centre on the official one, bottom on the official bottom (so resting contact is kept).
Then, on the frames where the reconstructed human touches the official mesh (nearest distance below CONTACT_M), it
measures two things against the candidate:
  - contact: is the same human within KEEP_M of the candidate surface?
  - penetration: how many human vertices lie inside the candidate's volume (filled voxels at PITCH_M). The official
    mesh gets the same count as a baseline, because reconstruction error alone pushes a few vertices inside. Nearest
    distance alone cannot see this: an oversized box swallows the hands and still reports them "close to the surface".
A candidate passes if it keeps contact on at least KEEP_SHARE of the contact frames and adds more than PEN_VERTS
penetrating vertices over the baseline on at most PEN_SHARE of them. Voxel filling needs a closed surface; an open
candidate under-reports penetration, so the report also says whether the candidate is watertight.

Inputs are Tier 3 products only: our CARI4D reconstruction (decode outputs) and the Tier 3 input directory.
Runs in the v2d_cari4d image (torch, trimesh, scipy), CPU.

    python swap_pilot.py <convert dir of the episode> <official mesh .glb> <ground_plane .json> <candidates dir> <group> <out dir>
"""

import json
import sys
from pathlib import Path

import numpy as np
import torch
import trimesh
from scipy.spatial import cKDTree

CONTACT_M = 0.015
KEEP_M = 0.02
PITCH_M = 0.01
PEN_VERTS = 50
KEEP_SHARE = 0.9
PEN_SHARE = 0.1
SURFACE_SAMPLES = 20000
FRAME_STRIDE = 3


def load_mesh(path: Path) -> trimesh.Trimesh:
    scene = trimesh.load(path, force="scene", process=False)
    mesh = scene.to_geometry() if hasattr(scene, "to_geometry") else scene.dump(concatenate=True)
    return trimesh.Trimesh(vertices=np.asarray(mesh.vertices, np.float64), faces=np.asarray(mesh.faces), process=False)


def frame_from_up(up: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Rows = (a1, a2, up): a1/a2 are the principal axes of the footprint (points projected on the plane normal to up)."""
    up = up / np.linalg.norm(up)
    helper = np.array([1.0, 0.0, 0.0]) if abs(up[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    e1 = np.cross(up, helper)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(up, e1)
    flat = (points - points.mean(0)) @ np.stack([e1, e2]).T
    _, vecs = np.linalg.eigh(np.cov(flat.T))
    a1 = vecs[0, 1] * e1 + vecs[1, 1] * e2  # largest principal direction
    a1 /= np.linalg.norm(a1)
    a2 = np.cross(up, a1)
    return np.stack([a1, a2, up])


def extents_in(frame: np.ndarray, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    local = points @ frame.T
    return local.min(0), local.max(0)


def inside_counts(mesh_local: trimesh.Trimesh, human: np.ndarray, obj: np.ndarray, frames: list[int]) -> np.ndarray:
    """Per contact frame: human vertices inside the mesh volume (mesh in object-local coordinates)."""
    grid = mesh_local.voxelized(PITCH_M).fill()
    counts = []
    for i in frames:
        local = (human[i] - obj[i, :3, 3]) @ obj[i, :3, :3]  # camera -> object-local
        lo, hi = mesh_local.bounds
        near = local[np.all((local > lo - PITCH_M) & (local < hi + PITCH_M), axis=1)]
        counts.append(int(grid.is_filled(near).sum()) if len(near) else 0)
    return np.asarray(counts)


def chamfer(a: np.ndarray, b: np.ndarray) -> float:
    return float((cKDTree(b).query(a)[0].mean() + cKDTree(a).query(b)[0].mean()) / 2)


def place(cand: trimesh.Trimesh, off_frame: np.ndarray, off_lo: np.ndarray, off_hi: np.ndarray, anisotropic: bool,
          off_samples: np.ndarray) -> tuple[np.ndarray, dict]:
    """Candidate vertices expressed in the official mesh's local frame."""
    cv = np.asarray(cand.vertices)
    c_frame = frame_from_up(np.array([0.0, 1.0, 0.0]), cv)
    c_lo, c_hi = extents_in(c_frame, cv)
    c_ext, o_ext = c_hi - c_lo, off_hi - off_lo
    scale = o_ext / np.maximum(c_ext, 1e-9) if anisotropic else np.full(3, o_ext[2] / max(c_ext[2], 1e-9))
    best = None
    for sx, sy in ((1, 1), (-1, -1)):  # proper rotations with up kept: a1 -> +-a1 and a2 -> +-a2 together
        flip = np.diag([sx, sy, 1.0])
        local = (cv @ c_frame.T - (c_lo + c_hi) / 2) @ flip  # candidate in its own (a1, a2, up) coords, centred
        local = local * scale
        local[:, 2] += -local[:, 2].min() + off_lo[2]  # bottom on the official bottom
        centre = (off_lo[:2] + off_hi[:2]) / 2
        local[:, :2] += centre - (local[:, :2].min(0) + local[:, :2].max(0)) / 2
        verts = local @ off_frame  # back from (a1, a2, up) coords to the official mesh's local frame
        samples = trimesh.Trimesh(verts, cand.faces, process=False).sample(SURFACE_SAMPLES // 4)
        score = chamfer(samples, off_samples[:: 4])
        if best is None or score < best[0]:
            best = (score, verts)
    footprint_ratio = (c_ext[:2] * scale[:2]) / np.maximum(o_ext[:2], 1e-9)
    return best[1], {"scale": [round(float(s), 4) for s in scale], "chamfer_to_official_cm": round(best[0] * 100, 2),
                     "footprint_ratio": [round(float(r), 3) for r in footprint_ratio]}


def main() -> None:
    conv, off_path, gp_path, cand_dir, group, out = (Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]),
                                                       Path(sys.argv[4]), sys.argv[5], Path(sys.argv[6]))
    out.mkdir(parents=True, exist_ok=True)
    obj = np.load(conv / "object_cam.npz")["T_cam_glb"]
    human = torch.load(conv / "mhr_mesh.pt", map_location="cpu", weights_only=True)["pred_vertices"].numpy()
    plane = np.asarray(json.loads(gp_path.read_text())["plane"], np.float64)
    n = plane[:3] / np.linalg.norm(plane[:3])
    up_cam = n if plane[3] > 0 else -n  # camera sits above the floor, so the normal toward the camera is world up

    official = load_mesh(off_path)
    off_v = np.asarray(official.vertices)
    up_local = obj[0, :3, :3].T @ up_cam
    off_frame = frame_from_up(up_local, off_v)
    off_lo, off_hi = extents_in(off_frame, off_v)
    off_samples = official.sample(SURFACE_SAMPLES)

    frames = list(range(0, len(obj), FRAME_STRIDE))
    def posed(samples: np.ndarray, i: int) -> np.ndarray:
        return samples @ obj[i, :3, :3].T + obj[i, :3, 3]
    contact = []
    for i in frames:
        d = cKDTree(posed(off_samples, i)).query(human[i])[0].min()
        if d < CONTACT_M:
            contact.append(i)

    base_inside = inside_counts(official, human, obj, contact) if contact else np.array([])
    # contact-frame human vertices in object-local coordinates, for collision-hull penetration (hull_check.py)
    lo, hi = official.bounds
    pts, idx = [], []
    for i in contact:
        local = (human[i] - obj[i, :3, 3]) @ obj[i, :3, :3]
        near = local[np.all((local > lo - 0.3) & (local < hi + 0.3), axis=1)]
        pts.append(near.astype(np.float32))
        idx.append(np.full(len(near), i, np.int32))
    np.savez_compressed(out / "contact_human_local.npz", points=np.concatenate(pts) if pts else np.zeros((0, 3), np.float32),
                        frame=np.concatenate(idx) if idx else np.zeros(0, np.int32))
    official.export(out / "official_local.glb")
    manifest = json.loads((cand_dir / "manifest.json").read_text())[group]
    rows = []
    for item in manifest:
        if "file" not in item:
            continue
        cand = load_mesh(cand_dir / item["file"])
        for aniso in (False, True):
            verts, info = place(cand, off_frame, off_lo, off_hi, aniso, off_samples)
            placed = trimesh.Trimesh(verts, cand.faces, process=False)
            s = placed.sample(SURFACE_SAMPLES)
            dists = np.array([cKDTree(posed(s, i)).query(human[i])[0].min() for i in contact]) if contact else np.array([])
            extra = inside_counts(placed, human, obj, contact) - base_inside if contact else np.array([])
            keep = float((dists < KEEP_M).mean()) if len(dists) else 0.0
            pen = float((extra > PEN_VERTS).mean()) if len(extra) else 0.0
            row = {"uid": item["uid"], "name": item["name"], "licence": item["licence"], "author": item["author"],
                   "variant": "bbox" if aniso else "height", **info, "watertight": bool(placed.is_watertight),
                   "contact_frames": len(contact), "kept_contact_share": round(keep, 3),
                   "human_to_candidate_cm_p50": round(float(np.median(dists)) * 100, 2) if len(dists) else None,
                   "penetrating_share": round(pen, 3), "extra_inside_vertices_p50": int(np.median(extra)) if len(extra) else None,
                   "pass": keep >= KEEP_SHARE and pen <= PEN_SHARE}
            rows.append(row)
            placed.export(out / f"{group}_{item['uid']}_{row['variant']}.glb")
    rows.sort(key=lambda r: (not r["pass"], r["penetrating_share"], -r["kept_contact_share"], r["chamfer_to_official_cm"]))
    report = {"episode_convert_dir": str(conv), "official_extents_m": [round(float(x), 3) for x in off_hi - off_lo],
              "official_watertight": bool(official.is_watertight),
              "baseline_inside_vertices_p50": int(np.median(base_inside)) if len(base_inside) else None,
              "frames_checked": len(frames), "contact_frames": len(contact), "candidates": rows}
    (out / "swap_report.json").write_text(json.dumps(report, indent=1))
    print(json.dumps({k: v for k, v in report.items() if k != "candidates"}))
    for r in rows:
        print(f"{'PASS' if r['pass'] else 'fail'} {r['variant']:6s} keep={r['kept_contact_share']} pen={r['penetrating_share']} "
              f"extra_in={r['extra_inside_vertices_p50']} wt={r['watertight']} chamfer={r['chamfer_to_official_cm']}cm "
              f"foot={r['footprint_ratio']} {r['licence']} {r['name']!r}")


if __name__ == "__main__":
    main()
