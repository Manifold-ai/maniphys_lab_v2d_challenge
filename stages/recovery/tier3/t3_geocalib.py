"""Independent focal length and gravity for each Tier 3 exo camera: GeoCalib (pinhole weights) on the per-episode
background images written by t3_camera_groups.py, plus FRAMES single frames per episode for the spread.

GeoCalib's estimate does not depend on MoGe or on the human, so it separates a focal-length error from the depth
scale that CARI4D takes from the human. Roll and pitch follow from its gravity direction in the OpenCV camera frame.

    python t3_geocalib.py <camera_groups dir> <tier3 work root> <out .json>
"""

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

FRAMES = 5
FULL_WIDTH = 1536


def main() -> None:
    from geocalib import GeoCalib

    groups_dir, work, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    model = GeoCalib(weights="pinhole")
    groups = json.loads((groups_dir / "camera_groups.json").read_text())["groups"]
    group_of = {nm: gi for gi, members in enumerate(groups) for nm in members}

    def calibrate(bgr: np.ndarray) -> dict:
        img = torch.from_numpy(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)).permute(2, 0, 1).float() / 255.0
        with torch.no_grad():
            res = model.calibrate(img, camera_model="pinhole")
        cam, grav = res["camera"], res["gravity"]
        f = float(cam.f[0, 0]) * FULL_WIDTH / bgr.shape[1]
        rp = grav.rp[0].numpy()  # roll, pitch in radians
        return {"fx": round(f, 1), "roll_deg": round(float(np.degrees(rp[0])), 2), "pitch_deg": round(float(np.degrees(rp[1])), 2)}

    rows = []
    for bg in sorted(groups_dir.glob("ep*_bg.jpg")):
        name = bg.name[: -len("_bg.jpg")]
        row = {"episode": name, "group": group_of.get(name), "background": calibrate(cv2.imread(str(bg)))}
        vids = sorted((work / name).glob("episode_*.0.color.mp4"))
        frames = []
        if vids:
            cap = cv2.VideoCapture(str(vids[0]))
            n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            for i in np.linspace(0, n - 1, FRAMES).astype(int):
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
                ok, f = cap.read()
                if ok:
                    frames.append(calibrate(f))
        row["frames"] = frames
        rows.append(row)
        print(json.dumps({"episode": name, "group": row["group"], **row["background"],
                          "frames_fx": [f["fx"] for f in frames]}), flush=True)
    out.write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
