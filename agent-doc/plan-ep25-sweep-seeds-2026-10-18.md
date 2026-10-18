# 计划：ep25 的 checkpoint 扫描与 Tier 1 补 seed（10/18 白天两台的卡，第 2 版）

2026-10-17 23:4x MDT 写定（服务器日志是北京时间，+14 小时），分支 track2/p1-training。第 1 版 bcd3330；第 2 版按独立复核（GO WITH FIXES）改，改了什么见文末“复核”。执行在两台训练机上自动接在 Tier 3 gb3 链后面（约 06:40 MDT 起）。
判据都在结果出来之前登记在这里；结果出来后只按这里的规则判，规则要改就另起一版、写明原因。

## 0. 事实（都有记录）

1. **ep25 的策略学会了把瓶子碰下桌。** ep25（cyan_water_bottle_rotate，859 帧）全部 run 的最终 checkpoint 在 4096 个世界里 MPPE 都在
   114–129 cm：Tier 1 的 cap10m 114.10、cap4m-r3o 129.06、cap10m-r3a-c10 127.10；Tier 2 的 cap4m 117.09、cap4m-r3a-c5 126.57、
   cap10m-r3a 123.93、cap10m-r3o 125.50；Tier 3 的 hm 118.60。ml40 上 Tier 1 cap10m 的第 330M、340M 步也是 116.65、114.85。
   失败原因比例物体、手掌都是 1.0。所以这是学成的行为，不是导出那一局运气差（`results/day2/eval_*ep25*`、`results/ml40/day2/eval_*ep25*`）。
2. **物体一直不动时的数。** Tier 1 对真值 49.71 cm（`results/select_t1/t1_static_floor_c10s43.txt`）；Tier 2 对 Tier 2 自己的轨迹
   49.51 cm（`results/t2diag/t2_static_floor.txt`，净室）。现在交的导出：Tier 1 117.99 cm，Tier 2 115.88 cm（b1014 那份，对自己的参考）。
   两档各算各的，不互相比较：Tier 2 的判断只用 Tier 2 的数。
3. **榜（10/17 20:50 快照 `results/submission/leaderboard_1017_2050.txt`；10/17 23:35 快照 `leaderboard_1017_2335.txt` 里这几个数没变）与要过的线（算术）。**
   - Tier 1 MPPE：Xueyi Wang (FF) 8.03204，DAP 12.65831，maniphys.ai 13.92082（第 3）。以 c10s43 清单（平均 13.827783，ep25 117.9944）为底，
     ep25 的导出 MPPE 要低于 117.9944 − (13.827783 − 12.65831) × 30 = **82.91 cm** 才能排到第 2。以 auc1017 清单（平均 14.905292，
     ep25 是 c10 那条的 131.5553）为底，要低于 131.5553 − (14.905292 − 12.65831) × 30 = **64.15 cm**；这份同时要保住 AUC 超过 FF 的 0.56422，
     ep25 的导出 AUC 要高于约 0.073（auc1017 的 ep25 是 0.1322，余量 (0.566180 − 0.56422) × 30 = 0.0588）。10/17 23:35 的快照里一个新队
     （Vi Nguyễn Văn）在 Tier 1 AUC 交了 0.96908，只出现在这一个榜；所以超过 FF 现在是这个榜的第 2，我们与 FF 的相对名次照旧。
   - Tier 2 MPPE：FF 13.87967，maniphys.ai 15.32195（b1014，`stages/evaluate/exports/t2_select_b1014.tsv`）。真值合计要减
     (15.32195 − 13.87967) × 30 = **43.27 cm** 以上；按自己参考的代理量算，ep25 的导出要低于 115.88 − 43.27 = **72.61 cm**（代理量，不是真值）。
   - Tier 3 MPPE 我们 55.77 领先 FF 的 67.33，ep25 在 Tier 3 上不扫。
4. **导出那 1 局是独立的公平抽样。** mf4090 上 30 对“逐世界 dump + 导出”：导出与评测里第 0 个世界逐位相同的 0 对，导出值在 4096 个世界里的分位
   0.04–0.95 散开（`results/t1diag/export_world0_mf4090.txt`，脚本 `stages/evaluate/export_world0.py`）；75 个 Tier 1 候选上导出成功数与
   4096 世界成功率之和的差 SP z +0.54、MP z +0.67（`results/ml40/select_t1/export_calibration_c10s43.txt`）。
