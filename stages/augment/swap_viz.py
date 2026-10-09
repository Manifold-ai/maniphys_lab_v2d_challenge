"""Reference video of an asset swap: the original reconstruction next to the edited one, over the exo video.

Left panel: the official mesh at the episode's object pose and the original SOMA body. Right panel: the swapped mesh
at the same pose and the body after palm_resolve.py + arm_refit.py. Both bodies are drawn from their soma_params.npz
the way the downstream reads them (frame-0 identity and scale, per-frame bone-length flexibles, no correctives), as
SOMA vertices: body orange, hands (skinned to the hand and finger joints) white; the mesh as blue surface samples.
Top bar per panel: left half yellow while the left hand is in contact, right half cyan for the right hand, with the
official retarget's rule (soma_to_g1.py --contact-threshold 0.02: a hand point within 2 cm of a mesh vertex; the
SOMA Hand joint and five fingertips stand in for the G1 palm link here), so the bar previews the contact labels the
retarget will write. Same crop for both panels, fixed over the clip.

Runs in the v2d_cari4d image (torch, soma, cv2, trimesh), CPU.

    python swap_viz.py <convert dir> <refit dir> <official mesh> <swapped mesh> <video> <soma assets> <out .mp4>
"""

import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import torch
import trimesh
from scipy.spatial import cKDTree

F_CV_TO_SOMA = np.diag([1.0, -1.0, -1.0])
CONTACT_M = 0.02
CHUNK = 64
SAMPLES = 40000
PANEL_H = 720
BAR_PX = 10
SIDES = ("Left", "Right")
TIPS = ("ThumbEnd", "IndexEnd", "MiddleEnd", "RingEnd", "PinkyEnd")
BLUE, ORANGE, WHITE = (255, 150, 60), (40, 140, 255), (255, 255, 255)  # BGR
YELLOW, CYAN = (0, 220, 255), (255, 230, 0)


def soma_forward(sp_path: Path, assets: str) -> tuple[np.ndarray, np.ndarray, list[str], np.ndarray]:
    from soma import SOMALayer
    from soma.units import Unit

    sp = np.load(sp_path, allow_pickle=True)
    n = len(sp["poses"])
    layer = SOMALayer(data_root=assets, identity_model_type="mhr", device="cpu", output_unit=Unit.METERS,
                      enable_procedural_transforms=False)
    ident = torch.tensor(np.repeat(sp["identity_coeffs"].reshape(n, -1)[:1], n, 0), dtype=torch.float32)
    scale = torch.tensor(np.repeat(sp["scale_params"].reshape(n, -1)[:1], n, 0), dtype=torch.float32)
    verts, joints = [], []
    for s in range(0, n, CHUNK):
        sl = slice(s, min(n, s + CHUNK))
        with torch.no_grad():
            got = layer(torch.tensor(sp["poses"][sl], dtype=torch.float32), ident[sl], scale_params=scale[sl],
                        transl=torch.tensor(sp["transl"][sl], dtype=torch.float32), apply_correctives=False,
                        kwargs={"bone_length_flexibles": torch.tensor(sp["bone_length_flexibles"][sl], dtype=torch.float32)})
        verts.append(got["vertices"].numpy().astype(np.float32))
        joints.append(got["joints"].numpy().astype(np.float32))
    weights = np.asarray(layer.skinning_weights, np.float64)
    wnames = [str(x) for x in layer._public_joint_names]
    hand = weights[:, [k for k, nm in enumerate(wnames) if "Hand" in nm]].sum(axis=1) >= 0.5
    return np.concatenate(verts), np.concatenate(joints), [str(x) for x in sp["joint_names"]], hand


def contact(joints: np.ndarray, names: list[str], cam: np.ndarray, mesh_vertices: np.ndarray) -> dict:
    """Per side, per frame: a hand point within CONTACT_M of a mesh vertex (object-local, SOMA frame -> OpenCV)."""
    tree = cKDTree(mesh_vertices)
    out = {}
    for side in SIDES:
        idx = [names.index(f"{side}Hand")] + [names.index(f"{side}Hand{t}") for t in TIPS]
        pts_cam = joints[:, idx] @ F_CV_TO_SOMA  # SOMA frame -> OpenCV camera frame
        local = np.einsum("nkj,nji->nki", pts_cam - cam[:, None, :3, 3], cam[:, :3, :3])
        out[side] = tree.query(local.reshape(-1, 3))[0].reshape(len(joints), -1).min(axis=1) < CONTACT_M
    return out


