#!/usr/bin/env bash
# Tier 3 CARI4D queue. Per episode, each stage skipped when its output already exists:
#   CARI4D on the official mesh (t3_cari4d_ep.sh, GPU) -> silhouette check (t3_object_check.py, CPU)
#   -> conversion (t3_convert_ep.py): decode (CPU) -> soma (GPU, ~1-2 min) -> residual (CPU) -> assemble (host)
#   into runs/tier3_cari4d/. Serial. Before each GPU stage:
#   - waits while $T3_ROOT/PAUSE exists (lets a short GPU job run between episodes);
#   - waits until the L40S has at least MIN_FREE_MIB free (CARI4D refinement peaks near 44 GB of 46 GB, so this
#     effectively waits for an idle card instead of colliding with a FlashCHORD run).
# Skips episodes whose CARI4D already finished (pipeline_report verdict PASS).
#   setsid nohup t3_queue_cari4d.sh [episodes...] > /dev/null 2>&1 < /dev/null &      (default: all 30)
# Progress: logs/t3_cari4d_queue.log. Stop: kill the process group.
set -u
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
PY=${T3_PY:-/lab_data/yqchen/v2d/venv/bin/python}
WEIGHTS=${T3_WEIGHTS:-/lab_data/yqchen/v2d/weights}
SOMA_ASSETS=${T3_SOMA_ASSETS:-/lab_data/yqchen/v2d/soma_assets}
TIER_OUT=$T/runs/tier3_cari4d
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
  epd="$T/$W/cari4d/episode_$(printf %06d "$ep")"
  out=runs/checks/$name
  if [ ! -f "$out/object_check.json" ]; then
    mkdir -p "$out"
    docker run --rm --user "$(id -u):$(id -g)" --entrypoint "" --network none -e HOME=/tmp \
      -v "$S":/s:ro -v "$T/$W":/w:ro -v "$T/input/mesh":/m:ro -v "$T/$out":/o \
      v2d_cari4d:latest python /s/t3_object_check.py "/w/cari4d/episode_$(printf %06d "$ep")" /w "/m/$obj/$obj.glb" /o 3 > "logs/check_$name.log" 2>&1
    summ=$(python3 -c "import json;j=json.load(open('$out/object_check.json'));r=j['all_p10_p50_p90'];print('ok=%s iou_p50=%s depth_factor_p10/50/90=%s centroid_p50=%s %s' % (j.get('ok'), r['iou_visible'][1], r['depth_factor'], r['centroid_px'][1], j.get('why','')))" 2>/dev/null)
    say "$name check $summ"
  fi
  # episodes failing the silhouette gate are still converted (the data is kept for diagnosis and refinement) but go to
  # a separate directory, so nothing that fails the gate reaches training by default
  if python3 -c "import json,sys; sys.exit(0 if json.load(open('$out/object_check.json')).get('ok', True) else 1)"; then
    TIER_DST=$TIER_OUT
  else
    TIER_DST=$T/runs/tier3_cari4d_suspect
  fi
  conv=$T/runs/convert/$name
  mkdir -p "$conv"
  run_c() {  # $1 = step, $2 = extra docker flags; logs to logs/<step>_<name>.log
    docker run --rm $2 --user "$(id -u):$(id -g)" --entrypoint "" --network none -e HOME=/tmp \
      -w /workspace/v2d_cari4d/lib/cari4d -v "$S":/s:ro -v "$epd":/e:ro -v "$WEIGHTS/cari4d":/w:ro \
      -v "$SOMA_ASSETS":/a:ro -v "$conv":/o v2d_cari4d:latest python /s/t3_convert_ep.py "${@:3}" > "logs/$1_$name.log" 2>&1
  }
  if [ ! -f "$conv/decode_report.json" ]; then
    run_c decode "" decode /e /w /o || { say "$name decode failed"; continue; }
  fi
  if [ ! -f "$conv/soma_params.npz" ]; then
    wait_turn
    run_c soma "--gpus all" soma /o /a || { say "$name soma failed"; continue; }
    fit=$(grep -E "Mean vertex error|Max vertex error" "logs/soma_$name.log" | sed 's/.*INFO:[^:]*://' | tr '\n' ' ')
    say "$name soma fit: $fit"
  fi
  if [ ! -f "$conv/residual_report.json" ]; then
    run_c residual "" residual /o /a || { say "$name residual failed"; continue; }
    res=$(python3 -c "import json;r=json.load(open('$conv/residual_report.json'));c=r['chamfer_cm'];print('chamfer_cm mean=%s p95_frame=%s max_frame=%s within_frame_p95_median=%s' % (c['mean'], c['p95_frame'], c['max_frame'], r['within_frame_p95_cm_median']))")
    say "$name residual $res"
  fi
  if [ ! -f "$TIER_DST/data/chunk-000/episode_$(printf %06d "$ep").parquet" ]; then
    "$PY" "$S/t3_convert_ep.py" assemble "$conv" "$T/input" "$ep" "$TIER_DST" > "logs/assemble_$name.log" 2>&1 \
      && say "$name assembled into $(basename "$TIER_DST")" || say "$name assemble failed"
  fi
done
say "QUEUE DONE"
