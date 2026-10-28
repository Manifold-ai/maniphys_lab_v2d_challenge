"""t3_held_fix: jump stretches inside held runs and the slerp repair.

Plan agent-doc/plan-t3hand-2026-10-27.md (track2/p1-training) v2, section 1 P1. Contract RECOVERY-C005.

Runs without pytest: python test_t3_held_fix.py
"""
import numpy as np
from scipy.spatial.transform import Rotation

from t3_held_fix import JUMP_DEG, slerp_fill, stretches, turn_deg


def _slow_turn(n, deg_per_frame=2.0):
    return Rotation.from_rotvec(np.outer(np.deg2rad(deg_per_frame) * np.arange(n), [0, 0, 1.0])).as_matrix()


def _flip(R, t0, t1, deg=170.0):
    out = R.copy()
    g = Rotation.from_rotvec([np.deg2rad(deg), 0, 0]).as_matrix()
    out[t0:t1] = out[t0:t1] @ g
    return out


def test_no_jumps_no_stretches():
    R = _slow_turn(60)
    assert stretches(R, np.ones(60, bool)) == []


def test_glitch_inside_held_run_is_bridged():
    R = _flip(_slow_turn(60), 20, 30)
    held = np.ones(60, bool)
    st = stretches(R, held)
    assert st == [(19, 30)]
    fixed = slerp_fill(R, 19, 30)
    assert turn_deg(fixed).max() <= JUMP_DEG
    assert np.allclose(fixed[19], R[19]) and np.allclose(fixed[30], R[30])


def test_jump_outside_held_run_is_ignored():
    R = _flip(_slow_turn(60), 20, 30)
    held = np.zeros(60, bool)
    assert stretches(R, held) == []


def test_branch_switch_is_bridged_at_the_cap_rate():
    R = _flip(_slow_turn(60), 40, 60)  # 170 deg switch that never returns: reachable at 24 deg/frame after 8 frames
    held = np.ones(60, bool)
    st = stretches(R, held)
    assert st == [(39, 47)]
    fixed = slerp_fill(R, 39, 47)
    assert turn_deg(fixed).max() <= JUMP_DEG + 1e-9


def test_switch_too_close_to_the_run_end_runs_to_the_end():
    R = _flip(_slow_turn(60), 56, 60)
    st = stretches(R, np.ones(60, bool))
    assert st == [(55, 59)]


def test_real_fast_turn_under_the_cap_is_kept():
    R = _slow_turn(60, deg_per_frame=20.0)
    assert stretches(R, np.ones(60, bool)) == []


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok", t.__name__)
    print(f"{len(tests)} passed")
