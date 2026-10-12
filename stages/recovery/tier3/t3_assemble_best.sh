#!/usr/bin/env bash
# Assemble one Tier 3 version from the best reconstruction of each episode. CPU only.
# Candidates per episode (all three share the world step: floor_fit_f830.json, body scaled, other cameras registered):
#   base   runs/convert     runs/track_check        runs/checks
#   v2sel  runs/convert_v2  runs/track_check_v2sel  runs/checks_v2
#   fp     runs/convert_fp  runs/track_check_fp     runs/checks_fp
# Best = lowest track-check lost_fraction; on a tie the earlier one in that list. OVERRIDE="ep19_cane=convert_pivot ..."
# replaces an episode's convert dir (its track check must be at <convert dir>/<ep>/track_check.json). An episode goes to
# ${OUT}_suspect when its chosen version's object check is not ok (as t3_queue_cari4d.sh).
#   OUT=tier3_cari4d_f830_best OVERRIDE=... t3_assemble_best.sh
# Output: runs/$OUT{,_suspect}/, runs/$OUT.selection.json (what was chosen and why), logs/assemble_$OUT.log.
set -u
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
PY=${T3_PY:-/lab_data/yqchen/v2d/venv/bin/python}
OUT=${OUT:?set OUT}
[ -e "$T/runs/$OUT" ] || [ -e "$T/runs/${OUT}_suspect" ] && { echo "runs/$OUT exists; pick a new name"; exit 1; }
SEL=$T/runs/$OUT.selection.json
"$PY" - "$T" "${OVERRIDE:-}" "$SEL" <<'EOF' || exit 1
import json, sys
from pathlib import Path
t, override, sel = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
cands = [("base", "convert", "track_check", "checks"), ("v2sel", "convert_v2", "track_check_v2sel", "checks_v2"),
         ("fp", "convert_fp", "track_check_fp", "checks_fp")]
over = dict(x.split("=", 1) for x in override.split())
meta = [json.loads(l) for l in (t / "input/meta/episodes_metadata.jsonl").read_text().splitlines() if l.strip()]
rows = []
for m in meta:
    e = f"ep{m['episode_index']:02d}_{m['object']}"
    seen = {}
    for name, conv, tc, chk in cands:
        f, w = t / "runs" / tc / f"{e}.json", t / "runs" / conv / e / "object_world.npz"
        if f.exists() and w.exists():
            c = t / "runs" / chk / e / "object_check.json"
            seen[name] = {"convert": conv, "lost_fraction": json.loads(f.read_text())["lost_fraction"],
                          "object_check_ok": json.loads(c.read_text()).get("ok") if c.exists() else None}
    if not seen:
        raise SystemExit(f"{e}: no finished version")
    best = min(seen, key=lambda k: (seen[k]["lost_fraction"], [c[0] for c in cands].index(k)))
    row = {"episode": e, "episode_index": m["episode_index"], "candidates": seen, "chosen": best, **seen[best]}
    if e in over:
        f = t / "runs" / over[e] / e / "track_check.json"
        if not (t / "runs" / over[e] / e / "object_world.npz").exists() or not f.exists():
            raise SystemExit(f"{e}: override {over[e]} lacks object_world.npz or track_check.json")
        row.update({"chosen": "override", "convert": over[e], "lost_fraction": json.loads(f.read_text())["lost_fraction"],
                    "override_of": best})
    rows.append(row)
sel.write_text(json.dumps(rows, indent=1))
for r in rows:
    print(r["episode_index"], r["episode"], r["convert"], "ok" if r["object_check_ok"] else "suspect", r["lost_fraction"], r["chosen"])
EOF
LOG=$T/logs/assemble_$OUT.log
{
  echo "# $(date '+%F %T') deployed: $(cat "$T/code/DEPLOYED" 2>/dev/null) OVERRIDE=${OVERRIDE:-}"
  "$PY" -c 'import json,sys; [print(r["episode_index"], r["episode"], r["convert"], int(bool(r["object_check_ok"]))) for r in json.load(open(sys.argv[1]))]' "$SEL" |
  while read -r ep name conv ok; do
    dst=$T/runs/$OUT; [ "$ok" = 1 ] || dst=${dst}_suspect
    "$PY" "$S/t3_convert_ep.py" assemble "$T/runs/$conv/$name" "$T/input" "$ep" "$dst" > /dev/null 2>&1 \
      && echo "$name: $conv -> ${dst#$T/runs/}" || echo "$name: assemble FAILED"
  done
  echo DONE
} > "$LOG" 2>&1
cat "$LOG"
