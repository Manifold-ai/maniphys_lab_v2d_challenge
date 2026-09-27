# ADR-00001：策略训练栈用 FlashCHORD，Isaac Lab ReconBody 作备选

**Status:** Proposed
**Date:** 2026-09-25
**Deciders:** rxzhou；仓库维护者

## Context

Track 2 固定本体与仿真器（G1 + Dex3），比的是重定向与策略学习。上游 toolkit 提供两套训练栈：

- **Isaac Lab ReconBody**（`SonicG1-ReconBody-v0`，RSL-RL PPO），2026-09 之前唯一的选项；
- **FlashCHORD**（v0.4.0 于 9/23 新增，Newton / Warp / JAX，FlashSAC 与 PPO），G1 配方为 FlashSAC。

约束与事实：

| 事实 | 来源 |
|---|---|
| 最坏情况要训 90 个策略（3 档 × 30 条；跨档热启动官方未表态，默认不做） | 规则解读，见 ADR-00002 |
| 训练窗口约 5 周（封榜 2026-11-04） | 挑战页 |
| mf4090：1× RTX 4090 24 GB，共用；ml40：1× L40S 48 GB（空闲 45,458 MiB），已到位，镜像等 docker 存储迁移 | 2026-09-26 只读核实 |
| Isaac Lab ReconBody：4096 env，3.34 s/iter，20k iter ≈ **18.6 小时/策略**（4090） | 早期 sweep 实测 |
| FlashCHORD：2048 个并行环境，后半段回归稳态 **≈ 50,500 env 步/秒**（日志末行 44,156 是含编译的累计均值），3.5 亿步 ≈ **1.9–2.2 小时/策略**（4090，replay buffer 缩到 100 万条，推算） | `runs/logs/fc_smoke_w2048.log` |
| FlashCHORD 默认 buffer 1000 万条在 4090 上 256 世界即撞 XLA 内存上限崩溃；官方文档要求 48 GB 且空闲 ≥ 46,000 MiB | `runs/logs/fc_smoke_w256.log`、上游 README |
| FlashCHORD 能直接读我们的 motion_v1 parquet；support 查找规则与 Isaac Lab 相同，找不到时报错 | A1 冒烟 |
| FlashCHORD 自带 `evaluate_policy.py`，输出 add_auc、mppe_cm、chord_sr、spider_sr_uncentered、maniptrans_sr | A1 评测冒烟 |
| FlashCHORD G1 配方默认 `source_frame_playback: true`、仿真 50 Hz：30 fps 参考按 1.67 倍速播放 | 配置与加载实测 |
| 官方提交脚本 `eval_robotic_grounding.py` 未发布；排行榜用哪套栈评测未说明 | 挑战页、上游仓库 |

## Decision

策略训练默认用 **FlashCHORD 的 G1 FlashSAC 配方**，满配训练放在 48 GB 卡上。
4090 只做冒烟、调试与缩小 buffer 的对照。Isaac Lab ReconBody 保留为备选，镜像和脚本不删。

## Options Considered

### Option A：FlashCHORD FlashSAC（选定）

| 维度 | 评估 |
|---|---|
| 复杂度 | 中：新栈，Hydra 配置；已有包装 `scripts/dev/in-flash-chord`、`stages/policy/fc_train.sh` |
| 成本 | 约 1.9–2.2 小时/策略（4090 小 buffer 推算）；90 个 ≈ 170–200 卡时，按此速度 1 张卡约 7–8 天；L40S 满配时长未测 |
| 可扩展性 | 受显存限制：满配需 48 GB；4090 只能小 buffer |
| 熟悉度 | 低：9/23 才发布 |

**Pros**：快约 8 倍；自带非对称 critic（`critic_context`）；评测器直接给出比赛指标；上游主推的新方向。
**Cons**：4090 跑不了满配；发布时间短，坑未知；默认 1.67 倍速播放是否与官方评测一致不明。

### Option B：Isaac Lab ReconBody PPO

| 维度 | 评估 |
|---|---|
| 复杂度 | 中：已跑通 200 iter 冒烟，官方 VOC 课程配方明确 |
| 成本 | 18.6 小时/策略；90 个 ≈ 1,700 卡时，需 3–4 张卡全程 |
| 可扩展性 | 4090 可跑满配（4096 env 仅 9.3 GB） |
| 熟悉度 | 中 |

**Pros**：4090 即可满配；PhysX 行为更成熟。
**Cons**：时间预算装不下 90 个策略；没有现成的比赛指标评测器（环境里的指标只进 TensorBoard，不落盘）。

## Trade-off Analysis

决定性因素是时间：90 个策略 × 18.6 小时超出窗口，FlashCHORD 把单策略压到约 2 小时，
留出调参与失败重跑的余量。代价是依赖 48 GB 卡，以及一个未证实的风险：官方评测若不用 FlashCHORD、
或按真实时长播放，训练与评测会有口径差。缓解：第一个完整策略出来后，同一条序列在两种播放速度下各训一次，
并在 `eval_robotic_grounding.py` 发布当天对照。

## Consequences

- 更容易：批量训练在 1 张 L40S 上可完成；本地就能算比赛指标。
- 更难：4090 上的结果不能代表满配效果；需要维护两套容器。
- 要回看：`eval_robotic_grounding.py` 发布后的评测栈与播放速度；FlashCHORD 满配在 L40S 上的实际时长
  （当前 1.9–2.2 小时是 4090 小 buffer 的推算）；官方是否提供 Tier 间迁移的说法。

## Action Items

1. [ ] 4090 上用 ep20 Tier 1 跑完整 3.5 亿步（buffer 尽量大），同时跑官方 snack_box 样例作对照
2. [ ] L40S 满配复跑 ep20，对比 buffer 大小的影响，确认单策略时长
3. [ ] 播放速度对照：`source_frame_playback` true / false 各训一次
4. [ ] `docs/contracts/policy.md` 补条目：训练产物、配置、种子、参考来源的落盘要求

## 变更记录

- 2026-09-25：初稿（Proposed）。
- 2026-09-26：吞吐改用稳态值（≈ 50,500 步/秒，1.9–2.2 小时/策略）；机器改为 mf4090 / ml40；评测字段名按 FlashCHORD 源码更正。
