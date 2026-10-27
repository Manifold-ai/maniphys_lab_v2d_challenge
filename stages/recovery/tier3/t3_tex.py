"""Textured point-splat rendering and photometric scores for t3fix part B1 (Tier 3 inputs only).

Plan: agent-doc/plan-t3fix-2026-10-27.md on track2/p1-training, version 3.1, section 1 B1.

The renderer runs on the CPU. It draws area-weighted samples on the mesh surface, takes each sample's colour from the
glb baseColorTexture by its UV (bilinear, trimesh's convention: the glTF loader flips v and uv_to_interpolated_color
flips it back; test_t3_tex checks a glb round trip), projects the samples with the same pinhole model and pixel
centres as t3_object_check.rasterise, and keeps the nearest sample per pixel (a depth buffer). With several samples per
pixel the nearest one lies on the front surface, so there is no back-face test; the renderer gate (silhouette IoU
against rasterise) checks the coverage.
Scores are normalised cross-correlations inside a region, per YCrCb channel, averaged over the channels whose
standard deviation on the reference side reaches CONTRAST (a flat channel carries only noise). Variant "i" uses the
images as they are, variant "ii" a band-pass (Gaussian sigma BAND[0] minus sigma BAND[1]) that removes slow shading.
A decision segment is a run of frames between two single-frame turns above JUMP_DEG: the dynamics post-process keeps
the nearest equivalent rotation from frame to frame, so a wrong symmetric branch can only change at such a jump. A cut
between two unheld frames is dropped, because an untouched object must not change its orientation.
"""
import cv2
import numpy as np

MIN_TEX_PX = 1500
SPLAT_PER_PX = 4
BAND = (1.5, 15.0)
CONTRAST = (8.0, 4.0, 4.0)  # Y, Cr, Cb standard deviation floors in 8-bit levels
DISTINCT_NCC = 0.95
SELF_MARGIN = 0.02
MIN_MEDIAN = 0.3
MIN_GAP = 0.05
BLOCK = 10  # samples at stride 3 = 30 frames, about 1 s
MIN_BLOCKS = 3
AGREE = 2 / 3
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
    u = np.floor(pts_cam[ok, 0] / z[ok] * k[0, 0] + k[0, 2] + 0.5).astype(np.int64)  # pixel centres on integers, as rasterise
    v = np.floor(pts_cam[ok, 1] / z[ok] * k[1, 1] + k[1, 2] + 0.5).astype(np.int64)
    inside = (u >= 0) & (u < w) & (v >= 0) & (v < h)
    idx, zz, cc = v[inside] * w + u[inside], z[ok][inside], col[ok][inside]
    img = np.zeros((h * w, 3), np.float32)
    depth = np.full(h * w, np.inf)
    np.minimum.at(depth, idx, zz)
    win = zz <= depth[idx]
    img[idx[win]] = cc[win]
    return img.reshape(h, w, 3), np.isfinite(depth).reshape(h, w)


def ycrcb(img_rgb):
    """float32 YCrCb of an RGB float or uint8 image."""
    return cv2.cvtColor(np.clip(img_rgb, 0, 255).astype(np.uint8), cv2.COLOR_RGB2YCrCb).astype(np.float32)


def blur(img, sigma: float):
    return cv2.GaussianBlur(img, (0, 0), sigma)


def masked_blur(img, cov, sigma: float):
    """Blur of img over the covered pixels only (normalised convolution), so the black background does not leak in."""
    w = blur(cov.astype(np.float32), sigma)
    return blur(img * cov[..., None], sigma) / np.maximum(w, 1e-6)[..., None]


def band(img, cov=None):
    """Band-pass: Gaussian BAND[0] minus Gaussian BAND[1]; cov restricts a render to its covered pixels."""
    if cov is None:
        return blur(img, BAND[0]) - blur(img, BAND[1])
    return masked_blur(img, cov, BAND[0]) - masked_blur(img, cov, BAND[1])


