"""t3_fix_onset: mask statistics and the drift / hand_late / still classification.

Plan agent-doc/plan-t3fix-2026-10-27.md (track2/p1-training) v2, section 1 C2. Contract RECOVERY-C003.

Runs without pytest: python test_t3_fix_onset.py
"""
import numpy as np

from t3_fix_onset import MIN_EVIDENCE, classify, mask_stats


def _box(x, y, w=40, h=30, shape=(200, 300)):
    m = np.zeros(shape, bool)
    m[y:y + h, x:x + w] = True
    return m


def test_still_mask_has_no_shift():
    st = mask_stats([_box(50, 50)] * 5)
    assert st["shift_px_max"] == 0 and st["iou_min"] == 1 and st["area_min"] == st["area_max"] == 1


def test_moving_mask_shifts():
    st = mask_stats([_box(50, 50), _box(70, 50)])
    assert abs(st["shift_px_max"] - 20) < 1e-9 and st["iou_min"] < 0.8


def test_drift_needs_the_guard():
    put = mask_stats([_box(50, 50)] * 3)
    assert classify(0.10, put, MIN_EVIDENCE, True) == "drift"
    assert classify(0.10, put, MIN_EVIDENCE, False) == "inconclusive"


def test_still_when_the_reference_stays():
    put = mask_stats([_box(50, 50)] * 3)
    assert classify(0.01, put, MIN_EVIDENCE, None) == "still"


def test_hand_late_when_the_mask_moves():
    moved = mask_stats([_box(50, 50), _box(80, 50)])
    assert classify(0.10, moved, MIN_EVIDENCE, None) == "hand_late"


def test_area_change_counts_as_motion_along_the_ray():
    grown = mask_stats([_box(50, 50, 40, 30), _box(50, 50, 43, 30)])  # 7.5% wider, centroid shift 1.5 px
    assert grown["shift_px_max"] <= 15 and grown["area_max"] > 1.05
    assert classify(0.10, grown, MIN_EVIDENCE, True) == "hand_late"


def test_too_little_evidence_is_inconclusive():
    put = mask_stats([_box(50, 50)] * 3)
    assert classify(0.10, put, MIN_EVIDENCE - 1, True) == "inconclusive"
    assert classify(0.10, None, 0, None) == "inconclusive"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok", t.__name__)
    print(f"{len(tests)} passed")
