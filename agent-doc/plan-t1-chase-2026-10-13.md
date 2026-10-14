# 计划：Tier 1 追 CHORD 基线（2026-10-13，第 2 版）

用户 10/13 看过榜单后：“我们至少要超越 CHORD 基线 然后尝试超越 Xueyi Wang (FF)”；21:46 前后决定 Tier 3 剩下的训练停，空出来的卡先给 Tier 1 追基线
（Tier 3 的经过见 `agent-doc/plan-d-t3hm-train-2026-10-12.md` 执行记录）。本计划排两台 GPU 接下来约 12 小时训什么、怎么判、怎么选。
不提交：新 CSV 打好后交不交由用户定。时间一律 UTC-6。

第 1 版经 Fable 5.1 审查（GO WITH FIXES，7 MINOR、4 NIT），处理见文末“审查与处理”，正文已按处理改过。
jev：第 1 版的 10 条核实（0.72–0.99），对照 4 条正常（`results/t1x/jev_claims_t1_chase.txt`）；第 2 版新加的 4 条核实（0.96–0.98），
对照 3 条正常（`results/t1x/jev_claims_t1_chase_v2.txt`）。

## 1. 事实

**差距**（榜单 10/13 18:00，`results/submission/leaderboard_1013_1800.txt`；逐项换算 `results/t1gap/t1_gap_1013.txt`）

- 第一次真实提交的四项与打包时本地复算相差都小于 1e-5（`agent-doc/plan-next-training-2026-10-12.md` 执行记录），Track 2 没有私榜，
  所以本地逐条选的结果就是榜上分数。
- 与 CHORD 基线比：SP-SR 18 条对 21 条，要多成功 4 条才超过（多 3 条打平）；30 条的 AUC 总和要加 1.173；MPPE 总和要减 204.0 cm；
  MP-SR 16 条对 6 条，已经超过。
- 与 Xueyi Wang (FF) 比：SP-SR 同样要多 4 条；MP-SR 16 条对 20 条，要多 5 条；AUC 总和要加 2.788；MPPE 总和要减 489.5 cm。
- 1 世界 SP-SR 失败的 12 条：ep1、2、3、4、9、11、13、16、17、19、25、28（`results/ml40/select_t1/select_t1x1013.txt` 的 CHOSEN 行）。
  MPPE 超过 15 cm 的 9 条（ep25、2、3、4、28、16、11、9、1）合计 669.5 cm，占 30 条总和的 91.0%。
- 能不能超过基线，卡在 SP-SR：上面 12 条里至少要有 4 条变成功。AUC 与 MPPE 要靠 MPPE 大的集一起补，这次能训到的 5 条怎么才够见第 2 节的粗估。

**指标的口径**（kit `third_party/v2d_submission_kit/update_0f2f9f4b/v2d_submission_kit/v2dlb/object_pose.py` 第 26–29、166–191 行，
`metric_code/track_2/SP-SR.py` 第 20–21 行，`metric_code/track_2/MP-SR.py` 第 22–23 行；FlashCHORD 8c778f9 的 `evaluation/metrics.py` 第 21–24 行同值）

- SP-SR、MP-SR 只看物体位姿：每个世界先把物体的位置误差与朝向误差（四元数测地角）按帧平均，再和门限比；不看手、手指、骨盆。
- SP-SR：平均位置误差 ≤ 0.10 m，且平均朝向误差 ≤ 0.5 rad（28.65°）。MP-SR：平均位置误差 < 0.03 m，且平均朝向误差 < 30°。
- Tier 1 每条 episode 只评 1 个世界（kit `config/tracks.json` 第 125 行），所以每条非 0 即 1，榜上是 30 条的平均。
- 训练时物体朝向的终止阈值：官方配方 1.5 rad，变体 A 0.6 rad（`stages/policy/arm_trial_chains.sh` 第 50–51 行），都比 SP-SR 的 0.5 rad 松。
- MPPE 小、SP-SR 却失败的 3 条（1 世界导出，`results/ml40/submission/exports/export_ml40_t1-ep<N>-w2048-cap10m-ml40_s349999104.txt` 第 20–21 行）：
  ep13 位置 4.06 cm、朝向 38.20°；ep17 4.04 cm、39.33°；ep19 10.50 cm、47.22°。ep13、ep17 只差朝向，ep19 两项都超。
  MPPE 的关键点离物体原点 5 cm（`object_pose.py` 第 36 行），转 38–47° 每个关键点最多只移约 3.3–4.0 cm，所以 MPPE 不到 12 cm 也可能过不了
  SP-SR 的朝向门限（读代码的推断）。变体 A 把朝向终止阈值从 1.5 rad 收到 0.6 rad，Tier 2 上 ep13、ep19 的 SP-SR 从 0 升到 0.615、0.634，
  与这个机制一致，没有单独验证。
