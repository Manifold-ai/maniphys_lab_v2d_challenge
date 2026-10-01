# 计划：Tier 2 批量第 1 批（27 条逐帧满配）＋训练链发散检测（2026-10-01，第 2 版：按 Fable 5.1 审查修改）

- 分支 `track2/p1-training`；时间一律 UTC-6（丹佛夏令时，到 11/1 为止）；服务器日志是北京时间（UTC+8），比 UTC-6 早 14 小时。
- 用户 10/1 的要求原文：“把plan细化到代码执行层面 开始训练前用fable5.1review代码的高效和合理性”。
- 顺序：事实 → 本计划与代码改动 → Fable 5.1 审代码（高效、合理）与计划 → 按审查修改 → 登记提交 → 执行。

## 1. 为什么跑

每次提交要全部 30 条 episode。Tier 1 的 30 条里 27 条有 policy（第 1 批 9/30 12:59 判定完），Tier 2 一条都没有。
按我们对档位规则的解读（`agent-doc/track2-challenge-survey.md`，属解读、非官方原文）：

- Tier 2 的 policy 只能从 Tier 2 的参考训出来，不能拿 Tier 1 的 policy 去评 Tier 2 的参考；
- Tier 2 参考用净室版 v5.4 降噪的结果（`runs/recovery/tier2_v54`），v5.4 是事先定好的提交方法。

两张卡都空着：mf4090 从 9/30 12:35、ml40 从 14:35 起。SOP“下一步与待办”里排在下一批 GPU 任务的两件事是：

- Tier 2 批次；
- 训练链加发散检测：冒烟判据查 W&B 摘要的 NaN 与最终 checkpoint 的非有限参数，正式训练挂 `ckpt_nonfinite.py --watch`。

本计划把两件事一起做。

## 2. 事实（10/1 00:00 前后实测，结果文件见括号）

1. **参考数据**：两台训练机上 `runs/motion/tier2/whole_body/soma/sequence_id=*/robot_name=g1/data.parquet` 各 30 个，sha256 两台逐个相同；
   30 条的物体位姿全部来自 `runs/recovery/tier2_v54/`（`results/t2/motion_tier2_sha_{mf4090,ml40}.txt`）。
   重定向汇总 `results/batch_summary_v040_t2v54.tsv` 的 Tier 2 行：28 条 OK，ep7 iron 与 ep20 rice_cooker 是 ALIGN
   （物体比桌面低 20.7 mm、22.1 mm），ep29 rolling_luggage 左右手接触帧都是 0（左脚推，NOCONTACT）。
2. **支撑面**（`stages/policy/support_kinds.py`，只读 Tier 2 的拷贝；`results/t2/support_kinds_tier2_{mf4090,ml40}.txt`，两台一致）：
   - 只有地面（空 Xform）16 条；
   - 圆柱 11 条；
   - 带 `xformOp:scale` 的方盒 3 条：ep1 vacuum、ep7 iron、ep28 squeegee。
   v0.4.0 与 kit 指定的评测运行时 aee95f2 会把这 3 个方盒建成 1 m 实心立方体（发散排查，H1′ 支持），所以这 3 条等组委会答复，本批不排。
3. **训练链现状**：`stages/policy/day2_train_chain.sh` + `stages/evaluate/day2_eval_chain.sh`，第 1 批跑通 21 条。缺口有四处：
   - 冒烟判据 `smoke_check.sh` 不查 NaN；
   - 正式训练不挂看守。Tier 1 第 1 批里 ep1 在 v0.4.0 上从 5000 万步那份 checkpoint 起有 5892 / 1,207,577 个参数是 NaN，
     链没发现，一直训到 3.5 亿步、写了 DONE；
   - 正向核对只断言 parquet 路径含 `sequence_id=<序列>/robot_name=g1/data.parquet`，t2 的 run 指到 tier1 的同名序列也能过；
   - 评测链固定评最后三个 checkpoint。
