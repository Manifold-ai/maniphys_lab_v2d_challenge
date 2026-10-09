#!/usr/bin/env bash
# Tier 3 CARI4D queue: per episode, CARI4D on the official mesh (t3_cari4d_ep.sh), then the silhouette check
# (t3_object_check.py, CPU). Serial. Before each episode:
#   - waits while $T3_ROOT/PAUSE exists (lets a short GPU job run between episodes);
#   - waits until the L40S has at least MIN_FREE_MIB free (CARI4D refinement peaks near 44 GB of 46 GB, so this
#     effectively waits for an idle card instead of colliding with a FlashCHORD run).
# Skips episodes whose CARI4D already finished (pipeline_report verdict PASS).
#   setsid nohup t3_queue_cari4d.sh [episodes...] > /dev/null 2>&1 < /dev/null &      (default: all 30)
# Progress: logs/t3_cari4d_queue.log. Stop: kill the process group.
set -u
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
MIN_FREE_MIB=${MIN_FREE_MIB:-44000}
QLOG=$T/logs/t3_cari4d_queue.log
say() { echo "$(date +%m-%d_%T) $*" >> "$QLOG"; }
wait_turn() {
  while [ -e "$T/PAUSE" ]; do say "paused ($T/PAUSE)"; sleep 60; done
  while true; do
    free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
    [ "$free" -ge "$MIN_FREE_MIB" ] && return
    say "waiting for GPU: ${free} MiB free < ${MIN_FREE_MIB}"
    sleep 300
  done
}
cd "$T"
eps=${*:-$(seq 0 29)}
for ep in $eps; do
  name=$(python3 -c "import json
for l in open('input/meta/episodes_metadata.jsonl'):
    m=json.loads(l)
    if m['episode_index']==$ep: print('ep%02d_%s' % ($ep, m['object']))")
  W=runs/work/$name
  rep="$W/cari4d/episode_$(printf %06d "$ep")/pipeline_report.json"
  if [ -f "$rep" ] && python3 -c "import json,sys; sys.exit(0 if json.load(open('$rep')).get('verdict')=='PASS' else 1)"; then
    say "$name skip: CARI4D done"
  else
    wait_turn
    say "$name cari4d start"
    "$S/t3_cari4d_ep.sh" "$name"
    rc=$?
    say "$name cari4d rc=$rc"
    [ "$rc" = 0 ] || continue
  fi
  obj=${name#ep[0-9][0-9]_}
  out=runs/checks/$name
  [ -f "$out/object_check.json" ] && continue
  mkdir -p "$out"
  docker run --rm --user "$(id -u):$(id -g)" --entrypoint "" --network none -e HOME=/tmp \
    -v "$S":/s:ro -v "$T/$W":/w:ro -v "$T/input/mesh":/m:ro -v "$T/$out":/o \
    v2d_cari4d:latest python /s/t3_object_check.py "/w/cari4d/episode_$(printf %06d "$ep")" /w "/m/$obj/$obj.glb" /o 3 > "logs/check_$name.log" 2>&1
  summ=$(python3 -c "import json;r=json.load(open('$out/object_check.json'))['all_p10_p50_p90'];print('iou_p50=%s depth_factor_p10/50/90=%s centroid_p50=%s' % (r['iou_visible'][1], r['depth_factor'], r['centroid_px'][1]))" 2>/dev/null)
  say "$name check $summ"
done
say "QUEUE DONE"
