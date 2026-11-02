# Tier 1：跟丢集试抓握闭合项权重 20，ep17 朝向项换种子（t1night，2026-11-01 夜，第 2 版）

日期 2026-11-01，分支 `track2/p1-training`。档位：只动 Tier 1。决定的来历：rxzhou 11/01 21:4x MST 定"今晚一夜别闲着，安排训练策略然后开始训练"。
相关计划：`plan-t1fill`（`t1hr2` 读数、`t1zs2` 在跑）、`plan-t1hard`（fc20、`-r3o-nv-` 的来历）、`plan-t12night` 第 3 节（换集规则 (a)–(c)）。

## 1. 事实

1. **`t1hr2` 读数**（ml40，20:46 MST 导出完；训练完成 2、评测成功 2、导出成功 2，nanwatch 非有限 0；4096 世界，对清单的基础配方 1000 万，`results/t1night/compare_t1hr2_mac.txt`）：
   - ep26 `-r3o-nv-`：AUC 0.492 → 0.569、SP-SR 0.946 → 1.000、MP-SR 0.956 → 1.000、MPPE 2.729 → 2.684 cm。四项都更好，但规则 (c) 要 MPPE 低 ≥ 0.5 cm，(a)、(b) 的 SR 升幅也不够，**按规则不换**。
   - ep23 `-r3o-nv-`：MP-SR 0.975 → 0.000、AUC 0.711 → 0.501，不换。
   - 按 `plan-t1fill` 第 3 节，0/2 换入：`-r3o-nv-` 不铺到 ep12。
2. **Tier 1 榜**（19:20 MST，`results/board/lb_1101_1920.txt`）：AUC 第 11（0.617；第 10 Team OPS 0.630）、SP-SR 第 7、MP-SR 第 10、MPPE 第 8（9.57 cm；第 7 domoarigato 7.78 cm）。
   提交门槛（`agent-doc/strategy-2026-10-19.md` 第 1 节）：AUC 期望领先 0.010、SR 领先 2 集、MPPE 领先 1.0 cm。
3. **MPPE 集中在四个跟丢集**。t1x1101 加 ep24、8、6 那份的导出那一局 MPPE 9.491 cm，合计 284.7 cm，其中 ep4 90.2、ep25 52.6、ep9 40.7、ep1 34.7，合计 218.2 cm（`results/t1list/t1x1101_ep24_8_6.txt`）。
   带门槛越过第 7 名要到 6.78 cm 以下：从这份未交的打包算合计约降 81 cm，从榜上的 9.575 cm（t1x1101）算约降 84 cm；不带门槛也要降约 51 cm（从榜上算约 54 cm）。
4. **这四集已有的 run**（4096 世界，SP、MP 都是 0）：
   - ep4：基础 1000 万 MPPE 109.9（清单这条），400 万 r3o 114.6，1000 万 r3a 123.2，pt08 127.3。没有试过 fc20。
   - ep9：400 万 fc20 **28.6**（AUC 0.197），基础 1000 万 40.5（清单，AUC 0.201），pt08 47.1，r3a 54.6。fc20 降 MPPE 约 30%，AUC 只低 0.004；按规则 (c)（要 AUC 升 0.03）没换。
   - ep25：pt05 56.4、pt08 68.7（清单）、fc20 117.9、基础 114.1。fc20 在 ep25 上没效果。
   - ep1：1000 万 r3a-c10 38.9（清单）、r3a 43.0、400 万 p185 45.6、r3o 49.2。没有试过 fc20，也没有基础配方 1000 万的 run。
5. **ep17 与 ep26 的朝向项**：ep17 `-r3o-nv-` seed 42 已换入（SP-SR 0 → 0.932，MP-SR 仍是 0，AUC 0.349 → 0.523）；`plan-t1hard` 记过"ep17 再换一颗种子"，没有排。
   ep26 见第 1 条。同集换种子差得多的例子：ep2 r3a-c10 seed 42 AUC 0.594、seed 43 0.422；ep11、ep19 也各差 0.02–0.15。
