# 计划：Tier 2 变体 A 铺开（24 条，ml40，2026-10-09，第 2 版）

第 1 版（c413099）经 Fable 5.1 独立审查（GO WITH FIXES，3 条 MAJOR），按意见改成本版，逐条处理见文末“审查与处理”。

用户 10/9：“进行 Tier 2 铺开和 Tier 3 试跑”。依据是第 3 步配方试验的 Tier 2 判定通过（`results/ml40/r3/verdict_t2.txt`：S1–S6 全过，
S1 的平均 MP-SR 差 +0.9335），以及 `agent-doc/plan-step3-recipe-trial-2026-10-04.md` 第 5 节登记的铺开：其余 24 条用变体 A、seed 42，
在 v5.4 参考上训练，全在 ml40 上，约 66 小时。本计划只把登记的铺开落成可执行的链，不改配方。
“每条 episode 交哪一个”（甲：全换变体 A；乙：按 4096 世界 MP-SR 取高者；丙：按交上去那条轨迹对照 v5.4 打分挑）仍由用户定，
训练与它无关，CSV 另写计划。时间一律 UTC−6。Tier 3 试跑另见 `agent-doc/plan-t3-pilot-2026-10-09.md`。

## 1. 事实

- **试验证据覆盖的情形**（`results/t2x/baseline_table_1009.txt`，由 `stages/evaluate/eval_table.py` 汇总 `results/ml40/day2/`、`results/day2/` 下的评测文本）。
  试验 5 条与对照 ep22 的基线，4096 世界失败原因里骨盆的比例是 0.001–0.051；变体 A 的 MP-SR 是 0.934–1.000。
  铺开的 24 条里，基线骨盆比例低于 0.5 的 14 条与试验同属一种情形；ep17 是 0.607；ep9、1、13、19、2、4、14、25、28 这 9 条在 0.994–1.000，
  几乎每个世界都摔，试验没有覆盖，变体 A 对它们的效果是外推。
- **基线。** 24 条现在交的 run（`stages/evaluate/exports/{ml40,mf4090}.tsv`）：ml40 上 1000 万 buffer 的 10 条（含 ep1 的 `-p185`、ep7 的 `-p185g`），
  mf4090 上 400 万 buffer 的 14 条（含 ep28 的 `-p185`）。对照 v5.4 的 4096 世界 MP-SR：19 条是 0，其余是 ep0 0.362、ep10 0.271、ep29 0.140、
  ep7 0.067、ep18 0.040（同上表）。
- **输入**（`results/ops/t2x_inputs_ml40_1009.txt`、`results/ops/t2x_inputs_mf4090_1009.txt`，`tools/motion_inputs_remote.sh`）：
  24 条的参考 parquet 在两台机器上 sha256 相同，并且等于各自基线 `run_record.jsonl` 记下的 `parquet_sha256`；
  `runs/motion_src/tier2/<序列>/v2d_meta.json` 与支撑面文件都在，两台相同；没有旧版的 `<序列>_g1_support.usda`。
- **机器**（`results/ops/machines_1009_1325.txt`、`results/ops/gpu_procs_ml40_1009_1340.txt`、`results/ops/t3_queue_ml40_1009_1335.txt`）：
  10/9 13:21 ml40 的 L40S 没有进程（同事的 Tier 3 CARI4D 队列 11:51 结束）；我们在 ml40 上没有会话和长链标记；`/lab_data` 可用约 1.6 TB；
  同事在宿主机上跑 CPU 任务（剪影检查第二版、换物体增强）。
- **占卡与同事。** 用户 10/9 指示进行，占用从 10/9 晚起：A 段约 40 小时，B 段约 24 小时（第 2 节）；同事那边由用户转告。
  同事的 CARI4D 队列在每个 GPU 阶段前等 L40S 空出 44000 MiB（`origin/track2/tier3-recon` 2ee4c5e 的 `stages/recovery/tier3/t3_queue_cari4d.sh:6-8,19-27`），
  我们占卡期间他的 GPU 阶段会一直等，不出错。我们这边，训练链与评测链见到 GPU 上有别的进程就每分钟看一次、最多等 6 小时（第 3 节），不抢卡。
- **代价。** 试验 A 段在 ml40 上每条正式训练 2:10–2:29，冒烟训练约 3 分钟（`agent-doc/experiments/2026-10-05-step3-recipe-trial.md`）。
  每段先跑完全部冒烟（训练之外还有 256 世界诊断与不动基线）才开第一条正式训练。
- **配置已展开**（`results/t2x/cfgcheck_ml40.txt`）：48 份配置（24 条 run 与冒烟）展开后与官方配方的意外差异 0。展开时用的是拆段前的队列 `ml40_t2x*`
  （52c6b17），拆成两段后每一行逐字节相同（只多了段名的注释行）；起链时 `precheck_expect.sh` 按拆段后的期望表再断言一遍。

