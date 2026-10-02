# 计划：8c778f9 评测运行时的兼容性验证 + 方盒三条两档重训（2026-10-01，第 1 版，待 Fable 5.1 审查）

- 分支 `track2/p1-training`；时间一律 UTC-6；服务器日志是北京时间（UTC+8），比 UTC-6 早 14 小时。
- 用户 10/1 的要求原文：“验证：我们用 v0.4.0 训出的 checkpoint，能不能直接在 8c778f9 的评测器里加载。接下来：ep1、ep7、ep28 在 Tier 1、Tier 2 各训一条，
  共 6 条，排在 Tier 2 这一批之后，开跑前照例先写计划、过 review。”同一条消息贴了两条规矩（第 5 节）。
- 顺序：事实 → 本计划与代码 → Fable 5.1 审代码与计划 → 按审查修改 → 登记提交 → 往服务器只加新文件（链在跑，不整体同步）→ 服务器上自动执行。

## 1. 为什么做

1. **提交要 30 条 episode 全有轨迹。** 官方打包器缺一条就整份拒绝（`tools/pack_submission.py:274`）。现在两档都凑不齐：
   - Tier 1 有 27 条可用 policy；ep1 的最终 policy 含 NaN，ep28 被看守停在 6000 万步，ep7 只有冒烟。三条都是在 v0.4.0 的错误几何
     （带 scale 的方盒建成 1 m 实心立方体）上训的。
   - Tier 2 第 1 批 27 条正在跑，方盒三条当时没排。

   所以方盒 6 条在第一份完整提交的关键路径上。
2. **评测运行时换了。** 组委会 10/1 的新 kit 把评测运行时钉在 8c778f9（决定记录 `agent-doc/decision-organizer-q1-q3-2026-10-01.md`）。
   我们已有和正在训的 54 份 policy（两档各 27 份）都是 v0.4.0 训的，先要实测它们能在 8c778f9 里加载、导出、打包，否则要重训。

## 2. 事实（10/1 17:00–19:30 实测；结果文件在括号里）

1. **v0.4.0（33129dd）→ 8c778f9**：6 个提交（#180–#185），flash_chord 下改了 11 个文件；依赖与镜像文件（pyproject、uv.lock、requirements、
   Dockerfile）改动 0 个。`src/` 下评测目录以外只改了两个文件：`scene/support.py`（#185），以及 `training/flash_sac/evaluation.py`。
   后者的全部改动是一行 import 写法，加一个默认为 None 的字段 `object_trajectories_output`（`results/submission/eval_runtime_facts.txt` 第 1 节）。
2. **kit 自带的评测入口**：新 kit 的 `flash_chord/` 只有 `scripts/evaluate_policy.py` 与三份 Hydra 配置，四个文件与 8c778f9 的同名文件逐字节相同。
   kit 说明要求自己装一个“带排行榜轨迹导出”的 FlashCHORD 运行时（同上第 2 节）。
3. **评测器怎样加载**：8c778f9 的 `harness.py:377–378` 先读 checkpoint 元数据、取出保存的配置，`:312` 再加载权重。
   这几处在 v0.4.0 → 8c778f9 的 diff 里没有改动（diff 只有新增的导出与来历代码），`use_checkpoint_config: true`（同上第 3 节）。
   推论（没跑过）：v0.4.0 训练写出的 checkpoint，与 8c778f9 训练会写出的格式相同；加载代码也没变，应当能加载。第 3 节就是去实测它。
4. **评分代码**：录制轨迹的 kernel 与原有指标的算法都没改；8c778f9 只新增了两个指标（`relative_position_error_cm`、`mean_per_point_error_cm`）。
   评测本身不逐位可复现：同一 checkpoint 在 4096 世界下评两次，ADD-AUC 差 −0.0028，MP-SR 与 SP-SR 各差 −0.013，MPPE 差 +0.29 cm
   （`agent-doc/experiments/2026-09-28-day2.md`）。
