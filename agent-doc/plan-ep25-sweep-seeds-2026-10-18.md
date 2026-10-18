# 计划：ep25 的 checkpoint 扫描与 Tier 1 补 seed（10/18 白天两台的卡，第 1 版）

2026-10-18 01:xx MDT，分支 track2/p1-training，基于 commit 32087ee。执行在两台训练机上自动接在 Tier 3 gb3 链后面（约 06:40 MDT 起）。
判据都在结果出来之前登记在这里；结果出来后只按这里的规则判，规则要改就另起一版、写明原因。

## 0. 事实（都有记录）

1. **ep25 的策略学会了把瓶子碰下桌。** ep25（cyan_water_bottle_rotate，859 帧）全部 run 的最终 checkpoint 在 4096 个世界里 MPPE 都在
   114–129 cm：Tier 1 的 cap10m 114.10、cap4m-r3o 129.06、cap10m-r3a-c10 127.10；Tier 2 的 cap4m 117.09、cap4m-r3a-c5 126.57、
   cap10m-r3a 123.93、cap10m-r3o 125.50；Tier 3 的 hm 118.60。ml40 上 Tier 1 cap10m 的第 330M、340M 步也是 116.65、114.85。
   失败原因比例物体、手掌都是 1.0。所以这是学成的行为，不是导出那一局运气差（`results/day2/eval_*ep25*`、`results/ml40/day2/eval_*ep25*`）。
2. **物体一直不动时的数。** Tier 1 对真值 49.71 cm（`results/select_t1/t1_static_floor_c10s43.txt`）；Tier 2 对 Tier 2 自己的轨迹
   49.51 cm（`results/t2diag/t2_static_floor.txt`，净室）。现在交的导出：Tier 1 117.99 cm，Tier 2 115.88 cm（b1014 那份，对自己的参考）。
3. **榜（10/17 20:50 快照，`results/submission/leaderboard_1017_2050.txt`）与要过的线（算术）。**
   - Tier 1 MPPE：Xueyi Wang (FF) 8.03204，DAP 12.65831，maniphys.ai 13.92082（第 3）。以 c10s43 清单（平均 13.827783，ep25 117.9944）为底，
     ep25 的导出 MPPE 要低于 117.9944 − (13.827783 − 12.65831) × 30 = **82.91 cm** 才能排到第 2。以 auc1017 清单（平均 14.905292，
     ep25 是 c10 那条的 131.5553）为底，要低于 131.5553 − (14.905292 − 12.65831) × 30 = **64.15 cm**；这份同时要保住 AUC 超过 FF 的 0.56422，
     ep25 的导出 AUC 要高于约 0.073（auc1017 的 ep25 是 0.1322，余量 (0.566180 − 0.56422) × 30 = 0.0588）。
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
   评测运行时 fc_8c778f9（与现有 4096 世界评测相同），记录 `results/day2/eval_<run>_s<步数>.txt`。附加表 `stages/evaluate/ckpt25_coarse_<机器>.tsv`，
   Tier 2 排前面。mf4090 14 份，ml40 28 份。
2. 细扫：`ckpt_sweep_pick.py refine` 在每条 run 的全部合格评测里取 MPPE 最低的一步，把 checkpoint 序列里紧挨着它的前后各一份（还没评过的）补评。
   每条最多 2 份。
3. 本机选点：`ckpt_sweep_pick.py final` 每档取本机 MPPE 最低的一点，**低于 100 cm** 就用 `export_chain.sh` 导出 1 个世界（核结构、来历与候选条件，
   `V2D_FALLBACK_MAX=0`）。导出只是取数，不等于要换。
4. 合格评测：world_count 4096、non_finite_worlds 空、step_count 859、checkpoint 指向这条 run 的这一步、四项指标都有限。
5. 时间：mf4090 最多 18 份约 1.5 小时，ml40 最多 36 份约 3.1 小时，导出各约 5 分钟。

### 2.3 判据（登记）

- **E1 选点（跨两台）。** 每档在两台的全部合格评测里（含已有的最终 checkpoint）取 4096 世界 MPPE 最低的一点。它不低于 100 cm：这一档判“没用”，不换。
- **E2 Tier 1 换不换。** 用 E1 那一点的导出。导出 MPPE（官方打包器按干净参考逐集算）低于现在的 117.9944，且 4096 世界 MPPE 低于现在交的那条的
  114.10：可以换。换法两份并列给 rxzhou：
  (a) c10s43 清单只换 ep25（只为 MPPE；SP-SR 0.8、MP-SR 0.6667 不变）；
  (b) auc1017 清单把 ep25 换成这一点（AUC 与 MPPE 一起，AUC 要仍高于 0.56422）。
  两份都逐项并列导出世界与 4096 世界的四项。Tier 1 交不交、交哪份由 rxzhou 定。
- **E3 Tier 2 换不换。** 用 E1 那一点的导出。导出 MPPE（对自己的 v5.4 参考，导出 JSON 的 mppe_cm）低于 115.88，且 4096 世界 MPPE 低于 117.09：
  b1014 清单只换 ep25，打包、预演，**按 10/16 的常设授权直接交**，报代理量（自己参考的合计变化）。例外：这一点的步数低于 150M（训练不到一半，
  策略可能还没学会走到桌边，换它等于拿“没碰到瓶子”换分），先问 rxzhou 再交。
