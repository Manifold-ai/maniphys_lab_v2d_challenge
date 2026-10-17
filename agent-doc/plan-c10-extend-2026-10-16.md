# 计划：接触标记提前的今夜延伸——Tier 1 补两集，Tier 2 按自己的数据试（2026-10-16 18:2x MDT，第 2 版：按独立复核修改）

## 1. 事实

- 卡的时间线：mf4090 上 t3pk、t3ps 约 23:15 结束；ml40 上 t1c 约 01:30 训完，02:00 前后出 C1 总判（`agent-doc/handoff-2026-10-16-evening.md`）。
  到 10/17 早上，两台各空 5–8 小时。
- 榜（`results/submission/leaderboard_1016_0630.txt`）：Tier 1 SP-SR 我们 0.73333、FF 0.80000（差 2 集）；MP-SR 0.63333 对 0.66666（差 1 集）；
  MPPE 我们 16.55939 排第三（DAP 12.65831、FF 8.22045）。Tier 2 MPPE 我们 15.32195、FF 15.34253，只领先 0.02 cm。
- 跟丢集：Tier 1 的 7 集（ep1、2、4、9、11、25、28）全在 Tier 2 的 8 集里，Tier 2 多一集 ep17（`stages/policy/r3o_verdict.json` 的 P1、P2）。
- Tier 1 现在交的 run 里，ep9、ep2 的 MPPE 是 40.66、24.51 cm（`results/t1gap/t1_gap_t1c1014b.txt`）。
- Tier 2 跟丢集的物体越线时刻（MP-SR 门槛 0.03 m、0.52 rad；Tier 2 的 run 对照 Tier 2 自己的参考；t_obj 中位步，逐帧回放下步号就是帧号）：
  ep1 130、ep2 118、ep4 51、ep9 164、ep11 61、ep17 124、ep25 119、ep28 111（`results/r3o/fall_order_one_t2_{ml40,mf4090}.txt`）。
- Tier 2 各集对照自己参考的 4096 世界 MPPE（10/14 交的 run，`results/first/t2_mppe_proxy.txt`）：ep4 119.8、ep25 117.1、ep28 58.7、ep9 56.9、
  ep1 46.7、ep17 34.4、ep2 26.4、ep11 21.1 cm。
- Tier 2 跟丢集的基线（`stages/evaluate/exports/{ml40,mf4090}.tsv`）：ep1 是 ml40 的 t2-ep1-w2048-cap10m-p185-ml40，其余 7 集都是 mf4090 的 400 万 buffer。
- 档位隔离：c10 的“起点提前 10 帧”是看 Tier 1 的诊断定的；“补 15 帧以内的空档”是设计时写下的常数，Tier 1 的诊断记录里没有空档统计（`agent-doc/plan-t1-contact-anticipation-2026-10-16.md`、`results/t1diag/contact_window_mf4090.txt`；第 2 版按独立复核改）。
  按净室规矩，Tier 2 的每个数值参数都要能只由 Tier 2 的数据加物理常识推出，Tier 1 的结果不拿来选或调 Tier 2 的参数。
  所以 Tier 2 不照搬 c10，按第 3 节用 Tier 2 的数据重定；Tier 2 这一路起不起也不看 C1 的结论，只按 Tier 2 自己的特征与结果判。
- 两台的代码：ml40 来历 4e58a15，已有 t1c* 段与 Tier 1、2 带后缀参考目录的放行，链在跑，今夜不能整体同步；
  mf4090 来历 4fff7bd，这两样都没有，t3ps 的链结束前不能同步。

## 2. 路 A：ml40，Tier 1 的 c10 补 ep9、ep2（段 t1c2）

- 条件：C1 总判是“有用”或“看不清”（`results/t1diag/verdict_C1_ml40.txt` 最后一行）。“没用”或没有总判就不起，卡空到早上。
  理由：“有用”时这两集是剩下的同类跟丢集（ep4 的机理不同，不做）；“看不清”时多两集能把判读看清；“没用”时这两集修好的机会很小，卡留给早上另定。