def project(pts: np.ndarray, k: np.ndarray) -> np.ndarray:
    z = np.maximum(pts[:, 2], 1e-3)
    return np.stack([k[0, 0] * pts[:, 0] / z + k[0, 2], k[1, 1] * pts[:, 1] / z + k[1, 2]], 1)


def draw(img: np.ndarray, uv: np.ndarray, colour: tuple, alpha: float) -> None:
    h, w = img.shape[:2]
    u, v = np.round(uv[:, 0]).astype(int), np.round(uv[:, 1]).astype(int)
    keep = (u >= 0) & (u < w - 1) & (v >= 0) & (v < h - 1)
    u, v = u[keep], v[keep]
    for dy in (0, 1):
        for dx in (0, 1):
            img[v + dy, u + dx] = (img[v + dy, u + dx] * (1 - alpha) + np.array(colour) * alpha).astype(np.uint8)


def main() -> None:
    conv, refit, off_mesh, new_mesh, video, assets, out = sys.argv[1:8]
    conv, refit = Path(conv), Path(refit)
    z = np.load(conv / "object_cam.npz")
    cam, k = z["T_cam_glb"], z["intrinsics"]
    n = len(cam)
    panels = []
    for sp_path, mesh_path in ((conv / "soma_params.npz", off_mesh), (refit / "soma_params.npz", new_mesh)):
        verts, joints, names, hand = soma_forward(sp_path, assets)
        mesh = trimesh.load(mesh_path, force="mesh", process=False)
        np.random.seed(0)
        surf = np.asarray(trimesh.Trimesh(mesh.vertices, mesh.faces, process=False).sample(SAMPLES))
        panels.append({"verts": verts, "hand": hand, "surf": surf, "contact": contact(joints, names, cam, np.asarray(mesh.vertices))})
        print(Path(mesh_path).name, {s: int(c.sum()) for s, c in panels[-1]["contact"].items()}, flush=True)
    # one crop for the whole clip: everything drawn, padded
    uvs = []
    for p in panels:
        for i in range(0, n, 10):
            uvs.append(project(p["verts"][i] @ F_CV_TO_SOMA, k))
            uvs.append(project(p["surf"] @ cam[i, :3, :3].T + cam[i, :3, 3], k))
    w0, h0 = int(round(2 * k[0, 2])), int(round(2 * k[1, 2]))
    allp = np.concatenate(uvs)
    x0, y0 = np.clip(np.percentile(allp, 0.5, axis=0) - 60, 0, None).astype(int)
    x1, y1 = np.minimum(np.percentile(allp, 99.5, axis=0) + 60, [w0, h0]).astype(int)
    pw = int(round((x1 - x0) * PANEL_H / (y1 - y0)))
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-noautorotate", "-i", video, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{2 * pw}x{PANEL_H}", "-r", "30",
                            "-i", "-", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    titles = ("original: official mesh + reconstructed body", "swapped: new mesh + refit body")
    for i in range(n):
        raw = dec.stdout.read(w0 * h0 * 3)
        if len(raw) < w0 * h0 * 3:
            raise SystemExit(f"video ran out at frame {i}")
        frame = np.frombuffer(raw, np.uint8).reshape(h0, w0, 3)
        tiles = []
        for p, title in zip(panels, titles):
            img = frame.copy()
            draw(img, project(p["surf"] @ cam[i, :3, :3].T + cam[i, :3, 3], k), BLUE, 0.45)
            body = p["verts"][i] @ F_CV_TO_SOMA
            draw(img, project(body[~p["hand"]], k), ORANGE, 0.55)
            draw(img, project(body[p["hand"]], k), WHITE, 0.85)
            tile = cv2.resize(img[y0:y1, x0:x1], (pw, PANEL_H), interpolation=cv2.INTER_AREA)
            if p["contact"]["Left"][i]:
                tile[:BAR_PX, : pw // 2] = YELLOW
            if p["contact"]["Right"][i]:
                tile[:BAR_PX, pw // 2:] = CYAN
            cv2.rectangle(tile, (0, BAR_PX), (pw, BAR_PX + 28), (0, 0, 0), -1)
            cv2.putText(tile, f"{title}  f{i}", (8, BAR_PX + 21), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
            tiles.append(tile)
        enc.stdin.write(np.hstack(tiles).tobytes())
    enc.stdin.close()
    if enc.wait() != 0:
        raise SystemExit("encoding failed")
    dec.stdout.close()
    dec.wait()


if __name__ == "__main__":
    main()
