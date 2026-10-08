# 计划：SOP 页面加成功与失败案例的策略 rollout 视频（2026-10-08，第 2 版）

第 1 版经 Fable 5.1 审查（GO WITH FIXES），9 条意见的处理见文末“审查与处理”；与正文冲突处以文末为准。

用户 10/7–10/8：“SOP 中更新一些成功范例和失败案例的可视化视频”“不要放在 mac 这边本地做”“依旧先规划 review plan 再 execute”。
时间一律 UTC-6。渲染、挑世界、转码都在服务器上；只有发布前把做好的几个 mp4 / jpg（几 MB）拉回 Mac，因为 Artifact 发布工具只读本机文件。

## 1. 事实

- 现有素材（`agent-doc/plan-site-media-2026-09-30.md`）：任务一览的 G1 动画是**运动学参考**（`stages/policy/site_ref_replay.py`，不跑物理），不是策略。
  要看成功与失败，得录策略真正跑出来的 rollout。
- 8c778f9 评测的 rollout 是 Python 逐步循环：`rollout.py:392–394` 每步 `jax_env.step(action)`，之后从 `env.state_0.body_q` 取位姿。可以包一层，在每步之后把全部刚体位姿抄下来。
- 评测时所有世界初始状态相同（评测场景 `object_scale` 1.0、显式重置在第 0 帧），世界之间的差别来自 GPU 计算的不确定性：同一 checkpoint 重跑，某个编号的世界不一定重现同样的结局。
  所以**要在同一次 rollout 里录下状态、按结局挑世界、再渲染录下的状态**，不能“记下编号再重跑”。
- 渲染：官方 `flash_chord.visualization.viewer` 的 `mp4` 后端（`MP4Viewer` 包 Newton 无头 GL）；容器里要 `PYGLET_HEADLESS=1`；`set_model`、`begin_frame`、`log_state`、`end_frame`、`close`、`set_camera`。
  相机沿用 `site_ref_replay.py` 的 `_camera_track`（按参考的机器人根与物体轨迹逐帧跟随）。ffmpeg 用容器里 imageio_ffmpeg 自带的 7.0.2。
- 数据与机器：Tier 1 的 checkpoint 在 mf4090（磁盘剩 1.6 GB），Tier 2 的在 ml40。录下的位姿只在内存里，落盘的只有选中世界的位姿（每段约 1 MB）和成片。
- Artifact 现有 123 个文件约 11 MB；每次发布只传新增文件，旧文件保留。

## 2. 案例（登记，6 段，来自 5 次 rollout）

| # | 档位 | run | 类别 | 讲什么 |
|---|---|---|---|---|
| 1 | Tier 1 | `t1-ep18-w2048-cap4m-r3a-mf4090` | 成功 | 变体 A 跟得准的样子 |
| 2 | Tier 1 | 同上，同一次 rollout | 摔倒（物体先丢） | 同一个策略的失败：物体先脱手，约 1.5 s 后摔倒（S4 不过的原因） |
| 3 | Tier 1 | `t1-ep20-w2048-cap4m-mf4090`（基线 s42） | 差一点（没摔） | 基线朝向跟不住（4096 世界朝向误差 35°） |
| 4 | Tier 1 | `t1-ep20-w2048-cap4m-r3a-mf4090`（变体 A s42） | 成功 | 变体 A 把同一条 episode 做成（与案例 3 同为 seed 42） |
| 5 | Tier 2 | `t2-ep24-w2048-cap10m-ml40`（基线 s42） | 差一点 | Tier 2 基线（对照 v5.4 参考） |
| 6 | Tier 2 | `t2-ep24-w2048-cap10m-r3a-ml40` | 成功 | Tier 2 变体 A（对照 v5.4 参考） |

## 3. 做法

1. `stages/evaluate/case_clip.py record`（容器、GPU）：原样跑官方 `evaluate_policy.py`（`world_count=256`，其余同 `fc_eval.sh`），包一层：每步把 256 个世界的 `body_q` 抄进内存；
   在 `score_reference_tracking` 处拿到逐世界误差，按第 4 节的规则分类、挑世界，只把选中世界的逐帧位姿与元数据存成 npz（`runs/site_cases/`，不进 git）。Tier 2 的进程先调 `forbid_tier1()`。
2. `case_clip.py render`（容器、GPU）：同样经 `evaluate_policy.py` 建一个 1 世界的环境（与评测同一套建场景代码），在 rollout 开始前接管：左栏逐帧把录下的位姿写进 `state_0.body_q` 渲染；
   右栏用 `env.reset(frame_id=f)` 取参考第 f 帧渲染；两栏同一条相机轨迹；渲完中止评测。
3. ffmpeg：两栏左右拼成 1280×480、实时速度（30 fps、一帧一个源帧）、H.264 CRF 28、faststart、去元数据；封面取关键帧（摔倒取骨盆超阈值那一帧，其余取中间帧）。
4. 页面：训练实验组新加一页 `pg-cases`“成功与失败案例”（放在第 3 步配方试验之后），每段一张卡：档位、run、世界编号、挑选规则、这一世界的 MP 误差与结局、看点；
   试验页与首页链过去。注明“左：策略在物理仿真里的 rollout；右：参考”“从 256 个世界里按规则挑的典型世界”。
