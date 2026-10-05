# 第 3 步配方试验：执行记录（2026-10-05 起，UTC-6）

计划 `agent-doc/plan-step3-recipe-trial-2026-10-04.md` 第 2 版（e333ac2；Fable 5.1 审第 1 版后修改，判据在跑之前登记）。工具 c575560：
`stages/policy/make_trial_queue.py`（队列与试验清单）、`stages/evaluate/trial_verdict.py`（中途检查与 S1–S6）、`stages/policy/chain_after.sh` 的段间判定命令、
`stages/policy/trial_g1.sh`（闸 G1）、`stages/policy/arm_trial_chains.sh`（配方断言、起四个会话）。测试在 Mac 与 ml40 宿主上都过
（`test_trial_verdict.py` 14 项、`test_chain_after.py` 7 项、`test_make_trial_queue.py` 3 项、`test_tier_guard.py`）。

## Tier 2（ml40）

### 闸 G1（10/5 11:20–12:09，`results/ml40/r3/g1_*`）

| 步 | 结果 |
|---|---|
| 1 展开配置 | 两段 32 份配置（16 条 run 与冒烟）`fc_config_check.sh` 全过，意外差异 0；变体的 `objective.object_position_std`、`termination.object_orientation_threshold` 与 `env.` 下的两份副本都判“允许” |
| 2 变体冒烟 | `smoke-t2-ep8-w2048-cap10m-r3a-ml40`（400 万步，v040_p185_nfg）约 3 分钟训完 |
| 3 评冒烟 | fc_8c778f9 按 4096 世界评测成功，`non_finite_worlds` 为空，指标有限（`EVAL_CHECK OK`）：官方评测器能读变体 A 的 checkpoint |
| 4 重评基线 | 6 条基线 seed 42（试验 5 条、对照 ep22）用 8c778f9 重评，与当时 v0.4.0 的数相比 MP-SR 差在 0.011 以内（ep22 0.735 对 0.724），checkpoint 相同 |
| 5 重复噪声 | ep22 基线用 8c778f9 再评一次：MP-SR 0.7336 对 0.7354（差 −0.0017），ADD-AUC 差 −0.0002，SP-SR 差 +0.0007 |

同一评测器重复评的差（0.002）远小于 S2 的 0.05 边距与 S1 的 0.15 门槛。

### 起链（10/5 12:10）

`arm_trial_chains.sh ml40`（`results/ml40/r3/arm_ml40.txt`；预演 `arm_dryrun_ml40.txt`）：来历 c575560，GPU 空闲，副本核对通过，32 份配置的配方断言全过，
6 条基线重评都在，段间门的判定命令在 ml40 宿主上能跑（预期地报“变体还没有评测结果”）。四个会话：

| 会话 | 日志 | 作用 |
|---|---|---|
| v2d-r3-a-train | `runs/logs/r3t2a_train_ml40.log` | A 段：ep8、12、20、24、26 与对照 ep22 的变体 A seed 42 |
| v2d-r3-a-eval | `runs/logs/r3t2a_eval_ml40.log` | A 段训完后用 8c778f9 评最终 checkpoint（4096 世界） |
| v2d-r3-bc-gate | `runs/logs/r3t2bc_train_ml40.log` | A 段评完、完成 6 条，跑 `trial_verdict.py --midcheck`，CONTINUE 才开 BC 段 |
| v2d-r3-bc-eval | `runs/logs/r3t2bc_eval_ml40.log` | BC 段（基线 seed 43 与变体 A seed 43）训完后评 |

预计：A 段约 10/6 01:40 评完、做中途检查；判继续时 BC 段约 10/7 00:10 评完。G1 的冒烟被链认作 DONE，没有重训。

## Tier 1（mf4090）

没有开跑：mf4090 的 GPU 上有别人的进程（`maniphys_visual_worker`，容器 `maniphys-geyu-shared-dev-person-120`，10/4 早上起，占 2.7 GB 显存、利用率 0%），
训练链与评测的 GPU 检查都会停。队列与试验清单已生成（`stages/policy/queues/mf4090_r3t1*`、`stages/evaluate/trials/r3_t1_mf4090.json`），等用户定。