- 配方与 t1c 完全相同：变体 A、seed 42、1000 万 buffer，参考 runs/motion/tier1_c10（起点提前 10 帧、补 15 帧以内的空档，参考轨迹不变）。
  run 名 t1-ep9-w2048-cap10m-r3a-c10-ml40、t1-ep2-w2048-cap10m-r3a-c10-ml40，先 ep9（MPPE 贡献大）。基线取法同 t1c（10/9 逐条选的清单，去掉 -r3a-）。
- 机制（不同步 ml40，只放新文件）：
  1. 本地改 `make_var_queue.py`：t1c 清单的 episodes 末尾加 9、2，预设段 t1c 不变；`make_var_queue.py t1c2 --episodes 9,2` 生成队列与导出清单，
     提交后用 push-new-files 放到 ml40。
  2. ml40 容器里 `contact_relabel.py` 只新增 ep9、ep2 两个序列到 tier1_c10（已有的 4 个不动；目标已存在会拒绝）；
     `check_inputs.py` 核对新参考；`fc_config_check.sh` 生成配置核对（容器里，不占 GPU）。
  3. `arm_after.sh` 复制到 runs/tools/，setsid 起：等 t1c 的三条链结束、卡空；`V2D_PRE_CMD` 跑 `stages/policy/gate_verdict.sh`（第 2 版新加，带测试）：等 C1 判读记录出现（最多 30 分钟），只看最后一行、整行匹配 `R3O_VERDICT (有用|看不清)`，见到 `.failed` 立刻不放行；
     t1c 的 4 条全部训完、评测与导出都没有失败才起 t1c2（arm_after 第 5 步）；起链前的预演与核对由 `arm_var_chain.sh` 自己做。
- 判读 C2（明早手工）：同 C1 的逐集判法，基线取 P1 登记的 ep9、ep2；C1、C2 合起来报。
- 时间：约 02:00 起，两条加评测导出约 5 小时，07:00 前后完。

## 3. 路 B：mf4090，Tier 2 按自己的数据定参数的接触标记提前（段 t2m）

### 3.1 第 0 步：Tier 2 诊断（只用 CPU；下面的判据在算之前登记）

- 只读 Tier 2 的 30 份参考（runs/motion/tier2）与第 1 节 Tier 2 的越线时刻。新脚本 `stages/evaluate/contact_onset_table.py`：
  只收 runs/motion/tier2/ 下的参考，启动时装 Tier 1 禁读（`libs/v2d_infra/tier_guard.forbid_tier1`）。
- 每集报：每只手的首次接触帧、接触段数、段间空档的长度；最早接触的那只手接触后 30 帧内物体自转与平移；跟丢集的 delay = 越线步 − 最早首次接触帧。
- 特征（三条至少过两条，才做 3.2）：
  1. 8 个跟丢集里至少 5 集 0 ≤ delay ≤ 40 帧；
  2. 接触后 30 帧内物体自转的中位，跟丢集至少是其余各集的 3 倍；
  3. 跟丢集里有接触的手，接触段数的中位 ≥ 3。
- 参数：
  - lead_T2 = 跟丢集里 delay ≥ 0 的最小值，向上取到 5 的倍数，限在 [5, 20] 帧。
  - gap_T2 = 15 帧（30 fps 下 0.5 秒）：取人松手再抓的最短间隔为 0.5 秒，0.5 秒以内的空档算同一次抓握。这是先验，不来自任何一档的数据；
    数值与 Tier 1 的相同，请复核判断合不合规。复核不认这个先验，就不补空档（gap_T2 = 0），只做提前。
    复核结论（第 2 版）：15 在 Tier 1 也是设计常数，不是从 Tier 1 数据算的，可以按先验用。gap 没有预登记只用 Tier 2 数据的规则；执行记录里“≤ 15 帧的 85/119”是用这个 15 算的，不能反过来当依据。下一轮按 Tier 2 的空档分布预登记取法。
- 注（第 2 版）：同一条 lead 规则代入 Tier 1 的数得 10（`results/t1diag/contact_onset_t1_ml40.txt`），与 c10 当时的取值一致，只说明规则是当时取法的公式化，不参与 Tier 2 的取值。三条特征的门槛（40 帧、3 倍、段数 3）是看过 Tier 1 的结果后定的，只决定路 B 做不做，不进 Tier 2 的参数。
- 选集：0 ≤ delay ≤ 40 的跟丢集里，按第 1 节的 MPPE 从大到小取前 3 集。
- 特征不过：路 B 不做，mf4090 空到早上。

