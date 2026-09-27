# ADR-00002：档位隔离用"净室参数 + 运行时守卫"两层保证

**Status:** Proposed
**Date:** 2026-09-25
**Deciders:** rxzhou；仓库维护者

## Context

规则原文（挑战页 Track 2）："For Tiers 2 and 3, teams are encouraged to propose methods for recovering
better estimates of the object trajectory using anything other than the clean trajectory captions provided in Tier 1."
三档都对照干净多视角物体轨迹评分。官方未说明开发期能否用 Tier 1 做验证或调参，也未说明能否跨档复用策略权重
（全部官方来源已查，包括未合并的规则草案 PR #164；Kaggle 规则页未登录不可见）。

2026-09-25 的 jev 合规检查（对照组：明显违规 0.92、明显合规 0.08）发现：

| 做法 | 违背 Tier 1 条款 | 推理时用了 Tier 1 派生信息 |
|---|---|---|
| Tier 2 推理只读 Tier 2 目录 | 0.06 | 0.06 |
| 用 Tier 1 − Tier 2 估腐蚀上限与步长，做成门限 | 0.72 | 0.49 |
| 在 Tier 1 轨迹生成的噪声上调静止阈值 | 0.50 | 0.81 |
| 用 Tier 1 训出的权重热启动 Tier 2/3 策略 | 0.42 | 0.74 |

同日 v5.4 完成后的 jev 复查（同一组对照）：

| 做法 | 违背 Tier 1 条款 | 推理时用了 Tier 1 派生信息 |
|---|---|---|
| v5.4：参数只由 Tier 2 与物理常识推出 | 0.07 | 0.07 |
| 方法定型后只拿 Tier 1 测一次、不据此回调 | 0.20 | — |

另有一个现成泄漏：`stages/recovery/denoise_v1.py` 在 import 时读 Tier 1 的 `episodes_metadata.jsonl`，
提交用的导出经依赖链间接触发。

## Decision

两层同时成立才算隔离：

1. **净室参数**：Tier 2/3 提交管线里的每个数值参数，只能由该档自己的数据加物理常识推出。
   Tier 1 只允许做一次性测量，不得用来选择或回调参数。Tier 2 现用 v5.4（`cleanroom_params.py`）。
2. **运行时守卫**：提交管线进程启动即调用 `libs/v2d_infra/tier_guard.forbid_tier1()`，此后任何读取
   `tier_1_multiview_caption` 的动作抛 `Tier1AccessError`；只 import 不读数据的纯函数模块（`t2core.py`）。
3. **策略不跨档热启动**，直到官方明确允许。

## Options Considered

### Option A：只保证推理时不读 Tier 1

| 维度 | 评估 |
|---|---|
| 复杂度 | 低 |
| 成本 | 无精度损失（Tier 2 用 v5.3，0.748） |
| 风险 | 高：jev 判违规 0.72–0.81；一旦被判定违规，Tier 2 成绩作废 |

### Option B：净室参数 + 运行时守卫（选定）

| 维度 | 评估 |
|---|---|
| 复杂度 | 中：`tier_guard.py`、`cleanroom_params.py`、`t2core.py` 已实现 |
| 成本 | Tier 2 ADD-AUC 0.748 → **0.707**（−0.041） |
| 风险 | 低：jev 判 v5.4 参数违规 0.07，与合规对照同级 |

### Option C：等组委会答复再定

| 维度 | 评估 |
|---|---|
| 风险 | 答复时间不可控；期间的训练产物可能要重做 |

## Trade-off Analysis

以 0.041 的 ADD-AUC 换掉被判定违规的风险。Tier 2 是三档里权重更高的一档（挑战页："Strong performance on
more challenging tiers will be weighted appropriately"），整档作废的代价远大于 0.041。
若组委会明确允许开发期使用 Tier 1，切回 v5.3 只需换 `T2_POSES` 目录，不动下游。

## Consequences

- 更容易：合规可以用机器证明（守卫 + 测试），不靠自觉。
- 更难：新的 Tier 2/3 方法不能再"用 Tier 1 调一下"；任何看过 Tier 1 结果之后的改动都要单独标注并重新论证。
- 要回看：组委会对"开发期用 Tier 1""只测量一次""跨档热启动"的答复；Tier 3 管线同样要接守卫。

## 验证

- `libs/v2d_infra/test_tier_guard.py`：open、np.load、pq.read_table、pq.ParquetFile、glob 五条路径全部被拦，Tier 2 照常可读。
- 守卫下重导 v5.3，与改前逐位一致（30/30），证明导出全程未读 Tier 1。

## Action Items

1. [ ] `docs/contracts/data.md` 落条目 DATA-I001（档位隔离），验证列指向 `test_tier_guard.py`
2. [ ] Tier 3 管线入口接 `forbid_tier1()`
3. [ ] 邮件问组委会：开发期用 Tier 1、只测量一次、跨档热启动

## 变更记录

- 2026-09-25：初稿（Proposed）。
- 2026-09-26：补入 v5.4 完成后的 jev 复查两行（此前只写在 Option B 与计划记录里）。
