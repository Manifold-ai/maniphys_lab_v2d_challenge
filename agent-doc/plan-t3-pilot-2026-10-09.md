# 计划：Tier 3 试跑 2 集（mf4090，2026-10-09，第 1 版）

用户 10/9：“进行 Tier 2 铺开和 Tier 3 试跑”。目的是确认同组同事的 CARI4D 重建产物（已落成 Tier 2 schema 的档目录）能走完我们这条链：
转换 → 重定向 → 训练（变体 A）→ 4096 世界评测 → 1 世界导出。只验证链路，不出提交，不评价重建精度，不读 Tier 1。时间一律 UTC−6。
Tier 2 铺开另见 `agent-doc/plan-t2-scaleout-2026-10-09.md`，两者分在两台机器上，互不影响。

## 1. 事实

- **产物**（`results/ops/t3_queue_ml40_1009_1335.txt`）：同事在 ml40 上的 `runs/tier3_cari4d`，部署版本 6820f70。队列 10/9 11:51 结束，
  29 集过了 CARI4D（ep6 没有结果），18 集进了这个目录，11 集没过剪影检查，在 `tier3_cari4d_suspect`。
- **选 ep8 与 ep24**（skinny_wood_chair push、watering_can pour）：
  - 两集都在 18 集里，两版剪影检查都过：ep8 可见 IoU 中位 0.80 / 0.82、深度因子中位 0.96 / 0.97；ep24 是 0.77 / 0.79、0.94 / 0.95
    （第一版 `runs/checks`、第二版 `runs/checks_v2`）。
  - 两集在 Tier 2 试验里都有变体 A 的 4096 世界评测（MP-SR 都是 0.999），可以比较同一条任务换成 Tier 3 参考后，跟踪是否变难。
  - 两集官方的支撑面都只有地面（`support_kinds.py`：`empty`，`results/ops/t3p_mf4090_inputs_1009.txt`），Tier 2 的基线与变体都带
    `scene.support=false`。试跑因此不用决定 Tier 3 的支撑面从哪来；要支撑面的集留到正式做时再定。
- **文件**（`results/ops/t3_episodes_ml40_1009.txt`，`tools/t3_episode_remote.sh`）：本用户可读。parquet 的 sha256：ep8 `0e0bd2e7…`、
  ep24 `efda4dc7…`。元数据的字段与 Tier 2 的 `episodes_metadata.jsonl` 相同，`mesh`、`ground_plane`、`support_surface` 是相对路径。
  重建时用的网格与地面文件，md5 与 mf4090 上官方 Tier 2 目录里的同名文件相同。
- **转换器。** `stages/retarget/challenge_to_soma.py` 能原样读这种档目录：同事 10/9 在 ep20 上用 `probe_rx_format.py` 验证过（77 关节、
  逐帧 flex、`poses.npy` 形状都对），只缺支撑面文件。`libs/v2d_infra/paths.py` 现在只有 Tier 1、Tier 2，要加一档。
- **规则解读（未确认）。** 同事的做法是 Tier 3 用 Tier 2 目录里的官方网格与地面平面，他的 README 标了“待向组委会确认”。试跑沿用，
  另从 Tier 2 目录取这两集的支撑面文件（内容是空的，训练时 `scene.support=false` 不加载）。试跑不提交；正式做 Tier 3 前要问清。
- **已知的重建问题。** 世界系按“exo 相机的 OpenCV 系就是发布的世界系”处理，尺度与倾角都没校正；进训练目录的 18 集，第一版检查的深度因子中位 0.94。
  这会影响计分，但计分要对照干净真值，本地算不了（算了就读了 Tier 1）。试跑只看链路与“跟着这份参考能不能做”。
- **机器**（`results/ops/machines_1009_1325.txt`、`results/ops/t3p_mf4090_inputs_1009.txt`）：mf4090 GPU 空闲，根分区可用 5594 MB；
  `robotic-grounding`、`flash_chord` 镜像与 `v040_p185_nfg`、`fc_8c778f9` 副本都在；还没有 `runs/motion/tier3`。

## 2. run

2 条：`t3-ep8-w2048-cap4m-r3a-mf4090`、`t3-ep24-w2048-cap4m-r3a-mf4090`，seed 42。配置与 Tier 1 在 mf4090 上的变体 A 补跑（r3x）相同：
官方 G1 配方 + 变体 A 两项 + `training.replay.capacity=4000000`（这张卡放不下 1000 万）+ `scene.support=false`；2048 个世界、3.5 亿步、逐帧回放；
训练挂 `v040_p185_nfg`，评测与导出用 `fc_8c778f9`；W&B 标签 `t3p`，不上传 checkpoint，`V2D_MAX_RETRY=0`。
与 Tier 2 同集变体 A 的差别不止参考：buffer 400 万对 1000 万、机器不同。比较只作参考。

## 3. 做法