## 2. run

24 条，命名 `t2-ep<N>-w2048-cap10m-r3a-ml40`，seed 42。配置：官方 G1 配方，只改变体 A 的两个取值
（`objective.object_position_std=0.05`、`termination.object_orientation_threshold=0.6`），加基线原有的 `scene.support=false`（基线有才加）；
buffer 用 ml40 的默认 1000 万（基线在 mf4090 上的，去掉 `training.replay.capacity=4000000`）；2048 个世界、3.5 亿步、逐帧回放。
训练挂带非有限防护的 `v040_p185_nfg`（与试验相同），评测与导出用 `fc_8c778f9`。W&B 标签 `t2x`，不上传 checkpoint（`V2D_WANDB_UPLOAD_CKPT=0`），
`V2D_MAX_RETRY=0`（与试验相同）。

**分两段**，顺序按基线的骨盆比例从低到高（按评测文本里未四舍五入的值；相同按 episode 号）：

| 段 | episode | 说明 |
|---|---|---|
| t2xa | 29、23、6、18、7、16、0、21、15、10、27、3、5、11、17 | 骨盆比例低于 0.65 的 15 条，与试验同一情形（ep17 0.607 在边上）；约 40 小时 |
| t2xb | 9、1、13、19、2、4、14、25、28 | 几乎每个世界都摔的 9 条，外推；约 24 小时 |

t2xa 现在起。t2xb 在 t2xa 的导出门结束后由我起，照登记默认要跑；起之前把 t2xa 的结果报给用户，用户要停就停。两段之间 GPU 会空一段时间，
同事要用卡可以排在这里。

## 3. 做法

1. **代码**（各带测试）：
   - `stages/policy/make_var_queue.py <段名>`：按段生成期望表、冒烟队列、正式队列与导出清单。t2x 从基线派生，复用 `make_trial_queue.py` 的 `baseline()`
     （期望表与队列各恰好一种、冒烟与正式一致、步数、没有种子与变体的键、种子 42）；基线覆盖里只允许 `scene.support=false` 与
     `training.replay.capacity=4000000`，出现别的键就报错。预设段 t2xa、t2xb；续跑与补跑用新的段名加 `--episodes`（第 4 节）。
     写 `stages/policy/queues/ml40_<段名>{.expect.tsv,_smoke.txt,.txt}` 与 `stages/evaluate/exports/cand_t2_<段名>_ml40.tsv`。
     测试 `stages/policy/test_make_var_queue.py`。
   - `stages/policy/arm_var_chain.sh <段名>`：`arm_r3x_chain.sh` 的参数化版本，核对项相同，另查停链标记不存在；冒烟目录已有 DONE 的放行
     （续跑时冒烟已经过了，训练链会重判），正式 run 的目录必须没有产物。`V2D_ARM_DRYRUN=1` 只核不起。
     t2x：L40S、`/lab_data/rxzhou/v2d/fc_src`、冒烟显存上限 44000 MiB（同试验）、可用空间 ≥ 200 GB；训练链停止阈值是默认的 2048 MB。
   - `stages/policy/day2_train_chain.sh`：加 `V2D_GPU_WAIT_S`（默认 0，即原来的“见到别的进程就停”）与停链标记 `runs/.chain-stop-<日志名>`；
     `stages/evaluate/day2_eval_chain.sh`：同样的 `V2D_GPU_WAIT_S`，开始时与每份评测前都看。两者的测试 `stages/policy/test_day2_chain_waits.py`
     （链脚本要 bash 4 以上，在服务器上跑）。本计划起链时给 `V2D_GPU_WAIT_S=21600`（6 小时）。
2. **部署**：提交、推送，同步 ml40 与 mf4090；测试在两台上用最终版本跑，经 `scripts/dev/record` 落盘。
3. **起链**（ml40，都经 record 落到 `results/t2x/`）：`V2D_ARM_DRYRUN=1 arm_var_chain.sh t2xa` → `arm_var_chain.sh t2xa`。
   三个会话：`v2d-t2xa-train`（训练链）→ `v2d-t2xa-eval`（等训练链结束，只评最终 checkpoint，4096 世界）→
   `v2d-t2xa-export`（导出门：评测链最后一行是“成功 N、失败 0”才导出，1 个世界，`V2D_FALLBACK_MAX=0`）。
