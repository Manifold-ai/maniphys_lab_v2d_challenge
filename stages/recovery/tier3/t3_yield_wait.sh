#!/usr/bin/env bash
# Wait for the L40S to be ours, then run a GPU pilot; rerun it whenever it yields. "Ours" (project rule, yield to
# rxzhou): none of his runs/.chain-active-* markers, no flash_chord container, and the card idle (under IDLE_MIB used)
# for IDLE_S straight. The pilot itself re-checks before every episode and exits 4 (rxzhou back) or 3 (card busy);
# then this waits again from zero. Any other exit status ends the wait.
#   setsid nohup t3_yield_wait.sh t3_init_pilot.sh ep13_snack_box ep28_squeegee > /dev/null 2>&1 < /dev/null &
# Log: logs/t3_yield_wait.log (one line per state change and every half hour while waiting).
set -u
S=$(cd "$(dirname "$0")" && pwd)
T=${T3_ROOT:-/lab_data/yqchen/v2d/tier3}
IDLE_S=${IDLE_S:-1800}
IDLE_MIB=${IDLE_MIB:-2000}
POLL_S=${POLL_S:-300}
LOG=$T/logs/t3_yield_wait.log
RX_RUNS=${RX_RUNS:-/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge/runs}
say() { echo "$(date +%m-%d_%T) $*" >> "$LOG"; }
rx_busy() { compgen -G "$RX_RUNS/.chain-active-*" > /dev/null || docker ps --format '{{.Image}}' | grep -q '^flash_chord'; }
used() { nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1; }
say "start: $*"
idle_since=""; last_note=0
while true; do
  now=$(date +%s)
  if rx_busy || [ "$(used)" -ge "$IDLE_MIB" ]; then
    [ -n "$idle_since" ] && say "busy again (rxzhou chain or $(used) MiB used), idle clock reset"
    idle_since=""
    if [ $((now - last_note)) -ge 1800 ]; then say "waiting: rxzhou chain or card in use ($(used) MiB)"; last_note=$now; fi
  else
    [ -z "$idle_since" ] && { idle_since=$now; say "card idle and no rxzhou chain, clock started"; }
    if [ $((now - idle_since)) -ge "$IDLE_S" ]; then
      say "idle for $((now - idle_since)) s, running $1"
      "$S/$1" "${@:2}"; rc=$?
      say "$1 exited $rc"
      case $rc in 3|4) idle_since="" ;; *) say "WAIT DONE"; exit "$rc" ;; esac
    fi
  fi
  sleep "$POLL_S"
done
