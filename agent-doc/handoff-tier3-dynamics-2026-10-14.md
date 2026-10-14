# Tier 3 物体动力学：检查与修复（2026-10-14，分支 `track2/tier3-recon`）

接 [handoff-tier3-2026-10-10.md](handoff-tier3-2026-10-10.md)。这份写给接手 Tier 3 数据或训练的 agent：best_hm 上训不动的
一个原因，以及一版候选数据 `best_dyn4`。**交付版仍是 `best_hm`**，`best_dyn4` 还没换上去，要不要用它做训练试点由用户定。

路径：`$T` = L40S `/lab_data/yqchen/v2d/tier3`，`$G` = `/lab_data/yqchen/v2d/gate`（rxzhou 门槛在我们这边的自测环境，
CPU 跑，venv 在 `$G/venv`）。

## 为什么查这个

t3p4a（best_hm 的 ep15、17、1、2、3）MP-SR 全是 0，骨盆失败占比 0.98–1.0；同集 Tier 2 是 0.806–0.987。重定向已排除
（rxzhou 训练用的 `tier3_hm` 与我们重定向出的统计逐项相同）。机器人层参考里，没被碰的物体在漂、在抖、在翻，包括对称物体的
朝向在等价姿态间跳变；静止物体的抖动还被算成「物体在移动」，于是看起来像机器人的手离移动中的物体 24–55 cm。

## 检查：`stages/recovery/tier3/gate/t3_dynamics_check.py`

读机器人层 parquet（训练实际吃的那一层）。先判每帧接触状态，再判该状态下运动是否物理上可能。判据建在加速度上，静止和
运动只用一个速度门槛（0.05 m/s）。

- **被碰**：参考自己的 `hand_contact_active`，或任一手部连杆的碰撞体表面离物体表面 10 cm 以内；任务文本提到脚时，脚掌也算。
  手部位置由 `flash_chord` 的 `main_with_hand.urdf` 做正运动学（`pinocchio`；掌心与 `ee_pose_w` 误差为 0），机器人层的
  `hand_frames_w` 是空的。只量掌心原点不够：食指、中指末节离掌心原点 12.7 cm，指尖拿杯子时会被判成没被碰。
- **支撑**：没被碰，且最低点离地面或支撑面顶 3 cm 以内；其余为悬空。
- 检查项：被碰时加速度上限、悬空时必须自由落体、支撑时只允许摩擦减速（μ ∈ [0.2, 1]）、没被碰时累计漂移 3 cm、
  用网格转动惯量的力矩上限、按形状判的转动漂移（对称物体绕对称轴转不算动）、单帧转角跳变、机器人根节点加速度。

用法：

```
T3_GATE=$G $G/venv/bin/python -I t3_dynamics_check.py <motion set dir> <episodes_metadata.jsonl> <support dir|stage> <out.json> [eps]
```

误报率（Tier 1、2 只用来读误报率，不用来调 Tier 3 的任何参数），物体违规帧占比：Tier 1 1.8%，Tier 2 1.4%，Tier 3 best_hm
25.5%，而且 best_hm 的 29 集全部在开头 30 帧内就违规。Tier 1 剩下的大头是 ep29：左脚推带轮行李箱，推完以后箱子自己滚，
不符合只受摩擦减速的假设，属于已知误报。结果文件：`$G/dyn/{tier1,tier2,tier3_hm}_v3.json`。

## 修复：`stages/recovery/tier3/t3_dynamics_post.py`

输入 best_hm，只改物体，人体不动。

1. **对称**：从网格自动找对称等价的旋转（杯子 3 个、球棒 24 个），逐帧取离上一帧最近的等价朝向，画面不变。
2. **锁定**：没被碰（人体层物理检查的 `held`，5 帧内的空隙补上）且落在 best_hm 静置段（`runs/<version>.height_post.json`
   的 `anchors`）里的连续段，只保留一个位姿。悬空又没被碰的帧不锁，保留原运动，交给检查报告：那是手或物体估计断了几帧，
   锁住会让物体悬停。
3. **被碰段**：吸收两端与锁定段之间的位置差和朝向差（线性 + slerp，只有一端有约束时另一端为 0），段内 0.3 s 窗口平滑。
4. **防穿地**：每帧最低点不低于输入和地面两者中较低的那个。

```
python t3_dynamics_post.py <tier3 root> <version> <physics dir> <out version> [eps]
# best_dyn4 是这样生成的：
python t3_dynamics_post.py $T tier3_cari4d_f830_best_hm runs/physics/tier3_cari4d_f830_best_hm tier3_cari4d_f830_best_dyn4
```

## best_dyn4 的结果

数据：`$T/runs/tier3_cari4d_f830_best_dyn4{,_suspect}`，修复记录 `$T/runs/tier3_cari4d_f830_best_dyn4.dynamics_post.json`。
在 `$G` 里重新重定向（门槛档名 `bdyn4`）后检查：

| | best_hm | best_dyn4 |
|---|---|---|
| 物体违规帧占比（29 集） | 25.5% | 6.3% |
| 开头 30 帧就违规的集 | 29 | 3（ep24、25、27） |
| 违规帧为 0 的集 | 0 | 9 |
| 画面对齐 IoU（30 集平均） | 0.700 | 0.697 |

质心改动 p95 在 0.8–11 cm。剩下违规多的集：ep29（带轮行李箱，见上）、ep13（295 帧，多为没被碰时漂移）、ep19（手杖，输入
本身在两个深度之间来回跳，原来就在跟丢名单里）、ep01、ep27、ep24、ep25、ep16、ep02。IoU 下降超过 2 个点的有 ep01 −4.2、
ep04 −4.5、ep07 −2.0、ep19 −2.8。

门槛：p2 表默认用官方支撑面，best_dyn4 不过 ep3、6、7、20、25（hm 不过 ep3、25），都是桌上物体判成悬空。用我们的支撑面（`t3_support_usda.py` 按本档重新生成），best_dyn4 和 hm 都是 30/30 过。

检查链：`$G/dyn/run_dyn1.sh <version> <gate set>`（重定向 → p2 表 → 动力学检查），`$G/dyn/oursup.sh <gate set>`（我们的支撑面
复查），`$T/code/stages/recovery/tier3/t3_align_check.py`（IoU）。结果：`$G/dyn/tier3_bdyn4.json`、`$G/logs/p2_bdyn4.txt`、
`$G/logs/oursup_bdyn4.txt`、`$T/dev/depth_diag/align_dyn4.json`。

## 还没做

- 训练试点：ep15、ep3 在 Tier 2 上能训到 0.8 以上，适合做对照。要不要用 best_dyn4 跑、什么时候跑，由用户定。
- 剩下违规多的几集还没逐集归因。
- 人体只做了跟随物体的平移，没有做时间平滑。