5. **几何**：#185 只改方盒（Cube）的导入；圆柱和只有地面的 27 条序列，两个运行时建出来的场景相同。
6. **kit 的导出与打包规矩**（`results/submission/eval_runtime_facts.txt` 第 4 节）：
   - kit 的批量导出脚本默认 1 个世界、`reset_mode=explicit`、关 W&B；`config/tracks.json` 里 Track 2 三档都是每条 episode 1 个世界、`private_fraction 0`；
   - 样例提交 22,989 行、30 条 episode、只有世界 0；
   - 打包器拒收 `environment_valid=false` 的世界；各条 episode 的 `eval_script_sha256`、`eval_code_sha256` 必须相同（“One submission is one evaluator build”）；
   - Track 2 的位姿换算：用第 0 帧求一个刚体变换，把评测器记下的参考对到“这一档发布的输入”上，要求每一帧都在 1 mm、1e-3 rad 以内（`pack_submission.py:78–79, 99, 118`）；
   - 输入不是发布的那份时要加 `--frame-references`。我们 Tier 2 用 v5.4 降噪后的参考训练，与发布的带噪输入差几厘米，不加这个参数打包必然报错；
   - 打包器对三档都按干净参考算一遍本地分数并打印（`locally computed`）。
7. **在哪跑打包**：kit 在 `.gitignore` 里，同步不到服务器。镜像里有 Python 3.11.15、numpy 2.4.6、pyarrow 24、trimesh 4.12.2，没有 pandas；
   两台服务器都没有 uv。mf4090 宿主机的 python3 是 3.10，带 pyarrow 25 与 numpy 2.2.6。
   所以服务器只负责用 GPU 导出轨迹（每条 episode 1 个世界，几百 KB）；打包在 Mac 上用 uv 跑。Kaggle token 也在 Mac 上。
8. **方盒三条**（`results/t2/support_kinds_tier2_*.txt`、`agent-doc/experiments/2026-09-30-divergence.md`）：
   - ep1 vacuum（椅背 Cube×1）、ep7 iron（桌面 Cube×1）、ep28 squeegee（两块板 Cube×2）。三个支撑面文件两档 md5 相同（f2fb02c8…、c413ad52…、a93e92e5…）；
   - #185 几何下：ep7 冒烟 8 个种子 0 发散（v0.4.0 几何 5 / 8）；ep1、ep28 截到 6000 万步各一条，全部有限；
   - Tier 1 参考（按标注尺寸算，即 #185 的几何）：ep28 刮水器有 239、209 帧的顶点从两块 2 cm 板另一侧穿出；ep1 吸尘器 385 / 747 帧低于地面超过 5 mm。
     ep17、ep22 的穿地程度与 ep1 相近，两条都训完没事；
   - Tier 2 参考（v5.4）：重定向对齐检查里 ep7 熨斗比桌面低 20.7 mm（ALIGN），桌面板厚 1 cm。按 #185 几何的逐帧穿透还没量，见第 7 节第 3 步。
9. **旧目录**：
   - mf4090：`t1-ep1-w2048-cap4m-mf4090` 有 DONE，最终 policy 含 NaN；`t1-ep28-…` 没有 DONE，留着两份含 NaN 的 state；另有两条冒烟目录；
   - ml40：`t1-ep7-w2048-cap10m-ml40` 是空目录，`smoke-t1-ep7-…` 有 DONE。
   同名重训时，链会把有 DONE 的跳过、把留有 state 的续训，所以新 run 名加 `-p185`，旧目录不动（它们是发散排查的证据）。
10. **链的进度**（10/1 17:25 UTC-6）：
    - mf4090 B 段 ep17 16:58 开训，还剩 6 条，预计 10/2 05:00–06:00 训完、06:40 前评完；
    - ml40 B 段 ep16 16:00 开训，还剩 7 条，预计 10/2 07:30–10:30 评完；之后 C 段（ep10 补跑）约 2.5 小时，10:00–13:00 评完。
