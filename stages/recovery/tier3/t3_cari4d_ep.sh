#!/usr/bin/env bash
# Tier 3, one episode: CARI4D wild-video inference with the checked masks and the official Track 2 object mesh
# (read from the Tier 2 directory's copy in $T3_ROOT/input/mesh; byte-identical to Tier 1's, and the mesh whose
# local frame the released poses and the scorer use). One GPU job: refinement peaks near 44 GB of the 46 GB.
#   t3_cari4d_ep.sh <episode_dir_name>      e.g. ep20_rice_cooker
# Log: $T3_ROOT/logs/cari4d_<name>.log; the last line carries rc.
set -u
name=$1
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
PY=${T3_PY:-/lab_data/yqchen/v2d/venv/bin/python}
WEIGHTS=${T3_WEIGHTS:-/lab_data/yqchen/v2d/weights}
W=$T/runs/work/$name
obj=${name#ep[0-9][0-9]_}
mesh=$T/input/mesh/$obj/$obj.glb
LOG=$T/logs/cari4d_$name.log
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
  source ~/proxy.sh >/dev/null
  export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
  export T3_FORWARD_ENV=PYTORCH_CUDA_ALLOC_CONF
  export T3_CONTAINER_ENV="TORCH_HOME=/data/weights_path/cari4d/torch_home"
  # CARI4D reuses finished stages only when their inputs are unchanged and refuses otherwise. When the packed
  # masks are newer than the last export (t3_masks.py repacked them), every stage from the export on is stale.
  overwrite=""
  marker=$(ls "$W"/cari4d/*/.stages/02_export.json 2>/dev/null | head -1)
  if [ -n "$marker" ] && [ "$W/masks_k0.h5" -nt "$marker" ]; then overwrite="--overwrite"; echo "masks newer than the last export: $overwrite"; fi
  $PY "$S/t3_run.py" v2d.cari4d.docker.run_inference $overwrite \
    --video_path "$video" --mask_h5_path "$W/masks_k0.h5" --object_mesh_path "$mesh" \
    --weights_path "$WEIGHTS/cari4d" --output_dir "$W/cari4d" \
    --skip_weight_download --expected_frames "$frames" --postopt_batch_size 128
} > "$LOG" 2>&1
rc=$?
echo "$(date +%T) cari4d rc=$rc" >> "$LOG"
exit $rc
