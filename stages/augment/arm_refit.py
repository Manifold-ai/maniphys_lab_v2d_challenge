"""Refit the SOMA arms to the hands moved by palm_resolve.py, so the edited human is one consistent body again.

palm_resolve.py moves each hand rigidly (a per-frame translation, in the SOMA frame) and leaves the arm where it was.
Here, per side and per frame the hand moved, the local rotations of Shoulder, Arm, ForeArm and Hand are optimised so
that the Hand joint and the five fingertip joints land on their original positions plus that frame's offset, with a
pull back to the original rotations (the smallest arm change that reaches) and a frame-to-frame smoothness term.
Six points on the hand fix its orientation too, so the hand keeps its original pose in the world; fingers keep their
local rotations. Every other joint, the root translation, the identity and the frames that were not moved are copied
unchanged, and the run asserts that.

The SOMA forward is the downstream's: frame-0 identity and scale repeated over the clip (read_soma.py reads frame 0),
per-frame bone-length flexibles, no correctives.

Runs in the v2d_cari4d image (torch, soma). CPU by default; the L40S GPU is shared.

    python arm_refit.py <convert dir> <offsets_<candidate>.npz> <soma assets dir> <out dir> [--device cpu|cuda]

Writes <out dir>/soma_params.npz (the convert dir's file with the arm rotations replaced) and arm_refit.json.
"""

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import torch

SIDES = ("Left", "Right")
ARM = ("Shoulder", "Arm", "ForeArm", "Hand")
TIPS = ("ThumbEnd", "IndexEnd", "MiddleEnd", "RingEnd", "PinkyEnd")
MOVED_M = 1e-3
ITERS = 400
LR = 0.01
W_REG = 0.05  # per rad^2, against the original local rotations
W_SMOOTH = 1.0  # per rad^2, between neighbouring frames
CHUNK = 128


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("conv")
    ap.add_argument("offsets")
    ap.add_argument("assets")
    ap.add_argument("out")
    ap.add_argument("--device", default="cpu")
    a = ap.parse_args()
    from soma import SOMALayer
    from soma.units import Unit

    conv, out, dev = Path(a.conv), Path(a.out), torch.device(a.device)
    out.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(4)
    sp = np.load(conv / "soma_params.npz", allow_pickle=True)
    names = [str(x) for x in sp["joint_names"]]
    n = len(sp["poses"])
    off = np.load(a.offsets)
    layer = SOMALayer(data_root=a.assets, identity_model_type="mhr", device=str(dev), output_unit=Unit.METERS,
                      enable_procedural_transforms=False)
    ident = torch.tensor(np.repeat(sp["identity_coeffs"].reshape(n, -1)[:1], n, 0), dtype=torch.float32, device=dev)
    scale = torch.tensor(np.repeat(sp["scale_params"].reshape(n, -1)[:1], n, 0), dtype=torch.float32, device=dev)
    transl = torch.tensor(sp["transl"], dtype=torch.float32, device=dev)
    flex = torch.tensor(sp["bone_length_flexibles"], dtype=torch.float32, device=dev)
    poses0 = torch.tensor(sp["poses"], dtype=torch.float32, device=dev)  # (n, 77, 3) local rotvecs

    def joints(poses: torch.Tensor, sl: slice) -> torch.Tensor:
        return layer(poses, ident[sl], scale_params=scale[sl], transl=transl[sl], apply_correctives=False,
                     kwargs={"bone_length_flexibles": flex[sl]})["joints"]

    with torch.no_grad():
        j0 = torch.cat([joints(poses0[s: s + CHUNK], slice(s, min(n, s + CHUNK))) for s in range(0, n, CHUNK)])
    poses = poses0.clone()
    report = {"frames": n, "sides": {}}
    for side in SIDES:
        shift = torch.tensor(off[f"{side}_world_soma"], dtype=torch.float32, device=dev)
        moved = np.nonzero(np.linalg.norm(off[f"{side}_world_soma"], axis=1) > MOVED_M)[0]
        if not len(moved):
            report["sides"][side] = {"moved_frames": 0}
            continue
        arm = [names.index(f"{side}{j}") for j in ARM]
        pts = [names.index(f"{side}Hand")] + [names.index(f"{side}Hand{t}") for t in TIPS]
        idx = torch.as_tensor(moved, device=dev)
        target = j0[idx][:, pts] + shift[idx][:, None]
        var = poses0[idx][:, arm].clone().requires_grad_(True)
        opt = torch.optim.Adam([var], lr=LR)
        consecutive = torch.as_tensor(np.diff(moved) == 1, device=dev)
        for it in range(ITERS):
            full = poses[idx].clone()
            full[:, arm] = var
            got = layer(full, ident[idx], scale_params=scale[idx], transl=transl[idx], apply_correctives=False,
                        kwargs={"bone_length_flexibles": flex[idx]})["joints"][:, pts]
            fit = ((got - target) ** 2).sum(-1).mean() / 0.01**2
            reg = W_REG * ((var - poses0[idx][:, arm]) ** 2).sum((-1, -2)).mean()
            smooth = W_SMOOTH * (((var[1:] - var[:-1]) ** 2).sum((-1, -2)) * consecutive).mean() if len(moved) > 1 else var.sum() * 0
            loss = fit + reg + smooth
            opt.zero_grad()
            loss.backward()
            opt.step()
        with torch.no_grad():
            poses[idx[:, None], torch.as_tensor(arm, device=dev)[None]] = var.detach()
            full = poses[idx]
            got = layer(full, ident[idx], scale_params=scale[idx], transl=transl[idx], apply_correctives=False,
                        kwargs={"bone_length_flexibles": flex[idx]})["joints"][:, pts]
            err_after = (got - target).norm(dim=-1).max(dim=1).values.cpu().numpy() * 100
            err_before = (j0[idx][:, pts] - target).norm(dim=-1).max(dim=1).values.cpu().numpy() * 100
            dtheta = (var.detach() - poses0[idx][:, arm]).norm(dim=-1).cpu().numpy()  # (m, 4) rad
        report["sides"][side] = {
            "moved_frames": int(len(moved)),
            "tip_error_cm_before": {"p50": round(float(np.median(err_before)), 2), "max": round(float(err_before.max()), 2)},
            "tip_error_cm_after": {"p50": round(float(np.median(err_after)), 2), "p95": round(float(np.percentile(err_after, 95)), 2),
                                   "max": round(float(err_after.max()), 2)},
            "rotation_change_deg_max": {j: round(float(np.degrees(dtheta[:, k].max())), 1) for k, j in enumerate(ARM)},
        }
    # nothing outside the arm chains and the moved frames may have changed
    changed = (poses - poses0).abs().amax(-1) > 0  # (n, 77)
    allowed = torch.zeros_like(changed)
    for side in SIDES:
        moved = np.nonzero(np.linalg.norm(off[f"{side}_world_soma"], axis=1) > MOVED_M)[0]
        for j in ARM:
            allowed[torch.as_tensor(moved, device=dev), names.index(f"{side}{j}")] = True
    assert not (changed & ~allowed).any(), "rotations outside the refit arms or frames changed"
    report["changed_rotations"] = int(changed.sum())
    saved = {k: sp[k] for k in sp.files}
    saved["poses"] = poses.cpu().numpy().astype(sp["poses"].dtype)
    np.savez(out / "soma_params.npz", **saved)
    for f in ("object_cam.npz",):
        shutil.copy(conv / f, out / f)
    (out / "arm_refit.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report))


if __name__ == "__main__":
    main()
