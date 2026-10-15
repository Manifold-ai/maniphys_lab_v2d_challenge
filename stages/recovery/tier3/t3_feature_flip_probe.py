"""Do pretrained pixel features tell an object's flips apart on our frames? V-JEPA 2 / DINOv2 zero-shot probe (10-15).

FoundationPose's scorer ranked flipped candidates nearly flat (t3_fp_score_probe.py). This asks the same of two general
encoders: per frame, the selected pose (fp_poses_cam) is turned about the mesh's principal axes in STEP_DEG steps
(as t3_fp_score_probe.py); each candidate is rendered textured (FoundationPose's nvdiffrast_render), the real frame and
each render are cropped to the same square around the object mask (CROP_SCALE of its larger side), everything outside
the object (the SAM2 mask for the real crop, the render's own silhouette) set to black, and resized to RES. Score: the
mean cosine similarity of corresponding patch tokens over the patches either object covers. V-JEPA 2 ViT-L
(facebook/vjepa2-vitl-fpc64-256, MIT) gets the crop repeated as a 16-frame clip and its tokens averaged over time;
DINOv2 ViT-L/14 with registers (local torch.hub checkout) gets the crop at 224. Zero-shot: neither was trained to
compare renders with photos, so a negative result says "not without training", not "not in the pixels".

Inside v2d_cari4d, the episode's CARI4D work dir at /data/video_path, FoundationPose weights at the CARI4D weights path,
the V-JEPA 2 snapshot at $VJEPA_DIR (mount the whole models--... dir: snapshot files link into its blobs/), the
DINOv2 hub dir at /dinohub:
    python t3_feature_flip_probe.py <episode> <frame:truth,...> <out dir>
truth: same (the selected pose is right) or flip (the long axis is turned end over end; candidates grouped by it).
"""

import json
import pickle
import sys
from pathlib import Path

import cv2
import numpy as np
from scipy.spatial.transform import Rotation

sys.path.insert(0, "/workspace/v2d_cari4d/lib/cari4d/prep")
STEP_DEG = 60
CROP_SCALE = 1.6
RES = 256
DINO_RES = 224


def crop_box(mask, H, W):
    ys, xs = np.nonzero(mask)
    cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
    half = max(xs.max() - xs.min(), ys.max() - ys.min()) * CROP_SCALE / 2 + 4
    x0, y0 = int(round(cx - half)), int(round(cy - half))
    return x0, y0, int(round(2 * half))