1. **代码**（各带测试）：
   - `libs/v2d_infra/paths.py`：加 `TIER3 = runs/tier3/root`，`tier(3)` 返回它。注明这不是官方数据，是我们从 exo 视频重建后拼成的档目录。
   - `stages/recovery/tier3_pack_remote.sh`（经 stdin 在 ml40 上跑）：自己找同事的 tier3 目录（恰好一个，不写名字），把指定集的 parquet、
     元数据与 `code/DEPLOYED` 打成 tar 写到 stdout。
   - `stages/recovery/tier3_root.py`（mf4090 上跑，只用标准库）：开头调 `tier_guard.forbid_tier1()`；从 `runs/tier3/incoming/<标签>/`
     拼出 `runs/tier3/root`：`data/chunk-000/episode_*.parquet`、`meta/episodes_metadata.jsonl`，以及元数据里 `mesh`、`ground_plane`、
     `support_surface` 指向的文件（从官方 Tier 2 目录复制）。逐个文件打 sha256；同一集已存在且内容不同就拒绝。测试 `test_tier3_root.py`。
   - `stages/recovery/tier3_stage.sh`（Mac 上跑，只转发）：`ssh ml40 'bash -s -- <集>' < tier3_pack_remote.sh | ssh mf4090 'tar -x …'`，
     再在 mf4090 上跑 `tier3_root.py`，核对 parquet 的 sha256 与第 1 节的记录相同。
   - `make_var_queue.py` 的 t3p 清单：从 Tier 2 基线 `t2-ep8-w2048-cap10m-ml40`、`t2-ep24-w2048-cap10m-ml40` 派生（`baseline()` 同上），
     parquet 换成 `runs/motion/tier3/…`，加 400 万 buffer 与变体 A；写 `stages/policy/queues/mf4090_t3p{.expect.tsv,_smoke.txt,.txt}` 与
     `stages/evaluate/exports/cand_t3_t3p_mf4090.tsv`。
   - `arm_var_chain.sh t3p`：RTX 4090、`$HOME/v2d/fc_src`、冒烟显存上限 24564 MiB、可用空间 ≥ 2500 MB、档位 3、2 条；链的环境加
     `V2D_PRUNE_SMOKE_STATE=1 V2D_MIN_FREE_MB=1200`（同 r3x）。
2. **部署**：与 Tier 2 铺开一起提交、推送、同步。
3. **准备数据**（都经 record 落到 `results/t3p/`）：`tier3_stage.sh t3p_1009 8 24` → mf4090 上 `stages/retarget/one.sh 3 8`、`one.sh 3 24`
   （转换 → 重定向 → 对齐检查，结果行 `runs/logs/batch/t3_ep08.tsv`、`t3_ep24.tsv`）。
4. **起链**（mf4090）：`fc_config_check.sh` 展开 4 份配置 → `V2D_ARM_DRYRUN=1 arm_var_chain.sh t3p` → `arm_var_chain.sh t3p`。
   三个会话 `v2d-t3p-train`、`v2d-t3p-eval`、`v2d-t3p-export`，做法同 r3x。约 6 小时，10/10 凌晨结束。
5. **结束后**：训练健康记录，拉回评测与导出，写比较报告，向用户回报。

## 4. 判据（执行前登记）

| 编号 | 判据 |
|---|---|
| P1 数据 | 两集 parquet 的 sha256 与 `t3_episodes_ml40_1009.txt` 相同；`tier3_root.py` 复制的网格与地面 md5 与 `t3p_mf4090_inputs_1009.txt` 相同 |
| P2 转换与重定向 | `one.sh` 的状态不是 `FAIL:*`；帧数等于元数据（708、748）；左右手接触至少一侧非零（两侧都是 0 时 force_closure 恒为 0，这条不训） |
| R1–R3 | 同 Tier 2 铺开计划第 4 节（训练健康、4096 世界评测、导出） |

- P1、P2 不过的集不训，查原因，向用户回报。R1–R3 不过的照实记，不换参数重跑；基础设施原因可原样补跑一次。
- **只报**：对齐检查的间隙与支撑面、IK 残差中位、左右手接触帧数（与 Tier 2 同集并列）；4096 世界 MP-SR、SP-SR、ADD-AUC、MPPE、失败原因
  （对照各自的参考）与 Tier 2 同集变体 A 并列。这些只说明“跟着这份参考能不能做”，不代表 Tier 3 的计分。

## 5. 风险

- **同事的产物还在变。** 第二版剪影检查正在跑，以后可能重出轨迹。试跑用 10/9 的快照，sha256 与 `DEPLOYED` 记下；正式做时重拉。
- **对齐检查。** 尺度与倾角没校正，物体在静止段可能离地或穿地，`one.sh` 会记 `ALIGN`。只报，不拦；穿地太深时训练开头就会出问题，R1 会记下。
- **磁盘。** mf4090 只剩约 5.6 GB。2 条约 1 GB，起链要求 ≥ 2500 MB，训练链不到 1200 MB 就停。
- **档位隔离。** 拼档目录与转换只读 Tier 3 产物和 Tier 2 目录里的网格、地面、支撑面；`tier3_root.py` 开头禁读 Tier 1。

## 6. 产物

代码与测试；`results/t3p/` 下的转发、拼目录、重定向、配置展开、起链与健康记录；执行记录写在本计划末尾；jev 规格与结果。
