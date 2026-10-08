#!/usr/bin/env bash
# 归档的完整流程（训练机上、仓库根执行，setsid nohup 后台跑）：上传 → 核对 → 抽查 → 删除，任何一步不过就停。
# 计划 agent-doc/plan-hf-archive-2026-10-01.md（state，第 2 版）与 agent-doc/plan-hf-archive-policies-2026-10-08.md（policy 中间份）。
# 凭据只经环境变量进来：启动方经 stdin 读入后 export HF_TOKEN、https_proxy、HTTPS_PROXY、HF_ENDPOINT=https://huggingface.co，
# 本脚本不读 .env、不打印它们。
# V2D_HF_ARCHIVE_STEPS：all（默认，一口气做完）、verify（上传、核对、抽查后停在删除前，等用户点头）、
#   delete（删除前先重新核对一遍仓库，落到 <输出前缀>.reverified.json，再按它与前一次的 .spotcheck.json 删）。
# V2D_HF_SPOTCHECK_N：抽查下载几个文件，默认 3；V2D_HF_SPOTCHECK_PER_RUN=1 时改成每条 run 随机挑 1 个。
# 删除前这几种情况就停：有训练链在跑（runs/.chain-active-*）、GPU 上有进程、有导出评测训练相关的进程
# （fc_export、fc_eval、fc_run、export_chain、case_clip），它们会删 runs/flash_chord 下的临时文件，让下面的比对误报。
# 删除前后各记一份 runs/flash_chord 下全部文件的清单与磁盘余量，判据：删除期间消失的文件只能是清单里的，其他文件一个都不能少；
# 另外报出清单里没删掉的个数（被重算的保护或本地改动挡下的）。
# 用法：bash runs/tools/hf_archive_run.sh <清单.json> <用户/仓库> <机器名> <输出前缀，如 runs/hf_archive_mf4090>
# 最后一行 HF_ARCHIVE_DONE、HF_ARCHIVE_VERIFIED、HF_ARCHIVE_FILES_CHECK_FAILED 或 HF_ARCHIVE_STOPPED <哪一步>。
set -uo pipefail
M=${1:?清单}; REPO=${2:?仓库}; PREFIX=${3:?机器名}; OUT=${4:?输出前缀}
STEPS="${V2D_HF_ARCHIVE_STEPS:-all}"; N="${V2D_HF_SPOTCHECK_N:-3}"; PER_RUN="${V2D_HF_SPOTCHECK_PER_RUN:-0}"
case "$STEPS" in all|verify|delete) ;; *) echo "V2D_HF_ARCHIVE_STEPS 只能是 all、verify、delete" >&2; exit 2 ;; esac
[[ $N =~ ^[1-9][0-9]*$ ]] || { echo "V2D_HF_SPOTCHECK_N 必须是正整数" >&2; exit 2; }
case "$PER_RUN" in 0) SPOT=(--n "$N"); SPOT_DESC="${N} 个" ;; 1) SPOT=(--per-run); SPOT_DESC="每条 run 1 个" ;;
  *) echo "V2D_HF_SPOTCHECK_PER_RUN 只能是 0 或 1" >&2; exit 2 ;; esac
T=runs/tools/hf_archive.py
ts() { date '+%F %T %Z'; }
stop() { echo "=== $(ts) HF_ARCHIVE_STOPPED $1"; exit 1; }
free_mb() { df -Pk . | awk 'NR == 2 {print int($4 / 1024)}'; }
all_files() { find runs/flash_chord -type f -printf '%p\n' | sort; }
echo "=== $(ts) 开始（步骤 ${STEPS}，抽查 ${SPOT_DESC}）；工具 md5 $(md5sum "$T" | cut -d' ' -f1)；清单 $M（$(python3 -c 'import json, sys; print(len(json.load(open(sys.argv[1]))))' "$M") 个文件，md5 $(md5sum "$M" | cut -d' ' -f1)）；可用 $(free_mb) MB"
if [ "$STEPS" != delete ]; then
  python3 "$T" upload --manifest "$M" --repo "$REPO" --prefix "$PREFIX" || stop upload
  python3 "$T" verify --manifest "$M" --repo "$REPO" --prefix "$PREFIX" --out "$OUT.verified.json" || stop verify
  python3 "$T" spotcheck --verified "$OUT.verified.json" "${SPOT[@]}" --out "$OUT.spotcheck.json" || stop spotcheck
fi
if [ "$STEPS" = verify ]; then
  echo "=== $(ts) 上传、核对、抽查都通过，按约定停在删除前，等用户确认；HF_ARCHIVE_VERIFIED"
  exit 0
fi
[ -s "$OUT.verified.json" ] && [ -s "$OUT.spotcheck.json" ] || stop "delete（缺核对或抽查结果）"
if [ "$STEPS" = delete ]; then
  python3 "$T" verify --manifest "$M" --repo "$REPO" --prefix "$PREFIX" --out "$OUT.reverified.json" || stop reverify
  V="$OUT.reverified.json"
else
  V="$OUT.verified.json"
fi
ls runs/.chain-active-* >/dev/null 2>&1 && stop "delete（有训练链在跑）"
gpu="$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>&1)" || stop "delete（nvidia-smi 查不了 GPU）"
[ -z "$gpu" ] || stop "delete（GPU 上有进程：$(tr '\n' ' ' <<< "$gpu")）"
busy="$(pgrep -af '[f]c_export|[f]c_eval|[f]c_run|[e]xport_chain|[c]ase_clip' || true)"
[ -z "$busy" ] || stop "delete（有导出、评测或训练相关的进程：$(tr '\n' ' ' <<< "$busy" | cut -c1-300)）"
all_files > "$OUT.files_before.txt"
python3 "$T" delete --verified "$V" --spotcheck "$OUT.spotcheck.json" --yes || stop delete
all_files > "$OUT.files_after.txt"
python3 -c 'import json, sys
for r in json.load(open(sys.argv[1])):
    print("runs/flash_chord/%s/%s" % (r["run"], r["file"]))' "$V" | sort > "$OUT.allowed.txt"
comm -23 "$OUT.files_before.txt" "$OUT.files_after.txt" > "$OUT.gone.txt"
odd="$(comm -23 "$OUT.gone.txt" "$OUT.allowed.txt")"
kept="$(comm -13 "$OUT.gone.txt" "$OUT.allowed.txt" | grep -c . || true)"
echo "=== $(ts) runs/flash_chord：删除前 $(wc -l < "$OUT.files_before.txt") 个文件、删除后 $(wc -l < "$OUT.files_after.txt") 个；消失 $(wc -l < "$OUT.gone.txt") 个（清单 $(wc -l < "$OUT.allowed.txt") 个，其中没删的 ${kept} 个）；清单外消失的文件：${odd:-无}"
echo "=== $(ts) 删除后可用 $(free_mb) MB"
if [ -n "$odd" ]; then echo "=== $(ts) HF_ARCHIVE_FILES_CHECK_FAILED"; exit 1; fi
echo "=== $(ts) HF_ARCHIVE_DONE"