5. **补 seed 的依据。** ep14 的 r3a：4096 世界 MP-SR 0.677（seed 42）、0.565（seed 43），两局导出都失败（MPPE 78.03、84.74 cm）；同一集的
   cap4m 那条导出 SP 1 / MP 0。ep11 的 c10：4096 世界 SP-SR 0.801 / MP-SR 0.127（seed 42）、0.608 / 0.224（seed 43），两局导出都失败。
   Tier 1 榜上 SP-SR FF 0.80000、我们 0.76666；MP-SR 两队都是 0.66666（FF 先交）。c10s43 清单的导出是 SP 24/30、MP 20/30：
   ep14 再成功一局 MP，MP-SR 到 0.7；ep11 再成功一局 SP，SP-SR 到 0.8333，都比 FF 高。
6. **花费。** ep25 一次 4096 世界评测 mf4090 约 4.7 分钟、ml40 约 5.2 分钟（评测日志的时间戳）；每条 run 每 10000384 步存一份 checkpoint，
   共 35 份（t2-ep25-w2048-cap4m-mf4090 只留了 270M 以后的 9 份，不扫）。一条训练约 2.2 小时。
7. **卡。** 两台的 gb3 链（mf4090 t3pg、ml40 t3qg）在训第 2 集，预计 05:50 训完、06:40 评测与导出做完（`agent-doc/handoff-2026-10-17-evening.md`）。

## 1. 范围

做：甲 ep25 的 checkpoint 扫描（Tier 1、Tier 2，只评测与导出，不训练）；乙 Tier 1 ep14、ep11 补 seed。
不做：同一 policy 换种子重导（等 rxzhou 定）；Tier 3 的重训（等 gb3 读数）；Tier 2 的 ep28、ep4；ep25 在 Tier 3 上的扫描。

## 2. 甲：ep25 的 checkpoint 扫描

### 2.1 扫哪几条

| 机器 | Tier 2 | Tier 1 |
|---|---|---|
| mf4090 | t2-ep25-w2048-cap4m-r3a-c5-mf4090 | t1-ep25-w2048-cap4m-r3o-mf4090 |
| ml40 | t2-ep25-w2048-cap10m-r3a-ml40、t2-ep25-w2048-cap10m-r3o-ml40 | t1-ep25-w2048-cap10m-ml40（现在交的）、t1-ep25-w2048-cap10m-r3a-c10-ml40 |

checkpoint 只在本机，不跨机传。

### 2.2 怎么扫（`stages/evaluate/ckpt_sweep.sh`，评测与导出都用现成的链）

1. 粗扫：每条 run 第 3、6、10、15、20、25、30 份 checkpoint（步数 = 份数 × 10000384），`day2_eval_chain.sh` 的附加表 eval 行，4096 世界，
   评测运行时 fc_8c778f9（经 `V2D_FC_SRC` 挂进容器，与提交导出同一份），记录 `results/day2/eval_<run>_s<步数>.txt`。附加表
   `stages/evaluate/ckpt25_coarse_<机器>.tsv`，Tier 2 排前面。mf4090 14 份，ml40 28 份。ml40 上 t1 cap10m 的 330M、340M、350M 三份是 9/30 用镜像
   自带的运行时评的（那时还没有 fc_8c778f9 副本）；它们都在 114 cm 以上，不会被选中，只作参照。
2. 选法（E1 用的同一个）：MPPE 不超过最低值 + 1 cm 的点里取步数最大的，再按 MPPE、run 名。早期 checkpoint 多半碰不到瓶子、都落在“不动”的
   49–50 cm 附近，彼此只差噪声；这时取训练得更久的那一份。
3. 细扫：`ckpt_sweep_pick.py refine` 在每条 run 的全部合格评测里按选法选一步，把 checkpoint 序列里紧挨着它的前后各一份（还没评过的）补评。
   每条最多 2 份。
4. 本机选点：`ckpt_sweep_pick.py final` 每档按选法选本机一点，**严格低于 100 cm** 就用 `export_chain.sh` 导出 1 个世界（核结构、来历与候选条件，
   `V2D_FALLBACK_MAX=0`）。导出只是取数，不等于要换。
