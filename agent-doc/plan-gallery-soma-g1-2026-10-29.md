# 计划：gallery 加“人（SOMA）与 G1 做同一个动作”的并排视频（2026-10-29，第 1.1 版）

第 1 版经 Fable 5.1 复核（GO WITH FIXES，13 条），处理见文末“复核与处理”；与正文冲突处以文末为准。

时间一律 Denver（MDT）。用户 10/28 23:5x：“似乎没有看到soma和G1的相同操作视频”。
现有 gallery（commit 3b96ae0，SOP 版本 65）只把物体叠在 exo 视频上，人和机器人都没有画出来。

## 1. 事实

- **人。** Tier 3 每个版本的 parquet（`runs/<version>/data/chunk-000/episode_*.parquet`）带 SOMA 的人体列，与 `observation.object.pose`
  同一个世界。`t3_world_probe.soma_cv()` 用 SOMA 层（`v2d_cari4d` 环境，CPU）算出 OpenCV 世界里的关节与顶点；
  `t3_hand_verts_export.py` 已经这样导出过手的顶点，物体位姿与版本 parquet 一致。`t3_gallery_video.py` 的 `render()`
  把带位姿的网格投到 exo 画面上（相似变换 `similarity()` 与内参来自 CARI4D 的转换目录）。所以人体网格可以和物体一样叠到 exo 视频上，只用 CPU。
- **G1 参考。** 重定向产物 `runs/motion/<集>/whole_body/soma/.../robot_name=g1/data.parquet` 有根位姿、关节角、手指关节、末端位姿 `ee_pose_w`。
  `stages/policy/site_ref_replay.py` 已经在容器里用 Newton 无头渲染过 G1 的运动学参考（SOP 任务一览的 G1 动画，GPU）。
- **G1 策略。** 1 世界导出（`export_8c778f9/s349999104_w1/*.parquet`）只有物体的达成/参考位姿，没有机器人身体。要画策略里的 G1，
  得重跑 rollout 并录下全部刚体位姿。`stages/evaluate/case_clip.py` 的 record / render 两步正是这样做的（10/8 计划第 2 版，三道门，
  SOP“成功与失败案例”页的 6 段视频），左栏是录下的 rollout、右栏是重置到参考第 f 帧的 G1，同一条相机轨迹。
  `case_clip.sh` 目前只认 `t1-`、`t2-` 开头的 run（计划 t3-pilot n7 记过）。
- **GPU。** ml40 在训 ep12 的 B2n（t3qb2n12，读数约 01:00–01:15），之后是它的 eval / export 链。mf4090 等 ep27 中转完成后要训 t3pb2r27（几小时）。
  `case_clip.sh` 见到 GPU 上有别的进程就拒绝运行，不会和训练抢卡。
- **规则。** Kaggle 4.b：人看视频不能用来挑或调 Tier 3 的输出。这批视频只做展示，不进任何选择。数据集 CC BY 4.0，页面已有署名说明。

## 2. 做什么

每集一段三栏视频，帧号按参考帧对齐：

| 栏 | 内容 | 怎么来 | 机器 |
|---|---|---|---|
| 左 | exo 视频 + SOMA 人体网格（单色半透明）+ 重建物体（按体坐标上色） | 新增 `t3_gallery_video.py` 的 `human=<version>` 面板 | ml40 CPU |
| 中 | 策略 rollout 里的 G1 和仿真物体 | `case_clip.sh record` + `render` 的左栏 | ml40 GPU（空闲时） |
| 右 | G1 运动学参考（重置到参考第 f 帧）和参考物体 | 同一次 `render` 的右栏 | 同上 |

集与 run（与 gallery 的“策略回放”组相同，gb5 系列的现役 checkpoint）：ep15（hr3s 重训）、ep5、ep10、ep23、ep14。
ep12、ep27 等 B2 / B2n 重训出读数后再补，用新 checkpoint。

