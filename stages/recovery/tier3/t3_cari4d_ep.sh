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
  source ~/proxy.sh >/dev/null
  export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
  export T3_FORWARD_ENV=PYTORCH_CUDA_ALLOC_CONF
  export T3_CONTAINER_ENV="TORCH_HOME=/data/weights_path/cari4d/torch_home"
  $PY "$S/t3_run.py" v2d.cari4d.docker.run_inference \
    --video_path "$video" --mask_h5_path "$W/masks_k0.h5" --object_mesh_path "$mesh" \
    --weights_path "$WEIGHTS/cari4d" --output_dir "$W/cari4d" \
    --skip_weight_download --expected_frames "$frames" --postopt_batch_size 128
} > "$LOG" 2>&1
rc=$?
echo "$(date +%T) cari4d rc=$rc" >> "$LOG"
exit $rc