5. 只报：导出的每一点再跑一次逐世界 dump（`fc_eval_dump.sh`，4096 世界，约 5 分钟），`dump_knock.py` 报物体平均位置误差超过 0.8 m 的世界比例
   （瓶子被带离很远的概率；不动约 0.45 m，掉到地上约 1.1 m）。
6. 合格评测：world_count 4096、non_finite_worlds 空、step_count 859、checkpoint 指向这条 run 的这一步、四项指标都有限。
7. 时间：mf4090 最多 18 份约 1.5 小时，ml40 最多 36 份约 3.1 小时，导出与 dump 各约 10 分钟。

### 2.3 判据（登记）

- **E1 选点（跨两台）。** 每档把两台的选点记录（`results/ckpt_sweep/ckpt25_<机器>_pick.txt` 里的全部合格评测点，含已有的最终 checkpoint）合在一起，
  按 2.2 第 2 条的选法选一点。它不严格低于 100 cm：这一档判“没用”，不换。
- **E2 Tier 1 换不换。** 用 E1 那一点的导出。导出 MPPE（官方打包器按干净参考逐集算）低于现在的 117.9944，且 4096 世界 MPPE 低于现在交的那条的
  114.10：可以换。换法两份并列给 rxzhou：
  (a) c10s43 清单只换 ep25（只为 MPPE；SP-SR 0.8、MP-SR 0.6667 不变）；
  (b) auc1017 清单把 ep25 换成这一点（AUC 与 MPPE 一起，AUC 要仍高于 0.56422）。
  两份都逐项并列导出世界与 4096 世界的四项。Tier 1 交不交、交哪份由 rxzhou 定。
- **E3 Tier 2 换不换。** 用 E1 那一点的导出。导出 MPPE（对自己的 v5.4 参考，导出 JSON 的 mppe_cm）低于 115.88，且 4096 世界 MPPE 低于 117.09：
  b1014 清单只换 ep25，打包、预演，**按 10/16 的常设授权直接交**，报代理量（自己参考的合计变化）。例外：这一点的步数 ≤ 150005760（第 15 份，
  训练不到一半，策略可能还没学会走到桌边，换它等于拿“没碰到瓶子”换分），先问 rxzhou 再交。
- **E4 没用的情形。** 两档都在 E1 判“没用”：ep25 不再投入，记录收尾。
- 只报不判：每个评测点的 AUC、SP-SR、MP-SR；胜出那一步的失败原因比例与 2.2 第 5 条的“带离很远”的世界比例。

## 3. 乙：Tier 1 补 seed

| 机器 | 段 | run | 配方 | 下一个 seed 的闸 |
|---|---|---|---|---|
| mf4090 | t1xb_s44 | t1-ep14-w2048-cap4m-r3a-s44-mf4090 | 与 s43 相同（r3a、400 万 buffer），只换种子 | t1xb_s45：`seed_gate.py <s44> 14 maniptrans_sr 0.3` |
| ml40 | t1c_s44 | t1-ep11-w2048-cap10m-r3a-c10-s44-ml40 | 与 s43 相同（c10 参考、1000 万 buffer），只换种子 | t1c_s45：`seed_gate.py <s44> 11 spider_sr_uncentered 0.4` |

- 队列由 `make_var_queue.py <段> --episodes <N> --seed <N>` 生成（记录 `results/jia/make_queue_*.txt`），与 s43 的行只差 run 名与种子两项。
- **S1 闸（登记）。** 上一个 seed 的导出那一局这一项已经成功，或 4096 世界这一项低于下限（ep14 MP-SR 0.3，沿用 10/14 计划第 4 节的停手线；
  ep11 SP-SR 0.4），或读不到合格的评测与导出：不训下一个 seed。其余训。
- 闸没过时 arm_after 日志最后一行是 `ARM_AFTER_STOPPED 前置命令没过（退出码 1）`，这是预期的结局，不是故障。
- **S2 选择。** 新候选按登记的 Tier 1 规则（select_t1：导出的 MP-SR → SP-SR → AUC / 0.3780 − MPPE / 25.1706）进下一次选集；
  4096 世界的值并列报。Tier 1 交不交由 rxzhou 定。

## 4. 起法与时间表

两台各挂两个 `arm_after.sh`（`runs/tools/` 里的副本，md5 07173c9b1013，与仓库相同），setsid 后台，日志 `runs/logs/arm_after_<段>_<机器>.log`。
命令原样如下（仓库根执行；`env -u` 去掉两个预演开关，免得起链的 shell 里带着它们，把扫描或起链变成什么都不做）：