6. **卡**：ml40 20:46 MST 起空闲（显存 0，没有链标记）。mf4090 `t1zs2` 在跑（ep26 训到 75%，之后 ep12），约 11/02 00:30 导出完；可用磁盘 23 GB。
   ml40 每条 1000 万约 2.4 小时（含冒烟、评测、导出），mf4090 每条 400 万约 2.5 小时。冻结 11/04 15:00 MST。

## 2. 做法

| 段 | 机器 | 集 | 改动（只差这一项） | 对照（第 3 节的换集规则对清单里同集的 run） | 预计导出完（MST） |
|---|---|---|---|---|---|
| `t1hg` | ml40 | ep4、ep9 | 基础配方，`objective.force_closure_weight` 5 → 20（`-fc20-`），1000 万，seed 42 | 清单的基础 1000 万（同机同配方） | 约 03:00 |
| `t1hg_s43` | ml40 | ep4 | 1000 万 fc20 换 seed 43 | 清单的基础 1000 万 | 约 05:30 |
| `t1hr_s43` | ml40 | ep17 | `-r3o-nv-` 换 seed 43 | 清单的 `t1-ep17-w2048-cap10m-r3o-nv-ml40` | 约 08:00 |
| `t1hf2` | mf4090 | ep1、ep4 | 基础配方加 fc20，400 万，seed 42 | 清单 run（ep1 是 r3a-c10，配方不同） | 约 05:30 |
| `t1hf2_s43` | mf4090 | ep9 | 400 万 fc20 换 seed 43 | 清单的基础 1000 万 | 约 08:00 |

- ep4 是 MPPE 最大的一集，也是今晚唯一够大的杠杆：ml40 上 1000 万试两颗种子，mf4090 上试 400 万。ep25 上 fc20 没效果，不排。
- 第 1 版第三格是 `t1hr2_s43`（ep26 朝向项换种子），复核指出它换入后 AUC 至多加 0.0026、够不上 AUC 门槛，改成 `t1hg_s43`；`t1hr2_s43` 的队列已生成、提交，不起。
- 生成器：`make_var_queue.py` 加 `t1hg`（ml40）、`t1hf2`（mf4090，episodes 含 9 供换种子），种子段走已有的种子路径。
  `test_make_var_queue.py` 加 `test_t1night_fc20`，全过（`results/t1night/test_make_var_queue_mac.txt`）。队列生成记录 `results/t1night/gen_queues_mac.txt`、`gen_queue_t1hg_s43_mac.txt`；逐行与清单 run 的行比过，只多 fc20 或种子两项，另有 `V2D_KEEP_STATES=1`（对照的 1000 万基础行没有；`fc_run.sh` 里它只管保不保留 state 文件，不影响训练）。
- `arm_var_chain.sh` 加 `t1hg*`（ml40，`NOVAR=1`，排在 `t1h*` 前面）；`t1hf*`、`t1hr*` 已覆盖种子段。
- 起链：提交后 ml40 普通同步（没有链在跑），跑三段的 `fc_config_check.sh` 与 `precheck_expect.sh`（`t1hr*` 用 oo 副本的 `V2D_FC_SRC`），起 `t1hg`；
  `t1hg_s43` 用 `V2D_AFTER_INDEPENDENT=1 arm_after.sh t1hg_s43 …t1hg… 2` 接在 `t1hg` 后面，`t1hr_s43` 用 `relay_when_armed.sh` 等 `t1hg_s43` 起链后再接（`arm_after.sh t1hr_s43 …t1hg_s43… 1`）。
  mf4090 有链在跑，不直接同步：`scripts/dev/stage-remote` 暂存，干跑 `stage_sync.sh` 没有删除项后，`arm_after.sh t1hf2 …t1zs2… 2` 带 `V2D_AFTER_SYNC_FROM` 与 `V2D_POST_SYNC_CMD`（两段的配置核对与预检）；
  `t1hf2_s43` 用 `relay_when_armed.sh` 接在 `t1hf2` 后面（`arm_after.sh t1hf2_s43 …t1hf2… 2`）。各接力的输出进 `runs/logs/arm_after_<段>_<机器>.log`。
  起之前核两台 `runs/tools/` 的 `arm_after.sh`、`stage_sync.sh`、`relay_when_armed.sh` 与仓库（或暂存树）md5 相同。

