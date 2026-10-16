# 计划：Tier 3 k-fix 参考上重训跟丢的 3 集，ep20 换方块桌面重训（2026-10-16 13:3x MDT，第 1 版）

## 事实（核过的）

- k-fix 方案 4 第一批重新评测（`results/t3kfix/reexport_mf4090.txt`，两道核对都过：包装层恒等、评测器一致）：
  现有策略对新参考，ep24 MP-SR 0.933 → 0.902、ep26 1.000 → 0.984，判据 5 判换；ep0 0.965 → 0.000、ep18 0.862 → 0.013、
  ep29 SP-SR 0.713 → 0.025，判不换。ep20 场景换成交付版方块桌面（参考不变）：SP-SR 0.895 → 0.248，判不换。
- 崩不崩与参考变化的大小对得上（两集，推断）：物体相对机器人根的位置差中位 ep24 0.78 cm、ep0 6.2 cm，网格与 URDF 逐字相同
  （`results/t3kfix/ref_pair_diff_ep{0,24}_mf4090.txt`）。现有策略只在训练时那一份参考上训过，参考变几厘米就跟不住。
- 另一位用户 gb3 的主机位世界系与 k-fix 逐位相同（`results/t3kfix/kfix_vs_gb3_world_ml40_1016.txt`），在 k-fix 参考上训出的策略后面能用到 gb3。
- ep20 现在交的场景是官方 Tier 2 的圆柱桌面，不合 10/12 定的“Tier 3 不用官方 support_surface/”；tier3_v2s 是同一份 v2 参考加交付版方块桌面
  （`results/t3kfix/stage_hf_v2s_mf4090.txt`，重定向间隙 −7.4 mm）。
- mf4090 自 12:05 空闲，可用 80 GB；ml40 的 P2b 评测链在跑，约 13:40 评完。

## 做法

1. 两个新段（`stages/policy/make_var_queue.py`，测试 ALL_OK）：
   - t3pk：ep0、18、29，参考 /runs/motion/tier3_kfix/，run 名 t3-ep<N>-w2048-cap4m-r3a-kfix-mf4090；
   - t3ps：ep20，参考 /runs/motion/tier3_v2s/，run 名 t3-ep20-w2048-cap4m-r3a-v2s-mf4090。
   取法同 t3p3（10/10 那批 v2 训练）：基线取 Tier 2 导出清单、支撑面开关沿用。生成的正式行与 t3p3 同集的行，除 run 名、参考目录、W&B 标签外逐字相同（已逐个核）。
2. mf4090 同步、`fc_config_check.sh` 生成两段的配置核对、`V2D_ARM_DRYRUN=1 arm_var_chain.sh t3pk` 得 DRYRUN_OK 之后起 t3pk；
   t3ps 由服务器上的 `arm_after.sh t3ps …` 在 t3pk 的训练、评测、导出都正常做完、卡空之后自动起（不靠 Mac）。
3. 每条约 2 小时，加冒烟、评测、导出，四条约 23:00 MDT 全部完。

## 判据（训练前登记）

- 判据 5 的同一写法，新旧比的是“新 run 对新参考”与“旧 run 对旧参考”，都是 4096 世界：
  旧 MP-SR > 0 时新 MP-SR ≥ 旧 − 0.05 且新 SP-SR ≥ 旧 − 0.05 记“换”；旧 MP-SR 为 0 时只看 SP-SR ≥ 旧 − 0.05。
  旧值取 10/11 的评测（10/16 的评测器核对显示与 fc_8c778f9 一致）：ep0 0.965/0.992，ep18 0.862/0.938，ep29 0.000/0.713，ep20 0.000/0.895。
- 判据 6 的计数只算参考变了的集（ep24、ep26 加 t3pk 里判“换”的集）；ep20 只换桌子，不计入（12:00 补的解释，待 rxzhou 确认）。够 3 集再打包预演，交不交由 rxzhou 定。
- ep20 的 t3ps 判“换”，就有了合规且不掉分的 ep20；换不换由 rxzhou 定。

## 不在这一步

- 提交（要 rxzhou 点头）；gb3 全量换参考（等交付，先量每集参考变化再定重训哪些）；Tier 1、Tier 2 的 GPU 安排。

## 风险

- 单种子：重训的 run 可能达不到旧 run 的值（10/10 那批是同配方单种子）。不换的集照旧用旧参考与旧 rollout。
- t3pk 有一条失败或发散，arm_after 不起 t3ps（安全方向），次日手动处理。