```bash
# mf4090，第一个：等 t3pg 链结束、卡空 → 扫描（限时 8 小时）→ 起 t1xb_s44
env -u V2D_SWEEP_DRYRUN -u V2D_ARM_DRYRUN V2D_AFTER_INDEPENDENT=1 V2D_POLL_S=60 V2D_AFTER_MAX_POLLS=720 V2D_PRE_TIMEOUT_S=28800 \
  V2D_PRE_CMD='V2D_FC_SRC=$HOME/v2d/fc_src/fc_8c778f9 stages/evaluate/ckpt_sweep.sh ckpt25_mf4090 stages/evaluate/ckpt25_coarse_mf4090.tsv 100' \
  setsid nohup bash runs/tools/arm_after.sh t1xb_s44 runs/logs/t3pg_train_mf4090.log runs/logs/t3pg_eval_mf4090.log runs/logs/cand_t3_t3pg_mf4090.log 4 \
  > runs/logs/arm_after_t1xb_s44_mf4090.log 2>&1 < /dev/null &
# mf4090，第二个：等 t1xb_s44 训练、评测、导出全部做完 → ep14 的闸 → 起 t1xb_s45
env -u V2D_SWEEP_DRYRUN -u V2D_ARM_DRYRUN V2D_POLL_S=60 V2D_AFTER_MAX_POLLS=1440 \
  V2D_PRE_CMD='python3 stages/evaluate/seed_gate.py t1-ep14-w2048-cap4m-r3a-s44-mf4090 14 maniptrans_sr 0.3' \
  setsid nohup bash runs/tools/arm_after.sh t1xb_s45 runs/logs/t1xb_s44_train_mf4090.log runs/logs/t1xb_s44_eval_mf4090.log runs/logs/cand_t1_t1xb_s44_mf4090.log 1 \
  > runs/logs/arm_after_t1xb_s45_mf4090.log 2>&1 < /dev/null &
# ml40，第一个：等 t3qg 链结束、卡空 → 扫描（限时 10 小时）→ 起 t1c_s44
env -u V2D_SWEEP_DRYRUN -u V2D_ARM_DRYRUN V2D_AFTER_INDEPENDENT=1 V2D_POLL_S=60 V2D_AFTER_MAX_POLLS=720 V2D_PRE_TIMEOUT_S=36000 \
  V2D_PRE_CMD='V2D_FC_SRC=/lab_data/rxzhou/v2d/fc_src/fc_8c778f9 stages/evaluate/ckpt_sweep.sh ckpt25_ml40 stages/evaluate/ckpt25_coarse_ml40.tsv 100' \
  setsid nohup bash runs/tools/arm_after.sh t1c_s44 runs/logs/t3qg_train_ml40.log runs/logs/t3qg_eval_ml40.log runs/logs/cand_t3_t3qg_ml40.log 4 \
  > runs/logs/arm_after_t1c_s44_ml40.log 2>&1 < /dev/null &
# ml40，第二个：等 t1c_s44 全部做完 → ep11 的闸 → 起 t1c_s45
env -u V2D_SWEEP_DRYRUN -u V2D_ARM_DRYRUN V2D_POLL_S=60 V2D_AFTER_MAX_POLLS=1440 \
  V2D_PRE_CMD='python3 stages/evaluate/seed_gate.py t1-ep11-w2048-cap10m-r3a-c10-s44-ml40 11 spider_sr_uncentered 0.4' \
  setsid nohup bash runs/tools/arm_after.sh t1c_s45 runs/logs/t1c_s44_train_ml40.log runs/logs/t1c_s44_eval_ml40.log runs/logs/cand_t1_t1c_s44_ml40.log 1 \
  > runs/logs/arm_after_t1c_s45_ml40.log 2>&1 < /dev/null &
```

这些命令写在 `stages/evaluate/arm_ckpt25.sh <机器>` 里（`V2D_ARM25_DRYRUN=1` 只核、只打印）。起之前：用同一串前置命令加 `V2D_SWEEP_DRYRUN=1` 预演（`scripts/dev/record ckpt_sweep/dryrun_<机器> env V2D_SWEEP_DRYRUN=1 bash -c '<前置命令>'`，
要 CKPT_SWEEP_DRYRUN_OK）；两个闸现在各跑一次，s44 还不存在，应当 `SEED_GATE FAIL 读不到…`（核命令写对了）。起完核四份日志的第一行与进程。

