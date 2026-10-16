#!/usr/bin/env bash
# The focal step of t3_convert_ep.py for every episode of one convert dir, under an intrinsics spec, into a new convert dir
# (10-16: the calibrated main-camera intrinsics). The source dir is only read: per episode the files the focal, world
# and assemble steps start from are copied (object_cam.npz, soma_params.npz, the decode/residual reports and, for a
# pivot dir, its pivot records), never the MHR mesh (~200 MB) the steps after soma do not read. CPU, v2d_cari4d image.
#   t3_focal_all.sh <src convert dir> <dst convert dir> <spec .json under runs/floor/>
#   e.g. t3_focal_all.sh convert convert_kgb intrinsics_gb.json
# JOBS (default 4) episodes at a time, each container on 4 CPUs. Logs logs/focal_<dst>_<ep>.log; last line FOCAL_ALL_DONE
# with the count of episodes that failed.
set -u
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
SOMA_ASSETS=${T3_SOMA_ASSETS:-/lab_data/yqchen/v2d/soma_assets}
SRC=${1:?usage: t3_focal_all.sh <src convert dir> <dst convert dir> <spec>}
DST=${2:?}
SPEC=${3:?}
JOBS=${JOBS:-4}
[ -f "$T/runs/floor/$SPEC" ] || { echo "no runs/floor/$SPEC"; exit 2; }
[ "$SRC" != "$DST" ] || { echo "source and destination are the same dir"; exit 2; }
mkdir -p "$T/runs/$DST" "$T/logs"
one() {
  local name=$1 src=$T/runs/$SRC/$1 dst=$T/runs/$DST/$1
  [ -f "$src/soma_params.npz" ] || { echo "$name: no soma_params.npz in $SRC, skipped"; return 0; }
  mkdir -p "$dst"
  for f in object_cam.npz soma_params.npz decode_report.json residual_report.json pivot_poses.npz pivot_summary.json; do
    [ -f "$src/$f" ] && cp -p "$src/$f" "$dst/$f"
  done
  docker run --rm --cpus 4 -e OMP_NUM_THREADS=4 --user "$(id -u):$(id -g)" --entrypoint "" --network none -e HOME=/tmp \
    -w /workspace/v2d_cari4d/lib/cari4d -v "$S":/s:ro -v "$T/runs/floor":/f:ro -v "$SOMA_ASSETS":/a:ro -v "$dst":/o/"$name" \
    v2d_cari4d:latest python /s/t3_convert_ep.py focal /o/"$name" /f/"$SPEC" /a > "$T/logs/focal_${DST}_$name.log" 2>&1 \
    && echo "$name: $(grep -o '"fx_new": [0-9.]*\|"principal_point_new": \[[0-9., ]*\]' "$T/logs/focal_${DST}_$name.log" | tr '\n' ' ')" \
    || echo "$name: focal FAILED (logs/focal_${DST}_$name.log)"
}
export -f one
export T S SRC DST SPEC SOMA_ASSETS
ls "$T/runs/$SRC" | grep '^ep' | xargs -P "$JOBS" -I{} bash -c 'one {}' | tee "$T/logs/focal_all_$DST.log"
echo "FOCAL_ALL_DONE failed=$(grep -c 'FAILED' "$T/logs/focal_all_$DST.log")"