## 3. 判据（先登记，结果出来之前）

- 健康与规则 (a)–(c) 同 `plan-t12night` 第 3 节，逐集、4096 世界、对清单里同集的 run。导出那一局只报，不用来选 run。
- **新增规则 (d)，只用于跟丢集**：清单 run 与新 run 在 4096 世界的 SP-SR、MP-SR 都 ≤ 0.05 时，新 run 的 MPPE 低 ≥ 3 cm 且低 ≥ 10%、AUC 不低 0.01 以上，换入；同一集多条满足时取 MPPE 低的。
  - (d) 只认登记之后导出的 run。登记前看过的 run 单凭它不换：ep9 的 400 万 fc20 seed 42（第 1 节第 4 条）要 `t1hg` 的 ep9 或 `t1hf2_s43` 至少一条也满足 (d)，ep9 才换，三条里取 MPPE 最低的；
    ep25 pt05（`results/t1fill/compare_ep25_pt05_mac.txt`，MPPE 低 12.3 cm、18%）按字面满足 (d)，但登记前已看过、今晚没有排确认的 run，不换。
- **新增规则 (e)，所有集**：AUC 高 ≥ 0.03，SP-SR、MP-SR 都不低，MPPE 不高，换入（四项都不差时 (c) 的 MPPE 门槛不再拦）。
  这条对 `t1zs2`（结果还没出来）与本计划各段都生效。ep26 seed 42 `-r3o-nv-` 在登记前已经看过，单凭它不换；`t1zs2` 的 ep26（400 万 r3o）也满足 (c) 或 (e)，ep26 才换（(a)、(b) 对 ep26 达不到），
  候选集合是 {ep26 `-r3o-nv-` seed 42、`t1zs2` 的 ep26}，按 MP-SR、再按 MPPE 取一条。
- (d)、(e) 不回溯到其它登记前看过的 run。
- 每段读数后算两份打包的导出那一局：t1x1101 加新换入的集、规则清单加新换入的集，两份都报。
- 提交条件不变：按 Kaggle 同分规则至少一个 Tier 1 榜前进一名，四项期望都不比 t1x1101 差，且期望领先够第 1 节第 2 条的门槛，才问 rxzhou；Tier 1 每次上传都要 rxzhou 明确同意。
- 预计：MPPE 榜带门槛要降约 81–84 cm，ep9 换入只降约 12 cm（4096 世界），ep4 要再降约 70 cm 才够。今晚各段让 Tier 1 任一榜前进的可能性低，这一点照实报。

## 4. 风险

- fc20 一好一坏（ep9 好、ep25 无效），ep4、ep1 可能无效；无效就不换，只损卡时。
- 规则 (d) 让 MPPE 降、AUC 小降的 run 换入；AUC 每集最多低 0.01，30 集打包后 AUC 至多低约 0.0003 每集，不会让 AUC 榜退后（AUC 第 12 名 0.582 差得远）。
- 规则 (e) 是看过 ep26 seed 42 之后加的。为免事后改规则，看过的那条单凭它不换，要一条登记后出来的 run 也满足才换。
- mf4090 磁盘 23 GB，400 万段的冒烟判过后删 state（`V2D_PRUNE_SMOKE_STATE=1`、低于 1200 MB 就停），三条 run 够用。
- 两台约 11/02 08:00 跑完，留出 11/02 白天到 11/04 15:00 打包与再排一轮。

## 5. 独立复核与改动（11/01 22:1x MST，第 1 版 → 第 2 版）

