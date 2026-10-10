"""Probe for t3_masks.choose_prompt_frame on the cached detector boxes (no GPU, no detector run).

Expected picks were read off the frames by eye on 2026-10-10 (the boxes drawn on the detector frames): ep01 the
vacuum leaning on the stool (not the tripod boxed as "vacuum" once), ep06 the monitor on the round table under the
person's hands (not a far monitor on a back desk), ep10 the white desk being lowered (not a background desk; its box
was labelled "... table" and used to be dropped as a support). Each must overlap the pick at IoU >= 0.5.
Injected defects, each must make the probe fail: the track rule off (MOVED_DIAGONALS = inf) and the own-support
rule off (labels naming the object still dropped as supports).

    python probe_prompt_pick.py <tier3 work dir> <tier3 input dir>
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t3_masks as tm

EXPECTED = {
    "ep01_vacuum": {"x0": 733, "y0": 619, "x1": 856, "y1": 851},
    "ep06_monitor": {"x0": 883, "y0": 495, "x1": 971, "y1": 634},
    "ep10_white_desk": {"x0": 640, "y0": 568, "x1": 989, "y1": 899},
}


def picks(work: Path, meta: dict) -> dict:
    out = {}
    for name in EXPECTED:
        m = meta[name]
        pick = tm.choose_prompt_frame(work / name / "detect", None, m["frames"], "a " + m["object"].replace("_", " "),
                                      "", 0.3, 13, object_name=m["object"])
        out[name] = pick["candidates"][0]["box"]
    return out


def passes(work: Path, meta: dict) -> dict:
    return {name: tm.iou(box, EXPECTED[name]) >= 0.5 for name, box in picks(work, meta).items()}


def main() -> None:
    work, inp = Path(sys.argv[1]), Path(sys.argv[2])
    rows = [json.loads(l) for l in (inp / "meta/episodes_metadata.jsonl").read_text().splitlines()]
    meta = {f"ep{r['episode_index']:02d}_{r['object']}": r for r in rows}
    tm.extract = lambda *a, **k: None  # every sampled frame is cached; never decode the video
    real = passes(work, meta)
    moved = tm.MOVED_DIAGONALS
    tm.MOVED_DIAGONALS = float("inf")
    no_tracks = passes(work, meta)
    tm.MOVED_DIAGONALS = moved
    is_support = tm.is_support
    # Defect: the previous rule, a label naming a support word is a support even when it also names the object.
    tm.is_support = lambda label, support_words, want, own_support: any(tm.label_matches(label, s) for s in support_words)
    no_own_support = passes(work, meta)
    tm.is_support = is_support
    ok = all(real.values()) and not all(no_tracks.values()) and not all(no_own_support.values())
    print(json.dumps({"real": real, "defect_no_tracks": no_tracks, "defect_no_own_support": no_own_support, "ok": ok}, indent=1))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