- 现在的候选在 4096 世界上的 SP-SR：ep3 0.0002、ep13 0.0007、ep16 0.0002、ep19 0、ep2 0.0166（`results/day2/`、`results/ml40/day2/` 的
  `eval_<run>_s349999104.txt` 第 14 行）。这几条靠现有的 run 再导出一次也几乎不可能成功，要换配方。

**不动基线**（物体一直不动时的 ADD-AUC，`results/day2/bar_smoke-*.txt`、`results/ml40/day2/bar_smoke-*.txt`；这些记录只有 AUC，
没有 SP-SR、MP-SR、MPPE）：14 条里有 8 条现在交的轨迹 AUC 低于不动基线，差得最多的是 ep3（0.119 对 0.539）、ep10（0.234 对 0.339）、
ep25（0.074 对 0.138）；ep2、11、28、1、16 各低 0.01–0.02。也就是说，这些集里策略把物体弄得比不碰还偏。这次只记下这个现象，
不据此改任何东西；要不要专门处理待定。

**变体 A 在 Tier 2 上的逐集结果**（`results/t2x/eval_table_t2xa.txt`、`results/t2x/eval_table_t2xb.txt`；4096 世界，对照 v5.4 参考，
不是干净真值，只看方向）。下表是 Tier 1 上 MP-SR 没成功的 14 条：

| ep | Tier 1 现在（1 世界 SP / MP，MPPE cm） | Tier 2 变体 A 1000 万 SP-SR / MP-SR | Tier 1 变体 A 的安排 |
|---|---|---|---|
| 16 | 0 / 0，63.20 | 0.939 / 0.938 | 10/12 计划 C 有，没起 |
| 3 | 0 / 0，94.52 | 0.854 / 0.806 | t1xb（400 万） |
| 19 | 0 / 0，11.08 | 0.634 / 0.000 | t1xb（400 万） |
| 13 | 0 / 0，4.78 | 0.615 / 0.130 | t1xb（400 万） |
| 2 | 0 / 0，99.98 | 0.422 / 0.011 | 10/12 计划 C 有，没起 |
| 14 | 1 / 0，5.89 | 0.948 / 0.000 | t1xb（400 万） |
| 10 | 1 / 0，4.53 | 0.974 / 0.963 | t1xb（400 万） |
| 17 | 0 / 0，4.98 | 0.000 / 0.000 | 10/12 已训，4096 世界 MP-SR 0 |
| 1、4、9、11、25、28 | 0 / 0，37.68–117.99 | 0.000 / 0.000 | 没有 |

- 12 条 SP-SR 失败的集里，Tier 2 变体 A 的 SP-SR 不低于 0.4 的只有 5 条：ep16、3、19、13、2。其余 7 条（ep1、4、9、11、17、25、28）
  在 Tier 2 上都是 0，骨盆失败比例 1.000（ep17 的 Tier 1 变体 A 也是 0）。
- 10/12 计划 C 的停手规则只看 t2xb 的 9 条（ep9、1、13、19、2、4、14、25、28），没有一条 MP-SR 不低于 0.5，所以 C 没起
  （`agent-doc/plan-next-training-2026-10-12.md` 执行记录 10/13 07:09）。C 里的 ep16 在 t2xa 里，不在这 9 条中；它在 Tier 2 上 MP-SR 0.938。

