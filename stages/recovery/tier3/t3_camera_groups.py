"""Which Tier 3 episodes were filmed by the same physical camera, from the same place? Exo videos only.

Per episode: a background image, the per-pixel median of FRAMES frames spread over the clip (the person moves, so the
median keeps the static scene). Per pair: SIFT matches (Lowe ratio test) and a RANSAC homography; the pair is the same
view when the homography has at least SAME_INLIERS inliers and moves a grid of image points by at most SAME_SHIFT_PX
on average. Groups are the connected components of "same view". A camera that was re-aimed between sessions shows up
as many inliers with a large shift; a different camera as few inliers.

    python t3_camera_groups.py <tier3 work root> <out dir>
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np

FRAMES = 21
SCALE = 0.5
RATIO = 0.75
SAME_INLIERS = 150
SAME_SHIFT_PX = 15.0  # at full resolution


def background(video: Path) -> np.ndarray:
    cap = cv2.VideoCapture(str(video))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frames = []
    for i in np.linspace(0, n - 1, FRAMES).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, f = cap.read()
        if ok:
            frames.append(cv2.resize(f, None, fx=SCALE, fy=SCALE, interpolation=cv2.INTER_AREA))
    if len(frames) < FRAMES // 2:
        raise SystemExit(f"{video}: read only {len(frames)} frames")
    return np.median(np.stack(frames), axis=0).astype(np.uint8)


def main() -> None:
    root, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    names, bgs = [], []
    for w in sorted(root.glob("ep[0-9][0-9]_*")):
        vids = sorted(w.glob("episode_*.0.color.mp4"))
        if not vids:
            continue
        bg = background(vids[0])
        cv2.imwrite(str(out / f"{w.name}_bg.jpg"), bg)
        names.append(w.name)
        bgs.append(bg)
    sift = cv2.SIFT_create(nfeatures=4000)
    feats = [sift.detectAndCompute(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), None) for b in bgs]
    h, w = bgs[0].shape[:2]
    grid = np.stack(np.meshgrid(np.linspace(0, w - 1, 9), np.linspace(0, h - 1, 7)), -1).reshape(-1, 1, 2).astype(np.float32)
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    n = len(names)
    inl = np.zeros((n, n), int)
    shift = np.full((n, n), np.inf)
    for i in range(n):
        for j in range(i + 1, n):
            (ki, di), (kj, dj) = feats[i], feats[j]
            if di is None or dj is None or len(ki) < 8 or len(kj) < 8:
                continue
            good = [m for m, nn in matcher.knnMatch(di, dj, k=2) if m.distance < RATIO * nn.distance]
            if len(good) < 8:
                continue
            a = np.float32([ki[m.queryIdx].pt for m in good])
            b = np.float32([kj[m.trainIdx].pt for m in good])
            hm, mask = cv2.findHomography(a, b, cv2.RANSAC, 3.0)
            if hm is None:
                continue
            inl[i, j] = inl[j, i] = int(mask.sum())
            moved = cv2.perspectiveTransform(grid, hm)
            shift[i, j] = shift[j, i] = float(np.linalg.norm(moved - grid, axis=-1).mean()) / SCALE
    same = (inl >= SAME_INLIERS) & (shift <= SAME_SHIFT_PX)
    group = list(range(n))

    def find(x: int) -> int:
        while group[x] != x:
            group[x] = group[group[x]]
            x = group[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            if same[i, j]:
                group[find(i)] = find(j)
    roots = {}
    labels = [roots.setdefault(find(i), len(roots)) for i in range(n)]
    groups = {}
    for nm, g in zip(names, labels):
        groups.setdefault(g, []).append(nm)
    report = {"thresholds": {"same_inliers": SAME_INLIERS, "same_shift_px": SAME_SHIFT_PX, "frames": FRAMES, "scale": SCALE},
              "groups": sorted(groups.values(), key=len, reverse=True), "episodes": names,
              "inliers": inl.tolist(), "shift_px": [[None if not np.isfinite(x) else round(x, 1) for x in r] for r in shift]}
    (out / "camera_groups.json").write_text(json.dumps(report, indent=1))
    # contact sheet, one row per group
    thumbs = {nm: cv2.resize(b, (256, 192)) for nm, b in zip(names, bgs)}
    rows = []
    for members in report["groups"]:
        tiles = []
        for nm in members:
            t = thumbs[nm].copy()
            cv2.putText(t, nm[:12], (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)
            tiles.append(t)
        for k in range(0, len(tiles), 8):
            chunk = tiles[k:k + 8] + [np.zeros_like(tiles[0])] * (8 - len(tiles[k:k + 8]))
            rows.append(np.hstack(chunk))
        rows.append(np.full((6, 256 * 8, 3), 255, np.uint8))
    cv2.imwrite(str(out / "camera_groups_sheet.jpg"), np.vstack(rows))
    print(json.dumps({"groups": report["groups"]}))


if __name__ == "__main__":
    main()