11. **同步的限制**：训练链每条 run 前核 `.v2d-source-commit`，变了就停（`day2_train_chain.sh:37`）。所以链跑完之前不能 `scripts/dev/remote`。
    新文件只能单独放上去：用 rsync，先写临时文件再改名，只放新路径，不碰链正在用的脚本。先例是 C 段的期望表，10/1 用 scp 放上去并核了 md5。
12. **磁盘**：mf4090 可用 9892 MB；每份源码副本约 414 MB。

## 3. 兼容性验证（GPU 部分在 Tier 2 第 1 批之后自动跑）

### 3.1 8c778f9 运行时副本

- Mac：`tools/make_fc_patch.sh` 从 GitHub 取两版的 11 个文件，生成三样东西：
  - `third_party/patches/flash_chord-v0.4.0-to-8c778f9.patch`；
  - 清单 `flash_chord-8c778f9.sha256`；
  - `flash_chord-8c778f9.eval.json`：8c778f9 的 `eval_code_sha256`（按 `harness.evaluation_code_sha256` 的算法）与 `evaluate_policy.py` 的 sha256。
  `support.py` 打完补丁的 sha256（8d82f600…）与现有 #185 副本相同。
- 服务器：`stages/policy/make_fc_src_8c778f9.sh <目录>` 做法同 `make_patched_fc_src.sh`：复制 third_party 的 v0.4.0 flash_chord、打补丁、写 `SOURCE_V2D.txt`，
  再用 `stages/policy/fc_src_check.py` 核对。核对四项：
  - 对照的 third_party 在 33129dd 且已跟踪文件干净；
  - 副本有 `SOURCE_V2D.txt`；
  - 副本与 v0.4.0 不同的文件正好是清单里的 11 个；
  - 每个文件的 sha256 都对。
  核不过就删掉 `SOURCE_V2D.txt`（in-flash-chord 不认没有它的副本）。
- 位置：mf4090 `~/v2d/fc_src/fc_8c778f9`，ml40 `/lab_data/rxzhou/v2d/fc_src/fc_8c778f9`。
- 镜像沿用 `flash_chord:latest`，依据是事实 1：依赖文件没有改动。

### 3.2 导出与核对的脚本

- `stages/evaluate/fc_export.sh <run> <步数>`：命令与 kit 的 `examples/run_policy_evaluation.py` 逐项同序，在 8c778f9 副本的运行时根目录里跑它自己的
  `scripts/evaluate_policy.py`，这份与 kit 自带的逐字节相同。参数：
  - 默认 1 个世界；`V2D_EXPORT_TRAJ=0` 时只写 metrics JSON，4096 世界比对用；
  - 输出 `runs/flash_chord/<run>/export_8c778f9/s<步数>_w<世界数>/episode_<6 位>.{json,parquet}`。打包器按文件名认 episode：我们的 parquet 路径里没有 `episode_` 字样，评测器记不下序号。
  - 退出码：
    - 2：V2D_FC_SRC 不是 8c778f9 副本，或 run 名的档位与 run 记录里 parquet 的档位不一致；
    - 6：GPU 有别的进程；
    - 12：规矩一，含 NaN 的 policy 不导出，不起容器；
    - 13：评测器报 must disable task failure termination，是规矩二的触发条件；
    - 3：其他失败。
- `stages/evaluate/check_export.py <run> <步数> <世界数>`：在服务器宿主机上跑，核结构与来历（判据 P2、P3），并只报不判两样：
  评测器记下的参考与 motion parquet 的物体位姿差；主要指标。

### 3.3 GPU 上的验证清单（`stages/evaluate/compat/<机器>.tsv`，驱动 `stages/evaluate/compat_8c778f9.sh`）

