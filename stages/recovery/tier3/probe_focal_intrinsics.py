"""Probe for t3_convert_ep's intrinsics re-expression (_intrinsics_map, _reexpress_object, _new_intrinsics), 10-16.

The focal step went from "change f" to "change f and the principal point" (main camera to rxzhou's ceiling-grid GB
intrinsics). What must hold, checked on synthetic poses and, given a convert dir, on real ones:
  pixels      every object position projects to the same pixel under the new intrinsics as under CARI4D's (< 1e-6 px)
  depth       depth scales by f_new / f_used
  view        the object keeps the side it shows the camera: R^T t / |t| unchanged (< 1e-9)
  reduction   with the principal point unchanged the map equals the old focal-only step (t @ diag(1, 1, k), < 1e-9 m)
  spec        `intrinsics` sets f, cx, cy; `focal_px` sets f only; null and an unknown group keep CARI4D's
  real        (with a convert dir) the old focal.json spec reproduces that dir's object_cam_focal.npz (< 1e-6 m: where
              CARI4D's float32 K has fy != fx, ep19's pivot dir by 7.4e-8, the old step ignored it and the new map keeps the
              pixel, 5.6e-8 m apart; everywhere else they agree to 1e-15)
Injected defect: a map that scales depth but ignores the principal point (the old formula used with new intrinsics)
must fail the pixel check, else the probe cannot see the error it is for.

    python probe_focal_intrinsics.py [<convert episode dir> <focal.json>]
Last line PROBE_FOCAL_INTRINSICS_OK or PROBE_FOCAL_INTRINSICS_FAILED.
"""

import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

sys.path.insert(0, str(Path(__file__).resolve().parent))
from t3_convert_ep import _intrinsics_map, _new_intrinsics, _reexpress_object  # noqa: E402

K_C = np.array([[824.1786, 0, 768.0], [0, 824.1786, 576.0], [0, 0, 1.0]])
K_GB = np.array([[866.3, 0, 701.8], [0, 866.3, 531.1], [0, 0, 1.0]])


def project(t, k):
    p = t @ k.T
    return p[:, :2] / p[:, 2:]


def poses(rng, n=2000):
    T = np.tile(np.eye(4), (n, 1, 1))
    T[:, :3, :3] = Rotation.random(n, random_state=rng).as_matrix()
    T[:, :3, 3] = np.c_[rng.uniform(-2, 2, n), rng.uniform(-1, 1.4, n), rng.uniform(1.0, 6.0, n)]
    return T


def check(name, ok, detail):
    print(f"  {'ok  ' if ok else 'FAIL'} {name}: {detail}")
    return ok


def main() -> int:
    rng = np.random.default_rng(0)
    T = poses(rng)
    t = T[:, :3, 3]
    good = True

    m = _intrinsics_map(K_C, K_GB)
    T2 = _reexpress_object(T, m)
    t2 = T2[:, :3, 3]
    px = np.abs(project(t2, K_GB) - project(t, K_C)).max()
    good &= check("pixels", px < 1e-6, f"max {px:.2e} px")
    ratio = np.abs(t2[:, 2] / t[:, 2] - K_GB[0, 0] / K_C[0, 0]).max()
    good &= check("depth", ratio < 1e-12, f"max |z'/z - f_new/f_used| {ratio:.2e}")
    v1 = np.einsum("nji,nj->ni", T[:, :3, :3], t / np.linalg.norm(t, axis=1, keepdims=True))
    v2 = np.einsum("nji,nj->ni", T2[:, :3, :3], t2 / np.linalg.norm(t2, axis=1, keepdims=True))
    good &= check("view", np.abs(v1 - v2).max() < 1e-9, f"max {np.abs(v1 - v2).max():.2e}")
    orth = np.abs(np.einsum("nij,nkj->nik", T2[:, :3, :3], T2[:, :3, :3]) - np.eye(3)).max()
    good &= check("rotation stays a rotation", orth < 1e-12, f"max {orth:.2e}")

    k830 = K_C.copy()
    k830[0, 0] = k830[1, 1] = 830.0
    old = T.copy()
    k = 830.0 / K_C[0, 0]
    old_t = t @ np.diag([1.0, 1.0, k])
    T3 = _reexpress_object(T, _intrinsics_map(K_C, k830))
    good &= check("reduction to the focal-only step", np.abs(T3[:, :3, 3] - old_t).max() < 1e-9,
                  f"max {np.abs(T3[:, :3, 3] - old_t).max():.2e} m")
    del old

    spec_i = {"camera_groups": {"0": ["a"]}, "intrinsics": {"0": {"f": 866.3, "cx": 701.8, "cy": 531.1}, "1": None}}
    spec_f = {"camera_groups": {"0": ["a"]}, "focal_px": {"0": 830.0, "1": None}}
    good &= check("spec intrinsics", np.allclose(_new_intrinsics(spec_i, 0, K_C), K_GB), "group 0 -> GB")
    good &= check("spec intrinsics null", np.array_equal(_new_intrinsics(spec_i, 1, K_C), K_C), "group 1 -> CARI4D's")
    good &= check("spec focal_px", np.allclose(_new_intrinsics(spec_f, 0, K_C), k830), "group 0 -> f 830, principal point kept")
    good &= check("spec unknown group", np.array_equal(_new_intrinsics(spec_i, None, K_C), K_C), "-> CARI4D's")

    # injected defect: depth scaled, principal point ignored
    bad = T.copy()
    bad[:, :3, 3] = t @ np.diag([1.0, 1.0, K_GB[0, 0] / K_C[0, 0]])
    px_bad = np.abs(project(bad[:, :3, 3], K_GB) - project(t, K_C)).max()
    good &= check("injected defect caught (pixel check fails)", px_bad > 1.0, f"defect moves pixels by up to {px_bad:.1f} px")

    if len(sys.argv) > 2:
        conv, spec = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text())
        oc = np.load(conv / "object_cam.npz")
        ref = np.load(conv / "object_cam_focal.npz")
        k_used = np.asarray(oc["intrinsics"], np.float64).reshape(3, 3)
        group = next((int(g) for g, mem in spec["camera_groups"].items() if conv.name in mem), None)
        k_new = _new_intrinsics(spec, group, k_used)
        got = _reexpress_object(oc["T_cam_glb"].astype(np.float64), _intrinsics_map(k_used, k_new))
        d = np.abs(got - ref["T_cam_glb"]).max()
        good &= check(f"real {conv.name}", d < 1e-6 and np.allclose(k_new, ref["intrinsics"]),
                      f"max |new code - existing object_cam_focal| {d:.2e}, intrinsics equal {np.allclose(k_new, ref['intrinsics'])}")

    print("PROBE_FOCAL_INTRINSICS_OK" if good else "PROBE_FOCAL_INTRINSICS_FAILED")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
