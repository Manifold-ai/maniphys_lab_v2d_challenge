# 计划：冻结前最后一轮，三台接着训 r3o 的余下各集，补 Tier 3、Tier 2 AUC 榜的余量（final1，11/03，第 2 版）

2026-11-03 13:3x MST 写定第 1 版，13:5x MST 按独立复核改成第 2 版（改动见第 5 节），分支 track2/p1-training。判据在结果出来之前登记在这里。Tier 3 只用 Tier 3 的参考与对自己参考的读数（Tier 1 只经已对齐的帧参考用到第 0 帧，打包沿用 t3m1029a 的做法）；Tier 2 净室照旧（v5.4），不用 Tier 1 的任何数。配方、判据与 `plan-t3auc1-2026-11-03.md`、`plan-t2auc3-2026-11-02.md` 相同，只加集、加段。

## 0. 事实

1. **冻结**：Kaggle 12 个榜的截止都是 2026-11-04 22:00 UTC（11/04 15:00 MST，`kaggle competitions list` 11/03 13:1x MST 读出）。打包、提交每档约半小时，最后一次提交要在 11/04 约 14:00 MST 前交完。
2. **Tier 3 AUC**（`results/board/lb_1103_1040.txt`）：我们 0.28173 第 5；第 4 Debajyoti Dasgupta 0.28710；第 3 nima arki 0.32937（按 0.21 折算要 4096 世界 AUC 平均涨 0.24，追不上）。所以这个榜最多再进 1 名。
   a、b 段（`plan-t3auc1` 执行记录）换 ep0（1000 万）、ep18、ep23、ep24、ep26 后，导出那一局 +0.0454、4096 世界 +0.0295，折算 0.2879，比 0.2891 还差 4096 世界平均 0.0056（30 集合计约 +0.17）。c 段 ep7、ep22（mf4090，约 16:00 MST）、ep18 1000 万臂、ep27（ml40，约 18:30 MST）还没出。
3. **Tier 2 AUC**：我们 0.51765 第 6；第 5 Xueyi Wang (FF) 0.52267；第 4 Debajyoti Dasgupta 0.55274（要导出平均涨 0.18，追不上）。最多再进 1 名。
   `t2l3` 换 ep18、ep6，加 `t2auc2` 的 ep26，导出 +0.0271、4096 世界 +0.0270，折算 0.5233 < 0.5247，还差导出平均 0.0064（合计约 +0.19）。`t2l3b` 的 ep15 已训完在评测，ep8 约 15:30–16:00 MST 导出完。
4. **余下没试过 r3o、跟得住的集**（4096 世界，对自己参考；Tier 3 来自 `results/t3auc1/table_4096_t3m1029a.txt`，Tier 2 来自 `results/t2auc2/table_4096_t2a1102.txt`）：
   - Tier 3，mf4090 上 400 万 gb4 等参考：ep20 AUC 0.687（MP 0.814、SP 0.844），ep6 0.604（MP 0.074、SP 0.978），ep21 0.558（hm，MP 0.501、SP 0.876），ep29 0.377（v2，MP 0、SP 0.713），ep8 0.816（MP ≥ 0.9）。
   - Tier 3，ml40 上 1000 万 gb5 参考：ep15 0.493（MP 0.878、SP 0.886），ep5 0.486（MP 0.501、SP 0.852），ep10 0.308（MP 0、SP 0.949），ep14 0.318（MP 0、SP 0.844）。
   - Tier 2，1000 万变体 A（ml40 的 run，l40n 有全部 30 集的参考）：ep5 0.622（MP 0.956），ep22 0.663（0.997），ep16 0.696（0.938），ep29 0.715（0.898），ep20 0.731（0.984），ep27 0.808，ep24 0.814。
   跟丢的集（Tier 3 9 集、Tier 2 AUC < 0.3 且 SR 为 0 的）不碰，同 `plan-t3auc1` 第 3 节。