| 机器 | 类型 | run | 用途 |
|---|---|---|---|
| mf4090 | export | `t1-ep8-…-mf4090` | 只有地面、Tier 1 通过 |
| mf4090 | export | `t1-ep6-…-mf4090` | 圆柱支撑面、Tier 1 通过 |
| mf4090 | export | `t2-ep2-…-mf4090` | Tier 2 第 1 批 A 段第一条 |
| mf4090 | eval（4096 世界） | `t1-ep6-…-mf4090` | 与 v0.4.0 评测器的 `eval_349999104_w4096.json` 比 |
| mf4090 | guard | `t1-ep1-…-mf4090` | 最终 policy 含 5892 个 NaN；期望退出码 12 |
| mf4090 | negctl | 同上 | 关掉守卫导出；期望评测器报错（13 / 3），或导出成功但核对不过 |
| ml40 | export | `t1-ep12-…-ml40`、`t2-ep0-…-ml40` | 这台的副本与 1000 万 buffer 训出的 checkpoint |

GPU 用时：mf4090 约 15 分钟（4096 世界评测约 5 分钟，其余每行 1–2 分钟，主要是 JIT 编译），ml40 约 5 分钟。

### 3.4 Mac 上的打包核对（CPU，导出拉回后做，不挡方盒训练）

- **E6，Tier 1**：用官方打包器，配一份只列 ep6、ep8 的 `tracks.json`（`--config` 是打包器自带的参数，不改源码），`--dataset-root` 指向从 mf4090
  拷到 Mac 的 Tier 1 `data/`、`meta/` 与这两条的网格。要求退出码 0，刚体换算的残差在打包器自己的容差内。交叉核对的那一行照录，只报不判。
- **E7，Tier 2**（不读 Tier 1）：直接调用打包器里的 `convert_track2_frame` 与 `input_frame_reference`，即打包器对每条 Track 2 episode 做的那一步：
  - 正向：评测器参考为 t2-ep2 的导出，帧参考为我们按 kit 格式写的 v5.4 npz（`coordinate_frame=released_track2_world`、`frame_index`、xyzw 的 `pose_xyzw [T,1,7]`）。
    npz 由 `runs/recovery/tier2_v54` 生成，生成脚本带 `tier_guard`。要求通过。
  - 反向对照：帧参考换成发布的 Tier 2 带噪输入，要求报“不是一个刚体变换”。
  - 帧网格取 Tier 2 的可见帧：可见性两档相同，不必读 Tier 1。
- E6、E7 的三个脚本（`pack_compat_tier1.sh`、`make_frame_references.py`、`frame_conversion_check.py`）在审查期间写，执行前补进第 6 节。

### 3.5 判据（执行前登记）

- **P1 加载**：每个 export 行评测器退出码 0，写出 metrics JSON 与轨迹 parquet。
- **P2 结构**：
  - schema `flash_chord_object_trajectories_v1`、米、xyzw；
  - 世界数对、物体刚体 1 个、起始帧 0；
  - 步数等于源帧数，行数等于步数 × 世界数，`reference_frame = step`；
  - `environment_valid` 全真，位姿全有限；
  - JSON 的 `non_finite_worlds` 为空。
- **P3 来历**：`checkpoint_sha256` 等于 policy 文件的 sha256；`eval_code_sha256`、`eval_script_sha256` 等于 3.1 节算出的 8c778f9 值。
- **P4 一致**：同一 checkpoint 两个评测器 4096 世界的结果，同一 sha256、|ΔADD-AUC| < 0.005、chord_sr |z| < 3（与 Day 2 恒等覆盖核对同一道闸）。
  其余指标只报。
- **N1、N2 对照**：守卫拦下含 NaN 的 policy（12）；关掉守卫时不出一份能通过核对的导出。
- **P5 Tier 1 打包**、**P6 Tier 2 换算**：见 3.4 节。

结论怎么下：

