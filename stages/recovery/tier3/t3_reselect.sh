#!/usr/bin/env bash
# Re-run episodes whose prompt pick changed under the moved-track rule of t3_masks.py (2026-10-10: ep01/06/10 picked
# a same-class background thing; the rule also changes ep03/07/13/19/22). The baseline is not touched: each episode
# gets runs/work_v2/<ep> with only the cached detector frames and boxes copied from runs/work/<ep>, then masks (SAM2),
# CARI4D, the object check, conversion with the fixed focal and floor fit (runs/floor/focal.json, floor_fit_f830.json;
# no refit, the other episodes keep their world), assemble into runs/tier3_cari4d_v2sel_f830/, and the track check
# into runs/track_check_v2sel/ to compare with runs/track_check/.
# GPU: SAM2, then one CARI4D job (refinement peaks near 44 GB). Same yield rule as t3_fp_pilot.sh: before every
# episode it stops when rxzhou's chains are back or less than MIN_FREE_MIB is free; it never waits for the card.
# Start it from t3_gpu_watch.sh (JOB=t3_reselect.sh). Log: logs/t3_reselect.log.
set -u
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
PY=${T3_PY:-/lab_data/yqchen/v2d/venv/bin/python}
WEIGHTS=${T3_WEIGHTS:-/lab_data/yqchen/v2d/weights}
SOMA_ASSETS=${T3_SOMA_ASSETS:-/lab_data/yqchen/v2d/soma_assets}
MIN_FREE_MIB=${MIN_FREE_MIB:-44000}
OUT=${OUT:-tier3_cari4d_v2sel_f830}
LOG=$T/logs/t3_reselect.log
say() { echo "$(date +%m-%d_%T) $*" >> "$LOG"; }
gpu_free() { nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1; }
RX_RUNS=${RX_RUNS:-/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge/runs}
rx_busy() { compgen -G "$RX_RUNS/.chain-active-*" > /dev/null || docker ps --format '{{.Image}}' | grep -q '^flash_chord'; }
D=(docker run --rm --user "$(id -u):$(id -g)" --entrypoint "" --network none -e HOME=/tmp -w /workspace/v2d_cari4d/lib/cari4d)
cd "$T" || exit 2
for name in "$@"; do
  ep=$((10#${name:2:2})); obj=${name#ep[0-9][0-9]_}; seq=$(printf episode_%06d "$ep")
  if rx_busy; then say "$name: rxzhou's chain is active again, yielding before this episode"; exit 4; fi
  free=$(gpu_free)
  [ "$free" -ge "$MIN_FREE_MIB" ] || { say "$name: only ${free} MiB free on the GPU, not started (agree a slot first)"; exit 3; }
  src=$T/runs/work/$name; dst=$T/runs/work_v2/$name
  [ -d "$src/detect" ] || { say "$name: no cached detections in $src"; continue; }
  if [ ! -d "$dst" ]; then
    mkdir -p "$dst" && cp -a "$src/detect" "$dst/detect" || { say "$name: copy failed"; continue; }
    say "$name: work_v2 seeded with the cached detections"
  fi
  "$PY" "$S/t3_masks.py" --input input --work runs/work_v2 --weights "$WEIGHTS" --episodes "$ep" > "$T/logs/masks_v2_$name.log" 2>&1 \
    || { say "$name: masks failed (logs/masks_v2_$name.log)"; continue; }
  say "$name: masks $(grep -E '^(ok|SUSPECT) ' "$T/logs/masks_v2_$name.log" | tail -1) $(grep -o '"prompt_frame": [0-9]*' "$dst/mask_report.json")"
  T3_WORK=runs/work_v2 T3_LOG_TAG=_v2 "$S/t3_cari4d_ep.sh" "$name" || { say "$name: CARI4D failed (logs/cari4d_${name}_v2.log)"; continue; }
  say "$name: CARI4D done"
  mkdir -p "$T/runs/checks_v2/$name" "$T/runs/convert_v2/$name" "$T/runs/track_check_v2sel"
  "${D[@]}" -v "$S":/s:ro -v "$dst":/w:ro -v "$T/input/mesh":/m:ro -v "$T/runs/checks_v2/$name":/o v2d_cari4d:latest \
    python /s/t3_object_check.py "/w/cari4d/$seq" /w "/m/$obj/$obj.glb" /o 3 > "$T/logs/check_v2_$name.log" 2>&1 || say "$name: check failed"
  conv=$T/runs/convert_v2/$name
  run_c() { "${D[@]}" $1 -v "$S":/s:ro -v "$dst/cari4d/$seq":/e:ro -v "$WEIGHTS/cari4d":/w:ro -v "$SOMA_ASSETS":/a:ro \
              -v "$T/runs/floor":/f:ro -v "$conv":/o/"$name" v2d_cari4d:latest python /s/t3_convert_ep.py "${@:2}"; }
  run_c "" decode /e /w /o/"$name" > "$T/logs/decode_v2_$name.log" 2>&1 || { say "$name: decode failed"; continue; }
  run_c "--gpus all" soma /o/"$name" /a > "$T/logs/soma_v2_$name.log" 2>&1 || { say "$name: soma failed"; continue; }
  run_c "" residual /o/"$name" /a > "$T/logs/residual_v2_$name.log" 2>&1 || say "$name: residual failed"
  run_c "" focal /o/"$name" /f/focal.json /a > "$T/logs/focal_v2_$name.log" 2>&1 || { say "$name: focal failed"; continue; }
  run_c "" world /o/"$name" /f/floor_fit_f830.json /a > "$T/logs/world_v2_$name.log" 2>&1 || { say "$name: world failed"; continue; }
  # same split as t3_queue_cari4d.sh: a failed silhouette gate goes to the _suspect directory, kept for diagnosis
  out=$T/runs/$OUT
  python3 -c "import json,sys; sys.exit(0 if json.load(open('$T/runs/checks_v2/$name/object_check.json')).get('ok', True) else 1)" \
    2>/dev/null || out=${out}_suspect
  "$PY" "$S/t3_convert_ep.py" assemble "$conv" "$T/input" "$ep" "$out" > "$T/logs/assemble_v2_$name.log" 2>&1 \
    && say "$name: -> $(basename "$out")" || say "$name: assemble failed"
  "${D[@]}" -v "$S":/s:ro -v "$T":/t -v "$SOMA_ASSETS":/a:ro v2d_cari4d:latest python /s/t3_track_check.py "/t/runs/convert_v2/$name" \
    "/t/runs/work_v2/$name" "/t/input/mesh/$obj/$obj.glb" /a "/t/runs/track_check_v2sel/$name.json" > "$T/logs/track_v2_$name.log" 2>&1 \
    || say "$name: track check failed"
  say "$name: done; lost frames $(grep -o '"lost_fraction": [0-9.]*' "$T/runs/track_check_v2sel/$name.json") (baseline $(grep -o '"lost_fraction": [0-9.]*' "$T/runs/track_check/$name.json" 2>/dev/null || echo none))"
done
say "RESELECT DONE"
