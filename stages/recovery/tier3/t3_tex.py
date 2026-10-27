"""Textured point-splat rendering and photometric scores for t3fix part B1 (Tier 3 inputs only).

Plan: agent-doc/plan-t3fix-2026-10-27.md on track2/p1-training, version 3, section 1 B1.

The renderer runs on the CPU. It draws area-weighted samples on the mesh surface, takes each sample's colour from the
glb baseColorTexture by its UV (bilinear, trimesh's convention: the glTF loader flips v and uv_to_interpolated_color
flips it back), projects the samples with the same pinhole model as t3_object_check.rasterise, and keeps the nearest
sample per pixel (z-buffer). With several samples per pixel the nearest one lies on the front surface, so there is no
back-face test; the renderer gate (silhouette IoU against rasterise) checks the coverage.
Scores are the normalised cross-correlation of the render and the video frame inside a region, per YCrCb channel
(each channel normalised by its own mean and standard deviation in the region), averaged over the three channels.
A decision segment is a run of frames between two single-frame turns above JUMP_DEG: the dynamics post-process keeps
the nearest equivalent rotation from frame to frame, so a wrong symmetric branch can only change at such a jump.
"""
import cv2
import numpy as np

MIN_TEX_PX = 1500
SPLAT_PER_PX = 4
BLUR_SIGMA = 4.0
DISTINCT_NCC = 0.95
MIN_MEDIAN = 0.3
MIN_GAP = 0.05
BLOCK = 10  # samples at stride 3 = 30 frames, about 1 s
N_BOOT = 2000


def surface_samples(verts, faces, uv, image, n: int, seed: int = 0):
    """(points (n, 3), colours (n, 3) float RGB 0-255) on the surface, area-weighted. uv is per vertex, image a PIL image."""
    from trimesh.visual.color import uv_to_interpolated_color
    rng = np.random.default_rng(seed)
    tri = verts[faces]
    area = 0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1)
    fi = rng.choice(len(faces), size=n, p=area / area.sum())
    r1, r2 = rng.random(n), rng.random(n)
    s = np.sqrt(r1)
    w = np.stack([1 - s, s * (1 - r2), s * r2], axis=1)
    pts = np.einsum("nk,nkd->nd", w, tri[fi])
    tuv = np.einsum("nk,nkd->nd", w, uv[faces[fi]])
    col = uv_to_interpolated_color(tuv, image)[:, :3].astype(np.float32)
    return pts, col


def splat(pts_cam, col, k, h: int, w: int):
    """(colour image (h, w, 3) float32, covered mask (h, w) bool): nearest sample per pixel."""
    z = pts_cam[:, 2]
    ok = z > 1e-3
    u = np.floor(pts_cam[ok, 0] / z[ok] * k[0, 0] + k[0, 2]).astype(np.int64)
    v = np.floor(pts_cam[ok, 1] / z[ok] * k[1, 1] + k[1, 2]).astype(np.int64)
    inside = (u >= 0) & (u < w) & (v >= 0) & (v < h)
    idx, zz, cc = v[inside] * w + u[inside], z[ok][inside], col[ok][inside]
    img = np.zeros((h * w, 3), np.float32)
    mask = np.zeros(h * w, bool)
    if len(idx):
        order = np.lexsort((zz, idx))
        idx, cc = idx[order], cc[order]
        first = np.r_[True, idx[1:] != idx[:-1]]
        img[idx[first]] = cc[first]
        mask[idx[first]] = True
    return img.reshape(h, w, 3), mask.reshape(h, w)


def ycrcb(img_rgb):
    """float32 YCrCb of an RGB float or uint8 image."""
    return cv2.cvtColor(np.clip(img_rgb, 0, 255).astype(np.uint8), cv2.COLOR_RGB2YCrCb).astype(np.float32)


def ncc(a, b, region) -> float:
    """Mean over channels of the normalised cross-correlation of a and b (h, w, c) inside region; nan if flat or empty."""
    if region.sum() < 2:
        return np.nan
    out = []
    for c in range(a.shape[2]):
        x, y = a[..., c][region], b[..., c][region]
        x, y = x - x.mean(), y - y.mean()
        d = np.sqrt((x * x).sum() * (y * y).sum())
        if d <= 1e-9:
            return np.nan
        out.append(float((x * y).sum() / d))
    return float(np.mean(out))


def blur(img, sigma: float = BLUR_SIGMA):
    return cv2.GaussianBlur(img, (0, 0), sigma)


def segments(step_deg, jump_deg: float) -> list[tuple[int, int]]:
    """[start, end) runs between single-frame turns above jump_deg (a jump at frame t starts a new segment at t)."""
    n = len(step_deg)
    cuts = [0] + [t for t in range(1, n) if step_deg[t] > jump_deg] + [n]
    return list(zip(cuts[:-1], cuts[1:]))


def boot_lower(diff, block: int = BLOCK, n_boot: int = N_BOOT, seed: int = 0) -> float:
    """2.5 % quantile of the median of diff under a moving-block bootstrap with blocks of `block` samples."""
    d = np.asarray(diff, np.float64)
    n = len(d)
    if n == 0:
        return np.nan
    b = min(block, n)
    starts = np.arange(n - b + 1)
    k = int(np.ceil(n / b))
    rng = np.random.default_rng(seed)
    meds = np.empty(n_boot)
    for i in range(n_boot):
        s = rng.choice(starts, size=k)
        meds[i] = np.median(np.concatenate([d[j:j + b] for j in s])[:n])
    return float(np.quantile(meds, 0.025))


def decide_segment(scores: dict[str, list[float]], min_median: float = MIN_MEDIAN, min_gap: float = MIN_GAP) -> dict:
    """One segment: scores per pose name ("current" plus candidates) on the same frames. Accept the best candidate only
    if it is not current, its median >= min_median, it beats the second best by >= min_gap in median, and the block
    bootstrap lower bound of its per-frame lead over the second best is > 0."""
    names = list(scores)
    med = {x: float(np.median(scores[x])) for x in names}
    order = sorted(names, key=lambda x: med[x], reverse=True)
    best, second = order[0], order[1] if len(order) > 1 else None
    res = {"median": med, "name": best, "decision": "refuse"}
    if second is None:
        return {**res, "reason": "no-alternative"}
    if best == "current":
        return {**res, "reason": "current-best"}
    if med[best] < min_median:
        return {**res, "reason": "below-gate"}
    gap = med[best] - med[second]
    lower = boot_lower(np.asarray(scores[best]) - np.asarray(scores[second]))
    res.update(gap=gap, boot_lower=lower)
    if gap < min_gap - 1e-12:
        return {**res, "reason": "gap"}
    if not lower > 0:
        return {**res, "reason": "bootstrap"}
    return {**res, "decision": "accept", "reason": "accept"}