4. **产能**（第 1 批实测，没发散的 run）：
   - 正式训练：ml40（1000 万 buffer）2 h 03 min 到 2 h 31 min；mf4090（400 万）1 h 57 min 到 2 h 14 min；
   - 冒烟加 256 世界 rollout 每条约 5 分钟；
   - 4096 世界评测每份：ml40 5.5 到 6.6 分钟，mf4090 约 5 分钟。
5. **机器**（10/1 13:56 北京时间，即 9/30 23:56 UTC-6；开链前由 `chain_preflight.sh` 再核一遍并落盘 `results/t2/preflight_<机器>.txt`）：
   - 两台 GPU 0 MiB、没有进程、没有 `runs/.chain-active-*`；
   - 镜像 ml40 `flash_chord:latest` 96c808f9…、mf4090 6f423d57…，与第 1 批相同；
   - 两台的 `.v2d-source-commit` 都是 `3ade51abb6f7-dirty`（9/30 渲染素材时同步的），开链前必须重新同步到干净的提交。
6. **磁盘**：ml40 `/lab_data` 剩 1.9 TB。mf4090 系统盘剩 6.8 GB（96%），各项占用：
   - `runs/flash_chord` 14 GB，其中 state 文件 64 个共 10.25 GB，policy 699 个共 3.39 GB；
   - 一条正式 run 509 MB：两份 state 各 160 MB、35 份 policy 共约 170 MB、本地 W&B 41 MB；
   - 一条冒烟 159 MB（一份 state）；一份 256 世界 rollout 约 5 MB。

   经 Mac 中转把文件从 mf4090 搬到 ml40 太慢：200 MB 跑了 5 分钟仍没传完，所以不考虑搬。
   用户提议把旧文件传到 Hugging Face。查下来现在传不了：两台服务器直连 huggingface.co 都超时（hf-mirror.com 能连，但只能下载）；
   Mac 和两台服务器上都没有 HF 的写权限 token。要走这条路，需要用户给一个写权限 token（按 CLAUDE.md 只经环境变量或 stdin），
   再试 `.env` 里的 `V2D_PROXY` 能不能把上传送到 huggingface.co。这件事不在本批的关键路径上（见第 5 节），另做。
7. **吞吐上的硬约束**：配方固定（官方 G1 FlashSAC、2048 世界、349,999,104 步、种子 42），单卡一次只跑得下一个训练；
   评测要等训练让出 GPU。能省的时间只在编排层面：评测份数、冒烟、容器启动、配置核对。

## 3. 设计

### 3.1 序列与机器分配

27 条 = 30 条去掉 ep1、ep7、ep28。按 episode 序号排好后交替分给两台，ml40 先，ml40 14 条、mf4090 13 条。
每台前 5 条为 A 段，其余为 B 段。B 段队列现在生成、随 A 一起同步；服务器上的等待包装在 A 评完后自动开 B（同第 1 批）。

| 机器 | A 段 | B 段 |
|---|---|---|
| ml40 | ep0、3、5、8、10 | ep12、14、16、18、20、22、24、26、29 |
| mf4090 | ep2、4、6、9、11 | ep13、15、17、19、21、23、25、27 |

### 3.2 配方与队列

- 官方 G1 FlashSAC，逐帧回放（不加回放或容差覆盖），2048 世界、349,999,104 步、种子 42。
- ml40 用默认的 1000 万 buffer；mf4090 加 `training.replay.capacity=4000000`。只有地面的加 `scene.support=false`。
- 队列由 `make_batch_queue.py --tier 2` 生成，命名为 `stages/policy/queues/{ml40,mf4090}_t2{a,b}{.expect.tsv,_smoke.txt,.txt}`。
- run 名用 `t2-ep<N>-w2048-{cap10m-ml40|cap4m-mf4090}`，冒烟加 `smoke-` 前缀。
- 环境变量：
  - 冒烟：`V2D_WANDB_PROJECT=v2d-selftest V2D_WANDB_TAG=smoke`；
  - 正式：`V2D_WANDB_TAG=t2batch V2D_KEEP_STATES=1`；
  - 两者都加 `V2D_MAX_RETRY=0 V2D_GPU_APPS=1 V2D_WANDB_UPLOAD_CKPT=0`。