| 机器 | 估计 |
|---|---|
| mf4090 | 扫描 06:40–08:20，t1xb_s44 训练到约 10:40、评测导出到约 10:55；过闸的话 t1xb_s45 约 11:00–13:30 |
| ml40 | 扫描 06:40–10:00，t1c_s44 训练到约 12:20、评测导出到约 12:35；过闸的话 t1c_s45 约 12:40–15:10 |

- 限时：每条链等卡最多 2 小时（`V2D_GPU_WAIT_S` 默认 7200），三条链都等满再加扫描本身，mf4090 约 7.6 小时、ml40 约 9.2 小时，所以限时设 8、10 小时。
  超时（退出码 124）时 arm_after 停、训练段不起；`timeout` 发的 SIGTERM 会触发扫描脚本的 EXIT trap 清掉自己的长链标记，日内照看时仍手动
  `ls runs/.chain-active-ckpt25_*` 核一次。
- 扫描链参数对就总是退出码 0（评测、选点、导出、dump 失败只记日志），不挡后面的训练段。
- 第二个 arm_after 用非独立模式：s44 要训练、评测、导出全部做完才看闸；它的等待条件要 s44 的训练日志存在且写完，s44 起之前不会误触发。等待上限 24 小时。
- 新脚本在链跑着时不能同步：已提交的文件用 `push-new-files` 放（第 1 版先 scp 上去的几份用 `V2D_PUSH_REPLACE_FROM=bcd3330` 换成第 2 版），
  记录头里有每个脚本的 md5，可以对回本地提交。
- 早上 gb3 的读数要卡做 Tier 3 的事：在第二个 arm_after 起训练之前停掉它（自己的进程）即可，不碰别人的进程。
- 日内照看：约 07:30 与 10:30 MDT 各看一次两台的 arm_after 与扫描日志。

## 5. 验证

- `stages/evaluate/test_ckpt_sweep_pick.py`：合格评测的定义（非有限世界、帧数、世界数、别的 run 的 checkpoint 都不算）、细扫取前后各一份、
  每档最低且严格低于上限才导出、平手取步数大的、表格不对退出码 2、seed 闸的五种情形、整条扫描链用假的评测链与导出链走一遍
  （先后顺序、导出参数 `V2D_FALLBACK_MAX=0`、长链标记清掉、重复起与缺 policy 都拒绝）。mf4090、ml40 上都过（`results/ckpt_sweep/tests_*.txt`）。
- 两台的扫描预演（`V2D_SWEEP_DRYRUN=1`，第 4 节的原样前置命令）都打印 CKPT_SWEEP_DRYRUN_OK：粗扫要用的 checkpoint 都在、run 都有 DONE、
  fc_8c778f9 副本核得过。
- 四个新段的队列：`fc_config_check.sh`（冒烟与正式，意外差异 0）与 `precheck_expect.sh`（PRECHECK_OK）在两台都过，记录
  `results/ckpt_sweep/{cfgcheck,precheck}_*`（ml40 的在 `results/ml40/ckpt_sweep/`）；`arm_var_chain.sh` 要的 `runs/cfgcheck/<run>.yaml`
  （冒烟与正式各一份）逐个核在不在。
- `V2D_ARM_DRYRUN=1 arm_var_chain.sh` 现在跑不了（卡被 gb3 占着会拒绝），留给 arm_after 在卡空之后自己预演。

## 6. 风险

- 扫描找到的最低点可能是训练早期、机器人还没学会走过去的 checkpoint（瓶子没被碰到）。E3 的 150M 例外就是为这个；Tier 1 本来就要 rxzhou 定。
- 7 点粗扫加前后各一份的细扫可能错过两个粗扫点之间很窄的低谷；这次只找“明显更好”的一步，不追求全局最低。
- Tier 2 的代理量是对自己 v5.4 参考的，真值的变化要交了才知道。
- ml40 扫描 3 小时以上，比 mf4090 长；ep11 的结果因此晚到下午。

## 复核