### 3.2 训练

- 参考：mf4090 容器里 `contact_relabel.py --src runs/motion/tier2 --dst runs/motion/tier2_c<lead_T2> --meta-src runs/motion_src/tier2 --meta-dst runs/motion_src/tier2_c<lead_T2> --lead <lead_T2> --gap <gap_T2>`，只放选中的 3 集；期望表 support 列是 true 的集，输出里必须打印出支撑面文件名，否则不起（第 2 版）；
  `check_inputs.py` 核对。
- 配方：变体 A、seed 42、400 万 buffer，只换参考目录（ep25、ep9 的基线是 mf4090 的 400 万 buffer，同机器、同 buffer；ep1 的基线是 ml40 的 1000 万 buffer，t2-ep1-w2048-cap10m-p185-ml40，这一集机器与 buffer 都不同）；run 名 t2-ep<N>-w2048-cap4m-r3a-c<lead_T2>-mf4090。
- 代码：
  - `make_var_queue.py` 新清单 t2m：Tier 2、mf4090、400 万，基线取 Tier 2 导出清单，带 -r3a- 的取基线配方 run（同 t2o）；
    Tier 2 段换参考目录（/runs/motion/tier2/ 换成 /runs/motion/<motion>/，目录名必须以 tier2_ 开头），补测试。
  - `arm_var_chain.sh` 加 t2m*（mf4090、Tier 2，EXTRA 同 t1x）。
- 起法：t3ps 的链全部结束、卡空后整体同步 mf4090（要 Mac 在线），先 df（可用少于 20 GB 不起；18:35 时 78 GB），再生成参考、配置核对、预演、起链。Mac 那时不在线就不做，mf4090 空到早上。
- 判读 C3（明早手工）：逐集判法同 C1，基线取 P2 登记的同集基线；总判：修好 ≥ 1 集“有用”，修好 0 集但有起色 ≥ 2 集“看不清”，其余“没用”。ep9 单列：Tier 2 参考里物体第 25 帧就离开初始位姿、首次接触第 161 帧，可能与 ep28、ep4 同一种丢法（第 2 版）。
  只报不判：新 run 的 4096 世界 MPPE 与 Tier 2 现在交的那条并列。
- 时间：约 23:30 起，3 条加评测导出约 8 小时，07:30 前后完。

## 4. 不做与风险

- 不拿 C1 的结论决定路 B（档位隔离）；路 A 是 Tier 1 内部的事，可以看 C1。
- 单种子；修好一集也可能是种子运气，修好的集下一步补 seed 43。
- 提前的帧数里参考的手离物体还有几厘米，抓握奖励与掌心跟踪会有一点冲突（同 t1c 的风险）。
- 路 A 起链时 GPU、来历、磁盘、配置的核对都由 `arm_var_chain.sh` 自己做，任何一步不过就不起，卡空着，明早处理。
- 路 B 要 Mac 在 23:15–01:30 之间在线完成同步；不在线就跳过，不影响别的。

## 5. 执行记录