**Tier 1 变体 A 与 Tier 2 变体 A 的对照**（Tier 1：`results/day2/eval_t1-ep<N>-w2048-cap4m-r3a-mf4090_s349999104.txt`，400 万 buffer；
Tier 2：`results/t2x/eval_table_t2xa.txt`，1000 万 buffer；都是 4096 世界 MP-SR）

| ep | 0 | 6 | 15 | 27 | 21 | 18 | 5 | 29 | 17 |
|---|---|---|---|---|---|---|---|---|---|
| Tier 1（seed 42） | 0.983 | 0.979 | 0.957 | 0.935 | 0.806 | 0.776 | 0.308 | 0.151 | 0.000 |
| Tier 2 | 0.986 | 0.991 | 0.987 | 0.987 | 0.965 | 0.995 | 0.956 | 0.898 | 0.000 |

- 方向一致：Tier 2 是 0 的 ep17，Tier 1 也是 0；Tier 2 高的 8 条，Tier 1 都高于 0.15。
- Tier 1 的 400 万版普遍低一些：9 条里 4 条低 0.15 以上（ep18、21、5、29）。差在 buffer、参考还是机器，没有拆开过。
- 种子：名字只差 `-s43-` 的 24 对 run（Tier 1、Tier 2，`results/day2/`、`results/ml40/day2/`）里，7 对的 4096 世界 MP-SR 变了 0.10 以上。
  变体 A 的 13 对（Tier 1 8 对、Tier 2 5 对）里只有 2 对变了 0.10 以上：Tier 1 ep29 0.151 → 0.499、ep20 0.794 → 0.918；
  官方配方的 11 对里有 5 对，例如 Tier 1 ep6 0.562 → 0.000、ep18 0.152 → 0.714、ep27 0.321 → 0.001。上表的 14 条都没有种子对。

**机器**（`results/t3p4/stop_t3p4b_mf4090.txt`、`results/t3q/stop_t3qa_ml40.txt`、`results/ops/mf4090_disk_1013_2150.txt`）

- mf4090：t3p4b 的最后一条 ep27 20:56 开训，22:04 时写了 18/35 份 policy，约 23:10 训完；之后评测 8 条、导出，约 00:05 空出来（估计）。
  仓库所在分区 21:54 可用 91,101,152 KiB（约 87 GiB）。
- ml40：t3qa 21:53 停链（完成 5 条），评测与导出约 22:35 结束（估计）。`/lab_data` 22:01 可用 1,415,914,908 KiB（约 1.32 TiB）。
- 速度：mf4090 每条约 2.2 小时；ml40（1000 万 buffer）的 t3qa ep7 用了 1 小时 58 分。冒烟每条另加约 10 分钟。

## 2. 排期

| 段 | 机器 | 内容 | 条数 | 时长（估计） | 状态 |
|---|---|---|---|---|---|
| t1xb | mf4090 | 10/12 计划 A 没开的 5 条换个顺序：ep3、19、13、10、14，变体 A seed 42，400 万 buffer | 5 | 约 11 小时 | 计划 A 已登记这 5 条；顺序是本计划改的，冒烟都已 DONE |
| t1yb | ml40 | 新：ep16、2、3、19、13，变体 A seed 42，1000 万 buffer | 5 | 约 11–12 小时 | 本计划 |

**t1xb 取代 t1xa3**（审查第 6 条）：计划 A 的顺序（ep10、13、19、3、14）是按骨盆比例排的，ep10、ep14 的 SP-SR 已经是 1。
现在挡着超过基线的是 SP-SR，Tier 3 重新开训时这一段可能被停链截断，所以把 SP-SR 失败的 ep3、19、13 排前面，ep10（Tier 2 MP-SR 0.963）在 ep14 前。
run 名、期望表行与 t1xa 的逐字相同，只换顺序与段名（`make_var_queue.py` 按清单的顺序出队，换顺序要一份新清单 `t1xb`）。
已提交的 t1xa3 四份文件删掉，免得误起。