- `V2D_KEEP_STATES=1` 只留最新一份 state，每条正式 run 省 160 MB。这一批不续训（`MAX_RETRY=0`，链对“有 state 没 DONE”的目录直接 SKIP），
  state 只在写入的瞬间有两份；checkpoint 是原子写入，不需要上一份兜底。
- mf4090 的两条训练链另设 `V2D_PRUNE_SMOKE_STATE=1 V2D_MIN_FREE_MB=1200`：冒烟全部判过、基线算完以后删掉这条冒烟自己的 state
  （只留 policy，步数记进 `STATE_PRUNED`，`smoke_check.sh` 重判时认它），每条省 160 MB。冒烟不续训，正式训练也不从冒烟的 state 起步，删掉不丢信息。

### 3.3 训练链的改动（代码已写，见第 6 节清单）

1. **档位断言**：从 run 名的 `t<档位>-` 前缀取档位，正向核对改成断言
   `task.parquet~=/repo/runs/motion/tier<档位>/whole_body/soma/sequence_id=<序列>/robot_name=g1/data.parquet`；
   名字没有档位前缀，或冒烟与正式前缀不一致，停整条链。断言只在 `precheck_expect.sh` 里维护一份，训练链第 1 步直接调用它，
   开链前也用它把四段队列预跑一遍（第 7 节第 5 步）。
2. **冒烟判据加发散两条**（`smoke_check.sh`）：
   - 最新一份完整 policy 没有非有限参数（`ckpt_nonfinite.py --last --fail-on-nonfinite`）；
   - 最新一段日志的 W&B 摘要里，动作均值、熵、回报没有 nan，loss_scale 不为 0 或 nan（`train_nan_scan.py --log`）。
   回合长度与回报照打、不作判据：9/30 发散排查的经验下界（回合 ≥ 64、回报 ≥ 2.37）出自 Tier 1 的冒烟，按净室解读不拿来给 Tier 2 当门槛。
3. **正式训练挂看守**（新包装 `fc_run_watched.sh`）：
   - 后台起 `ckpt_nonfinite.py --watch`：每 120 秒扫新写完的 policy，按步数连续 2 份含非有限参数就 `fc_stop`；
     `--parent` 指向包装脚本，包装不在了它也退出；
   - 起看守 2 秒后确认它还活着，没起来就不开训练（退出码 11，链记“失败”）；
   - 前台跑 `fc_run.sh`；结束后收掉看守。成功时等 12 秒（扫描只认 10 秒前写完的文件），再扫一遍最新 policy；
   - 退出码 9：看守止损。判据是这次追加的看守日志里有 `NAN_WATCH_STOPPED`，或 fc_run 按 STOP 退出（3）且日志里已有看守调用 fc_stop 前打的那一行
     （真的 fc_stop 要等 `docker stop` 最多 60 秒，看守可能来不及打出 `NAN_WATCH_STOPPED` 就被收掉）；
   - 看守在调用 fc_stop 前再查一次 DONE，已结束的 run 不止损，交给训完后的最终检查；
   - 退出码 10：训完但最新 policy 非有限，写 `NONFINITE`，评测链不评。
   - 链把 9 和 10 都记为“发散”，最后一行改成 `DAY2_TRAIN_DONE（完成 x、失败 y、跳过 z、发散 v）`。
   - 一条 run 从开始出 NaN 到被停，最多再跑约 2 份 checkpoint（约 2000 万步，6 到 7 分钟），
     比 Tier 1 第 1 批 ep1 的情形（多训 3 亿步、约 2.5 小时）短得多。
4. **磁盘守卫**：每条冒烟与正式开跑前，仓库所在分区可用空间不到 `V2D_MIN_FREE_MB`（默认 2048 MB，mf4090 设 1200 MB）就停整条链
   （`DAY2_TRAIN_FAILED`），评测链照常评已有 DONE 的。一条正式 run 运行中最多多占约 0.52 GB（写新 state 的瞬间两份共存）。
