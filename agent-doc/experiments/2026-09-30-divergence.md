# ep1、ep7（与 ep28）训练发散排查：执行记录

时间一律丹佛时间（MDT）；服务器日志是北京时间，早 14 小时。

## 登记

- 计划 `agent-doc/plan-ep1-ep7-divergence-2026-09-30.md` 第 2 版，独立审查 GO WITH FIXES（无 BLOCKER），按意见修改后登记于 af261bf（09:56 前）。
- 本记录覆盖 CPU 步骤 C1–C5、C2b 与 ep28 看守（M1/M2）。GPU 步骤（G0–G4）另写附录、再审后执行。

## C1–C5（CPU）

| 步 | 结果 | 证据 |
|---|---|---|
| C1 | ep1、ep7 冒烟训练日志末尾的 W&B 历史与摘要段 | `results/diverge/wandb_summary_t1-ep1-w2048-cap4m-mf4090.txt`、`results/ml40/diverge/wandb_summary_smoke-t1-ep7-w2048-cap10m-ml40.txt` |
| C2 | ep1 的 policy：4000 万步全部有限，5000 万步起每份 5892 / 1,207,577 个 NaN；ep7 冒烟最终一份同样 5892 个；其余 73 个已完成的 run 最终一份全部有限 | `results/diverge/ckpt_nonfinite_{ep1,ep7_smoke,last_mf4090,last_ml40}.txt` |
| C2b | 两者非有限的张量完全相同：`state.0021`–`state.0028`（256 / 1024 维，整个是 NaN），`state.0029`、`state.0030`（486 维）里 386 个 | `results/diverge/ckpt_nonfinite_by_tensor_{ep1,ep7_smoke}.txt` |
| C3 | 本地 W&B 历史：ep7 冒烟在环境步 2,406,400 这一行，动作均值、回报与各分项、回报归一化分母、critic loss、骨盆位置误差同时变成 nan，loss scale 262144 → 6.1e-05（一行之内约 32 次减半），下一行回合长度 50 → 23；ep1 在 42,444,800 步（课程第 1 段，voc 0.75）同样，loss scale 4.19e6 → 2.1e-22 → 0，回合长度 60 → 5.9。ep9 冒烟、ep6 正式训练全程有限。W&B 摘要迷你曲线上“第 3/40 个点就 nan”是降采样的假象 | `results/diverge/wandb_local_history.txt`（`stages/policy/wandb_local_history.py`） |
| C4 | 代码（上游 v0.4.0）：BatchNorm 滑动统计按 0.01 做指数平均，更新处没有非有限过滤（`network.py:113–149`，文件里唯一的 isfinite 在第 451 行动作缩放的配置校验）；梯度非有限时参数经 `_apply_adam_if_finite` 跳过更新，但同一步算出的 actor / critic / target 统计量照写（`learner.py:625, 643, 759, 776, 786`）；loss scale 遇非有限梯度就乘 0.5（`update.py:59, 76`）；回放缓冲写入时把观测转成存储精度、采样时转回 float32（`replay.py:265–271, 394–399`）；G1 配方把 `observation_storage_dtype` 设为 float16（`g1_recon_body_flash_sac.yaml:76`，训练默认 float32），训练默认混合精度、`compute_dtype: float16`；观测、终止、重置里没有截断或 nan 处理；方盒建成 `add_shape_box`、圆柱建成 `add_shape_cylinder`（`support.py:105–116`） | `results/diverge/code_facts.txt`（`stages/policy/divergence_code_facts.sh`） |
| C4b | 486 维统计量逐块：所有位置、速度、位置差与目标历史块整块 nan；所有 6D 朝向块、只取自参考的未来根位置（世界系）与参考相位整块有限 | `results/diverge/obs_block_nan_map.txt`（`stages/policy/obs_block_nan_map.py`） |
| C5 | 参考几何（Tier 1）：ep1 吸尘器 385 / 747 帧低于地面超过 5 mm（最深 23.8 mm），对椅背方盒最多嵌入 4.1 mm、不穿板；ep7 熨斗对 1 cm 桌面最多嵌入 0.5 mm、不穿地；ep28 刮水器对两块 2 cm 方盒最多嵌入 10 mm（67、101 帧超过 5 mm），239、209 帧有顶点从板另一侧穿出；三条圆柱对照嵌入 ≤ 2.4 mm。穿地对照：ep17 123 / 440 帧（最深 16.8 mm）、ep22 136 / 719 帧（13.8 mm），两条都训完没事 | `results/diverge/support_penetration{,_floor_controls}.txt`（`stages/retarget/support_penetration.py`） |

