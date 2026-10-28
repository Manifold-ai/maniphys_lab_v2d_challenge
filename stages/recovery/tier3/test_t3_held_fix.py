"""t3_held_fix: unwrapping of orientation jumps inside a free run and the end-matching twist.

Plan agent-doc/plan-t3hand-2026-10-27.md (track2/p1-training) v3, section 1 P1. Contract RECOVERY-C005.

Runs without pytest: python test_t3_held_fix.py
"""
import numpy as np
from scipy.spatial.transform import Rotation

from t3_held_fix import JUMP_DEG, turn_deg, unwrap_run


def _slow_turn(n, deg_per_frame=2.0):
    return Rotation.from_rotvec(np.outer(np.deg2rad(deg_per_frame) * np.arange(n), [0, 0, 1.0])).as_matrix()


def _flip(R, t0, t1, deg=170.0):
    out = R.copy()
    g = Rotation.from_rotvec([np.deg2rad(deg), 0, 0]).as_matrix()
    out[t0:t1] = out[t0:t1] @ g
    return out


def test_no_jumps_unchanged():
    R = _slow_turn(60)
    out, jumps, d = unwrap_run(R, 0, 60)
    assert jumps == [] and np.allclose(out, R) and d == 0


def test_glitch_that_returns_is_removed_and_ends_match():
    R = _flip(_slow_turn(60), 20, 30)
    out, jumps, d = unwrap_run(R, 0, 60)
    assert jumps == [20, 30] and d < 1e-3
    assert np.abs(out - _slow_turn(60)).max() < 1e-3  # the motion inside the glitch is kept, the flip is gone
    assert turn_deg(out).max() <= JUMP_DEG


def test_branch_switch_is_spread_over_the_run():
    R = _flip(_slow_turn(100), 40, 100)
    out, jumps, d = unwrap_run(R, 0, 100)
    assert jumps == [40] and abs(d - 170) < 1
    assert np.abs(out[0] - R[0]).max() < 1e-4 and np.abs(out[99] - R[99]).max() < 1e-4  # both ends meet the measured poses
    assert turn_deg(out).max() <= 2 + 170 / 99 * np.pi / 2 + 0.5  # slow turn plus the cosine-weighted twist


def test_run_at_the_episode_end_keeps_the_unwrapped_branch():
    R = _flip(_slow_turn(100), 40, 100)
    out, jumps, d = unwrap_run(R, 0, 100, match_end=False)
    assert jumps == [40] and np.abs(out - _slow_turn(100)).max() < 1e-3


def test_fast_turn_under_the_cap_is_not_a_jump():
    R = _slow_turn(60, deg_per_frame=20.0)
    out, jumps, d = unwrap_run(R, 0, 60)
    assert jumps == [] and np.allclose(out, R)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok", t.__name__)
    print(f"{len(tests)} passed")
