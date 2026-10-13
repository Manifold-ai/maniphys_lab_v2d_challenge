#!/usr/bin/env bash
# 等上一段的长链都结束、卡空，先跑一条前置命令，再看上一段是否全部做完，都过了再起下一段（训练机上执行，setsid 后台跑）。
# 计划 agent-doc/plan-mf4090-handover-2026-10-13.md（第 2 版）。
# 链在跑时 scripts/dev/remote 拒绝同步，服务器上的仓库副本里可能还没有本脚本：复制到 runs/tools/ 再跑，复制时记下 md5（同 queue_after.sh）。
# 用法：bash runs/tools/arm_after.sh <下一段段名> <上一段训练日志> <上一段评测日志> <上一段导出日志> <上一段条数>
#   V2D_PRE_CMD：前置命令（可选），在仓库根用 bash -c 跑，限时 V2D_PRE_TIMEOUT_S 秒（默认 3600），退出码 0 才往下（这次是 HF 第 4 批的删除）
#   V2D_POLL_S（默认 60）；V2D_AFTER_MAX_POLLS（等上一段，默认 720 次，约 12 小时）；V2D_GPU_MAX_POLLS（等卡空，默认 120 次，约 2 小时）
# 1. 记下来历（.v2d-source-commit）与下一段的队列、导出清单的 md5。
# 2. 每 V2D_POLL_S 秒看一次：runs/.chain-active-* 一个都没有，且训练、评测日志的最后一行分别是 DAY2_TRAIN_DONE/FAILED、DAY2_EVAL_DONE/FAILED，才往下走。
#    本脚本自己不写长链标记：删除一步见到任何标记都会停（hf_archive_run.sh）；等待期间不同步这台机器，第 6 步再核一次。
# 3. 卡空：nvidia-smi 没有计算进程，也没有导出、评测、训练相关的进程（同 hf_archive_run.sh 删除前的闸）。
# 4. 跑 V2D_PRE_CMD，输出照抄；超时或退出码非 0 不起。前置命令不看上一段的结局（删除只要求没有链、卡空）。
# 5. 上一段全部做完才起（D 计划第 4 节“每集”与“停”）：训练日志最后一行 DAY2_TRAIN_DONE（完成 <条数>、失败 0、跳过 0、发散 0），
#    评测日志 DAY2_EVAL_DONE（成功 N、失败 0）且 N ≥ 1，导出日志 EXPORT_CHAIN_DONE（成功 <条数>、失败 0）。
# 6. 来历与 md5 跟第 1 步相同（这段时间没有同步、队列没变）。
# 7. 从环境里去掉 HF 凭据、代理与前置命令（HF_TOKEN、https_proxy、HTTPS_PROXY、http_proxy、HTTP_PROXY、HF_ENDPOINT、V2D_PRE_CMD）。
# 8. V2D_ARM_DRYRUN=1 stages/policy/arm_var_chain.sh <段名>：退出码 0、最后一行 DRYRUN_OK 才起；再 stages/policy/arm_var_chain.sh <段名>：
#    退出码 0、最后一行 ARMED。两次的核对都由 arm_var_chain.sh 自己做（GPU、来历、磁盘、配置等）。
# 抄进本日志的上一段的行把结束标记换成中文（同 train_after.sh：别的脚本按日志最后一行判结局）。
# 最后一行 ARM_AFTER_ARMED，或 ARM_AFTER_STOPPED <原因>。
# 测试：stages/policy/test_arm_after.py。
set -uo pipefail
N=${1:?用法见文件头}; PT=${2:?}; PE=${3:?}; PX=${4:?}; PN=${5:?}
[[ $N =~ ^[a-z0-9_]+$ ]] || { echo "arm_after: 段名非法：$N" >&2; exit 2; }
[[ $PN =~ ^[1-9][0-9]*$ ]] || { echo "arm_after: 上一段条数必须是正整数：$PN" >&2; exit 2; }
cd "$(dirname "$0")/../.."
[ -f stages/policy/arm_var_chain.sh ] || { echo "arm_after: 不在仓库根（找不到 stages/policy/arm_var_chain.sh）" >&2; exit 2; }
POLL=${V2D_POLL_S:-60}; MAXA=${V2D_AFTER_MAX_POLLS:-720}; MAXG=${V2D_GPU_MAX_POLLS:-120}; PTO=${V2D_PRE_TIMEOUT_S:-3600}
ts() { date '+%F %T %Z'; }
say() { echo "=== $(ts) $*"; }
stop() { say "ARM_AFTER_STOPPED $*"; exit 1; }
free_mb() { df -Pk . | awk 'NR == 2 {print int($4 / 1024)}'; }
markers() { ls runs/.chain-active-* 2>/dev/null | tr '\n' ' '; }
last() { tail -1 "$1" 2>/dev/null; }
demark() { sed -E 's/DAY2_TRAIN_(DONE|FAILED)/训练链结束（\1）/g; s/DAY2_EVAL_(DONE|FAILED)/评测链结束（\1）/g; s/EXPORT_CHAIN_(DONE|FAILED)/导出链结束（\1）/g'; }
snap() { cat .v2d-source-commit 2>&1; md5sum stages/policy/queues/*_"$N".* stages/policy/queues/*_"$N"_* stages/evaluate/exports/cand_t*_"$N"_*.tsv 2>&1; }

S0="$(snap)"
say "等 runs/.chain-active-* 都消失、$PT 与 $PE 写完最后一行，再起 ${N}；前置命令：${V2D_PRE_CMD:-无}；可用 $(free_mb) MB"
say "来历与 ${N} 的队列：$(tr '\n' ' ' <<< "$S0")"
i=0
until [ -z "$(markers)" ] && last "$PT" | grep -qE 'DAY2_TRAIN_(DONE|FAILED)' && last "$PE" | grep -qE 'DAY2_EVAL_(DONE|FAILED)'; do
  i=$((i + 1)); [ "$i" -le "$MAXA" ] || stop "等了 ${MAXA} 次还没结束（标记：$(markers)）"
  sleep "$POLL"
done
say "上一段的链都结束了。训练：$(last "$PT" | demark)；评测：$(last "$PE" | demark)；导出：$(last "$PX" | demark)"

j=0
while :; do
  g="$(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader 2>&1)" || stop "nvidia-smi 查不了 GPU：$g"
  b="$(pgrep -af '[f]c_export|[f]c_eval|[f]c_run|[e]xport_chain|[c]ase_clip' || true)"
  [ -z "$g" ] && [ -z "$b" ] && break
  j=$((j + 1)); [ "$j" -le "$MAXG" ] || stop "卡上或机器上还有进程：$(printf '%s %s' "$g" "$b" | tr '\n' ' ' | cut -c1-300)"
  sleep "$POLL"
done
say "卡空，也没有导出、评测、训练相关的进程；可用 $(free_mb) MB"

if [ -n "${V2D_PRE_CMD:-}" ]; then
  say "前置命令开始（限时 ${PTO} 秒）"
  timeout "$PTO" bash -c "$V2D_PRE_CMD"; rc=$?
  say "前置命令退出码 ${rc}；可用 $(free_mb) MB"
  [ "$rc" = 0 ] || stop "前置命令没过（退出码 ${rc}$([ "$rc" = 124 ] && echo '，超时')）"
fi

last "$PT" | grep -qF "DAY2_TRAIN_DONE（完成 ${PN}、失败 0、跳过 0、发散 0）" || stop "上一段训练没有全部完成（要 ${PN} 条完成、失败跳过发散都是 0）"
last "$PE" | grep -qE 'DAY2_EVAL_DONE（成功 [1-9][0-9]*、失败 0）' || stop "上一段评测有失败或没有正常结束"
last "$PX" | grep -qF "EXPORT_CHAIN_DONE（成功 ${PN}、失败 0）" || stop "上一段导出没有全部成功（要 ${PN} 条成功、失败 0）"
[ "$(snap)" = "$S0" ] || stop "来历或 ${N} 的队列在等待期间变了：$(snap | tr '\n' ' ')"
say "上一段 ${PN} 条训练、评测、导出都做完；来历与队列没变"

unset HF_TOKEN https_proxy HTTPS_PROXY http_proxy HTTP_PROXY HF_ENDPOINT V2D_PRE_CMD
out="$(V2D_ARM_DRYRUN=1 bash stages/policy/arm_var_chain.sh "$N" 2>&1)"; rc=$?
printf '%s\n' "$out"
[ "$rc" = 0 ] && [ "$(tail -1 <<< "$out")" = DRYRUN_OK ] || stop "预演没过（退出码 ${rc}）"
out="$(bash stages/policy/arm_var_chain.sh "$N" 2>&1)"; rc=$?
printf '%s\n' "$out"
[ "$rc" = 0 ] && [ "$(tail -1 <<< "$out")" = ARMED ] || stop "起链没起全（退出码 ${rc}）"
say ARM_AFTER_ARMED
