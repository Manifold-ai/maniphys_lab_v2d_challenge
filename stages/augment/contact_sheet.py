"""Thumbnail sheets of fetched candidate assets, for picking replacements by eye.

Each candidate is drawn standing on its assumed up axis (+Y for glTF unless its manifest entry carries "up"), seen
from a three-quarter view, as shaded surface samples. A candidate drawn lying down or upside down has a different up
axis in its file; note the axis when picking it, and swap_pilot.py will use it. Tile 0 is the official mesh on its
up axis from official_up.json, as the reference. Each label: tile number, uid prefix, height / footprint width ratio
(official in the first tile), face count, licence, name.
CPU and ffmpeg only, no extra Python packages:

    python contact_sheet.py <candidates dir> <official mesh .glb> <out dir> [--per-page N]
"""

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
import trimesh

AXES = {"+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0), "-y": (0, -1, 0), "+z": (0, 0, 1), "-z": (0, 0, -1)}
OFFICIAL_UP = Path(__file__).with_name("official_up.json")
TILE = 280
LABEL = 44
COLS = 8
SAMPLES = 60000
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
AZIMUTH, ELEVATION = np.radians(35), np.radians(20)
LIGHT = np.array([0.4, 0.8, 0.45]) / np.linalg.norm([0.4, 0.8, 0.45])


def upright_basis(up: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Rows (a1, up, a2): a1 the footprint's principal axis, so every asset is seen from a comparable side."""
    up = up / np.linalg.norm(up)
    helper = np.array([1.0, 0.0, 0.0]) if abs(up[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    e1 = np.cross(up, helper)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(up, e1)
    flat = (pts - pts.mean(0)) @ np.stack([e1, e2]).T
    _, vecs = np.linalg.eigh(np.cov(flat.T))
    a1 = vecs[0, 1] * e1 + vecs[1, 1] * e2
    a1 /= np.linalg.norm(a1)
    return np.stack([a1, up, np.cross(a1, up)])


def render(mesh: trimesh.Trimesh, up: np.ndarray) -> tuple[np.ndarray, float]:
    np.random.seed(0)
    pts, face = trimesh.sample.sample_surface(mesh, SAMPLES)
    normals = mesh.face_normals[face]
    basis = upright_basis(up, pts)
    p, nrm = pts @ basis.T, normals @ basis.T
    ext = p.max(0) - p.min(0)
    ratio = float(ext[1] / max(ext[0], ext[2], 1e-9))
    ca, sa, ce, se = np.cos(AZIMUTH), np.sin(AZIMUTH), np.cos(ELEVATION), np.sin(ELEVATION)
    yaw = np.array([[ca, 0, sa], [0, 1, 0], [-sa, 0, ca]])
    pitch = np.array([[1, 0, 0], [0, ce, -se], [0, se, ce]])
    view = pitch @ yaw
    q, nq = (p - (p.min(0) + p.max(0)) / 2) @ view.T, nrm @ view.T
    span = max(np.ptp(q[:, 0]), np.ptp(q[:, 1]), 1e-9)
    s = (TILE - 24) / span
    u = np.round(q[:, 0] * s + TILE / 2).astype(int).clip(0, TILE - 2)
    v = np.round(-q[:, 1] * s + TILE / 2).astype(int).clip(0, TILE - 2)
    shade = 0.3 + 0.7 * np.abs(nq @ LIGHT)
    order = np.argsort(q[:, 2])  # far to near: nearer points are written last and stay on top
    img = np.full((TILE, TILE, 3), 245.0)
    colour = shade[order, None] * np.array([70.0, 110.0, 200.0])
    for dy in (0, 1):
        for dx in (0, 1):
            img[v[order] + dy, u[order] + dx] = colour
    return img, ratio


def load(path: Path) -> trimesh.Trimesh:
    mesh = trimesh.load(path, force="mesh", process=False)
    return trimesh.Trimesh(np.asarray(mesh.vertices, np.float64), np.asarray(mesh.faces), process=False)


def page(tiles: list[np.ndarray], labels: list[str], out: Path) -> None:
    rows = (len(tiles) + COLS - 1) // COLS
    sheet = np.full((rows * (TILE + LABEL), COLS * TILE, 3), 255, np.uint8)
    for j, t in enumerate(tiles):
        r, c = divmod(j, COLS)
        sheet[r * (TILE + LABEL): r * (TILE + LABEL) + TILE, c * TILE: (c + 1) * TILE] = t.clip(0, 255).astype(np.uint8)
        sheet[r * (TILE + LABEL): (r + 1) * (TILE + LABEL), c * TILE] = 180
    draws = []
    for j, text in enumerate(labels):
        r, c = divmod(j, COLS)
        for k, line in enumerate(text.split("\n")):
            safe = line.replace("\\", "").replace(":", r"\:").replace("'", "").replace("%", "")
            draws.append(f"drawtext=fontfile={FONT}:text='{safe}':x={c * TILE + 6}:y={r * (TILE + LABEL) + TILE + 3 + k * 20}:"
                         f"fontsize=15:fontcolor=black")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{sheet.shape[1]}x{sheet.shape[0]}",
                    "-i", "-", "-vf", ",".join(draws), str(out)], input=sheet.tobytes(), check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cands")
    ap.add_argument("official")
    ap.add_argument("out")
    ap.add_argument("--per-page", type=int, default=40)
    a = ap.parse_args()
    cands, official, out = Path(a.cands), Path(a.official), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    up_table = json.loads(OFFICIAL_UP.read_text())
    off_img, off_ratio = render(load(official), np.array(AXES[up_table[official.stem]["up"]], np.float64))
    items = [x | {"group": g} for g, v in json.loads((cands / "manifest.json").read_text()).items() for x in v if "file" in x]
    index, tiles, labels = [], [], []
    for n, x in enumerate(items, start=1):
        try:
            img, ratio = render(load(cands / x["file"]), np.array(AXES[x.get("up", "+y")], np.float64))
            info = f"h/w {ratio:.2f}"
        except Exception as e:  # noqa: BLE001 - one broken download must not stop the sheet
            img, ratio, info = np.full((TILE, TILE, 3), 200.0), None, f"load failed: {type(e).__name__}"
        name = (x.get("name") or "")[:30]
        tiles.append(img)
        licence = {"cc0": "CC0", "by": "CC-BY"}.get(x["licence"], x["licence"])
        labels.append(f"#{n} {x['uid'][:8]} {info}\n{licence} {x['faces'] // 1000}k {name}")
        index.append({"tile": n, "uid": x["uid"], "file": x["file"], "group": x["group"], "name": x.get("name"),
                      "licence": x["licence"], "author": x.get("author"), "url": x.get("url"), "faces": x["faces"],
                      "height_over_width": None if ratio is None else round(ratio, 3)})
        print(f"{n}/{len(items)}", flush=True)
    per = a.per_page - 1  # tile 0 of every page is the official reference
    for p in range(0, len(tiles), per):
        page([off_img] + tiles[p: p + per], [f"#0 OFFICIAL {official.stem}\nh/w {off_ratio:.2f} (reference)"] + labels[p: p + per],
             out / f"sheet_{p // per + 1:02d}.png")
    (out / "index.json").write_text(json.dumps(index, indent=1))


if __name__ == "__main__":
    main()
