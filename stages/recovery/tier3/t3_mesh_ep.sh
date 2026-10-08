#!/usr/bin/env bash
# Tier 3, one episode, up to (not including) CARI4D:
#   pick K time-spread frames that show the object well -> MoGe-2 point maps of those frames -> SAM 3D Objects
#   generates the object at metric scale from each point map -> per-frame metric mesh + self-check
#   (t3_scale_mesh.py) -> choose one (t3_select_mesh.py).
# Fully automatic; refuses episodes whose masks are missing or flagged. No Track 2 mesh is read.
#   t3_mesh_ep.sh <episode_dir_name>      e.g. ep20_rice_cooker
# Log: $T3_ROOT/logs/mesh_<name>.log; the last line carries rc.
set -u
name=$1
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
PY=${T3_PY:-/lab_data/yqchen/v2d/venv/bin/python}
WEIGHTS=${T3_WEIGHTS:-/lab_data/yqchen/v2d/weights}
K=${T3_MESH_FRAMES:-3}
W=$T/runs/work/$name
LOG=$T/logs/mesh_$name.log
{
  if [ -e "$W/MASK_SUSPECT" ] || [ ! -f "$W/mask_report.json" ]; then echo "masks missing or flagged MASK_SUSPECT"; exit 2; fi
  if [ -f "$W/sam3d_out/object.glb" ]; then  # single-frame layout of 2026-10-09 batch 1: keep it aside, do not mix
    mkdir -p "$W/sam3d_out/single_frame_v1" && mv "$W"/sam3d_out/{object.glb,object_scaled.glb,transform.json,intrinsics.json,scale_report.json} "$W/sam3d_out/single_frame_v1/" 2>/dev/null
  fi
  video=$(ls "$W"/episode_*.0.color.mp4)
  $PY "$S/t3_pick_frame.py" --work "$W" --video "$video" --out "$W/sam3d_in" --k "$K" || exit 3
  frames=$(python3 -c "import json;print(' '.join('%06d' % i for i in json.load(open('$W/sam3d_in/pick.json'))['frames']))")
  pngs=$(for f in $frames; do printf '/work/sam3d_in/frame_%s.png ' "$f"; done)
  docker run --rm --gpus all --user "$(id -u):$(id -g)" --entrypoint "" --network none \
    -e HF_HOME=/w/hf_home -e HF_HUB_OFFLINE=1 -e HOME=/tmp \
    -v "$WEIGHTS/cari4d/hf_home":/w/hf_home:ro -v "$S":/s:ro -v "$W":/work \
    v2d_cari4d:latest python /s/t3_moge_frame.py /work $pngs || exit 4
  source ~/proxy.sh >/dev/null
  for f in $frames; do
    o="$W/sam3d_out/f$f"
    mkdir -p "$o"
    $PY "$S/t3_run.py" v2d.sam3d.docker.run_image_to_mesh \
      --image_path "$W/sam3d_in/frame_$f.png" --mask_path "$W/sam3d_in/mask_$f.png" \
      --mesh_path "$o/object.glb" --transform_path "$o/transform.json" \
      --intrinsics_path "$o/intrinsics.json" --weights_dir "$WEIGHTS/sam3d" --seed 0 \
      --pointmap_path "$W/moge_$f/points.npy" --pointmap_intrinsics_path "$W/moge_$f/intrinsics.json" || { echo "sam3d failed on frame $f"; continue; }
    $PY "$S/t3_scale_mesh.py" --sam3d "$o" --frame-dir "$W/sam3d_in" --moge "$W/moge_$f" --out "$o" --frame "$((10#$f))" || echo "scale check failed on frame $f"
  done
  $PY "$S/t3_select_mesh.py" "$W/sam3d_out" || exit 6
} > "$LOG" 2>&1
rc=$?
echo "$(date +%T) mesh rc=$rc" >> "$LOG"
exit $rc