| 情况 | 结论与动作 |
|---|---|
| P1–P3 两台都过 | “v0.4.0 训出的 checkpoint 能在 8c778f9 里加载、导出”。54 份 policy 继续当候选，提交一律用 8c778f9 副本导出 |
| P1 不过 | 停，按报错分析；可能要在 8c778f9 上重训，另写计划。方盒训练链不开（3.6 节的门槛） |
| P4 不过 | 已有的 4096 世界判定不能直接沿用到 8c778f9，提交前候选要在 8c778f9 下重评，另写计划。不挡方盒训练 |
| P5 不过 | 我们重定向链路里物体的坐标系与发布的坐标系不是一个刚体变换，两档都交不了，另写计划 |
| P6 不过 | 修 frame-reference 的生成，只挡 Tier 2 |
| N1 / N2 不过 | 修守卫，修好之前不做任何提交导出 |

### 3.6 门槛：方盒训练链挂在 P1–P3 上

`compat_8c778f9.sh` 结束时写门槛文件 `runs/logs/compat_<机器>.gate`，内容是一行 `DAY2_TRAIN_DONE（完成 <export 通过数>、失败 <不过数>、跳过 0、发散 0）`。
方盒训练链用现成的 `chain_after.sh`（不改），把门槛文件当“上一段训练日志”，把 compat 日志当“上一段评测日志”，门槛设成 export 的行数
（mf4090 为 3，ml40 为 2）。这样 export 全过才开方盒训练。

理由：方盒用 #185 补丁副本训，训练代码是 v0.4.0 的。如果 8c778f9 加载不了 v0.4.0 的 checkpoint，方盒也该改在 8c778f9 上训；这时先停、等人看，
比白训 6 条（约 13 GPU 小时）划算。eval、guard、negctl 三类不进门槛：它们管的是已有结果能否沿用、守卫灵不灵，与方盒怎么训无关。

## 4. 方盒 6 条

### 4.1 分配

| 机器 | 顺序 | 预计 |
|---|---|---|
| mf4090（400 万 buffer） | t1-ep1、t1-ep7、t1-ep28、t2-ep28 | 约 06:40 开始 compat，06:55 起训，四条约 9 小时，10/2 16:00 前后评完 |
| ml40（1000 万 buffer） | t2-ep1、t2-ep7 | C 段评完后 compat 约 5 分钟，两条约 4.8 小时，10/2 15:00–18:00 评完 |

一台三条的分法（mf4090 只跑 Tier 1）要到 10/2 18:30 前后才全部评完。4 + 2 两台差不多同时结束，这 6 条之后才能做第一份完整提交，早结束有用。
两档混在一台上没有问题：链按 run 名前缀断言档位与参考目录（`precheck_expect.sh`）。

### 4.2 配方与队列

- 官方 G1 FlashSAC，逐帧回放，2048 世界，349,999,104 步，种子 42；支撑面开着（方盒）。mf4090 加 `training.replay.capacity=4000000`。
- 队列由 `make_batch_queue.py --box185` 生成（本版新增），命名 `stages/policy/queues/{mf4090,ml40}_box{.expect.tsv,_smoke.txt,.txt}`：
  - run 名 `t<档位>-ep<N>-w2048-{cap4m|cap10m}-p185-<机器>`，冒烟加 `smoke-`；
  - 正式行 `V2D_WANDB_TAG=box185 V2D_KEEP_STATES=1 V2D_MAX_RETRY=0 V2D_GPU_APPS=1 V2D_WANDB_UPLOAD_CKPT=0`，冒烟行同第 1 批；
  - 只接受 ep1、ep7、ep28，Tier 2 另按 Tier 2 的支撑面清单核；
  - 队列行里不写 `V2D_FC_SRC`，由链的环境给。
- 帧数：Tier 1 取 `results/day2/sequence_stats_tier1.txt`，Tier 2 取 `results/batch_summary_v040_t2v54.tsv` 的 Tier 2 行，生成脚本两档各读各的。
  三条都是 747、896、988。

### 4.3 运行时

- **训练**挂 #185 补丁副本：链的环境 `V2D_ALLOW_FC_SRC=1 V2D_FC_SRC=<p185 副本>`。
  - ml40 用已有的 `/lab_data/rxzhou/v2d/fc_src/v040_p185`；mf4090 用 `make_patched_fc_src.sh ~/v2d/fc_src/v040_p185` 新生成；
  - 两份都用 `fc_src_check.py` 加清单 `third_party/patches/flash_chord-p185.sha256` 核，与 v0.4.0 只差 `support.py`；
  - 训练代码与其余 54 条相同，#185 几何的发散证据也是在这份副本上取得的（事实 8）。
