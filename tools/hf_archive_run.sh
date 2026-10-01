#!/usr/bin/env bash
# 归档的完整流程（训练机上、仓库根执行，setsid nohup 后台跑）：上传 → 核对 → 抽查 → 删除，任何一步不过就停。
# 计划 agent-doc/plan-hf-archive-2026-10-01.md（第 2 版）。凭据只经环境变量进来：启动方经 stdin 读入后 export
# HF_TOKEN、https_proxy、HTTPS_PROXY、HF_ENDPOINT=https://huggingface.co，本脚本不读 .env、不打印它们。
# 删除前后各记一份 t2 目录（Tier 2 第 1 批在用）的文件清单与磁盘余量。训练链同时在写新 checkpoint、按 V2D_KEEP_STATES=1
# 剪旧 state，所以判据是：删除期间 t2 目录里消失的只能是 state_*.safetensors（被训练剪掉的），其他文件一个都不能少。
# 用法：bash runs/tools/hf_archive_run.sh <清单.json> <用户/仓库> <机器名> <输出前缀，如 runs/hf_archive_mf4090>
# 最后一行 HF_ARCHIVE_DONE、HF_ARCHIVE_T2_CHECK_FAILED 或 HF_ARCHIVE_STOPPED <哪一步>。
set -uo pipefail
M=${1:?清单}; REPO=${2:?仓库}; PREFIX=${3:?机器名}; OUT=${4:?输出前缀}
T=runs/tools/hf_archive.py
ts() { date '+%F %T %Z'; }
stop() { echo "=== $(ts) HF_ARCHIVE_STOPPED $1"; exit 1; }
free_mb() { df -Pk . | awk 'NR == 2 {print int($4 / 1024)}'; }
t2_list() { find runs/flash_chord -mindepth 2 -maxdepth 2 -path '*t2-*' -type f -printf '%p\n' | sort; }
echo "=== $(ts) 开始；工具 md5 $(md5sum "$T" | cut -d' ' -f1)；清单 $M（$(python3 -c 'import json, sys; print(len(json.load(open(sys.argv[1]))))' "$M") 个文件）；可用 $(free_mb) MB"
python3 "$T" upload --manifest "$M" --repo "$REPO" --prefix "$PREFIX" || stop upload
python3 "$T" verify --manifest "$M" --repo "$REPO" --prefix "$PREFIX" --out "$OUT.verified.json" || stop verify
python3 "$T" spotcheck --verified "$OUT.verified.json" --n 3 --out "$OUT.spotcheck.json" || stop spotcheck
t2_list > "$OUT.t2_before.txt"
python3 "$T" delete --verified "$OUT.verified.json" --spotcheck "$OUT.spotcheck.json" --yes || stop delete
t2_list > "$OUT.t2_after.txt"
gone="$(comm -23 "$OUT.t2_before.txt" "$OUT.t2_after.txt")"
odd="$(grep -v -E '/state_[0-9]+\.safetensors$' <<< "$gone" | grep . || true)"
echo "=== $(ts) t2 目录：删除前 $(wc -l < "$OUT.t2_before.txt") 个文件、删除后 $(wc -l < "$OUT.t2_after.txt") 个；期间被训练剪掉的 state $(grep -c . <<< "$gone") 个；其他消失的文件：${odd:-无}"
echo "=== $(ts) 删除后可用 $(free_mb) MB"
if [ -n "$odd" ]; then echo "=== $(ts) HF_ARCHIVE_T2_CHECK_FAILED"; exit 1; fi
echo "=== $(ts) HF_ARCHIVE_DONE"
