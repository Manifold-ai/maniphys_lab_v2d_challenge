# 计划：Tier 3 试跑 2 集（mf4090，2026-10-09，第 2 版）

第 1 版（c413099）经 Fable 5.1 独立审查（GO WITH FIXES，2 条 MAJOR），按意见改成本版，逐条处理见文末“审查与处理”。

用户 10/9：“进行 Tier 2 铺开和 Tier 3 试跑”。目的是确认同组同事的 CARI4D 重建产物（已落成 Tier 2 schema 的档目录）能走完我们这条链：
转换 → 重定向 → 训练（变体 A）→ 4096 世界评测 → 1 世界导出。只验证链路，不出提交，不评价重建精度，不读 Tier 1。时间一律 UTC−6。
Tier 2 铺开另见 `agent-doc/plan-t2-scaleout-2026-10-09.md`，两者分在两台机器上，互不影响。

## 1. 事实

- **产物**（`results/ops/t3_queue_ml40_1009_1335.txt`）：同事在 ml40 上的 `runs/tier3_cari4d`，部署版本 6820f70。队列 10/9 11:51 结束，
  29 集过了 CARI4D（ep6 没有结果）；按第一版剪影检查，18 集进了这个目录，11 集在 `tier3_cari4d_suspect`。他正在重跑第二版检查（ep26 已从不过变成过），
  这个划分以后会变。
- **选 ep8 与 ep24**（skinny_wood_chair push、watering_can pour）：
  - 两集都在 18 集里，两版剪影检查都过：ep8 可见 IoU 中位 0.80 / 0.82、深度因子中位 0.96 / 0.97；ep24 是 0.77 / 0.79、0.94 / 0.95
    （第一版 `runs/checks`、第二版 `runs/checks_v2`）。
  - 两集在 Tier 2 试验里都有变体 A 的 4096 世界评测（MP-SR 都是 0.999），可以比较同一条任务换成 Tier 3 参考后，跟踪是否变难。
  - 两集官方的支撑面都只有地面（`support_kinds.py`：`empty`，`results/ops/t3p_mf4090_inputs_1009.txt`），Tier 2 的基线与变体都带
    `scene.support=false`。试跑因此不用决定 Tier 3 的支撑面从哪来；要支撑面的集留到正式做时再定。
- **文件**（`results/ops/t3_episodes_ml40_1009.txt`，`tools/t3_episode_remote.sh`）：本用户可读。parquet 的 sha256：ep8 `0e0bd2e7…`、
  ep24 `efda4dc7…`。元数据的字段与 Tier 2 的 `episodes_metadata.jsonl` 相同（ep8 那一行逐字节相同），`mesh`、`ground_plane`、`support_surface`
  是相对路径。重建时用的网格与地面文件，md5 与 mf4090 上官方 Tier 2 目录里的同名文件相同。
- **转换器。** `stages/retarget/challenge_to_soma.py` 能原样读这种档目录：同事 10/9 在 ep20 上用 `probe_rx_format.py` 验证过（77 关节、
  逐帧 flex、`poses.npy` 形状都对），只缺支撑面文件。
- **规则解读（未确认）。** 同事的做法是 Tier 3 用 Tier 2 目录里的官方网格与地面平面，他的 README 标了“待向组委会确认”。试跑沿用，
  另从 Tier 2 目录取这两集的支撑面文件（内容是空的，训练时 `scene.support=false` 不加载）。试跑不提交；正式做 Tier 3 前要问清。
- **已知的重建问题。** 世界系按“exo 相机的 OpenCV 系就是发布的世界系”处理，尺度与倾角都没校正；进训练目录的 18 集，第一版检查的深度因子中位 0.94。
  这会影响计分，但计分要对照干净真值，本地算不了（算了就读了 Tier 1）。试跑只看链路与“跟着这份参考能不能做”。