**挑世界（登记）。** `case_clip record` 照旧跑 256 世界，类别 `success,nearmiss,fall`。成片用的类别：有成功世界就用 success，
否则 nearmiss，否则 fall；类内取离中位数最近的世界（`pick_worlds` 原规则）。标题写明类别与这次 256 世界的 MP-SR，
不让一段成功片段代表整集。

**帧对齐。** 中、右两栏的第 t 帧对应参考第 t 帧（`render.json` 的段落与 rollout 步数）。左栏取版本 parquet 的第 t 帧。
开工前核：1 世界导出的 `reference_frame` 列从 0 起逐步加 1；版本 parquet 与重定向 parquet 的帧数一致（不一致就截到短的，记下）。

## 3. 代码改动

1. `case_clip.sh`：run 名的正则放开 `t3-`；`_guard_tier()` 对 `t3-` 调 `forbid_lower_tiers()`（与 Tier 3 其它工具相同）。
   参考 parquet 的检查 `[[ $PARQ == /repo/runs/motion/tier* ]]` 不变（Tier 3 的 motion 目录也以 tier3 开头）。
2. `t3_gallery_video.py`：新面板 `label=human:<version>`。SOMA 顶点在服务器上先由新脚本 `t3_soma_verts_export.py`（`v2d_cari4d`，CPU）
   导出成 npz（每帧顶点，按 SOMA 的面），gallery 读 npz。人体网格减面到 ≤ 6000 个三角形，单色（肤色灰）α 0.45，物体画在人之后。
3. `stages/evaluate/case_compose.py` 加一个可选第三栏：读左栏 mp4，按帧号拼在最左边；输出 1440×360 左右的三栏成片。
4. 测试：`case_clip.sh` 的参数检查接受 `t3-` 并拒绝 `t4-`；SOMA 导出在一个造的姿态上顶点数与面数对得上；三栏拼接在造的三段视频上帧数取最短。

## 4. 门（登记，任何一道不过就不发这一段）

- G1 栏沿用 case_clip 的三道门：录下的物体位置与评测器记录逐步一致（≤ 1e-6 m）、1 世界场景重置位姿差 ≤ 1 mm、骨盆无单步 > 0.3 m 的跳变（有就截断并在标题注明）。
- 人体栏：导出 npz 里的物体位姿与 `world_pose()` 读的同一版本逐帧一致（差 ≤ 1e-6 m、≤ 1e-4°），证明人和物体在同一个世界。
- 人体投影健全性：手腕关节投影在 exo 画面内的帧占比 ≥ 90%（人一直在画面里）；不满足就停下查坐标系，不发。
- 帧对齐：第 2 节的两项核对通过。

## 5. 顺序与时间

1. 写代码与测试（Mac 上写，推到 t3sil / track2 分支；**不用 V2D_FORCE_SYNC**，有链在跑时文件经 `runs/t3b2/tools/` 或等链结束再同步）。
2. ml40 CPU：SOMA 导出与左栏（nice 19，与训练并行，约 10 分钟/集）。
3. ml40 GPU：t3qb2n12 链全部结束（`.chain-active-*` 含 `cand_*` 全部消失）后，依次 5 集 record + render（预计每集 5–10 分钟）。
   这段时间若有新训练要排上 ml40，训练优先，视频顺延。
4. 拼三栏、拉回 Mac（几 MB）、更新 gallery 页（新增一组“人与 G1 同一动作”）、site_check、名字检查、提交、发布到原 URL。

## 6. 不做

- 不把 G1 叠到 exo 视频上（重定向坐标系与重建坐标系之间要一个刚体映射，机器人比人小，叠出来容易误导）。
- 不为好看换 checkpoint 或挑世界；类别规则在第 2 节登记。
- 不导出 Tier 1 / Tier 2 的人体（这批只讲 Tier 3 的重建到策略）。

## 复核与处理（第 1.1 版）

**改成两步。** 第一步只做“人与 G1 参考”两栏（复核第 13 条）：左栏 exo + SOMA + 重建物体，右栏 G1 运动学参考，
用 `site_ref_replay.py` 渲 1 世界、不跑策略，GPU 只占几分钟。第二步再加策略栏（case_clip），等 ml40 空闲、按下面第 1、3、4、6 条改完再做。

