#!/usr/bin/env bash
# Tier 3, one episode: CARI4D wild-video inference with the checked masks and the official Track 2 object mesh
# (read from the Tier 2 directory's copy in $T3_ROOT/input/mesh; byte-identical to Tier 1's, and the mesh whose
# local frame the released poses and the scorer use). One GPU job: refinement peaks near 44 GB of the 46 GB.
#   t3_cari4d_ep.sh <episode_dir_name>      e.g. ep20_rice_cooker
# T3_WORK (default runs/work) picks the work root under $T3_ROOT; T3_FP_MODE=register-every-frame lays
# third_party/patches/cari4d-fp-sequence-mode.patch over the inference entry and runs FoundationPose registering every
# frame (re-acquires a lost object) instead of registering once and tracking.
# T3_CARI4D_EXTRA adds wrapper flags as they are (e.g. --optimize_object_rotation for t3_rot_pilot.sh).
# T3_SKIP_RENDER=1 (with T3_FP_MODE) drops stage 08, which only renders review videos (third_party/patches/cari4d-skip-render.patch).
# Log: $T3_ROOT/logs/cari4d_<name><T3_LOG_TAG>.log; the last line carries rc.
set -u
name=$1
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
PY=${T3_PY:-/lab_data/yqchen/v2d/venv/bin/python}
WEIGHTS=${T3_WEIGHTS:-/lab_data/yqchen/v2d/weights}
W=$T/${T3_WORK:-runs/work}/$name
FP_MODE=${T3_FP_MODE:-register-first-then-track}
obj=${name#ep[0-9][0-9]_}
mesh=$T/input/mesh/$obj/$obj.glb
LOG=$T/logs/cari4d_$name${T3_LOG_TAG:-}.log
{
  if [ -e "$W/MASK_SUSPECT" ] || [ ! -f "$W/masks_k0.h5" ]; then echo "masks missing or flagged MASK_SUSPECT"; exit 2; fi
  [ -f "$mesh" ] || { echo "no official mesh at $mesh"; exit 2; }
  video=$(ls "$W"/episode_*.0.color.mp4)
  frames=$(ffprobe -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets -of csv=p=0 "$video")
  echo "frames=$frames mesh=$mesh"
  # third_party/patches/cari4d-fp-no-observation-nan.patch, laid over the image's copy of one file
  up=/workspace/v2d_cari4d/lib/cari4d/prep/run_foundationpose_mhr_export.py
  pdir=$T/patched; mkdir -p "$pdir"
  if [ "$(md5sum < "$pdir/run_foundationpose_mhr_export.py" 2>/dev/null | cut -c1-32)" != 556a32239f14f8b87a137f1edec26514 ]; then
    docker run --rm --entrypoint "" --network none v2d_cari4d:latest cat "$up" > "$pdir/upstream.py"
    [ "$(md5sum < "$pdir/upstream.py" | cut -c1-32)" = c93056318b5320eb028a170d4ae482b6 ] || { echo "image's $up is not the patched-against upstream"; exit 2; }
    patch -s -o "$pdir/run_foundationpose_mhr_export.py" "$pdir/upstream.py" < "$S/../../../third_party/patches/cari4d-fp-no-observation-nan.patch" || exit 2
    [ "$(md5sum < "$pdir/run_foundationpose_mhr_export.py" | cut -c1-32)" = 556a32239f14f8b87a137f1edec26514 ] || { echo "patched file md5 mismatch"; exit 2; }
  fi
  export T3_EXTRA_MOUNTS="$pdir/run_foundationpose_mhr_export.py:$up:ro"
  if [ "$FP_MODE" != register-first-then-track ]; then
    ri=/workspace/v2d_cari4d/lib/run_inference.py
    if [ "$(md5sum < "$pdir/run_inference.py" 2>/dev/null | cut -c1-32)" != 45d83632944176002d5bba81bfdc87ae ]; then
      docker run --rm --entrypoint "" --network none v2d_cari4d:latest cat "$ri" > "$pdir/upstream_run_inference.py"
      [ "$(md5sum < "$pdir/upstream_run_inference.py" | cut -c1-32)" = ea62dbdb9c60b00d0b0e4a488c806d97 ] || { echo "image's $ri is not the patched-against upstream"; exit 2; }
      patch -s -o "$pdir/run_inference.py" "$pdir/upstream_run_inference.py" < "$S/../../../third_party/patches/cari4d-fp-sequence-mode.patch" || exit 2
      [ "$(md5sum < "$pdir/run_inference.py" | cut -c1-32)" = 45d83632944176002d5bba81bfdc87ae ] || { echo "patched run_inference.py md5 mismatch"; exit 2; }
    fi
    mount=$pdir/run_inference.py
    if [ "${T3_SKIP_RENDER:-0}" = 1 ]; then
      # third_party/patches/cari4d-skip-render.patch over the sequence-mode file: no stage 08 (review videos only)
      if [ "$(md5sum < "$pdir/run_inference_norender.py" 2>/dev/null | cut -c1-32)" != 9dd956923d66839dc07ccea0981b5de9 ]; then
        patch -s -o "$pdir/run_inference_norender.py" "$pdir/run_inference.py" < "$S/../../../third_party/patches/cari4d-skip-render.patch" || exit 2
        [ "$(md5sum < "$pdir/run_inference_norender.py" | cut -c1-32)" = 9dd956923d66839dc07ccea0981b5de9 ] || { echo "skip-render file md5 mismatch"; exit 2; }
      fi
      mount=$pdir/run_inference_norender.py
    fi
    T3_EXTRA_MOUNTS="$T3_EXTRA_MOUNTS;$mount:$ri:ro"
    export V2D_FP_SEQUENCE_MODE=$FP_MODE
  fi
  [ "${T3_SKIP_RENDER:-0}" != 1 ] || [ "$FP_MODE" != register-first-then-track ] || { echo "T3_SKIP_RENDER needs a sequence mode"; exit 2; }
  echo "foundationpose mode: $FP_MODE${T3_CARI4D_EXTRA:+, extra: $T3_CARI4D_EXTRA}${T3_SKIP_RENDER:+, skip render: $T3_SKIP_RENDER}"
  source ~/proxy.sh >/dev/null
  export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
  export T3_FORWARD_ENV=PYTORCH_CUDA_ALLOC_CONF${V2D_FP_SEQUENCE_MODE:+,V2D_FP_SEQUENCE_MODE}
  export T3_CONTAINER_ENV="TORCH_HOME=/data/weights_path/cari4d/torch_home"
  # CARI4D reuses finished stages only when their inputs are unchanged and refuses otherwise. When the packed
  # masks are newer than the last export (t3_masks.py repacked them), every stage from the export on is stale.
  overwrite=""
  marker=$(ls "$W"/cari4d/*/.stages/02_export.json 2>/dev/null | head -1)
  if [ -n "$marker" ] && [ "$W/masks_k0.h5" -nt "$marker" ]; then overwrite="--overwrite"; echo "masks newer than the last export: $overwrite"; fi
  $PY "$S/t3_run.py" v2d.cari4d.docker.run_inference $overwrite \
    --video_path "$video" --mask_h5_path "$W/masks_k0.h5" --object_mesh_path "$mesh" \
    --weights_path "$WEIGHTS/cari4d" --output_dir "$W/cari4d" \
    --skip_weight_download --expected_frames "$frames" --postopt_batch_size 128 ${T3_CARI4D_EXTRA:-}
} > "$LOG" 2>&1
rc=$?
echo "$(date +%T) cari4d rc=$rc" >> "$LOG"
exit $rc