5. **r3o 已有的读数**：Tier 3 七条换集里六条过，ADD-AUC +0.08 到 +0.25；没过的两条一条是 MP-SR 差 0.005（ep12），一条 1000 万臂崩了（ep26，SR 0）。Tier 2 八条里六条过（+0.17 到 +0.37），ep21（MP 0.965 起点）没涨。MP-SR 起点低的集上 r3o 还没读数。
6. **机器与时长**（11/03 实测）：mf4090 400 万一条训约 1 小时 55 分，两条一段训、评、导出约 5 小时；ml40 1000 万一段约 4.5 小时；l40n（L40）一条约 2 小时 20 分，一段约 5 小时。盘：mf4090 剩 13 GB，ml40 904 GB，l40n 34 GB，一条 run 约 0.36 GB。
7. **接线**：派生用 `stages/policy/derive_r3o_rows.py`（Tier 3）与 `stages/policy/make_var_queue.py`（Tier 2，加配置项）；`arm_var_chain.sh` 已认 `t3pr3o*`、`t3qr3o*`、`t2l*`。链在跑时不许普通同步：新段的队列经 `scripts/dev/stage-remote` 暂存，由 `arm_after.sh` 的 `V2D_AFTER_SYNC_FROM` 在上一段结束后同步，`V2D_POST_SYNC_CMD` 跑 cfgcheck 与 precheck。

## 1. 做什么

排序：MP-SR ≥ 0.5 的集先排，同一档里按对照 ADD-AUC 从低到高；每台接在 c 段（l40n 是 `t2l3b`）后面，一段两条。

| 段 | 机器 | 集 | 配方 | 预计导出完（MST） |
|---|---|---|---|---|
| `t3pr3o2d` | mf4090 | ep20、ep6 | r3o，400 万，seed 42（由 `mf4090_t3pg4` 同集行派生） | 11/03 约 21:00 |
| `t3pr3o2e` | mf4090 | ep21、ep8 | 同上（ep21 由 `mf4090_t3p4b`、ep8 由 `mf4090_t3pg4`） | 11/04 约 02:00 |
| `t3pr3o2f` | mf4090 | ep29 | 同上（`mf4090_t3p3a`） | 11/04 约 05:00 |
| `t3qr3o2d` | ml40 | ep15、ep5 | r3o，1000 万，种子同对照（ep15 seed 42，ep5 seed 43；`ml40_t3qhr3s`、`ml40_t3qs_s43`） | 11/03 约 23:00 |
| `t3qr3o2e` | ml40 | ep10、ep14 | 同上（seed 43，`ml40_t3qs_s43`） | 11/04 约 03:30 |
| `t2l4` | l40n | ep5、ep22 | r3o，1000 万，seed 42（配方同 `t2l3`） | 11/03 约 21:00 |
| `t2l4b` | l40n | ep16、ep20 | 同上 | 11/04 约 02:00 |
| `t2l4c` | l40n | ep29、ep27 | 同上 | 11/04 约 07:00 |

- 截止线：一条 run 的预计导出完晚于 11/04 10:00 MST 就不起（留读数、打包、提交约 4 小时）。上表都在线内；实际进度晚了，由执行者用停链标记截掉排在后面的段。
- 第 3 段之后机器若还空，不另起新配方的 run。ml40 约 03:30 起空：同配方的 `t3qr3o2f`（ep20、ep6 的 1000 万臂，由 `mf4090_t3pg4` 加 `+10m` 派生，预计 08:00 前导出完）要先把两集的 gb4 参考经 HF 中转库转到 ml40（同 11/03 上午 ep0、26、18 的做法，`root_gb4` 已在 ml40）；03:30 前转好、核过才挂，转不好就让 ml40 空着。
- 起链：每台的第 1 个新段用 `arm_after.sh`（`V2D_AFTER_INDEPENDENT=1`）挂在现在那段后面，`V2D_AFTER_SYNC_FROM` 指向本计划提交的暂存目录，`V2D_POST_SYNC_CMD` 跑本段的 `fc_config_check.sh` 与 `precheck_expect.sh`（记录在服务器 `results/final1/`）。
  第 2、3 段不能现在就挂带同步的接力：第 1 段同步会改仓库副本的来历，`arm_after.sh` 等待中见到来历变了就停。所以第 2 段用 `relay_when_armed.sh` 等第 1 段的接力日志写 ARM_AFTER_ARMED，再起普通 `arm_after.sh`（不同步，照样跑 cfgcheck、precheck）；第 3 段等第 2 段的接力日志。接力日志 `runs/logs/arm_after_<段名>_<机器>.log`。
  ml40 上再让卡时（`arm_after_yield.sh` 会把上一段的日志移走），执行者要把下游接力重挂一次。
