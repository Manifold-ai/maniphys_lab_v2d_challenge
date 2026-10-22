# 契约：轨迹恢复（recovery）

边界：`stages/recovery`：Tier 2 从带噪轨迹、Tier 3 从 exo 视频，估出人体与物体轨迹，按 `data.md` 的 schema 落盘。Tier 1 不经过这一面。

**契约 ID**：`RECOVERY-<层><序号>`，层用 U / C / D / I。Caller 已有 RECOVERY-C001；其余表空白，上游 ADR 未定，条目待填。

## User-facing

| ID | 主题 | 交付 | 验证 | 审阅 | 状态 |
|---|---|---|---|---|---|

## Caller

| ID | 主题 | 交付 | 验证 | 审阅 | 状态 |
|---|---|---|---|---|---|
| RECOVERY-C001 | silhouette pose choice | choose_pose accepts only when the best median is at least 0.5, the gain over current is at least 0.05, and the gap over the second best is at least 0.05, using the plan check order; right_multiply right-multiplies and does not change translation. | `stages/recovery/tier3/test_t3_sil_choose.py` | 待审 | 已实现 |

## Data

| ID | 主题 | 交付 | 验证 | 审阅 | 状态 |
|---|---|---|---|---|---|

## Internal

| ID | 主题 | 交付 | 验证 | 审阅 | 状态 |
|---|---|---|---|---|---|

## 非目标

待填。
