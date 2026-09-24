# Track 2 赛题勘察

2026-09-23 读赛事页面、数据集 README 与官方 toolkit 的公开内容整理。引号内是原文。
**标「待核对」的条目来自页面摘要，本仓尚未亲自打开文件确认。**

来源：

- 赛事页：https://nvidia-isaac.github.io/video_to_data/v2d_challenge/
- 数据集：https://huggingface.co/datasets/nvidia/video_to_data_challenge/tree/main/track_2
- 官方 toolkit：https://github.com/nvidia-isaac/video_to_data/tree/release/0.2.0/
- 联系：v2d_challenge@nvidia.com

## 赛题

- 问题："How much reconstruction error can be tolerated?"
- 输入：第三人称 4D 人-物交互数据，分三个质量档位。
- 输出：训练好的机器人策略。
- 本体与仿真器固定："Embodiment and simulator are fixed and provided: G1 + Dex3"。
- 三档：
  - Tier 1 "Clean multi-view caption, representing an upper bound for upstream reconstruction"
  - Tier 2 "Synthetic corruption: jitter, dropout, and contact errors are sampled from Track 1's error distributions"
  - Tier 3 "Off-the-shelf reconstructions. Today's best practice"，参考方案 CARI4D。
- 档位隔离："For Tiers 2 and 3, teams are encouraged to propose methods for recovering
  better estimates of the object trajectory using anything other than the clean
  trajectory captions provided in Tier 1"。
- 指标："object-tracking accuracy using AUC, SP-SR, MP-SR, and MPPE as defined in the
  CHORD manuscript"，每档分别计分。**定义待核对。**
- 计分："Track 2 is scored separately at each of its three input tiers, because each
  tier supplies a different reference trajectory and scores across tiers are not comparable"。
- 提交："Teams will submit recorded evaluations of their trained policies using the
  eval_robotic_grounding.py script provided to produce the artifact for submission"。
  **这个脚本在 release/0.2.0 的公开页面摘要里没有出现，位置待核对。**

## 时间与提交规则

| 事件 | 时间 |
|---|---|
| 报名开启、数据发布 | 9 月 21 日（页面摘要写作 2025，结合其余日期应为 2026，待核对） |
| 榜单冻结 | 2026-11-04 17:00 EST |
| 公布结果 | 2026-11-12，CoRL 2026 tutorial |

- 每队每周最多 5 次提交，冻结前最后三天不限。
- 榜单反映一次新提交最多需要 24 小时。
- 获奖资格：有效的最终提交、承诺以研究许可发布代码、技术报告。

## 数据集（Track 2）

摘自 `track_2/README.md`：

- 同一批 **30 个 episode**，**22,990 帧**，各档之间 episode 顺序、任务、exo 相机 RGB、
  拟合地面、G1 支撑面都相同。
- 每个档位目录是一份完整的 **LeRobot v2.1** 数据集：`README.md`、`meta/`、`data/`、
  `videos/`、`mesh/`。
- Tier 1（`tier_1_multiview_caption/`）：原始 SOMA-X 人体重建，原始物体位姿与对齐网格。
- Tier 2（`tier_2_synthetic_noise/`）：人体与物体轨迹都经合成扰动，网格为原始网格。
- "Participants should select one tier directory as their dataset root rather than
  combining tiers"；episode 与全局帧号刻意对齐，用于逐帧比较。
- "The observation.images.exo_camera video stream is byte-identical across tiers and is
  the monocular input participants should use for reconstruction."
- 分阶段发布：目前只有 Tier 1 与 Tier 2 两个目录，Track 2 目录总计约 2.16 GB。

## 官方 toolkit（robotic_grounding）

摘自 release/0.2.0 的 README 摘要，**待核对**：

- 仿真 Isaac Lab 2.3.1，训练 RSL-RL（PPO）。README 注明当前版本 "may require longer
  training to converge"，约 2 小时训练的加速版计划 2026 年 9 月发布。
- 管线阶段：Load（MANO 前向运动学出 parquet）→ URDF → Retarget（Sharpa / Dex3 / G1）→
  Support（支撑面）→ Vis → Plan（由 Dex3 末端路径生成 G1 全身轨迹）。
- 注册的 Isaac Lab 任务包括 `SonicG1-ReconBody-v0`、`SonicG1-ReconHand-v0`，以及
  ReconHand 的三阶段变体（warm-up → contact grounding → finetune）。
- 训练入口 `scripts/rsl_rl/train.py`，评测入口 `scripts/rsl_rl/eval.py`，零动作基线
  `scripts/rsl_rl/dummy_agent.py`。
- 运动数据路径约定 `assets/human_motion_data/<dataset>/<dataset>_processed/sequence_id=<seq>/robot_name=<robot>/`。
- 环境：NVIDIA driver 580.126.09 / CUDA 13.0；RTX A6000、L40S 验证过；Blackwell 不支持
  HOI 重建。

## 待核对清单

- `eval_robotic_grounding.py` 在哪、输入输出是什么。
- AUC / SP-SR / MP-SR / MPPE 在 CHORD 论文里的定义。
- 哪个 Isaac Lab 任务对应 Track 2 的评测。
- LeRobot v2.1 数据集与 toolkit 的 parquet 分区之间怎么转换。
- Tier 3 数据何时发布、形态如何。
