#!/usr/bin/env bash
# Object-rotation pilot: rerun only CARI4D's post-optimization (stage 07) and render (08) with the object rotation
# optimized (wrapper flag --optimize_object_rotation), on copies of finished register-every-frame runs (runs/work_fp).
# Why: the per-frame orientation jumps in best_hm are CoCoNet's (stage 06): on ep03/02/28/13 FoundationPose's output has
# 3/39/31/13 single-frame turns over 24 deg, CoCoNet's 35/112/88/54, and the default post-optimization freezes the object
# rotation (freeze_object_rotation=True; it moved ep03's rotation at most 0.052 deg), so its temporal term
# (object surface acceleration) never acts on them. With the flag, rotation is optimized under the same temporal,
# contact, silhouette and penetration terms (mhr_opt_refineout.py in the image).
# GPU: refinement peaks near 44 GB. Same yielding as t3_fp_pilot.sh: before every episode it stops (exit 4) when
# rxzhou's chains are back (runs/.chain-active-* or a flash_chord container) and never waits for the card (exit 3).
#   setsid nohup t3_rot_pilot.sh ep03_contigo_coffee_mug ep01_vacuum > /dev/null 2>&1 < /dev/null &
# Per episode: runs/work_fp/<ep> is copied to runs/work_rot/<ep> (the source is not touched), stage 07/08 markers and
# outputs are removed from the copy so stages 01-06 are reused. Log: logs/t3_rot_pilot.log; CARI4D log
# logs/cari4d_<ep>_rot.log. An episode whose copy already has a refined bundle is skipped.
set -u
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
MIN_FREE_MIB=${MIN_FREE_MIB:-44000}
LOG=$T/logs/t3_rot_pilot.log
say() { echo "$(date +%m-%d_%T) $*" >> "$LOG"; }
gpu_free() { nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1; }
RX_RUNS=${RX_RUNS:-/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge/runs}
rx_busy() { compgen -G "$RX_RUNS/.chain-active-*" > /dev/null || docker ps --format '{{.Image}}' | grep -q '^flash_chord'; }
for name in "$@"; do
  ep=$((10#${name:2:2})); seq=$(printf episode_%06d "$ep")
  src=$T/runs/work_fp/$name; dst=$T/runs/work_rot/$name; c=$dst/cari4d/$seq
  [ -f "$c/inference/refined.pth" ] && { say "$name: already has a refined bundle in work_rot, skipped"; continue; }
  [ -f "$src/cari4d/$seq/pipeline_report.json" ] || { say "$name: no finished run in work_fp"; continue; }
  if rx_busy; then say "$name: rxzhou's chain is active, yielding before this episode"; exit 4; fi
  free=$(gpu_free)
  [ "$free" -ge "$MIN_FREE_MIB" ] || { say "$name: only ${free} MiB free on the GPU, not started"; exit 3; }
  if [ ! -d "$dst" ]; then
    mkdir -p "$T/runs/work_rot" && cp -a "$src" "$dst" || { say "$name: copy failed"; continue; }
    rm -f "$c"/.stages/0[78]_*.json "$c"/inference/refined.pth "$c"/inference/refinement_checkpoint.pth "$c"/inference/*.mp4 "$c"/pipeline_report.json
    say "$name: copied work_fp to work_rot, stages 07-08 cleared"
  fi
  T3_WORK=runs/work_rot T3_FP_MODE=register-every-frame T3_LOG_TAG=_rot T3_CARI4D_EXTRA=--optimize_object_rotation \
    "$S/t3_cari4d_ep.sh" "$name" || { say "$name: CARI4D failed (logs/cari4d_${name}_rot.log)"; continue; }
  # every stage before 07 must have been reused, not rerun: the copy is only a test of the post-optimization
  rerun=$(grep -h -o '0[1-6]_[a-z_]* elapsed_seconds=[0-9.]*' "$T/logs/cari4d_${name}_rot.log" | tr '\n' ' ')
  say "$name: done; $(grep -h -o '0[78]_[a-z_]* elapsed_seconds=[0-9.]*' "$T/logs/cari4d_${name}_rot.log" | tr '\n' ' ')${rerun:+ RERAN EARLIER STAGES: $rerun}"
done
say "ROT PILOT DONE"
