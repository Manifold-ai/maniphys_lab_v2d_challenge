# 交接：10/18 早上到下午，两台服务器上自己跑的事（2026-10-17 23:5x MDT，分支 track2/p1-training）

Mac 可能随时断网：下面这些都在服务器上 setsid 后台跑，记录落在各自服务器的 `results/`，Mac 联网后用 `scripts/dev/pull-results`
（ml40 加 `V2D_ENV=ml40`）拉回再提交。计划：`agent-doc/plan-ep25-sweep-seeds-2026-10-18.md` 第 2 版（判据已登记；独立复核 GO WITH FIXES，已按意见改，见计划文末）。起链命令原样在计划第 4 节。
上一份交接 `agent-doc/handoff-2026-10-17-evening.md` 的 gb3 部分照旧有效。

## 两台的安排

| 机器 | 现在 | gb3 链结束、卡空之后（arm_after 自己接） | 再往后 |
|---|---|---|---|
| mf4090 | t3pg（gb3 参考上训 ep20、0、22、21），约 06:40 评测导出做完 | 前置命令：ep25 扫描 `ckpt25_mf4090`（Tier 2 c5、Tier 1 r3o 各 7 份粗扫 + 细扫，约 1.7 小时，限时 8 小时），然后起 t1xb_s44（ep14 seed 44） | t1xb_s44 做完后看闸（ep14：导出 MP 已成功或 4096 世界 MP-SR < 0.3 就不训），过了起 t1xb_s45 |
| ml40 | t3qg（ep6、8、7、29），约 06:40 做完 | 前置命令：ep25 扫描 `ckpt25_ml40`（Tier 2 两条、Tier 1 两条，约 3.3 小时，限时 10 小时），然后起 t1c_s44（ep11 seed 44） | 同上，ep11 的闸看 SP-SR（下限 0.4），过了起 t1c_s45 |

- 日志：`runs/logs/arm_after_<段>_<机器>.log`（最后一行 `ARM_AFTER_ARMED` 或 `ARM_AFTER_STOPPED <原因>`）；扫描 `runs/logs/ckpt25_<机器>.log`
  （最后一行 `CKPT_SWEEP_DONE（…）`），粗扫、细扫、导出各自的链日志 `ckpt25_<机器>_{c,r,x}.log`；选点记录 `results/ckpt_sweep/ckpt25_<机器>_pick.txt`。
- 扫描链参数对就总是退出码 0；扫描超时（mf4090 8 小时、ml40 10 小时）或参数错，arm_after 停、训练段不起，要手动处理，并 `ls runs/.chain-active-ckpt25_*` 核标记清掉了没有。
- 闸没过时第二个 arm_after 的最后一行是 `ARM_AFTER_STOPPED 前置命令没过（退出码 1）`，这是预期的。

## 早上要做

1. 拉回两台的 results，读 gb3 的两份 `switch_*` 记录（见上一份交接），按 G3 选 Tier 3、打包预演，交不交与 ep22 由 rxzhou 定。
2. 读两份 ep25 选点记录（`results/ckpt_sweep/ckpt25_<机器>_pick.txt`，ml40 的拉回后在 `results/ml40/ckpt_sweep/`），按计划 2.3 的 E1 把两台的点合在一起，
   用同一个选法（最低值 + 1 cm 内取步数最大）选一点；dump 的“带离很远”比例只报：
   - Tier 2（E3）：导出 MPPE（导出 JSON，对自己的 v5.4 参考）< 115.88 且 4096 世界 < 117.09 → b1014 清单只换 ep25，`pull_submission.sh tables`
     与 `select` 把 30 集拉进一个新目录（`exports` 子命令遇到已有的 episode_000025 会拒绝），`pack_tier.sh 2` 打包预演，按常设授权交；
     步数 ≤ 150005760 先问 rxzhou。
   - Tier 1（E2）：导出 MPPE < 117.9944 → 做 (a) c10s43 只换 ep25、(b) auc1017 把 ep25 换成这一点 两份，`pack_tier.sh 1` 打包预演，
     并列导出世界与 4096 世界的四项，交不交、交哪份由 rxzhou 定（auc1017 本身也还在等）。
3. 第二个 arm_after 起训练前，如果 Tier 3 要卡，停掉它（自己的进程）。
4. 07:00 SOP 定时更新；约 07:30、10:30 MDT 各看一次两台的 arm_after 与扫描日志。

## 还开着的

- auc1017（`runs/submission/csv/track2_tier1_select_auc1017.csv`，sha256 e87c70e5…）等 rxzhou 点头；Tier 1 本周还剩 2 次，下一次空出是 10/20 17:53 MDT。
- 同一 policy 换种子重导一局（导出是公平抽样，重导等于挑运气）：等 rxzhou 定，计划没有用。
- 组委会账号加仓库协作者（要组织管理员）；要不要发邮件问组委会三档怎么合成，rxzhou 定。
