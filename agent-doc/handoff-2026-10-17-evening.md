# 交接：10/17 晚到 10/18 早上，两台服务器上自己跑的事（2026-10-17 17:2x MDT，分支 track2/p1-training）

Mac 可能随时断网：下面这些都在服务器上用 tmux 或 setsid 跑，记录落在各自服务器的 `results/`，Mac 联网后用 `scripts/dev/pull-results`
（ml40 加 `V2D_ENV=ml40`）拉回再提交。计划：`agent-doc/plan-t3-gb3-switch-2026-10-17.md`（第 2 版，独立复核 GO WITH FIXES 已改；执行记录在文末）。

## 两台的安排

| 机器 | 现在 | 链结束、卡空之后（服务器上的 arm_after 自己接） | 读数 |
|---|---|---|---|
| mf4090 | t2m2：Tier 2 ep2、11、17 的接触标记提前（tier2_c5），约 21:00 评完导出 | t3pg：gb3 参考上训 ep20、ep0、ep22、ep21（buffer 400 万），日志 `runs/logs/arm_after_t3pg_mf4090.log` | 评测链写完后自动跑 `gb3_switch.py`，记录 `results/t3gb3/switch_t3pg_mf4090.txt`（最后一行 `GB3_SWITCH_DONE <换> <不判>`） |
| ml40 | t1c_s43：Tier 1 ep28、11、2 补 seed 43，约 21:00 评完导出 | t3qg：gb3 参考上训 ep6、ep8、ep7、ep29（buffer 1000 万），日志 `runs/logs/arm_after_t3qg_ml40.log` | ml40 上 `results/t3gb3/switch_t3qg_ml40.txt`（拉回后在 `results/ml40/t3gb3/` 下） |

- arm_after 设了 `V2D_AFTER_INDEPENDENT=1`：t2m2、t1c_s43 有一条失败也照起 Tier 3（两段互不相干）。arm_after 日志最后一行是 `ARM_AFTER_ARMED`
  或 `ARM_AFTER_STOPPED <原因>`；停了（例如卡被别人占着超过 2 小时）就早上手动起：`stages/policy/arm_var_chain.sh t3pg`（ml40 是 t3qg），先 `V2D_ARM_DRYRUN=1` 预演。
- 估计：每条约 2.2 小时，两台的训练约 05:50 写完；评测链等整段训练写完才开始，评测与导出约 06:40 做完。
- 换不换按计划判据 G2（规则 S，结果出来之前登记）：候选 MPPE ≤ 现选 + 4.0 cm 且 SP-SR ≥ 0.5。ep21 只报；ep22 进选集要 rxzhou 点头
  （10/16 定的留旧参考），人脚检验已做：gb3 的 ep22 −3.77 cm，与旧参考 −3.76 cm 基本相同（`results/ml40/t3gb3/feet_gb3_ml40.txt`）。

## 21:10 的检查（Mac 在线时）

1. t1c_s43 → 按 c10 的选法把 seed 43 的三集放进 `runs/select_t1_c10` 打分（`--no-pack`，标签 c10s43_1017），交 Tier 1 要先问 rxzhou。
2. t2m2 → `r3o_verdict.py C4`；修好的集按 4096 世界优先换进 Tier 2 选集，打包预演后直接交（rxzhou 10/16 的常设授权）。
3. 看两份 arm_after 日志是不是 `ARM_AFTER_ARMED`，tmux 里 v2d-t3pg-*、v2d-t3qg-* 三个会话都在。

## 明早要做

1. 拉回两台的 results，读两份 `switch_*` 记录。
2. 按计划做法 4 选集（kfix1017 的 30 行，判换的集换成新 run），逐集并列报 4096 世界与导出世界的值，打包预演；交不交、ep22 进不进由 rxzhou 定。
3. 判读按 G3（τ = 1.0 cm；“看不清”时 AUC 与 SP-SR 都不低于 kfix1017 才留新版）。
4. 写 Tier 2 ep28、ep4（物体动了很久都没有接触标记）与 Tier 1 跟丢集的计划，排 10/18 白天的卡。

## 今天已经知道的（都有记录）

- gb3 的 11 集参考对各自训练参考的变化（物体相对机器人根，中位）：ep8 1.59 cm，其余 2.5–6.3 cm；k-fix → gb3：ep0、18、24 约 1 cm，ep26 1.8 cm，
  ep29 5.8 cm（`results/t3gb3/refdiff_mf4090.txt`）。
- gb3 的重定向间隙 −0.5 到 0.0 mm，比 v2、k-fix 参考小得多（`results/t3gb3/retarget_mf4090.txt`）。
