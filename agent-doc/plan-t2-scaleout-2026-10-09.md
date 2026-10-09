# 计划：Tier 2 变体 A 铺开（24 条，ml40，2026-10-09，第 1 版）

用户 10/9：“进行 Tier 2 铺开和 Tier 3 试跑”。依据是第 3 步配方试验的 Tier 2 判定通过（`results/ml40/r3/verdict_t2.txt`：S1–S6 全过，
S1 的平均 MP-SR 差 +0.9335），以及 `agent-doc/plan-step3-recipe-trial-2026-10-04.md` 第 5 节登记的铺开：其余 24 条用变体 A、seed 42，
在 v5.4 参考上训练，全在 ml40 上，约 66 小时。本计划只把登记的铺开落成可执行的链，不改配方。
“每条 episode 交哪一个”（甲：全换变体 A；乙：按 4096 世界 MP-SR 取高者；丙：按交上去那条轨迹对照 v5.4 打分挑）仍由用户定，
训练与它无关，CSV 另写计划。时间一律 UTC−6。Tier 3 试跑另见 `agent-doc/plan-t3-pilot-2026-10-09.md`。

## 1. 事实

- **试验证据覆盖的情形。** 试验 5 条与对照 ep22 的基线，4096 世界失败原因里骨盆的比例是 0.001–0.051；变体 A 的 MP-SR 是 0.934–1.000
  （`results/ml40/day2/eval_t2-ep{8,12,20,24,26,22}-w2048-cap10m{,-r3a,-r3a-s43}-ml40_s349999104.txt`）。
  铺开的 24 条里，基线骨盆比例低于 0.5 的 14 条与试验同属一种情形；ep17 是 0.607；ep9、1、13、19、2、4、14、25、28 这 9 条在 0.994–1.000，
  几乎每个世界都摔，试验没有覆盖，变体 A 对它们的效果是外推。
- **基线。** 24 条现在交的 run（`stages/evaluate/exports/{ml40,mf4090}.tsv`）：ml40 上 1000 万 buffer 的 10 条（含 ep1 的 `-p185`、ep7 的 `-p185g`），
  mf4090 上 400 万 buffer 的 14 条（含 ep28 的 `-p185`）。对照 v5.4 的 4096 世界 MP-SR：19 条是 0，其余是 ep0 0.362、ep10 0.271、ep29 0.140、
  ep7 0.067、ep18 0.040（`results/ml40/day2/`、`results/day2/` 下各基线的 `eval_<run>_s349999104.txt`）。
- **输入**（`results/ops/t2x_inputs_ml40_1009.txt`、`results/ops/t2x_inputs_mf4090_1009.txt`，`tools/motion_inputs_remote.sh`）：
  24 条的参考 parquet 在两台机器上 sha256 相同，并且等于各自基线 `run_record.jsonl` 记下的 `parquet_sha256`；
  `runs/motion_src/tier2/<序列>/v2d_meta.json` 与支撑面文件都在，两台相同；没有旧版的 `<序列>_g1_support.usda`。
- **机器**（`results/ops/machines_1009_1325.txt`、`results/ops/gpu_procs_ml40_1009_1340.txt`、`results/ops/t3_queue_ml40_1009_1335.txt`）：
  10/9 13:21 ml40 的 L40S 没有进程（同事的 Tier 3 CARI4D 队列 11:51 结束）；我们在 ml40 上没有会话和长链标记；`/lab_data` 可用约 1.6 TB；
  同事在宿主机上跑 CPU 任务（剪影检查第二版、换物体增强）。ml40 的来历是 d8b309e，起链前要同步到新的 HEAD。
- **同事的 GPU 任务会等我们。** 他的 CARI4D 队列在每个 GPU 阶段前等 L40S 空出 44 GB（`t3_queue_cari4d.sh`）。我们的链占卡期间，他的 GPU 阶段一直等，
  不会出错。我们这边，`fc_run.sh` 开新段前、`day2_train_chain.sh` 每条 run 前都查 GPU 上有没有别的进程，有就停，不与他抢卡。
- **代价。** 试验 A 段在 ml40 上每条正式训练 2:10–2:29（`agent-doc/experiments/2026-10-05-step3-recipe-trial.md`）。24 条：冒烟、正式、
  4096 世界评测、1 世界导出合计约 60–66 小时。10/9 傍晚起链，约 10/12 上午结束。

## 2. run

24 条，命名 `t2-ep<N>-w2048-cap10m-r3a-ml40`，seed 42。配置：官方 G1 配方，只改变体 A 的两个取值
（`objective.object_position_std=0.05`、`termination.object_orientation_threshold=0.6`），加基线原有的 `scene.support=false`（基线有才加）；
buffer 用 ml40 的默认 1000 万（基线在 mf4090 上的，去掉 `training.replay.capacity=4000000`）；2048 个世界、3.5 亿步、逐帧回放。
训练挂带非有限防护的 `v040_p185_nfg`（与试验相同），评测与导出用 `fc_8c778f9`。W&B 标签 `t2x`，不上传 checkpoint（`V2D_WANDB_UPLOAD_CKPT=0`），
`V2D_MAX_RETRY=0`（与试验相同）。

**顺序**按基线的骨盆比例从低到高（相同按 episode 号）：与试验同一情形的放前面，链中途要停时，最可能受益的先训完：

ep29、23、6、18、7、16、0、21、15、10、27、3、5、11、17、9、1、13、19、2、4、14、25、28。

## 3. 做法