| # | 级别 | 意见 | 处理 |
|---|---|---|---|
| 1 | BLOCKER | 训练分支的 tier_guard 没有 `forbid_lower_tiers` | 第二步前把 t3sil 的 `tier_guard.py` 合到训练分支并加测试。第一步不经 case_clip：参考渲染的脚本只接受 `/repo/runs/motion/tier3_*` 的 parquet，别的路径直接拒绝 |
| 2 | MAJOR | “人和物体同一世界”的门是同义反复 | 换成两道：(a) 导出 npz 里的人体参数与该版本 parquet 的 `observation.human.*` 逐列相同（≤ 1e-6），证明画的是这个版本的人；(b) 画出的人体轮廓（去掉物体掩码内的像素）与 SAM2 人体掩码的 IoU，每 5 帧取一帧，中位数 ≥ 0.5，不过就不出片 |
| 3 | MAJOR | case_clip 不看链标记 | 参考渲染脚本和第二步的 case_clip 都加：有 `runs/.chain-active-*` 就拒绝，自己写 `runs/.chain-active-gallery` 并在退出时删掉 |
| 4 | MAJOR | 挑世界偏向成功 | 第二步改成取世界数最多的类别，标题写 MP-SR 和该类占比 |
| 5 | MINOR | 版本与 run 手工配对 | 按 `runs/tier3/root_<集>/meta/provenance.json` 的 `source_parquet` 取版本；没有这一项的（root_gb5）就比对物体位姿与人体参数逐帧相同才认 |
| 6 | MINOR | 起始帧核错对象 | 第二步在 record 里核 `rollout.start_frame == 0`；第一步参考渲染第 f 帧就是 `reset(frame_id=f)`，重定向逐帧不插值（`run_soma_to_g1.py:5-9`），核版本帧数 = 重定向帧数 |
| 7 | MINOR | 拼接的 fps 与高度 | 拼接前两栏都转成 30 fps、高 480，按帧数取短 |
| 8 | MINOR | 自动裁剪会切掉人 | 有人体栏时裁剪框取人体掩码与物体掩码的并集 |
| 9 | MINOR | 不可见帧上参考物体停在最后位姿 | 页面说明里加一句 |
| 10 | NIT | 逐帧减面破坏顶点对应 | 不减面，SOMA 全网格 |
| 11 | NIT | case_clip 走固定路径 | 链标记全部消失后用 `scripts/dev/remote` 同步，mp4 用 rsync 拉回 |
| 12 | NIT | `V2D_FC_SRC` 是必填 | 命令里写明 |
| 13 | — | 更简单的路线 | 采纳，即上面的两步 |

第一步的集：ep15（hr3s_dyn7）、ep5、ep10、ep23、ep14（gb5 现役参考）。第一步不涉及策略，不挑世界。

## 执行记录

- 10/29 00:05–00:36 MDT：第一步的 CPU 部分在 ml40 跑完（t3sil ccc9114、9e 后的参数顺序修正；`gallery_pair.sh cpu`，记录在 ml40 `results/ml40/gallery_pair/`）。
  第一次跑 `human_iou` 的参数顺序写反（s 与 K），ep15、ep5、ep10 报错，没有出片；修正后重跑。
  5 集人体栏全部过门：人体参数与版本 parquet 逐列相同（最大差 0），人体轮廓对 SAM2 人体掩码 IoU 中位 0.833（ep15）、0.844（ep5）、0.849（ep10）、0.868（ep23）、0.881（ep14），门槛 0.5。
  另修了 `crop=auto` 的一个旧问题：它取 h5 的前 n 个键，物体与人体掩码交替排列，实际只覆盖前一半帧；现在逐帧取。已发布的 13 段视频不重渲。
- G1 参考栏（GPU）等 ml40 上 t3qb2n12 的链标记全部消失后再跑，之后同步、渲染、拼接。