**t1yb 取代 10/12 计划 C 的停手规则**（审查第 5 条）：C 的门（t2xb 9 条里 4096 世界 MP-SR ≥ 0.5 的有没有）是按 MP-SR 登记的，
现在的目标是 SP-SR，所以重新登记判据：Tier 2 变体 A 的 4096 世界 SP-SR ≥ 0.4。C 里的 ep16、ep2 按新判据进 t1yb；
C 的其余 4 条（ep11、4、9、25）在 Tier 2 上都是 0，照旧不起，t1ya 不起。

**t1yb 为什么是这 5 条、这个顺序**

1. 只有 SP-SR 挡着超过基线；AUC 与 MPPE 跟着 MPPE 大的集一起补（第 1 节）。
2. 选 Tier 2 先验不低于 0.4 的 5 条。其余 7 条在 Tier 2 上变体 A 没有任何信号，这次不训。
3. ep16、ep2 不在 t1xb 里，只能在 ml40 上训。ep3、19、13 在 t1xb 里是 400 万 buffer，Tier 2 上成功的是 1000 万 buffer；两台各训一版，
   逐条选时取好的，每条多一次机会。两版的 buffer 与机器都不同，不是独立重复，不能把成功概率按独立事件算。
4. 顺序：只有这里训的两条在前，ep16（先验最高）→ ep2（MPPE 99.98 cm）；之后是 mf4090 上也训的三条，按 MPPE 从大到小 ep3 → ep19 → ep13。

**粗估**（都是量级估计，不是测出来的）

- SP-SR：把 Tier 2 的 4096 世界 SP-SR 当成 Tier 1 一条 1 世界导出成功的概率（Tier 1 的 400 万版历来偏低，所以偏乐观）：
  ep16 0.94、ep3 0.85、ep19 0.63、ep13 0.62、ep2 0.42，只算一版的期望约 3.5 条；两版的机会会高一些，但不独立，算不准。
  多成功 4 条才超过基线、3 条打平。
- AUC 与 MPPE：按 `t1_gap.py` 的“像成功的”假设（修好的集取现在成功集的中位 AUC 0.715、MPPE 2.14 cm），只看这 5 条：
  MPPE 总和要减 204.0 cm，ep16、3、2 三条都要成（少了其中任何一条，其余几条加起来最多减 201.8 cm）；
  AUC 总和要加 1.173，要有 3 条以上成，或恰好是 ep3 与 ep2 两条（两条加 1.197，别的两条组合最多加 1.080）。
  t1xb 里的 ep10、ep14 若也成，还能各补 MPPE 约 2.4、3.8 cm 与 AUC 约 0.48、0.39。
- 合起来：这一轮要四项都超过基线，5 条里大致要成 4 条，而且 ep16、3、2 都在里面。可能做到，但不是大概率；做不到时 SP-SR 打平或差一条最可能。

**这次不做的**

- Tier 2 先验为 0 的 7 条（ep1、4、9、11、17、25、28）：另查失败原因（方盒几何、VOC 依赖、物体转很多圈），查清再说。
- seed 43：等 t1xb、t1yb 的结果，只补 1 世界没成功的集（10/12 第 4a 节第 6 条），这次新加一个条件：4096 世界 SP-SR 不是 0。
- HF 归档第 5 批：mf4090 磁盘够，非必须不删。
- Tier 2 b1013 交不交：用户定。

## 3. 代码、清单与输入

