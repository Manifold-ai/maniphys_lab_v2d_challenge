#!/usr/bin/env bash
# Re-acquisition pilot: CARI4D with FoundationPose registering every frame (t3_cari4d_ep.sh, T3_FP_MODE=
# register-every-frame) on copies of finished episodes, then the same checks and conversion as the baseline.
# GPU: one CARI4D job (refinement peaks near 44 GB) plus the SOMA fit. Start it only in a GPU slot agreed with rxzhou
# (ml40 rule) or from t3_gpu_watch.sh; before every episode it yields (stops, between episodes) when rxzhou's chains
# are back (a runs/.chain-active-* marker in his repository or a flash_chord container) or less than MIN_FREE_MIB is
# free, and it never waits for the card.
#   setsid nohup t3_fp_pilot.sh ep03_contigo_coffee_mug ep02_blue_easter_basket > /dev/null 2>&1 < /dev/null &
# Per episode: runs/work/<ep> is copied to runs/work_fp/<ep> (the baseline is not touched), FoundationPose and later
# stage outputs and markers are removed from the copy so stages 01-04 are reused and 05-08 rerun; outputs:
# runs/checks_fp/<ep>/object_check.json, runs/track_check_fp/<ep>.json, runs/convert_fp/<ep>/,
# runs/tier3_cari4d_fp_pilot/. Log: logs/t3_fp_pilot.log.
set -u
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
PY=${T3_PY:-/lab_data/yqchen/v2d/venv/bin/python}
WEIGHTS=${T3_WEIGHTS:-/lab_data/yqchen/v2d/weights}
SOMA_ASSETS=${T3_SOMA_ASSETS:-/lab_data/yqchen/v2d/soma_assets}
MIN_FREE_MIB=${MIN_FREE_MIB:-44000}
LOG=$T/logs/t3_fp_pilot.log
say() { echo "$(date +%m-%d_%T) $*" >> "$LOG"; }
gpu_free() { nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1; }
RX_RUNS=${RX_RUNS:-/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge/runs}
rx_busy() { compgen -G "$RX_RUNS/.chain-active-*" > /dev/null || docker ps --format '{{.Image}}' | grep -q '^flash_chord'; }
D=(docker run --rm --user "$(id -u):$(id -g)" --entrypoint "" --network none -e HOME=/tmp -w /workspace/v2d_cari4d/lib/cari4d)
for name in "$@"; do
  ep=$((10#${name:2:2})); obj=${name#ep[0-9][0-9]_}; seq=$(printf episode_%06d "$ep")
  if rx_busy; then say "$name: rxzhou's chain is active again, yielding before this episode"; exit 4; fi
  free=$(gpu_free)
  [ "$free" -ge "$MIN_FREE_MIB" ] || { say "$name: only ${free} MiB free on the GPU, not started (agree a slot first)"; exit 3; }
  src=$T/runs/work/$name; dst=$T/runs/work_fp/$name
  [ -f "$src/cari4d/$seq/pipeline_report.json" ] || { say "$name: no finished baseline in $src"; continue; }
  if [ ! -d "$dst" ]; then
    mkdir -p "$T/runs/work_fp" && cp -a "$src" "$dst" || { say "$name: copy failed"; continue; }
    c=$dst/cari4d/$seq
    rm -f "$c"/.stages/0[5-8]_*.json "$c"/foundationpose/"$seq".pkl* "$c"/inference/* "$c"/pipeline_report.json
    rm -rf "$c"/foundationpose/debug
    say "$name: copied to work_fp, stages 05-08 cleared"
  fi
  T3_WORK=runs/work_fp T3_FP_MODE=register-every-frame T3_LOG_TAG=_fp "$S/t3_cari4d_ep.sh" "$name" \
    || { say "$name: CARI4D failed (logs/cari4d_${name}_fp.log)"; continue; }
  say "$name: CARI4D done $(grep -h 'elapsed_seconds' "$T/logs/cari4d_${name}_fp.log" | grep -o '0[5-8]_[a-z_]* elapsed_seconds=[0-9.]*' | tr '\n' ' ')"
  mkdir -p "$T/runs/checks_fp/$name" "$T/runs/convert_fp/$name" "$T/runs/track_check_fp"
  "${D[@]}" -v "$S":/s:ro -v "$dst":/w:ro -v "$T/input/mesh":/m:ro -v "$T/runs/checks_fp/$name":/o v2d_cari4d:latest \
    python /s/t3_object_check.py "/w/cari4d/$seq" /w "/m/$obj/$obj.glb" /o 3 > "$T/logs/check_fp_$name.log" 2>&1 || say "$name: check failed"
  conv=$T/runs/convert_fp/$name
  run_c() { "${D[@]}" $1 -v "$S":/s:ro -v "$dst/cari4d/$seq":/e:ro -v "$WEIGHTS/cari4d":/w:ro -v "$SOMA_ASSETS":/a:ro \
              -v "$T/runs/floor":/f:ro -v "$conv":/o/"$name" v2d_cari4d:latest python /s/t3_convert_ep.py "${@:2}"; }
  run_c "" decode /e /w /o/"$name" > "$T/logs/decode_fp_$name.log" 2>&1 || { say "$name: decode failed"; continue; }
  run_c "--gpus all" soma /o/"$name" /a > "$T/logs/soma_fp_$name.log" 2>&1 || { say "$name: soma failed"; continue; }
  run_c "" residual /o/"$name" /a > "$T/logs/residual_fp_$name.log" 2>&1 || say "$name: residual failed"
  run_c "" world /o/"$name" /f/floor_fit.json /a > "$T/logs/world_fp_$name.log" 2>&1 || { say "$name: world failed"; continue; }
  "$PY" "$S/t3_convert_ep.py" assemble "$conv" "$T/input" "$ep" "$T/runs/tier3_cari4d_fp_pilot" > "$T/logs/assemble_fp_$name.log" 2>&1 \
    || say "$name: assemble failed"
  "${D[@]}" -v "$S":/s:ro -v "$T":/t -v "$SOMA_ASSETS":/a:ro v2d_cari4d:latest python /s/t3_track_check.py "/t/runs/convert_fp/$name" \
    "/t/runs/work_fp/$name" "/t/input/mesh/$obj/$obj.glb" /a "/t/runs/track_check_fp/$name.json" > "$T/logs/track_fp_$name.log" 2>&1 \
    || say "$name: track check failed"
  say "$name: pilot done; lost frames $(grep -o '"lost_fraction": [0-9.]*' "$T/runs/track_check_fp/$name.json") (baseline $(grep -o '"lost_fraction": [0-9.]*' "$T/runs/track_check/$name.json"))"
done
say "PILOT DONE"
