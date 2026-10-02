# 计划：8c778f9 评测运行时的兼容性验证 + 方盒三条两档重训（2026-10-01，第 2 版：按 Fable 5.1 的计划与代码两份审查修改）

- 分支 `track2/p1-training`；时间一律 UTC-6；服务器日志是北京时间（UTC+8），比 UTC-6 早 14 小时。
- 用户 10/1 的要求原文：“验证：我们用 v0.4.0 训出的 checkpoint，能不能直接在 8c778f9 的评测器里加载。接下来：ep1、ep7、ep28 在 Tier 1、Tier 2 各训一条，
  共 6 条，排在 Tier 2 这一批之后，开跑前照例先写计划、过 review。”同一条消息贴了两条规矩（第 5 节）。
- 顺序：事实 → 计划与代码（第 1 版，6a3b0b1）→ Fable 5.1 审代码与计划（两份都是 GO WITH FIXES，没有 BLOCKER）→ 按审查修改（本版）→ 登记提交
  → 往服务器只加新文件（链在跑，不整体同步）→ 服务器上的 CPU 预检 → 起好等待中的 tmux → 自动执行。

## 1. 为什么做

1. **提交要 30 条 episode 全有轨迹。** 官方打包器缺一条就整份拒绝（`tools/pack_submission.py:274`）。现在两档都凑不齐：
   - Tier 1 有 27 条可用 policy；ep1 的最终 policy 含 NaN，ep28 被看守停在 6000 万步，ep7 只有冒烟。三条都是在 v0.4.0 的错误几何
     （带 scale 的方盒建成 1 m 实心立方体）上训的。
   - Tier 2 第 1 批 27 条正在跑，方盒三条当时没排。

   所以方盒 6 条在第一份完整提交的关键路径上。
2. **评测运行时换了。** 组委会 10/1 的新 kit 把评测运行时钉在 8c778f9（决定记录 `agent-doc/decision-organizer-q1-q3-2026-10-01.md`）。
   我们已有和正在训的 54 份 policy（两档各 27 份）都是 v0.4.0 训的，先要实测它们能在 8c778f9 里加载、导出、打包，否则要重训。

## 2. 事实（10/1 17:00–21:00 实测；结果文件在括号里）

1. **v0.4.0（33129dd）→ 8c778f9**：6 个提交（#180–#185），flash_chord 下改了 11 个文件；依赖与镜像文件（pyproject、uv.lock、requirements、
   Dockerfile）改动 0 个。`src/` 下评测目录以外只改了两个文件：`scene/support.py`（#185），以及 `training/flash_sac/evaluation.py`。
   后者的全部改动是一行 import 写法，加一个默认为 None 的字段 `object_trajectories_output`（`results/submission/eval_runtime_facts.txt` 第 1 节）。
2. **kit 自带的评测入口**：新 kit 的 `flash_chord/` 只有 `scripts/evaluate_policy.py` 与三份 Hydra 配置，四个文件与 8c778f9 的同名文件逐字节相同。
   kit 说明要求自己装一个“带排行榜轨迹导出”的 FlashCHORD 运行时（同上第 2 节）。
3. **评测器怎样加载**：8c778f9 的 `harness.py:377–378` 先读 checkpoint 元数据、取出保存的配置，`:312` 再加载权重。
   这几处在 v0.4.0 → 8c778f9 的 diff 里没有改动（diff 只有新增的导出与来历代码），`use_checkpoint_config: true`（同上第 3 节）。
   推论（没跑过）：v0.4.0 训练写出的 checkpoint，与 8c778f9 训练会写出的格式相同；加载代码也没变，应当能加载。第 3 节就是去实测它。
4. **评分代码**：录制轨迹的 kernel 与原有指标的算法都没改；8c778f9 只新增了两个指标（`relative_position_error_cm`、`mean_per_point_error_cm`）。
   v0.4.0 的评测配置默认就是 `reset_mode: explicit`，补丁只加了 `object_trajectories_output`，所以 4096 世界的比对是同样设置下的比较。
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
7. **帧号对得上**（代码事实，审查核过）：`challenge_to_soma.py` 的 `fill_invisible` 保留全部 T 帧，评测器的 `reference_frame = step`（起始帧 0），
   打包器只要可见帧，而可见帧是 0..T−1 的子集。所以帧号不需要换算。v5.4 的 npz 是 `[x,y,z,qw,qx,qy,qz]`，与发布数据同一约定，给 `--frame-references` 时换成 xyzw。
8. **在哪跑打包**：kit 在 `.gitignore` 里，同步不到服务器。镜像里有 Python 3.11.15、numpy 2.4.6、pyarrow 24、trimesh 4.12.2，没有 pandas；
   两台服务器都没有 uv。mf4090 宿主机的 python3 是 3.10，带 pyarrow 25 与 numpy 2.2.6；ml40 宿主机的 python3 没有 numpy（第 7 节第 3 步实测，
   `results/box/tests_ml40.txt`），所以 check_export 经 `stages/evaluate/check_export.sh` 在 ml40 上进容器跑。
   所以服务器只负责用 GPU 导出轨迹（每条 episode 1 个世界，几百 KB）；打包在 Mac 上用 uv 跑。Kaggle token 也在 Mac 上。
