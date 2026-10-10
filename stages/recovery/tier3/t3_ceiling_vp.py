"""Focal length of a fixed exo camera from the ceiling light grid: two orthogonal vanishing points.

The suspended ceiling is a regular grid (T-bar rails and the rectangular light panels set in it) on a plane parallel to
the floor. Its lines fall into two orthogonal 3D directions; each family converges to a vanishing point on the horizon. With the principal point p,
orthogonality gives f^2 = -(v1 - p).(v2 - p). Both points lie near the horizon row, so f depends almost only on the
horizontal principal point; the vertical one enters as (horizon - cy)^2, about 1% of f^2.

Per episode: full-resolution background (per-pixel median of FRAMES frames); LSD line segments above ROW_MAX, at least
MIN_LEN long and not near-vertical (walls, tripods); two families by angle clustering; each vanishing point by RANSAC
(a segment agrees when the direction from its midpoint to the point is within AGREE_DEG of its own), then
length-weighted least squares on the agreeing segments. Also separately from the left and right halves of the image as a lens
distortion check. A wide lens bends lines towards the edges (first run: left half 812-820 px, right half 860-865 px), so
segment end points are undistorted with one radial term, x_u = c + (x_d - c)(1 + k1 r^2), r in units of F_NORM, for k1
over K1_GRID; the reported k1 is the one where the two halves agree best on f. Reports f for cy at the image centre and
at CY_ALT, the horizon row at the image centre, and the roll.

    python t3_ceiling_vp.py <tier3 work root> <comma-separated episode dir names> <out dir>
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np

FRAMES = 21
ROW_MAX = 330
MIN_LEN = 30.0
VERTICAL_DEG = 25.0
AGREE_DEG = 1.0
CY_ALT = 520.0
F_NORM = 850.0
K1_GRID = np.round(np.arange(-0.10, 0.101, 0.01), 3)


def background(video: Path) -> np.ndarray:
    cap = cv2.VideoCapture(str(video))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frames = []
    for i in np.linspace(0, n - 1, FRAMES).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, f = cap.read()
        if ok:
            frames.append(f)
    return np.median(np.stack(frames), axis=0).astype(np.uint8)


def ceiling_segments(img: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray[ROW_MAX:] = 0
    lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD)
    lines = lsd.detect(gray)[0]
    segs = []
    for x1, y1, x2, y2 in ([] if lines is None else lines.reshape(-1, 4)):
        p, q = np.array([x1, y1], np.float64), np.array([x2, y2], np.float64)
        d = q - p
        if np.linalg.norm(d) < MIN_LEN or max(y1, y2) >= ROW_MAX - 2:
            continue
        if abs(np.degrees(np.arctan2(abs(d[0]), abs(d[1])))) < VERTICAL_DEG:  # within VERTICAL_DEG of vertical
            continue
        segs.append((p, q))
    return segs


def vanishing_point(segs: list[tuple[np.ndarray, np.ndarray]], rng: np.random.Generator) -> tuple[np.ndarray, float, int]:
    """RANSAC on pairwise intersections, then length-weighted least squares (perpendicular distance) on the inliers."""
    mid = np.array([(p + q) / 2 for p, q in segs])
    dirs = np.array([(q - p) / np.linalg.norm(q - p) for p, q in segs])
    lens = np.array([np.linalg.norm(q - p) for p, q in segs])
    nrm = np.c_[-dirs[:, 1], dirs[:, 0]]
    off = (nrm * mid).sum(1)

    def agree(v: np.ndarray) -> np.ndarray:
        to = v - mid
        to /= np.linalg.norm(to, axis=1, keepdims=True)
        return np.degrees(np.arccos(np.clip(np.abs((to * dirs).sum(1)), 0, 1))) < AGREE_DEG

    best, best_w = None, -1.0
    for _ in range(2000):
        i, j = rng.choice(len(segs), 2, replace=False, p=lens / lens.sum())
        a = np.array([nrm[i], nrm[j]])
        if abs(np.linalg.det(a)) < 1e-6:
            continue
        v = np.linalg.solve(a, [off[i], off[j]])
        wsum = lens[agree(v)].sum()
        if wsum > best_w:
            best, best_w = v, wsum
    keep = agree(best)
    w = np.sqrt(lens[keep])
    v = np.linalg.lstsq(nrm[keep] * w[:, None], off[keep] * w, rcond=None)[0]
    keep = agree(v)
    w = np.sqrt(lens[keep])
    v = np.linalg.lstsq(nrm[keep] * w[:, None], off[keep] * w, rcond=None)[0]
    return v, float(np.sqrt(np.mean((nrm[keep] @ v - off[keep]) ** 2))), int(keep.sum())


def undistort(edges, k1: float, w_img: int, h_img: int):
    c = np.array([w_img / 2.0, h_img / 2.0])

    def u(p: np.ndarray) -> np.ndarray:
        d = (p - c) / F_NORM
        return c + (p - c) * (1 + k1 * (d @ d))

    return [(u(p), u(q)) for p, q in edges]


def solve(edges, w_img: int, h_img: int) -> dict | None:
    rng = np.random.default_rng(0)
    if len(edges) < 16:
        return None
    ang = np.array([np.arctan2(*(q - p)[::-1]) for p, q in edges])
    z = np.c_[np.cos(2 * ang), np.sin(2 * ang)].astype(np.float32)  # doubled angle: direction, not orientation
    _, lab, _ = cv2.kmeans(z, 2, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-4), 10, cv2.KMEANS_PP_CENTERS)
    lab = lab.ravel()
    fams = [[e for e, l in zip(edges, lab) if l == k] for k in (0, 1)]
    if min(len(f) for f in fams) < 8:
        return None
    (v1, r1, n1), (v2, r2, n2) = (vanishing_point(f, rng) for f in fams)
    cx = w_img / 2.0
    out = {"edges": [len(f) for f in fams], "inliers": [n1, n2], "vp1": v1.round(1).tolist(), "vp2": v2.round(1).tolist(),
           "vp_rms_px": [round(r1, 2), round(r2, 2)]}
    for tag, cy in (("cy_center", h_img / 2.0), ("cy_alt", CY_ALT)):
        p = np.array([cx, cy])
        f2 = -float((v1 - p) @ (v2 - p))
        out[f"f_{tag}"] = round(float(np.sqrt(f2)), 1) if f2 > 0 else None
    slope = (v2[1] - v1[1]) / (v2[0] - v1[0])
    out["horizon_row_at_cx"] = round(float(v1[1] + slope * (cx - v1[0])), 1)
    out["roll_deg"] = round(float(np.degrees(np.arctan(slope))), 2)
    return out


def main() -> None:
    work, names, out = Path(sys.argv[1]), sys.argv[2].split(","), Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in names:
        vids = sorted((work / name).glob("episode_*.0.color.mp4"))
        if not vids:
            continue
        img = background(vids[0])
        h, w = img.shape[:2]
        edges = ceiling_segments(img)
        sweep = []
        for k1 in K1_GRID:
            ue = undistort(edges, float(k1), w, h)
            sweep.append({"k1": float(k1), "all": solve(ue, w, h),
                          "left": solve([e for e in ue if (e[0][0] + e[1][0]) / 2 < w / 2], w, h),
                          "right": solve([e for e in ue if (e[0][0] + e[1][0]) / 2 >= w / 2], w, h)})
        ok = [r for r in sweep if all(r[k] and r[k]["f_cy_center"] for k in ("all", "left", "right"))]
        best = min(ok, key=lambda r: abs(r["left"]["f_cy_center"] - r["right"]["f_cy_center"])) if ok else None
        row = {"episode": name, "segments": len(edges), "best": best, "k1_zero": next(r for r in sweep if r["k1"] == 0.0), "sweep": sweep}
        rows.append(row)
        dbg = img.copy()
        for p, q in edges:
            cv2.line(dbg, tuple(np.round(p).astype(int)), tuple(np.round(q).astype(int)), (0, 0, 255), 2)
        cv2.imwrite(str(out / f"{name}_ceiling.jpg"), dbg[:ROW_MAX + 40])
        brief = lambda r: r and {"k1": r["k1"], **{side: r[side] and {kk: r[side][kk] for kk in ("f_cy_center", "horizon_row_at_cx", "roll_deg")}
                                                 for side in ("all", "left", "right")}}
        print(json.dumps({"episode": name, "segments": len(edges), "best": brief(best), "k1_zero": brief(row["k1_zero"])}), flush=True)
    (out / "ceiling_vp.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
