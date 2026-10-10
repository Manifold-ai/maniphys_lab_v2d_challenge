#!/usr/bin/env bash
# Corrected Tier 3 data for every converted episode, in three passes:
#   1. focal step (CPU, v2d_cari4d image) with runs/floor/$FOCAL_SPEC;
#   2. t3_floor_fit.py on the focal-corrected poses -> runs/floor/$FIT;
#   3. world step with that fit, then assemble (host venv) into runs/${OUT}/ or runs/${OUT}_suspect/, following the
#      episode's current silhouette-gate directory.
# Earlier outputs (runs/tier3_cari4d{,_suspect}/ W = I, runs/tier3_cari4d_floor{,_suspect}/ CARI4D focal) are left alone.
#   FOCAL_SPEC=focal.json FIT=floor_fit_f830.json OUT=tier3_cari4d_f830_floor t3_world_all.sh
set -u
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
PY=${T3_PY:-/lab_data/yqchen/v2d/venv/bin/python}
SOMA_ASSETS=${T3_SOMA_ASSETS:-/lab_data/yqchen/v2d/soma_assets}
FOCAL_SPEC=${FOCAL_SPEC:-focal.json}
FIT=${FIT:-floor_fit_f830.json}
OUT=${OUT:-tier3_cari4d_f830_floor}
[ -f "$T/runs/floor/$FOCAL_SPEC" ] || { echo "no runs/floor/$FOCAL_SPEC"; exit 2; }
[ -e "$T/runs/floor/$FIT" ] && { echo "runs/floor/$FIT exists; pick a new FIT name rather than overwrite"; exit 2; }
D=(docker run --rm --cpus 4 --user "$(id -u):$(id -g)" --entrypoint "" --network none -e HOME=/tmp -w /workspace/v2d_cari4d/lib/cari4d)
eps=()
for conv in "$T"/runs/convert/ep*; do [ -f "$conv/soma_params.npz" ] && eps+=("$(basename "$conv")"); done
for name in "${eps[@]}"; do
  conv=$T/runs/convert/$name
  "${D[@]}" -v "$S":/s:ro -v "$T/runs/floor":/f:ro -v "$SOMA_ASSETS":/a:ro -v "$conv":/o/"$name" v2d_cari4d:latest \
    python /s/t3_convert_ep.py focal /o/"$name" /f/"$FOCAL_SPEC" /a > "$T/logs/focal_$name.log" 2>&1 \
    && echo "$name: focal $(grep -o '"depth_ratio": [0-9.]*' "$T/logs/focal_$name.log")" || { echo "$name: focal FAILED"; exit 1; }
done
"${D[@]}" -v "$S":/s:ro -v "$T":/t v2d_cari4d:latest python /s/t3_floor_fit.py /t "/t/runs/floor/$FIT" > "$T/logs/floor_fit_$FIT.log" 2>&1 \
  || { echo "floor fit FAILED (logs/floor_fit_$FIT.log)"; exit 1; }
grep '^{' "$T/logs/floor_fit_$FIT.log" | cut -c1-400
for name in "${eps[@]}"; do
  conv=$T/runs/convert/$name; ep=$((10#${name:2:2})); f=$(printf "episode_%06d.parquet" "$ep")
  if [ -f "$T/runs/tier3_cari4d/data/chunk-000/$f" ]; then dst=$T/runs/$OUT
  elif [ -f "$T/runs/tier3_cari4d_suspect/data/chunk-000/$f" ]; then dst=$T/runs/${OUT}_suspect
  else echo "$name: in neither gate directory, skipped"; continue; fi
  "${D[@]}" -v "$S":/s:ro -v "$T/runs/floor":/f:ro -v "$SOMA_ASSETS":/a:ro -v "$conv":/o/"$name" v2d_cari4d:latest \
    python /s/t3_convert_ep.py world /o/"$name" /f/"$FIT" /a > "$T/logs/world_$name.log" 2>&1 \
    || { echo "$name: world failed (logs/world_$name.log)"; continue; }
  "$PY" "$S/t3_convert_ep.py" assemble "$conv" "$T/input" "$ep" "$dst" > "$T/logs/assemble_${OUT}_$name.log" 2>&1 \
    && echo "$name: -> $(basename "$dst") $(grep -o '"body_rigid_max_err_mm": [0-9.e-]*' "$T/logs/world_$name.log")" \
    || echo "$name: assemble failed"
done
echo ALLDONE
