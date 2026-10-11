"""Injected-defect probe for t3_physics_check.py on one real episode (run inside v2d_cari4d, after `extract`).

Each defect is written into a copy of the episode's arrays and must raise its own check by at least the number of
frames it touched (relative to the unmodified episode, which may already carry findings of its own):
  - object pushed 0.10 m below its pose along the floor normal for 30 frames  -> object_floor_penetration
  - object moved 0.30 m sideways and back over 40 frames, away from the hands  -> unheld_motion
  - a 0.20 m jump of the object at one frame                                  -> pose_jump
  - the person moved 0.10 m down for 30 frames                                -> feet_penetration

    python probe_physics_check.py <tier3 root> <episode npz> <soma assets> <scratch dir>
"""

import json
import t3_inputs  # noqa: E402  (same directory: released inputs Tier 3 may read)
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t3_physics_check as pc


def frames(out: Path, check: str) -> int:
    rep = json.loads(next(out.glob("ep*.json")).read_text())
    return sum(f["frames"] for f in rep["findings"] if f["check"] == check)


def run(root: Path, arrays: dict, assets: str, scratch: Path, tag: str) -> Path:
    d = scratch / tag
    shutil.rmtree(d, ignore_errors=True)
    (d / "npz").mkdir(parents=True)
    np.savez(d / "npz" / "episode_probe.npz", **arrays)
    pc.check(root, d / "npz", assets, d / "out")
    return d / "out"


def main() -> None:
    root, src, assets, scratch = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
    base = dict(np.load(src))
    m = {json.loads(l)["episode_index"]: json.loads(l) for l in (root / "input/meta/episodes_metadata.jsonl").read_text().splitlines() if l}
    gp = np.asarray(t3_inputs.ground_plane(root, m[int(base["episode_index"])]), np.float64)
    up = gp[:3] / np.linalg.norm(gp[:3]) * (1 if gp[3] > 0 else -1)
    side = np.cross(up, [1.0, 0.0, 0.0])
    side /= np.linalg.norm(side)
    real = run(root, base, assets, scratch, "real")
    per = np.load(next(real.glob("ep*.npz")))

    def window(mask: np.ndarray, length: int) -> int:
        for s0, s1 in pc.runs(mask):
            if s1 - s0 >= length:
                return s0
        raise SystemExit(f"no window of {length} frames for this defect in this episode; pick another episode")

    on_floor = window(np.abs(per["obj_low"]) < pc.FLOOR_TOL_M, 30)  # sinking is only visible where it rests on the floor
    unheld = window(~per["held"], 40)  # moving it is only unheld where no hand is near
    a = len(base["object_pose"]) // 3
    results = {"windows": {"on_floor": on_floor, "unheld": unheld}}

    def defect(tag: str, check: str, touched: int, edit) -> None:
        arr = {k: np.array(v, copy=True) for k, v in base.items()}
        edit(arr)
        got = frames(run(root, arr, assets, scratch, tag), check)
        results[tag] = {"check": check, "real_frames": frames(real, check), "defect_frames": got, "touched": touched,
                        "caught": got - frames(real, check) >= touched}

    def sink(arr):
        arr["object_pose"][on_floor:on_floor + 30, :3] -= 0.10 * up

    def wander(arr):
        t = np.sin(np.linspace(0, np.pi, 40))[:, None]
        arr["object_pose"][unheld:unheld + 40, :3] += 0.30 * t * side

    def jump(arr):
        arr["object_pose"][a + 20:, :3] += 0.20 * side

    def person_down(arr):
        arr["transl"][a:a + 30] -= 0.10 * (up @ np.diag([1.0, -1.0, -1.0]))  # SOMA frame = OpenCV frame flipped in y, z

    defect("sink", "object_floor_penetration", 30, sink)
    defect("wander", "unheld_motion", 20, wander)
    defect("jump", "pose_jump", 1, jump)
    defect("person_down", "feet_penetration", 30, person_down)
    ok = all(r["caught"] for k, r in results.items() if k != "windows")
    print(json.dumps({"results": results, "ok": ok}, indent=1))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