| # | 级别 | 意见 | 处理 |
|---|---|---|---|
| 1 | MAJOR | (d) 按字面会让登记前看过的 ep25 pt05 换入 | 采纳：(d) 只认登记后导出的 run，ep25 pt05 写明不换 |
| 2 | MINOR | (e) 的 ep26 候选集合没写；(d)、(e) 不回溯要写明；`plan-t1fill` 执行记录要记 `t1zs2` 的判据多了 (e) | 采纳 |
| 3 | MINOR | ml40 第三格 ep26 换种子杠杆太小，MPPE 是今晚唯一够得着的榜，ep4 是唯一够大的一集 | 采纳：改成 `t1hg_s43`（ep4 1000 万 fc20 seed 43） |
| 4 | NIT | 81 / 51 cm 取自未交的打包；从榜上算是 84 / 54 cm，ep4 要降约 70 cm | 采纳 |
| 5 | NIT | 队列多 `V2D_KEEP_STATES=1`，没写 | 采纳，写明不影响训练 |
| 6 | NIT | 接力的条数参数、两台 `runs/tools/` 三个脚本的 md5 核对没写 | 采纳 |
| 7 | — | 档位合规：只动 Tier 1，确认 | — |

## 执行记录
- 11/01 22:0x MST：提交 fe618523，ml40 普通同步（预演没有删除项），仓库副本来历 fe618523a772。`t1hg`、`t1hg_s43` 配置核对用默认副本、`t1hr_s43` 用 oo 副本，都通过，fc20 与种子的改动都在核对输出里；
  三段 precheck 全过（`results/ml40/t1night/cfgcheck_*`、`precheck_*`）。`runs/tools/arm_after.sh` 与仓库 md5 相同（69413829…），`relay_when_armed.sh` 从仓库复制到 `runs/tools/`（ea77acde…）。
  22:05 MST `arm_var_chain.sh t1hg` 预演 DRYRUN_OK 后起链（ARMED）；`t1hg_s43` 接力 `V2D_AFTER_INDEPENDENT=1 arm_after.sh t1hg_s43 …t1hg… 2`（`runs/logs/arm_after_t1hg_s43_ml40.log`，第一行记下来历与队列 md5）。
  `t1hr_s43` 的等待进程第一次在 `relay_when_armed.sh` 复制到之前就跑了，报找不到脚本、没有挂上（`arm_after_t1hr_s43_ml40.try1.log`）；第二次把输出误重定向进 /dev/null，停掉这条自己的进程；
  22:10 MST 第三次挂上：`relay_when_armed.sh` 等 `arm_after_t1hg_s43` 起链后跑 `arm_after.sh t1hr_s43 …t1hg_s43… 1`（`V2D_RELAY_MAX_POLLS=1200`、`V2D_AFTER_MAX_POLLS=1200`），日志 `runs/logs/arm_after_t1hr_s43_ml40.log`。

- 11/01 22:14 MST：`scripts/dev/stage-remote` 暂存到 mf4090 的 `runs/stage/fe618523a772/`，五段队列都在；`runs/tools/` 的 `arm_after.sh`（69413829…）、`stage_sync.sh`（c7054abb…）、`relay_when_armed.sh`（ea77acde…）与暂存树 md5 相同。
  `V2D_DRYRUN=1 stage_sync.sh` 没有删除项，在跑的 `t1zs2` 的队列不在改动里（`runs/logs/stage_sync_dry_fe618523.log`）。
  `t1hf2` 接力：`V2D_AFTER_INDEPENDENT=1 V2D_AFTER_SYNC_FROM=runs/stage/fe618523a772 V2D_PRE_TIMEOUT_S=7200 arm_after.sh t1hf2 …t1zs2… 2`，后置命令跑 `t1hf2`、`t1hf2_s43` 的配置核对（默认副本）与两段 precheck，
  记进 `results/t1night/`（`runs/logs/arm_after_t1hf2_mf4090.log`，第一行记下来历 fe618523a772 与队列 md5）。`t1hf2_s43`：`relay_when_armed.sh` 等 `t1hf2` 起链后跑 `arm_after.sh t1hf2_s43 …t1hf2… 2`（`runs/logs/arm_after_t1hf2_s43_mf4090.log`）。
  不同步窗口：到 `t1hf2` 记 ARM_AFTER_ARMED（约 00:40 MST）为止，不对 mf4090 跑 `scripts/dev/remote`，看榜与站点的提交只推 git。