1. **代码**（各带测试）：
   - `stages/policy/make_var_queue.py`：生成本计划的 t2x 清单与 Tier 3 试跑的 t3p 清单。t2x 从基线派生，复用 `make_trial_queue.py` 的 `baseline()`
     （期望表与队列各恰好一种、冒烟与正式一致、步数、没有种子与变体的键、种子 42）；基线覆盖里只允许 `scene.support=false` 与
     `training.replay.capacity=4000000`，出现别的键就报错。写 `stages/policy/queues/ml40_t2x{.expect.tsv,_smoke.txt,.txt}` 与导出清单
     `stages/evaluate/exports/cand_t2_t2x_ml40.tsv`。测试 `stages/policy/test_make_var_queue.py`。
   - `stages/policy/arm_var_chain.sh t2x|t3p`：`arm_r3x_chain.sh` 的参数化版本。按名字取机器、GPU 型号、副本目录、冒烟显存上限、
     起链时要求的可用空间、档位和条数；核对项与 `arm_r3x_chain.sh` 相同（GPU 型号、来历干净、日志与标记与会话都不存在、GPU 空、可用空间、
     副本按 sha256 清单核对、`v2d_meta.json` 都在、run 目录没有训练产物、导出清单与期望表一致、配置 precheck 与配方断言）。
     `V2D_ARM_DRYRUN=1` 只核不起。t2x：L40S、`/lab_data/rxzhou/v2d/fc_src`、冒烟显存上限 44000 MiB（同试验）、可用空间 ≥ 200 GB、24 条。
2. **部署**：提交、推送，同步 ml40 与 mf4090；测试在两台上用最终版本跑，经 `scripts/dev/record` 落盘。
3. **起链**（ml40，都经 record 落到 `results/t2x/`）：`fc_config_check.sh` 展开 48 份配置 → `V2D_ARM_DRYRUN=1 arm_var_chain.sh t2x` → `arm_var_chain.sh t2x`。
   三个会话：`v2d-t2x-train`（训练链）→ `v2d-t2x-eval`（等训练链结束，只评最终 checkpoint，4096 世界）→
   `v2d-t2x-export`（导出门：评测链最后一行是“成功 N、失败 0”才导出，1 个世界，`V2D_FALLBACK_MAX=0`）。
4. **等**：链在 ml40 的 tmux 里跑，Mac 可以离线。每天 7 点的 SOP 更新顺带看链的状态。
5. **结束后**（约 10/12）：训练健康记录（同 r3x 的 R1 做法）→ 拉回评测与导出 → 按用户定的甲、乙或丙另写 CSV 计划。不提交。

## 4. 判据（执行前登记）

| 编号 | 判据 |
|---|---|
| R1 训练健康 | 每条 run：冒烟通过，有 `DONE`，没有 `NONFINITE`，run 日志里 `NONFINITE_GUARD_STOP` 0 次；训练链最后一行的“发散”为 0 |
| R2 评测 | 每条有 DONE 的 run 有 4096 世界评测：`world_count` 4096、`non_finite_worlds` 为空、`step_count` 与 sha256 和导出相同；评测链最后一行“失败 0” |
| R3 导出 | 每条导出状态 `ok`（只用最终 checkpoint，不回退） |

- R1–R3 不过的 run 不进候选，照实记下，不换参数重跑。原因在基础设施（W&B 网络、GPU 被别人占、磁盘）时，链结束后用同一配置原样补跑一次，记下。
- 评测链没有干净结束时，导出门一条都不导；补评与手动导出的做法同 `agent-doc/plan-t1-r3x-2026-10-08.md` 第 4 节。
- **只报**：每条的 4096 世界 MP-SR、SP-SR、ADD-AUC、MPPE 与失败原因（对照 v5.4），与基线并列；按基线骨盆比例“< 0.5”（14 条）、
  ep17、“≥ 0.99”（9 条）分组汇总，最后一组是外推，单独写。

## 5. 风险

- **同事要用卡。** L40S 会被占约 2.5 天。他要用时，给还没开始的 run 建 `runs/flash_chord/<run>/STOP`（`fc_run.sh` 开新段前见到就退出码 3，
  不开训），当前 run 训完后链自然走完；剩下的以后用同一队列续起（有 DONE 的跳过）。不停正在训的 run：续训不恢复 replay，停了这条就作废。
- **外推。** 变体 A 在几乎每个世界都摔的 9 条上没有证据。乙、丙两种挑法都只在更好时换，CSV 不会因此变差；甲会，这一点在用户定挑法时说明。
- **W&B 网络。** 10/8 mf4090 上 ep5 seed 42 开跑两分钟 `wandb.init` 超时，`V2D_MAX_RETRY=0` 下这条被跳过。按第 4 节，链结束后原样补跑一次。
- **来历。** 起链后长链标记挡住 ml40 的同步；Tier 3 试跑只同步 mf4090。
- **链被意外杀掉。** 没有结束行，下游的链会一直等，长链标记挡同步。先确认三个会话与相关进程都不在，再删 `runs/.chain-active-t2x_*` 与
  `runs/.chain-active-cand_t2_t2x_ml40*`，从断处续。
- **档位隔离。** 只读 Tier 2 的 v5.4 参考，评测只对照 v5.4；不读 Tier 1。

## 6. 产物

代码与测试（第 3 节第 1 步）；`results/t2x/` 下的测试、配置展开、预演、起链与健康记录；`results/ops/` 下的输入核对；执行记录写在本计划末尾；jev 规格与结果。