9. **方盒三条**（`results/t2/support_kinds_tier2_*.txt`、`agent-doc/experiments/2026-09-30-divergence.md`）：
   - ep1 vacuum（椅背 Cube×1）、ep7 iron（桌面 Cube×1）、ep28 squeegee（两块板 Cube×2）。三个支撑面文件两档 md5 相同（f2fb02c8…、c413ad52…、a93e92e5…）；
   - #185 几何下：ep7 冒烟 8 个种子 0 发散（v0.4.0 几何 5 / 8）；ep1、ep28 截到 6000 万步各一条，全部有限。这些对照都是在 ml40 的 p185 副本上跑的；
   - Tier 1 参考（按标注尺寸算，即 #185 的几何）：ep28 刮水器有 239、209 帧的顶点从两块 2 cm 板另一侧穿出；ep1 吸尘器 385 / 747 帧低于地面超过 5 mm。
     ep17、ep22 的穿地程度与 ep1 相近，两条都训完没事；
   - Tier 2 参考（v5.4）在 #185 几何下（`results/box/support_penetration_t2_mf4090.txt`，10/1 21:00 量）：ep1 吸尘器对椅背最深嵌入 10 mm，121 帧超过 5 mm，
     52 帧有顶点穿到板另一侧；ep7 熨斗对 1 cm 桌板最深 5 mm，123 帧有顶点穿到板另一侧（最多 289 个）；ep28 刮水器两块板各有 244、211 帧穿过，
     另有 160 帧低于地面超过 5 mm。
10. **旧目录**：
    - mf4090：`t1-ep1-w2048-cap4m-mf4090` 有 DONE，最终 policy 含 NaN；`t1-ep28-…` 没有 DONE，留着两份含 NaN 的 state；另有两条冒烟目录；
    - ml40：`t1-ep7-w2048-cap10m-ml40` 是空目录，`smoke-t1-ep7-…` 有 DONE。
    同名重训时，链会把有 DONE 的跳过、把留有 state 的续训，所以新 run 名加 `-p185`，旧目录不动（它们是发散排查的证据）。
11. **链的进度**（10/1 20:12 快照，`results/t2/status_{mf4090,ml40}_2000.txt`）：
    - mf4090 B 段在训第 4 条（ep19），预计 10/2 05:35 训完、06:15 评完；
    - ml40 B 段在训第 5 条（ep20），预计 07:25 训完、08:15 评完；之后 C 段（ep10 补跑）约 2.5 小时，约 10:45 结束。
12. **同步的限制**：训练链每条 run 前核 `.v2d-source-commit`，变了就停（`day2_train_chain.sh:37`）。所以链跑完之前不能 `scripts/dev/remote`。
    新文件只能单独放上去：用 rsync，先写临时文件再改名，只放新路径，不碰链正在用的脚本。审查核过：链调用的脚本自部署的 90a73fa 之后接口没变
    （只改过可执行位），新文件都不覆盖旧路径。先例是 C 段的期望表，10/1 用 scp 放上去并核了 md5。
13. **挂载行在哪**：in-flash-chord 挂副本时往 stderr 打一行。训练段的在 `runs/logs/<run>.log`（冒烟 `runs/logs/smoke-<run>.log`），
    `fc_eval.sh` 的在 `runs/logs/<run>.eval_<步数>_w<世界数>.log`；record 的结果文件里没有这一行。`fc_export.sh` 自己会把这一次的挂载行打到 stdout。
14. **磁盘**：mf4090 20:12 可用 9431 MB；每份源码副本约 414 MB。

## 3. 兼容性验证（GPU 部分在 Tier 2 第 1 批之后自动跑）

### 3.1 8c778f9 运行时副本

- Mac：`tools/make_fc_patch.sh` 从 GitHub 取两版的 11 个文件，生成补丁 `third_party/patches/flash_chord-v0.4.0-to-8c778f9.patch`、清单
  `flash_chord-8c778f9.sha256`，以及 `flash_chord-8c778f9.eval.json`：8c778f9 的 `eval_code_sha256`（按 `harness.evaluation_code_sha256` 的算法）与
  `evaluate_policy.py` 的 sha256。审查从 GitHub 取旧文件实打过一遍：11 个文件与上游 8c778f9 逐字节相同，两个摘要按原算法重算一致。
- 服务器：`stages/policy/make_fc_src_8c778f9.sh <目录>` 做法同 `make_patched_fc_src.sh`：复制 third_party 的 v0.4.0 flash_chord、打补丁、写 `SOURCE_V2D.txt`，
  再用 `stages/policy/fc_src_check.py` 核四项：对照的 third_party 在 33129dd 且已跟踪文件干净；副本有 `SOURCE_V2D.txt`；副本与 v0.4.0 不同的文件
  正好是清单里的 11 个；每个文件的 sha256 都对。任何一步失败都删掉整个目标目录。副本用过之后根下可能出现 `wandb/`、`.hydra/`，核对时不比、只报个数。
