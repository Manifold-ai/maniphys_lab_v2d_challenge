"""Apply the silhouette quality gate to episodes already assembled, in both directions: an episode whose
object_check.json says ok=false goes from runs/tier3_cari4d/ to runs/tier3_cari4d_suspect/, one that says ok=true goes
back, parquet and metadata together. An episode with no verdict (no report, or a report from before the gate) is left
where it is and reported: "not judged" is not "failed" (the first run moved ep00 and ep20 for exactly that reason).
Used for episodes assembled before the gate existed, and again after the check itself changes (the 10-10 fix to its
renderer); the queue routes new episodes itself.

    python t3_regate.py <tier3 root>
"""

import json
import shutil
import sys
from pathlib import Path


def main() -> None:
    root = Path(sys.argv[1])
    main_dir, suspect = root / "runs" / "tier3_cari4d", root / "runs" / "tier3_cari4d_suspect"
    for here, there, belongs in ((main_dir, suspect, True), (suspect, main_dir, False)):
        for pq in sorted((here / "data" / "chunk-000").glob("episode_*.parquet")):
            ep = int(pq.stem.split("_")[1])
            meta_path = here / "meta" / f"episode_{ep:06d}.metadata.json"
            name = f"ep{ep:02d}_{json.loads(meta_path.read_text())['object']}"
            check = root / "runs" / "checks" / name / "object_check.json"
            verdict = json.loads(check.read_text()).get("ok") if check.exists() else None
            if verdict is None:
                print(f"{name}: no gate verdict yet; left in {here.name}, recheck it")
                continue
            if verdict is belongs:
                print(f"{name}: stays in {here.name} (gate ok={verdict})")
                continue
            for src, sub in ((pq, "data/chunk-000"), (meta_path, "meta")):
                dst = there / sub / src.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), dst)
            print(f"{name}: moved {here.name} -> {there.name} (gate ok={verdict})")


if __name__ == "__main__":
    main()
