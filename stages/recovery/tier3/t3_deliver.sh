#!/usr/bin/env bash
# Deliver a checked Tier 3 version (run on L40S, 10-16): its support usda (the ones its gate check used) into the version
# dirs at each episode's metadata path, every one checked identical to the gate's copy, and its delivery report
# (gate/t3_delivery_report.py from a spec json) as DELIVERY.md in the version dir. Stops on the first problem.
#   t3_deliver.sh <version> <gate set> <spec json>
# Registering the version as delivered (versions.json) and the handoff are done in the repo, from the same report.
set -u
V=$1; S=$2; SPEC=$3
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}; G=${T3_GATE:-/lab_data/yqchen/v2d/gate}
S_DIR=$G/support_usda_$S; HERE=$(cd "$(dirname "$0")" && pwd)
[ -d "$T/runs/$V" ] || { echo "no runs/$V"; exit 1; }
[ -f "$S_DIR/support_usda.json" ] || { echo "no support usda for gate set $S"; exit 1; }
n=0
for sub in "" _suspect; do
  D=$T/runs/$V$sub; [ -d "$D/meta" ] || continue
  mkdir -p "$D/support_surface"
  for f in "$D"/meta/episode_*.metadata.json; do
    rel=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['support_surface'])" "$f") || { echo "no support_surface in $f"; exit 1; }
    src=$S_DIR/$(basename "$rel")
    [ -f "$src" ] || { echo "missing $src"; exit 1; }
    cp "$src" "$D/$rel" && cmp -s "$src" "$D/$rel" || { echo "copy differs: $D/$rel"; exit 1; }
    n=$((n + 1))
  done
  cp "$S_DIR/support_usda.json" "$D/support_surface/"
done
echo "support usda placed: $n"
[ "$n" -eq 30 ] || { echo "expected 30 episodes"; exit 1; }
${T3_PY:-$G/venv/bin/python} "$HERE/gate/t3_delivery_report.py" "$T" "$G" "$SPEC" > "$T/runs/$V/DELIVERY.md" || { echo "report failed"; exit 1; }
[ -d "$T/runs/${V}_suspect" ] && cp "$T/runs/$V/DELIVERY.md" "$T/runs/${V}_suspect/DELIVERY.md"
echo "DELIVERY.md written ($(wc -l < "$T/runs/$V/DELIVERY.md") lines)"
echo DELIVER_DONE