4. **等**：链在 ml40 的 tmux 里跑，Mac 可以离线。每天 7 点的 SOP 更新顺带看链的状态。
5. **t2xa 结束后**（约 10/11 上午）：训练健康记录（同 r3x 的 R1 做法）→ 拉回评测与导出 → 报给用户 → 起 t2xb（同第 3 步）。
6. **全部结束后**（约 10/12）：按用户定的甲、乙或丙另写 CSV 计划。不提交。

## 4. 判据（执行前登记）

| 编号 | 判据 |
|---|---|
| R1 训练健康 | 每条 run：冒烟通过，有 `DONE`，没有 `NONFINITE`，run 日志里 `NONFINITE_GUARD_STOP` 0 次；训练链最后一行的“发散”为 0 |
| R2 评测 | 每条有 DONE 的 run 有 4096 世界评测：`world_count` 4096、`non_finite_worlds` 为空、`step_count` 与 sha256 和导出相同；评测链最后一行“失败 0” |
| R3 导出 | 每条导出状态 `ok`（只用最终 checkpoint，不回退） |

- R1–R3 不过的 run 不进候选，照实记下，不换参数重跑。原因在基础设施（W&B 网络、GPU 被别人占、磁盘）时，同一配置原样补跑一次，记下。
- **续跑与补跑**（审查 M2）：另起一段，段名不同（如 t2xa2），用 `make_var_queue.py <段名> --episodes …` 只放还没训的 run 或要补跑的 run。
  run 名不变，日志、导出名、导出结果表都是新的；已导出过的 run 不放进去，每个 checkpoint 仍只导出一次。补跑的 run 先把它失败的目录改名为
  `runs/flash_chord/<run>.attempt<k>`（记进执行记录），再起链。补跑的 W&B id 与失败那次相同（`<run>-s1`），W&B 上两段会挂在同一个 id 下，只影响看板。
- 评测链没有干净结束时，导出门一条都不导；补评与手动导出的做法同 `agent-doc/plan-t1-r3x-2026-10-08.md` 第 4 节。
- **只报**：每条的 4096 世界 MP-SR、SP-SR、ADD-AUC、MPPE 与失败原因（对照 v5.4），与基线并列；按 t2xa、t2xb 分开汇总，t2xb 是外推，单独写。
  基线在 mf4090 上的 14 条，与变体之间除配方外还差 buffer（400 万对 1000 万）、机器和训练副本（审查 m4）；只有基线在 ml40 上的 10 条是同条件的对比。

## 5. 风险

- **同事要用卡。** 要让卡时建 `runs/.chain-stop-t2xa_train_ml40`：正在训的 run 训完，剩下的冒烟与正式训练都不开，训练链照常写结束行，
  评测链与导出门接着处理已完成的 run；剩下的以后用续跑段接上（第 4 节）。不停正在训的 run：续训不恢复 replay，停了这条就作废。
  （第 1 版写的 `runs/flash_chord/<run>/STOP` 不管用：没起容器的 run，`fc_run.sh:131-134` 会把它当残留清掉。）
- **别人的进程上了卡。** 训练链在每条冒烟与正式训练前、评测链在开始时与每份评测前看 GPU，有别的进程就每分钟看一次，最多等 6 小时，空了接着跑；
  等不到才停（训练链 `DAY2_TRAIN_FAILED`、评测链 `DAY2_EVAL_FAILED`，导出门随之不导出），之后用续跑段与补评接上。
- **外推。** 变体 A 在几乎每个世界都摔的 9 条上没有证据（Tier 1 上变体 A 能把 ep5 的骨盆比例从 0.127 抬到 0.54–0.63）。所以分段，
  t2xb 起之前先报 t2xa 的结果。乙、丙两种挑法都只在更好时换，CSV 不会因此变差；甲会，这一点在用户定挑法时说明。
- **W&B 网络。** 10/8 mf4090 上 ep5 seed 42 开跑两分钟 `wandb.init` 超时，`V2D_MAX_RETRY=0` 下这条被跳过。按第 4 节补跑。
- **来历。** 起链后长链标记挡住 ml40 的同步；Tier 3 试跑只同步 mf4090。执行记录写实际的来历。
- **链被意外杀掉。** 没有结束行，下游的链会一直等，长链标记挡同步。先确认三个会话与相关进程都不在，再删 `runs/.chain-active-t2xa_*` 与
  `runs/.chain-active-cand_t2_t2xa_ml40*`，用续跑段接上。
- **档位隔离。** 只读 Tier 2 的 v5.4 参考，评测只对照 v5.4；不读 Tier 1。

## 6. 产物

代码与测试（第 3 节第 1 步）；`results/t2x/` 下的测试、配置展开、预演、起链与健康记录；`results/ops/` 下的输入核对；执行记录写在本计划末尾；jev 规格与结果。

## 审查与处理（Fable 5.1，GO WITH FIXES）——第 2 版