5. **运行时守卫**：环境或队列行里出现 `V2D_FC_SRC`（会把 #185 补丁源码副本挂成 /workspace）就停链，除非 `V2D_ALLOW_FC_SRC=1`。
   这一批全部用 third_party 里的上游 v0.4.0，和 Tier 1 第 1 批相同；fc_run 的运行记录只记 third_party 的提交，看不出挂了哪份源码，所以靠守卫保证。
   开链前 `chain_preflight.sh` 另核：third_party 的 HEAD 是 33129dd、已跟踪文件没有改动、support.py 的 md5 是 95e5e33f…（`results/diverge/support_py_versions.txt`）。
6. **冒烟 rollout 的非有限世界**：冒烟通过那一行照打 256 世界 rollout 里非有限世界的个数，只报数、不作判据
   （第 1 批 ep7 在 1 m 立方体几何上是 172 / 256，这是最便宜的几何异常信号）。
7. **B 段的开跑门槛**改用 `chain_after.sh`：等 A 段评测链结束，A 段训练链最后一行是 `DAY2_TRAIN_DONE` 且“完成”≥ 3 条才开 B，
   否则在 B 的日志里写原因与 `DAY2_TRAIN_FAILED`。“完成”不够的来路有发散、失败、显存不足（链遇退出码 4 直接 break）、冒烟没过，几种都不该接着烧 B 段的 GPU。

### 3.4 评测与判定

- 评测链加 `V2D_EVAL_STEPS`，本批设为 `349999104`，只评最终 checkpoint：按训练时的回放、4096 世界，核对 step_count。
  第 1 批每条评最后三份，只有最终那份用于判定和提交，另两份只报走势。这一批每条省两份评测，ml40 约 13 分钟、mf4090 约 10 分钟，
  全批约 5 GPU 小时。policy 全留着，以后要看走势可以补评。
- 判定用 `batch_verdict.py --steps 349999104`，判据同 Day 1：chord_sr > 0、maniptrans_sr > 0、ADD-AUC 高于这条序列 Tier 2 参考的不动基线；
  边缘标注同第 1 批。只有一份评测时没有走势，也不做“checkpoint sha256 两两不同”这一条。
- ep20 rice_cooker 的 Tier 2 参考里物体比桌面低 22.1 mm（重定向对齐检查 ALIGN）。事先登记：它若不通过，先归到参考几何（物体陷进桌面），
  不当作训练或方法的问题；看它评测输出里的终止原因是否集中在物体。
- 这些数字都是对着 Tier 2 v5.4 参考算的，不是对着官方计分用的真值，所以三点要守：
  - 不与 Tier 1 的数字比；
  - 不拿来调降噪器或超参；
  - 写进执行记录和 SOP 时注明“对照 Tier 2 参考”。

### 3.5 净室

- 训练只读 `runs/motion/tier2` 的 parquet、Tier 2 支撑面的拷贝与 Tier 2 的物体网格。
- 队列生成只读 `batch_summary_v040_t2v54.tsv` 的 Tier 2 行与 Tier 2 支撑面清单，不读 Tier 1 的统计。
- 配方是官方配方，不是由 Tier 1 结果调出来的。
- 排除 ep1、ep7、ep28 的依据是两样：Tier 2 支撑面文件本身，和导入器代码的事实（support.py 不读 scale）。

## 4. 判据（执行前登记）

- **冒烟通过**：
  - 第 1 批的各项冒烟判据（DONE、编译成功、无显存错误、checkpoint 步数、W&B 同步、显存峰值、镜像指纹）；
  - 3.3 节第 2 条的两项发散判据；
  - 256 世界 rollout 的帧数等于源帧数。

  不通过的，这条的正式训练记 SKIPPED，其余照跑。显存峰值上限沿用第 1 批：ml40 44000 MiB、mf4090 24564 MiB。
- **正式训练**的结局分五种：
  - 完成：有 DONE，最新 policy 有限；
  - 发散：看守止损，或 NONFINITE；
  - 失败：其他非零退出；
  - 跳过：冒烟没过，或目录有残留；
  - 显存不足：退出码 4，这台这段剩下的全部停。

  都不人工续训。
