# 交接：10/16 下午到 10/17 早上，两台服务器上自己跑的事（2026-10-16 15:2x MDT，分支 track2/p1-training）

用户 13:1x：“不要使用 mac 这边，mac 这边随时可能断网”“不需要推送”。下面这些都在服务器上用 tmux 或 setsid 跑，Mac 断网不影响；
记录落在各自服务器的 `results/`，Mac 联网后用 `scripts/dev/pull-results`（ml40 加 `V2D_ENV=ml40`）拉回再提交（只提交，不推送）。

## mf4090（来历 4fff7bd，今天不能再整体同步：t3ps 的 arm_after 要求来历不变；新文件可用 push-new-files）

| 时间（MDT，估） | 事 | 看哪里 |
|---|---|---|
| 13:32 起 | t3pk：k-fix 参考上重训 ep0（15:58 训完）、ep18（约 18:15）、ep29（约 20:20）（tmux v2d-t3pk-train / eval / export） | `runs/logs/t3pk_{train,eval}_mf4090.log`、`runs/logs/cand_t3_t3pk_mf4090.log` |
| 约 20:50 | t3pk 评测结束 → `run_after_log.sh` 自动跑判据 5 读数 | `results/t3kfix/retrain_switch_t3pk_mf4090.txt`（最后一行 `RETRAIN_SWITCH_DONE <换> <不判>`） |
| t3pk 全部做完、卡空后 | `runs/tools/arm_after.sh` 自动起 t3ps：方块桌面重训 ep20 | `runs/logs/arm_after_t3ps_mf4090.log`（最后一行 `ARM_AFTER_ARMED` 或 `ARM_AFTER_STOPPED <原因>`） |
| 约 23:15 | t3ps 评测结束 → 自动读数 | `results/t3kfix/retrain_switch_t3ps_mf4090.txt` |

- 计划与判据：`agent-doc/plan-t3-kfix-retrain-2026-10-16.md`（独立复核 GO WITH FIXES，已改）。门槛写死在 `stages/evaluate/retrain_switch_t3{pk,ps}.json`。
- t3pk 有一条失败或发散，arm_after 不起 t3ps（安全方向），次日手动处理。

## ml40（来历 4e58a15，链在跑，今晚不再整体同步）

- P2 已判“没用”（`results/r3o/verdict_P2_ml40.txt`），r3o 两档都停。
- t1c（接触标记提前，ep25、28、11、1）：独立复核 GO WITH FIXES（已改），16:49 起链（来历 4e58a15，tmux v2d-t1c-train / eval / export），
  约 10/17 01:30 训完；评测链结束后由 `run_after_log.sh` 自动跑 `r3o_verdict.py C1`（无对照：修好 ≥ 1 集有用），记录 `results/t1diag/verdict_C1_ml40.txt`，
  等待日志 `runs/logs/after_verdict_C1_ml40.log`。起链前实测：同一策略对 tier1 与 tier1_c10 评出来一致（`results/t1diag/eval_pair_c10_ep25_ml40.txt`）。
  ml40 今晚也不能再整体同步（链在跑）。
  计划 `agent-doc/plan-t1-contact-anticipation-2026-10-16.md`；参考在 `runs/motion/tier1_c10/`（只改了 hand_contact_active，`results/t1diag/c10_relabel_ml40.txt`）。

## 明早要做

1. 拉回两台的 results，看三份读数：t3pk、t3ps 的判据 5，t1c 的 C1 总判。
2. 判据 6：ep24、ep26（现有策略已判换）加 t3pk 判“换”的集，够 3 集就打包预演（`agent-doc/plan-t3-kfix-2026-10-16.md` 的收尾清单），交不交由 rxzhou 定。
3. ep20：t3ps 判“换”就有了合规且不掉分的版本，换不换由 rxzhou 定（10/12 定过 Tier 3 不用官方 support_surface/）。
4. t1c 有用：给修好的集补 seed 43，并把同样的改法用到 Tier 2 的跟丢集；没用：另写计划。
5. 另一位用户的 gb3 交付：先量每集参考变了多少（`stages/evaluate/ref_pair_diff.py`），变化大的才重训。

## 今天已经知道的（都有记录）

- k-fix 重导：两道核对都过；ep24、ep26 判换，ep0、ep18、ep29 跟丢；崩不崩看参考变化大小（`results/t3kfix/ref_pair_diff_ep{0,24}_mf4090.txt`）。
- gb3 主机位与 k-fix 物体位置、人体参数逐位相同，朝向最多差 0.33°（`results/t3kfix/kfix_vs_gb3_world_ml40_1016.txt`）。
- Tier 1 跟丢集：接触后 9–32 帧丢；接触后 30 帧物体自转中位 16.4°（其余 1.0°）（`results/t1diag/contact_window_mf4090.txt`）。

## 18:5x 更新

- 榜（`results/submission/leaderboard_1016_1850.txt`）：FF 10/16 09:18 交了新的 Tier 2，MPPE 14.31296，**Tier 2 MPPE 第一丢了**（我们 15.32195）；其余三项 Tier 2 仍是第一。FF 14:55 又交 Tier 1，MPPE 8.03204。
- 计划 `agent-doc/plan-c10-extend-2026-10-16.md`（第 2 版，独立复核 GO WITH FIXES 已改）：
  - 路 A（ml40）已挂：t1c 结束、C1 总判是“有用”或“看不清”时自动起 t1c2（Tier 1 ep9、ep2，同 t1c 配方），日志 `runs/logs/arm_after_t1c2_ml40.log`，最后一行 `ARM_AFTER_ARMED` 或 `ARM_AFTER_STOPPED <原因>`；总判“没用”时停在前置命令，属正常。
  - 路 B（mf4090）：t3ps 的链结束后整体同步 mf4090，生成 tier2_c5（Tier 2 ep25、9、1，提前 5 帧、补 15 帧，参数只由 Tier 2 的数据定），核对后起 t2m。要 Mac 在线；Mac 断了就明早做（步骤见计划 3.2 与本节下一条）。
  - 路 B 的手工步骤（Mac，仓库根）：`scripts/dev/record ops/sync_mf4090_<时间> scripts/dev/remote` → mf4090 容器里 `contact_relabel.py --src runs/motion/tier2 --dst runs/motion/tier2_c5 --meta-src runs/motion_src/tier2 --meta-dst runs/motion_src/tier2_c5 --lead 5 --gap 15 <三个序列>`（三集都要打印出支撑面文件名）→ `check_inputs.py` → `fc_config_check.sh stages/policy/queues/mf4090_t2m_smoke.txt stages/policy/queues/mf4090_t2m.txt` → `V2D_ARM_DRYRUN=1 stages/policy/arm_var_chain.sh t2m` → `stages/policy/arm_var_chain.sh t2m`。
- 新发现（明天写计划）：Tier 2 的 ep28、ep4 在参考里物体动了很久都没有接触标记（`results/t2diag/motion_before_contact_t2_ml40.txt`），这是 Tier 2 MPPE 贡献最大的两集。
- 另一位成员的 gb3：世界坐标系转换 54 条成功，汇总一步失败（11:13），之后没有新文件（`results/ops/t3_gb3_chain_ml40_1016_1845.txt`）。
- SOP 页 18:45 版已发布（只本地提交，未推送）。
