"""t3_fix_units: decision units, candidate turns about the centre of mass, the null control, and per-unit decisions.

Plan agent-doc/plan-t3fix-2026-10-27.md (track2/p1-training) v2, section 1 A2-A5. Contract RECOVERY-C002.

Runs without pytest: python test_t3_fix_units.py
"""
import numpy as np

from t3_fix_units import (MIN_EVIDENCE, candidates, decide, near_sym_axis, null_candidates, rot, runs, turn_deg,
                          turn_poses, units)
from t3_sil_choose import choose_pose


def _still(n):
    return np.tile(np.eye(3), (n, 1, 1))


def test_runs_cover_true_spans():
    assert runs([0, 1, 1, 0, 1]) == [(1, 3), (4, 5)]
    assert runs([1, 1]) == [(0, 2)]
    assert runs([0, 0]) == []


def test_turn_deg_sees_a_half_turn():
    R = _still(3)
    R[2] = rot([0, 0, 1], 180)
    d = turn_deg(R)
    assert d[0] == 0 and abs(d[1]) < 1e-6 and abs(d[2] - 180) < 1e-6


def test_unheld_run_is_one_unit_even_across_a_jump():
    R = _still(40)
    R[20:] = rot([0, 0, 1], 180)  # a flip inside an untouched rest
    out = units(R, np.zeros(40, bool))
    assert out == [{"start": 0, "end": 40, "held": False}]


def test_held_run_splits_at_jumps_and_units_cover_all_frames():
    R = _still(30)
    R[15:] = rot([1, 0, 0], 180)
    held = np.r_[np.zeros(5, bool), np.ones(20, bool), np.zeros(5, bool)]
    out = units(R, held)
    assert [(u["start"], u["end"], u["held"]) for u in out] == [(0, 5, False), (5, 15, True), (15, 25, True), (25, 30, False)]
    covered = np.zeros(30, int)
    for u in out:
        covered[u["start"]:u["end"]] += 1
    assert (covered == 1).all()


def test_turn_about_com_keeps_the_centre_of_mass():
    T = np.tile(np.eye(4), (2, 1, 1))
    T[:, :3, 3] = [[1.0, 2.0, 3.0], [0.0, 0.0, 1.0]]
    T[1, :3, :3] = rot([0, 1, 0], 37)
    com_b = np.array([0.1, -0.2, 0.3])
    out = turn_poses(T, rot([0, 0, 1], 180), com_b)
    before = np.einsum("nij,j->ni", T[:, :3, :3], com_b) + T[:, :3, 3]
    after = np.einsum("nij,j->ni", out[:, :3, :3], com_b) + out[:, :3, 3]
    assert np.allclose(before, after)
    assert not np.allclose(out[:, :3, 3], T[:, :3, 3])  # the origin moves when it is not the centre of mass


def test_near_sym_axis_picks_the_odd_moment():
    axes = np.eye(3)
    assert np.allclose(near_sym_axis([1.0, 5.0, 5.2], axes), [1, 0, 0])
    assert near_sym_axis([1.0, 3.0, 5.0], axes) is None
    assert near_sym_axis([5.0, 5.1, 5.2], axes) is None


def test_candidates_drop_symmetries_and_invisible_turns():
    axes = np.eye(3)
    flip_z = rot([0, 0, 1], 180)
    shift = lambda g: 0.0 if np.allclose(g, flip_z) else 0.05
    out = candidates([1.0, 3.0, 5.0], axes, shift, 0.01)
    assert sorted(out) == ["flip_a0", "flip_a1"]
    out = candidates([1.0, 3.0, 5.0], axes, lambda g: 0.05, 0.01, group=[np.eye(3), rot([1, 0, 0], 180)])
    assert sorted(out) == ["flip_a1", "flip_a2"]


def test_candidates_add_steps_about_a_near_symmetry_axis():
    out = candidates([1.0, 5.0, 5.2], np.eye(3), lambda g: 0.05, 0.01)
    assert "turn030" in out and "turn330" in out and "flip_a0" in out
    assert "turn180" not in out  # the same turn as flip_a0, kept once


def test_null_candidates_are_invisible_turns():
    out = null_candidates(np.eye(3), group=[np.eye(3), rot([0, 0, 1], 180)], cont_axis=np.array([0.0, 0.0, 1.0]))
    assert sorted(out) == ["null_5deg", "null_cont090", "null_g1"]
    assert np.allclose(out["null_g1"], rot([0, 0, 1], 180))


def test_decide_refuses_units_without_evidence_and_accepts_a_clear_flip():
    n = 40
    scores = {"current": np.full(n, 0.3), "flip_a0": np.full(n, 0.8)}
    scores["current"][:5] = np.nan  # five frames without mask evidence
    unit_list = [{"start": 0, "end": 8, "held": True}, {"start": 8, "end": 40, "held": True}]
    rows = decide(scores, unit_list, choose_pose, 0.05)
    assert rows[0]["reason"] == "evidence" and rows[0]["evidence"] == 3 < MIN_EVIDENCE
    assert rows[1]["decision"] == "accept" and rows[1]["name"] == "flip_a0" and rows[1]["evidence"] == 32


def test_decide_uses_the_given_min_gain():
    n = 20
    scores = {"current": np.full(n, 0.60), "flip_a0": np.full(n, 0.67)}
    u = [{"start": 0, "end": n, "held": True}]
    assert decide(scores, u, choose_pose, 0.05)[0]["decision"] == "accept"
    assert decide(scores, u, choose_pose, 0.08)[0]["reason"] == "gain"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok", t.__name__)
    print(f"{len(tests)} passed")