- **能进候选**：完成、有最终 checkpoint 的评测、step_count = 源帧数、non_finite_worlds 为空、结果头的来历不带 -dirty / -syncing。
  满足的，`policy_349999104` 作为这条 Tier 2 episode 当前的候选提交 policy（aee95f2 评测器实测后确认），不从多个 checkpoint 里挑。
- **质量只报数**：Day 1 判据（见 3.4），另报 SP-SR、MPPE。
- **B 段自动开跑的条件**（每台各自判断，`chain_after.sh`），两条都要满足：
  - A 段评测链已结束；
  - A 段训练链最后一行是 `DAY2_TRAIN_DONE`，且其中“完成”≥ 3 条。

  不满足就不开 B，在 B 的训练日志里写原因与 `DAY2_TRAIN_FAILED`（让 B 的评测链空跑结束），另写诊断计划。

## 5. 时间与磁盘

- 开链约 10/1 02:30（审查与修改之后）。
  - ml40：A 段约 12.5 小时（5 条冒烟约 25 分钟，5 条训练约 11.5 小时，5 份评测约 30 分钟）；B 段 9 条约 22 小时；合计约 35 小时，约 10/2 13:30 评完。
  - mf4090：A 段约 11 小时，B 段 8 条约 17.5 小时，合计约 29 小时，约 10/2 07:30 评完。
- mf4090 的磁盘（第 1 版的估算漏了“一段的冒烟全部先跑”这一点，已按审查重算）：
  - 冒烟判过就删它的 state 之后，每条约 0.36 GB（正式 350 MB + 冒烟的 policy 与日志约 5 MB + rollout 5 MB），13 条约 4.7 GB；
  - 眼下剩 6.8 GB，跑完约剩 2.1 GB。守卫设 1200 MB：最后一条开跑前约剩 2.4 GB，过得去；
  - 估算偏了也不会写满磁盘：守卫会在某条开跑前停链，剩下的条目放下一批。
  - 第 1 批留在 mf4090 上、已经用不上的文件约 6.5 GB：22 个 DONE 冒烟的 state 约 3.5 GB，19 条 DONE 正式 run 里较旧的一份 state 约 3.0 GB。
    这一批不碰它们。用户提议传到 HF 再删，条件见事实 6，另做。

## 6. 代码清单（10/1 提交前的工作树）

| 文件 | 改动 | 测试 |
|---|---|---|
| `stages/policy/support_kinds.py` | 新：列支撑面形状与带 scale 的方盒 | 已在两台实跑，结果一致 |
| `stages/policy/make_batch_queue.py` | 加 `--tier 2`；`V2D_QUEUE_DIR` | `test_make_batch_queue.py`：Tier 1 重新生成第 1 批四份队列与已提交的逐字节相同；Tier 2 的行、拒排方盒、拒绝覆盖 |
| `stages/policy/ckpt_nonfinite.py` | 加 `--fail-on-nonfinite`、看守的 `--parent` | `test_ckpt_nonfinite.py` 原 6 项 + 2 项 |
| `stages/policy/train_nan_scan.py` | 加 `--log`（单个日志的发散判据，退出码） | `test_train_nan_scan.py`：摘要段取自真实日志，5 项 |
| `stages/policy/smoke_check.sh` | 加两项发散判据；等 policy 写完满 11 秒；认 `STATE_PRUNED` | 在服务器上对第 1 批已知正常的冒烟与发散的 run 各跑一次（执行第 3 步） |
| `stages/policy/fc_run_watched.sh` | 新：正式训练的看守包装 | `test_fc_run_watched.py`：正常、中途发散、最后一份非有限、fc_run 失败、慢 fc_stop、看守起不来六种，且不留看守进程 |
| `stages/policy/day2_train_chain.sh` | 第 1 步调 precheck、正式走看守包装（退出码 9 / 10 / 11）、磁盘守卫（MB）、`V2D_FC_SRC` 守卫、冒烟 state 删除（开关）、rollout 非有限世界照打 | `bash -n`；开链时第 1 步正向核对就是实跑 |
| `stages/evaluate/day2_eval_chain.sh` | `V2D_EVAL_STEPS`；跳过 NONFINITE | `bash -n` |
| `stages/evaluate/batch_verdict.py` | `--steps` | 默认三步时，第 1 批四份判定与 9/30 落盘结果逐行相同 |
| `stages/policy/precheck_expect.sh` | 档位断言、`V2D_FC_SRC` 守卫；训练链第 1 步改为调用它 | 开链前四段实跑 |
| `stages/policy/chain_after.sh` | 新：B 段门槛（等 A 评完、完成 ≥ 3） | `test_chain_after.py` 4 项 |
| `stages/policy/chain_preflight.sh` | 新：开链前环境核对 | 两台实跑并落盘 |
| `stages/policy/fc_config_check.sh` | 一次接受多份队列、按 parquet 缓存官方配方 | `bash -n`；开链前实跑 |

