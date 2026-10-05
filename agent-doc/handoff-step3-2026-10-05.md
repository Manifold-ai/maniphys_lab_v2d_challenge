# 交接：第 3 步配方试验与 Tier 2 降噪（2026-10-05 13:40，UTC-6；分支 track2/p1-training）

## 目标

- 第 3 步：变体 A（`objective.object_position_std=0.05`、`termination.object_orientation_threshold=0.6`）在每档 5 条“差一点”的 episode 与 1 条对照上试，
  按登记的 S1–S6 判，过了再铺开到 30 条。计划 `agent-doc/plan-step3-recipe-trial-2026-10-04.md` 第 2 版。
- Tier 2 降噪改进，只用 Tier 2 验证。计划 `agent-doc/plan-tier2-denoise-2026-10-04.md` 第 2 版。

## 已完成

- 两份计划经 Fable 5.1 审查后改为第 2 版（e333ac2），审查与处理意见在 `agent-doc/review-*-2026-10-04.md`。
- Tier 2 降噪评价跑完：没有候选通过，保持 v5.4（`agent-doc/experiments/2026-10-05-t2-denoise-eval.md`，jev 7/7，97e46a0）。
- Tier 2 配方试验：G1 全过，10/5 12:10 在 ml40 起链；Tier 1：按用户指示停掉 mf4090 上同事的空闲 GPU 容器后，G1 全过，13:30 起链
  （`agent-doc/experiments/2026-10-05-step3-recipe-trial.md`）。恢复那个容器：`docker start maniphys-geyu-shared-dev-person-120`。

## 在跑

两台各四个 tmux：`v2d-r3-a-train`、`v2d-r3-a-eval`、`v2d-r3-bc-gate`、`v2d-r3-bc-eval`。查进度（mf4090 把路径换成 `~/v2d/maniphys_lab_v2d_challenge`、
日志后缀换成 `_mf4090`、档位换成 t1）：

```
ssh ml40 'cd /lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge && for l in r3t2a_train r3t2a_eval r3t2bc_train r3t2bc_eval; do echo "$l：$(grep -a "^=== " runs/logs/${l}_ml40.log | tail -1)"; done'
```

链在跑时 `scripts/dev/remote` 拒绝同步（长链标记），只读查询直接 ssh。预计：Tier 2 中途检查 10/6 01:40、全部评完 10/7 00:10；
Tier 1 中途检查 10/6 03:15、全部评完 10/7 01:45（判继续时）。

## 评完之后

1. `V2D_ENV=ml40 scripts/dev/pull-results`（ml40）、`scripts/dev/pull-results`（mf4090）。
2. 在 ml40 上：`scripts/dev/record r3/verdict_t2 python3 stages/evaluate/trial_verdict.py stages/evaluate/trials/r3_t2_ml40.json`；
   mf4090 上同理用 `r3_t1_mf4090.json`
   （中途检查判停时会报 STOPPED_AT_MIDCHECK，结论看 `runs/logs/r3t2bc_train_ml40.log` 里段间门的输出）。
3. 归因项：对变体与基线各 run 跑 `stages/policy/wandb_local_history.py --by-stage`（容器里），看第 6–8 段的终止:物体与进度（计划第 4 节）。
4. 写进执行记录，过 jev，报用户。通过时铺开与“每条 episode 交哪一个”要用户定（计划第 5 节）。

## 要用户定

1. 视频路线的可行性闸（降噪计划第 7 节）。
2. 重定向一侧的支撑面穿透要不要查（降噪执行记录“只报”一节）。
3. 仍未决的：邀请 Nvidia-V2D-Challenge 进仓库、什么时候交哪一档。