1. `stages/policy/make_var_queue.py` 加两份清单，基线都取 `stages/evaluate/exports/t1_select_r3x.tsv`：
   - `t1xb`：mf4090、400 万 buffer、run 名 `t1-ep<N>-w2048-cap4m-r3a-mf4090`，派生规则同 t1x，W&B 标签 `t1xb`。5 条的期望表行与 t1xa 的逐字相同，
     冒烟都已 DONE（state 已删，记 STATE_PRUNED），正式 run 的目录里只有 `.lock`（`results/t1x/precheck_t1xa3_mf4090.txt`，同一批 run）。
   - `t1yb`：ml40、1000 万 buffer、run 名 `t1-ep<N>-w2048-cap10m-r3a-ml40`，派生规则同 t1y，W&B 标签 `t1yb`。ep16、ep2 的期望表行与 t1ya 的逐字相同
     （t1ya 没起过链）。ml40 上 5 条的正式与冒烟目录都没有，也没有 t1y 的日志（`results/t1x/precheck_t1yb_ml40.txt`，10/13 22:01）。
2. `stages/policy/test_make_var_queue.py` 补两段的用例：顺序、run 名、W&B 标签、buffer 覆盖（t1xb 一律 400 万；t1yb 没有，测试夹具里奇数号的基线
   在 mf4090 上，带的 400 万覆盖要去掉），以及同一条 run 在两段里的行相同（期望表逐字，正式行只差标签，冒烟行相同）。
   已有的段（t2xa 到 t3qb 的预设段与 t1xa2）重新生成逐字节不变（`results/t1x/queue_t1xb_t1yb_regen.txt`；第 1 版的 `queue_t1yb_regen.txt` 留档）。
3. 删掉 t1xa3 的四份文件；`stages/evaluate/exports/t1_select_t1x1013.tsv` 是 t1x1013 的选中清单（与 `results/ml40/select_t1/t1_select_t1x1013.tsv`
   逐字节相同），给 `select_t1.sh` 的 `V2D_SELECT_CURRENT` 用（它只接受 `stages/evaluate/exports/` 下的文件，审查第 1 条）。
4. 输入核对（同 10/12 第 0 步第 7 条）：在 ml40 上重新收集 5 条序列的 Tier 1 参考 parquet 的 sha256、`v2d_meta.json` 与支撑面 md5，
   与基线 `run_record` 里的值和 mf4090 上的比（真实基线在 mf4090 上训的是 ep3、ep16）。10/13 22:00 做过：5 条都过，INPUTS_OK
   （`results/ops/t1yb_inputs_{ml40,mf4090}_1013.txt`、`results/ops/t1yb_inputs_compare_1013.txt`）。
5. 一次提交、推送。ml40 的长链标记都没了再同步；mf4090 等 Tier 3 的三条链结束再同步。每台同步前确认 Tier 3 的链都已结束，再删掉这台的
   Tier 3 停链标记并记录（同 10/12 的做法，审查第 11 条）。同步后在这台跑一次测试，再跑配置展开（意外键 0 个）、预演，最后起链。

## 4. 判据（执行前登记）

- 每条 run：冒烟过检查，256 世界 rollout 没有非有限世界；正式 run 有 DONE、35 份 policy、最后一步 349999104，最新 policy 非有限 0；
  评测 4096 世界；导出用 8c778f9 副本、1 个世界，导出与核对通过（同 10/12 计划 A）。
- 选（审查第 1、2 条）：每段导出完就用 `relay_t1x.sh <段> <基础目录>` 把新候选集中到 ml40（t1xb 经 Mac 管道转，t1yb 在 ml40 上直接抄）。
  先完的那段，基础目录是 `runs/select_t1_t1xa2`（t1x1013 用的那份）；后完的那段，基础目录是先完那段转出来的 `runs/select_t1_<先完的段>`。
  每转完一段就在 ml40 上跑一次 `select_t1.sh`，`V2D_SELECT_DIR=runs/select_t1_<刚转完的段>`；标签第一次 `t1c1014a`、第二次 `t1c1014b`。
  候选是 t1x1013 的全部候选加已转来的新候选；`V2D_SELECT_CURRENT=stages/evaluate/exports/t1_select_t1x1013.tsv`，
  `V2D_SELECT_GATE=0.471279,0.600000,0.533333,24.536550`（t1x1013 的四项合计，差不超过 1e-4），不满足就停。
  这期间用户若交了别的 CSV，现在交的清单与打分门换成那一份的；
  选择规则照登记的第 2 版不变：先比 MP-SR，再比 SP-SR，再比 AUC / 0.3780 − MPPE / 25.1706（大者优先），全部相同保留现在交的那条。打出新 CSV，不提交。
