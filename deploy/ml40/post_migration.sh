#!/usr/bin/env bash
# ml40 docker 存储迁移之后的收尾。整段在 ml40 上后台跑完，不依赖 Mac 在线（用户会断网去做别的事）。
# 以 rxzhou 执行，不需要 sudo。工作目录不能在旧仓库里（第 3 步要搬走它），所以从 /lab_data/rxzhou 起：
#   cd /lab_data/rxzhou && setsid nohup bash ~/v2d/maniphys_lab_v2d_challenge/deploy/ml40/post_migration.sh \
#     /lab_data/rxzhou/ops/migrate-apply-<时间>.log > /lab_data/rxzhou/ops/post-migration-<时间>.log 2>&1 < /dev/null &
# 步骤，任何一步不符即停；日志最后一行是 POST_MIGRATION_DONE 或 POST_MIGRATION_FAILED：
#   1. 等迁移日志出结果；回滚或中止就停
#   2. 复核（判据事先定好）：flash_chord:latest 镜像 ID 仍以 sha256:96c808f9 开头；用新存储上的镜像以 64 个世界
#      评测冒烟 policy，与迁移前 256 个世界的结果 ADD-AUC 差 < 0.005、checkpoint 相同（stages/policy/eval_compare.py）
#   3. 搬仓库副本：deploy/ml40/move_repo.sh --apply（旧副本改名为 .pre-move，不删）
#   4. 在新位置跑包装的行为测试 stages/policy/test_fc_wrappers.sh
# 第 2、4 步的输出经 scripts/dev/record 落到仓库的 results/ops/，随仓库一起搬到新位置。
# 不做的事：--cleanup（删系统盘上的 docker 旧数据）与删除 .pre-move，都等人确认；Mac 上的 .env.ml40 改路径由 Mac 侧做。
set -uo pipefail
MLOG=${1:?用法：post_migration.sh <迁移日志>}
OLD=$HOME/v2d/maniphys_lab_v2d_challenge
NEW=/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge
EXPECT_IMG=sha256:96c808f9
SMOKE=runs/flash_chord/smoke-t1-ep20-w2048-cap10m-ml40
say() { printf '[%s] %s\n' "$(date '+%F %T %Z')" "$*"; }
fail() { say "$*"; say POST_MIGRATION_FAILED; exit 1; }
case "$PWD/" in "$OLD"/*) fail "工作目录不能在旧仓库里（第 3 步要搬走它）";; esac

say "1. 等迁移结果：$MLOG"
until grep -qE '迁移完成并验收通过|已回滚|中止' "$MLOG" 2>/dev/null; do sleep 20; done
grep -q '迁移完成并验收通过' "$MLOG" || fail "迁移没有成功：$(grep -E '已回滚|中止' "$MLOG" | tail -2 | tr '\n' ' ')"
say "迁移成功：Docker Root Dir $(docker info --format '{{.DockerRootDir}}')"

say "2. 复核"
id=$(docker image inspect -f '{{.Id}}' flash_chord:latest) || fail "读不到 flash_chord:latest"
case "$id" in "$EXPECT_IMG"*) say "镜像 ID 未变：$id" ;; *) fail "镜像 ID 变了：$id" ;; esac
(cd "$OLD" && scripts/dev/record ops/eval_smoke_w64_after_migration \
   env V2D_EVAL_WORLDS=64 stages/policy/fc_eval.sh smoke-t1-ep20-w2048-cap10m-ml40 4096000) || fail "64 世界评测失败"
(cd "$OLD" && scripts/dev/record ops/eval_compare_w64_vs_w256_after_migration \
   python3 stages/policy/eval_compare.py "$SMOKE/eval_4096000_w64.json" "$SMOKE/eval_4096000_w256.json" --max-add-auc-diff 0.005) \
  || fail "64 世界与迁移前 256 世界的评测不一致，见 results/ops/eval_compare_w64_vs_w256_after_migration.txt.failed"
say "评测一致：$(grep RESULT "$OLD/results/ops/eval_compare_w64_vs_w256_after_migration.txt")"

say "3. 搬仓库副本"
bash "$OLD/deploy/ml40/move_repo.sh" --apply || fail "搬仓库失败（旧目录保持原样）"

say "4. 新位置跑包装测试"
(cd "$NEW" && V2D_RECORD_TRACEBACK_OK=1 scripts/dev/record ops/test_fc_wrappers_after_move bash stages/policy/test_fc_wrappers.sh) || fail "包装测试失败"
say "测试：$(grep -cE '^  PASS' "$NEW/results/ops/test_fc_wrappers_after_move.txt") 通过，$(grep -cE '^  FAIL' "$NEW/results/ops/test_fc_wrappers_after_move.txt") 失败"
say "完成。新仓库副本 $NEW；待人确认后再删：$OLD.pre-move 与系统盘上 /var/lib/{containerd,docker}.pre-migration（migrate_docker_storage.sh --cleanup）"
say POST_MIGRATION_DONE