- **E4 没用的情形。** 两档都在 E1 判“没用”：ep25 不再投入，记录收尾。
- 只报不判：每个评测点的 AUC、SP-SR、MP-SR；胜出那一步的失败原因比例。

## 3. 乙：Tier 1 补 seed

| 机器 | 段 | run | 配方 | 下一个 seed 的闸 |
|---|---|---|---|---|
| mf4090 | t1xb_s44 | t1-ep14-w2048-cap4m-r3a-s44-mf4090 | 与 s43 相同（r3a、400 万 buffer），只换种子 | t1xb_s45：`seed_gate.py <s44> 14 maniptrans_sr 0.3` |
| ml40 | t1c_s44 | t1-ep11-w2048-cap10m-r3a-c10-s44-ml40 | 与 s43 相同（c10 参考、1000 万 buffer），只换种子 | t1c_s45：`seed_gate.py <s44> 11 spider_sr_uncentered 0.4` |

- 队列由 `make_var_queue.py <段> --episodes <N> --seed <N>` 生成（记录 `results/jia/make_queue_*.txt`），与 s43 的行只差 run 名与种子两项。
- **S1 闸（登记）。** 上一个 seed 的导出那一局这一项已经成功，或 4096 世界这一项低于下限（ep14 MP-SR 0.3，沿用 10/14 计划第 4 节的停手线；
  ep11 SP-SR 0.4），或读不到合格的评测与导出：不训下一个 seed。其余训。
- **S2 选择。** 新候选按登记的 Tier 1 规则（select_t1：导出的 MP-SR → SP-SR → AUC / 0.3780 − MPPE / 25.1706）进下一次选集；
  4096 世界的值并列报。Tier 1 交不交由 rxzhou 定。

## 4. 起法与时间表

两台各挂两个 `arm_after.sh`（`runs/tools/` 里的副本，md5 07173c9b1013，与仓库相同），setsid 后台，日志 `runs/logs/arm_after_<段>_<机器>.log`：

| 机器 | 等哪一段 | 前置命令（`V2D_PRE_CMD`） | 起哪一段 | 估计 |
|---|---|---|---|---|
| mf4090 | t3pg（4 条，独立模式） | 扫描 `ckpt25_mf4090`，限时 4 小时 | t1xb_s44 | 扫描 06:40–08:15，训练到约 10:35，评测导出到约 10:50 |
| mf4090 | t1xb_s44（1 条） | ep14 的闸 | t1xb_s45 | 过闸的话约 10:50–13:25 |
| ml40 | t3qg（4 条，独立模式） | 扫描 `ckpt25_ml40`，限时 6 小时 | t1c_s44 | 扫描 06:40–09:50，训练到约 12:10，评测导出到约 12:25 |
| ml40 | t1c_s44（1 条） | ep11 的闸 | t1c_s45 | 过闸的话约 12:25–15:00 |

- 扫描链参数对就总是退出码 0（评测、选点、导出失败只记日志），不挡后面的训练段；扫描超时或参数错，arm_after 停、训练段不起，早上手动处理。
- 第二个 arm_after 用非独立模式：s44 要训练、评测、导出全部做完才看闸。等待上限设 24 小时。
- 新脚本在链跑着时不能同步，按 md5 单文件拷到两台（同 gb3 那次）；记录头里有每个脚本的 md5，可以对回本地提交。
- 早上 gb3 的读数要卡做 Tier 3 的事：在第二个 arm_after 起训练之前停掉它（自己的进程）即可，不碰别人的进程。

## 5. 验证

- `stages/evaluate/test_ckpt_sweep_pick.py`：合格评测的定义（非有限世界、帧数、世界数、别的 run 的 checkpoint 都不算）、细扫取前后各一份、
  每档最低且严格低于上限才导出、平手取步数大的、表格不对退出码 2、seed 闸的五种情形、整条扫描链用假的评测链与导出链走一遍
  （先后顺序、导出参数 `V2D_FALLBACK_MAX=0`、长链标记清掉、重复起与缺 policy 都拒绝）。mf4090、ml40 上都过（`results/ckpt_sweep/tests_*.txt`）。
- 两台的扫描预演（`V2D_SWEEP_DRYRUN=1`）都打印 CKPT_SWEEP_DRYRUN_OK：粗扫要用的 checkpoint 都在、run 都有 DONE、fc_8c778f9 副本核得过。
- arm_after 起之前各跑一次 `V2D_ARM_DRYRUN=1 arm_var_chain.sh` 不行（卡被 gb3 占着会拒绝），改为核队列文件齐全、md5 与本地相同；起链时 arm_after 自己会预演。

## 6. 风险

- 扫描找到的最低点可能是训练早期、机器人还没学会走过去的 checkpoint（瓶子没被碰到）。E3 的 150M 例外就是为这个；Tier 1 本来就要 rxzhou 定。
- 7 点粗扫加前后各一份的细扫可能错过两个粗扫点之间很窄的低谷；这次只找“明显更好”的一步，不追求全局最低。
- Tier 2 的代理量是对自己 v5.4 参考的，真值的变化要交了才知道；“不动”时自己参考与真值只差 0.2 cm（49.51 对 49.71），量级可信。
- ml40 扫描 3 小时以上，比 mf4090 长；ep11 的结果因此晚到下午。
