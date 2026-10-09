"""Overlay the palm re-solve on the source exo video, for checking by eye.

Per candidate, every frame of the episode video gets:
  - the object mesh (official or swapped) as blue surface samples, placed by the episode's object pose;
  - the SOMA hand vertices before the edit in red;
  - the hand vertices after the edit in green, only on frames the edit moved them (|t| > 1 mm);
  - a bar along the top edge: left half yellow while the left hand is in a contact segment, right half cyan for the
    right hand (left/right of the person, not of the image).
The arm is not refit at this step, so a moved hand sits off the forearm by the offset; that gap is expected.

Then a grid of up to six candidates (2x2 or 3x2, half size, labelled) and stills of the grid at each segment's middle frame.
CPU and ffmpeg only, no extra Python packages:

    python palm_viz.py <convert dir> <pilot dir> <palm dir> <video> <out dir>

<palm dir> is palm_resolve.py's output (hand_forward.npz, offsets_*.npz, palm_report.json).
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import trimesh

F_CV_TO_SOMA = np.diag([1.0, -1.0, -1.0])
SURFACE_SAMPLES = 40000
MOVED_M = 0.001
BAR_PX = 14
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SIDES = ("Left", "Right")
BLUE, RED, GREEN = np.array([60, 140, 255]), np.array([255, 50, 50]), np.array([40, 255, 80])
YELLOW, CYAN = np.array([255, 220, 0]), np.array([0, 230, 255])


def project(pts: np.ndarray, k: np.ndarray, w: int, h: int) -> tuple[np.ndarray, np.ndarray]:
    pts = pts[pts[:, 2] > 1e-3]
    u = np.round(k[0, 0] * pts[:, 0] / pts[:, 2] + k[0, 2]).astype(int)
    v = np.round(k[1, 1] * pts[:, 1] / pts[:, 2] + k[1, 2]).astype(int)
    keep = (u >= 1) & (u < w - 1) & (v >= 1) & (v < h - 1)
    return u[keep], v[keep]


def splat(img: np.ndarray, u: np.ndarray, v: np.ndarray, color: np.ndarray, alpha: float, radius: int) -> None:
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            uu, vv = np.clip(u + dx, 0, img.shape[1] - 1), np.clip(v + dy, 0, img.shape[0] - 1)
            img[vv, uu] = (1 - alpha) * img[vv, uu] + alpha * color


def render(video: Path, out: Path, k: np.ndarray, size: tuple[int, int], n: int, cam: np.ndarray, surf: np.ndarray,
           hands: dict, moved: dict, active: dict) -> None:
    w, h = size
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-threads", "2", "-i", str(video), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", "30",
                            "-i", "-", "-threads", "2", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", str(out)],
                           stdin=subprocess.PIPE)
    for i in range(n):
        raw = dec.stdout.read(w * h * 3)
        if len(raw) < w * h * 3:
            raise SystemExit(f"{video}: ran out of frames at {i}, expected {n}")
        img = np.frombuffer(raw, np.uint8).reshape(h, w, 3).astype(np.float32)
        u, v = project(surf @ cam[i, :3, :3].T + cam[i, :3, 3], k, w, h)
        splat(img, u, v, BLUE, 0.35, 0)
        for s in SIDES:
            u, v = project(hands[s][i], k, w, h)
            splat(img, u, v, RED, 0.8, 1)
            if moved[s] is not None and np.linalg.norm(moved[s][i] - hands[s][i], axis=1).max() > MOVED_M:
                u, v = project(moved[s][i], k, w, h)
                splat(img, u, v, GREEN, 0.8, 1)
        if active["Left"][i]:
            img[:BAR_PX, : w // 2] = YELLOW
        if active["Right"][i]:
            img[:BAR_PX, w // 2 :] = CYAN
        enc.stdin.write(img.clip(0, 255).astype(np.uint8).tobytes())
    enc.stdin.close()
    if enc.wait() != 0:
        raise SystemExit(f"encoding {out} failed")
    dec.stdout.close()
    dec.wait()


def label(name: str, row: dict | None) -> str:
    stem, _, variant = name.removeprefix("stool_").rpartition("_")
    name = f"{stem[:8]}_{variant}" if stem else name
    if row is None:
        return name
    verdict = "PASS" if row.get("pass") else "FAIL"
    if "no_grasp_site" in row:
        return f"{name}  no grasp site"
    parts = [f"{s[0]} kept {v['kept_share']:.3f} pen {v['palm_pen_share']:.3f}" for s, v in row["sides"].items()]
    return f"{name}  {verdict}  " + "  ".join(parts)


def main(conv: Path, pilot: Path, palm: Path, video: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    z = np.load(conv / "object_cam.npz")
    cam, k = z["T_cam_glb"], z["intrinsics"]
    n = len(cam)
    w, h = (int(x) for x in subprocess.check_output(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(video)],
        text=True).strip().split(","))
    fw = np.load(palm / "hand_forward.npz")
    # SOMA frame -> OpenCV camera frame (F is its own inverse)
    hands = {s: fw[f"{s}_hand_verts"].astype(np.float64) @ F_CV_TO_SOMA for s in SIDES}
    report = json.loads((palm / "palm_report.json").read_text())
    rows = {r["candidate"]: r for r in report["candidates"]}
    active = {s: np.zeros(n, bool) for s in SIDES}
    for s in SIDES:
        for a, b in report["segments"][s]:
            active[s][a:b] = True

    names = sorted(p.stem.removeprefix("offsets_") for p in palm.glob("offsets_*.npz"))
    names = ["official"] + [x for x in names if x != "official"]
    clips = []
    for name in names:
        mesh = trimesh.load(pilot / ("official_local.glb" if name == "official" else f"{name}.glb"), force="mesh", process=False)
        np.random.seed(0)
        surf = np.asarray(trimesh.Trimesh(mesh.vertices, mesh.faces, process=False).sample(SURFACE_SAMPLES), np.float64)
        off = np.load(palm / f"offsets_{name}.npz")
        moved = {s: hands[s] + (off[f"{s}_world_soma"] @ F_CV_TO_SOMA)[:, None] for s in SIDES}
        clip = out / f"{name}.mp4"
        render(video, clip, k, (w, h), n, cam, surf, hands, moved, active)
        clips.append((clip, label(name, rows.get(name))))
        print(f"wrote {clip}", flush=True)

    # 2x2 (up to four clips) or 3x2 grid, half size per tile, labelled; the first six clips in the order above
    tiles = clips[:6]
    cols = 2 if len(tiles) <= 4 else 3
    inputs, filters = [], []
    for j, (clip, text) in enumerate(tiles):
        inputs += ["-i", str(clip)]
        safe = text.replace(":", r"\:").replace("'", "")
        filters.append(f"[{j}:v]scale={w // 2}:{h // 2},drawtext=fontfile={FONT}:text='{safe}':x=8:y={BAR_PX + 6}:"
                       f"fontsize=18:fontcolor=white:box=1:boxcolor=black@0.6[t{j}]")
    while len(filters) < 2 * cols:
        j = len(filters)
        filters.append(f"color=black:s={w // 2}x{h // 2}:r=30:d={n / 30}[t{j}]")
    layout = "|".join(f"{c * (w // 2)}_{r * (h // 2)}" for r in range(2) for c in range(cols))
    graph = ";".join(filters) + ";" + "".join(f"[t{j}]" for j in range(2 * cols)) + f"xstack=inputs={2 * cols}:layout={layout}[g]"
    grid = out / "grid.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[g]", "-threads", "4",
                    "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", str(grid)], check=True)
    print(f"wrote {grid}", flush=True)

    stills = out / "stills"
    stills.mkdir(exist_ok=True)
    for s in SIDES:
        for a, b in report["segments"][s]:
            mid = (a + b - 1) // 2
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(grid), "-vf", f"select=eq(n\\,{mid})", "-frames:v", "1",
                            str(stills / f"{s.lower()}_seg{a:04d}-{b:04d}_f{mid:04d}.png")], check=True)
    print(f"wrote {stills}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) != 6:
        sys.exit(__doc__)
    main(*(Path(a) for a in sys.argv[1:]))