- 只报：每条的 4096 世界 SP-SR、MP-SR 与 Tier 2 先验并列；同一集两版（400 万、1000 万）并列；新 CSV 用 `t1_gap.py` 重算与两家的差距。
- 停：另一位用户交出新版重建、Tier 3 门槛加上两项检查之后，Tier 3 要重新开训时，用停链标记停 Tier 1 的段，在训的那条训完，已训完的照常评测与导出。

## 5. 风险与限制

- Tier 2 的先验对照的是 v5.4 参考；Tier 1 的 400 万版历来低于 Tier 2 的 1000 万版；1 世界导出有运气成分（ep29、ep5 是碰上的成功）。
- 组委会若事后重跑策略核验，碰上的成功可能复现不了；规则没写会不会重跑。
- 两段都在 Tier 1 上，Tier 3 新版重建来得早就要停链，最多晚一条 run（约 2.2 小时）。
- 封榜 11/4 15:00（UTC-6），训练在 10/27 前结束；本周每个 Tier 1 比赛已交 1 次（每周 5 次）。
- 档位隔离：Tier 1 的计划读 Tier 2 的评测结果来选集，方向是 Tier 2 → Tier 1，不碰规则禁止的“Tier 2、Tier 3 读 Tier 1 干净轨迹”；
  Tier 2、Tier 3 的管线不读这次 Tier 1 的任何结果。

## 审查与处理（Fable 5.1，GO WITH FIXES）——第 1 版

审查抽查约 70 个数，只有一处与记录不符（第 3 条）；`t1yb` 条目、`resolve()` 的取名、已有段逐字节不变、测试 11 个用例都确认过；
执行顺序与 `scripts/dev/remote`、`arm_var_chain.sh`、`relay_t1x.sh`、`select_t1.sh` 的规则一致；档位隔离与提交规则没问题。

| # | 级别 | 意见 | 处理 |
|---|---|---|---|
| 1 | MINOR | `select_t1.sh` 的 `V2D_SELECT_CURRENT` 只接受 `stages/evaluate/exports/` 下的文件，t1x1013 的选中清单不在那里；起链后 ml40 不能同步 | 采纳：复制为 `stages/evaluate/exports/t1_select_t1x1013.tsv`，随这次提交同步 |
| 2 | MINOR | 基础目录写死成“t1yb 用 t1xa3 转完的那份”，但 t1yb 多半先完；`relay_t1x.sh` 要求基础目录已存在；选的标签没登记 | 采纳：先完的段用 `runs/select_t1_t1xa2`，后完的用先完那段的目录；标签 `t1c1014a`、`t1c1014b` |
| 3 | MINOR | “变体 A 的 10 对”数错 | 采纳：13 对（Tier 1 8、Tier 2 5），2 对变 0.10 以上 |
| 4 | MINOR | “超过基线至少修 AUC 2 条、MPPE 2 条”沿用了从 ep25 修起的顺序，ep25 这次不训 | 采纳：第 2 节按这 5 条重写 AUC、MPPE 各要成哪几条 |
| 5 | MINOR | 计划 C 的停手规则已判不起，本计划用新判据训 C 里的 ep16、ep2，只在第 1 节侧面提到 | 采纳：第 2 节写明 t1yb 取代 C 的门、理由，其余 4 条照旧不起 |
| 6 | MINOR | t1xa3 先训 SP-SR 已是 1 的 ep10，Tier 3 重新开训会截断这一段 | 采纳：新清单 `t1xb`（ep3、19、13、10、14），删掉 t1xa3 的文件；ml40 的顺序相应改成 ep16、2、3、19、13 |
| 7 | NIT | seed 43 的规则多了一个条件，却写成“同 4a 第 6 条” | 采纳：标成这次新加的条件 |
| 8 | NIT | 磁盘数单位混用 | 采纳：写 KiB 原值，括号里换算成 GiB、TiB |
| 9 | NIT | “这次要训的 14 条”应是表里的 14 条 | 采纳 |
| 10 | NIT | “奇数号基线在 mf4090 上”说的是测试夹具 | 采纳：注明夹具；真实情形写在第 3 节第 4 条 |
| 11 | NIT | 两台的 Tier 3 停链标记链结束后还在 | 采纳：第 3 节第 5 条加一步，同步前删并记录 |

