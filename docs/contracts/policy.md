# 契约：策略训练与回放（policy）

边界：`stages/policy`：在 Isaac Lab 里训练跟随参考运动的策略，产出 checkpoint 与回放。

**契约 ID**：`POLICY-<层><序号>`，层用 U / C / D / I。目前只有 Internal 层的非有限防护条目（训练用的补丁副本
`fc_src/v040_p185_nfg`，ADR-00003 变更记录 2026-10-02；设计与闸见 `agent-doc/plan-ep7-eval-and-guards-2026-10-02.md` 的 B 部分），其余待填。

## User-facing

| ID | 主题 | 交付 | 验证 | 审阅 | 状态 |
|---|---|---|---|---|---|

## Caller

| ID | 主题 | 交付 | 验证 | 审阅 | 状态 |
|---|---|---|---|---|---|

## Data

| ID | 主题 | 交付 | 验证 | 审阅 | 状态 |
|---|---|---|---|---|---|

## Internal

| ID | 主题 | 交付 | 验证 | 审阅 | 状态 |
|---|---|---|---|---|---|
| POLICY-I001 | 非有限防护 | 世界内任一刚体位姿含 NaN / inf、或平移绝对值超过 1e3 m 时，ReconBody 终止判定当步把这个世界判终止，原因记骨盆、骨盆位置误差记 −1、其余误差记 0，不受冻结期屏蔽 | `stages/policy/nfg_test_kernels.py`<br>- test_k1<br>`stages/policy/nfg_env_probe.py`（GPU）<br>- T2 | 待审 | 已实现 |
| POLICY-I002 | 非有限防护 | 世界全部有限时，打了防护的终止判定 12 个输出与上游 v0.4.0 逐位相同 | `stages/policy/nfg_test_kernels.py`<br>- test_k1<br>`stages/policy/nfg_env_probe.py`（GPU）<br>- K1 | 待审 | 已实现 |
| POLICY-I003 | 非有限防护 | 重置时，被重置世界的 `qacc_warmstart`（与 `act`，若有）只要一行里有非有限值就整行清零，有限的行与没被重置的世界逐位不动；被重置的坏世界之后保持有限 | `stages/policy/nfg_test_kernels.py`<br>- test_k2<br>`stages/policy/nfg_env_probe.py`（GPU）<br>- T2<br>- T2n | 待审 | 已实现 |
| POLICY-I004 | 非有限防护 | 交给 `consume_transition` 的 transition 全部有限、观测存得进回放的存储精度；坏的世界步是“终止 1、其余 0”的失败样本，重置后的观测与上下文只在它们自己非有限时才换 | `stages/policy/nfg_test_learner.py`<br>- test_bad<br>- test_env_flag<br>- test_consume | 待审 | 已实现 |
| POLICY-I005 | 非有限防护 | 没有坏的世界步时，清洗函数返回的每个数组与输入逐位相同 | `stages/policy/nfg_test_learner.py`<br>- test_clean | 待审 | 已实现 |
| POLICY-I006 | 非有限防护 | 有坏世界步的日志窗口打一行 `NONFINITE_GUARD_EVENT`；只有学习器判出的世界步累计超过 100、或同一世界连续 3 步坏时，打一行 `NONFINITE_GUARD_STOP` 后停训 | `stages/policy/nfg_test_learner.py`<br>- test_report<br>`stages/policy/nfg_train_inject.py`（GPU）<br>- T6 | 待审 | 已实现 |

## 非目标

待填。
