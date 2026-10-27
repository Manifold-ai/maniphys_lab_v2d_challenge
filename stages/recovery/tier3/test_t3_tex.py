"""t3_tex: point-splat rendering, photometric NCC, decision segments and the segment decision.

Plan agent-doc/plan-t3fix-2026-10-27.md (track2/p1-training) v3.1, section 1 B1. Contract RECOVERY-C004.

Runs without pytest: python test_t3_tex.py
"""
import numpy as np
from PIL import Image

from t3_tex import BLOCK, MIN_BLOCKS, boot_lower, decide_segment, merge_variants, ncc, segments, splat, surface_samples

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
    a = (100 * rng.random((16, 16, 3))).astype(np.float32)
    reg = np.ones((16, 16), bool)
    assert abs(ncc(a, 2 * a + 5, reg) - 1) < 1e-6
    assert abs(ncc(a, -a, reg) + 1) < 1e-6
    assert np.isnan(ncc(np.ones_like(a), a, reg))


def test_ncc_skips_low_contrast_channels():
    rng = np.random.default_rng(5)
    a = (100 * rng.random((16, 16, 3))).astype(np.float32)
    b = a.copy()
    a[..., 1:] = 128 + rng.normal(0, 1, (16, 16, 2))  # flat chroma: noise only
    b[..., 1:] = 128 + rng.normal(0, 1, (16, 16, 2))
    reg = np.ones((16, 16), bool)
    assert abs(ncc(a, b, reg) - 1) < 1e-6  # only Y is used


def test_segments_cut_at_jumps_only():
    step = np.zeros(10)
    step[4] = 30
    step[7] = 20
    assert segments(step, 24) == [(0, 4), (4, 10)]


def test_segments_keep_an_untouched_run_whole():
    step = np.zeros(10)
    step[4] = 30
    unheld = np.ones(10, bool)
    assert segments(step, 24, unheld) == [(0, 10)]
    unheld[4] = False
    assert segments(step, 24, unheld) == [(0, 4), (4, 10)]


def test_boot_lower_sign():
    assert boot_lower(np.full(40, 0.1) + np.random.default_rng(1).normal(0, 0.01, 40)) > 0
    assert boot_lower(np.random.default_rng(2).normal(0, 0.1, 40)) < 0


def test_decide_accepts_a_clear_better_candidate():
    rng = np.random.default_rng(3)
    s = {"current": list(0.30 + rng.normal(0, 0.02, 30)), "flip": list(0.60 + rng.normal(0, 0.02, 30))}
    assert decide_segment(s)["decision"] == "accept"


def test_decide_needs_three_full_blocks():
    n = MIN_BLOCKS * BLOCK - 1
    s = {"current": [0.3] * n, "flip": [0.6] * n}
    assert decide_segment(s)["reason"] == "evidence"


def test_decide_ignores_grid_neighbours_as_rivals():
    rng = np.random.default_rng(6)
    s = {"current": list(0.30 + rng.normal(0, 0.02, 40)), "cont010": list(0.60 + rng.normal(0, 0.02, 40)),
         "cont020": list(0.59 + rng.normal(0, 0.02, 40))}
    assert decide_segment(s)["reason"] == "gap"
    assert decide_segment(s, near={"cont010": {"cont020"}, "cont020": {"cont010"}})["decision"] == "accept"


def test_decide_needs_block_agreement():
    a = [0.6] * 20 + [0.3] * 20
    b = [0.3] * 20 + [0.6] * 20
    s = {"current": [0.2] * 40, "x": [v + 0.01 for v in a], "y": b}
    assert decide_segment(s)["decision"] == "refuse"


def test_merge_variants_needs_the_same_accept():
    acc = {"decision": "accept", "name": "flip"}
    assert merge_variants({"i": acc, "ii": acc})["decision"] == "accept"
    assert merge_variants({"i": acc, "ii": {"decision": "accept", "name": "turn030"}})["reason"] == "variants"
    assert merge_variants({"i": acc, "ii": {"decision": "refuse", "name": None}})["reason"] == "variants"


def test_glb_round_trip_keeps_texture_orientation():
    import io
    import trimesh
    v, f, uv, _ = _quad()
    tex = np.zeros((8, 8, 3), np.uint8)
    tex[:4, :4] = [255, 0, 0]  # image top-left
    tex[:4, 4:] = [0, 255, 0]
    tex[4:, :4] = [0, 0, 255]
    tex[4:, 4:] = [255, 255, 0]
    img = Image.fromarray(tex)
    mesh = trimesh.Trimesh(v, f, visual=trimesh.visual.TextureVisuals(uv=uv, image=img), process=False)
    before = surface_samples(v, f, uv, img, 4000, seed=1)[1]
    back = trimesh.load(io.BytesIO(mesh.export(file_type="glb")), file_type="glb", force="mesh", process=False)
    assert back.visual.kind == "texture"
    after = surface_samples(np.asarray(back.vertices), np.asarray(back.faces), np.asarray(back.visual.uv),
                            back.visual.material.baseColorTexture, 4000, seed=1)[1]
    assert np.abs(before - after).max() < 2


def test_decide_refuses_current_best_low_and_close():
    rng = np.random.default_rng(4)
    assert decide_segment({"current": [0.6] * 20, "flip": [0.4] * 20})["reason"] == "current-best"
    assert decide_segment({"current": [0.1] * 30, "flip": [0.2] * 30})["reason"] == "below-gate"
    close = {"current": list(0.50 + rng.normal(0, 0.05, 30)), "flip": list(0.52 + rng.normal(0, 0.05, 30))}
    assert decide_segment(close)["decision"] == "refuse"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok", t.__name__)
    print(f"{len(tests)} passed")