5. 发布：成片与封面经 `scripts/dev/pull-results` 一类的拉取放到 Mac 的 `runs/site_media/cases/`，`tools/site_check.py --media-dir` 过后用 Artifact `files` 只传新增文件。

## 4. 判据（执行前登记）

**挑世界的规则**（在这次 rollout 的 256 个世界里，不看画面挑）：

- 成功：MP-SR 判成功的世界里，逐世界平均物体位置误差最接近这一类中位数的那个。
- 摔倒（物体先丢）：失败且骨盆超阈值、物体先丢（与 `fall_order.py` 同一定义，k = 25）的世界里，t_pel − t_obj 最接近这一类中位数的那个。
- 差一点：失败且骨盆从未超阈值的世界里，逐世界平均位置误差最接近这一类中位数的那个。
- 某一类在这 256 个世界里为空，就如实写“这次 rollout 里没有”，不换别的 run 或重跑去凑。

**门**：

- 录制：256 世界这次 rollout 的 MP-SR 与 4096 世界评测相差在二项抽样的 3σ 内（只报，不停）；npz 里选中世界第 0 帧的位姿有限。
- 渲染：1 世界环境 `env.reset(frame_id=0)` 的刚体位姿与录下的选中世界第 0 帧相比，最大位置差 ≤ 2 cm（刚体顺序对得上）；不满足就停。渲染帧数 = 参考帧数，全部有限。
- 成片：每段 ≤ 3 MB，6 段合计 ≤ 15 MB；封面抽看机器人与物体在画面里（人工看，补充）。
- 页面：`site_check.py --media-dir runs/site_media` 输出 SITE_OK；成片不进 git。

## 5. 风险

- 刚体顺序：1 世界与 256 世界由同一套代码建场景，按世界切片后顺序应相同；第 0 帧的门把关。
- 右栏的参考是 `env.reset(frame_id=f)` 摆出的姿态，不跑物理，与任务一览的参考动画同一类。
- Tier 2 的参考是 v5.4（策略的输入），不是排行榜对照的干净真值，页面写明。
- 显存：256 世界的 rollout 加 1 世界渲染，在 4090 上都远低于训练时的用量。

## 6. 产物

`case_clip.py`（带一个不需要 GPU 的测试：挑世界规则在造的误差上覆盖三类与空类）、`results/site/cases_manifest.txt`、页面新页、执行记录、jev 核页面上的论断。

## 审查与处理（Fable 5.1，GO WITH FIXES）——第 2 版

审查确认：录制加重渲的做法可行，`stages/evaluate/diag_palms.py` 已用同样的方式在 `record_object_pose_rollout` 里逐步读 `env.state_0.body_q`；内存约 300 MB。

| # | 级别 | 意见 | 处理 |
|---|---|---|---|
| 1 | should | 第 0 帧 2 cm 的门分辨不出相邻的 Dex3 指节 | 改成三道确定性门：从录下的 `body_q` 取出的物体位置与评测器记录的 `achieved_pose_w` 逐步相差 ≤ 1e-6 m（证明世界切片与步对齐）；1 世界与录制时每世界的刚体数、刚体名逐个相同；两边的重置位姿相差 ≤ 1 mm |
| 2 | should | 被判终止的世界在评测里会不会被拉回参考（画面瞬移） | 选中世界逐步查骨盆单步位移，超过 0.3 m 就在跳变前截断，卡片上注明 |
| 3 | should | 案例 3、4 的种子不配对 | 案例 4 改为变体 A seed 42（`t1-ep20-w2048-cap4m-r3a-mf4090`，4096 世界 MP-SR 0.794），与基线 seed 42 配对；卡片上写两种子的 MP-SR |
| 4 | should | 挑世界规则要排除非有限世界、平手取最小编号；卡片要写逐世界误差与门槛 | 都加上；摔倒案例写这个世界与这一类中位数的 t_pel − t_obj |
| 5 | should | 清单要钉住 step、sha256、parquet、世界编号、规则、逐世界误差、代码 md5 | 清单 `results/site/cases_manifest.txt` 全部带上 |
| 6 | should | 渲染进程也要调 `forbid_tier1()`；Tier 2 的“对照 v5.4”写在数字旁边 | 两种模式都调；Tier 2 卡片的数字旁直接标 |
| 7 | nit | 步与帧对齐、重置接口 | 评测器第 k 步对照参考第 start_frame + k 帧（`reference_object_pose`）；8c778f9 的 `RLEnv.reset` 有 `frame_id` 参数（已核） |
| 8 | nit | 传输与编码 | 成片 rsync 到 Mac 的 `runs/site_media/cases/`，页面引用 `media/cases/…`；`yuv420p`；两栏标签用页面上的 HTML 叠字；中间文件用完删除；每次录制前查磁盘；同一条 run 的参考栏只渲一次 |
| 9 | nit | GPU 守卫与长链标记 | 已查 GPU；批处理期间写 `runs/.chain-active-sitecases`，跑完删除 |