- **机器**（`results/ops/machines_1009_1325.txt`、`results/ops/t3p_mf4090_inputs_1009.txt`）：mf4090 GPU 空闲，根分区可用 5594 MB；
  `robotic-grounding`、`flash_chord` 镜像与 `v040_p185_nfg`、`fc_8c778f9` 副本都在；还没有 `runs/motion/tier3`。r3x 在 mf4090 上每条 run
  约占 330 MB（`agent-doc/plan-t1-r3x-2026-10-08.md` 第 1 节与执行记录）。

## 2. run

2 条：`t3-ep8-w2048-cap4m-r3a-mf4090`、`t3-ep24-w2048-cap4m-r3a-mf4090`，seed 42。配置与 Tier 1 在 mf4090 上的变体 A 补跑（r3x）相同：
官方 G1 配方 + 变体 A 两项 + `training.replay.capacity=4000000`（这张卡放不下 1000 万）+ `scene.support=false`；2048 个世界、3.5 亿步、逐帧回放；
训练挂 `v040_p185_nfg`，评测与导出用 `fc_8c778f9`；W&B 标签 `t3p`，不上传 checkpoint，`V2D_MAX_RETRY=0`。
与 Tier 2 同集变体 A 的差别不止参考：buffer 400 万对 1000 万、机器不同。比较只作参考。

## 3. 做法

1. **代码**（各带测试）：
   - `libs/v2d_infra/paths.py`：加 `TIER3 = runs/tier3/root`，`tier(3)` 返回它。注明这不是官方数据，是我们从 exo 视频重建后拼成的档目录。
   - `stages/recovery/tier3_expect.py`（Mac）：从 `t3_episodes_ml40_1009.txt` 取 parquet 与元数据的 sha256、从 `t3p_mf4090_inputs_1009.txt` 取
     网格、地面与支撑面的 md5，写哈希表 `stages/recovery/expect/t3p_1009.tsv`（提交、同步）。测试 `test_tier3_expect.py`。
   - `stages/recovery/tier3_pack_remote.sh`（经 stdin 在 ml40 上跑）：自己找同事的 tier3 目录（恰好一个，不写名字），把指定集的 parquet、
     元数据与 `code/DEPLOYED` 打成 tar 写到 stdout。报错只用相对路径，tar 自己的 stderr 丢掉、只报退出码（审查 M2）。
   - `stages/recovery/tier3_root.py --expect <哈希表>`（mf4090，只用标准库）：开头调 `tier_guard.forbid_tier1()`；转来的 parquet 与元数据、
     要复制的官方 Tier 2 文件逐个比对哈希表，表里每行也都要用上，任何一处不符就什么也不写（审查 M1）；拼出 `runs/tier3/root`，
     并写 `meta/provenance.json`（每集的部署版本、哈希、哈希表路径）。同一集已存在且内容不同就拒绝。测试 `test_tier3_root.py`。
   - `stages/recovery/tier3_stage.sh`（Mac，只转发）：解到 `runs/tier3/incoming/<标签>.partial/`，失败就删，成功才改名（审查 m3）；
     在 mf4090 上只打部署版本的 40 位 commit（审查 M2），再跑 `tier3_root.py --expect stages/recovery/expect/<标签>.tsv`。
   - `stages/retarget/challenge_to_soma.py`：转 Tier 3 时把 `meta/provenance.json` 里这一集的来源写进 `v2d_meta.json` 的 `object_pose_source`
     （`kind: tier3_reconstruction`），缺来源就停（审查 m5）。测试加在 `test_challenge_to_soma.py`。
   - `make_var_queue.py t3p`：从 Tier 2 基线 `t2-ep8-w2048-cap10m-ml40`、`t2-ep24-w2048-cap10m-ml40` 派生，parquet 换成 `runs/motion/tier3/…`，
     加 400 万 buffer 与变体 A；写 `stages/policy/queues/mf4090_t3p{.expect.tsv,_smoke.txt,.txt}` 与 `stages/evaluate/exports/cand_t3_t3p_mf4090.tsv`。
   - `arm_var_chain.sh t3p`：RTX 4090、`$HOME/v2d/fc_src`、冒烟显存上限 24564 MiB、可用空间 ≥ 2500 MB；链的环境加
     `V2D_PRUNE_SMOKE_STATE=1 V2D_MIN_FREE_MB=1200`（同 r3x）与 `V2D_GPU_WAIT_S=21600`（同 Tier 2 铺开）。
