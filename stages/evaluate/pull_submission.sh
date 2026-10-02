#!/usr/bin/env bash
# 把打包要用的东西从训练机拉到 Mac（Mac 上、仓库根执行）。计划 agent-doc/plan-submission-exports-2026-10-02.md 第 3.4 节。
# 只走 ssh 流（ml40 上 scp 会卡住，见 ml40 的运维记录）；每个文件落地后与远端的 sha256 逐个核对，有一个不对就退出码 1。
# 目标文件已存在：内容相同就跳过，不同就拒绝（退出码 1），不覆盖。
# 用法：
#   pull_submission.sh data                       mf4090 的 Tier 1 干净参考（meta、data、mesh、README.md）与 Tier 2 发布输入（meta、data、README.md）
#                                                 → data/challenge/track_2/<档位目录>/。打包器用干净参考核帧、算本地分数，用网格算 AUC 的交叉核对
#   pull_submission.sh refs                       mf4090 的 runs/submission/frame_refs_t2/ → 同名目录（Tier 2 打包的 --frame-references）
#   pull_submission.sh exports <机器> <结果表名>    远端 runs/exports/<结果表名>.tsv（export_chain.sh 写的）里状态为 ok、fallback 的 JSON 与 parquet
#                                                 → runs/submission/final/t<档位>/episode_XXXXXX.{json,parquet}；no_eval、fallback_noeval 的（不满足候选条件）
#                                                 → runs/submission/final/held/t<档位>/；
#                                                 结果表本身存到 runs/submission/final/<结果表名>.tsv；按结果表里的 sha256 核
#   pull_submission.sh compat <机器>              兼容性验证里 1 个世界的导出（stages/evaluate/compat/<机器>.tsv 的 export 行）→ runs/submission/compat/t<档位>/
# 机器：mf4090 用 .env，ml40 用 .env.ml40（scripts/dev/_load-env）。最后一行 PULL_OK <文件数> 或 PULL_FAIL <原因>。
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
MODE=${1:?用法见文件头}
fail() { echo "PULL_FAIL $*"; exit 1; }
host_env() { case "$1" in mf4090) unset V2D_ENV ;; ml40) export V2D_ENV=ml40 ;; *) fail "机器只能是 mf4090 或 ml40：$1" ;; esac; . scripts/dev/_load-env; }
lsha() { shasum -a 256 "$1" | cut -d' ' -f1; }
mkdir -p runs/submission; TMP="$(mktemp -d runs/submission/.pull.XXXXXX)"; trap 'rm -rf "$TMP"' EXIT   # 临时目录放在 runs/ 下（不进 git），不用系统 /tmp
n=0
place() {  # place <拉到的临时文件> <目标> <期望 sha256>：核对后放到目标；目标已存在且相同就跳过
  local got; got="$(lsha "$1")"
  [ "$got" = "$3" ] || fail "sha256 不符：${2}（远端 ${3:0:16}…，拉到 ${got:0:16}…）"
  if [ -e "$2" ]; then
    [ "$(lsha "$2")" = "$3" ] || fail "目标 $2 已存在且内容不同，不覆盖"
  else
    mkdir -p "$(dirname "$2")"; cp -p "$1" "$2"
  fi
  n=$((n + 1))
}
stream() {  # stream <文件清单>：按清单（相对远端仓库根）用一个 tar 流拉到 $TMP/x/
  mkdir -p "$TMP/x"
  ssh "$V2D_HOST" "cd '$V2D_REMOTE' && tar cf - -T -" < "$1" | tar xf - -C "$TMP/x" || fail "tar 流中断"
}
remote_sha() {  # remote_sha <文件清单> <输出>：远端现算 sha256，输出“sha256  路径”
  ssh "$V2D_HOST" "cd '$V2D_REMOTE' && tr '\\n' '\\0' | xargs -0 sha256sum" < "$1" > "$2" || fail "远端 sha256sum 失败"
}