## 7. 执行步骤

1. Mac：按审查改代码与计划，五个 Python 测试（test_ckpt_nonfinite、test_train_nan_scan、test_make_batch_queue、test_fc_run_watched、test_chain_after）在 Mac 上全过，提交、推送（工作树干净）。
2. Mac：生成四段队列并提交：
   ```
   python3 stages/policy/make_batch_queue.py --tier 2 ml40 t2a agent-doc/plan-t2-batch-2026-10-01.md 0 3 5 8 10
   python3 stages/policy/make_batch_queue.py --tier 2 ml40 t2b agent-doc/plan-t2-batch-2026-10-01.md 12 14 16 18 20 22 24 26 29
   python3 stages/policy/make_batch_queue.py --tier 2 mf4090 t2a agent-doc/plan-t2-batch-2026-10-01.md 2 4 6 9 11
   python3 stages/policy/make_batch_queue.py --tier 2 mf4090 t2b agent-doc/plan-t2-batch-2026-10-01.md 13 15 17 19 21 23 25 27
   ```
3. 同步：`V2D_DRYRUN=1 scripts/dev/remote`、`scripts/dev/remote`；ml40 同样加 `V2D_ENV=ml40`。核对两台 `.v2d-source-commit` 等于本地提交、不带 -dirty。
4. 两台各自落盘环境核对与测试：
   - `scripts/dev/record t2/preflight_<机器> ssh <机器> 'cd <仓库> && stages/policy/chain_preflight.sh'`，要 PREFLIGHT_OK；
   - 这五个 Python 测试与 `bash stages/policy/test_fc_wrappers.sh`；
   - 新冒烟判据的回归：对第 1 批一条正常冒烟应得 SMOKE_OK（ml40 `smoke-t1-ep12-w2048-cap10m-ml40`、mf4090 `smoke-t1-ep6-w2048-cap4m-mf4090`）；
     mf4090 的 `t1-ep1-w2048-cap4m-mf4090`（发散）用 `train_nan_scan.py --log` 与 `ckpt_nonfinite.py --last --fail-on-nonfinite` 都应得退出码 1。
     这条回归测不到“刚写完 10 秒内”的情形，那种情形由 smoke_check 里的等待与 Mac 上的测试覆盖。
5. 配置核对与正向预跑：两台各在 tmux 里对自己四份队列一次跑完 `fc_config_check.sh`（同一 parquet 的官方配方只展开一次），
   再对 A、B 两段各跑 `precheck_expect.sh`，日志写到 `runs/logs/t2_cfgcheck_<机器>.log`。
   跑完用 `scripts/dev/record t2/cfgcheck_<机器> ssh <机器> cat …` 落盘。意外差异为 0、两段都 PRECHECK_OK 才开链；不过就停下改。