- 位置：mf4090 `~/v2d/fc_src/fc_8c778f9`，ml40 `/lab_data/rxzhou/v2d/fc_src/fc_8c778f9`。镜像沿用 `flash_chord:latest`，依据是事实 1。

### 3.2 导出与核对的脚本

- `stages/evaluate/fc_export.sh <run> <步数>`：命令与 kit 的 `examples/run_policy_evaluation.py` 逐项同序，在 8c778f9 副本的运行时根目录里跑它自己的
  `scripts/evaluate_policy.py`，这份与 kit 自带的逐字节相同。
  - 默认 1 个世界；`V2D_EXPORT_TRAJ=0` 只写 metrics JSON（4096 世界比对用）；`V2D_EXPORT_DRYRUN=1` 只做守卫、run 记录、`v2d_meta.json`、
    输出路径的核对并打印容器命令，不加锁、不查 GPU、不起容器、不写文件；
  - 输出 `runs/flash_chord/<run>/export_8c778f9/s<步数>_w<世界数>/episode_<6 位>.{json,parquet}`，打包器按文件名认 episode；
  - 退出码：2（副本不对、档位不一致、读不了元数据）、6（GPU 有别的进程）、12（规矩一：含 NaN 的 policy 不导出）、
    13（这一次追加的日志里有 must disable task failure termination，规矩二的触发条件）、3（其他失败）。摘要脚本出错不影响退出码。
- `stages/evaluate/check_export.py <run> <步数> <世界数>`：在服务器宿主机上跑，核结构与来历（判据 P2、P3），刚体数取自 motion parquet；
  只报不判两样：评测器记下的参考与 motion parquet 的物体位姿差（合成数据上 float32 舍入约 0.0001 mm、0.03°），以及主要指标。
- `stages/evaluate/frame_ref_check.py --tier 1|2`（新）：用 numpy 照 kit 的 `convert_track2_frame` 重写，在 CPU 上对全部 episode 算打包时的刚体换算残差：
  Tier 1 对发布的 Tier 1 输入，Tier 2 对 v5.4（只读 Tier 2 的文件，开 `tier_guard`）。评测器参考取 motion parquet 的物体位姿（事实 7、check_export 复核）。

### 3.3 GPU 上的验证清单（`stages/evaluate/compat/<机器>.tsv`，驱动 `stages/evaluate/compat_8c778f9.sh`）

| 机器 | 类型 | run | 世界数 | 用途 |
|---|---|---|---|---|
| mf4090 | export | `t1-ep8-…-mf4090` | 1 | 只有地面、Tier 1 通过 |
| mf4090 | export | `t1-ep6-…-mf4090` | 1 | 圆柱支撑面、Tier 1 通过 |
| mf4090 | export | `t2-ep2-…-mf4090` | 1 | Tier 2 第 1 批 A 段第一条 |
| mf4090 | export | `t1-ep8-…-mf4090` | 2 | 多世界的结构；世界 0 与世界 1 的差别（只报） |
| mf4090 | eval | `t1-ep6-…-mf4090` | 4096 | 与 v0.4.0 评测器的 `eval_349999104_w4096.json` 比 |
| mf4090 | guard | `t1-ep1-…-mf4090` | 1 | 最终 policy 含 5892 个 NaN；期望退出码 12 |
| mf4090 | negctl | 同上 | 1 | 关掉守卫导出；期望评测器报错（13 / 3），或导出成功但核对的最后一行是 EXPORT_FAIL |
| ml40 | export | `t1-ep12-…-ml40`、`t2-ep0-…-ml40` | 1 | 这台的副本与 1000 万 buffer 训出的 checkpoint |
| ml40 | eval | `t1-ep12-…-ml40` | 4096 | P4 覆盖 1000 万 buffer 与 L40S |

GPU 用时：mf4090 约 15 分钟，ml40 约 10 分钟。

### 3.4 打包相关的核对

- **P5′（CPU，今晚）**：`frame_ref_check.py --tier 1` 与 `--tier 2` 在 mf4090 上对 30 条各跑一遍，落盘。
- **E6（Mac，导出拉回后）**：官方打包器配一份只列 ep6、ep8 的 `tracks.json`（`--config` 是打包器自带的参数），数据放成
  `<根>/track_2/tier_1_multiview_caption/{data,meta,mesh}`（`v2dlb/dataset.py:21–27`），`--code-commit` 给本仓库某个提交的 URL。要求退出码 0、残差在容差内；
  交叉核对那一行照录、只报。
- **E7（Mac，不读 Tier 1）**：直接调用打包器里的 `convert_track2_frame` 与 `input_frame_reference`：正向用 t2-ep2 的导出加 v5.4 帧参考（npz，xyzw，`frame_index` 0..T−1），
  要求通过；反向对照换成发布的 Tier 2 带噪输入，要求报“不是一个刚体变换”。帧网格取 Tier 2 的可见帧。