- 冒烟过关条件（链本身的之外）：训练日志有 `V2D object_orientation term: weight=1.0 std=0.4`。
- 测试：`derive_r3o_rows.py` 的输出过 `r3o_lines.awk`（坏行 0；派生文件表头写的是 `plan-t3auc1`，脚本写死的，配方相同，不改）；`make_var_queue.py` 新配置项 `t2l4` 的测试 `test_final1`；每段 cfgcheck 意外键 0、precheck 全过。

## 2. 判据（登记）

- **健康、换集**：与 `plan-t3auc1` 第 2 节、`plan-t2auc3` 第 2 节逐字相同（4096 世界，对各档自己的参考；ADD-AUC 比对照高 ≥ 0.03；MP-SR、SP-SR 不低于对照 − 0.02；MPPE 不比对照高 0.5 cm 以上）。同一集有两臂都满足时取 ADD-AUC 高的。
- **打包与上传**：各档的底是当时榜上 AUC 那份（Tier 3 t3m1029a，Tier 2 t2a1102）。所有满足换集条件的集（`t3auc1`、`t2auc2`、`t2auc3` 与本计划的）合进一份包算变化，门槛与折算条件照两份计划：
  - Tier 3：导出 ≥ 底 +0.010，4096 世界 ≥ 底 +0.005，0.28173 + 0.21 × min（两种变化）≥ 当时下一名 + 0.002。
  - Tier 2：导出 ≥ 底 +0.010，4096 世界 ≥ 底 +0.005，0.51765 + 0.21 × min（两种变化）≥ 当时下一名 + 0.002。取两者小的，与 Tier 3 相同，防止导出那一局一次抽签的运气单独过折算条件（`plan-t2auc3` 第 2 节只乘导出那一局，这里改严）。
  三条都满足才问 rxzhou，只交 AUC 一个榜（`--only add_auc`）。问时写明 0.21 只来自 Tier 2 的一对读数（另一对是负的），Tier 3 没校准过。
- **几时交**：c 段（Tier 3）或 `t2l3b`（Tier 2）读完时门槛就过的，当时就问，不等本计划的段；之后本计划的段读出来又有新的集过换集条件：交过一次之后下一名已经够不着（Tier 3 nima arki 0.329、Tier 2 Debajyoti Dasgupta 0.553），折算条件不再用；改成前两条门槛照旧、并且两种变化都比已交的那份高，才再问一次（榜分会变，不是同分重交）。最后一次读数在 11/04 约 10:30 MST，打包、提交在 14:00 MST 前完。
- **不交的榜**：SP-SR、MP-SR、MPPE 不重交（同 `plan-t3auc1` 第 2 节）。
- 读数不改判据；读法另写，标明是解释。

## 3. 不做什么

- 不碰跟丢的集；不改参考；不调 r3o 的参数。
- 不看 Tier 1 的数。
- 不停另一位成员的任何进程，不写她的目录；她要用 ml40 时照 11/03 12:0x 的做法让卡（`tools/arm_after_yield.sh`），由 rxzhou 定。

## 4. 执行记录

