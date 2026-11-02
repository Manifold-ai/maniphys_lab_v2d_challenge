# Tier 1：跟丢集试抓握闭合项权重 20，两条朝向项 run 换种子（t1night，2026-11-01 夜）

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
   带门槛越过第 7 名要到 6.78 cm 以下，合计约降 81 cm；不带门槛也要降约 51 cm。
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
| `t1hr_s43` | ml40 | ep17 | `-r3o-nv-` 换 seed 43 | 清单的 `t1-ep17-w2048-cap10m-r3o-nv-ml40` | 约 05:30 |
| `t1hr2_s43` | ml40 | ep26 | `-r3o-nv-` 换 seed 43 | 清单的基础 1000 万 | 约 08:00 |
| `t1hf2` | mf4090 | ep1、ep4 | 基础配方加 fc20，400 万，seed 42 | 清单 run（ep1 是 r3a-c10，配方不同） | 约 05:30 |
| `t1hf2_s43` | mf4090 | ep9 | 400 万 fc20 换 seed 43 | 清单的基础 1000 万 | 约 08:00 |

- ep4 两台各试一种容量的 fc20，它是 MPPE 最大的一集。ep25 上 fc20 没效果，不排。
- 生成器：`make_var_queue.py` 加 `t1hg`（ml40）、`t1hf2`（mf4090，episodes 含 9 供换种子），种子段走已有的种子路径。
  `test_make_var_queue.py` 加 `test_t1night_fc20`，全过（`results/t1night/test_make_var_queue_mac.txt`）。队列生成记录 `results/t1night/gen_queues_mac.txt`；逐行与清单 run 的行比过，只多 fc20 或种子两项。
- `arm_var_chain.sh` 加 `t1hg*`（ml40，`NOVAR=1`，排在 `t1h*` 前面）；`t1hf*`、`t1hr*` 已覆盖种子段。
- 起链：提交后 ml40 普通同步（没有链在跑），跑三段的 `fc_config_check.sh` 与 `precheck_expect.sh`（`t1hr*` 用 oo 副本的 `V2D_FC_SRC`），起 `t1hg`；
  `t1hr_s43` 用 `V2D_AFTER_INDEPENDENT=1 arm_after.sh` 接在 `t1hg` 后面，`t1hr2_s43` 用 `relay_when_armed.sh` 等 `t1hr_s43` 起链后再接。
  mf4090 有链在跑，不直接同步：`scripts/dev/stage-remote` 暂存，干跑 `stage_sync.sh` 没有删除项后，`arm_after.sh t1hf2 …t1zs2… 2` 带 `V2D_AFTER_SYNC_FROM` 与 `V2D_POST_SYNC_CMD`（两段的配置核对与预检）；
  `t1hf2_s43` 用 `relay_when_armed.sh` 接在 `t1hf2` 后面。各接力的输出进 `runs/logs/arm_after_<段>_<机器>.log`。

## 3. 判据（先登记，结果出来之前）

- 健康与规则 (a)–(c) 同 `plan-t12night` 第 3 节，逐集、4096 世界、对清单里同集的 run。导出那一局只报，不用来选 run。
- **新增规则 (d)，只用于跟丢集**：清单 run 与新 run 在 4096 世界的 SP-SR、MP-SR 都 ≤ 0.05 时，新 run 的 MPPE 低 ≥ 3 cm 且低 ≥ 10%、AUC 不低 0.01 以上，换入；同一集多条满足时取 MPPE 低的。
  - ep9 的 400 万 fc20 seed 42（第 1 节第 4 条）在登记前已经看过，单凭它不换。`t1hg` 的 ep9 或 `t1hf2_s43` 至少一条也满足 (d)，ep9 才换，三条里取 MPPE 最低的。
- **新增规则 (e)，所有集**：AUC 高 ≥ 0.03，SP-SR、MP-SR 都不低，MPPE 不高，换入（四项都不差时 (c) 的 MPPE 门槛不再拦）。
  这条对 `t1zs2`（结果还没出来）与本计划各段都生效。ep26 seed 42 在登记前已经看过，单凭它不换；`t1hr2_s43` 或 `t1zs2` 的 ep26 也满足 (a)–(e) 之一，ep26 才换，按 MP-SR、再按 MPPE 取一条。
- 每段读数后算两份打包的导出那一局：t1x1101 加新换入的集、规则清单加新换入的集，两份都报。
- 提交条件不变：按 Kaggle 同分规则至少一个 Tier 1 榜前进一名，四项期望都不比 t1x1101 差，且期望领先够第 1 节第 2 条的门槛，才问 rxzhou；Tier 1 每次上传都要 rxzhou 明确同意。
- 预计：MPPE 榜带门槛要降约 81 cm，ep9 换入只降约 12 cm（4096 世界），ep4 要再降 60 cm 以上才够。今晚各段让 Tier 1 任一榜前进的可能性低，这一点照实报。

## 4. 风险

- fc20 一好一坏（ep9 好、ep25 无效），ep4、ep1 可能无效；无效就不换，只损卡时。
- 规则 (d) 让 MPPE 降、AUC 小降的 run 换入；AUC 每集最多低 0.01，30 集打包后 AUC 至多低约 0.0003 每集，不会让 AUC 榜退后（AUC 第 12 名 0.582 差得远）。
- 规则 (e) 是看过 ep26 seed 42 之后加的。为免事后改规则，看过的那条单凭它不换，要一条登记后出来的 run 也满足才换。
- mf4090 磁盘 23 GB，400 万段的冒烟判过后删 state（`V2D_PRUNE_SMOKE_STATE=1`、低于 1200 MB 就停），三条 run 够用。
- 两台约 11/02 08:00 跑完，留出 11/02 白天到 11/04 15:00 打包与再排一轮。