## 执行记录（10/13，时间 UTC-6）

- 22:26 ml40 上 Tier 3 的三条链都结束（`results/t3q/end_t3qa_ml40_1013_2226.txt`），删掉 t3qa 的停链标记（`results/t3q/unstop_t3qa_ml40.txt`）。
- 22:27 同步 ml40 到 004978a（工作树干净）；测试 `test_make_var_queue.py`、`test_make_trial_queue.py`、`test_select_t1.py` 都是 ALL_OK，
  几个链脚本 `bash -n` 通过，t1yb 四份文件的 md5 与 Mac 上的相同（`results/t1x/tests_ml40_1013.txt`）。
- t1yb 配置展开：10 份配置，与官方配方不同 14–16 个键，意外 0 个，配置核对通过（`results/t1x/cfgcheck_t1yb_ml40.txt`）；
  预演 DRYRUN_OK：5 条 run，来历 004978af97ed，可用 1,381,278 MB，训练挂 `v040_p185_nfg`，评测与导出挂 `fc_8c778f9`，只评 349999104 步
  （`results/t1x/arm_dryrun_t1yb_ml40.txt`）。
- 22:29 t1yb 起链 ARMED，第一条冒烟 ep16（`results/t1x/arm_t1yb_ml40.txt`）。5 条冒烟先跑完再跑正式，预计 10/14 10:00 前后训完（估计）。
- 22:55 t1yb 的 5 条冒烟都通过（SMOKE_OK，256 世界 rollout 非有限世界 0 个），开训正式 ep16（`results/t1x/status_t1yb_ml40_1013_2359.txt`）。
- 23:53 mf4090 上 t3p4b 的三条链都结束：DAY2_TRAIN_DONE（完成 8）、DAY2_EVAL_DONE（成功 8）、EXPORT_CHAIN_DONE（成功 8、失败 0）
  （`results/t3p4/end_t3p4b_mf4090_1013_2354.txt`、`results/t3p4/export_t3p4b_mf4090.txt`）。23:54 删掉 t3p4b 的停链标记
  （`results/t3p4/unstop_t3p4b_mf4090.txt`；这份记录里打印导出表的 awk 引号写错，那一段报错没打出来，删标记照常执行，导出表另记在 export 那份）。
- 23:55 同步 mf4090 到 fa52504（`results/` 以外干净）；三个测试都是 ALL_OK，链脚本 `bash -n` 通过，t1xb 四份文件的 md5 与 Mac 上的相同
  （`results/t1x/tests_mf4090_1014.txt`）。
- t1xb 配置展开：5 份正式配置与官方配方不同 16 个键，意外 0 个；5 条冒烟此前已 DONE，跳过核对（`results/t1x/cfgcheck_t1xb_mf4090.txt`）。
  预演 DRYRUN_OK：5 条 run，来历 fa5250481779，可用 88,893 MB，训练挂 `v040_p185_nfg`，评测与导出挂 `fc_8c778f9`，只评 349999104 步
  （`results/t1x/arm_dryrun_t1xb_mf4090.txt`）。
- 23:56 t1xb 起链 ARMED（`results/t1x/arm_t1xb_mf4090.txt`）。冒烟已 DONE 的 run 先由链复核（SMOKE_OK）再开训正式，第一条正式是 ep3。
  t3p4b 在这台每条训 1 小时 53 分到 2 小时 33 分（平均约 2 小时 10 分），照此估计 5 条正式 10/14 11:00 前后训完，评测与导出再加约 40 分钟（估计）。