def cut(img, box, res):
    x0, y0, s = box
    pad = s
    big = cv2.copyMakeBorder(img, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
    c = big[y0 + pad:y0 + pad + s, x0 + pad:x0 + pad + s]
    return cv2.resize(c, (res, res), interpolation=cv2.INTER_AREA if c.dtype != bool else cv2.INTER_NEAREST)


def main() -> None:
    import torch
    import torch.nn.functional as F
    import run_foundationpose_mhr_export as rf
    from transformers import AutoVideoProcessor, VJEPA2Model

    ep, cases, out = int(sys.argv[1]), [c.split(":") for c in sys.argv[2].split(",")], Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    root = Path("/data/video_path/cari4d") / f"episode_{ep:06d}"
    export_seq = root / "export" / f"episode_{ep:06d}"
    fp = pickle.load(open(root / "foundationpose" / f"episode_{ep:06d}.pkl", "rb"))
    depth_root, camera_id, names = Path(fp["metadata"]["depth_root"]), int(fp["camera_id"]), list(fp["frames"])
    K, _ = rf.camera_calibration(rf.load_edex(export_seq), camera_id)
    mesh = rf.load_export_object_mesh(export_seq)
    est = rf._pose_estimator(mesh, out / "debug")
    import nvdiffrast.torch as dr
    glctx = dr.RasterizeCudaContext()
    to_c = est.get_tf_to_centered_mesh().cpu().numpy()
    _, axes = np.linalg.eigh(np.asarray(mesh.convex_hull.moment_inertia))
    turns = [("none", np.eye(3))] + [(f"ax{k}_{d}", Rotation.from_rotvec(axes[:, k] * np.deg2rad(d)).as_matrix())
                                     for k in range(3) for d in range(STEP_DEG, 360, STEP_DEG)]
    long_axis = axes[:, 0]

    import os
    vjdir = os.environ.get("VJEPA_DIR", "/vjepa")  # a snapshot dir; its files link into the repo's blobs/
    proc = AutoVideoProcessor.from_pretrained(vjdir)
    vj = VJEPA2Model.from_pretrained(vjdir, torch_dtype=torch.float16).cuda().eval()
    dino = torch.hub.load("/dinohub/facebookresearch_dinov2_main", "dinov2_vitl14_reg", source="local", pretrained=False)
    dino.load_state_dict(torch.load("/dinohub/checkpoints/dinov2_vitl14_reg4_pretrain.pth", map_location="cpu"))
    dino = dino.cuda().eval()
    mean = torch.tensor([0.485, 0.456, 0.406], device="cuda")[:, None, None]
    std = torch.tensor([0.229, 0.224, 0.225], device="cuda")[:, None, None]

    @torch.no_grad()
    def vj_tokens(crops):  # (N, RES, RES, 3) uint8 RGB -> (N, 16*16, D)
        feats = []
        for c in crops:
            clip = np.repeat(c[None], 16, 0)  # (T, H, W, C)
            x = proc(videos=[clip], return_tensors="pt")["pixel_values_videos"].to("cuda", torch.float16)
            t = vj.get_vision_features(x)[0].float()  # (T/2 * 16*16, D)
            feats.append(t.reshape(-1, 256, t.shape[-1]).mean(0))
        return torch.stack(feats)

    @torch.no_grad()
    def dino_tokens(crops):
        x = torch.as_tensor(np.stack([cv2.resize(c, (DINO_RES, DINO_RES)) for c in crops]), device="cuda").permute(0, 3, 1, 2).float() / 255
        x = (x - mean) / std
        return dino.forward_features(x)["x_norm_patchtokens"].float()  # (N, 16*16, D)

    def score(tok, masks):  # tok (1+C, P, D): real first; masks (1+C, RES, RES) bool
        g = int(round(tok.shape[1] ** 0.5))
        cover = torch.as_tensor(np.stack([cv2.resize(m.astype(np.uint8), (g, g), interpolation=cv2.INTER_AREA) > 0 for m in masks]), device="cuda").reshape(len(masks), -1)
        sim = F.cosine_similarity(tok[:1], tok[1:], dim=-1)  # (C, P)
        use = cover[:1] | cover[1:]
        return ((sim * use).sum(1) / use.sum(1).clamp(min=1)).cpu().numpy()

    rows = []
    for f_s, truth in cases:
        f = int(f_s)
        _, rgb, depth, _, mask_o, Kf = rf._read_foundationpose_frame(export_seq, depth_root, camera_id, names[f], K)
        H, W = mask_o.shape
        P = np.asarray(fp["fp_poses_cam"][f, 0], np.float64)
        Pc = P @ np.linalg.inv(to_c)
        cands = []
        for _, Rt in turns:
            C = Pc.copy()
            C[:3, :3] = Pc[:3, :3] @ Rt
            cands.append(C)
        cands = torch.as_tensor(np.asarray(cands, np.float32), device="cuda")
        color, _, _ = rf.Utils.nvdiffrast_render(K=Kf, H=H, W=W, ob_in_cams=cands, glctx=glctx, mesh_tensors=est.mesh_tensors)
        color = (color.clamp(0, 1) * 255).byte().cpu().numpy()  # (C, H, W, 3) RGB
        sil = color.sum(-1) > 0
        box = crop_box(mask_o, H, W)
        real = np.where(mask_o[..., None], rgb, 0).astype(np.uint8)
        crops = [cut(real, box, RES)] + [cut(np.where(sil[i][..., None], color[i], 0).astype(np.uint8), box, RES) for i in range(len(turns))]
        masks = [cut(mask_o.astype(np.uint8), box, RES) > 0] + [cut(sil[i].astype(np.uint8), box, RES) > 0 for i in range(len(turns))]
        right = np.array([nm == "none" for nm, _ in turns]) if truth == "same" else \
            np.array([float((Rt @ long_axis) @ long_axis) <= 0 for _, Rt in turns])
        row = {"episode": ep, "frame": f, "truth": truth, "object_px": int(mask_o.sum())}
        for nm, tok in (("vjepa2", vj_tokens(crops)), ("dinov2", dino_tokens(crops))):
            s = score(tok, masks)
            order = np.argsort(-s)
            row[nm] = {"top": turns[order[0]][0], "top_is_right": bool(right[order[0]]),
                       "best_right": round(float(s[right].max()), 4), "best_wrong": round(float(s[~right].max()), 4),
                       "spread": round(float(s.max() - s.min()), 4)}
        rows.append(row)
        print(json.dumps(row), flush=True)
        sheet = np.vstack([np.hstack(crops[i:i + 6] + [np.zeros_like(crops[0])] * max(0, 6 - len(crops[i:i + 6]))) for i in range(0, len(crops), 6)])
        cv2.imwrite(str(out / f"ep{ep:02d}_f{f:04d}_crops.jpg"), cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR))
    (out / f"ep{ep:02d}_feature_probe.json").write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
