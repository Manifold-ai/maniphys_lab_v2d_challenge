#!/usr/bin/env bash
# Physics check (t3_physics_check.py) over one assembled Tier 3 version and its _suspect directory. CPU only.
#   t3_physics_all.sh tier3_cari4d_f830_floor
# Output: runs/physics/<version>/out/<ep>.json|.npz and summary.json; logs/physics_<version>.log.
set -u
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
PY=${T3_PY:-/lab_data/yqchen/v2d/venv/bin/python}
SOMA_ASSETS=${T3_SOMA_ASSETS:-/lab_data/yqchen/v2d/soma_assets}
V=${1:?usage: t3_physics_all.sh <version dir under runs/>}
P=$T/runs/physics/$V
LOG=$T/logs/physics_$V.log
mkdir -p "$P"
{
  echo "# $(date '+%F %T') deployed: $(cat "$T/code/DEPLOYED" 2>/dev/null)"
  for dir in "$T/runs/$V" "$T/runs/${V}_suspect"; do
    [ -d "$dir" ] && "$PY" "$S/t3_physics_check.py" extract "$T" "$dir" "$P/npz" || echo "extract $dir failed"
  done
  docker run --rm --cpus 8 --user "$(id -u):$(id -g)" --entrypoint "" --network none -e HOME=/tmp -w /workspace/v2d_cari4d/lib/cari4d \
    -v "$S":/s:ro -v "$T":/t:ro -v "$SOMA_ASSETS":/a:ro -v "$P":/o v2d_cari4d:latest \
    python /s/t3_physics_check.py check /t /o/npz /a /o/out 2>&1 | grep '^{'
  echo DONE
} > "$LOG" 2>&1