2. **部署**：与 Tier 2 铺开一起提交、推送、同步。
3. **准备数据**（都经 record 落到 `results/t3p/`）：
   1. Mac 上 `scripts/dev/record t3p/stage_mf4090 stages/recovery/tier3_stage.sh t3p_1009 8 24`。
   2. mf4090 上在 tmux 里经 record 跑 `stages/retarget/one.sh 3 8`、`one.sh 3 24`（转换 → 重定向 → 对齐检查，结果行
      `runs/logs/batch/t3_ep08.tsv`、`t3_ep24.tsv`；放 tmux 是为了 Mac 断网时不留半截记录，审查 n8）。
4. **起链**（mf4090）：`fc_config_check.sh` 展开 4 份配置 → `V2D_ARM_DRYRUN=1 arm_var_chain.sh t3p` → `arm_var_chain.sh t3p`。
   三个会话 `v2d-t3p-train`、`v2d-t3p-eval`、`v2d-t3p-export`，做法同 r3x。约 6 小时。导出门结束前，mf4090 的根分区上不放别的东西。
5. **结束后**：训练健康记录，拉回评测与导出，写比较报告，向用户回报。

## 4. 判据（执行前登记）

| 编号 | 判据 |
|---|---|
| P1 数据 | `tier3_root.py --expect` 以 `TIER3_ROOT_OK` 结束（两集 parquet 与元数据的 sha256、六个 Tier 2 文件的 md5 都与哈希表相同，表里每行都用上） |
| P2 转换与重定向 | `one.sh` 的状态不是 `FAIL:*`；帧数等于元数据（708、748）；左右手接触至少一侧非零（两侧都是 0 时 force_closure 恒为 0，这条不训）；对齐检查的间隙不低于 −50 mm（物体穿进地面超过 5 cm 就停下问用户，不训） |
| R1–R3 | 同 Tier 2 铺开计划第 4 节（训练健康、4096 世界评测、导出） |
| 试跑结论 | 两条 run 都走到导出 `ok` 算通过（链路通了）。R1 不过的那条，评测与导出没有被验证到，结论里照实写“没验证” |

- P1、P2 不过的集不训，查原因，向用户回报。R1–R3 不过的照实记，不换参数重跑；基础设施原因可原样补跑一次。
- **只报**：对齐检查的间隙与支撑面、IK 残差中位、左右手接触帧数（与 Tier 2 同集并列）；4096 世界 MP-SR、SP-SR、ADD-AUC、MPPE、失败原因
  （对照各自的参考）与 Tier 2 同集变体 A 并列。这些只说明“跟着这份参考能不能做”，不代表 Tier 3 的计分。

## 5. 风险

- **同事的产物还在变。** 第二版剪影检查正在跑，以后可能重出轨迹。试跑用 10/9 的快照：哈希表把版本钉死，换了就拼不进来；`provenance.json` 与
  `v2d_meta.json` 记下部署版本。正式做时重拉、重出哈希表。
- **对齐。** 尺度与倾角没校正，物体在静止段可能离地或穿地，`one.sh` 会记 `ALIGN`（|间隙| ≥ 20 mm）。−50 mm 以内只报，更深就停（第 4 节）。
- **磁盘。** mf4090 只剩约 5.6 GB。2 条约 0.7 GB，起链要求 ≥ 2500 MB，训练链不到 1200 MB 就停。
- **别的检查脚本。** `stages/evaluate/case_clip.sh`、`ep7_ckpt_eval.sh` 只认 `t1-`、`t2-` 开头的 run，不在这条链里；以后要用它们看 Tier 3 的 run 得先改。
- **档位隔离。** 拼档目录与转换只读 Tier 3 产物和 Tier 2 目录里的网格、地面、支撑面；`tier3_root.py` 开头禁读 Tier 1；转换器只经 `tier(3)` 读 `runs/tier3/root`。