- E6、E7 的脚本（`pack_compat_tier1.sh`、`make_frame_references.py`、`frame_conversion_check.py`）进提交流程计划，这一版不写；P5′ 已经回答“换算会不会挡住”。

### 3.5 判据（执行前登记）

- **P1 加载**：每个 export 行 `fc_export.sh` 退出码 0（评测器加载了 checkpoint，写出了 metrics JSON 与轨迹 parquet）。
- **P2 结构**：schema `flash_chord_object_trajectories_v1`、米、xyzw；世界数对、刚体数对、起始帧 0；步数等于源帧数，行数等于步数 × 世界数 × 刚体数，
  `reference_frame = step`；`environment_valid` 全真，位姿全有限；JSON 的 `non_finite_worlds` 为空。
- **P3 来历**：`checkpoint_sha256` 等于 policy 文件的 sha256；`eval_code_sha256`、`eval_script_sha256` 等于 3.1 节算出的 8c778f9 值。
- **P4 一致**：同一 checkpoint 两个评测器 4096 世界的结果，同一 sha256、|ΔADD-AUC| < 0.005、chord_sr |z| < 3（与 Day 2 恒等覆盖核对同一道闸）。
  0.005 不到已知重复噪声的 2 倍，所以 P4 不过时先用 8c778f9 再评一次，两次都不过才下结论。
- **N1、N2 对照**：守卫拦下含 NaN 的 policy（12）；关掉守卫时不出一份能通过核对的导出。
- **P5′**：30 条的残差都在 1 mm、1e-3 rad 以内（两档各自）。
- **只报**：1 个世界的指标与同一 checkpoint 4096 世界均值的差；2 个世界的导出里世界 0 与世界 1 的差（世界间本来就有差别，单世界提交是这个分布里的一个样本；
  重复导出也不会逐位相同，这会影响规矩二的回退：退一步之后的结果不能指望与之前那次逐位可比）。

| 情况 | 结论与动作 |
|---|---|
| P1–P3 两台都过 | “v0.4.0 训出的 checkpoint 能在 8c778f9 里加载、导出”。54 份 policy 继续当候选，提交一律用 8c778f9 副本导出 |
| P1 两台都不过 | 停，按报错分析；可能要在 8c778f9 上重训，另写计划。方盒训练链不开（3.6 节的门槛） |
| P1 只有一台不过 | 多半是那台的副本或环境，与 checkpoint 格式无关：那台的方盒链不开，另一台照常；查那台的副本与报错 |
| P2 不过（P1 过） | 导出格式或我们的核对有缺陷，属提交流程的问题；方盒训练照常，修好之前不做提交导出 |
| P3 不过（P1 过） | 副本与上游不一致，或摘要算法理解错了；方盒训练照常，修好之前不做提交导出 |
| P4 不过（重评一次仍不过） | 已有的 4096 世界判定不能直接沿用到 8c778f9，提交前候选要在 8c778f9 下重评，另写计划。不挡方盒训练 |
| P5′ 不过 | 看是哪档、哪几条：Tier 1 不过说明重定向链路里物体的坐标系与发布的不是一个刚体变换，两档都交不了，另写计划；只有 Tier 2 不过就修帧参考 |
| N1 / N2 不过 | 修守卫，修好之前不做任何提交导出 |

### 3.6 门槛：方盒训练链只挂在 P1 上

`compat_8c778f9.sh` 结束时写门槛文件 `runs/logs/compat_<机器>.gate`：清单里每个 export 行的 `fc_export.sh` 都退出码 0，写
`DAY2_TRAIN_DONE（完成 1、失败 0、跳过 0、发散 0）`，否则写“完成 0、失败 1”。方盒训练链用现成的 `chain_after.sh`（不改），把门槛文件当
“上一段训练日志”，把 compat 日志当“上一段评测日志”，门槛 1。check_export、eval、guard、negctl 不进门槛：不过的照样记 COMPAT_FAIL，人来看。

理由：方盒用 #185 补丁副本训，训练代码是 v0.4.0 的。如果 8c778f9 加载不了 v0.4.0 的 checkpoint，方盒也该改在 8c778f9 上训；这时先停、等人看，
比白训 6 条（约 13 GPU 小时）划算。门槛不挂在 check_export 上，是因为它还没在真的 8c778f9 导出上跑过，格式上的小出入不该让两张卡空一整夜。
compat 启动时日志或门槛文件已存在就拒绝（旧的结尾行会让 `chain_after.sh` 立刻开链）；清单读不了、没有 export 行也拒绝。

## 4. 方盒 6 条

### 4.1 分配

| 机器 | 顺序 | 预计 |
|---|---|---|
| mf4090（400 万 buffer） | t1-ep1、t1-ep7、t1-ep28、t2-ep28 | 约 06:15 开始 compat，06:30 起训，四条约 9 小时，10/2 15:30 前后评完 |
| ml40（1000 万 buffer） | t2-ep1、t2-ep7 | C 段评完（约 10:45）后 compat 约 10 分钟，两条约 4.8 小时，10/2 16:00 前后评完 |