第 1 版（bcd3330）交 Fable 5.1 独立复核：**GO WITH FIXES**。核过没问题的：扫描链对两条现成链的调用、日志与标记名、`V2D_FC_SRC` 的传递、
导出只会是选中那一步（`V2D_FALLBACK_MAX=0` 加候选条件的 sha256 比对）、出错与超时都会清掉标记；第二个 arm_after 不会提前起；第 0 节的算术
（82.91、64.15、0.0588/0.073、43.27/72.61）与各条评测记录；导出是公平抽样（30 个分位的 KS D ≈ 0.15，n = 30 的临界值 0.24）；从约 44 个 4096 世界
均值里取最小的选择偏差约 2.2 倍标准误、不到 1 cm，比这里要的十几厘米小得多。按意见改的：
1. （major）第 4 节写出四条原样的起链命令，起之前用同一串前置命令预演，`env -u` 去掉预演开关。
2. （major）补拉两台的配置核对与预检记录，逐个核 `runs/cfgcheck/<run>.yaml`。
3. （minor）前置命令限时从 4、6 小时改为 8、10 小时（三条链各等卡 2 小时的最坏情形）；加日内照看时间。
4. （minor）选法改为“最低值 + 1 cm 内取步数最大”（早期 checkpoint 之间只差噪声），E3 的例外写成“步数 ≤ 150005760”，导出的点加逐世界 dump，
   报瓶子被带离很远的世界比例。
5. （minor）删掉第 6 节拿 Tier 1 真值印证 Tier 2 代理量的那句；第 0 节注明两档各算各的。
6. （nit）第 0 节补新队的 Tier 1 AUC 0.96908；第 3 节注明闸没过时 arm_after 的结局是预期的；第 2.2 节注明 9/30 那三份评测的运行时不同；
   交接里写明 ep25 的导出用 `pull_submission.sh select` 拉进新目录（`exports` 子命令遇到已有的 episode_000025 会拒绝）。

## 执行记录

- 10/17 23:55（mf4090）、23:56 MDT（ml40）：`arm_ckpt25.sh` 起完核过（ARMED_2），每台两个 arm_after 在等（`results/ckpt_sweep/arm_launch_{mf4090,ml40}.txt`）。
  起之前：第 2 版测试两台都过（`tests_v2_*`）；原样前置命令的扫描预演 CKPT_SWEEP_DRYRUN_OK（`dryrun_*`）；两个闸现在跑是 `SEED_GATE FAIL 读不到…`（预期）；
  四个新段冒烟与正式共 8 份 `runs/cfgcheck/<run>.yaml` 都在；配置核对意外差异 0、预检 PRECHECK_OK（`cfgcheck_*`、`precheck_*`）。ml40 的记录在 `results/ml40/ckpt_sweep/`。
- 现在交的两条 ep25 的逐世界 dump（`dump_knock.py`，只读已有文件）：Tier 2 t2-ep25-w2048-cap4m-mf4090 物体平均位置误差超过 0.8 m 的世界 0.9990
  （中位 1.151 m）；Tier 1 t1-ep25-w2048-cap10m-ml40 0.9998（中位 1.119 m）。碰掉瓶子几乎发生在每个世界（`knock_check_*`）。
- 时间更正：10/17 晚上的榜单快照实际在 23:35 MDT 拍（Mac 时钟是 EDT），原名 `leaderboard_1018_0215.txt` 改为 `leaderboard_1017_2335.txt`，名次和按新名字重算，数不变。
- 10/18 07:02（mf4090）、08:28 MDT（ml40）：两台的扫描做完，粗扫与细扫评测全部成功（mf4090 18 份、ml40 28 份粗扫加细扫，`runs/logs/ckpt25_<机器>_{c,r}.log`），
  两台都没有低于 100 cm 的点、导出清单 0 行；arm_after 随后起了 t1xb_s44（07:02）与 t1c_s44（08:28）。
- E1（跨两台合并，`results/ckpt_sweep/ckpt25_mf4090_pick.txt`、`results/ml40/ckpt_sweep/ckpt25_ml40_pick.txt`）：Tier 1 最低 103.13 cm（mf4090 r3o 第 50001920 步），
  1 cm 内取步数最大选到第 60002304 步 103.68 cm；Tier 2 最低 105.16 cm（ml40 r3o 第 260009984 步），1 cm 内只有它。两档都不低于 100 cm，按 E4 判“没用”：
  ep25 不再在现有 checkpoint 里找。从第 20000768 步到最终，评过的每一份都在 103 cm 以上，说明训练早期的策略就会碰到瓶子；要改善 ep25 得另找原因、另写计划。