## 6. 产物

代码与测试；`stages/recovery/expect/t3p_1009.tsv`；`results/t3p/` 下的转发、拼目录、重定向、配置展开、起链与健康记录；执行记录写在本计划末尾；jev 规格与结果。

## 审查与处理（Fable 5.1，GO WITH FIXES）——第 2 版

| 编号 | 级别 | 意见 | 处理 |
|---|---|---|---|
| M1 | MAJOR | P1 靠人看记录：`tier3_stage.sh` 只打印 sha256，`tier3_root.py` 不比对 | 加 `tier3_expect.py` 生成哈希表，`tier3_root.py --expect` 逐个比对、不符就什么也不写，并写 `provenance.json`；测试覆盖 |
| M2 | MAJOR | 报错路径会带出别人的目录名：tar 的 stderr 没脱敏；mf4090 上整个打印 `DEPLOYED` | tar 的 stderr 丢掉、只报退出码，其余报错只用相对路径；`DEPLOYED` 只取 40 位 commit |
| m3 | MINOR | 转发失败会留下空目录，同一标签再转就被拒 | 先解到 `.partial`，失败就删，成功才改名 |
| m4 | MINOR | 没有试跑结论与穿地的停止线 | 第 4 节加“试跑结论”一行与 −50 mm 的停止线，R1 不过时写明评测、导出没验证 |
| m5 | MINOR | `v2d_meta.json` 看不出 Tier 3 参考的来源 | 转换器把 `provenance.json` 里这一集的来源写进 `object_pose_source` |
| n6 | NIT | 18 / 11 是第一版检查的划分，第二版会变 | 第 1 节写明 |
| n7 | NIT | `case_clip.sh`、`ep7_ckpt_eval.sh` 只认 t1、t2 | 第 5 节记下，这条链不用 |
| n8 | NIT | 磁盘要说明不放别的；`one.sh` 别在前台 ssh 里跑 | 第 3 节写明：导出门结束前根分区不放别的；`one.sh` 在 mf4090 的 tmux 里经 record 跑 |
| n9 | NIT | 档位隔离可以接受 | 不改 |

## 执行记录

- 10/9 14:48 第一次拼档目录（`results/t3p/stage_mf4090_run1.txt`）：`TIER3_ROOT_OK`，两集 parquet 与元数据的 sha256、六个 Tier 2 文件的 md5 都与
  哈希表 `stages/recovery/expect/t3p_1009.tsv` 相同（P1 过）。这时对方的 `DEPLOYED` 已是 f421235，不是 13:35 快照里的 6820f70：
  这两集的 parquet 是队列早先写的（北京时间 10/9 14:36、23:08），文件本身没变（哈希相同），变的只是对方之后部署的代码。
  `provenance.json` 原来把这个字段叫 `deployed_commit`，容易读成“写出这份 parquet 的版本”，改名为 `deployed_at_staging`，另记 parquet 在对方的修改时间。
- 14:49 删掉 mf4090 上的 `runs/tier3/root` 与 `runs/tier3/incoming/t3p_1009`，用 7aa1905 重拼（`results/t3p/stage_mf4090.txt`）：`TIER3_ROOT_OK`，
  ep8 parquet 修改时间 2026-10-09T06:36:25Z、ep24 15:08:36Z，转发时对方部署版本 f421235（干净）。记录里没有别人的名字。
- 14:50 mf4090 的 tmux `v2d-t3p-retarget` 里经 record 跑 `stages/retarget/eps.sh 3 8 24`（来历 9c31ba8）。
