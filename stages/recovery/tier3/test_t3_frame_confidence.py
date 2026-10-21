"""t3_frame_confidence.py on synthetic frames: a cube in front of a camera, its mask drawn from the true pose.

Guards: a frame the mask confirms is ok, a shifted pose is bad, an occluded object is unverified (no evidence either
way); the world pose goes back to the camera through the world step's similarity; jumps and unheld motion are bad; lost
segments keep runs, not isolated frames; stride carries values from the last measured frame. Runs with the gate venv
on L40S (no pytest there): python test_t3_frame_confidence.py
"""
import numpy as np
from scipy.spatial.transform import Rotation

import t3_frame_confidence as fc
from t3_object_check import rasterise

H, W = 480, 640
K = np.array([[800.0, 0, 320], [0, 800.0, 240], [0, 0, 1]])
CUBE_V = np.array([[x, y, z] for x in (-0.05, 0.05) for y in (-0.05, 0.05) for z in (-0.05, 0.05)])
CUBE_F = np.array([[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1],
                   [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]])


def pose(p, rotvec=(0.3, 0.4, 0.0)):
    T = np.eye(4)
    T[:3, :3] = Rotation.from_rotvec(rotvec).as_matrix()
    T[:3, 3] = p
    return T


def mask_of(T_cam):
    return rasterise(CUBE_V @ T_cam[:3, :3].T + T_cam[:3, 3], CUBE_F, K, H, W)


IDENT = (np.eye(3), np.zeros(3), 1.0)


def test_confirmed_frame_is_good():
    T = pose([0, 0, 1.0])
    px, iou, cpx, sil = fc.silhouette(CUBE_V, CUBE_F, T, *IDENT, K, mask_of(T), np.zeros((H, W), bool))
    assert px >= fc.MIN_MASK_PX and iou > 0.9 and cpx < 1 and sil == 0.0


def test_shifted_pose_is_bad():
    T = pose([0, 0, 1.0])
    off = pose([0.12, 0, 1.0])  # ~96 px off
    *_, sil = fc.silhouette(CUBE_V, CUBE_F, off, *IDENT, K, mask_of(T), np.zeros((H, W), bool))
    assert sil == 1.0


def test_occluded_object_has_no_evidence():
    T = pose([0, 0, 1.0])
    obj = mask_of(T)
    px, iou, _, sil = fc.silhouette(CUBE_V, CUBE_F, pose([0.3, 0, 1.0]), *IDENT, K, obj, obj.copy())
    assert px == 0 and np.isnan(iou) and np.isnan(sil)


def test_world_pose_goes_back_through_the_similarity():
    T_cam = pose([0.05, -0.02, 1.2])
    rot, t, s = Rotation.from_rotvec([0.1, -1.2, 0.3]).as_matrix(), np.array([0.4, 1.3, -2.0]), 0.98
    T_world = np.eye(4)
    T_world[:3, :3] = rot @ T_cam[:3, :3]
    T_world[:3, 3] = s * rot @ T_cam[:3, 3] + t  # world = s * rot @ cam + t
    _, iou, cpx, sil = fc.silhouette(CUBE_V, CUBE_F, T_world, rot, t, s, K, mask_of(T_cam), np.zeros((H, W), bool))
    assert iou > 0.9 and cpx < 1 and sil == 0.0
    # the same world pose read with the identity similarity is off: the mapping is what makes it match
    *_, sil_wrong = fc.silhouette(CUBE_V, CUBE_F, T_world, *IDENT, K, mask_of(T_cam), np.zeros((H, W), bool))
    assert sil_wrong == 1.0


def test_motion_flags():
    n = 60
    Tw = np.tile(np.eye(4), (n, 1, 1))
    Tw[:, 0, 3] = np.arange(n) * 0.02  # 0.6 m/s
    Tw[40:, 0, 3] += 0.2  # one 20 cm step at frame 40
    far = Tw[:, None, :3, 3] + [0, 1.0, 0]  # a hand 1 m away
    near = Tw[:, None, :3, 3] + [0.05, 0, 0]  # a hand on the surface
    jump, unheld, hand_d, speed = fc.motion_flags(Tw, far, CUBE_V)
    assert jump.tolist() == [i == 40 for i in range(n)]
    assert unheld[5:35].all() and hand_d.min() > fc.HAND_M and np.median(speed) > fc.MOVING_MPS
    _, unheld_near, _, _ = fc.motion_flags(Tw, near, CUBE_V)
    assert not unheld_near.any()
    still = np.tile(np.eye(4), (n, 1, 1))
    _, unheld_still, _, _ = fc.motion_flags(still, still[:, None, :3, 3] + [0, 1.0, 0], CUBE_V)
    assert not unheld_still.any()


def test_labels_and_lost_segments():
    n = 100
    sil = np.zeros(n)
    sil[10:12] = np.nan
    sil[30] = 1.0  # isolated bad frame
    sil[50:70] = 1.0  # a bad run
    jump = np.zeros(n, bool)
    jump[90] = True
    lab, lost = fc.label(sil, jump, np.zeros(n, bool))
    assert lab[0] == "ok" and lab[10] == "unverified" and lab[30] == "bad" and lab[60] == "bad" and lab[90] == "bad"
    assert lost[50:70].all() and not lost[30] and not lost[90] and not lost[:29].any()


def test_stride_carries_the_last_measured_frame():
    x = np.array([5.0, np.nan, 7.0, np.nan, np.nan])
    measured = np.array([True, False, True, False, False])
    assert fc.carry(x, measured).tolist() == [5.0, 5.0, 7.0, 7.0, 7.0]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok", t.__name__)
    print(f"{len(tests)} passed")
