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
# REUSE_FIT=1: the focal step and runs/floor/$FIT are already there (the floor fit reads object contacts only), redo
# world + assemble, e.g. after a change to the world step: REUSE_FIT=1 OUT=tier3_cari4d_f830_sim t3_world_all.sh
REUSE_FIT=${REUSE_FIT:-0}
# REGISTER=camera_register.json: floor-plane motions of the other exo cameras onto the main camera's world (world step);
# EPS="ep12_black_platform ...": only these episodes (default every converted episode)
REGISTER=${REGISTER:-}
EPS=${EPS:-}
mesh_of() {  # the official object mesh of an episode dir name (ep16_spray_bottle -> mesh/spray_bottle/spray_bottle.glb), under input/
  python3 -c 'import json,sys; ep=int(sys.argv[2][2:4]); print(next(m["mesh"] for m in map(json.loads, open(sys.argv[1]).read().splitlines()) if m and m["episode_index"]==ep))' \
    "$T/input/meta/episodes_metadata.jsonl" "$1"
}
[ -f "$T/runs/floor/$FOCAL_SPEC" ] || { echo "no runs/floor/$FOCAL_SPEC"; exit 2; }
if [ "$REUSE_FIT" = 1 ]; then
  [ -f "$T/runs/floor/$FIT" ] || { echo "REUSE_FIT=1 but no runs/floor/$FIT"; exit 2; }
else
  [ -e "$T/runs/floor/$FIT" ] && { echo "runs/floor/$FIT exists; pick a new FIT name rather than overwrite"; exit 2; }
fi
D=(docker run --rm --cpus 4 --user "$(id -u):$(id -g)" --entrypoint "" --network none -e HOME=/tmp -w /workspace/v2d_cari4d/lib/cari4d)
eps=()
for conv in "$T"/runs/convert/ep*; do
  [ -f "$conv/soma_params.npz" ] || continue
  [ -z "$EPS" ] || [[ " $EPS " == *" $(basename "$conv") "* ]] || continue
  eps+=("$(basename "$conv")")
done
[ -z "$REGISTER" ] || [ -f "$T/runs/floor/$REGISTER" ] || { echo "no runs/floor/$REGISTER"; exit 2; }
[ "$REUSE_FIT" = 1 ] || for name in "${eps[@]}"; do
  conv=$T/runs/convert/$name
  "${D[@]}" -v "$S":/s:ro -v "$T/runs/floor":/f:ro -v "$SOMA_ASSETS":/a:ro -v "$T/input":/i:ro -v "$conv":/o/"$name" v2d_cari4d:latest \
    python /s/t3_convert_ep.py focal /o/"$name" /f/"$FOCAL_SPEC" /a /i/"$(mesh_of "$name")" > "$T/logs/focal_$name.log" 2>&1 \
    && echo "$name: focal $(grep -o '"depth_ratio": [0-9.]*' "$T/logs/focal_$name.log")" || { echo "$name: focal FAILED"; exit 1; }
done
if [ "$REUSE_FIT" != 1 ]; then
  "${D[@]}" -v "$S":/s:ro -v "$T":/t v2d_cari4d:latest python /s/t3_floor_fit.py /t "/t/runs/floor/$FIT" > "$T/logs/floor_fit_$FIT.log" 2>&1 \
    || { echo "floor fit FAILED (logs/floor_fit_$FIT.log)"; exit 1; }
  grep '^{' "$T/logs/floor_fit_$FIT.log" | cut -c1-400
fi
for name in "${eps[@]}"; do
  conv=$T/runs/convert/$name; ep=$((10#${name:2:2})); f=$(printf "episode_%06d.parquet" "$ep")
  if [ -f "$T/runs/tier3_cari4d/data/chunk-000/$f" ]; then dst=$T/runs/$OUT
  elif [ -f "$T/runs/tier3_cari4d_suspect/data/chunk-000/$f" ]; then dst=$T/runs/${OUT}_suspect
  else echo "$name: in neither gate directory, skipped"; continue; fi
  "${D[@]}" -v "$S":/s:ro -v "$T/runs/floor":/f:ro -v "$SOMA_ASSETS":/a:ro -v "$conv":/o/"$name" v2d_cari4d:latest \
    python /s/t3_convert_ep.py world /o/"$name" /f/"$FIT" /a ${REGISTER:+/f/$REGISTER} > "$T/logs/world_$name.log" 2>&1 \
    || { echo "$name: world failed (logs/world_$name.log)"; continue; }
  "$PY" "$S/t3_convert_ep.py" assemble "$conv" "$T/input" "$ep" "$dst" > "$T/logs/assemble_${OUT}_$name.log" 2>&1 \
    && echo "$name: -> $(basename "$dst") $(grep -h "^FALLBACK" "$T/logs/world_$name.log" "$T/logs/focal_$name.log" 2>/dev/null | tr "\n" " ")$(grep -o '"body_rigid_max_err_mm": [0-9.e-]*\|"joint_err_mm_max": [0-9.e-]*\|"tol_mm": [0-9.e-]*' "$T/logs/world_$name.log" | tr '\n' ' ')" \
    || echo "$name: assemble failed"
done
echo ALLDONE
