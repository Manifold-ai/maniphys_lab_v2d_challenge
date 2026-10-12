#!/usr/bin/env bash
# Rerun the object check (t3_object_check.py) and the track check (t3_track_check.py) on every finished episode of the
# three CARI4D versions, after a change to the checks (10-12: IoU of dilated silhouettes). CPU only, JOBS episodes at
# a time. Versions (work dir, convert dir, object-check dir, track-check dir):
#   baseline  runs/work     runs/convert     runs/checks     runs/track_check
#   reselect  runs/work_v2  runs/convert_v2  runs/checks_v2  runs/track_check_v2sel
#   every-fr. runs/work_fp  runs/convert_fp  runs/checks_fp  runs/track_check_fp
# An episode is finished when its CARI4D pipeline_report.json and its convert dir's object_cam.npz and soma_params.npz
# exist (an episode still running in the GPU queue is skipped; the queue checks it with the new code itself).
# The previous outputs should be copied away first; this overwrites them.
#   JOBS=4 t3_recheck_all.sh            log: logs/recheck_all.log, one line per episode and check, last line DONE
#   TRACK_ONLY=1 skips the object check (a change to t3_track_check.py alone; 10-12: contact joints)
set -u
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
SOMA_ASSETS=${T3_SOMA_ASSETS:-/lab_data/yqchen/v2d/soma_assets}
JOBS=${JOBS:-4}
LOG=$T/logs/recheck_all.log
one() {  # <work> <convert> <checks> <track> <episode dir name>
  local work=$1 conv=$2 checks=$3 track=$4 name=$5
  local ep=$((10#${name:2:2})) obj=${name#ep[0-9][0-9]_}; local seq; seq=$(printf episode_%06d "$ep")
  local D=(docker run --rm --cpus 4 --user "$(id -u):$(id -g)" --entrypoint "" --network none -e HOME=/tmp -w /workspace/v2d_cari4d/lib/cari4d)
  [ -f "$T/runs/$work/$name/cari4d/$seq/pipeline_report.json" ] && [ -f "$T/runs/$conv/$name/object_cam.npz" ] \
    && [ -f "$T/runs/$conv/$name/soma_params.npz" ] || { echo "$work $name: not finished, skipped"; return; }
  mkdir -p "$T/runs/$checks/$name" "$T/runs/$track"
  if [ -z "${TRACK_ONLY:-}" ]; then
    "${D[@]}" -v "$S":/s:ro -v "$T/runs/$work/$name":/w:ro -v "$T/input/mesh":/m:ro -v "$T/runs/$checks/$name":/o v2d_cari4d:latest \
      python /s/t3_object_check.py "/w/cari4d/$seq" /w "/m/$obj/$obj.glb" /o 3 > "$T/logs/recheck_obj_${work}_$name.log" 2>&1 \
      && echo "$work $name: object $(grep -o '"ok": [a-z]*' "$T/runs/$checks/$name/object_check.json")" || echo "$work $name: object check FAILED"
  fi
  "${D[@]}" -v "$S":/s:ro -v "$T":/t -v "$SOMA_ASSETS":/a:ro v2d_cari4d:latest python /s/t3_track_check.py "/t/runs/$conv/$name" \
    "/t/runs/$work/$name" "/t/input/mesh/$obj/$obj.glb" /a "/t/runs/$track/$name.json" > "$T/logs/recheck_track_${work}_$name.log" 2>&1 \
    && echo "$work $name: track $(grep -o '"lost_fraction": [0-9.]*' "$T/runs/$track/$name.json")" || echo "$work $name: track check FAILED"
}
export -f one; export T S SOMA_ASSETS TRACK_ONLY
{
  echo "# $(date '+%F %T') recheck, JOBS=$JOBS TRACK_ONLY=${TRACK_ONLY:-}"
  for spec in "work convert checks track_check" "work_v2 convert_v2 checks_v2 track_check_v2sel" "work_fp convert_fp checks_fp track_check_fp"; do
    set -- $spec
    for d in "$T/runs/$1"/ep*; do echo "$spec $(basename "$d")"; done
  done | xargs -P "$JOBS" -L 1 bash -c 'one "$@"' _
  echo DONE
} > "$LOG" 2>&1