6. 开链：每台四个 tmux。ml40 在 `/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge` 下：
   ```
   tmux new-session -d -s v2d-t2a -c "$PWD" 'stages/policy/day2_train_chain.sh stages/policy/queues/ml40_t2a.expect.tsv stages/policy/queues/ml40_t2a_smoke.txt stages/policy/queues/ml40_t2a.txt 44000 t2a_train_ml40'
   tmux new-session -d -s v2d-t2a-eval -c "$PWD" 'V2D_EVAL_STEPS=349999104 V2D_WAIT_FOR_LOG=runs/logs/t2a_train_ml40.log stages/evaluate/day2_eval_chain.sh stages/policy/queues/ml40_t2a.expect.tsv - t2a_eval_ml40'
   tmux new-session -d -s v2d-t2b -c "$PWD" 'stages/policy/chain_after.sh runs/logs/t2a_train_ml40.log runs/logs/t2a_eval_ml40.log 3 stages/policy/queues/ml40_t2b.expect.tsv stages/policy/queues/ml40_t2b_smoke.txt stages/policy/queues/ml40_t2b.txt 44000 t2b_train_ml40'
   tmux new-session -d -s v2d-t2b-eval -c "$PWD" 'V2D_EVAL_STEPS=349999104 V2D_WAIT_FOR_LOG=runs/logs/t2b_train_ml40.log stages/evaluate/day2_eval_chain.sh stages/policy/queues/ml40_t2b.expect.tsv - t2b_eval_ml40'
   ```
   mf4090 在 `~/v2d/maniphys_lab_v2d_challenge` 下，命令见附录 A：显存上限是 **`24564`**，两条训练命令前加 `V2D_PRUNE_SMOKE_STATE=1 V2D_MIN_FREE_MB=1200`。
   开链后确认：
   - 两台 A 段正向核对通过，日志里有“含档位目录”；
   - 第一条冒烟 SMOKE_OK，打出 policy 与摘要那一行；mf4090 还要有“冒烟 … 的 state 已删”；
   - 第一条正式 run 的 `runs/logs/<run>.nanwatch.log` 有“开始看守”；
   - A 段评测链与 B 段的 `chain_after.sh` 都在等。

   之后只做短查询。
7. 收尾：A 段评完后，先用 `scripts/dev/pull-results` 和 `V2D_ENV=ml40 scripts/dev/pull-results` 拉回结果。两台各自落盘判定：
   ```
   scripts/dev/record t2/batch_verdict_<机器>_t2a python3 stages/evaluate/batch_verdict.py stages/policy/queues/<机器>_t2a.expect.tsv <结果目录> --steps 349999104
   ```
   结果目录：mf4090 是 `results/day2`，ml40 是 `results/ml40/day2`。

   然后确认 B 段已自动开跑、第一条冒烟 SMOKE_OK。执行记录写在 `agent-doc/experiments/2026-10-01-t2-batch.md`，承重结论过 jev。B 段评完同样处理。

## 8. 不做的事

- 不改配方、不调超参、不换种子，不人工续训。
- 不做参考平滑，这一批也不据抖动调任何参数。改参考是方法改动，另写计划。已有的量只有 `results/nopen_jitter.txt`，
  统计的是不穿地约束改过的 6204 帧：v5.2 角加速度中位 1.26°/帧²、p99 3.59。v5.4 全部帧的抖动还没单独量过。
- 不排 ep1、ep7、ep28。
- 链在跑期间不同步两台。
- T1 诊断（要 GPU）另写计划，排在 mf4090 跑完这一批之后。
- 本批结果不拿来调 Tier 2 / Tier 3 的方法。

## 附录 A：mf4090 的四条开链命令（逐字）

```
tmux new-session -d -s v2d-t2a -c "$PWD" 'V2D_PRUNE_SMOKE_STATE=1 V2D_MIN_FREE_MB=1200 stages/policy/day2_train_chain.sh stages/policy/queues/mf4090_t2a.expect.tsv stages/policy/queues/mf4090_t2a_smoke.txt stages/policy/queues/mf4090_t2a.txt 24564 t2a_train_mf4090'
tmux new-session -d -s v2d-t2a-eval -c "$PWD" 'V2D_EVAL_STEPS=349999104 V2D_WAIT_FOR_LOG=runs/logs/t2a_train_mf4090.log stages/evaluate/day2_eval_chain.sh stages/policy/queues/mf4090_t2a.expect.tsv - t2a_eval_mf4090'
tmux new-session -d -s v2d-t2b -c "$PWD" 'V2D_PRUNE_SMOKE_STATE=1 V2D_MIN_FREE_MB=1200 stages/policy/chain_after.sh runs/logs/t2a_train_mf4090.log runs/logs/t2a_eval_mf4090.log 3 stages/policy/queues/mf4090_t2b.expect.tsv stages/policy/queues/mf4090_t2b_smoke.txt stages/policy/queues/mf4090_t2b.txt 24564 t2b_train_mf4090'
tmux new-session -d -s v2d-t2b-eval -c "$PWD" 'V2D_EVAL_STEPS=349999104 V2D_WAIT_FOR_LOG=runs/logs/t2b_train_mf4090.log stages/evaluate/day2_eval_chain.sh stages/policy/queues/mf4090_t2b.expect.tsv - t2b_eval_mf4090'
```

