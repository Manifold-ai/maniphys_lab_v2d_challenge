"""t3_tex: point-splat rendering, photometric NCC, decision segments and the segment decision.

Plan agent-doc/plan-t3fix-2026-10-27.md (track2/p1-training) v3, section 1 B1. Contract RECOVERY-C004.

Runs without pytest: python test_t3_tex.py
"""
import numpy as np
from PIL import Image

from t3_tex import boot_lower, decide_segment, ncc, segments, splat, surface_samples

K = np.array([[100.0, 0, 32], [0, 100.0, 32], [0, 0, 1]])


def _quad():
    """A 0.4 m square at z = 1 m, uv over the whole texture; the texture's left half red, right half blue."""
    v = np.array([[-0.2, -0.2, 1.0], [0.2, -0.2, 1.0], [0.2, 0.2, 1.0], [-0.2, 0.2, 1.0]])
    f = np.array([[0, 1, 2], [0, 2, 3]])
    uv = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], float)
    tex = np.zeros((8, 8, 3), np.uint8)
    tex[:, :4] = [255, 0, 0]
    tex[:, 4:] = [0, 0, 255]
    return v, f, uv, Image.fromarray(tex)


def test_splat_covers_the_projected_square():
    v, f, uv, img = _quad()
    pts, col = surface_samples(v, f, uv, img, 20000)
    im, m = splat(pts, col, K, 64, 64)
    assert m[13:51, 13:51].mean() > 0.99 and not m[:10].any()


def test_texture_lands_on_the_right_side():
    v, f, uv, img = _quad()
    pts, col = surface_samples(v, f, uv, img, 20000)
    im, m = splat(pts, col, K, 64, 64)
    assert im[32, 20, 0] > 200 and im[32, 20, 2] < 50  # u small -> left -> red
    assert im[32, 44, 2] > 200 and im[32, 44, 0] < 50


def test_nearest_sample_wins():
    pts = np.array([[0.0, 0, 2.0], [0.0, 0, 1.0]])
    col = np.array([[255.0, 0, 0], [0, 255.0, 0]], np.float32)
    im, m = splat(pts, col, K, 64, 64)
    assert m[32, 32] and im[32, 32, 1] == 255


def test_ncc_is_one_for_affine_copies_and_nan_for_flat():
    rng = np.random.default_rng(0)
    a = rng.random((16, 16, 3)).astype(np.float32)
    reg = np.ones((16, 16), bool)
    assert abs(ncc(a, 2 * a + 5, reg) - 1) < 1e-6
    assert abs(ncc(a, -a, reg) + 1) < 1e-6
    assert np.isnan(ncc(np.ones_like(a), a, reg))


def test_segments_cut_at_jumps_only():
    step = np.zeros(10)
    step[4] = 30
    step[7] = 20
    assert segments(step, 24) == [(0, 4), (4, 10)]


def test_boot_lower_sign():
    assert boot_lower(np.full(40, 0.1) + np.random.default_rng(1).normal(0, 0.01, 40)) > 0
    assert boot_lower(np.random.default_rng(2).normal(0, 0.1, 40)) < 0


def test_decide_accepts_a_clear_better_candidate():
    rng = np.random.default_rng(3)
    s = {"current": list(0.30 + rng.normal(0, 0.02, 30)), "flip": list(0.60 + rng.normal(0, 0.02, 30))}
    assert decide_segment(s)["decision"] == "accept"


def test_decide_refuses_current_best_low_and_close():
    rng = np.random.default_rng(4)
    assert decide_segment({"current": [0.6] * 20, "flip": [0.4] * 20})["reason"] == "current-best"
    assert decide_segment({"current": [0.1] * 20, "flip": [0.2] * 20})["reason"] == "below-gate"
    close = {"current": list(0.50 + rng.normal(0, 0.05, 30)), "flip": list(0.52 + rng.normal(0, 0.05, 30))}
    assert decide_segment(close)["decision"] == "refuse"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok", t.__name__)
    print(f"{len(tests)} passed")