一台三条的分法（mf4090 只跑 Tier 1）要到 10/2 18:30 前后才全部评完。4 + 2 两台差不多同时结束，这 6 条之后才能做第一份完整提交，早结束有用。
两档混在一台上没有问题：链按 run 名前缀断言档位与参考目录（`precheck_expect.sh`）。

### 4.2 配方与队列

- 官方 G1 FlashSAC，逐帧回放，2048 世界，349,999,104 步，种子 42；支撑面开着（方盒）。mf4090 加 `training.replay.capacity=4000000`。
- 队列由 `make_batch_queue.py --box185` 生成（`stages/policy/queues/{mf4090,ml40}_box{.expect.tsv,_smoke.txt,.txt}`，已生成）：
  - run 名 `t<档位>-ep<N>-w2048-{cap4m|cap10m}-p185-<机器>`，冒烟加 `smoke-`；
  - 正式行 `V2D_WANDB_TAG=box185 V2D_KEEP_STATES=1 V2D_MAX_RETRY=0 V2D_GPU_APPS=1 V2D_WANDB_UPLOAD_CKPT=0`，冒烟行同第 1 批；
  - 只接受 ep1、ep7、ep28，Tier 2 另按 Tier 2 的支撑面清单核；队列行里不写 `V2D_FC_SRC`，由链的环境给。
- 帧数：Tier 1 取 `results/day2/sequence_stats_tier1.txt`，Tier 2 取 `results/batch_summary_v040_t2v54.tsv` 的 Tier 2 行，生成脚本两档各读各的。三条都是 747、896、988。

### 4.3 运行时

- **训练**挂 #185 补丁副本：链的环境 `V2D_ALLOW_FC_SRC=1 V2D_FC_SRC=<p185 副本>`。理由：#185 几何下不发散的全部对照（ep7 冒烟 8 个种子、ep1 与 ep28 截到
  6000 万步）都是在这份副本上跑的。8c778f9 副本与它在训练上只差 `training/flash_sac/evaluation.py` 的一行 import 与一个默认为 None 的字段，换哪份
  数值上都一样；用 p185 是为了与证据完全一致。
  - ml40 用已有的 `/lab_data/rxzhou/v2d/fc_src/v040_p185`；mf4090 用 `make_patched_fc_src.sh ~/v2d/fc_src/v040_p185` 新生成；
  - 两份都用 `fc_src_check.py` 加清单 `third_party/patches/flash_chord-p185.sha256` 核，与 v0.4.0 只差 `support.py`。
- **冒烟的不动基线**（256 世界 diag_rollout）在训练链里跑，同样挂 p185 副本。p185 的评测代码与 v0.4.0 相同，和此前所有冒烟一样。
- **评测**：评测链的环境 `V2D_FC_SRC=<8c778f9 副本>`。只评最终 checkpoint（`V2D_EVAL_STEPS=349999104`），4096 世界，判定与排行榜同一个运行时。
- **挂载核对**（`stages/policy/mount_check.py`）：冒烟与正式训练日志至少一行挂载、全部指向 p185 副本；评测日志 `runs/logs/<run>.eval_349999104_w4096.log`
  至少一行、全部指向 8c778f9 副本。每条 run 评完后跑，落盘。

### 4.4 自动编排（不依赖 Mac 在线）

每台三个 tmux，按 compat → box → box-eval 的顺序起，起之前确认 `runs/logs/compat_<机器>.{log,gate}` 与 `runs/logs/box_{train,eval}_<机器>.log` 都不存在，
起之后确认三个窗格都显示“等 …”。mf4090 在 `~/v2d/maniphys_lab_v2d_challenge` 下：

```
tmux new-session -d -s v2d-compat -c "$PWD" 'V2D_FC_SRC=$HOME/v2d/fc_src/fc_8c778f9 V2D_WAIT_FOR_EVAL_LOG=runs/logs/t2b_eval_mf4090.log stages/evaluate/compat_8c778f9.sh stages/evaluate/compat/mf4090.tsv compat_mf4090'
tmux new-session -d -s v2d-box -c "$PWD" 'V2D_ALLOW_FC_SRC=1 V2D_FC_SRC=$HOME/v2d/fc_src/v040_p185 V2D_PRUNE_SMOKE_STATE=1 V2D_MIN_FREE_MB=1200 stages/policy/chain_after.sh runs/logs/compat_mf4090.gate runs/logs/compat_mf4090.log 1 stages/policy/queues/mf4090_box.expect.tsv stages/policy/queues/mf4090_box_smoke.txt stages/policy/queues/mf4090_box.txt 24564 box_train_mf4090'
tmux new-session -d -s v2d-box-eval -c "$PWD" 'V2D_FC_SRC=$HOME/v2d/fc_src/fc_8c778f9 V2D_EVAL_STEPS=349999104 V2D_WAIT_FOR_LOG=runs/logs/box_train_mf4090.log stages/evaluate/day2_eval_chain.sh stages/policy/queues/mf4090_box.expect.tsv - box_eval_mf4090'
```

