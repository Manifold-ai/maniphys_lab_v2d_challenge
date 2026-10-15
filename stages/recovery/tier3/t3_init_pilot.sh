#!/usr/bin/env bash
# Initialization pilot: rerun CARI4D from CoCoNet (stage 06) on, with FoundationPose's unreliable frames re-initialized
# from its reliable neighbours (t3_fp_init.py), on copies of finished register-every-frame runs (runs/work_fp).
# Tests the premise that CoCoNet follows its initialization: if it does, the jumps on the replaced frames go away.
# GPU and yielding as t3_rot_pilot.sh: before every episode it stops (exit 4) when rxzhou's chains are back
# (runs/.chain-active-* or a flash_chord container) and never waits for the card (exit 3); t3_init_wait.sh waits.
#   setsid nohup t3_init_pilot.sh ep13_snack_box ep28_squeegee > /dev/null 2>&1 < /dev/null &
# Per episode: runs/work_fp/<ep> is copied to runs/work_init/<ep> (the source is not touched), the pkl is rewritten in
# the copy, stage 06-08 markers and outputs are removed so stages 01-05 are reused. Log: logs/t3_init_pilot.log; CARI4D
# log logs/cari4d_<ep>_init.log. An episode whose copy already has a refined bundle is skipped.
set -u
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
MIN_FREE_MIB=${MIN_FREE_MIB:-44000}
LOG=$T/logs/t3_init_pilot.log
say() { echo "$(date +%m-%d_%T) $*" >> "$LOG"; }
gpu_free() { nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1; }
RX_RUNS=${RX_RUNS:-/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge/runs}
rx_busy() { compgen -G "$RX_RUNS/.chain-active-*" > /dev/null || docker ps --format '{{.Image}}' | grep -q '^flash_chord'; }
for name in "$@"; do
  ep=$((10#${name:2:2})); seq=$(printf episode_%06d "$ep")
  src=$T/runs/work_fp/$name; dst=$T/runs/work_init/$name; c=$dst/cari4d/$seq
  [ -f "$c/inference/refined.pth" ] && { say "$name: already has a refined bundle in work_init, skipped"; continue; }
  [ -f "$src/cari4d/$seq/pipeline_report.json" ] || { say "$name: no finished run in work_fp"; continue; }
  if rx_busy; then say "$name: rxzhou's chain is active, yielding before this episode"; exit 4; fi
  free=$(gpu_free)
  [ "$free" -ge "$MIN_FREE_MIB" ] || { say "$name: only ${free} MiB free on the GPU, not started"; exit 3; }
  if [ ! -f "$c/foundationpose/fp_init.json" ]; then
    rm -rf "$dst"; mkdir -p "$T/runs/work_init" && cp -a "$src" "$dst" || { say "$name: copy failed"; continue; }
    rm -f "$c"/.stages/0[678]_*.json "$c"/inference/coconet.pth "$c"/inference/materialized_inputs.h5 \
      "$c"/inference/refined.pth "$c"/inference/refinement_checkpoint.pth "$c"/inference/*.mp4 "$c"/pipeline_report.json
    r=$(docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp --entrypoint "" -v "$c:/c" -v "$S:/s:ro" \
      v2d_cari4d:latest python /s/t3_fp_init.py /c 2>&1) || { say "$name: t3_fp_init.py failed: $r"; continue; }
    say "$name: copied work_fp to work_init, stages 06-08 cleared; $r"
  fi
  T3_WORK=runs/work_init T3_FP_MODE=register-every-frame T3_LOG_TAG=_init \
    "$S/t3_cari4d_ep.sh" "$name" || { say "$name: CARI4D failed (logs/cari4d_${name}_init.log)"; continue; }
  # stage 05 must have been reused: a rerun would overwrite the rewritten initialization
  rerun=$(grep -h -o '0[1-5]_[a-z_]* elapsed_seconds=[0-9.]*' "$T/logs/cari4d_${name}_init.log" | tr '\n' ' ')
  say "$name: done; $(grep -h -o '0[678]_[a-z_]* elapsed_seconds=[0-9.]*' "$T/logs/cari4d_${name}_init.log" | tr '\n' ' ')${rerun:+ RERAN EARLIER STAGES: $rerun}"
done
say "INIT PILOT DONE"