- **冒烟的不动基线**（256 世界 diag_rollout）在训练链里跑，同样挂 p185 副本。p185 的评测代码与 v0.4.0 相同，和此前所有冒烟一样。
- **评测**：评测链的环境 `V2D_FC_SRC=<8c778f9 副本>`。只评最终 checkpoint（`V2D_EVAL_STEPS=349999104`），4096 世界，判定与排行榜同一个运行时。
- **挂载核对**：fc_run 的运行记录只记 third_party 的提交，看不出挂了哪份副本。每条 run 训完后数 `runs/logs/<run>.log` 里的挂载行，
  必须至少一行、且全部指向 p185 副本。评测记录头里的挂载行必须指向 8c778f9 副本。

### 4.4 自动编排（不依赖 Mac 在线）

每台三个 tmux，都在等待状态下起好。mf4090 在 `~/v2d/maniphys_lab_v2d_challenge` 下：

```
tmux new-session -d -s v2d-compat -c "$PWD" 'V2D_FC_SRC=$HOME/v2d/fc_src/fc_8c778f9 V2D_WAIT_FOR_EVAL_LOG=runs/logs/t2b_eval_mf4090.log stages/evaluate/compat_8c778f9.sh stages/evaluate/compat/mf4090.tsv compat_mf4090'
tmux new-session -d -s v2d-box -c "$PWD" 'V2D_ALLOW_FC_SRC=1 V2D_FC_SRC=$HOME/v2d/fc_src/v040_p185 V2D_PRUNE_SMOKE_STATE=1 V2D_MIN_FREE_MB=1200 stages/policy/chain_after.sh runs/logs/compat_mf4090.gate runs/logs/compat_mf4090.log 3 stages/policy/queues/mf4090_box.expect.tsv stages/policy/queues/mf4090_box_smoke.txt stages/policy/queues/mf4090_box.txt 24564 box_train_mf4090'
tmux new-session -d -s v2d-box-eval -c "$PWD" 'V2D_FC_SRC=$HOME/v2d/fc_src/fc_8c778f9 V2D_EVAL_STEPS=349999104 V2D_WAIT_FOR_LOG=runs/logs/box_train_mf4090.log stages/evaluate/day2_eval_chain.sh stages/policy/queues/mf4090_box.expect.tsv - box_eval_mf4090'
```

ml40 在 `/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge` 下：compat 等 `runs/logs/t2c_eval_ml40.log`，清单 `compat/ml40.tsv`，门槛 2，冒烟显存上限 44000，
不设 `V2D_PRUNE_SMOKE_STATE` 与 `V2D_MIN_FREE_MB`。副本路径换成 `/lab_data/rxzhou/v2d/fc_src/…`。

链之间怎么接：

| 情形 | 结果 |
|---|---|
| Tier 2 评测链结束（DONE 或 FAILED） | compat 开始 |
| compat 结束 | 写门槛，日志最后一行 DAY2_EVAL_DONE / FAILED |
| export 全过 | `chain_after.sh` 开方盒训练链 |
| export 没全过 | 方盒训练日志写 DAY2_TRAIN_FAILED，方盒评测链空跑结束，GPU 空着等人看 |

方盒训练链自己还有三道检查：GPU 检查、磁盘守卫、`check_src`。

### 4.5 判据（执行前登记，与 Tier 2 第 1 批相同的部分不重复）