- 11/03 13:2x MST：派生八段队列（Tier 3 五段 `derive_r3o_rows.py` DERIVE_R3O_OK，`r3o_lines.awk` 坏行 0；Tier 2 三段 `make_var_queue.py t2l4|t2l4b|t2l4c`，`test_make_var_queue.py` ALL_OK，`results/t2auc3/test_make_var_queue_final1_mac.txt`）。三台上八段的参考 parquet 都在（15 份 OK）。提交 1ff201ef，`scripts/dev/stage-remote` 暂存到三台的 `runs/stage/1ff201ef1a6d`。
- 13:25 MST 挂接力（`V2D_AFTER_INDEPENDENT=1 V2D_AFTER_MAX_POLLS=1320`，每段的 `V2D_POST_SYNC_CMD` 跑 cfgcheck 与 precheck，记录在服务器 `results/final1/`）：
  mf4090 `t3pr3o2d`（带同步，等 `t3pr3o2c`）→ `t3pr3o2e` → `t3pr3o2f`；ml40 `t3qr3o2d`（带同步，等 `t3qr3o2c`）→ `t3qr3o2e`；l40n `t2l4`（带同步，等 `t2l3b`）→ `t2l4b` → `t2l4c`。第 2、3 段由 `relay_when_armed` 等前一条接力的 ARM_AFTER_ARMED。
  事故：mf4090 的 `t3pr3o2f` 第一次挂时，`relay_when_armed.sh` 把前一条接力（也是它自己）等待行里的 “ARM_AFTER_ARMED” 字样当成已起链，当场起了 `arm_after.sh t3pr3o2f`（还在等 e 段的日志，没起链）。停掉这个进程（我们自己的），日志改名 `.aborted_early`；改 `relay_when_armed.sh` 只认 arm_after 自己的结束行 “=== <时间> ARM_AFTER_ARMED”，加回归测试（Mac 与 mf4090 的 bash 5 都 ALL_OK，`results/final1/test_relay_when_armed_mac.txt`），提交 e 后的版本装成三台的 `runs/tools/relay_when_armed2.sh`（md5 6928cfe6934c），重挂 `t3pr3o2f`。正在跑的旧版本 relay（mf4090 `t3pr3o2e`）等的是 arm_after 的日志，不受这个问题影响，不动。
- 13:3x MST ml40 `t3qr3o2f`：`tools/t3auc1_gb4_stage.sh` 加 `V2D_GB4_SEQS`、`V2D_GB4_NO_ROOT`，在 mf4090 打包 ep20、ep6 的 gb4 参考（motion 59 MB、msrc 77 MB，不带 `root_gb4`），HF 中转库标签 `t3final_gb4_1103` HF_PUSH_OK 3，ml40 HF_PULL_OK 3，两个 tar sha256 OK，UNPACK_OK。`derive_r3o_rows.py --seg t3qr3o2f` 由 `mf4090_t3pg4` 加 `+10m` 派生 ep20、ep6（坏行 0；ep20 与对照一样带支撑面，没有 `scene.support=false`）。
  提交后单独暂存到 ml40，`t3qr3o2f` 的接力用 `relay_when_armed2.sh` 等 `t3qr3o2e` 起链，再起带同步（新暂存目录）的 `arm_after.sh`；那时仓库副本已是 1ff201ef，同步不会撞上别的接力。13:31 MST 挂上（`V2D_AFTER_SYNC_FROM=runs/stage/762ad7d0e370`），日志 `runs/logs/arm_after_t3qr3o2f_ml40.log`。
  预计：ml40 c 段约 17:30 MST 完，d 约 22:00，e 约 02:30，f 约 07:00（在 10:00 的截止线内）；mf4090 f 段约 05:00 完，之后空着。

## 5. 独立复核（11/03 13:4x MST）

结论 GO WITH FIXES，8 条全部采纳：

| # | 级别 | 问题 | 处理 |
|---|---|---|---|
| 1 | BLOCKER | 三段都带 `V2D_AFTER_SYNC_FROM` 现在挂上，第 1 段同步改了来历，后两段的接力会自己停 | 第 2、3 段用 `relay_when_armed.sh` 等前一段起链后再挂普通接力 |
| 2 | MAJOR | Tier 2 折算只乘导出那一局，一次抽签的运气能单独过 | 改成 min（两种变化），同 Tier 3 |
| 3 | MAJOR | 第 3 段接力等太久会超过默认 720 次；让卡会移走上一段日志 | 错开挂法后等待在 12 小时内；让卡后重挂下游接力 |
| 4 | MINOR | ml40 03:30 起、mf4090 05:00 起空着 | ml40 加同配方的 `t3qr3o2f`（ep20、ep6 1000 万臂），要先转参考，转不好就空着 |
| 5 | MINOR | 交过一次后“同样的门槛”永远过不了 | 第二次的门槛改成前两条加“两种变化都比已交的高” |
| 6 | MINOR | 排序规则与表不一致 | 改成 MP-SR ≥ 0.5 先排，再按 AUC 升序 |
| 7 | MINOR | `stage-remote` 要干净的提交、一个提交只暂存一次 | 先提交，再从同一提交暂存到三台 |
| 8 | NIT | ep5、10、14 的对照是 seed 43 | 换集比较用 `table_4096_t3m1029a.txt` 里 seed 43 的那一行 |
