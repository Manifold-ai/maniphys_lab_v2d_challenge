#!/usr/bin/env bash
# Floor-corrected Tier 3 data for every converted episode: world step (CPU, v2d_cari4d image) then assemble (host venv)
# into runs/tier3_cari4d_floor/ or runs/tier3_cari4d_floor_suspect/, following the episode's current silhouette-gate
# directory. The W = I directories runs/tier3_cari4d{,_suspect}/ are left as they are (frozen baseline).
#   t3_world_all.sh            (needs runs/floor/floor_fit.json from t3_floor_fit.py)
set -u
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
PY=${T3_PY:-/lab_data/yqchen/v2d/venv/bin/python}
SOMA_ASSETS=${T3_SOMA_ASSETS:-/lab_data/yqchen/v2d/soma_assets}
FIT=$T/runs/floor/floor_fit.json
[ -f "$FIT" ] || { echo "no $FIT"; exit 2; }
for conv in "$T"/runs/convert/ep*; do
  name=$(basename "$conv"); ep=$((10#${name:2:2})); f=$(printf "episode_%06d.parquet" "$ep")
  [ -f "$conv/soma_params.npz" ] || { echo "$name: not converted, skipped"; continue; }
  if [ -f "$T/runs/tier3_cari4d/data/chunk-000/$f" ]; then dst=$T/runs/tier3_cari4d_floor
  elif [ -f "$T/runs/tier3_cari4d_suspect/data/chunk-000/$f" ]; then dst=$T/runs/tier3_cari4d_floor_suspect
  else echo "$name: in neither gate directory, skipped"; continue; fi
  docker run --rm --cpus 4 --user "$(id -u):$(id -g)" --entrypoint "" --network none -e HOME=/tmp \
    -w /workspace/v2d_cari4d/lib/cari4d -v "$S":/s:ro -v "$T/runs/floor":/f:ro -v "$SOMA_ASSETS":/a:ro -v "$conv":/o/"$name" \
    v2d_cari4d:latest python /s/t3_convert_ep.py world /o/"$name" /f/floor_fit.json /a > "$T/logs/world_$name.log" 2>&1 \
    || { echo "$name: world failed (logs/world_$name.log)"; continue; }
  "$PY" "$S/t3_convert_ep.py" assemble "$conv" "$T/input" "$ep" "$dst" > "$T/logs/assemble_floor_$name.log" 2>&1 \
    && echo "$name: -> $(basename "$dst") $(grep -o '"body_rigid_max_err_mm": [0-9.e-]*' "$T/logs/world_$name.log")" \
    || echo "$name: assemble failed (logs/assemble_floor_$name.log)"
done
echo ALLDONE