ml40 在 `/lab_data/rxzhou/v2d/maniphys_lab_v2d_challenge` 下：compat 等 `runs/logs/t2c_eval_ml40.log`，清单 `compat/ml40.tsv`，门槛同样是 1，冒烟显存上限 44000，
不设 `V2D_PRUNE_SMOKE_STATE` 与 `V2D_MIN_FREE_MB`，副本路径换成 `/lab_data/rxzhou/v2d/fc_src/…`。单引号里的 `$HOME` 由 tmux 的 shell 展开。

| 情形 | 结果 |
|---|---|
| Tier 2 评测链结束（DONE 或 FAILED） | compat 开始 |
| compat 正常结束 | 写门槛，日志最后一行 DAY2_EVAL_DONE |
| compat 中途停（GPU 被占、副本核不过） | 门槛“完成 0”，日志最后一行 DAY2_EVAL_FAILED |
| 门槛“完成 1” | `chain_after.sh` 开方盒训练链 |
| 门槛“完成 0” | 方盒训练日志写 DAY2_TRAIN_FAILED，方盒评测链空跑结束，GPU 空着等人看 |
| compat 在写门槛之前崩溃 | `chain_after.sh` 一直等；GPU 空着，没有坏结果。查 compat 窗格 |

方盒训练链自己还有三道检查：GPU 检查、磁盘守卫、`check_src`。

### 4.5 判据（执行前登记，与 Tier 2 第 1 批相同的部分不重复）

- **冒烟通过**：第 1 批各项，加两项发散判据，加“rollout 帧数等于源帧数”。显存上限 mf4090 24564 MiB、ml40 44000 MiB。不过的，正式训练记 SKIPPED。
- **正式训练的结局**：完成 / 发散（看守止损或 NONFINITE）/ 失败 / 跳过 / 显存不足，都不人工续训。
- **能进候选**：
  - 完成，最终 checkpoint 有 8c778f9 下的 4096 世界评测，step_count 等于源帧数，non_finite_worlds 为空；
  - 结果头的来历不带 -dirty / -syncing（来历会是 90a73fa，见第 7 节的说明）；
  - 挂载核对通过（4.3 节）。
  满足的，`policy_349999104` 是这条 episode 当前的候选。按规矩二退回的 checkpoint 也要先在 8c778f9 下评 4096 世界，评完才进候选。
- **质量只报数**：
  - Day 1 判据：chord_sr > 0、maniptrans_sr > 0、ADD-AUC 高于这条序列这一档参考的不动基线（`batch_verdict.py --steps 349999104`）；
  - 另报 SP-SR、MPPE。Tier 2 的数对照 Tier 2 v5.4 参考，不和 Tier 1 比。
- **事先登记的预期**（只描述，不作判据）：
  - t1-ep28 的参考穿过两块板，若不通过，先归到参考几何；
  - t2-ep7 的参考有 123 帧穿过桌板、t2-ep28 两块板各 244、211 帧穿过、t2-ep1 对椅背 121 帧嵌入超过 5 mm，同样先归到参考几何；
  - t1-ep1 的穿地与 ep17、ep22 同级。
  发散方面，#185 几何下 8 + 2 条对照全部有限，满 3.5 亿步没跑过，靠看守兜底。

### 4.6 净室

- Tier 2 的两条 run 只读 `runs/motion/tier2` 的参考（v5.4）、Tier 2 支撑面拷贝与 Tier 2 网格；队列生成对 Tier 2 行只读 Tier 2 的表。
- `frame_ref_check.py --tier 2` 开 `tier_guard`，只读 Tier 2 的数据与 v5.4；E7 同样不读 Tier 1。
- 重训这三条的依据是支撑面文件与导入器代码（v0.4.0 不读 scale），配方是官方配方。
- “#185 几何下不发散”出自 Tier 1 ep7 的冒烟对照，是 Tier 1 实验得出的。拿它决定“Tier 2 也用 #185 训”属解读：这个决定并不依赖它，
  官方评测运行时本来就是 8c778f9，训练几何与评测几何一致。

### 4.7 磁盘

- mf4090 20:12 可用 9431 MB。B 段剩 5 条约 1.8 GB；两份副本约 0.83 GB；compat 导出不到 10 MB；方盒 4 条约 1.5 GB（冒烟 state 删、正式只留一份 state）。
  跑完约剩 5.3 GB，守卫 1200 MB 足够。
- ml40 剩 1.9 TB。

## 5. 提交的两条规矩（用户 10/1 采纳，原文）

- 规矩一：“含 NaN 的 policy 不拿去导出，训练链今天起已经会自动拦下；”
  - 训练链：看守止损、`NONFINITE`、评测链不评（10/1 上线）；
  - 导出：`fc_export.sh` 守卫，退出码 12，不起容器。
- 规矩二：“提交时某条 episode 如果报这个错，就退到同一条 run 里更早的一份正常 checkpoint。”
  - `fc_export.sh` 只看这一次追加的日志，把这个错认成退出码 13；
  - 往前退的逻辑写进提交流程（另写计划）：按步数从最终 checkpoint 往前，跳过非有限的，第一份导出成功且核对通过的就用，记下用的是哪一步；
    退回的那一份要先在 8c778f9 下评 4096 世界（4.5 节）。这是唯一允许不用最终 checkpoint 的情形。