- 11/01 22:20 MST 看榜（`results/board/diff_1101_2220.txt`）：Rice RobotPI Lab 19:39 MST 重交 Tier 1，四项都变好，SP-SR 0.833 → 0.967 越过 maniphys.ai（Tier 1 SP-SR 第 7 → 第 8；同为 26/30 的 FF、domoarigato 都比我们先交）；
  其余三个 Tier 1 榜它本来就在前面，maniphys.ai 名次不变。nima arki 20:50 MST 重交 Tier 2，SP-SR 0.700 → 0.733 与 maniphys.ai 同分（我们 10/14 先交，Kaggle 规则仍第 4；官网规则按名字也仍在前），AUC、MP-SR 仍在后面，MPPE 同分重交。
  名次和：读法 B 68 → 69（Kaggle 规则第 5；官网规则第 4）；读法 A 16 不变（第 5）。
  决定：策略不变，不交。Tier 1 SP-SR 要回第 7 需要 27/30，即至少一个跟丢集（ep1、4、9、25）SP 成功，今晚各段都对着 MPPE、不会让这四集 SP 成功；Tier 2 SP-SR 同分时我们先交，不要重交 SP-SR 榜。
  两台都在跑本计划：ml40 `t1hg` 冒烟过、ep4 正式 22:19 MST 开始；mf4090 `t1zs2` ep12 51%，`t1hf2` 接力在等。
- 11/02 01:0x MST：mf4090 `t1zs2` 读完（读数与健康见 `plan-t1fill` 执行记录）。`t1hf2` 接力 11/01 23:46 MST 起链（ARM_AFTER_ARMED），后置配置核对通过、两段 precheck 全过（`results/t1night/cfgcheck_t1hf2_mf4090.txt`、`precheck_t1hf2*_mf4090.txt`），ep1 正式 23:55 MST 起。
  ep26：`t1zs2` 的 ep26 满足 (c)、(e)，第 3 节的条件成立，候选集合 {`-r3o-nv-` seed 42、`t1zs2` ep26} 两条都满足 (e)。
  按登记的同分序（先 MP-SR、再 MPPE）取 `-r3o-nv-` seed 42：MP-SR 0.9998 对 0.9966（4096 世界里差 13 个世界）。`t1zs2` 那条 AUC 高 0.27（0.840 对 0.569）、MPPE 低 1.81 cm（0.87 对 2.68）。
  按规则换入的是 `-r3o-nv-`。改取 `t1zs2` 是看过结果后改同分序，本计划不改；交哪一条由 rxzhou 定（待定）。
  导出那一局（`results/t1list/`，各报两种 ep26）：t1x1101 加 ep6、ep26 AUC 0.6223（r3o-nv）/ 0.6309（t1zs2），SP 26/30、MP 21/30，MPPE 9.571 / 9.512；
  规则清单加 ep26 AUC 0.6279 / 0.6364，SP 24/30、MP 20/30，MPPE 10.881 / 10.822；t1x1101 加 ep24、8、6、26 AUC 0.6355 / 0.6441，SP 26/30、MP 21/30，MPPE 9.492 / 9.432。
  Tier 1 AUC 榜第 10 名 Team OPS 0.630、第 9 名 Debajyoti Dasgupta 0.648：t1x1101 加 ep24、8、6、26（t1zs2）导出那一局高出第 10 名 0.014，到不了第 9；SP、MP 不变，MPPE 降 0.06 cm，过不了第 7 名。
- 11/02 01:04 MST 看榜（`results/board/diff_1102_0104.txt`）：只有 Kelly To the H 重交 Tier 2、Tier 3，都在 maniphys.ai 之后；12 个榜名次、B 69（Kaggle 第 5、官网第 4）、A 16（第 5）都不变。策略不变，不交。
  卡：ml40 `t1hg` ep4 训完（00:27 MST），ep9 正式 00:30 起、23%，约 02:40 训完后两集评测、导出；mf4090 `t1hf2` ep1 58%，约 01:50 训完后接 ep4。两条 nanwatch 都是非有限 0。