## 解读（推断，未经 GPU 复现）

- **放大路径（H4）在代码里成立**：一个批次里只要有非有限的输入，BatchNorm 的滑动统计就永久变成 nan；loss scale 跳步只护住参数，
  统计量照写，之后所有前向输出都是 nan，训练实际停止。这解释了“一处出事、整条 run 死掉”和 loss scale 掉到 0。
- **触发更像是数值很大、而不是仿真状态本身变成 nan**：6D 朝向同样依赖仿真状态，但塌掉后 3 亿步里它的统计量一直有限，
  说明朝向输入从没变成非有限；变成 nan 的全是没有上界的位置、速度类量。回放缓冲按 fp16（最大 65504）存观测，
  物体或机器人被弹飞时速度、位置超过这个范围就存成 inf，进批次后统计量变 nan。这是推断：C3 的记录间隔（5.12 万步）分不出环境侧与学习侧谁先坏，
  要靠 GPU 复现时按 fp32 存储做对照。
- **方盒与发散的关联**：方盒 3 条里 ep1、ep7 发散（分组是事后定的），ep28 见下；圆柱与空支撑面 27 条里已训的都没有。
  参考几何只对 ep28 给出直接的冲突（穿板）；ep7 的参考是干净的，发散要从动力学上找（1 cm 薄板与手、物体的接触）；
  ep1 的穿地在 ep17、ep22 也有，只看几何不足以解释。

## ep28 看守（M1/M2）

- 看守 08:57 起在 mf4090 运行（`runs/tools/ckpt_nonfinite.py`，md5 127d40a4…，与 af261bf 一致）。ep28 09:01 开训。
- 1000–4000 万步的 checkpoint 全部有限；09:19 `.wandb` 首次出现 NaN 字样；09:23 扫到 5000 万步的 checkpoint 有 5892 个非有限参数（与 ep1、ep7 同一模式）。
- 09:29:54 扫到 6000 万步的 checkpoint 同样 5892 个非有限参数，按 M2（连续两份）调用 `fc_stop.sh`，09:30:54 退出码 0；run_record 记 exit 137、stopped；
  训练链记“t1-ep28 失败（退出码 3），继续下一条”，09:30:56 开训 ep29（gpu_check 没有卡住，恢复预案没用上）。按 ep1 的轨迹，这一停省了约 2–3 小时 GPU。
  证据 `results/diverge/ep28_nan_watch_log.txt`、`results/diverge/ep28_chain_and_record.txt`。
- ep28 的目录里留有 state 与 STOP 标记：重训前要先移走 `runs/flash_chord/t1-ep28-w2048-cap4m-mf4090`，否则链按残留跳过。mf4090 的 B 段评测链会对 ep28 记“没有 DONE：不评”。
- 按计划登记的判据：ep28 正式训练出现非有限 checkpoint → 方盒添一例。方盒 3 条全部发散（ep1 正式约 4244 万步、ep7 冒烟约 241 万步、ep28 正式约 4000–5000 万步）；
  其中只有 ep28 是登记之后才观察的一例。圆柱与空支撑面已训的 27 条都没有发散。

## 对 GPU 步骤的影响（写附录时用）

- ep1 与 ep28 都坏在约 4000–5000 万步（课程第 1 段附近），ep7 坏在第 0 段约 241 万步：截断复现 ep1 / ep28 要训到 6000 万步左右，ep7 用冒烟长度即可。
- 最直接的对照是存储精度：同样种子下 `replay.observation_storage_dtype=float32`（显存更大，mf4090 的 400 万 buffer 要重估），看发散是否消失或变成可恢复。
  另一层是几何：加厚方盒、圆柱替换（顶面不变）。两层分开判。

## jev

- 规格 `agent-doc/experiments/2026-09-30-divergence.claims.json`，结果 `results/diverge/jev_claims_divergence.txt`：13 条全部核实（0.71–0.98），5 道对照正常。
- 第 1 轮（`…_run1.txt`）“统计量照写”只有 0.64：证据只摘了单行 `batch_stats=actor_batch_stats`，看不出它不受条件约束。论断原文不改，
  给 `divergence_code_facts.sh` 补上 `learner.py` 三段带行号的原文（`_apply_adam_if_finite` 的文档串“Skip only parameters and Adam moments;
  callers retain all other attempted-update state”，以及三处 `replace(params=…, batch_stats=…)`）后为 0.94；其余各条两轮相差不超过 0.04。
- 参考几何那条（ep1 穿地、ep7 不嵌入）0.71，刚过线：两条序列放在一条论断里，数值由脚本算出，不靠 jev。
