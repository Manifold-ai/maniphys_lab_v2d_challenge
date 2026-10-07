# 审查：Tier 1 失败世界的先后顺序计划第 1 版（Fable 5.1，2026-10-07）

结论：**GO WITH FIXES**。审查原文（英文）要点与处理如下；处理后的计划是第 2 版。

| # | 级别 | 意见 | 处理 |
|---|---|---|---|
| 1 | must | 0.3 cm 的 MPPE 复现门槛对长尾 run 不成立（ep27 变体 s43 的 sd 26 cm，4096 世界均值的标准误约 0.41 cm），会误停 | MP-SR ≤ 0.01 是唯一硬门；MPPE 差只报，参考容差 max(0.3, 3·sd/√N)；另核 checkpoint sha256 相同 |
| 2 | must | 没核 npz 与同一次评测 JSON 的对齐 | 加：npz 的 MP-SR 与新评 JSON 相差 < 1e-9，误差数组形状 = (step_count, world_count, 6) |
| 3 | must | 各 run 的阈值被默默读进来用 | 加：8 条 run 的骨盆、手掌、物体位置阈值与 active_after_step 相同，物体朝向阈值变体 0.6、基线 1.5，否则停 |
| 4 | should | 冻结期偏差：t_pel < 75 的摔倒按构造只能判骨盆先 | 只报这类世界的个数，另算 t_obj 从第 0 步起的敏感性 |
| 5 | should | 结论分不清“变体特有”还是“ep18 本来就这样摔” | 只报“变体 − 基线”的比例差、没摔的失败世界数、逐 episode 的比例；两条 episode 的多数类别须与合计一致才下结论 |
| 6 | should | 钩子调用次数没计 | 计数，≠ 1 就非零退出；npz 记评测代码 md5 |
| 7 | nit | `step > active_after_step` 的比较方向 | 已核：评测器 `harness.py:595` 也是 `step > criteria.active_after_step[index]`，一致 |
| 8 | nit | 包装目录留在 sys.path | 去掉，sys.path[0] 只放官方脚本目录 |
| 9 | nit | 测试没覆盖“同时”与摔倒世界太少 | 补上，另加 sha256 不符的停止测试；共 7 项，容器里全过 |
| 10 | nit | 报骨盆超阈值后是否一直不回来（真摔还是走偏），各类别举 3 个世界编号 | 都加进只报项 |

审查另确认：方法回答得了问题；monkeypatch 加 runpy 的写法与 10/2 的 `stages/evaluate/diag_rollout.py` 相同、那次跑通过；hydra 的 config_path 按 `__main__` 里任务函数的文件解析，不是新风险；
一次 64 世界小跑加 8 × 4–5 分钟是回答这个问题的最小开销。
