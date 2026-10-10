"""Room walls in each exo camera's world frame, from MoGe-2 on a people-free background plate (dev probe, Tier 3 inputs).

The floor marks are nearly symmetric about the capture area, so they cannot tell a camera that faces the main one from
one that looks the same way. Walls can: a top-down map of what stands 0.5-2.2 m above the floor shows which part of the
room each camera sees. Steps:

  plates  (host venv)   per-pixel median of N_FRAMES RGB frames -> <out>/plate_<ep>.png
  moge    (v2d_cari4d, CPU)   MoGe-2 point map of each plate -> <out>/moge_<ep>.npz (points, mask, normals if any)
  walls   (host venv)   MoGe's own floor (RANSAC on points with near-vertical normals in the lower image) is turned onto
                        the released plane's normal about the camera and scaled so the camera height matches the released
                        plane's offset; points WALL_LO_M..WALL_HI_M above the floor are binned on the floor plane at
                        GRID_M -> <out>/walls_<ep>.png and .npz, in the same plane coordinates as t3_floor_register.py.
    python t3_walls.py plates <tier3 root> <out> <ep>...
    python t3_walls.py moge <out> <ep>...
    python t3_walls.py walls <tier3 root> <out> <ep>...
"""

import json
import sys
from pathlib import Path

import numpy as np

N_FRAMES = 41
GRID_M = 0.05
HALF_EXTENT_M = 9.0
WALL_LO_M = 0.5
WALL_HI_M = 2.2
MAX_RANGE_M = 12.0