- 顺带登记一个解读，待用户确认（属解读，不是官方原文）：
  - 官方打包器对 Tier 2 / Tier 3 也读干净参考，用它核帧、算本地分数。官方原文：“Local scores use the clean reference”。
  - 打包是官方的提交步骤，照做；但 Tier 2 / Tier 3 的本地分数是 Tier 1 派生的数，按净室规矩不拿来做任何 Tier 2 / Tier 3 的选择，
    提交流程里 Tier 2 / Tier 3 打包时把 `locally computed` 那一行滤掉、不落盘。
  - Kaggle 的 Tier 2 排行榜给出的也是对干净参考的分数，而且滤不掉。排行榜反馈怎么用，要在第一次交 Tier 2 之前写进提交流程计划。

## 6. 代码清单

| 文件 | 改动 | 测试 |
|---|---|---|
| `tools/make_fc_patch.sh` | 新：生成 8c778f9 补丁、清单、评测摘要 | 已跑，11 个文件；审查从 GitHub 取旧文件实打过一遍 |
| `third_party/patches/flash_chord-v0.4.0-to-8c778f9.patch`、`flash_chord-8c778f9.sha256`、`flash_chord-8c778f9.eval.json`、`flash_chord-p185.sha256` | 新 | 同上；服务器上生成副本时 dry-run 加 fc_src_check |
| `stages/evaluate/eval_runtime_facts.sh` | 新：第 2 节的事实摘录 | 已落盘 `results/submission/eval_runtime_facts.txt` |
| `stages/policy/make_fc_src_8c778f9.sh` | 新：失败时删整个目标 | 服务器上实跑 |
| `stages/policy/fc_src_check.py` | 新：根下 wandb/、.hydra/ 不比 | `test_fc_src_check.py`：正常与噪声 2 种、出错 6 种 |
| `stages/evaluate/fc_export.sh` | 新：dry-run、只看新增日志、摘要不影响退出码 | `test_fc_export.py` 8 项 |
| `stages/evaluate/check_export.py`、`check_export.sh` | 新：刚体数取自 motion parquet；宿主机缺库时进容器跑 | `test_check_export.py`：复刻上游写入器，正例 4、反例 6（Mac 用 uv，ml40 在容器里） |
| `stages/evaluate/compat_8c778f9.sh`、`compat_expect.sh`、`compat/{mf4090,ml40}.tsv` | 新：门槛只看导出、拒绝旧日志、预检模式 | `test_compat_8c778f9.py` 7 组（连同真的 record 与 chain_after.sh） |
| `stages/evaluate/frame_ref_check.py` | 新：P5′ | `test_frame_ref_check.py`（uv）：两档各正反例 |
| `stages/policy/mount_check.py` | 新：挂载核对 | `test_mount_check.py`：正常 1、出错 4 |
| `stages/retarget/box_ref_check.sh` | 新：Tier 2 方盒参考的穿透 | 服务器上实跑 |
| `stages/policy/arm_box_chains.sh` | 新：起三个等待中的 tmux，起之前核旧日志、标记、会话、副本 | 服务器上实跑 |
| `scripts/dev/push-new-files` | 新：链在跑时只加新文件、核 md5；只许覆盖我们自己先前放上去的版本 | 两台实跑 |
| `stages/policy/make_batch_queue.py` | 加 `--box185`（只在 Mac 上用） | `test_make_batch_queue.py`：原 4 项不变，加 2 项 |
| `stages/policy/queues/{mf4090,ml40}_box*` | 新：方盒队列 | 服务器上 `fc_config_check.sh` 与 `precheck_expect.sh` |

## 7. 执行步骤

1. Mac：全部测试在 Mac 上过；提交、推送（本版）。落盘 `results/submission/eval_runtime_facts.txt`（已做）。
2. 放文件：两台先确认要放的路径都不存在，再从仓库根 `rsync -a --relative` 放这些新文件：
   第 6 节表里除 `tools/`、`make_batch_queue.py`、Mac 上的测试之外的全部文件，加上 `third_party/patches/` 的四个新文件、`stages/evaluate/compat/` 两份清单、
   六份队列、`libs/v2d_infra/tier_guard.py`（已在服务器上，不动）。之后逐个比 md5，落盘 `results/box/deploy_<机器>.txt`。
   不碰链正在用的任何文件，`.v2d-source-commit` 不变，仍是 90a73fa。执行记录写明真实的提交号与部署文件，方盒链跑完后整体同步一次。