case "$MODE" in
  data)
    host_env mf4090
    D=data/challenge/track_2
    for t in tier_1_multiview_caption tier_2_synthetic_noise; do [ ! -e "$D/$t" ] || fail "$D/$t 已存在（要重拉先挪走）"; done
    ssh "$V2D_HOST" "set -o pipefail; cd '$V2D_REMOTE' && find $D/tier_1_multiview_caption/meta $D/tier_1_multiview_caption/data $D/tier_1_multiview_caption/mesh \
      $D/tier_1_multiview_caption/README.md $D/tier_2_synthetic_noise/meta $D/tier_2_synthetic_noise/data $D/tier_2_synthetic_noise/README.md -type f | sort" \
      > "$TMP/list" || fail "远端列文件失败"
    remote_sha "$TMP/list" "$TMP/sha"; stream "$TMP/list"
    while read -r sha p; do place "$TMP/x/$p" "$p" "$sha"; done < "$TMP/sha"
    echo "Tier 1 干净参考 $(grep -c tier_1_multiview_caption "$TMP/sha") 个文件、Tier 2 发布输入 $(grep -c tier_2_synthetic_noise "$TMP/sha") 个文件；清单的 sha256 $(shasum -a 256 < "$TMP/sha" | cut -c1-16)…"
    ;;
  refs)
    host_env mf4090
    R=runs/submission/frame_refs_t2
    echo "$R/manifest.tsv" > "$TMP/m"; remote_sha "$TMP/m" "$TMP/msha"; stream "$TMP/m"
    place "$TMP/x/$R/manifest.tsv" "$R/manifest.tsv" "$(cut -d' ' -f1 < "$TMP/msha")"
    tail -n +2 "$R/manifest.tsv" | cut -f6 | sed "s|^|$R/|" > "$TMP/list"
    [ "$(wc -l < "$TMP/list" | tr -d ' ')" = 30 ] || fail "manifest 不是 30 条"
    stream "$TMP/list"
    while IFS=$'\t' read -r _ _ _ _ _ f sha; do place "$TMP/x/$R/$f" "$R/$f" "$sha"; done < <(tail -n +2 "$R/manifest.tsv")
    ;;
  exports)
    M=${2:?用法：exports <机器> <结果表名>}; NAME=${3:?用法：exports <机器> <结果表名>}; host_env "$M"
    [[ $NAME =~ ^[A-Za-z0-9_-]+$ ]] || fail "结果表名非法：$NAME"
    F=runs/submission/final
    echo "runs/exports/$NAME.tsv" > "$TMP/t"; remote_sha "$TMP/t" "$TMP/tsha"; stream "$TMP/t"
    place "$TMP/x/runs/exports/$NAME.tsv" "$F/$NAME.tsv" "$(cut -d' ' -f1 < "$TMP/tsha")"
    awk -F'\t' 'NR > 1 && ($5 == "ok" || $5 == "fallback" || $5 == "no_eval" || $5 == "fallback_noeval") { print $6; print $7 }' "$F/$NAME.tsv" > "$TMP/list"
    [ -s "$TMP/list" ] || fail "结果表里没有能拉的行"
    stream "$TMP/list"
    while IFS=$'\t' read -r tier ep run step st j q jsha qsha; do
      case "$st" in ok|fallback) sub="t$tier" ;; no_eval|fallback_noeval) sub="held/t$tier" ;; *) continue ;; esac
      e6="$(printf %06d "$ep")"
      [[ $(basename "$j") == "episode_$e6.json" && $(basename "$q") == "episode_$e6.parquet" ]] || fail "Tier $tier ep${ep} 的文件名与 episode 不符：$j"
      place "$TMP/x/$j" "$F/$sub/episode_$e6.json" "$jsha"; place "$TMP/x/$q" "$F/$sub/episode_$e6.parquet" "$qsha"
    done < <(tail -n +2 "$F/$NAME.tsv")
    echo "结果表 ${NAME}：$(awk -F'\t' 'NR > 1 { c[$5]++ } END { for (s in c) printf "%s %d  ", s, c[s] }' "$F/$NAME.tsv")"
    ;;
  compat)
    M=${2:?用法：compat <机器>}; host_env "$M"
    awk -F'\t' '$1 == "export" && $4 == 1 { print $2 "\t" $3 }' "stages/evaluate/compat/$M.tsv" > "$TMP/rows"
    [ -s "$TMP/rows" ] || fail "stages/evaluate/compat/$M.tsv 没有 1 个世界的 export 行"
    ssh "$V2D_HOST" "cd '$V2D_REMOTE' && while IFS=\$'\\t' read -r run step; do ls runs/flash_chord/\$run/export_8c778f9/s\${step}_w1/episode_*.json runs/flash_chord/\$run/export_8c778f9/s\${step}_w1/episode_*.parquet; done" \
      < "$TMP/rows" > "$TMP/list" 2> "$TMP/err" || true
    [ "$(wc -l < "$TMP/list" | tr -d ' ')" = "$((2 * $(wc -l < "$TMP/rows" | tr -d ' ')))" ] \
      || fail "远端缺兼容性验证的导出（compat 跑完了吗）：$(head -3 "$TMP/err" | tr '\n' ' ')"
    remote_sha "$TMP/list" "$TMP/sha"; stream "$TMP/list"
    while read -r sha p; do
      run="$(cut -d/ -f3 <<< "$p")"; tier="${run:1:1}"
      place "$TMP/x/$p" "runs/submission/compat/t$tier/$(basename "$p")" "$sha"
    done < "$TMP/sha"
    ;;
  *) fail "不认识的模式 $MODE" ;;
esac
echo "PULL_OK $n"
