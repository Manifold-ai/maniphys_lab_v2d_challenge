# 计划：ep7 两份最后有限的 checkpoint 的评测（A）与训练的非有限防护（B）

第 1 版，2026-10-02。用户 10/2 的决定（原话）：“先评，同时写防护的计划”。事实依据：`agent-doc/experiments/2026-10-02-ep7-divergence-analysis.md`（jev 19 条核实）。
时间一律 UTC-6。A 部分先成文、先审、先跑；B 部分在本文件第 2 版里补全，另行审查，审过之前不动训练代码、不重训。

## A. 评两份最后有限的 checkpoint

### A.1 要回答的问题

- Q1：t1-ep7 的 130,004,992 步、t2-ep7 的 140,005,376 步这两份 policy，在评测条件（VOC 为 0、确定性动作、4096 世界）下是什么分数，够不够候选条件。
  用不用它们先凑齐 30 条，由用户看了结果再定；这一步不导出、不打包、不上传。
- Q2：评测里会不会出现崩掉的世界。出现的话崩在参考的哪一帧附近。

### A.2 做法

| 机器 | run | 步数 | 评测运行时 | 何时跑 |
|---|---|---|---|---|
| ml40 | `t2-ep7-w2048-cap10m-p185-ml40` | 140005376 | `/lab_data/rxzhou/v2d/fc_src/fc_8c778f9` | GPU 空着，审过就起 |
| mf4090 | `t1-ep7-w2048-cap4m-p185-mf4090` | 130004992 | `~/v2d/fc_src/fc_8c778f9` | 等诊断链 `runs/logs/diag2_mf4090.log` 出结束行之后 |

每台在 tmux 里跑一条 `stages/evaluate/ep7_ckpt_eval.sh <run> <步数> ep7_eval_<机器>`（新脚本，只新增文件，不替换服务器上任何现有文件）：

1. 先查：日志不存在、policy 文件在、两份源码副本在、这份 policy 没有非有限参数（规矩一）。
2. 等 GPU 空出来（最多 7200 秒；mf4090 另等诊断链的结束行），再用 8c778f9 副本跑 `stages/policy/fc_eval.sh`（4096 世界），
   与方盒评测链是同一条命令、同一运行时，结果落成 `results/day2/eval_<run>_s<步数>.txt`。
3. 评测失败，或评测 JSON 的 `non_finite_worlds` 非空：再跑一次取证 rollout `stages/evaluate/blowup_rollout.py`（4096 世界，挂 v0.4.0 + #185 副本，
   与 `diag_rollout.py --palms` 用同一个手掌记录器），把物体与两只手掌逐步的位置原样存成 npz（不清零），并打印崩掉的世界数与第一次出问题的帧的分布。
   评测成功且没有非有限世界就不跑取证。
4. 日志最后一行 `EP7_EVAL_DONE（评测 …；非有限世界 …；取证 …）`。

之后在 Mac 上拉回 `results/`，用 `stages/evaluate/batch_verdict.py stages/policy/queues/<机器>_ep7ckpt.expect.tsv <结果目录> --steps <步数>` 按批量判据出判定（期望表各只有 ep7 一行，取自方盒期望表）。

为什么不直接用 `diag_rollout.py --palms`：它存盘前把非有限世界的手掌清零，评测器也把这些世界的物体位姿清零，崩之前的轨迹看不到；
评分阶段若因有世界被判终止而报错，它不存盘。mf4090 的诊断链还在用它，这次不改它。

### A.3 判据（跑之前登记）

- **A-1 评测完成**：日志最后一行是 `EP7_EVAL_DONE`，且评测为“成功”。评测失败（例如评测器报 must disable task failure termination）本身是 Q2 的一个结果，照实记。
- **A-2 候选条件**（与导出链对候选的要求相同）：评测 JSON 里 `world_count` 为 4096、`non_finite_worlds` 为空、`step_count` 为 896、checkpoint sha256 等于这份 policy 文件。
  满足才说“这份 policy 可以作临时候选”；不满足就说不可以。满足也不自动使用，等用户定。
- **A-3 质量只报数**：chord_sr、MP-SR、SP-SR、ADD-AUC 与不动基线之差、MPPE，以及 `batch_verdict.py` 的判定。它们不改变 A-2 的结论。
  t2-ep7 的分数对照的是 Tier 2 v5.4 参考，不和 Tier 1 比，也不拿来调方法。
- **A-4 触发**：
  - 取证 rollout 报出崩掉的世界数大于 0：报世界数、第一次出问题的帧的最早、中位、最晚与最集中的几帧。只描述，不据此下“触发就是薄桌面”的结论；
    要下这个结论，另需对照（例如把桌面加厚后同一份 policy 的同样 rollout），那是 B 之后的事。
  - 两份都没有崩掉的世界：结论只能是“这两份 policy 在 VOC 为 0 的 4096 × 896 步里没有出现”，不能推出训练里不会再出现。触发仍未知，留给 B 的事件日志。
- 结论的范围：两份 policy 分别只训到 VOC 0.25、刚进 0.1，评测在 VOC 为 0 下跑，与训练里出事时的条件不同。

### A.4 风险与守卫

- 与在跑的链抢 GPU：脚本每次用 GPU 之前都等它空出来；mf4090 那条另等诊断链的结束行。ml40 上所有链都已结束（14:30 的快照里没有长链标记）。
- 改动在跑的链要用的文件：不改。新文件只有 `stages/evaluate/{ep7_ckpt_eval.sh,blowup_rollout.py}`，`diag_rollout.py`、`diag_palms.py`、`fc_eval.sh` 原样。
- 磁盘：评测 JSON 很小；取证 npz 估计 100–250 MB（896 帧 × 4096 世界 × 物体 1 个、手掌 2 只的位置，加评测器自己的逐步误差）。mf4090 可用 5640 MB（14:30）。
- 16:47 的收尾任务（拉导出、打包、只跑 `--dry-run`）不受影响：它只读两台的导出表，两档都缺 ep7，按决策表列缺项。
- 不往 Kaggle 上传任何东西。

### A.5 测试

- `stages/evaluate/test_ep7_ckpt_eval.py`（6 组，Mac 上全过）：没有非有限世界不跑取证；有非有限世界或评测失败才跑，且取证挂的是 #185 副本、走 GPU；
  五种拒绝；等别的链结束；GPU 一直被占则停；试跑不写日志。
- `blowup_rollout.py` 只能在容器里跑。起链前在 ml40 上用 16 个世界试跑一次（占 GPU 约 1 分钟，ml40 空着），确认它能存盘、打印 `BLOWUP_ROLLOUT_OK`。

## B. 训练的非有限防护与 ep7 重训

第 2 版补全后另审。