- **冒烟通过**：第 1 批各项，加两项发散判据，加“rollout 帧数等于源帧数”。显存上限 mf4090 24564 MiB、ml40 44000 MiB。不过的，正式训练记 SKIPPED。
- **正式训练的结局**：完成 / 发散（看守止损或 NONFINITE）/ 失败 / 跳过 / 显存不足，都不人工续训。
- **能进候选**：
  - 完成，最终 checkpoint 有 8c778f9 下的 4096 世界评测，step_count 等于源帧数，non_finite_worlds 为空；
  - 结果头的来历不带 -dirty / -syncing；
  - 挂载核对通过（4.3 节）。
  满足的，`policy_349999104` 是这条 episode 当前的候选。
- **质量只报数**：
  - Day 1 判据：chord_sr > 0、maniptrans_sr > 0、ADD-AUC 高于这条序列这一档参考的不动基线（`batch_verdict.py --steps 349999104`）；
  - 另报 SP-SR、MPPE。Tier 2 的数对照 Tier 2 v5.4 参考，不和 Tier 1 比。
- **事先登记的预期**（只描述，不作判据）：
  - t1-ep28 的参考穿过两块板，若不通过，先归到参考几何；
  - t2-ep7 的参考比桌面低 20.7 mm，同样处理；
  - t1-ep1 的穿地与 ep17、ep22 同级。
  发散方面，#185 几何下 8 + 2 条对照全部有限，满 3.5 亿步没跑过，靠看守兜底。

### 4.6 净室

- Tier 2 的两条 run 只读 `runs/motion/tier2` 的参考（v5.4）、Tier 2 支撑面拷贝与 Tier 2 网格；队列生成对 Tier 2 行只读 Tier 2 的表。
- 重训这三条的依据是支撑面文件与导入器代码（v0.4.0 不读 scale），配方是官方配方。
- “#185 几何下不发散”出自 Tier 1 ep7 的冒烟对照，是 Tier 1 实验得出的。拿它决定“Tier 2 也用 #185 训”属解读：这个决定并不依赖它，
  官方评测运行时本来就是 8c778f9，训练几何与评测几何一致。

### 4.7 磁盘

- mf4090 现在 9892 MB。B 段剩 6 条约 2.2 GB；两份副本约 0.83 GB；compat 导出不到 10 MB（4096 世界那行不写轨迹）；方盒 4 条约 1.5 GB（冒烟 state 删、正式只留一份 state）。
  跑完约剩 5.4 GB，守卫 1200 MB 足够。
- ml40 剩 1.9 TB。

## 5. 提交的两条规矩（用户 10/1 采纳，原文）

- 规矩一：“含 NaN 的 policy 不拿去导出，训练链今天起已经会自动拦下；”
  - 训练链：看守止损、`NONFINITE`、评测链不评（10/1 上线）；
  - 导出：`fc_export.sh` 守卫，退出码 12，不起容器。
- 规矩二：“提交时某条 episode 如果报这个错，就退到同一条 run 里更早的一份正常 checkpoint。”
  - `fc_export.sh` 把这个错认成退出码 13；
  - 往前退的逻辑写进提交流程（另写计划）：按步数从最终 checkpoint 往前，跳过非有限的，第一份导出成功且核对通过的就用；
  - 记下用的是哪一步。这是唯一允许不用最终 checkpoint 的情形。
- 顺带登记一个解读，待用户确认（属解读，不是官方原文）：
  - 官方打包器对 Tier 2 / Tier 3 也读干净参考，用它核帧、算本地分数。官方原文：“Local scores use the clean reference”。
  - 打包是官方的提交步骤，照做；但 Tier 2 / Tier 3 的本地分数是 Tier 1 派生的数，按净室规矩不拿来做任何 Tier 2 / Tier 3 的选择。
  - 提交流程里 Tier 2 / Tier 3 打包时把 `locally computed` 那一行滤掉、不落盘。本计划的 E7 只调换算函数，不跑完整打包器，不读 Tier 1。

## 6. 代码清单