def ncc(a, b, region, ref=None, floors=CONTRAST) -> float:
    """Mean over the usable channels of the normalised cross-correlation of a and b (h, w, c) inside region. A channel
    is usable when its standard deviation in ref (default a) inside region reaches its floor. nan if none is usable."""
    if region.sum() < 2:
        return np.nan
    ref = a if ref is None else ref
    out = []
    for c in range(a.shape[2]):
        if ref[..., c][region].std() < floors[c]:
            continue
        x, y = a[..., c][region], b[..., c][region]
        x, y = x - x.mean(), y - y.mean()
        d = np.sqrt((x * x).sum() * (y * y).sum())
        if d > 1e-9:
            out.append(float((x * y).sum() / d))
    return float(np.mean(out)) if out else np.nan


def segments(step_deg, jump_deg: float, unheld=None) -> list[tuple[int, int]]:
    """[start, end) runs between single-frame turns above jump_deg (a jump at frame t starts a new segment at t). With
    unheld flags, a cut whose two sides are both unheld is dropped."""
    n = len(step_deg)
    cut = [t for t in range(1, n) if step_deg[t] > jump_deg and not (unheld is not None and unheld[t - 1] and unheld[t])]
    cuts = [0] + cut + [n]
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


def decide_segment(scores: dict[str, list[float]], near: dict[str, set] | None = None, min_median: float = MIN_MEDIAN,
                   min_gap: float = MIN_GAP) -> dict:
    """One segment: scores per pose name ("current" plus candidates) on the same frames. The rival of the best pose is
    the best of "current" and the candidates not in near[best] (neighbours on a turn grid). Accept the best only if it is
    not current, there are MIN_BLOCKS full blocks, its median >= min_median, it leads the rival by >= min_gap in median,
    the block-bootstrap lower bound of its per-frame lead over the rival is > 0, and it is the top pose in at least AGREE
    of the full blocks."""
    near = near or {}
    names = list(scores)
    n = len(scores[names[0]])
    med = {x: float(np.median(scores[x])) for x in names}
    best = max(names, key=lambda x: med[x])
    res = {"median": med, "name": best, "decision": "refuse"}
    rivals = [x for x in names if x != best and (x == "current" or x not in near.get(best, set()))]
    if not rivals:
        return {**res, "reason": "no-alternative"}
    if best == "current":
        return {**res, "reason": "current-best"}
    if n < MIN_BLOCKS * BLOCK:
        return {**res, "reason": "evidence"}
    rival = max(rivals, key=lambda x: med[x])
    if med[best] < min_median:
        return {**res, "rival": rival, "reason": "below-gate"}
    gap = med[best] - med[rival]
    lead = np.asarray(scores[best]) - np.asarray(scores[rival])
    lower = boot_lower(lead)
    nb = n // BLOCK
    tops = [max(names, key=lambda x: np.median(scores[x][i * BLOCK:(i + 1) * BLOCK])) for i in range(nb)]
    agree = sum(t == best for t in tops) / nb
    res.update(rival=rival, gap=gap, boot_lower=lower, agree=agree)
    if gap < min_gap - 1e-12:
        return {**res, "reason": "gap"}
    if not lower > 0:
        return {**res, "reason": "bootstrap"}
    if agree < AGREE - 1e-12:
        return {**res, "reason": "blocks"}
    return {**res, "decision": "accept", "reason": "accept"}


def merge_variants(rows_by_variant: dict[str, dict]) -> dict:
    """Accept only if every variant accepts the same pose; otherwise refuse with reason "variants"."""
    rows = list(rows_by_variant.values())
    if all(r["decision"] == "accept" for r in rows) and len({r["name"] for r in rows}) == 1:
        return {"decision": "accept", "name": rows[0]["name"], "reason": "accept"}
    return {"decision": "refuse", "name": None, "reason": "variants" if any(r["decision"] == "accept" for r in rows) else "none"}