def meta_of(root: Path) -> dict:
    return {f"ep{m['episode_index']:02d}_{m['object']}": m for m in map(json.loads, (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines()) if m}


def plates(root: Path, out: Path, names: list[str]) -> None:
    import cv2

    out.mkdir(parents=True, exist_ok=True)
    meta = meta_of(root)
    for name in names:
        cap = cv2.VideoCapture(str(root / "input/videos" / f"episode_{meta[name]['episode_index']:06d}.mp4"))
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frames = []
        for i in np.linspace(0, n - 1, N_FRAMES).round().astype(int):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
            ok, f = cap.read()
            if ok:
                frames.append(f)
        cv2.imwrite(str(out / f"plate_{name}.png"), np.median(np.stack(frames), 0).astype(np.uint8))
        print(name, len(frames))


def moge(out: Path, names: list[str]) -> None:
    import torch
    from moge.model.v2 import MoGeModel
    from PIL import Image

    torch.set_num_threads(12)
    model = MoGeModel.from_pretrained("Ruicheng/moge-2-vitl-normal", revision="b135031bae30b5ac2ae141a0e68717795ce38340",
                                      local_files_only=True).eval()
    for name in names:
        rgb = np.asarray(Image.open(out / f"plate_{name}.png").convert("RGB"))
        image = torch.from_numpy(rgb).permute(2, 0, 1).float().div_(255.0)
        with torch.inference_mode():
            pred = model.infer(image, resolution_level=9, force_projection=True, apply_mask=True, use_fp16=False)
        arrays = {"points": pred["points"].float().numpy(), "mask": pred["mask"].numpy().astype(bool)}
        if "normal" in pred:
            arrays["normal"] = pred["normal"].float().numpy()
        np.savez_compressed(out / f"moge_{name}.npz", **arrays)
        print(name, {k: v.shape for k, v in arrays.items()}, flush=True)


def plane_basis(n: np.ndarray, d: float):
    k = np.linalg.norm(n)
    n, d = n / k, d / k
    if d < 0:
        n, d = -n, -d
    u = np.array([1.0, 0.0, 0.0]) - n[0] * n
    u /= np.linalg.norm(u)
    return n, d, -d * n, u, np.cross(n, u)


def rot_onto(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    v, c = np.cross(a, b), float(a @ b)
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + k + k @ k / (1 + c)


def walls(root: Path, out: Path, names: list[str]) -> None:
    import cv2

    meta = meta_of(root)
    gp = np.asarray(json.loads((root / "input" / meta[names[0]]["ground_plane"]).read_text())["plane"], np.float64)
    n_r, d_r, o, u, v = plane_basis(gp[:3], gp[3])
    rng = np.random.default_rng(0)
    for name in names:
        z = np.load(out / f"moge_{name}.npz")
        pts, mask = z["points"].astype(np.float64), z["mask"]
        h, w = mask.shape
        rows = np.arange(h)[:, None].repeat(w, 1)
        cand = pts[mask & (rows > h * 0.55)]
        if "normal" in z:
            nrm = z["normal"].astype(np.float64)[mask & (rows > h * 0.55)]
            cand = cand[np.abs(nrm @ np.array([0.0, -1.0, 0.0])) > 0.9]
        best = (0, None)
        for _ in range(500):  # RANSAC plane on the lower image
            s = cand[rng.choice(len(cand), 3, replace=False)]
            nn = np.cross(s[1] - s[0], s[2] - s[0])
            if np.linalg.norm(nn) < 1e-9:
                continue
            nn /= np.linalg.norm(nn)
            dd = -nn @ s[0]
            inl = int((np.abs(cand @ nn + dd) < 0.03).sum())
            if inl > best[0]:
                best = (inl, (nn, dd))
        nn, dd = best[1]
        if dd < 0:
            nn, dd = -nn, -dd
        r = rot_onto(nn, n_r)  # MoGe's floor normal onto the released one, about the camera
        s = d_r / dd  # camera height -> released offset
        world = (pts[mask] @ r.T) * s
        hgt = world @ n_r + d_r
        far = np.linalg.norm(world, axis=1) < MAX_RANGE_M
        sel = (hgt > WALL_LO_M) & (hgt < WALL_HI_M) & far
        a, b = (world[sel] - o) @ u, (world[sel] - o) @ v
        m = int(round(2 * HALF_EXTENT_M / GRID_M))
        ia, ib = np.floor(a / GRID_M + m / 2).astype(int), np.floor(b / GRID_M + m / 2).astype(int)
        ok = (ia >= 0) & (ia < m) & (ib >= 0) & (ib < m)
        occ = np.zeros((m, m), np.float32)
        np.add.at(occ, (ib[ok], ia[ok]), 1.0)
        fl = (np.abs(hgt) < 0.05) & far
        fa, fb = (world[fl] - o) @ u, (world[fl] - o) @ v
        ja, jb = np.floor(fa / GRID_M + m / 2).astype(int), np.floor(fb / GRID_M + m / 2).astype(int)
        okf = (ja >= 0) & (ja < m) & (jb >= 0) & (jb < m)
        floor = np.zeros((m, m), np.float32)
        np.add.at(floor, (jb[okf], ja[okf]), 1.0)
        np.savez_compressed(out / f"walls_{name}.npz", occ=occ, floor=floor, grid_m=GRID_M, half_extent_m=HALF_EXTENT_M,
                            moge_floor_inliers=best[0], scale=s, tilt_deg=float(np.degrees(np.arccos(np.clip(nn @ n_r, -1, 1)))))
        vis = np.zeros((m, m, 3), np.uint8)
        vis[..., 1] = np.clip(floor * 40, 0, 255)
        vis[..., 2] = np.clip(occ * 8, 0, 255)
        c = m // 2
        cv2.circle(vis, (int(round(((0 - o) @ u) / GRID_M + c)), int(round(((0 - o) @ v) / GRID_M + c))), 6, (255, 255, 255), -1)  # camera
        cv2.imwrite(str(out / f"walls_{name}.png"), vis)
        print(name, "moge floor inliers", best[0], "scale", round(s, 3), "tilt", round(float(np.degrees(np.arccos(np.clip(nn @ n_r, -1, 1)))), 2))


def main() -> None:
    cmd = sys.argv[1]
    if cmd == "plates":
        plates(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4:])
    elif cmd == "moge":
        moge(Path(sys.argv[2]), sys.argv[3:])
    elif cmd == "walls":
        walls(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4:])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
