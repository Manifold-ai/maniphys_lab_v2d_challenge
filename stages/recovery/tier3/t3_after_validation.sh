#!/usr/bin/env bash
# One-off driver run after the ep01-03 validation queue (2026-10-09): wait for it, re-judge the episodes assembled
# before the silhouette gate existed, rebuild masks for the episodes not yet run with the v2 mask rules, then start
# the full CARI4D queue (finished stages are skipped). Log: logs/after_validation.log.
set -u
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
PY=${T3_PY:-/lab_data/yqchen/v2d/venv/bin/python}
LOG=$T/logs/after_validation.log
say() { echo "$(date +%m-%d_%T) $*" >> "$LOG"; }
cd "$T"
while ps -eo args | grep -q "[t]3_queue_cari4d.sh"; do sleep 120; done
say "validation queue finished"
# ep01 was checked before the gate existed: recheck so its report carries a verdict
for name in ep01_vacuum; do
  ep=${name:2:2}; mv "runs/checks/$name" "runs/checks/${name}_pregate" 2>/dev/null; mkdir -p "runs/checks/$name"
  obj=${name#ep[0-9][0-9]_}
  docker run --rm --user "$(id -u):$(id -g)" --entrypoint "" --network none -e HOME=/tmp -v "$S":/s:ro \
    -v "$T/runs/work/$name":/w:ro -v "$T/input/mesh":/m:ro -v "$T/runs/checks/$name":/o v2d_cari4d:latest \
    python /s/t3_object_check.py "/w/cari4d/episode_0000$ep" /w "/m/$obj/$obj.glb" /o 3 > "logs/check_${name}_regate.log" 2>&1
done
"$PY" "$S/t3_regate.py" "$T" >> "$LOG" 2>&1
say "regate done"
# v2 masks for every episode not yet run with them (ep00/05/20 passed CARI4D on v1 masks and are left as they are)
eps=$(python3 -c "print(','.join(str(e) for e in range(30) if e not in (0, 1, 2, 3, 5, 20)))")
"$PY" "$S/t3_masks.py" --input input --work runs/work --weights /lab_data/yqchen/v2d/weights --episodes "$eps" --recheck > logs/masks_v2_rest.log 2>&1
say "masks v2 rc=$? $(grep -cE '^ok ' logs/masks_v2_rest.log) ok, $(grep -cE '^(SUSPECT|!!)' logs/masks_v2_rest.log) not ok"
rm -f "$T/PAUSE"
setsid nohup "$S/t3_queue_cari4d.sh" > logs/t3_cari4d_queue.stdout 2>&1 < /dev/null &
say "full queue started"
