# 计划：Tier 1 变体 A 失败世界里，物体先丢还是骨盆先偏（2026-10-07，第 2 版）

第 1 版经 Fable 5.1 审查（GO WITH FIXES，`agent-doc/review-t1-fall-order-plan-2026-10-07.md`），10 条意见都已处理，改动写在第 4 节与审查文件末尾。

用户 10/7：“把 ep18、ep27 的变体和基线导出 4096 世界的轨迹，看失败的世界里是物体先丢还是骨盆先偏。先 plan、review plan 再 execute，高效执行。”
时间一律 UTC-6。只用 Tier 1 的数据，结论只用于 Tier 1。不改第 3 步已登记的判定（Tier 1 不通过）。

## 1. 事实

- 第 3 步 Tier 1 的 S4 不过，超出的 MPPE 全部来自 ep18（+2.68 cm）、ep27（+2.01 cm）。评测 JSON 的均值与标准差显示长尾：变体 ep18 位置误差 8.80±16.19 cm、
  ep27 seed 43 11.73±26.27 cm；变体各 run 的 1 − MP-SR 与“失败:骨盆”占比几乎相等（ep18 0.224 对 0.224）；失败:骨盆两种子平均基线 0.064、变体 0.125
  （`results/r3/eval_spread_t1.txt`，执行记录 `agent-doc/experiments/2026-10-05-step3-recipe-trial.md` 末节）。评测 JSON 没有逐世界数组，这些是推断。
- 8c778f9 评测器在内存里记录逐步、逐世界的 6 个跟踪误差（`rollout.tracking_error`，形状 (步, 世界, 6)：骨盆位置 m、骨盆朝向 rad、手掌位置 m、手掌朝向 rad、
  物体位置 m、物体朝向 rad；`evaluation/harness.py:184–200`、`rollout.py:40–56`），用 checkpoint 自带的阈值事后判失败原因，但**不落盘**；
  对象轨迹 parquet 只有物体位姿，没有骨盆（`rollout.py:59–107`）。
- 阈值（checkpoint 自带）：骨盆位置、骨盆朝向两边相同；手掌两边相同；物体位置 0.10 m 两边相同，物体朝向变体 0.6 rad、基线 1.5 rad。手掌与物体在第 50 步之后才判，骨盆从第 0 步就判。
- 同一 checkpoint 重复评，MP-SR 相差 0.0017–0.0034（闸 G1）：评测不是逐位确定的。
- 一次 4096 世界评测在 mf4090 上约 4–5 分钟；mf4090 空闲，磁盘剩 2.6 GB。

## 2. 假设

- **甲（丢了收不回）**：失败世界里物体先丢（位置 > 0.10 m 或朝向 > 0.6 rad），之后骨盆才超阈值（摔倒）。对应“训练里很少练偏了再拉回来”。
- **乙（为跟紧而失衡）**：骨盆先超阈值，物体在那之前还跟着。对应“动作更激进，牺牲了平衡”。

## 3. 做法

1. `stages/evaluate/eval_dump_errors.py`（容器里跑）：替换 `flash_chord.evaluation.harness.score_reference_tracking`，在调用原函数之前把 `rollout.tracking_error`（float16）、
   误差名、阈值、`active_after_step`、completion 各数组、`non_finite_worlds` 存成 npz，然后用 `runpy` 原样执行 `/workspace/scripts/evaluate_policy.py`，hydra 参数与 `fc_eval.sh` 相同。
   官方代码不改。
2. `stages/evaluate/fc_eval_dump.sh <run> <步数>`：照 `fc_eval.sh` 的守卫（8c778f9 副本、GPU 空闲、policy 有限），输出 `runs/flash_chord/<run>/eval_dump/`（JSON 与 npz，不进 git）。
3. `stages/evaluate/fall_order.py`（容器里跑，numpy）：逐 run 读 npz，按下面第 4 节分类，打表。
4. 顺序：小跑（ep18 变体 seed 42，64 个世界）核对 npz 形状、阈值与 JSON；然后 8 条 run（ep18、ep27 × 基线 s42、s43、变体 s42、s43）各评一次 4096 世界，约 40 分钟；
   最后跑 `fall_order.py`，经 `scripts/dev/record` 落到 `results/r3/fall_order_t1.txt`。
