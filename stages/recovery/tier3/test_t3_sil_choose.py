"""choose_pose: accept an object-pose candidate only when the silhouette scores tell it apart.

Runs without pytest: python test_t3_sil_choose.py
"""
import numpy as np

from t3_sil_choose import choose_pose, right_multiply


def test_accepts_a_clearly_better_yaw():
    out = choose_pose({"current": [0.40, 0.42, 0.44], "yaw180": [0.70, 0.72, 0.74]})
    assert out["decision"] == "accept" and out["name"] == "yaw180" and out["reason"] == "accept"
    assert out["median"]["current"] == 0.42 and out["median"]["yaw180"] == 0.72


def test_tie_refuses_even_when_both_beat_current():
    out = choose_pose({"current": [0.40, 0.40, 0.40], "a": [0.70, 0.70, 0.70], "b": [0.70, 0.70, 0.70]})
    assert out["decision"] == "refuse" and out["name"] is None and out["reason"] == "tie"


def test_below_gate_before_gain():
    out = choose_pose({"current": [0.10, 0.10, 0.10], "yaw180": [0.48, 0.48, 0.48]})
    assert out["reason"] == "below-gate"


def test_small_gain_refuses():
    out = choose_pose({"current": [0.60, 0.62, 0.64], "yaw180": [0.64, 0.66, 0.68]})
    assert out["reason"] == "gain"


def test_current_best_refuses():
    out = choose_pose({"current": [0.80, 0.80, 0.80], "yaw180": [0.60, 0.60, 0.60]})
    assert out["reason"] == "current-best"


def test_empty_list_refuses():
    out = choose_pose({"current": [0.8, 0.8, 0.8], "yaw180": []})
    assert out["reason"] == "empty"


def test_missing_current_refuses():
    out = choose_pose({"yaw180": [0.9, 0.9, 0.9]})
    assert out["reason"] == "no-current" and out["median"] == {}


def test_no_alternative_refuses():
    out = choose_pose({"current": [0.8, 0.8, 0.8]})
    assert out["reason"] == "no-alternative" and out["median"] == {}


def test_tied_low_scores_are_below_gate_not_tie():
    out = choose_pose({"current": [0.10, 0.10, 0.10], "a": [0.49, 0.49, 0.49], "b": [0.49, 0.49, 0.49]})
    assert out["reason"] == "below-gate"


def test_right_multiply_keeps_translation_and_is_not_a_left_multiply():
    poses = np.tile(np.eye(4), (2, 1, 1))
    poses[:, :3, 3] = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
    rotation = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    out = right_multiply(poses, rotation)
    assert np.allclose(out[:, :3, 3], poses[:, :3, 3])
    r4 = np.eye(4)
    r4[:3, :3] = rotation
    assert np.allclose(out, poses @ r4)
    assert not np.allclose(out, r4 @ poses)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok", t.__name__)
    print(f"{len(tests)} passed")
