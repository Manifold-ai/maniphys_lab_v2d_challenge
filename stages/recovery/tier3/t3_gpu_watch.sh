#!/usr/bin/env bash
# Start a GPU job (JOB, default the re-acquisition pilot t3_fp_pilot.sh; t3_reselect.sh for re-picked masks) once
# rxzhou's ml40 work is really over, not in the short pause between two of his training episodes. A second watcher
# queues behind the first: it starts watching only after every other t3_gpu_watch.sh and every running job script
# (t3_fp_pilot.sh, t3_reselect.sh) has exited. "Over" = for QUIET_MIN minutes in a row, checked every CHECK_S seconds:
# no runs/.chain-active-* marker in his repository (his chains hold one for their whole run, pauses included), no
# flash_chord container, and at least MIN_FREE_MIB free on the GPU. Then it launches the job and exits when it ends;
# a job that yielded the card (rc 3 or 4, the job scripts' "not enough free" / "rxzhou is back") is waited for and
# launched again with the same list (the job scripts skip the episodes they finished).
#   setsid nohup t3_gpu_watch.sh ep28_squeegee ep27_woven_basket ... > /dev/null 2>&1 < /dev/null &
#   JOB=t3_reselect.sh setsid nohup t3_gpu_watch.sh ep01_vacuum ... > /dev/null 2>&1 < /dev/null &
# Cancel: touch $T3_ROOT/WATCH_STOP. Log: logs/t3_gpu_watch.log.
set -u
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
RX_RUNS=${RX_RUNS:-/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge/runs}
MIN_FREE_MIB=${MIN_FREE_MIB:-44000}
QUIET_MIN=${QUIET_MIN:-30}
CHECK_S=${CHECK_S:-120}
FC_IMAGE=${FC_IMAGE:-flash_chord}
JOB=${JOB:-t3_fp_pilot.sh}
LOG=$T/logs/t3_gpu_watch.log
say() { echo "$(date +%m-%d_%T) $*" >> "$LOG"; }
[ $# -gt 0 ] || { echo "usage: t3_gpu_watch.sh <episode dir name> ..."; exit 2; }
# Other watchers and job scripts run in their own session (setsid); this watcher's own subshells share its session.
mysid=$(ps -o sid= -p $$ | tr -d ' ')
others() { for p in $(pgrep -f '^(/usr)?(/bin/)?bash [^ ]*t3_(gpu_watch|fp_pilot|reselect)\.sh( |$)'); do
  [ "$(ps -o sid= -p "$p" 2>/dev/null | tr -d ' ')" = "$mysid" ] || printf '%s ' "$p"; done; }
if [ -n "$(others)" ]; then
  say "$JOB queued behind pids $(others)"
  while [ -n "$(others)" ]; do
    [ -e "$T/WATCH_STOP" ] && { say "WATCH_STOP found, exiting without starting"; exit 0; }
    sleep "$CHECK_S"
  done
fi
say "watching for rxzhou's ml40 work to end; then $JOB on: $*"
quiet_since=""
last=""
while true; do
  [ -e "$T/WATCH_STOP" ] && { say "WATCH_STOP found, exiting without starting"; exit 0; }
  markers=$(compgen -G "$RX_RUNS/.chain-active-*" | xargs -r -n1 basename | tr '\n' ' ')
  fc=$(docker ps --format '{{.Names}} {{.Image}}' | awk -v img="$FC_IMAGE" 'index($2, img) == 1 {print $1}' | tr '\n' ' ')
  free=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
  if [ -z "$markers" ] && [ -z "$fc" ] && [ "$free" -ge "$MIN_FREE_MIB" ]; then
    now=$(date +%s)
    [ -n "$quiet_since" ] || { quiet_since=$now; say "quiet: no chain marker, no flash_chord, ${free} MiB free; waiting ${QUIET_MIN} min"; }
    if [ $(( now - quiet_since )) -ge $(( QUIET_MIN * 60 )) ]; then
      say "quiet for ${QUIET_MIN} min, starting $JOB"
      "$S/$JOB" "$@"
      rc=$?
      if [ "$rc" -eq 3 ] || [ "$rc" -eq 4 ]; then
        say "$JOB yielded the card rc=$rc; watching again"
        quiet_since=""; last=""; sleep "$CHECK_S"; continue
      fi
      say "$JOB exited rc=$rc; watcher done"
      exit 0
    fi
  else
    state="markers=[${markers}] flash_chord=[${fc}]"
    [ -n "$quiet_since" ] && say "not quiet any more: $state free=${free}"
    [ "$state" != "$last" ] && [ -z "$quiet_since" ] && say "busy: $state free=${free}"
    last=$state
    quiet_since=""
  fi
  sleep "$CHECK_S"
done