- 18:30:41 第 1 版与 `contact_onset_table.py` 先提交（063bd9d），18:31:04 再在 ml40 容器里跑 Tier 2 诊断（只读 runs/motion/tier2 的 30 份参考，装了 Tier 1 禁读；
  `results/t2diag/contact_onset_t2_ml40.txt`）：
  - 特征 3/3 过。特征 1：0 ≤ delay ≤ 40 的 6 集（ep1 +26、ep2 +24、ep9 +3、ep11 +3、ep17 +10、ep25 +17）；特征 2：接触后 30 帧内物体自转中位
    跟丢 20.6°、其余 4.8°（4.3 倍）；特征 3：跟丢集有接触的手 15 只，段数中位 7。
  - lead_T2 = 5（最小 delay 是 ep9、ep11 的 +3，向上取到 5）。与 Tier 1 的 10 不同，按 Tier 2 自己的数定。gap_T2 按登记取 15，等复核。
  - 选集：ep25（117.1 cm）、ep9（56.9）、ep1（46.7）。参考目录 tier2_c5，run 名带 -c5-。
  - 新看到的（只记录，今夜不处理）：ep28 的 delay 是 −288、ep4 是 −82，即 Tier 2 参考里这两集物体先越线、接触标记很晚才开始
    （ep28 首次接触第 399 帧，越线第 111 步）。这两集正是 MPPE 贡献第 1、3 大的，丢的机理与接触后来不及抓不同，提前 5 帧管不到，明天另写计划。
  - 18:37 补量（只报不判，`results/t2diag/motion_before_contact_t2_ml40.txt`，Tier 2 的 30 份参考，门槛 3 cm 或 10° 只用于描述）：
    物体离开初始位姿与首次接触标记之差，跟丢 8 集中位 +42 帧（接触晚 30 帧以上的 4 集：ep4 +122、ep9 +136、ep17 +99、ep28 +285），其余 22 集中位 −40 帧
    （晚 30 帧以上的 3 集：ep6、ep24、ep26，都跟得好）。离开初始位姿而没有接触标记的帧占比：ep28 78%、ep4 43%。
    读法（推断）：ep28、ep4 的参考里物体动了很久都没有接触标记，force_closure 在这段完全不计分；ep9、ep17 的“提前离开”可能是参考的漂移，
    它们越线在首次接触后 3、10 帧。这个量对跟得好的集也会报出 +184（ep26），单用它分不清真动与漂移，明天的计划要换更稳的“在动”判据。
- 代码：`make_var_queue.py` 的 t1c 清单加 ep9、ep2（预设段 t1c 不变），新清单 t2m，Tier 1、2 段换参考目录合成一个分支并核对目录名的档位；
  `arm_var_chain.sh` 加 t2m*；`r3o_verdict.json` 加 C2（基线照抄 P1 的 ep9、ep2）与 C3（照抄 P2 的 ep25、ep9、ep1；ep1 登记的基线是
  t2-ep1-w2048-cap10m-r3a-ml40，队列取基线配方用的是导出清单里的 t2-ep1-w2048-cap10m-p185-ml40，两者失败_物体都是 1.0、SP-SR 都是 0）。
  测试：`test_make_var_queue.py`（加 t1c2、t2m 两项）、`test_r3o_verdict.py`（C2、C3 的基线与 P1、P2 一致）都 ALL_OK。
- 生成的队列：`stages/policy/queues/ml40_t1c2*`、`mf4090_t2m*`，导出清单 `stages/evaluate/exports/cand_t1_t1c2_ml40.tsv`、`cand_t2_t2m_mf4090.tsv`。
  t2m 三集的期望表 support 列都是 true，支撑面由 `contact_relabel.py` 照抄到 tier2_c5。
- 独立复核（Fable，18:5x）：GO WITH FIXES，没有 MAJOR，7 条 MINOR、4 条 NIT。处理：
  - MINOR 1（gap 的来历）、MINOR 2（时间戳）、NIT 8（ep1 的基线、命令缺参数）、NIT 10（特征门槛的来历）、NIT 11（ep9 单列）：改正文，见上。
  - MINOR 3：路 A 的闸改用 `stages/policy/gate_verdict.sh`（只看最后一行、整行匹配，见到 .failed 立刻停），`test_gate_verdict.py` ALL_OK。
  - MINOR 4：`tier_guard` 只拦原始数据目录 tier_1_multiview_caption，runs/motion/tier1、runs/motion_src/tier1 不在内；这两个诊断脚本真正起作用的是只收
    runs/motion/tier<档>/ 的路径检查，打印的提示改成实话。把派生目录加进 `tier_guard` 要先查它的所有调用方（打包器读 Tier 1 的参考算本地分数），留作后续，不在今夜改。
  - MINOR 5：`test_contact_onset_table.py` 在 ml40 容器里跑并记录（`results/t2diag/test_contact_onset_table_ml40.txt`，ALL_OK）。
  - MINOR 6、7：路 B 起链前加 df 一步，三集的支撑面文件必须在 relabel 输出里打印出来，见 3.2。
  - NIT 9：t1c2 队列头注沿用 t1c 清单的描述（“跟丢的 4 条”），同一行写着“这一段 t1c2：ep9、ep2”，不改（改了要重推队列、重做配置核对）。
