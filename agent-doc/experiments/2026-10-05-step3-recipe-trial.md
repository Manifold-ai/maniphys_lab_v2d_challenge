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
A 段 6 条冒烟都过（256 世界 rollout 非有限世界 0），12:37 起正式训练。

## Tier 1（mf4090）

10/5 12:51 按用户的指示（“mf4090 上同事那个占着 GPU 的进程直接停掉 开始我们的任务”）停掉了 GPU 上的空闲容器 `maniphys-geyu-shared-dev-person-120`
（`docker stop`，记录 `results/ops/mf4090_stop_person_container_1005.txt`；恢复用 `docker start maniphys-geyu-shared-dev-person-120`，重启策略
`unless-stopped`，没人启动就一直停着）。停之前它占 2.7 GB 显存、GPU 利用率 0%、CPU 0.01%；停之后 GPU 上 0 个进程。同组的
`maniphys-visual-dev-worker-120` 有 GPU 权限但没有占用，没动。

### 闸 G1（10/5 12:52–13:29，`results/r3/g1_*`）

| 步 | 结果 |
|---|---|
| 1 展开配置 | 32 份配置全过，意外差异 0 |
| 2 变体冒烟 | `smoke-t1-ep6-w2048-cap4m-r3a-mf4090` 约 4 分钟训完 |
| 3 评冒烟 | fc_8c778f9 按 4096 世界评测成功，`non_finite_worlds` 为空（`EVAL_CHECK OK`） |
| 4 重评基线 | 6 条基线 seed 42 用 8c778f9 重评，与 v0.4.0 的数相比 MP-SR 差在 0.008 以内（ep6 0.570 对 0.562，与兼容性验证 P4 相同），checkpoint 相同 |
| 5 重复噪声 | ep8 基线再评一次：MP-SR 0.9802 对 0.9768（差 +0.0034），ADD-AUC 差 +0.0006 |

### 起链（10/5 13:30）

`arm_trial_chains.sh mf4090`（`results/r3/arm_mf4090.txt`；预演 `arm_dryrun_mf4090.txt`）：来历 bbaa151，GPU 空闲，32 份配置的配方断言全过，6 条基线重评都在。
四个会话同 ml40，日志 `runs/logs/r3t1{a,bc}_{train,eval}_mf4090.log`。预计 A 段 10/6 03:15 前后评完、做中途检查；判继续时 BC 段 10/7 01:45 前后评完。