| 编号 | 级别 | 意见 | 处理 |
|---|---|---|---|
| M1 | MAJOR | 第 5 节的 STOP 做法不管用：没起容器的 run，`fc_run.sh:131-134` 把 STOP 当残留清掉；即使管用，退出码 3 也会被训练链记成失败、接着开下一条 | `day2_train_chain.sh` 加停链标记，见到就不开剩下的、照常写结束行；测试 `test_day2_chain_waits.py`；第 5 节改写 |
| M2 | MAJOR | 没有续跑、补跑的路：起链脚本拒绝已有的日志、导出名与有产物的 run 目录，导出结果表也不许重建 | 分段生成与起链，续跑与补跑另起一段（新段名、只放没训或要补跑的 run）；起链脚本放行已有 DONE 的冒烟目录；第 4 节写明 |
| M3 | MAJOR | 别人的进程一上卡，训练链与评测链都直接停；占卡时段没有和同事约定的记录；同事队列等 44 GB 的说法没有出处 | 两条链加有限时等卡（默认不等，本计划 6 小时），测试同上；第 1 节写明用户 10/9 指示进行、由用户转告同事，并给出同事脚本的行号 |
| m4 | MINOR | mf4090 基线与变体之间还差 buffer、机器、训练副本，并列时要说明 | 第 4 节“只报”加上，注明只有 ml40 的 10 条是同条件对比 |
| m5 | MINOR | 9 条外推要花约 22 小时 | 分成 t2xa（15 条）与 t2xb（9 条）两段，t2xb 起之前先报 t2xa 的结果 |
| n6 | NIT | 第 1 节的来历过时 | 删去，执行记录写实际值 |
| n7 | NIT | 没写冒烟全部先跑、t2x 的磁盘停止阈值 | 第 1、3 节写明（默认 2048 MB） |

## 执行记录

- 10/9 13:20–14:20 事实与输入核对：`results/ops/t2x_inputs_{ml40,mf4090}_1009.txt`（24 条，有问题 0 条）、`results/t2x/baseline_table_1009.txt`；
  计划事实的 jev 第 2 轮 8 / 8 核实（0.71–0.99），3 道对照题正常（`results/decisions/jev_claims_t2x_t3p_plan_1009.txt`；第 1 轮一条说法依赖上一条、
  得 0.06，改写后重跑，第 1 轮留作 `_run1.txt.failed`）。
- 配置展开：48 份配置意外差异 0（`results/t2x/cfgcheck_ml40.txt`，用的是拆段前的 `ml40_t2x*`，52c6b17）；拆段前后正式与冒烟各 24 行逐行相同
  （`results/t2x/split_lines_same.txt`）。
- 第 2 版的代码与测试：两台都在 1d98bd3 上全过（`results/t2x/tests2_{mf4090,ml40}.txt`），含停链与等卡的 8 项（bash 5.1）。
- 14:49 预演 `DRYRUN_OK`（`results/t2x/arm_dryrun_t2xa_ml40.txt`）：15 条 run，来历 1d98bd3，可用 1623613 MB，30 份配置的 precheck 与配方断言全过。
- 14:50 起链 `ARMED`（`results/t2x/arm_t2xa_ml40.txt`）：会话 `v2d-t2xa-train`、`v2d-t2xa-eval`、`v2d-t2xa-export`，来历 1d98bd3
  （当时 HEAD 是 7aa1905，多出的只有 Tier 3 的文件、计划与记录，ml40 用不到）。训练链 14:50 正向核对 15 条通过，开始第一条冒烟（ep29）。
  按冒烟每条几分钟、正式每条 2:10–2:29 估，训练约 10/11 凌晨到早上结束，评测与导出随后。
- 10/10 07:31 进度（`results/t2x/status_ml40_1010_0730.txt`、`results/ops/machines_1010_0730.txt`，服务器日志的 CST 已换成 UTC−6）：
  正式训练按队列顺序完成 7 条，ep29、ep6、ep18、ep7、ep16、ep0、ep21，各 1 段，每条 1:58–2:13，比起链时估的 2:10–2:29 快；
  `fc_run_watched` 记的最新 policy 都是非有限 0，看守日志里含非有限的扫描行 0。ep15 06:54 开始，07:31 时 27%；后面还有 ep10、ep27、ep3、ep5、
  ep11、ep17。按这个速度训练约 10/10 22:00 前后结束，评测与导出再要约 1.5 小时（估计）。停链标记没有建。同组成员 10/9 20:43 起在 ml40 上
  挂了等卡脚本，参数是 ep28、ep27、ep19、ep3 四集（`results/ops/t3_queue_ml40_1010_0735.txt`）。