| 文件 | 改动 | 测试 |
|---|---|---|
| `tools/make_fc_patch.sh` | 新：生成 8c778f9 补丁、清单、评测摘要 | 已跑，11 个文件；`support.py` 与 #185 副本 sha256 相同 |
| `third_party/patches/flash_chord-v0.4.0-to-8c778f9.patch`、`flash_chord-8c778f9.sha256`、`flash_chord-8c778f9.eval.json`、`flash_chord-p185.sha256` | 新 | 补丁能否打上：服务器上生成副本时 dry-run 加 fc_src_check |
| `stages/evaluate/eval_runtime_facts.sh` | 新：第 2 节的事实摘录 | 已跑，登记后落盘 |
| `stages/policy/make_fc_src_8c778f9.sh` | 新 | 服务器上实跑 |
| `stages/policy/fc_src_check.py` | 新 | `test_fc_src_check.py`（待写） |
| `stages/evaluate/fc_export.sh` | 新 | `test_fc_export.py` 5 项，Mac 上全过 |
| `stages/evaluate/check_export.py` | 新 | `test_check_export.py`（待写，uv 带 pyarrow） |
| `stages/evaluate/compat_8c778f9.sh`、`compat_expect.sh`、`compat/{mf4090,ml40}.tsv` | 新 | `test_compat_8c778f9.py`（待写：全过、export 不过、副本核不过、等待；门槛文件接真的 `chain_after.sh`） |
| `stages/policy/make_batch_queue.py` | 加 `--box185`（只在 Mac 上用） | `test_make_batch_queue.py`：原 4 项不变，加 2 项，全过 |
| 挂载核对、Tier 2 方盒参考的穿透、E6 / E7 三个脚本 | 待写 | — |

## 7. 执行步骤

1. Mac：按审查改代码与计划；全部测试在 Mac 上过；生成两份方盒队列，提交、推送。
   ```
   python3 stages/policy/make_batch_queue.py --box185 mf4090 box agent-doc/plan-box6-and-eval-runtime-2026-10-01.md t1:1 t1:7 t1:28 t2:28
   python3 stages/policy/make_batch_queue.py --box185 ml40 box agent-doc/plan-box6-and-eval-runtime-2026-10-01.md t2:1 t2:7
   ```
   落盘 `scripts/dev/record submission/eval_runtime_facts stages/evaluate/eval_runtime_facts.sh`。
2. 放文件：两台先确认这些路径都不存在，再从仓库根 `rsync -a --relative <新文件…> <机器>:<仓库>/`；之后逐个比 md5，落盘 `results/box/deploy_<机器>.txt`。
   不碰链正在用的任何文件，`.v2d-source-commit` 不变。
3. 服务器 CPU 步骤（不占 GPU，可以与链并行）：
   - 生成副本：mf4090 两份（p185、8c778f9），ml40 一份（8c778f9）。每份 `fc_src_check.py` 落盘，ml40 已有的 p185 副本也核一遍；
   - 两台对方盒队列跑 `fc_config_check.sh` 与 `precheck_expect.sh`，要 PRECHECK_OK；
   - Tier 2 方盒参考按 #185 几何算穿透：三条序列的 parquet、网格、Tier 2 支撑面拷到 `runs/diag/box_refs_t2/` 下，在容器里跑 `support_penetration.py`，落盘。
4. 起 4.4 节的 tmux（每台三个），确认三个都在等，长链标记都在。
5. 之后只做短查询。compat 跑完后：
   - Mac 拉回结果与导出（每份几百 KB）；
   - 跑 E6、E7，记执行记录 `agent-doc/experiments/2026-10-02-box6-eval-runtime.md`；
   - 承重结论过 jev。
   方盒评完后用 `batch_verdict.py --steps 349999104` 判定，挂载核对一并落盘。

## 8. 不做的事

- 不改配方、超参、种子，不人工续训，不改参考。
- 不碰正在跑的 Tier 2 链与它们用的脚本；链跑完前不整体同步。
- 不往 Kaggle 交任何东西：本计划只验证到打包为止，第一份提交另写计划。
- 不删旧目录（第 1 批 v0.4.0 几何的发散证据）。
- 不用 Tier 2 / Tier 3 的本地分数（第 5 节）。

## 审查与处理

（待填）
