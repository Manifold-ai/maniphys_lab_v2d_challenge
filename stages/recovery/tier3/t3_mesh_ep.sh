#!/usr/bin/env bash
# Tier 3, one episode, up to (not including) CARI4D:
#   pick the frame that shows the object best -> MoGe-2 point map of that frame -> SAM 3D Objects generates
#   the object at metric scale from the point map -> metric mesh + self-check (t3_scale_mesh.py).
# Fully automatic; refuses episodes whose masks are missing or flagged. No Track 2 mesh is read.
#   t3_mesh_ep.sh <episode_dir_name>      e.g. ep20_rice_cooker
# Log: logs/mesh_<name>.log; the last line carries rc.
set -u
name=$1
T=/lab_data/yqchen/v2d/tier3
W=$T/runs/work/$name
PY=/lab_data/yqchen/v2d/venv/bin/python
WEIGHTS=/lab_data/yqchen/v2d/weights
LOG=$T/logs/mesh_$name.log
{
  if [ -e "$W/MASK_SUSPECT" ] || [ ! -f "$W/mask_report.json" ]; then echo "masks missing or flagged MASK_SUSPECT"; exit 2; fi
  video=$(ls "$W"/episode_*.0.color.mp4)
  $PY $T/scripts/t3_pick_frame.py --work "$W" --video "$video" --out "$W/sam3d_in" || exit 3
  f=$(python3 -c "import json;print('%06d' % json.load(open('$W/sam3d_in/pick.json'))['frame_index'])")
  docker run --rm --gpus all --user "$(id -u):$(id -g)" --entrypoint "" --network none \
    -e HF_HOME=/w/hf_home -e HF_HUB_OFFLINE=1 -e HOME=/tmp \
    -v $WEIGHTS/cari4d/hf_home:/w/hf_home:ro -v $T/scripts:/s:ro -v "$W":/work \
    v2d_cari4d:latest python /s/t3_moge_frame.py /work/sam3d_in/frame_$f.png /work/moge_$f || exit 4
  mkdir -p "$W/sam3d_out"
  source ~/proxy.sh >/dev/null
  $PY $T/scripts/t3_run.py v2d.sam3d.docker.run_image_to_mesh \
    --image_path "$W/sam3d_in/frame_$f.png" --mask_path "$W/sam3d_in/mask_$f.png" \
    --mesh_path "$W/sam3d_out/object.glb" --transform_path "$W/sam3d_out/transform.json" \
    --intrinsics_path "$W/sam3d_out/intrinsics.json" --weights_dir $WEIGHTS/sam3d --seed 0 \
    --pointmap_path "$W/moge_$f/points.npy" --pointmap_intrinsics_path "$W/moge_$f/intrinsics.json" || exit 5
  $PY $T/scripts/t3_scale_mesh.py --sam3d "$W/sam3d_out" --frame-dir "$W/sam3d_in" --moge "$W/moge_$f" --out "$W/sam3d_out" || exit 6
} > "$LOG" 2>&1
rc=$?
echo "$(date +%T) mesh rc=$rc" >> "$LOG"
exit $rc
