#!/usr/bin/env bash
# 10-17: the calibrated-intrinsics (GB) version, from the world step's outputs to the gate, unattended; stops before
# delivery (delivery changes what rxzhou reads, so it waits for the user). Waits for t3_gb3_register.sh (GB3_REGISTER_DONE),
# then, each step checked, stopping with GB_CHAIN_FAILED <step>:
#   1. assemble tier3_cari4d_gb_best{,_suspect}: best's per-episode pick (tier3_cari4d_f830_best.selection.json) with each
#      convert dir swapped for its _gb3 re-expression, the same main/_suspect split; selection json written alongside
#   2. physics check of gb_best                           (t3_physics_all.sh)
#   3. supports of gb_best in the GB world                (t3_support.py, T3_FLOOR_FIT / T3_REGISTER = the _gb3 files)
#   4. depth post-process -> tier3_cari4d_gb_best_dr2s     (t3_depth_post.py, --move-human=3d, as best_dr2s)
#   5. physics check of gb_best_dr2s
#   6. dynamics post-process -> tier3_cari4d_gb_best_dr2s_dyn7 (t3_dynamics_post.py, as best_dr2s_dyn7)
#   7. all checks of gb_best_dr2s_dyn7: alignment, physics, rxzhou's gate, our supports (gate/chain_check.sh, set gbdyn7)
# Log: logs/gb_chain.log, last line GB_CHAIN_DONE.
#   setsid nohup stages/recovery/tier3/t3_gb_chain.sh > $T/logs/gb_chain.log 2>&1 &
set -u
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
PY=${T3_PY:-/lab_data/yqchen/v2d/venv/bin/python}
GPY=${T3_GPY:-/lab_data/yqchen/v2d/gate/venv/bin/python}
B=tier3_cari4d_gb_best
log() { echo "$(date '+%m-%d %T') $*"; }
fail() { log "GB_CHAIN_FAILED $*"; exit 1; }
cd "$T" || exit 1
log "deployed: $(cat code/DEPLOYED)"
until grep -q -E "GB3_REGISTER_DONE|GB3_FAILED" logs/gb3_register.log 2>/dev/null; do sleep 60; done
grep -q GB3_REGISTER_DONE logs/gb3_register.log || fail "t3_gb3_register.sh did not finish: $(tail -1 logs/gb3_register.log)"
for v in $B ${B}_dr2s ${B}_dr2s_dyn7; do [ -e "runs/$v" ] || [ -e "runs/${v}_suspect" ] && fail "runs/$v exists"; done

# 1. assemble
"$PY" - "$T" <<'EOF' || fail "selection"
import json, sys
from pathlib import Path
t = Path(sys.argv[1])
rows = json.loads((t / "runs/tier3_cari4d_f830_best.selection.json").read_text())
for r in rows:
    r["convert_f830"] = r["convert"]
    r["convert"] = r["convert"] + "_gb3"
    if not (t / "runs" / r["convert"] / r["episode"] / "object_world.npz").exists():
        raise SystemExit(f"{r['episode']}: no {r['convert']} world output")
(t / "runs/tier3_cari4d_gb_best.selection.json").write_text(json.dumps(rows, indent=1))
print(len(rows), "episodes")
EOF
"$PY" -c 'import json,sys; [print(r["episode_index"], r["episode"], r["convert"], int(bool(r["object_check_ok"]))) for r in json.load(open(sys.argv[1]))]' \
  runs/$B.selection.json | while read -r ep name conv ok; do
    dst=runs/$B; [ "$ok" = 1 ] || dst=${dst}_suspect
    "$PY" "$S/t3_convert_ep.py" assemble "runs/$conv/$name" input "$ep" "$dst" > /dev/null 2>&1 && echo "$name $conv -> $dst" || echo "$name assemble FAILED"
  done > logs/assemble_$B.log
grep -q FAILED logs/assemble_$B.log && fail "assemble (logs/assemble_$B.log)"
n=$(ls runs/$B/data/chunk-000/*.parquet runs/${B}_suspect/data/chunk-000/*.parquet 2>/dev/null | wc -l)
[ "$n" = 30 ] || fail "assemble: $n episodes, want 30"
log "1 assembled $B: $n episodes ($(ls runs/${B}_suspect/data/chunk-000/*.parquet 2>/dev/null | wc -l) suspect)"

# 2-3. physics and supports
"$S/t3_physics_all.sh" $B; grep -q DONE logs/physics_$B.log || fail "physics $B"
log "2 physics $B"
T3_FLOOR_FIT=floor_fit_gb3.json T3_REGISTER=camera_register_gb3.json OMP_NUM_THREADS=4 \
  "$GPY" "$S/t3_support.py" "$T" $B runs/physics/$B dev/walls runs/support/$B > logs/support_$B.log 2>&1 || fail "support (logs/support_$B.log)"
log "3 supports: $(ls runs/support/$B | wc -l) files"

# 4-6. post-processes
"$GPY" "$S/t3_depth_post.py" "$T" $B runs/$B.selection.json runs/support/$B runs/physics/$B ${B}_dr2s --move-human=3d \
  > logs/depth_post_${B}_dr2s.log 2>&1 || fail "depth post (logs/depth_post_${B}_dr2s.log)"
log "4 $B"_dr2s
"$S/t3_physics_all.sh" ${B}_dr2s; grep -q DONE logs/physics_${B}_dr2s.log || fail "physics ${B}_dr2s"
log "5 physics ${B}_dr2s"
"$GPY" "$S/t3_dynamics_post.py" "$T" ${B}_dr2s runs/physics/${B}_dr2s ${B}_dr2s_dyn7 > logs/dynamics_post_${B}_dr2s_dyn7.log 2>&1 \
  || fail "dynamics post (logs/dynamics_post_${B}_dr2s_dyn7.log)"
log "6 ${B}_dr2s_dyn7"

# 7. checks
SEL=$B.selection.json SUP=$B bash "$S/gate/chain_check.sh" ${B}_dr2s_dyn7 gbdyn7 > logs/chain_check_gbdyn7.log 2>&1
grep -q CHAIN_DONE logs/chain_check_gbdyn7.log || fail "chain check (logs/chain_check_gbdyn7.log)"
log "7 checks: gate $(tail -3 /lab_data/yqchen/v2d/gate/logs/p2_gbdyn7.txt | tr '\n' ' ' | cut -c1-300)"
log "   our supports: $(tail -2 /lab_data/yqchen/v2d/gate/logs/oursup_gbdyn7.txt | tr '\n' ' ' | cut -c1-300)"
log GB_CHAIN_DONE