3. 服务器 CPU 步骤（不占 GPU，可以与链并行）：
   - 生成副本：mf4090 两份（p185、8c778f9），ml40 一份（8c778f9）。每份 `fc_src_check.py` 落盘，ml40 已有的 p185 副本也核一遍；
   - 两台跑 compat 的预检（`V2D_COMPAT_DRYRUN=1`，环境与参数同第 4.4 节），要 COMPAT_DRYRUN_OK：宿主机 python3 的 numpy、pyarrow，要等的日志存在，副本核得过，
     每行 fc_export 的预检退出码对（含各 run 的 `v2d_meta.json` 与 run 记录）；
   - 两台对方盒队列跑 `fc_config_check.sh` 与 `precheck_expect.sh`，要 PRECHECK_OK；
   - mf4090 跑 `frame_ref_check.py --tier 1` 与 `--tier 2`（P5′），落盘；
   - mf4090 跑 `box_ref_check.sh 2`（Tier 2 方盒参考的穿透），落盘。
4. 起第 4.4 节的 tmux（每台三个，按顺序），确认三个都在等、长链标记都在。
5. 之后只做短查询。compat 跑完后：Mac 拉回结果与导出（每份几百 KB），写执行记录 `agent-doc/experiments/2026-10-02-box6-eval-runtime.md`，承重结论过 jev。
   方盒评完后用 `batch_verdict.py --steps 349999104` 判定，`mount_check.py` 一并落盘。

## 8. 不做的事

- 不改配方、超参、种子，不人工续训，不改参考。
- 不碰正在跑的 Tier 2 链与它们用的脚本；链跑完前不整体同步。
- 不往 Kaggle 交任何东西：本计划只验证到打包的换算为止，第一份提交另写计划。
- 不删旧目录（第 1 批 v0.4.0 几何的发散证据）。
- 不用 Tier 2 / Tier 3 的本地分数（第 5 节）。

## 审查与处理（第 2 版，10/1 20:30–21:30）

两份独立审查都用 Fable 5.1，结论都是 GO WITH FIXES，没有 BLOCKER。

**计划审查**：
- MAJOR 门槛挂在没在真数据上跑过的 check_export 上，格式上的小出入会让两张卡空一夜 → 门槛只看 fc_export 的退出码（P1），check_export 不过记 COMPAT_FAIL、不挡训练（3.6 节）。
- MAJOR ml40 宿主机的 numpy、pyarrow 没核 → compat 预检里核，两台都跑（第 7 节第 3 步）。
- MAJOR 打包的刚体换算可以现在就在 CPU 上对 60 条全核，却只排了 3 条 → 新增 `frame_ref_check.py`（P5′），今晚跑；帧号对齐的理由写进事实 7。
- MAJOR 挂载核对是候选条件之一却没写，且第 1 版把评测的挂载行写错了地方 → 新增 `mount_check.py` 与测试，4.3 节改正，事实 13。
- MINOR 决策表缺 P2、P3 不过、只有一台不过等情形 → 补齐（3.5 节）。
- MINOR P4 的阈值不到已知噪声的 2 倍 → P4 不过先重评一次；ml40 加一行 4096 世界比对。
- MINOR 便宜的对照没用上 → mf4090 加一行 2 个世界的导出；1 个世界与 4096 世界的差、世界间的差都只报；24 GB 卡上评 1000 万 buffer 的 checkpoint 没试过，各台导出自己的。
- MINOR 无人值守启动时旧日志会让链立刻开 → compat 拒绝旧日志与旧门槛，起 tmux 前逐个确认（4.4 节）。
- MINOR 来历会显示 90a73fa → 执行记录写明真实提交与部署文件，链跑完后整体同步。
- MINOR “训练代码与其余 54 条相同”不严谨 → 改成“与 #185 几何下的全部对照用的是同一份副本”（4.3 节）。
- MINOR 退回的 checkpoint 怎么进候选、排行榜反馈怎么用没登记 → 4.5 节、第 5 节补上；E6 的数据目录与 `--code-commit` 写明（3.4 节）。

**代码审查（高效与合理）**：
- MAJOR fc_export 按累积日志判终止错误，重跑会把别的失败误判成 13 → 只看这一次追加的日志行；测试“先 13 后 3”。
- MAJOR 没有 CPU 预检，元数据、库、日志名、旧日志任何一项出问题都要到早上才知道 → fc_export 加 dry-run，compat 加预检模式，起链前两台都跑。
- MINOR 清单为空时报 COMPAT_PASS → 清单读不了或没有 export 行就拒绝。
- MINOR fc_export 的退出码等于摘要脚本的 → 摘要出错不影响退出码。
- MINOR check_export 写死 1 个刚体 → 刚体数取自 motion parquet；测试加 2 个刚体。
- MINOR negctl 时核对脚本崩溃也会被当成“核对不过” → 要求最后一行是 EXPORT_FAIL；测试覆盖。
- MINOR 副本用过之后根下的 wandb/、.hydra/ 会让复核失败 → 不比，只报个数。
- MINOR make_fc_src_8c778f9.sh 失败时留下半成品 → 失败就删整个目标。
- MINOR 计划里评测挂载行的位置写错 → 同计划审查第 4 条。
审查还实测确认了补丁、两个摘要、门槛与 chain_after 的互通（8 个情形）、check_export 对上游写入格式的读取、副本树的比较逻辑都没有问题。