## 审查与处理（第 2 版，10/1 00:20–01:10）

两份独立审查都用 Fable 5.1，结论都是 GO WITH FIXES，没有 BLOCKER。

**代码审查（高效与合理）**。效率整体没问题：每条 run 的 GPU 空转只有评测链、B 段唤醒各 ≤ 60 秒，加上写入余量与核对容器，全批不到 10 分钟；
只评最终 checkpoint 省约 5 GPU 小时；冒烟约 2.25 GPU 小时是不动基线的来源，保留。问题与处理：
- MAJOR 冒烟刚训完就判，最新 policy 写完不到 10 秒，非有限扫描不认它，会误判 SMOKE_FAIL、正式训练被跳过 → smoke_check 先等 policy 写完满 11 秒。
- MAJOR mf4090 磁盘不够跑完 B 段 → 本批冒烟判过就删自己的 state（`V2D_PRUNE_SMOKE_STATE=1`），smoke_check 重判时认 `STATE_PRUNED`；第 1 批的文件不碰。
- MINOR 看守止损的判断经管道，pipefail 下可能被 SIGPIPE 盖掉 → 改成不经管道。
- MINOR 看守在扫描与止损之间 run 刚好 DONE，会对已结束的 run 调 fc_stop → 调用前再查一次 DONE。
- MINOR 看守起不来时包装不知道 → 起 2 秒后检查，没起来就退出码 11、不开训练。
- MINOR 变量紧跟全角字符没加花括号（仓库约定）→ 改完，并扫过全部改动行。
- MINOR 官方配方按队列行各展开一次 → `fc_config_check.sh` 一次接受多份队列，同一 parquet 只展开一次。
- MINOR 测试里 Tier 2 帧数断言分不出来源 → 注释改成“只作回归”。

**计划审查（合理性）**：
- MAJOR 磁盘估算漏了“一段的冒烟全部先跑”，B 段会白跑冒烟 → 用冒烟 state 删除重算（第 5 节），守卫改按 MB 判。
- MAJOR 没预跑 `precheck_expect.sh`，而且它还是旧断言 → 断言改成档位感知并只维护这一份，训练链第 1 步调用它；开链前四段都预跑（第 7 节第 5 步）。
- MAJOR B 段开跑条件只数发散，A 段全败也会开 B → 改成“完成 ≥ 3”（`chain_after.sh`，带测试）。
- MAJOR 没核挂进容器的 third_party 工作树 → `chain_preflight.sh` 核 HEAD、已跟踪文件、support.py md5、镜像指纹，落盘。
- MINOR 冒烟 rollout 的非有限世界没登记 → 照打个数；ep20 陷桌面的判定口径事先登记（第 3.4 节）。
- MINOR “抖动怎么看”没写清 → 第 8 节引 nopen_jitter.txt 并写明口径。
- MINOR 看守止损的标签依赖时序，假 fc_stop 没覆盖 → 退出码 3 加 fc_stop 那一行也记 9，测试里用会睡几秒的假 fc_stop 覆盖。
- MINOR 事实 5、6 没落盘、ep1 的措辞 → preflight 落盘；改成“5892 / 1,207,577 个参数是 NaN”。

净室方面，计划审查人核过：队列生成只读 Tier 2 行与 Tier 2 支撑面；不动基线出自 Tier 2 冒烟；门槛是结构性的。
排除方盒三条依据的“方盒致发散”是 Tier 1 实验的结论，属解读，计划已标明。