5. 磁盘：npz 每条约 42 MB，8 条约 0.34 GB；mf4090 剩 2.6 GB，够。

## 4. 判据（跑之前登记）

**门**（任一不过就停，查原因，不做分类）：

- 同一条 run 的 npz 与新评 JSON 零误差对齐：npz 的 MP-SR 与 JSON 相差 < 1e-9，误差数组形状等于 JSON 的 (step_count, world_count, 6)（审查 2）。
- 新评与原评测 JSON 的 checkpoint sha256 相同，MP-SR 相差 ≤ 0.01；MPPE 的差只报，参考容差 max(0.3, 3·sd/√N) cm（长尾 run 上 0.3 cm 会误停，审查 1）。
- 8 条 run 的骨盆、手掌、物体位置阈值与 active_after_step 相同，物体朝向阈值变体 0.6、基线 1.5（审查 3）。
- 包装的钩子只被调用一次，npz 里记评测代码的 md5（审查 6）。

**定义**（两边用同一套门槛，物体朝向统一用 0.6 rad，以免变体与基线门槛不同）：

- 失败世界：这个世界的 MP-SR 判失败（逐世界按帧平均的物体位置误差 ≥ 3 cm 或朝向 ≥ 30°，与评测器同一判法）。
- t_obj：第 50 步之后，物体位置 > 0.10 m 或物体朝向 > 0.6 rad 的第一步；t_pel：骨盆位置或骨盆朝向超过 checkpoint 阈值的第一步；t_palm：第 50 步之后手掌超阈值的第一步（只报）。
- 摔倒的失败世界：失败世界里 t_pel 存在的。
- 类别（只对摔倒的失败世界）：物体先（t_obj ≤ t_pel − 25，即至少早 0.5 s）、骨盆先（t_pel ≤ t_obj − 25，或 t_obj 不存在）、同时（相差 < 25 步）。

**结论规则**（按变体两种子、两条 episode 合起来的摔倒失败世界数）：

- “物体先”占 ≥ 60%：支持甲；“骨盆先”占 ≥ 60%：支持乙；都不到：不下结论，照实报告。
- 两条 episode 各自的多数类别必须与合计一致，否则不下结论（ep18 的摔倒世界约是 ep27 的两倍，合计会被它主导；审查 5）。
- 摔倒的失败世界少于 50 个时，只描述不下结论。
- 只报：基线的同样分类与“变体 − 基线”的比例差、没摔的失败世界数（审查 5）；t_pel < 冻结期 + k 的世界数与 t_obj 从第 0 步算的敏感性（这些世界按构造只能判骨盆先或同时，审查 4）；
  骨盆超阈值后到最后一步仍超的比例（像真摔还是暂时走偏，审查 10）；各类别举 3 个世界编号；各类世界的平均位置误差与对 MPPE 的贡献；t_obj 到 t_pel 的间隔分布；摔倒前 2 s 物体位置误差的中位曲线（每 0.5 s 一点）；t_palm 相对 t_obj、t_pel 的先后。

## 5. 风险

- 评测不是逐位确定的：复现门槛给了余量；分类是统计量，单个世界的差别不影响结论。
- 25 步的“同时”窗口是人定的；另报 10、50 步时的分类作敏感性，不据此改结论。
- “骨盆超阈值”不一定是摔倒（也可能是走偏）；另报 t_pel 之后骨盆高度信息拿不到（误差里没有高度分量），只能说“骨盆偏离参考”。

## 6. 顺序与产物

计划经 Fable 5.1 审查后执行。产物：上面三个脚本（带测试：`fall_order.py` 用造的误差数组覆盖三类与边界）、`results/r3/fall_order_t1.txt`、执行记录追加一节、jev 核对结论。
