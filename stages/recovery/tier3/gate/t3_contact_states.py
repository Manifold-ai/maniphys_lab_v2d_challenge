"""Per-frame contact states of a retargeted reference, exactly as t3_dynamics_check judges them, for the post-process.

t3_dynamics_post.py states=<dir> locks the runs the check calls supported, so the rule that rewrites the object and
the rule that judges it are the same one. Frame indices are the reference's, which are the Tier 3 version's.

Usage: t3_contact_states.py <motion set dir> <episodes_metadata.jsonl> <support source> <out dir> [episode,...]
Arguments as t3_dynamics_check.py. Writes <out dir>/epNN.npz with held and supported (bool per frame).
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from t3_dynamics_check import FOOT_TASK, check, supports_of  # noqa: E402


def main():
    mset, meta, sup_src, out = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
    only = {int(x) for x in sys.argv[5].split(",")} if len(sys.argv) > 5 else None
    out.mkdir(parents=True, exist_ok=True)
    done = 0
    for m in map(json.loads, open(meta)):
        ep, seq = m["episode_index"], m["sequence_id"]
        if only and ep not in only:
            continue
        part = mset / "whole_body/soma" / f"sequence_id={seq}" / "robot_name=g1"
        if not (part / "data.parquet").exists():
            continue
        sd = mset / "whole_body/reconstructed_stage" if sup_src == "stage" else Path(sup_src)
        pf = check(part, supports_of(sd / f"{seq}_support.usda"), feet=bool(FOOT_TASK.search(m["task"])), frames=True)["per_frame"]
        np.savez(out / f"ep{ep:02d}.npz", held=pf["held"], supported=pf["supported"])
        print(f"ep{ep:02d} T={len(pf['held'])} held {pf['held'].mean():.3f} supported {pf['supported'].mean():.3f}", flush=True)
        done += 1
    if not done:
        raise SystemExit(f"no episode found under {mset}")


if __name__ == "__main__":
    main()
