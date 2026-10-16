# 交接：10/16 下午到 10/17 早上，两台服务器上自己跑的事（2026-10-16 15:2x MDT，分支 track2/p1-training）

用户 13:1x：“不要使用 mac 这边，mac 这边随时可能断网”“不需要推送”。下面这些都在服务器上用 tmux 或 setsid 跑，Mac 断网不影响；
记录落在各自服务器的 `results/`，Mac 联网后用 `scripts/dev/pull-results`（ml40 加 `V2D_ENV=ml40`）拉回再提交（只提交，不推送）。

## mf4090（来历 4fff7bd，今天不能再整体同步：t3ps 的 arm_after 要求来历不变；新文件可用 push-new-files）

| 时间（MDT，估） | 事 | 看哪里 |
|---|---|---|
| 13:32 起 | t3pk：k-fix 参考上重训 ep0、ep18、ep29（tmux v2d-t3pk-train / eval / export） | `runs/logs/t3pk_{train,eval}_mf4090.log`、`runs/logs/cand_t3_t3pk_mf4090.log` |
| 约 20:50 | t3pk 评测结束 → `run_after_log.sh` 自动跑判据 5 读数 | `results/t3kfix/retrain_switch_t3pk_mf4090.txt`（最后一行 `RETRAIN_SWITCH_DONE <换> <不判>`） |
| t3pk 全部做完、卡空后 | `runs/tools/arm_after.sh` 自动起 t3ps：方块桌面重训 ep20 | `runs/logs/arm_after_t3ps_mf4090.log`（最后一行 `ARM_AFTER_ARMED` 或 `ARM_AFTER_STOPPED <原因>`） |
| 约 23:15 | t3ps 评测结束 → 自动读数 | `results/t3kfix/retrain_switch_t3ps_mf4090.txt` |

- 计划与判据：`agent-doc/plan-t3-kfix-retrain-2026-10-16.md`（独立复核 GO WITH FIXES，已改）。门槛写死在 `stages/evaluate/retrain_switch_t3{pk,ps}.json`。
- t3pk 有一条失败或发散，arm_after 不起 t3ps（安全方向），次日手动处理。

## ml40（来历 cf38fcd）

- P2 已判“没用”（`results/r3o/verdict_P2_ml40.txt`），r3o 两档都停。
- t1c（接触标记提前，ep25、28、11、1）：配置核对、预演都过（DRYRUN_OK），等独立复核过了再起；起了之后约 10/17 02:00 训完，
  评测链结束后由 `run_after_log.sh` 自动跑 `r3o_verdict.py C1`（无对照：修好 ≥ 1 集有用），记录 `results/t1diag/verdict_C1_ml40.txt`。
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
